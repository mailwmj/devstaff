# 方向形成后的设计 token 校准

本包提供实现校准配方、10 套色彩、6 种排版角色分配、3 种密度、4 种形状和 4 类布局尺寸。配置见 `assets/design/tokens.json`；实际预览见 `assets/design/gallery.html`。它们只帮助把已形成的项目方向转成一致变量，不负责产生页面命题、信息架构、母题或行业答案，也不是保证任何组合都高级的认证。

进入本文件前应已按 [设计上下文](design-context.md)、[页面设计合同](surface-brief.md) 和 [视觉方向](visual-direction.md) 确定用户路径、首屏结构、真实内容与母题。**尚不能说明母题从哪来时，不要进入 token 选择**——挑选配方不能代替设计判断，**没有任何一个配方能作为"方向"提交给用户**。这条由 `build` 的方向闸门机械执行，不靠提醒。

## 选择顺序

1. 用户参考或已有设计系统优先。已有 token 时做语义映射，不引入第二套全局变量覆盖它。
2. 根据已经确定的内容形状映射布局尺寸：阅读/写作 reading、记录/比较 workspace、收藏/作品 collection、介绍/叙述 story。名称只是校准入口，不是页面职责分类器；布局配置给尺寸与组织建议，不能自动生成信息架构。
3. 按**角色分配**选排版（见 [工艺审查](craft-review.md)）：`ui` 无衬线统一承担界面、`reading` 宋体承担标题与连续正文、`narrative` 衬线标题配无衬线正文、`display` 大尺度无衬线标题主导构图、`cultural` 楷体标题与引文、`technical` 无衬线与等宽数字、字阶更紧。字体默认是含中文回退的**本机字体栈**（零下载、离线可用、渲染最锐利）。**设计需要时可以加载网络字体**（西文/数字展示字体、品牌指定字体，中文按 [中文排版规范](chinese-typography.md) 的子集化例外），但每个加载字体都必须同时写出系统栈回退，并在断网或加载失败时保持首屏与主任务版式不破：**外部资源是增强，不是必需品**。实际设备必须查看回退效果。

   加载字体按外部资产登记：在本合同的 [素材地图](surface-brief.md) 里为每个字体开一行 `AS-*`，填来源 URL、许可、子集范围（实际用字或字符集）、回退栈与加载策略，状态用 `ready / missing / replace` 反映它是否真的可用。**字体不是"只是 CSS"就免登记**——没有这一行，回退与许可就没有落点，token 里写下的字体名只是无法验收的散文。
4. 按操作频率与设备选密度：桌面高频比较可 compact，普通工具 comfortable，展示 spacious。紧凑模式下触屏仍使用 44px 的项目默认操作高度；不能通过压小正文容纳内容。
5. 按品牌与内容气质选色彩/形状。深色要有明确需求或选定依据，不把“高级”直接翻译成黑底发光。色彩应从真实来源采样并按 [工艺审查](craft-review.md) 收敛成语义角色；本包的色板只是实现示例，不作为采样依据。
6. 展示项目自己的代表页面、完成选择后导出并复验。更换任一维度后重新看布局和实际色对，不仅看色板。

## 推荐配方

配方是**实现校准 profile**，按内容形状与任务性质索引，不是视觉方向清单，也不能用来替代母题推导。引用具体色值前先按第 5 条确认采样来源。

| 配方 | 用途 | 组合重点 |
| --- | --- | --- |
| reading-journal | 长文、读书笔记 | 纸页松墨、中文长阅读、平面排版 |
| field-notes | 田野记录、课程手记、文化考察 | 纸色、楷体标题与引文、平面排版 |
| quiet-library | 书目/资料收藏 | 亚麻橄榄、温和叙述、清晰索引 |
| daily-workspace | 日常记录工具 | 石墨瓷白、清晰界面、柔和控件 |
| precise-operations | 桌面业务记录 | 钴蓝、密集数据、紧凑密度 |
| warm-service | 独立品牌/服务 | 陶土暖白、温和叙述、舒展空间 |
| creative-portfolio | 作品内容 | 梅紫、展示字阶、平面结构 |
| calm-planner | 计划/习惯 | 深青海盐、清晰界面、圆润形状 |
| friendly-community | 社群/活动 | 莓红柔粉、温和叙述、亲和形状 |
| night-studio | 明确需要深色的创作工具 | 夜蓝、密集数据、舒适密度 |
| dark-archive | 明确需要暗色的藏品展示 | 炭黑琥珀、展示字阶、平面结构 |

配方是实现校准 profile，不是视觉方向、用途分类器或用户确认。用户可以选择另一种表达；不把颜色与行业或人群刻板绑定。不同方向若只有配方变化，应视为同一个结构方向，而不是多个候选。

