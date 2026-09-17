---
name: site-design-v3
description: v3 网站与 Web 产品设计。使用项目事实、设计规范、模板、Token、素材规则和内置检索制作可见方向、流程体验稿或只读视觉审查；不修改正式业务源码。
---
# v3 网站设计

设计能力完整保留，流程按需加载。目标是用项目事实形成有辨识度、可实现、可验证的方向，不是套模板，也不是让用户学习设计流程。

## 先选分支

| 任务 | 读取 | 产出 |
| --- | --- | --- |
| 新建、整体改版、核心流程或信息结构变化 | [设计上下文](references/design-context.md)、[视觉方向](references/visual-direction.md)、[页面设计合同](references/surface-brief.md)、[体验稿](references/prototype.md)、[工艺审查](references/craft-review.md) | 一个完整推荐方向；真实取舍存在时再给对照方向 |
| 成熟系统中的局部页面或样式修复 | [设计上下文](references/design-context.md)、[工艺审查](references/craft-review.md) | 继承基线和最小修正，不重做设计系统 |
| 流程、状态或操作顺序实验 | [设计上下文](references/design-context.md)、[体验稿](references/prototype.md)、[页面设计合同](references/surface-brief.md) | 可点击状态演示和保留/改变规则 |
| 截图、图片或网址参考 | [参考输入](references/reference-input.md) | `replicate | adapt | behavior-only` 结论和可见依据 |
| 只读视觉审查 | [工艺审查](references/craft-review.md) | 带页面、状态、视口和证据的发现 |

方向形成后，按需读取 [设计 Token](references/design-tokens.md) 和 [内置工具链](references/design-toolchain.md)。不要预读无关分支，也不要为了显得完整而查询所有领域。

## 默认工作法

1. 先看活跃工程、真实内容、品牌、素材和明确参考；缺失事实才调用 `site-brief-v3`。
2. 写出使用者、主任务、业务对象、真实内容、关键状态、设备和风险。
3. 识别类别默认，说明本项目为什么不照搬，并形成结构、母题、色彩来源、字体角色、构图命题和细节签名。结构指信息拓扑与主要操作，不是视觉外观；配色、字体、圆角、阴影只影响视觉，不构成不同的结构候选。
4. 默认制作一个接近成品的推荐核心页面。只有真实取舍无法由事实消解时才增加对照方向。
5. 用相同内容、状态和视口实际查看；按工艺审查集中修正一次。
6. 用户确认的是一个完整方向，包含任务、范围、结构和视觉。`site-builder-v3` 用一次 `decide` 记录，不拆成结构、视觉和开发三道门。
7. 在 `.v3/design/surface-brief.md` 中只填写本轮适用字段，再交回实现和检查。

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

使用五字段回执 `status / summary / artifacts / evidence / limitations` 返回一次，然后停止。
