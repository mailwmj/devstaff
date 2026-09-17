# 内置设计检索接口

本项目已经内置 `design-intelligence` `2.13.0` 的检索代码与数据。它只负责快速召回候选和实现注意项；项目事实、方向筛选、用户确认与实际渲染仍由本 Skill 负责。

## 先看能力目录

```text
python <site-design-v3 安装目录>/scripts/design.py catalog
```

目录固定暴露 12 个搜索领域：

```text
style  color  chart  landing  product  ux
typography  google-fonts  icons  gsap  react  web
```

以及 22 个实现栈：

```text
react  nextjs  vue  svelte  astro  nuxtjs  nuxt-ui  angular
laravel  swiftui  react-native  flutter  jetpack-compose
html-tailwind  shadcn  threejs  javafx  wpf  winui  avalonia  uno  uwp
```

这已经覆盖本次核对的上游 `2.13.0` 快照中的风格、颜色、排版、UX、图表、动效、图标、产品/落地页推理、React 性能与全部技术栈数据。运行时不需要读取供应方目录，也不要把 CSV 全文塞进上下文。

## 按一个问题查询

| 目的 | 命令 | 何时用 |
| --- | --- | --- |
| 扩大完整方向候选池 | `design.py research "<2-5 个词>" --design-system --project-name "<名称>"` | 新建、整体改版或新视觉世界；通常一次 |
| 验证单一设计问题 | `design.py research "<2-5 个词>" --domain <domain> --max-results 3` | 只选一个最贴近的问题领域 |
| 获取已检测技术栈的实现注意项 | `design.py research "<2-5 个词>" --stack <stack> --max-results 3` | 项目已明确使用该栈时；不猜栈 |

查询规则：

1. 每次只有一个主要意图，并包含产品、平台或使用情境之一；不要把整段需求当查询。
2. 先用最小查询。无结果或明显偏题时只允许缩窄重试一次，不用近义词循环消耗上下文。
3. 只读取返回的 `retrieval`、`decision_record` 和少量相关 `result`；不要遍历数据目录寻找“更好看”的随机答案。
4. `verified_match` 只表示检索有稳定候选，不表示适合项目。必须用真实用户、任务、内容、设备、风险或既有系统作为 `fit_basis`。
5. `no_verified_match` 时采用本项目通用规则，并在合同记录回退；不得编造 Result ID。

## 领域路由

| 当前问题 | 首选领域 |
| --- | --- |
| 风格机制与候选命名 | `style` |
| 语义色、品牌配色与相邻色对 | `color` |
| 图表类型、数据关系、文本替代 | `chart` |
| 落地页信息顺序与转化模式 | `landing` |
| 产品类型、页面职责与常见风险 | `product` |
| 表单、导航、反馈、无障碍与任务机制 | `ux` |
| 字体角色与配对 | `typography`；确需联网字体时才查询 `google-fonts` |
| 图标语义 | `icons` |
| 动效机制 | `gsap` |
| React 性能 | `react` |
| 通用 Web 实现与无障碍 | `web` |

不要为了“完整”逐领域查询。新方向一般是一次 `--design-system`，再针对真实风险补 0～2 次领域或栈查询；成熟系统中的局部问题只查询受影响领域，甚至可以不查询。

## 决策记录

工具返回的 `decision_record.selected` 和 `fit_basis` 故意为空，要求 Agent 显式完成项目匹配。把最终记录写入 `.v3/design/surface-brief.md#设计方法来源`：

```text
Query：
Route：design-system | domain:<name> | stack:<name>
Candidate ID：稳定 ID，或 no_verified_match
Selected：yes | no
Fit basis：至少两条项目事实；有现成系统/真实素材时至少一条 measured
Rejected reason：高排名候选未采用的项目原因
Contract effect：进入母题 / Token / 组件状态 / VA-* 的具体机制
```

不能直接复制搜索结果里的行业功能、Landing 顺序、色板、字体、组件或代码。先经过范围分级、项目匹配、反默认和候选交换检查。

## 图表与技术栈的额外门槛

- 图表先写清关系：比较、趋势、分布、组成、相关、层级或流向；再选图型。提供同等意义的文本/表格替代，不只靠颜色区分系列；键盘、Tooltip、极端值和窄屏简化都要在真实页面验证。
- 栈建议只在活跃工程已确认该栈时使用。它是实现注意项，不得覆盖项目现有约定，也不能反向决定视觉方向。
- Google Fonts 条目只证明候选存在；许可、中文覆盖、加载与离线策略仍需单独核对。已有字体系统优先继承。

## 验证与边界

```text
python <site-design-v3 安装目录>/scripts/design.py validate
```

此命令验证内置版本、结构化数据、配方下限与 gallery 同步。代码位于 `../intelligence/`，许可为 MIT。项目长期设计事实只写 `surface-brief.md`；不生成供应方设计主文件，也不把检索结果当用户确认或设计通过。
