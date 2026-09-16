---
name: site-check
description: 只验收或独立检查已有网站和 Web 应用的构建、核心任务、视觉及再次打开行为，输出有证据的结果但不修复源码；也由 site-builder 在正式交付前调用。“检查并修复”由 site-builder 编排。
---
# 网站独立检查

## 协作契约

交接或恢复会话时读 [上下文契约](../site-brief/references/context-contract.md)。检查档位、证据类型、浏览器降级、矩阵和修复闭环以 [验证规则](references/verification.md) 为准；本 Skill 不复制命令级校验。

| 字段 | 本 Skill 的接口 |
| --- | --- |
| `reads` | 冻结源码、brief、页面设计合同、实施计划、`state.py show` 与验证规则；第三方无状态项目不初始化 |
| `writes` | 仅 `.site/checks/` 内自己的凭据；不写源码、状态或恢复快照 |
| `schema` | `passed / failed / incomplete / blocked`；矩阵含 profile、browser、逐项 axis/status/blocking/evidence |
| `handoff` | 矩阵与发现交回 `site-builder`；失败供受控修复，直接验收到报告为止 |
| `evidence` | 命令/检查 `check_id`、产物哈希、操作记录与页面/状态/视口 |

## 执行

1. **确定对象和范围。** 读取源码、原生说明、`.site` 记录和当前状态；页面设计合同是方向、页面、状态和视觉验收的共同接口。
2. **建立矩阵。** 按 [验证规则](references/verification.md) 选择 `smoke`、`targeted` 或 `full`，声明浏览器能力，并把本轮适用承诺映射到检查项。`full` 的五个轴为 `static_build / core_task / visual_desktop / visual_mobile / reopen`。
3. **执行检查。** 先跑项目原生静态/构建检查，再覆盖核心任务、关键视觉状态和再次打开；不能由当前能力证明的项保持 `not_run`，不根据源码推定通过。
4. **视觉审查。** 有真实浏览器时调用 `site-design` 的只读分支；没有真实渲染时保留视觉轴的 `not_run`，不得补造方向匹配结论。
5. **报告与交接。** 每项记录预期、实际、状态、影响和证据，生成内容寻址矩阵凭据并回传 `check_id`。失败只交回 `site-builder` 修复，Checker 不改源码。

## 协作回执

返回 `passed | failed | incomplete | blocked`、检查矩阵与 `check_id`、阻断项、非阻断建议、实际入口、未执行项及恢复条件。连续两次复验没有新证据时返回 `blocked`。
