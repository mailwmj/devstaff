---
name: site-design
description: 为网站或 Web 产品制作结构/视觉体验稿、页面设计合同，或进行只读视觉审查。适用于新页面、整体改版、既有界面局部设计、截图/网址参考、流程状态验证，以及由 site-builder 或 site-check 发起的设计工作；不修改正式业务源码。
---
# 网站设计与只读审查

## 协作契约

交接或恢复会话时读 [上下文契约](../site-brief/references/context-contract.md)。确认模型以 [领域术语](../CONTEXT.md) 为准，状态记录以 [状态协议](../site-brief/references/state.md) 为准；本 Skill 只描述设计职责和分支。

| 字段 | 本 Skill 的接口 |
| --- | --- |
| `reads` | 活跃源码、真实内容/素材、brief、状态、参考输入；只读审查沿用已有页面设计合同 |
| `writes` | 设计分支写页面设计合同与体验稿；只读审查分支不写项目 |
| `schema` | `draft_ready / structure_confirmed / visual_confirmed / flow_decided / review_complete / needs_user / blocked` |
| `handoff` | 选定方向与合同交回调用者实施；只读发现交回 Checker；业务未知交回 `site-brief` |
| `evidence` | 方向来源、参考适配依据、取舍、真实渲染页面/状态/视口；未查看项为 `not_run` |

目标是得到一个由项目事实支撑、能实际查看、可交给实现和验收的设计结果。正式页面、共享样式和业务代码由 `site-builder` 修改；本 Skill 不授予开发权限，也不宣布交付。

## 先选唯一分支

| 本轮任务 | 参考入口 | 必须得到 | 停止条件 |
| --- | --- | --- | --- |
| 新页面、整体改版、核心流程或信息结构变化 | [设计上下文](references/design-context.md)、[工具链](references/design-toolchain.md)、[视觉方向](references/visual-direction.md)、[页面设计合同](references/surface-brief.md)、[体验稿](references/prototype.md)、[工艺审查](references/craft-review.md)；方向确定后按需读 [设计 token](references/design-tokens.md) | 推荐结构；结构确定后默认两个母题层不同的视觉方向；实际渲染证据；同一份 `surface-brief.md` | 缺少高影响事实；未实际查看；结构或视觉尚待用户决定 |
| 成熟系统中的局部页面或低风险样式修复 | [设计上下文](references/design-context.md)、[工艺审查](references/craft-review.md) | 现有基线、受影响项和最小修正合同 | 不重新发明方向或第二套 token 系统 |
| 流程、状态或操作顺序实验 | [设计上下文](references/design-context.md)、[页面设计合同](references/surface-brief.md)、[体验稿](references/prototype.md) | 可点击状态演示、保留/改变规则、失败与再次打开结果 | 业务语义不明时交回 `site-brief` |
| 截图、图片或网址参考 | [参考输入](references/reference-input.md) | 区分 `replicate | adapt | behavior-only`，记录可见事实与未知项 | 未实际查看就不能声称还原 |
| 只读视觉审查 | [工艺审查](references/craft-review.md) 和已有页面设计合同 | 带页面/状态/视口证据的发现 | 不写项目、不修改确认状态、不启动需求访谈 |

不要预读其他分支的参考。任务扩大时明确切换分支，再加载新增参考。

## 所有分支的硬约束

1. 先看活跃代码、真实内容、品牌和用户材料；行业模板不能创造首版功能。
2. 用 `required / recommended / confirm / excluded` 约束范围；高风险后果必须回到 `site-brief`。
3. 默认给一个有依据的推荐结构；只有结构会改变主任务或重要风险时才比较多个。结构选择和视觉选择按 [确认模型](../CONTEXT.md) 与状态协议分别记录。
4. 候选必须在母题层不同，不能只换肤；检索结果只扩大候选池，采用/拒绝理由写进页面设计合同。
5. 项目长期设计事实只写 `.site/design/surface-brief.md`；不创建平行设计规格。
6. 实际查看才算验证；文件存在、构建成功、色对通过、按钮可点或截图存在，都不能单独证明设计通过。
7. 常规 UI 默认保持同一图标体系；素材记录来源、许可、裁剪和 alt，缺口要诚实呈现。

## 新设计与流程分支的制作顺序

1. 建立上下文账本和任务交互合同；缺少高影响信息时调用 `site-brief`。
2. 用项目事实形成视觉世界、母题、色彩来源、字体角色和构图命题，再按需查询工具链。
3. 制作最小可见成果，在页面设计合同中标记已演示、模拟与未覆盖条件。
4. 按 [工艺审查](references/craft-review.md) 实际查看并集中修正一次；只读审查不修复。
5. 展示当前唯一需要用户决定的差异、推荐和取舍；没有实际展示和对应原话，不得回执已确认。
6. 视觉确认后补全同一份页面设计合同的实现规格，并把 `coverage / findings` 交给 `site-builder` 和 `site-check`。

## 回执

返回适用的 `status`、`artifact`、`design_contract`、`context_basis`、`direction`、`viewed`、`materials`、`result` 和 `next_skill`。`review_complete` 只表示审查结束，不表示页面通过。
