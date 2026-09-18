---
name: site-check
version: 1.0.0
description: 只读验证。生成和校验检查计划与报告，按 L0-L5 轴只读验证核心任务和相称的静态、错误、移动端、再次打开行为，不改源码。
---
# 网站检查与验证

检查本身很轻，结果确定且机器可读，自己不启动浏览器。先用 `check.py` 生成计划或校验报告协议，再按计划在浏览器里只读取证；浏览器验证由宿主在独立的 Checker 上下文里完成。

## 协议

`check.py plan PROJECT --contract .site/design/surface-brief.md [--changed-from REF]` 读合同和源码，算出 SHA-256 指纹，给出本轮要查的轴、门禁顺序，以及（给了 `--changed-from` 时）哪些轴已失效。`REF` 有两种输入，不会混淆：可读的旧计划或报告 JSON（直接用它的指纹），或者项目所在仓库里能解析的 git revision（分支、标签、提交，按该 revision 重算合同和源码指纹再比对）。两种都不是时，机器可读地报错，并保守升级到 `guided-core`，不谎称没有变化。git 解析只用 stdlib 子进程，结果确定，不启动浏览器。`check.py validate-report PROJECT REPORT.json` 校验一份检查报告是否符合协议，返回 `valid / overall / invalidated_axes / reverify / reverify_vas / browser_blocked / errors`，供 `state.py verify --report` 使用。

六个层级、八条轴：

| 层级 | 轴 | 浏览器 |
| --- | --- | --- |
| L0 | `contract` | 否 |
| L1 | `static_build` | 否 |
| L2 | `core_task` | 是 |
| L3 | `negative_path` | 是 |
| L4 | `visual_desktop` / `visual_mobile` | 是 |
| L5 | `reopen` / `risk` | 是 |

`guided` 的下限是 `guided-core`（contract + static_build + core_task）再加一条最可能失败的路径；`strict` 还要查 `reopen` 和 `risk`，并且独立验证。范围边界说不清时按 `guided-core` 查，不要悄悄缩小覆盖。

## 失败与复验

- **静态门禁**：L0/L1 没过就不启动浏览器；浏览器轴必须记为 `not_run`，overall 为 `blocked`。
- **视觉复验范围**：视觉轴没过只复验受影响的页面、状态和视口（报告里记 `failed_vas`），不重跑全部视口。
- **哈希失效**：合同 SHA-256 一变，所有轴失效；源码 SHA-256 一变，L1-L5 失效（合同在 `.site` 下单独指纹，改源码不影响 L0）。
- **轴依赖**：一条轴没过，依赖它的轴要复验（L0→全部，L1→L2-L5，L2→L3-L5，L3/L4→L5）。
- **模式**：`guided` 可以如实返回 `limited`；`strict` 不能 `limited`，而且 `verified` 必须带 `independent`。`independent` 只有在宿主用独立 Checker 上下文真的查过之后才算数；做不到就返回 `blocked`，不要自己打标。

## 五字段回执

返回 `status / summary / artifacts / evidence / limitations`，说完发现、证据和限制就停下，不改源码、不改需求、不说交付。这些字段最终会变成用户看到的话，措辞按 `AGENTS.md` 的《说人话》。`status` 用 `verified`、`limited` 或 `blocked`：

- `verified`：这轮核心任务真的跑通了，有证据。
- `limited`：核心任务实现了，但有明确没验证的部分；`guided` 可以据此交付，但要把限制说清楚。
- `blocked`：核心任务没过，或者缺了让结论成立的关键证据。

有 `.site/design/surface-brief.md` 时，以里面适用的页面、状态、视口和 `VA-*` 为依据；视觉检查走 `site-design` 的只读审查分支，不重新发明方向。先按风险选最小够用的范围：局部修改只查静态和受影响的结果；普通首版查核心任务的成功路径加一个最可能失败的反例（长文本不换行、0 条数据、320px 窄屏这类情况也要试）；严格项目查核心任务、关键反例、适用视口、再次打开和权限隐私风险，并独立取证。
