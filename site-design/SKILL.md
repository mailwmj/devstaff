---
name: site-design
version: 1.0.0
description: 网站与 Web 产品设计。使用项目事实、设计规范、模板、Token、素材规则和内置检索制作可见方向、流程体验稿或只读视觉审查；不修改正式业务源码。
---
# 网站设计

设计能力完整保留，流程按需加载。目标是用项目事实形成有辨识度、可实现、可验证的方向，不是套模板，也不是让用户学习设计流程。

## 先选分支

| 任务 | 读取 | 产出 |
| --- | --- | --- |
| 新建、整体改版、核心流程或信息结构变化 | [设计上下文](references/design-context.md)、[视觉方向](references/visual-direction.md)、[页面设计合同](references/surface-brief.md)、[体验稿](references/prototype.md)、[工艺审查](references/craft-review.md) | 2 种信息架构（含骨架预览）➔ 2 种视觉风格（轻量对比无过度测试）➔ 资产继承 |
| 成熟系统中的局部页面或样式修复 | [设计上下文](references/design-context.md)、[工艺审查](references/craft-review.md) | 继承基线和最小修正，不重做设计系统 |
| 流程、状态或操作顺序实验 | [设计上下文](references/design-context.md)、[体验稿](references/prototype.md)、[页面设计合同](references/surface-brief.md) | 可点击状态演示和保留/改变规则 |
| 截图、图片或网址参考 | [参考输入](references/reference-input.md) | `replicate | adapt | behavior-only` 结论和可见依据 |
| 只读视觉审查 | [工艺审查](references/craft-review.md) | 带页面、状态、视口和证据的发现 |

方向形成后，按需读取 [设计 Token](references/design-tokens.md) 和 [内置工具链](references/design-toolchain.md)。不要预读无关分支，也不要为了显得完整而查询所有领域。

## 默认工作法

1. 先看活跃工程、真实内容、品牌、素材和明确参考；缺失事实才调用 `site-brief`。
2. 写出使用者、主任务、业务对象、真实内容、关键状态、设备和风险。
3. **信息架构双选**：从主任务与信息拓扑出发，用通俗易懂的大白话提炼 2 种高区分度架构方案（说明适合谁、第一眼看到什么、怎么操作）；同时直接轻量快速生成单文件骨架预览页（纯灰阶布局、顶部带切换），提供文件链接优先引导在 Agent 客户端自带浏览器打开供用户挑选。
4. **视觉风格双选**：骨架选定后，推导母题、色彩角色与构图命题，在同一骨架上提供 2 种视觉气质差异鲜明的方案，直接生成轻量静态视觉预览单页（双风格无感切换）。严格坚守轻量：不写复杂业务逻辑代码，严禁执行单元测试、合同校验及全套浏览器深度断言。
5. **微调收敛与资产平滑继承**：支持用户在视觉 Demo 上快速提出微调偏好（在单页 HTML/CSS 中快速响应，用户在内置浏览器即时刷新查看）；用户确认满意的 Demo 直接作为正式代码胚胎：提取 CSS 变量沉淀为正式 Token，提取核心 HTML 作为第一条纵向切片的基础模板，微调诉求同步沉淀至视觉验收标准（`VA-*`）。
6. 用户确认完整方向后，`site-builder` 用一次 `decide` 记录，正式进入构建循环。
7. 在 `.site/design/surface-brief.md` 中只填写本轮适用字段，交回实现和检查。

## 设计资产

- `assets/design/`：Token、gallery 和基础样式。
- `scripts/design.py`：设计系统检索、Token 构建和资产校验。
- `intelligence/`：内置检索数据与 MIT 许可代码。
- `references/`：上下文、方向、体验稿、参考输入、Token、工具链、完整页面合同和工艺审查。

## 硬约束

- 行业、竞品、模板和检索结果不能创造首版功能。
- 配方和色板只校准已形成的方向，不能代替方向。
- 实际查看才算验证；文件存在、构建成功或截图存在都不能单独证明设计成立。
- 素材记录来源、许可、裁剪和 alt；缺失时诚实呈现。
- 方向确认前不修改正式业务源码；流程体验稿不连接正式数据库。
- 体验稿与视觉预览阶段坚守轻量边界，不堆砌业务逻辑代码，严禁跑重度测试套件浪费时间和 Token；不承诺“秒级生成”等绝对速度。

使用五字段回执 `status / summary / artifacts / evidence / limitations` 返回一次，然后停止。
