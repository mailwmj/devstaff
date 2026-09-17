---
name: site-check-v3
description: v3 只读验证。生成与校验检查计划/报告，按 L0-L5 轴只读验证核心任务和相称的静态、错误、移动端或再次打开行为，不修改源码。
---
# v3 验证

检查轻量、确定、机器可读，本身不启动浏览器。先用 `check.py` 生成计划或校验报告协议，再按计划在浏览器里只读取证；`site-check-v3` 的浏览器验证由宿主在独立 Checker 上下文完成。

## 协议

`check.py plan PROJECT --contract .v3/design/surface-brief.md [--changed-from REF]` 读合同与源码、算出 SHA-256 指纹，产出本轮要检查的轴、门禁顺序和（若给定 `--changed-from`）失效轴。`REF` 支持两种输入，无歧义：可读的旧计划/报告 JSON（直接取其指纹），或项目所属仓库中可解析的 git revision（分支/标签/提交，按该 revision 重算合同与源码指纹再比对本轮）。既非可读报告也非可解析 revision 的 `REF` 机器可读报错并保守升级 `guided-core`，绝不谎称无变化。git 解析仅用 stdlib 子进程、确定、不启浏览器。`check.py validate-report PROJECT REPORT.json` 校验一份检查报告是否符合协议，返回 `valid / overall / invalidated_axes / reverify / reverify_vas / browser_blocked / errors`，供 `state.py verify --report` 采用。

六个层级、八条轴：

| 层级 | 轴 | 浏览器 |
| --- | --- | --- |
| L0 | `contract` | 否 |
| L1 | `static_build` | 否 |
| L2 | `core_task` | 是 |
| L3 | `negative_path` | 是 |
| L4 | `visual_desktop` / `visual_mobile` | 是 |
| L5 | `reopen` / `risk` | 是 |

guided 的下限是 `guided-core`（contract + static_build + core_task）外加一条最可能失败路径；strict 额外要求 `reopen` 与 `risk` 并独立验证。范围边界不明确时升级到 `guided-core`，不悄悄缩小覆盖。

## 失败与复验规则

- **静态门禁**：L0/L1 失败不启动浏览器；浏览器轴必须为 `not_run`，overall 为 `blocked`。
- **视觉复验范围**：视觉轴失败只复验受影响页面/状态/视口（报告里记 `failed_vas`），不重跑全部视口。
- **哈希失效**：合同 SHA-256 改变使全部轴失效；源码 SHA-256 改变使 L1-L5 失效（合同在 `.v3` 下单独指纹，源码改不动 L0）。
- **轴依赖**：一条轴失败使其依赖轴需要复验（L0→全部，L1→L2-L5，L2→L3-L5，L3/L4→L5）。
- **模式**：guided 可诚实 `limited`；strict 不得 `limited`，且 `verified` 必须带 `independent`。`independent` 只在宿主用独立 Checker 上下文实际完成检查后成立；做不到时返回 `blocked`，不自行打标。

## 五字段回执

`status / summary / artifacts / evidence / limitations` 返回发现、证据和限制后停止，不修源码、不改需求、不宣布交付。状态使用 `verified`、`limited` 或 `blocked`：

- `verified`：本轮核心任务已实际完成并有证据。
- `limited`：核心任务已实现，但有明确未验证项；允许 guided 交付，必须披露限制。
- `blocked`：核心任务失败或缺少使结论成立的关键证据。

存在 `.v3/design/surface-brief.md` 时，以其中适用的页面、状态、视口和 `VA-*` 为项目特定依据；视觉检查调用 `site-design-v3` 的只读审查分支，不重新发明方向。先按风险选择最小充分范围：局部修改只查静态和受影响结果；普通首版查核心任务成功路径与一个最可能失败反例；严格项目查核心任务、关键反例、适用视口、再次打开和权限/隐私风险并独立取证。
