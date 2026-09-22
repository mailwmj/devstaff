# AI员工「网站开发专家」配置与能力档案

> **对应包版本：1.2.2** ｜ 最后同步：2026-09-22 ｜ 维护：`fde-dev`
> 用途：平台上架评审、运营配置核对、市场素材交接。字段值的唯一真相在配置文件
> （[`release/metadata.json`](release/metadata.json)、[`release/agent/home.json`](release/agent/home.json)、[`release/agent/bindings.yaml`](release/agent/bindings.yaml)、[`release/package-files.txt`](release/package-files.txt)）；
> 本档把它们翻译成业务语言，并标出还没交付的部分。

**写法口径**：面向用户与市场的文案（§一–§五）按企业办公、教育及知识工作者定位写，不出现技术黑话。
本档本身供运营与评审阅读，允许出现文件路径与字段名。提示词原文不在这里复述：执行指令见
[`release/agent/Agent.md`](release/agent/Agent.md)，工作台与市场页的提示词见对应配置字段。
本档不含任何画面生成提示词。

**平台契约**：包结构遵循 ClawHive AI 员工规范 `schemaVersion 2.0`。三个面向用户的配置位是
「工作台能力卡」（`home.json`）、市场页「推荐场景」（`metadata.agent.showcases`）和
「推荐 Prompt 模板」（`metadata.agent.quickPrompts`）。

**状态标记**：`已交付` 随包发布、客户端可见 ｜ `待补` 方案已定、素材或配置未做 ｜ `待确认` 需要产品或平台侧拍板（汇总见 §十）。

---

## 一、员工画像（一分钟版）

| 项 | 内容 |
| :--- | :--- |
| 岗位 | 网站开发专家（`website-developer`） |
| 服务对象 | 不懂技术的企业办公、教育及知识工作者 |
| 交付物 | 可直接打开的网站首版：机构门户、团队与服务介绍、产品与品牌展示、活动报名与日常登记页、事务工作台、个人主页、办事指南 |
| 四个能力入口 | 网站搭建（从零做）｜参考建站（照着做）｜设计灵感（先看两版样子）｜体验升级（把现有页面改好看） |
| 工作方式 | 问清核心任务 → 给一个可见方向 → 用户点头 → 小步实现 → 交给他看 → 他点头后在浏览器里只读验证 → 诚实说明验过什么、没验什么 |
| 用户感知的承诺 | 每步看满意才交付；数据存放在他自己的环境里；检查结论不带自夸 |
| 不做什么 | 不代替发布上线；不代替法务、无障碍、安全、隐私、货币类专业结论；不搬用他人 Logo、品牌名与商标；没有的素材不编造 |

## 二、身份与元数据

对应文件：[`release/metadata.json`](release/metadata.json) ｜ 状态：`已交付`

| 配置字段 | 当前配置值 | 客户端生效位置 | 业务作用与注意事项 |
| :--- | :--- | :--- | :--- |
| `schemaVersion` | `"2.0"` | — | 平台元数据契约版本 |
| `id` / `name` | `"website-developer"` | 安装目录、包文件名 | 两者必须完全一致，kebab-case |
| `version` | `"1.2.2"` | 市场版本号、`dist/website-developer-1.2.2.zip` | SemVer；四个随包技能的 VERSION 同值 |
| `type` | `"agent"` | 平台实体类型 | 固定值 |
| `ownership` | `"general"` | 内容归属 | 平台枚举为 `general` / `enterprise` / `personal` 三选一 |
| `displayName` | `"网站开发专家"` | 市场列表、详情页标题、技能区 | 对外唯一名称 |
| `description` | 见下方全文 | 招募详情页名字下方那段 | **平台唯一一段自由文案**，第一句是能力枚举；`slogan` 类字段平台不读（依据见下） |
| `categoryId` | `"rd"`（产品设计） | 市场分类筛选 | 客户端内置枚举为 `office` / `rd` / `project` / `support` / `data` / `custom`；原先的 `developer-tools` 在客户端里不存在 |
| `icon` / `iconAlt` | `"./agent/assets/logo.png"`（360 × 360，人物头像） | 市场列表、工作台头像 | 平台约定头像就放 `assets/logo.png`；`iconAlt` 与 `displayName` 一致 |
| `tags` | `["网站开发", "机构门户", "产品展示", "品牌官网", "活动落地页"]` | 市场检索 | 保持 5 个内容型标签；工具型需求（报名、登记）由能力卡提示词与 `description` 覆盖，不占标签位 |
| `agent.action.type` | `"conversation"` | 打开方式 | 原生对话型；该取值下平台禁止 `action.page` |
| `agent.owner` | `"fde-dev"` | 内部维护标识 | 业务责任团队 |
| `agent.visibility.departments` | `[]` | 可见范围 | 空数组 = 全员可见 |
| `agent.defaultEnabled` | `true` | 招募安装行为 | 安装后默认启用 |
| `agent.quickPrompts` | 3 条 | 市场页「推荐 Prompt 模板」 | 见 §四；客户端只渲染前 3 条 |
| `agent.showcases` | 4 条 | 市场页「案例」 | 见 §三 |

