# Site Design 研究、差距分析与分层整合路线图

> 后续状态：本报告冻结后，建站套件已重构为 `site-builder`、`site-brief`、`site-design`、`site-check` 协作架构并统一到 0.4.0；当前 manifest 已通过 `python scripts/verify_skills.py .`。文中关于视觉资产的研究结论仍可作为后续专项输入，但文件行号和“哈希漂移”属于冻结时快照。
>
> 研究冻结日期：2026-09-11  
> 范围：`jakubkrehel/skills`、`pbakaus/impeccable`、`Leonxlnx/taste-skill`；补充对照 Anthropic `frontend-design` 与 Google Labs `DESIGN.md`。  
> 方法：实际 clone 五个仓库，阅读 README、核心 Skill、参考文档、实现、资产与相关提交历史；本报告只提出分析与路线，不修改现有 Skill 或代码。

## 1. 执行摘要

当前 `site-design` 的问题不是“缺少设计原则”。相反，它已经明确要求使用真实业务内容、让候选方案在结构上不同而非只换色、中文标题默认正常字距、减少无意义英文眉题，并在真实页面、宽窄屏和关键状态中验收。真正的 gap 是：**规范层说得对，默认生产资料却持续把执行拉回同一种页面**。

最直接的证据如下（本地行号以当前工作区文件为准）：

- [事实] static 与 tool 两个 web starter 都以 `.eyebrow` 开场：`site-builder/assets/templates/static/web/index.html:4`、`site-builder/assets/templates/tool/web/index.html:4`。
- [事实] static starter 的 H1 使用 `clamp(40px,8vw,88px)` 与 `letter-spacing:-.045em`（`site-builder/assets/templates/static/web/style.css:1`）；tool starter 也使用负字距（`site-builder/assets/templates/tool/web/style.css:1`）。这与本地“中文标题默认正常字距”的规则冲突。
- [事实] 两套 starter 都以暖白纸面、同一绿色 `#276957` 和 `system-ui` 为默认起点，虽用途不同，视觉世界却高度相似。
- [事实] gallery 的 reading、workspace、collection、story 四个场景都以 eyebrow 开头；页面脚本主要在相同场景容器中切换 recipe token（`site-design/assets/design/gallery.html:41-73`）。
- [事实] `tokens.json` 的十个推荐 recipe 本质仍是 `palette × typography × density × shape × layout` 的有限正交组合；四套 typography 都依赖系统字体或宋体回退（`site-design/assets/design/tokens.json`）。
- [判断] 因而当前流程虽要求“方向不同”，可用的 starter、gallery 和 token 选择器却把“方向”暗示成换色、换字体栈、换密度和圆角。模型最容易服从可复制资产，而不是较远处的文字原则。

建议不要继续以增加 palette/recipe 数量解决同质化，而应把 token 降回实现层，把以下五项提升为方向生成的主轴：

1. **主题事实**：产品、受众、任务、内容、证据与约束；
2. **视觉世界**：与主题有关的文化材料、媒介、环境和行为隐喻；
3. **页面概念**：这一页独有的命题、叙事顺序和拒绝的类别默认；
4. **构图原型**：信息拓扑、首屏尺度、密度、交互与强调关系；
5. **真实素材与状态**：真实文案、图片/品牌输入、极端内容及运行状态。

最值得吸收的外部机制是：

- Anthropic：编码前写出**项目特定设计计划**，并反问“同类产品的默认生成式答案是什么，本项目为何不采用它”。
- Jakub Krehel：一次只选一个真正有业务意义的变化轴，候选进入**真实页面和真实内容**，选择后删除其余方案；另以隔离 harness 压测坏状态。
- Impeccable：把持久产品事实、视觉系统、单页面方向分层；用可分享决策页、参考截图、构图稿、独立评审与确定性 detector 形成闭环。
- Google Labs `DESIGN.md`：用“**机器可执行 token + 人类设计意图 prose**”保存设计系统，并提供 lint、引用检查、对比度检查、diff 与 export。
- Taste Skill：可借鉴对 AI 惯性模式的敏感度与资产优先意识，但其硬禁令、固定数值和营销页偏好不能升级为跨领域真理。

建议按 P0/P1/P2 渐进整合：P0 先修正默认资料与方向合同；P1 增加结构候选、上下文转译、中文专项验收和持久设计记忆；P2 再引入截图 diff、确定性检测、资产 provenance 和演化工具。核心验收不是“新增多少规则”，而是**不同项目是否能稳定产生可解释、结构不同、符合真实任务且中文无退化的结果**。

---

## 2. 研究基线与证据纪律

### 2.1 外部仓库冻结点