## 使用工具

先解析 `site-design` 的安装目录，再使用绝对脚本路径；Windows 可按实际环境使用 `py -3`：

```sh
python3 /absolute/site-design/scripts/design.py list
python3 /absolute/site-design/scripts/design.py validate
python3 /absolute/site-design/scripts/design.py sync-gallery   # 改过 tokens.json 后刷新 gallery 内嵌目录
python3 /absolute/site-design/scripts/design.py build --recipe reading-journal --project-root /absolute/project --out /absolute/project/design-choice
python3 /absolute/site-design/scripts/design.py build --recipe daily-workspace --palette ocean --density compact --shape crisp --project-root /absolute/project --out /absolute/project/alternate-choice
```

`build` 默认先过**方向闸门**：它从 `--project-root`（缺省为当前目录）读取 `.site/design/surface-brief.md`，合同缺失、不可读，或母题 / 反默认原因 / 构图命题 / 细节签名未填、未引用合同自己声明的项目事实时，直接拒绝并列出 blocker code，**不写任何文件**。闸门只组合已有规则（`check-contract` 的 direction 阶段 + 本文件要求的四项判断），不新增自己的判据。

放行后 `selection.json` 会记录 `direction_evidence`：`{"mode": "direction-gate", "contract_sha256": ...}`，把这次校准钉在具体的合同版本上；合同一改，旧选择即可判定过期。确实只需要一份无方向依据的草稿时，显式加 `--standalone`，产出会标记 `{"mode": "standalone"}` 并在 `intent.md` 顶部写明"未读取任何项目合同"。**没有任何理由在真实项目里静默使用 `--standalone`。**

输出目录须为新目录或空目录，已有内容拒绝覆盖。输出 `tokens.css`、`selection.json` 与 `intent.md`；它们都是隔离的校准草稿，不是项目规格、设计方向或用户选稿凭证。只把最终采用的语义映射、项目理由和例外合并进 `.site/design/surface-brief.md`；`site-builder` 的实施计划引用该合同，不另行定义视觉事实。

`validate` 检查每个配方与每套色板的**列出色对**和**排版下限**（字号、正文行高、中文标题字距、字体许可），并会把不合格的配方判为失败——它守的是目录默认值，不是你的页面。`sync-gallery` 在 `tokens.json` 变化后重新注入 gallery 的内嵌目录，避免预览与配置漂移。

制作体验稿时只把 CSS 和按需使用的 `primitives.css` 复制到隔离的体验稿目录；把选定 token 和文件路径交给 `site-builder`，由它按项目结构应用到正式工程。最终运行不能依赖 Skill 安装路径。工具只生成 token，不替换现有页面、存储或业务逻辑。

## 变量职责与应用

- `--ds-canvas/surface/surface-raised`：页面与表面；`text/text-muted`：文字层级。
- `accent/on-accent/accent-hover`：主要操作；`selection/on-selection`：选中反馈。
- `success/error/warning` 与配对 surface：语义反馈，不用品牌色替代所有状态。
- `border` 用于非关键分隔，`border-control` 用于需要辨识的控件边界，不能互相替代。
- `font-*`、`text-*`、`weight-*`、`leading-*`、`font-data`：字体角色分配、字阶和行距；**中文标题字距默认 0**，`tracking-heading` 只在西文 display 上才考虑轻微收紧。数字对齐用 `data-numeric: tabular-nums`。
- `space-*`、`control-*`、`row-height`、`panel-padding`、`layout-gap`：统一空间节奏。
- `radius-*`、`shadow-*`、`focus-*`、`motion-*`、`z-*`：形状、层次、焦点和反馈。
- `content-max/reading-max/reading-measure/sidebar-width/grid-min`：布局尺寸起点。连续正文行长用 `reading-measure` 这类 `ic`/`em` 单位表达，不用固定 px。

shadcn 或其他库的 background/foreground/primary/input/ring 等语义变量应映射到对应角色；映射还应检查库的色值格式和当前主题 API，不能盲目拼接 hsl()。已有 Tailwind 等系统时在其统一主题处维护，不在每个页面重复硬编码。

修改品牌色时同时复核按钮文字、悬停、链接、焦点与选中状态；不要只改一个 accent。工具检查目录内指定的不透明色对，文字默认目标 4.5、控件边界与焦点默认目标 3。它不检查透明、图片叠层、动态状态、实际字体、所有邻接背景或色觉辨识，不代表整页无障碍合规。

**工具全部通过不等于设计通过。** token 表里相邻的色，和渲染后真正落在一起的色不是一回事；目录里的字号，也不是最终页面的字号。展示前必须按 [工艺审查](craft-review.md) 在实际渲染上重做字面、色对与触控断言。