`description` 全文：

> 支持网站搭建、参考建站、设计灵感与体验升级。无需懂技术，说清想法先出两版设计挑方向，你确认后再动手开发，每一步都看得见

**第一句就是能力枚举**，与 §五 的四张能力卡逐项对应；招募前的人在详情页第一眼看到的就是它。

**平台实际读取的字段（客户端代码核对结果）**：

| 层级 | 字段 |
| :--- | :--- |
| 根级 | `displayName`、`description`、`version`、`ownership`、`icon` |
| `agent` | `action`、`showcases`、`quickPrompts`、`promptBackground`（未写进规范但确在读） |
| `home.json` | `scenes[].name` / `.description` / `.icon`，同时渲染成详情页「推荐场景」与工作台卡片 |

`slogan`、`tagline` 这类字段在客户端代码里出现 0 次，写了也不显示，本包已删除；`promptBackground` 用平台默认外观。

**文案口径提醒**：「先做两版 Demo」在新建与整体改版时成立（有结构分歧时骨架双选，之后必然有双风格对比）；
改文案、颜色、间距的局部修改走快速路径，没有 Demo 环节。

## 三、市场招募详情页「案例」（showcases）

对应字段：`metadata.agent.showcases` ｜ 状态：`已交付` ｜ 素材来源：[`release/agent/assets/showcases/SOURCES.md`](release/agent/assets/showcases/SOURCES.md)

平台把这一组渲染成「案例」区的图片卡片：客户端把卡片标题写死为空，**只显示 `description` 这一句文案**，图片按卡片宽度铺满（`object-fit: cover`）。
（详情页另一块「推荐场景」来自 `home.json` 的 `scenes`，见 §五。）四张图与四个演示页面一一对应。

| 序号 | 标识 (`id`) | 卡片文案 | 字数 | 素材（1600 × 900） |
| :---: | :--- | :--- | :---: | :--- |
| 1 | `org-portal` | 机构门户首页 | 6 | `agent/assets/showcases/org-portal.png` |
| 2 | `service-team` | 企业服务与团队介绍页 | 10 | `agent/assets/showcases/service-team.png` |
| 3 | `product-showcase` | 多品类产品展示页 | 8 | `agent/assets/showcases/product-showcase.png` |
| 4 | `brand-page` | 品牌形象与故事单页 | 9 | `agent/assets/showcases/brand-page.png` |

每个条目另有固定字段：`mediaType: "image"`、`usage: "marketplace-preview"`。

**素材性质与待确认**：四张都是演示页面截图，图中的机构名、品牌名、商品与人物均为演示内容，不构成对第三方的授权；
页面中照片素材（建筑、人物、商品）的可商用范围需要素材权利方确认后再公开发布，未确认前应替换为已授权的原创素材。

## 四、市场招募详情页「推荐 Prompt 模板」（quickPrompts）

对应字段：`metadata.agent.quickPrompts` ｜ 状态：`已交付`

市场页横滑的短句模板，用户点一下即成为他的第一句话。写法与平台既有员工一致：完整句子、20–30 字、句号收尾。

**客户端只渲染前 3 条**（代码为 `quickPrompts.slice(0, 3)`），所以这里只维护 3 条，多写的条目不会显示。