| 项目 | 实际读取 commit | 角色 |
|---|---|---|
| `jakubkrehel/skills` | [`267330e1adfc66a718fb65fa6918c1f06d0a689e`](https://github.com/jakubkrehel/skills/commit/267330e1adfc66a718fb65fa6918c1f06d0a689e) | 原子设计技能、变体与压力测试 |
| `pbakaus/impeccable` | [`67d018fe052853c104a96d441ce175dd5ec4c39d`](https://github.com/pbakaus/impeccable/commit/67d018fe052853c104a96d441ce175dd5ec4c39d) | 完整产品化设计工作流与工具链 |
| `Leonxlnx/taste-skill` | [`ccbc15639c97057cbfcf32ecebc38ef716e4bb37`](https://github.com/Leonxlnx/taste-skill/commit/ccbc15639c97057cbfcf32ecebc38ef716e4bb37) | 强主张审美 guardrail 与反懒惰实验 |
| `anthropics/skills` | [`41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f`](https://github.com/anthropics/skills/commit/41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f) | 轻量、生成式前端设计基准 |
| `google-labs-code/design.md` | [`9bf8eae67128b6cc55ad9bf86665767deb4c11cd`](https://github.com/google-labs-code/design.md/commit/9bf8eae67128b6cc55ad9bf86665767deb4c11cd) | 可持久、可校验的设计系统格式 |

### 2.2 事实与建议标记

- **[事实]**：可由冻结源码、文档或本地文件直接验证。
- **[判断]**：基于事实的 gap 或适用性分析。
- **[建议]**：面向本仓库的整合方案，不代表外部项目原话。

本地工作目录不是 Git 仓库，无法为本地文件生成 commit permalink；因此本地证据使用文件路径和当前行号，外部关键事实均使用固定 commit permalink。

---

## 3. 当前 `site-design` 现状诊断

### 3.1 已有能力：应保留的正确基线

[事实] 当前规范已经覆盖多项成熟实践：

- 先理解目标、受众、内容和限制，而不是直接美化；
- 依不确定性决定给出一个方向或 2–3 个方向；
- 多方向使用相同真实业务内容比较，且结构、节奏、强调关系必须不同；
- 区分方案确认、视觉确认和开发授权；
- 使用语义 token、组件边界与真实页面；
- 验证宽窄屏、键盘、空/错/加载等关键状态；
- 已识别紫蓝渐变、卡片滥用、虚构指标、眉题泛滥和中文负字距等低级 AI 味。

[判断] 这些原则说明本地体系的方向是对的。整合外部项目不应推翻“任务优先、真实内容、先确认再开发”的主流程，而应解决**从原则到默认资产、从一次会话到持久记忆、从人工判断到证据闭环**的断层。

### 3.2 具体同质化 gap

#### A. starter 与自身原则相冲突

| 观察 | 事实 | 后果 |
|---|---|---|
| 固定开场语法 | 两个 starter 都是 eyebrow → H1 → 导语 | 新项目在内容尚未成形时就继承 AI SaaS 式层级 |
| 中文负字距 | static `-.045em`；tool `-.035em` | 中文标题易拥挤，与本地规则直接冲突 |
| 视觉起点相同 | 暖白、绿色、system-ui、窄居中列、水平分隔线 | static 内容页与操作工具在“世界”层面不可辨识 |
| starter 内容先验 | 通用“开始/下一步/记录”文案与连续 section | 容易把实际任务重新解释成 starter 的内容模型 |

[判断] starter 应只保证可运行性、安全性和最低可访问性，不应偷偷充当默认艺术指导。当前模板把“技术起点”和“视觉成品雏形”混在了一起。

#### B. gallery 用同一语法展示所谓不同方向

[事实] reading、workspace、collection、story 四类 scene 都使用 eyebrow 开场；recipe 切换主要将 token 注入同一预览容器。下载功能也只导出当前 token CSS。

[判断] gallery 实际教会模型的是“一个共同页面骨架可以通过 token 成为不同设计”。这与规范要求的“结构不同而非只换色”相悖。场景名虽不同，构图语言仍趋同。

#### C. token recipe 被提升成了方向生成器

[事实] 十个 recipe 从若干 palette、typography、density、shape、layout 选择中组合；四个 typography 依赖系统 UI 字体、中文无衬线回退或宋体回退。

[判断] 正交 token 很适合实现一致性，却不适合负责概念生成。它不能回答：

- 为什么这个产品应来自某种视觉世界；
- 首屏为什么采取这种信息拓扑；
- 哪件真实素材是主角；
- 什么是该页面独有的记忆点；
- 为什么拒绝该类别最常见的 hero/cards/dashboard 默认；
- 组件和动效如何表达任务，而不只是套用密度与圆角。

继续扩充 recipe 会增加组合数，但不会增加设计思想的维度。

#### D. 上下文虽被采集，尚未形成可追踪的设计推导

[事实] `CONTEXT.md`、`site-design/SKILL.md`、`site-design/references/reference-input.md` 与 `site-brief` 已要求读取项目资料、品牌和参考输入。

[判断] 仍缺少从输入到决策的中间产物，例如：

`来源事实 → 设计含义 → 页面决策 → 验证证据`

没有该链条，参考图容易被表面模仿，品牌词容易退化成 mood adjectives，真实内容也可能只是在默认布局里被替换。

#### E. 设计记忆以机器 token 为主，人类意图不够持久

[事实] `tokens.json` 能保存颜色、排版、密度、形状、布局和 recipe。

[判断] 它更像候选目录，而不是项目设计系统。缺少：北极星、拒绝项及原因、内容与任务策略、首屏命题、组件角色、动效语法、例外边界、素材来源，以及版本演化理由。

#### F. 验证正确但仍偏“完成性”，对“特异性”证据不足

[事实] 本地已有真实页面、状态、视口与浏览器验证要求。

[判断] 需要再分开三类检查：

1. **确定性检查**：对比度、溢出、点击尺寸、跳级标题、负字距等；
2. **实现/任务检查**：流程是否完成、状态是否真实、控件是否可用；
3. **设计判断**：是否忠于方向、是否像类别默认、是否有结构与内容上的独特性。

将三者混成一次“看起来不错”评审，既容易漏技术问题，也容易让 detector 的清单绑架审美。

### 3.3 架构与打包一致性风险

[事实] 当前目录已把可运行 starter 归于 `site-builder/assets/templates/...`，把 token、gallery 与视觉规则归于 `site-design`，所有权边界比旧布局清楚。但本次执行 `python scripts/verify_skills.py .` 时，`site-builder/manifest.json` 与 `site-design/manifest.json` 均报告 `SKILL.md` 哈希漂移。

[判断] starter 归 `site-builder`、设计规则归 `site-design` 是合理分工；仍需保证两者引用同一套已确认视觉意图，并让 manifest 校验持续通过。否则研究或修改可能基于与实际打包内容不同的快照。这是版本治理风险，不是审美结论。

---

## 4. 逐项目拆解

## 4.1 `jakubkrehel/skills`

### 机制与流程

[事实] 该仓库把能力拆成原子技能，`better-interface` 只做编排，排版、颜色、布局、文案、可访问性和 UI 各自作为事实来源，要求先 recon、再以证据排序、合并系统性问题，并默认不修改代码（[better-interface L10-L26, L38-L119](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/better-interface/SKILL.md#L10-L119)）。

[事实] `variant` 不允许只做不同 tint：先选择一个主要变化轴，让三个答案站在轴的不同位置；候选放进真实页面并使用真实、具有产品形状的内容，说明 trade-off，用户选择后只保留一个（[variant L9-L35](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/variant/SKILL.md#L9-L35)、[L64-L103](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/variant/SKILL.md#L64-L103)）。其 picker 还处理 URL 参数、历史记录与可访问名称，使选择可分享而不是只存在于对话中（[picker L1-L82](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/variant/picker.md#L1-L82)）。

[事实] `break` 刻意与真实页候选相反：它把真实组件置于隔离 harness，以规划好的极端场景逐一渲染；只报告在浏览器里实际看到的破坏，不把推测当发现，也不未经请求修复（[break L9-L45](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/break/SKILL.md#L9-L45)、[L51-L78](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/break/SKILL.md#L51-L78)）。

[事实] 截图反推明确区分 measured、derived、inferred；只把像素色值和对比度视为可精确测量，不从截图伪称精确字号、字体或技术栈（[explain-interface L54-L82](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/explain-interface/SKILL.md#L54-L82)、[from-an-image L5-L45](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/explain-interface/from-an-image.md#L5-L45)）。

### 设计覆盖

- 布局：按分组、阅读顺序、渐进披露和增长/裁切风险处理（[better-layout L8-L56](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/better-layout/SKILL.md#L8-L56)）。
- 色彩：先构建小型 ramp，再以语义角色命名；对比度必须测量实际渲染色对（[better-colors L8-L59](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/better-colors/SKILL.md#L8-L59)）。
- 动效：要求可打断、只 transition 实际变化属性、谨慎使用 `will-change`（[better-ui L30-L82](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/better-ui/SKILL.md#L30-L82)）。
- 评审：针对 change 而非整个 codebase，区分 diff 与真实 surface，阅读删除内容并按意图分类（[interface-review L15-L100](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/interface-review/SKILL.md#L15-L100)）。

### 可借鉴与局限

[建议] 最适合本地直接吸收的是“**真实页候选 + 单轴差异 + 选后删除**”和“**隔离坏状态 harness**”的二轨结构。前者判断方向在上下文中是否成立，后者判断组件能否自卫，不能用一个 gallery 同时替代。

[判断] 局限是这些原子技能偏向局部 UI 改进和审查，并不独自完成品牌世界、整页叙事和素材生产；技能之间存在 owner/编排依赖。若直接复制全部文件，会让现有 Skill 变得碎片化且增加调度成本。

## 4.2 `pbakaus/impeccable`

### 机制与流程

[事实] Impeccable 是一套产品化系统：README 当前宣称 1 个 Skill、23 个命令和 61 条确定性 detector 规则；`init` 将长期产品事实写入 `PRODUCT.md`，每个 surface 的 visitor mode/方向与全局 `DESIGN.md` 分开（[README L3-L16](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/README.md#L3-L16)、[L34-L44](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/README.md#L34-L44)）。

[事实] 它按 surface 选择 Persuade、Operate、Read、Experience，而不是按产品一次性定型；“工具的 landing page 仍是 Persuade”（[SKILL.src L29-L42](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/SKILL.src.md#L29-L42)）。这避免把营销页的表现主义硬套到后台工具。

[事实] 新世界流程不是直接挑 token，而是：确定已知事实，只问会改变设计的问题；从受众的文化世界列出具体系统/器物/场所/仪式；通过 `concept-seed` 打破排序惯性，与 challenger 比较；为页面写 direction contract，包含 THESIS、OWN-WORLD、STORY、FIRST VIEWPORT、FORM、FINISH，其中明确记录“拒绝的类别默认”（[new-work L5-L53](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/new-work.md#L5-L53)、[L75-L79](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/new-work.md#L75-L79)）。

[事实] 它保留一个“category standard”退出门，用户可主动选择熟悉方案；因此突破默认不是强迫用户接受陌生设计（[new-work L47-L53](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/new-work.md#L47-L53)）。

[事实] comp-led 路径要求三张使用真实内容的高保真构图稿；已有设计系统时，以代表页面截图作为 pixel reference，明确哪些视觉特征应继承、哪些页面内容不能泄漏。批准结果由 brief 和 sidecar 持久化，之后将 comp 测量成区域 spec，而不是凭记忆重画（[visualize L3-L38](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/visualize.md#L3-L38)）。生成 raster 还嵌入 prompt 或来源以保存 provenance（[visualize L40-L42](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/visualize.md#L40-L42)）。

[事实] 完成阶段批量截取目标宽度，以方向合同和批准 comp 评审，限制修正轮数；comp-led 运行 region diff，并由不继承构建上下文的独立 reviewer 做最后判断（[new-work L135-L149](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/new-work.md#L135-L149)）。

[事实] critique 刻意让“设计判断”和“detector/browser 证据”由两个互不锚定的 assessment 完成，再合并成 P0–P3 结果并保存快照（[critique L3-L12](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/critique.md#L3-L12)、[L33-L69](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/critique.md#L33-L69)）。README 同时明确 clean detector 只是证据，不是视觉或无障碍质量证明（[README L466-L468](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/README.md#L466-L468)）。

### 审美约束及其边界

[事实] craft floor 将大部分高频 AI 模式定义为“类别默认而非禁令”，用户 brief 可覆盖；但 eyebrow 被单独设为绝对禁令（[craft-floor L19-L27](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/craft-floor.md#L19-L27)）。Operate 则明确偏向熟悉、单字体家族、固定 rem 标题和状态型动效（[operate L5-L42](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/operate.md#L5-L42)）。

### 可借鉴与局限

[建议] 本地优先借鉴其**分层记忆、方向合同、参考截图继承、独立评审与 deterministic detector 分流**，而不是整体移植。

[判断] 其流程非常重：随机 seed、决策服务器、图像生成、subagent、浏览器、Rust CLI、comp spec/diff 和 sidecar 都带来安装、运行与维护成本。固定“三张”、固定“两轮”、强制独立 agent，以及 eyebrow 绝对禁令均是其工作流选择，不应成为本地所有项目的硬合同。其 asset generation 对无图像工具环境也有明显降级。

## 4.3 `Leonxlnx/taste-skill`

### 机制与流程

[事实] Taste Skill 以高强度规则抑制模型的默认前端惯性：先读取页面类型、受众、参考和品牌资产，再声明 design read 与三项 dial（[taste-skill SKILL L13-L78](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/skills/taste-skill/SKILL.md#L13-L78)）；其图像策略又明确优先生成或使用真实素材，反对用 div 假截图替代视觉资产（[L262-L301](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/skills/taste-skill/SKILL.md#L262-L301)）。`brandkit` 将 logo、颜色、字体和品牌资料转化为可复用输入（[brandkit L1-L111](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/skills/brandkit/SKILL.md#L1-L111)）；`redesign-skill` 与 `stitch-skill` 则覆盖现有页面分析和设计系统衔接（[redesign L1-L110](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/skills/redesign-skill/SKILL.md#L1-L110)、[stitch L1-L116](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/skills/stitch-skill/SKILL.md#L1-L116)）。

[事实] 仓库还记录了针对“模型知道规则却偷懒”的实验，比较不同 prompt/规则强度下的遵循情况；这是经验性探索，不是通用设计科学定律（[research README L1-L79](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/research/laziness/README.md#L1-L79)、[empirical results L1-L120](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/research/laziness/findings/empirical-results.md#L1-L120)）。

### 内部矛盾与领域边界

[判断] Taste Skill 最大价值是指出：只写“做得漂亮”无法抵抗生成惯性，规则必须可操作、可观察。但它也存在必须显式标注的边界：

1. **硬禁令与上下文冲突**：某些模式在营销模板里确实泛滥，但在数据产品、无障碍、品牌规范或原生平台中可能合理；禁止本身不能代替“为何不适合本项目”的判断。
2. **固定数值与响应情境冲突**：统一字号、间距、圆角或动画时长可提高短期一致性，却可能在中文、密集工具、长文阅读和小屏中失效。
3. **“大胆审美”与任务效率冲突**：强视觉表现适合 Persuade/Experience，不适合所有 Operate/Read surface。
4. **规则自身存在张力**：一方面鼓励差异化、打破默认，另一方面大量严格形态规则又会形成新的 taste 模板；一方面鼓励真实资产，另一方面生成/占位资产可能制造真实性误读。
5. **实验外推有限**：其 laziness 研究是特定模型、任务与评分设定下的仓库内实验，不能证明某条禁令跨模型、语言和产品类型普遍有效。

[建议] 只吸收“反惯性清单、素材优先、明显模式 detector 候选”和品牌输入流程；所有审美规则分成：无障碍/正确性硬门禁、项目默认、可覆盖启发式三层，绝不把 Taste 的任意硬禁令原样升级为普遍真理。

---

## 5. 补充对照

## 5.1 Anthropic `frontend-design`

[事实] Anthropic 的 Skill 先要求理解目的、受众、技术约束，再选择明确审美方向；近期文本强调在实现前形成项目特定设计思路，并主动避免收敛到常见 AI 默认，例如过度使用相同字体、紫色渐变、卡片网格和缺乏上下文的通用布局（[frontend-design L7-L42](https://github.com/anthropics/skills/blob/41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f/skills/frontend-design/SKILL.md#L7-L42)）。

[建议] 本地应把这一点变成一个短而强制的“默认反事实”步骤，而不是追加审美黑名单：

> 如果按这一类别最常见的生成式默认来做，页面会是什么样？本项目的事实为何要求另一种构图、排版、素材或交互答案？

输出应具体到项目，至少包含：类别默认、拒绝原因、替代命题、可验证表现。若无法回答，说明方向尚未形成，不能进入 token 选择。

## 5.2 Google Labs `DESIGN.md`

[事实] Google Labs 提出的格式把可机读 YAML token 与固定顺序的人类可读 Markdown 结合：token 是规范值，prose 解释如何使用、为何这样使用（[spec L1-L89](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/docs/spec.md#L1-L89)）。示例同时记录颜色、字体、圆角、间距和组件引用，以及 North Star、布局、颜色、排版、组件、动效等意图（[example DESIGN.md L1-L183](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/examples/paws-and-paths/DESIGN.md#L1-L183)）。

[事实] 工具不是只读文档：CLI 提供 lint、diff 与 export；规则包含 token broken-ref 和对比度检查（[diff.ts L1-L119](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/packages/cli/src/commands/diff.ts#L1-L119)、[export.ts L1-L120](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/packages/cli/src/commands/export.ts#L1-L120)、[broken-ref.ts L1-L77](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/packages/cli/src/linter/linter/rules/broken-ref.ts#L1-L77)、[contrast-ratio.ts L1-L103](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/packages/cli/src/linter/linter/rules/contrast-ratio.ts#L1-L103)）。其哲学强调格式应可渐进采用，并兼顾人类与 agent（[PHILOSOPHY L1-L83](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/PHILOSOPHY.md#L1-L83)）。

[建议] 本地不必立即采用完整外部 schema，但应借鉴“机器事实与人类意图同文件或强关联”的原则。`tokens.json` 继续作为实现输入，新增的项目设计记忆引用它而不复制值，防止 prose 与 JSON 双源漂移。

---

## 6. 横向对比矩阵

评分：● 强；◐ 部分覆盖；○ 非重点。评分是本报告分析，不是项目自述。

| 维度 | 本地现状 | Jakub | Impeccable | Taste | Anthropic | Google DESIGN.md |
|---|---:|---:|---:|---:|---:|---:|
| 项目事实/上下文采集 | ● | ◐ | ● | ◐ | ◐ | ◐ |
| 品牌与参考图输入 | ◐ | ●（测量纪律） | ●（pixel reference） | ●（brandkit） | ◐ | ◐ |
| 项目特定概念计划 | ◐ | ◐ | ● | ◐ | ● | ●（持久意图） |
| 默认反事实自检 | ◐（反模式） | ◐ | ● | ●（但偏硬） | ● | ○ |
| 结构性候选生成 | 原则 ● / 资产 ○ | ● | ● | ◐ | ◐ | ○ |
| 真实内容/真实页面比较 | ● | ● | ● | ◐ | ◐ | ○ |
| 布局/排版/色彩细则 | ● | ● | ● | ● | ● | ●（记录） |
| 动效策略 | ◐ | ● | ● | ● | ● | ●（记录） |
| 组件与状态 | ● | ● | ● | ● | ◐ | ●（有限 schema） |
| 渐进式披露 | ● | ● | ● | ◐ | ○ | ●（可选 section） |
| 资产生产与 provenance | ◐ | ○ | ● | ◐ | ◐ | ○ |
| 浏览器/截图验证 | ● | ● | ● | ◐ | ◐ | ○ |
| 确定性检测 | ◐ | ●（计算型） | ● | ◐ | ○ | ● |
| 独立设计评审 | ◐（有只读分支） | ◐ | ● | ○ | ○ | ○ |
| 持久设计系统 | token 为主 | ○ | ● | ◐ | ○ | ● |
| 避免模板僵化 | 原则强/资产弱 | ● | ● | ◐ | ● | ◐ |
| 工具复杂度 | 中 | 低–中 | 很高 | 中 | 低 | 中 |

结论：没有一个项目应被整体照搬。最合理的组合是：

- 用本地流程作为主干；
- 用 Anthropic 的计划/反事实补上进入设计前的判断；
- 用 Jakub 的 variant/break 补上“真实上下文选择 + 隔离压力测试”；
- 用 Impeccable 的分层记忆、参考图继承和评审解耦补上闭环；
- 用 Google 的 token + intent 格式补上持久化；
- 将 Taste 限定为可覆盖的反惯性提示与 detector 灵感库。

---

## 7. 可借鉴机制与不可照搬项

### 7.1 可借鉴机制

1. **方向前置合同**：编码前写 100–200 字项目特定计划，包含命题、用户路径、首屏、真实素材、拒绝的类别默认和完成条件。
2. **证据转译表**：每条参考/品牌输入标注来源、确定性、贡献、禁止照搬内容和最终落点。
3. **单主轴候选**：2–3 个候选先在信息拓扑、内容顺序、密度或交互模型上分开，再选择与之相干的 token。
4. **真实页面 picker**：同一真实数据与内容，稳定 URL，可分享选择；批准一个后移除其他实现。
5. **双验证场**：真实页验证上下文，隔离 harness 验证极端状态。
6. **三层评审**：设计判断、确定性 detector、任务/实现检查分开产生证据，最后综合。
7. **持久设计记忆**：规范 token 与人类意图关联，记录例外和演化，不把配方目录当项目系统。
8. **资产 provenance**：记录原图来源、参考约束、生成 prompt/许可及最终用途。

### 7.2 不可照搬项

- 不照搬 Taste 或 Impeccable 的绝对 eyebrow 禁令；本地应禁止“无语义、惯性式眉题”，但允许合法 breadcrumb、分类标签、期刊栏目或品牌规范中的 kicker。
- 不固定所有任务都生成三稿、两轮截图或独立 subagent；按风险与不确定性升级。
- 不引入随机 seed 作为差异化本身。随机性只能打破排序惯性，最终方向必须由产品事实解释。
- 不把营销页的大胆排版、生成图像和 signature interaction 套到后台、表单、文档和高频工具。
- 不把截图当源码，不从像素伪推精确字体和技术栈。
- 不让 detector 充当审美裁判；clean 只代表已检查的机械问题未触发。
- 不先写一套理想 token 再强迫实现符合；新世界先形成方向和页面，再从真实实现提取稳定系统。
- 不整体引入 Impeccable 的 Rust CLI、服务端选择器、图像生成与多 agent 编排，除非收益经 P1 数据证明。

---

## 8. 目标工作流与信息架构

### 8.1 目标工作流

#### Step 0：确定工作类型

区分：新世界、现有系统新增页面、局部改进、重设计、纯审查。局部请求不应被强迫重做品牌世界。

#### Step 1：建立“已知事实包”

采集产品/页面目的、受众、首要任务、真实内容、证据、平台、技术和无障碍约束；扫描已有页面、品牌资产、字体、token、组件和截图。只追问会改变设计的问题。

#### Step 2：转译品牌与参考输入

为每项输入记录：

- 来源与许可；
- measured / derived / inferred；
- 要继承的结构、节奏、色彩、字体角色、组件性格；
- 不得复制的内容、商标、具体版式；
- 对当前页面决策的影响。

#### Step 3：项目特定设计计划 + 默认反事实

先写：

- `THESIS`：这页独有的一个命题；
- `USER PATH`：用户理解、相信、操作的顺序；
- `FIRST VIEWPORT`：首屏具体构图，不写“现代、简洁”；
- `REAL MATERIAL`：真实文案、数据、图片或对象；
- `DEFAULT COUNTERFACTUAL`：类别默认会是什么，为何拒绝；
- `FINISH`：什么证据才算完成。

#### Step 4：按不确定性探索结构方向

- 低不确定性：一个方向；
- 中高不确定性：2–3 个候选，每个选择一个主变化轴；
- 必须改变拓扑/顺序/密度/强调/交互之一，token 变化只作为结果；
- 使用相同真实内容和关键状态；
- 每个候选陈述收益、风险及最适场景。

#### Step 5：视觉确认并冻结选择

在真实页面或可分享 picker 比较。记录选择和原因，删除未选实现；保留短决策记录而非长期维护多套分支。

#### Step 6：实现系统化

从方向推导语义 token、组件角色、状态和响应规则。starter 只提供中性技术骨架，不预设 eyebrow、绿色或超大负字距 H1。

#### Step 7：双场验证

- 真实页：任务、首屏、层级、内容、品牌一致性、窄/宽屏；
- harness：空、少、长、极多、错误、加载、禁用、权限、离线/失败；
- 中文专项：标点、数字/英文混排、长标题、长按钮、换行、行高、字距和字体 fallback。

#### Step 8：三路评审与修正

先做无 detector 锚定的设计 critique，再跑机械检查，最后验证任务与实现完整性；按 P0–P3 合并，一批修正后复验。高风险任务可使用独立 reviewer，普通任务可在同一 agent 中严格分阶段。

#### Step 9：持久化真实系统

完成后保存项目设计记忆和稳定 token；记录规则、理由、例外、组件用法、动效语法、素材 provenance 与变更摘要。后续普通页面继承，不重新发明视觉世界。

### 8.2 建议信息架构

以下是目标结构，不是本轮实施要求：

```text
project design memory
├── product facts            # 稳定事实：受众、任务、证据、约束
├── design intent            # 北极星、视觉世界、默认反事实、规则及例外
├── normative tokens         # 机器可读、单一真值
├── surface briefs           # 每页面命题、首屏、路径、批准方向
├── reference ledger         # 品牌/截图/素材来源及转译边界
├── component contracts      # 角色、状态、内容极限、响应行为
└── review snapshots         # 视口、状态、发现、选择与演化原因
```

渐进披露原则：主 `SKILL.md` 只保留路由和不可跳过的门禁；上下文、方向、候选、中文排版、组件压力测试、评审、持久化各自作为按需 reference。机器检测放脚本，不把所有规则堆入 prompt。

---

## 9. P0 / P1 / P2 路线图

## P0：纠正默认起点，建立最小方向合同

**目标：先停止资产对原则的反向诱导。**

1. 明确 starter 的唯一职责：可运行、语义化、可访问、无视觉立场。
2. 移除默认 eyebrow 结构；不再内置绿色/暖白作为隐性品牌；中文标题不设负字距。
3. gallery 不再让四种 scene 共用 eyebrow → heading 语法；至少展示彼此不同的信息拓扑。
4. 在进入 recipe 前强制输出项目特定 design plan 与 default counterfactual。
5. recipe 标注为“实现起点/校准工具”，不能被称为设计方向。
6. 修复并持续运行 manifest 哈希检查，保持 `site-builder` 的 starter 与 `site-design` 的规则边界可验证。
7. 增加中文最低门禁：中文标题 `letter-spacing` 默认 `normal`，检查混排、换行和 fallback。

**P0 验收**：见第 10 节 A、B、C、F。

## P1：结构性探索、输入转译与持久设计记忆

**目标：使差异来自项目事实和构图，而非 token。**

1. 增加 surface brief，保存 THESIS / USER PATH / FIRST VIEWPORT / DEFAULT COUNTERFACTUAL / FINISH。
2. 将现有 `?direction=a|b|c` 约定落地为可复用、可验证的真实页 picker；高不确定任务提供 2–3 个结构候选，选择后清理其余分支。
3. 增加 reference ledger，区分 measured / derived / inferred 和允许继承/禁止复制项。
4. 建立 real-page 与 break-harness 双轨验证。
5. 设计项目级 `token + intent` 持久格式：token 保持机器规范，prose 保存角色、理由、例外和组件使用。
6. 增加 mode/surface 判断，至少区分 Persuade、Operate、Read、Experience，避免单一审美覆盖所有页面。
7. 建立中文内容 fixture：最长标题、长实体名、数字/拉丁混排、中文标点、无空格长串、密集表格和按钮文案。

**P1 验收**：见第 10 节 D、E、G、H。

## P2：证据自动化与演化治理

**目标：在证明有效后增加工具，不先堆基础设施。**

1. 实现确定性 detector：负字距中文、溢出、对比度、触控尺寸、跳级标题、缺失状态、无语义 eyebrow 频率等。
2. 对批准构图与实现增加可选 screenshot/region diff；不以单一像素相似度作为设计质量分数。
3. 将设计 critique、detector 和任务验证隔离后综合；高风险项目可启用独立 reviewer。
4. 增加设计记忆 lint：broken token ref、重复真值、对比度、缺失理由、过期 reference。
5. 支持 token export/diff 和设计变更摘要，说明“数值变了什么、意图为何改变”。
6. 为生成、库存和第三方资产保存 prompt/来源、许可、裁切和用途 provenance。
7. 基于真实项目结果维护反模式统计，淘汰无效规则，而不是持续累加禁令。

**P2 验收**：见第 10 节 I、J、K。

---

## 10. 可测验收指标

### A. starter 中性度（P0）

- 0 个 starter 默认以 eyebrow/kicker 开场；
- 0 个中文 starter 标题使用负 `letter-spacing`；
- static 与 tool 不共享完整的背景色 + accent + 字体 + 页面骨架四元组；
- starter 删除后不影响业务页面的视觉方向，证明其不是隐性设计系统。

### B. gallery 结构差异（P0）

- 四个示例场景至少覆盖三种不同首屏拓扑；
- 任意两个候选不能仅凭 token diff 被判定为不同方向；
- 评审者在灰度、统一字体条件下仍能描述候选的结构差异。

### C. 方向前置率（P0）

抽查 10 个新建/重设计任务：100% 在首个视觉实现前有项目特定计划；其中 100% 明确写出类别默认、拒绝理由和替代构图，而非泛化词汇。

### D. 真实上下文率（P1）

- 方向比较 100% 使用相同真实或经明确标注的代表性内容；
- 禁止 lorem ipsum 与固定三行假数据作为批准依据；
- 所有批准候选至少含一个关键真实状态。

### E. 方向差异质量（P1）

对每轮候选计算人工 rubric：信息拓扑、内容顺序、密度、强调方式、交互模型五项中至少两项显著不同；仅色彩/字体/圆角不同判失败。

### F. 中文专项（P0/P1）

在 320、375、768 和目标桌面宽度验证：

- 中文标题无非预期拥挤、截断或孤立标点；
- body 行长与行高可读；
- 中英数字混排基线和间距稳定；
- 长按钮、长导航、表格和输入错误文案不溢出；
- 字体不可用时 fallback 不造成布局不可用；
- 除有明确字体证据外，中文标题字距为 `normal`。

### G. 参考可追踪率（P1）

所有实际影响设计的参考均记录来源、确定性、继承项和禁止复制项；所有 shipping raster 有来源或生成 provenance，目标覆盖率 100%。

### H. 持久设计记忆完整度（P1）

- token 引用无断链；
- 数值只在机器层存在一个规范真值；
- 每个核心设计规则有理由与至少一个适用/例外说明；
- 普通新增页面能继承系统，无需重新选择基础 palette/typography。

### I. 检测与判断解耦（P2）

评审报告分别列出设计判断、机械发现、任务/实现发现；detector clean 不得自动产生“设计通过”。对每条发现保存证据路径和严重度。

### J. 视觉回归（P2）

关键页面保存目标视口与状态截图；批准构图存在时记录主要 region 的缺失、错位或语义替代。像素差只作为调查线索，响应式合理变化不算失败。

### K. 同质化趋势（P2）

每季度抽样至少 20 个输出，统计：

- eyebrow 首屏占比；
- 暖白 + 单绿色占比；
- system-ui 作为无理由默认的占比；
- hero + 三卡片结构占比；
- 仅 token 差异候选占比；
- 项目特定素材与构图命题覆盖率。

目标不是把某模式降到绝对 0，而是任何高频模式都能由项目事实解释；无法解释的惯性模式持续下降。

---

## 11. 风险与开放问题

### 11.1 主要风险

1. **用新模板替代旧模板**：如果 direction contract 变成固定六段套话、视觉世界变成固定“器物隐喻”，同质化只会换一种外观。
2. **流程过重**：小修复若也要求三方向、picker、截图 diff 和独立 reviewer，会增加延迟并诱使 agent 跳过整个流程。
3. **持久文件漂移**：token JSON、prose、CSS 和组件若互相复制数值，会产生多个真值源。
4. **detector 过权**：容易检测的模式会得到过多关注，难以机械化的叙事、品牌适切性和信息架构反被忽视。
5. **中文规则过度简化**：`letter-spacing: normal` 是安全默认，不是所有字体、字号和艺术标题的绝对真理；例外必须有字体和视觉证据。
6. **参考图泄漏**：pixel reference 可保持一致，也可能复制原页面内容、竞品构图或受版权保护资产。
7. **生成资产真实性**：生成图不能暗示真实客户、真实产品能力、真实证言或真实数据。
8. **运行时资产不一致**：starter 与设计规则虽已分属 `site-builder` / `site-design`，但 manifest 哈希漂移说明工作区与打包快照可能不一致，规范修改可能未进入实际分发。
9. **外部项目快速演化**：Impeccable 当前 commit 的命令数、detector 数和流程细节可能变化；本地应复制原则，不绑定易变实现。

### 11.2 开放问题

- `site-builder` 拥有 starter、`site-design` 拥有设计规则后，二者通过什么稳定接口共享已确认方向？manifest 在何阶段自动校验？
- 项目级设计记忆应放在现有 `CONTEXT.md`、新增 `DESIGN.md`，还是生成目录？谁负责更新？
- 哪些任务算高不确定性，触发多方向和 picker？可否用“新品牌/新页面类型/高业务风险/参考冲突”四项判定？
- 浏览器、截图和 subagent 在实际运行环境中的可用性与成本是多少？降级路径如何披露？
- 中文字体是否允许网络加载？若不允许，如何针对 Windows/macOS/Android 的不同回退验证？
- 资产生成工具是否可用，生成内容的许可与隐私边界是什么？
- 如何定义“无语义 eyebrow”：靠 DOM 邻接、字号/字距 detector，还是由评审判断？
- 是否需要兼容 Google `DESIGN.md` schema，还是只借鉴思想并维持更小的本地格式？
- P0/P1 的实际样本能否证明结构候选比增加 recipe 更有效？应在引入 P2 重工具前先收集对照数据。

---

## 12. 最终建议

短期不要再增加第 十一套 palette recipe 或第五套系统字体组合。先让默认 starter 和 gallery 停止违反已有规则，并在任何视觉实现前增加一份非常短、项目特定、带默认反事实的方向合同。

中期把“方向”从 token 选择提升为**主题事实 → 视觉世界 → 页面命题 → 构图原型 → token/组件**的推导链；使用真实页候选做选择、隔离 harness 做压力测试，并以 token + intent 保存完成后的真实系统。

长期只自动化可确定的部分：引用、对比度、溢出、状态、截图和 token diff。设计特异性仍由基于证据的 critique 判断，并与 detector 隔离。成功标准不是页面都避开某个颜色、圆角或 eyebrow，而是每个决定都能回答：**它来自什么项目事实，替代了哪个默认答案，并由什么真实页面证据证明有效。**

---

## 13. 引用来源索引

### 主项目

- Jakub Krehel Skills：[`README.md`](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/README.md)、[`variant`](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/variant/SKILL.md)、[`break`](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/break/SKILL.md)、[`better-interface`](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/better-interface/SKILL.md)、[`explain-interface`](https://github.com/jakubkrehel/skills/blob/267330e1adfc66a718fb65fa6918c1f06d0a689e/skills/explain-interface/SKILL.md)。
- Impeccable：[`README.md`](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/README.md)、[`SKILL.src.md`](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/SKILL.src.md)、[`new-work`](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/new-work.md)、[`visualize`](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/visualize.md)、[`critique`](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/critique.md)、[`document`](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/document.md)、[`detector registry`](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/crates/foundation/src/registry.rs)。
- Taste Skill：[`README.md`](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/README.md)、[`taste-skill`](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/skills/taste-skill/SKILL.md)、[`brandkit`](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/skills/brandkit/SKILL.md)、[`redesign-skill`](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/skills/redesign-skill/SKILL.md)、[`laziness research`](https://github.com/Leonxlnx/taste-skill/blob/ccbc15639c97057cbfcf32ecebc38ef716e4bb37/research/laziness/README.md)。

### 补充对照

- Anthropic：[`frontend-design/SKILL.md`](https://github.com/anthropics/skills/blob/41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f/skills/frontend-design/SKILL.md)。
- Google Labs：[`README.md`](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/README.md)、[`PHILOSOPHY.md`](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/PHILOSOPHY.md)、[`spec.md`](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/docs/spec.md)、[`example DESIGN.md`](https://github.com/google-labs-code/design.md/blob/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/examples/paws-and-paths/DESIGN.md)、[`CLI source`](https://github.com/google-labs-code/design.md/tree/9bf8eae67128b6cc55ad9bf86665767deb4c11cd/packages/cli/src)。

### 本地证据

- `REQUIREMENTS.md`
- `CONTEXT.md`
- `site-design/SKILL.md`
- `site-design/references/{design-quality,design-tokens,reference-input,prototype}.md`
- `site-design/assets/design/{tokens.json,gallery.html}`
- `site-design/manifest.json`
- `site-builder/{SKILL.md,manifest.json}`
- `site-builder/assets/templates/{static,tool}/web/*`
- `site-check/references/verification.md`
