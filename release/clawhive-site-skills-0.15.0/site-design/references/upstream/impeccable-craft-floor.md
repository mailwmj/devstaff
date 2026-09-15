# Impeccable 工艺下限

方向确定后、制作体验稿和正式页面时使用。已确认 brief、成熟设计系统和用户选择优先；本文件只守完成度，不替项目选择风格。

## 集中检查

以下检查应在同一轮桌面与移动渲染中完成，再集中修正，避免无边界微调：

- **Contrast：** 普通正文和 Placeholder 至少 4.5:1，大字至少 3:1；彩色表面上的次要文字从该色相或前景色推导。
- **Depth：** 阴影表达层次时同时具有 Offset 与 Soft Blur；无位移彩色 Halo 只是装饰。
- **Spacing：** 相关内容更紧、不同组更松；标题上方空间通常大于下方，并读取实际 computed value。
- **Type：** 连续正文约 65～75ch；正文、Label 和 Display 有明确尺度/字重层级；用真实中文、长词和极端内容检查换行。中文标题字距默认为 0。
- **Motion：** 至少有一个经过设计的反馈或转场即可，不给每段复制同一种入场。动效从内容可见的默认状态开始，并支持 Reduced Motion。
- **States：** 覆盖实际可达的 Hover、Pressed、Focus、Disabled、Loading、Error、Empty、Success 和真实内容。
- **Browser surfaces：** Selection、Caret、Scrollbar、Focus Ring、Underline Offset 和 Tabular Numerals 与设计系统一致；无必要时保留更可靠的系统默认。
- **Copy：** 使用产品自己的语言；控件说明动作，错误说明问题与恢复路径。
- **Coverage：** 每条页面设计合同要求都能在数秒内找到对应页面、状态和证据。

## 惯性答案检查

下面不是无条件风格禁令；用户 brief 或真实视觉世界可以使其中一项成立。没有依据时出现，说明设计没有做决定：

- 同尺寸的“图标 + 标题 + 正文”卡片成为整页结构；
- 大数字、短标签、辅助统计组成默认 Hero；
- 无信息价值的 Eyebrow、01/02/03 编号或 Pill；
- 不需要中断和保护 Focus 的任务被放进 Modal；
- Gradient Text、装饰性 Glass/Blur、粗色边卡片；
- 不属于 Neobrutalist 世界的硬 Offset Shadow；
- Sparkline、Progress Ring 或软阴影圆角矩形替代真实内容；
- Monospace 仅作为“技术感”装饰；
- 系统粗体字成为品牌页面的 Display Voice；
- Unicode 或 Emoji 替代一致的 Icon System；
- 几何 Mask 冒充人物、植物等有机轮廓；
- 类别名称决定 Light/Dark，而不是使用场景和环境光；
- 边框和阴影同时表达同一层级；
- 不属于内容世界的条纹、Grid Overlay、Noise 和 Sketch Illustration；
- 未提供的数字、评价、功能或配置被写成事实。

## 项目化约束

- Card 圆角、边界和层次使用页面合同中的 Token；Pill 只用于紧凑状态或控件。
- 真实插图或真实媒体优先；SVG 适合图标、几何、Diagram、Linework 和 Shader，不用来廉价模仿复杂照片。
- Background Texture 必须来自主题材料，不从装饰库随机挑选。
- 所有示例值明确标记，事实与商业承诺只能来自用户或可追溯来源。

全部机械检查通过后，仍要判断页面是否兑现选定母题、构图和内容重心；通过 Checklist 不等于设计成立。