| 序号 | 标识 (`id`) | 文案 | 字数 | 对应入口 |
| :---: | :--- | :--- | :---: | :--- |
| 1 | `new-site` | 帮我做一个网站，把单位的基本情况、主要业务和联系方式讲清楚。 | 30 | 网站搭建 |
| 2 | `reference-link` | 我会给你一个喜欢的网站链接或截图，请照着它做一个我们自己的版本。 | 32 | 参考建站 |
| 3 | `design-first` | 先别写代码，给我两版不同气质的设计看看，我挑一版再继续。 | 28 | 设计灵感 |

三条都不提版面、字段或结构，避免入口文案反过来指挥信息架构；两条参考路径（网址与截图）合并成一条，字数与其他员工一致。

## 五、对话工作台 4 个能力入口（home.json）

对应文件：[`release/agent/home.json`](release/agent/home.json) ｜ 状态：`已交付`

招募成功后进入工作台，中部横向轮播四张能力卡，点卡片直接把最下面那条提示词送进会话；**同一份 `scenes` 也是招募详情页「推荐场景」那四张卡的来源**（客户端两块共用同一数据）。
卡片答的是「这东西能帮我干什么」，不要求用户先想清楚自己的需求属于哪一类网站。卡片图按卡宽铺满（`object-fit: cover`），564 × 576 的方形图标会被裁掉上下；四个主体都居中在安全区，已按 1.9:1 中心带裁切核对过。

| 序号 | 标识 (`id`) | 卡片名 | 副标题 | 图标（564 × 576） | 点击后发出的提示词 | 驱动技能 |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `site-build` | 网站搭建 | 从想法到首版上线 | `agent/assets/home/icon-build.png` | 我想做一个网站，用途是……（比如单位介绍、产品展示、活动报名或日常登记）。你先问我几个最关键的问题。 | `site-brief` `site-design` |
| 2 | `site-reference` | 参考建站 | 对标心仪网站定制 | `agent/assets/home/icon-reference.png` | 我很喜欢这个网站：〈粘贴网址或截图〉，想要同样的感觉，内容换成我们自己的。 | `site-design` `site-builder` |
| 3 | `design-inspiration` | 设计灵感 | 先看两版再定方向 | `agent/assets/home/icon-inspiration.png` | 我们网站要做的事是……。先别写代码，给我两版不同气质的样子挑一挑。 | `site-design` |
| 4 | `experience-upgrade` | 体验升级 | 界面优化与细节打磨 | `agent/assets/home/icon-upgrade.png` | 我有一个做好的页面，看着太素、点着也别扭，想让它更好看、更好用。 | `site-design` `site-builder` |

三张卡的行为边界写在 [`release/agent/Agent.md`](release/agent/Agent.md)：

- **设计灵感**只问一两件最要紧的事（这个站做什么用、给谁看）就直接出两版，不走常规那轮 3–5 题收敛。
- **体验升级**只改呈现与交互细节（配色、字号、间距、组件状态、动效、窄屏），不重排信息架构、不加业务功能。
- **参考建站**默认按提取设计 DNA 走：把参考的设计语言（配色、字阶、间距、圆角、动效、材质）装进用户自己的内容，文案、Logo、品牌名和素材用他自己的；只有他说只要那个感觉时才采调性。

**「活动报名」「日常登记」没有独立卡片**，它们由第一张卡的提示词举例覆盖；市场页顶部 `description` 里也写着这两个用途。

## 六、员工行为契约

对应文件：[`release/agent/Agent.md`](release/agent/Agent.md)（安装后注入为项目根 `AGENTS.md`）｜ 状态：`已交付`

这是该员工对用户说话的方式、做事顺序与红线的唯一权威，其他文件只引用不复述。

### 1. 唯一控制回路

```text
preflight → 执行 next_action → 产出结果 → 写入结果 → 再次 preflight
```

四条支撑纪律：顺序由脚本给（只做 `allowed_actions`）；一次一条可完整体验的切片；结论必须带证据
（没有实际验证就不能说「已完成」）；对用户说的话不含内部术语。内部状态只有五种：
`discovering / decided / building / blocked / delivered`，用户全程看不到状态名与路径。

### 2. 三档路径

| 路径 | 触发情形 | 用户能感知的流程 |
| :--- | :--- | :--- |
| `quick`（无状态捷径） | 文案、颜色、间距、明确 Bug 的局部修改 | 直接改 → 相称检查 → 说明结果（不建 `.site`） |
| `guided`（默认） | 新建、整体改版、主流程变化 | 核心任务 → 一个可见方向 → 确认 → 实现 → 交他看 → 他点头后验证 |
| `strict` | 支付、权限、隐私、共享数据、公开部署、多人协作 | 同 `guided`，另加独立验证与风险证据 |

