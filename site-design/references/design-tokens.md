# 方向形成后的设计 token 校准

本包提供 10 个实现校准配方、10 套色彩、4 种排版、3 种密度、4 种形状和 4 类布局尺寸。配置见 `assets/design/tokens.json`；实际预览见 `assets/design/gallery.html`。它们只帮助把已形成的项目方向转成一致变量，不负责产生页面命题、信息架构或行业答案，也不是保证任何组合都高级的认证。

进入本文件前应已按 [设计上下文](design-context.md) 和 [页面方向合同](surface-brief.md) 确定用户路径、首屏结构和真实内容。若尚不能说明项目为何采用该结构，先回到方向判断，不通过挑选配方代替设计。

## 选择顺序

1. 用户参考或已有设计系统优先。已有 token 时做语义映射，不引入第二套全局变量覆盖它。
2. 根据已经确定的内容形状映射布局尺寸：阅读/写作 reading、记录/比较 workspace、收藏/作品 collection、介绍/叙述 story。名称只是校准入口，不是页面职责分类器；布局配置给尺寸与组织建议，不能自动生成信息架构。
3. 按内容选排版：中文长阅读 editorial、日常 UI system、温和叙述 humanist、大幅内容展示 display。字体是含中文回退的本机字体栈，不下载字体；实际设备必须查看回退效果。
4. 按操作频率与设备选密度：桌面高频比较可 compact，普通工具 comfortable，展示 spacious。紧凑模式下触屏仍使用 44px 的项目默认操作高度；不能通过压小正文容纳内容。
5. 按品牌与内容气质选色彩/形状。深色要有明确需求或选定依据，不把“高级”直接翻译成黑底发光。
6. 展示项目自己的代表页面、完成选择后导出并复验。更换任一维度后重新看布局和实际色对，不仅看色板。

## 推荐配方

| 配方 | 用途 | 组合重点 |
| --- | --- | --- |
| reading-journal | 长文、读书笔记 | 纸页松墨、中文阅读、平面排版 |
| quiet-library | 书目/资料收藏 | 亚麻橄榄、温和标题、清晰索引 |
| daily-workspace | 日常记录工具 | 石墨瓷白、舒适密度、柔和控件 |
| precise-operations | 桌面业务记录 | 钴蓝、紧凑密度、清晰边界 |
| warm-service | 独立品牌/服务 | 陶土暖白、叙述排版、舒展空间 |
| creative-portfolio | 作品内容 | 梅紫、展示字阶、平面结构 |
| calm-planner | 计划/习惯 | 深青海盐、舒适密度、圆润形状 |
| friendly-community | 社群/活动 | 莓红柔粉、温和叙述、亲和形状 |
| night-studio | 明确需要深色的创作工具 | 夜蓝、清晰 UI、舒适密度 |
| dark-archive | 明确需要暗色的藏品展示 | 炭黑琥珀、展示字阶、平面结构 |

配方是实现校准 profile，不是视觉方向、用途分类器或用户确认。用户可以选择另一种表达；不把颜色与行业或人群刻板绑定。不同方向若只有配方变化，应视为同一个结构方向，而不是多个候选。

## 使用工具

先解析 `site-design` 的安装目录，再使用绝对脚本路径；Windows 可按实际环境使用 `py -3`：

```sh
python3 /absolute/site-design/scripts/design.py list
python3 /absolute/site-design/scripts/design.py validate
python3 /absolute/site-design/scripts/design.py build --recipe reading-journal --out /absolute/project/design-choice
python3 /absolute/site-design/scripts/design.py build --recipe daily-workspace --palette ocean --density compact --shape crisp --out /absolute/project/alternate-choice
```

输出目录须为新目录或空目录，已有内容拒绝覆盖。输出 `tokens.css`、`selection.json` 与 `intent.md`；后两者分别记录工具配置和待补充的人类设计意图。它们不是设计方向或用户选稿凭证；确认结果按 [体验流程](prototype.md) 交给 `site-brief` 写入 `.site/brief.md`，正式实现约束由 `site-builder` 写入 `.site/implementation-plan.md`。

制作体验稿时只把 CSS 和按需使用的 `primitives.css` 复制到隔离的体验稿目录；把选定 token 和文件路径交给 `site-builder`，由它按项目结构应用到正式工程。最终运行不能依赖 Skill 安装路径。工具只生成 token，不替换现有页面、存储或业务逻辑。

## 变量职责与应用

- `--ds-canvas/surface/surface-raised`：页面与表面；`text/text-muted`：文字层级。
- `accent/on-accent/accent-hover`：主要操作；`selection/on-selection`：选中反馈。
- `success/error/warning` 与配对 surface：语义反馈，不用品牌色替代所有状态。
- `border` 用于非关键分隔，`border-control` 用于需要辨识的控件边界，不能互相替代。
- `font-*`、`text-*`、`weight-*`、`leading-*`：字体、字阶和行距；中文标题字距默认 0。
- `space-*`、`control-*`、`row-height`、`panel-padding`、`layout-gap`：统一空间节奏。
- `radius-*`、`shadow-*`、`focus-*`、`motion-*`、`z-*`：形状、层次、焦点和反馈。
- `content-max/reading-max/sidebar-width/grid-min`：布局尺寸起点。`breakpoint-narrow` 是记录值；CSS 自定义属性不能直接代入媒体查询条件，须同步采用实际断点数值并验证。

shadcn 或其他库的 background/foreground/primary/input/ring 等语义变量应映射到对应角色；映射还应检查库的色值格式和当前主题 API，不能盲目拼接 hsl()。已有 Tailwind 等系统时在其统一主题处维护，不在每个页面重复硬编码。

修改品牌色时同时复核按钮文字、悬停、链接、焦点与选中状态；不要只改一个 accent。工具检查目录内指定的不透明色对，文字默认目标 4.5、控件边界与焦点默认目标 3。它不检查透明、图片叠层、动态状态、实际字体、所有邻接背景或色觉辨识，不代表整页无障碍合规。