### 3. 两道用户门禁

1. **点头门禁**：构建完成后先把这一版交给用户，停下等他回话；他明确同意才开独立验证轮。理由：验证报告只对写它的那一版成立，他看完再改一次，刚跑完的那轮就白跑。
2. **只认报告**：验证轮只收结构化检查报告，报告先过协议校验；指纹对不上当前源码、或某条轴没写清自己查了什么，都不算数。没重跑的轴如实记为 `limited`。

用户可感知的质量门槛：一轮只让他做一个高影响决定（3–5 题、带推荐答案、手机一屏读完）；先说结论不铺垫；
不写自夸心路；不汇报断言条数与像素；没检查的部分必须点出来。

### 4. 四条红线

1. 核心任务和方向未确认前，不写正式源码。
2. 影响大的选择未确认前，不替用户决定。
3. 没有实际验证就不说「已验证」，`verified` / `limited` / `blocked` 分开说。
4. 体验稿与视觉预览阶段守住轻量边界，不堆业务逻辑、不跑重度测试。

费用、系统变更、密钥、真实敏感数据和公开发布，每次都要单独停下来等用户明确决定。

### 5. 参考边界（提取设计 DNA，装进自己的内容）

权威写在 [`release/skills/site-design/references/reference-dna.md`](release/skills/site-design/references/reference-dna.md)
的《参考 DNA》一节，其余文件只引用。要旨：

| 用户的目标 | 实现怎么走 | 验收基准 |
| :--- | :--- | :--- |
| 默认：把参考的设计语言装进自己的内容 | 提取参考的 Design DNA（设计系统 / 定性气质 / 视觉特效），三个维度照 DNA 还原，包括配色；文案、业务对象、Logo、品牌名和素材用用户自己的 | 参考的测量结果（`measured.json`；有网址时加侦察值） |
| 明确说“只要那个感觉，不要它整套” | 采调性（色相区间、明暗关系、饱和度水平、色彩个数与主次），写进合同后按自有色板实现 | 合同里定稿的自有色板 |

唯一硬边界是来源识别：不把对方的 Logo、品牌名与商标直接拿过来，也不用对方的客户 Logo、评价充当自己的；
「品牌色」不是禁止项，DNA 里的配色照做。法律结论不由本员工下，工程上只按「不造成来源混淆」划线，
涉及商标与授权让用户找专业的人。

### 6. 适用边界（对用户预期的影响）

产出是可运行的首版与验收证据，不替代专业判断。法规、无障碍合规、安全、隐私与货币类结论，
需要具备相应资质的专业人士审核后才能用于正式决策。素材须记录来源、许可与替代文本；缺失时诚实呈现，
不编造社会证明。

## 七、四个技能与内置能力

对应文件：[`release/agent/bindings.yaml`](release/agent/bindings.yaml) ｜ 状态：`已交付`

| 技能标识 (`id`) | 技能显示名 | 引用来源 | 强依赖 | 核心分工 | 版本 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `site-builder` | 网站开发 | `embedded` | true | 唯一业务编排者：推进状态机、按纵向切片小步增量改代码、守住不重写防线、交付时说明验过与没验什么 | 1.2.2 |
| `site-brief` | 需求梳理 | `embedded` | false | 需求前置收敛：问清核心诉求与关键边界，用通俗选项锁定首版范围；严禁向用户提问设计与信息架构 | 1.2.2 |
| `site-design` | 网站设计与体验稿 | `embedded` | false | 骨架双选（存在真实结构分歧时）、双风格高保真体验稿、参考取证与还原度比对、中文排版与设计 Token、页面设计合同 | 1.2.2 |
| `site-check` | 网站检查与验证 | `embedded` | false | 交付前客观巡检：真实浏览器端到端只读演练、移动端横向滚动排查、出具带指纹的客观事实报告 | 1.2.2 |

平台规定 `required` 表示「是否为员工激活的硬依赖」，`required=false` 只影响发布后的运行期策略、
不豁免上传校验。四个技能**全部标 `true`**：`guided` 流程缺任何一个都跑不通（需求收敛、设计、验证），
标 `false` 等于告诉平台它们可有可无。这条由 [`tests/test_spec.py`](tests/test_spec.py) 钉住，将来真要加可选技能时先改测试。

每个技能目录自带 `metadata.json` 与 `VERSION`，并在包内分发自己的测试；技能之间不互相调用，
只向 `site-builder` 返回一次五字段回执（`status / summary / artifacts / evidence / limitations`）。

### `site-design` 内置资产

| 资产 | 内容 | 规模/版本 | 许可 |
| :--- | :--- | :--- | :--- |
| `references/` | 设计推导、体验稿、落地页、动效、参考判读、Token、中文排版、工艺审查等 12 份规范 | 12 份 Markdown | 自有 |
| `assets/design/` | Token 基线、组件基础样式、gallery、骨架预览起手壳 | 4 个文件 | 自有 |
| `intelligence/` | 内置检索代码与固定快照数据（UI/UX/技术栈/动效等） | `2.13.0` | MIT（随包附 LICENSE） |
| `dna/` | 参考取色与还原度比对：`measure`（图片量色板）、`recon`（网址读 CSS/DOM）、`verify`（比对到通过），仅依赖 Python 3.9+ 标准库 | `0.2.0-design-dna@593e39b` | MIT，移植自 [zanwei/design-dna](https://github.com/zanwei/design-dna) |
| `agents/openai.yaml` | 支持该约定的宿主用它显示技能名、短描述与默认提示词；不支持的宿主忽略 | — | 自有 |

许可与移植边界详见 [`release/skills/site-design/dna/VERSION`](release/skills/site-design/dna/VERSION) 与 `intelligence/LICENSE`。

## 八、资产清单（实测值）

| 资产 | 数量 | 实测规格 | 用途 |
| :--- | :---: | :--- | :--- |
| 员工头像 `agent/assets/logo.png` | 1 | 360 × 360 PNG，RGBA 透明底、底部渐隐 | 市场列表、工作台头像 |
| 能力卡图标 `agent/assets/home/icon-*.png` | 4 | 564 × 576 PNG（188 × 192 的 3 倍图） | 工作台能力卡 |
| 市场案例图 `agent/assets/showcases/*.png` | 4 | 1600 × 900 PNG（16:9） | 市场页「推荐场景」 |
| 素材来源说明 | 1 | `showcases/SOURCES.md` | 素材性质与授权待确认项 |

核对命令（从仓库根目录执行）：

```text
python3 -c "import glob,os,struct;[print(f'{p} {struct.unpack(\">II\",open(p,\"rb\").read(24)[16:24])} {os.path.getsize(p)//1024}KB') for p in sorted(glob.glob('release/agent/assets/**/*.png',recursive=True))]"
```

**已退役**：按旧场景绘制的 6 张图标（`icon-portal` / `icon-showcase` / `icon-workbench` / `icon-landing` /
`icon-bio` / `icon-guide`）与旧的螃蟹标识头像已移出包内，需要时用 git 历史恢复。

## 九、打包与校验链路

对应文件：[`release/package-files.txt`](release/package-files.txt)、[`tools/build_dist.py`](tools/build_dist.py)、[`tests/test_bundle.py`](tests/test_bundle.py)、[`tests/test_spec.py`](tests/test_spec.py)、[`.github/workflows/verify.yml`](.github/workflows/verify.yml) ｜ 状态：`已交付`

- **清单是唯一真相**：`package-files.txt` 决定什么随包分发；`release/` 内任何被清单覆盖的文件改动后，必须重跑构建重建 `dist/`，否则开发测试会直接报错。
- **构建产物**：`dist/website-developer-1.2.2/` 与 `dist/website-developer-1.2.2.zip`。zip 确定性生成（条目排序、固定时间戳与权限），无改动的重建不产生新产物。
- **一致性保证**：`test_bundle.py` 逐字节比对 dist 与 release；`test_spec.py` 钉住本档与配置源之间可机验的事实（包版本、素材路径与尺寸、卡片与案例覆盖）。
- **自足性保证**：CI 在 Python 3.9 / 3.10 / 3.12 上跑全部测试，并从 `git archive HEAD:release` 解出的干净归档里再跑一遍随包测试与设计资产校验，确认解包即用。

维护命令：

```text
python3 -m unittest discover -s tests -p 'test_*.py'            # 仓库侧测试（含本档一致性校验）
python3 tools/build_dist.py                                     # 重建平台包
python3 release/skills/site-design/scripts/design.py validate   # 设计资产与数据自检
```

## 十、同步责任、自检清单与待确认项

### 1. 什么改动必须同时更新本档

| 改动 | 必须同步 |
| :--- | :--- |
| 版本号、名称、口号、简介、标签、分类、头像 | §二 表格与顶部包版本 |
| 能力卡增删、图标替换、提示词调整 | §五 表格与 §八 资产清单 |
| 市场案例增删、素材替换、文案调整 | §三 表格、§八 资产清单与 `showcases/SOURCES.md` |
| 市场 Prompt 模板调整 | §四 表格 |
| 行为规则变化（门禁、边界、参考用法） | §六 |
| 技能增删、`required` 变化、技能显示名或版本 | §七 表格 |
| 打包清单、构建脚本、校验链路变化 | §九 |

机器能验的部分由 [`tests/test_spec.py`](tests/test_spec.py) 兜底；判断性的部分靠这张表。

### 2. 上架前自检清单

- [ ] §二 所有字段与 `release/metadata.json` 一致，`description` 第一句仍是能力枚举。
- [ ] §三 四条 showcase 的图片路径全部可解析，文案不超过两行。
- [ ] §四 三条 Prompt 模板与平台既有员工的字数与句式一致。
- [ ] §五 四张能力卡的 id、名称、图标与 `release/agent/home.json` 一致。
- [ ] §八 图标实测 564 × 576，头像 360 × 360，案例图 1600 × 900。
- [ ] `python3 -m unittest discover -s tests -p 'test_*.py'` 全部通过。
- [ ] `python3 tools/build_dist.py` 已重跑，`dist/` 与 `release/` 逐字节一致。
- [ ] 在真实客户端核对三处渲染：详情页名字下方那段、详情页「推荐场景」四张卡、市场页「推荐 Prompt 模板」胶囊。

### 3. 待确认项

已定（2026-09-21）：`categoryId` 取 `rd`（产品设计）；`tags` 保持 5 个内容型；四个技能 `required` 全部为 `true`；版本保持 `1.2.0`（该版本未上传过市场，不需升版）。

| 项 | 说明 | 影响 |
| :--- | :--- | :--- |
| 工作台侧的真实渲染 | 之前用作参照的那屏是客户端内置演示（`uiEmployeeHome*` 字样），真实包在工作台上的排版要在客户端实测一次 | 卡片图与文案的实际观感 |
| 案例图内照片的可商用范围 | 建筑、人物、商品照片为示意素材，见 `showcases/SOURCES.md` | 公开发布的合规风险 |

## 十一、变更记录

| 版本 | 日期 | 要点 |
| :--- | :--- | :--- |
| 1.0 | — | 四个技能成形，仅 `site-design` 带 `agents/openai.yaml`；旧 `install.py` 安装器移除 |
| 1.1 | 2026-09-19 | 验证轮前增加用户点头门禁（`handoff` → `begin-check --quote`）；检查协议修掉指纹 fail-open；指纹排除规则细化 |
| 1.2 | 2026-09-21 | 参考取证与还原度比对落地（`measure` / `recon` / `verify`）；工作台从 6 个场景卡改为 4 个能力卡（网站搭建 / 参考建站 / 设计灵感 / 体验升级）；新增人物头像与 4 张能力卡图标；补齐市场页 4 个案例与 3 条 Prompt 模板；能力枚举移入 `description` 首句并删除平台不读的 `slogan`；技能中文名去掉黑话（`site-builder` → 网站开发）；`categoryId` 从平台不存在的 `developer-tools` 改为 `rd`，四个技能 `required` 统一为 `true`；参考用法定为「提取设计 DNA 装进自有内容」（沿用上游 design-dna 的三维框架，配色照 DNA，品牌标识与内容用自己的），并收敛到 `reference-dna.md`；本档改写为「配置源 + 状态 + 校验」结构；发布前加固把 strict 独立验证与轴范围改为硬校验（反转 1.1 的取舍，原做法可被绕过） |

本档按 §十 第 1 节的表格维护；每次包版本变更时更新顶部「对应包版本」与「最后同步」。
