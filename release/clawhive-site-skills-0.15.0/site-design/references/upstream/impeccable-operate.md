# Impeccable：Operate 与 Read

用于工具、后台、设置、数据表格、编辑器、登录后工作区及长阅读页面。`Operate` 的目标是让界面融入任务；`Read` 的目标是理解、导航和再次定位。

## Product Slop Test

熟悉通常是优点。真正的问题不是界面克制，而是无意义的陌生：装饰按钮、不一致表单、标准任务上的自造交互、Label 使用 Display Font、与状态无关的动效。熟悉模式只有在改善当前任务时才改变。

## Typography

- 一个调校良好的字族通常足够承担 Heading、Button、Label、Body 和 Data。
- 工具界面使用稳定的 `rem` 字阶；不要让同一 H1 因容器宽度在 Sidebar 与主区之间漂移。
- 字阶比保持紧凑，角色靠尺寸、字重、颜色和间距共同区分。
- 连续正文仍控制 65～75ch；表格和数据可以更宽、更密。
- `Read` 页面优先保证章节、目录、引文和连续阅读，不把正文拆成卡片。

## Color

- 默认使用 restrained palette；强调色只服务 Primary Action、Selection 和重要状态。
- 定义 Hover、Focus、Active、Disabled、Selected、Loading、Error、Warning、Success、Info。
- Sidebar、Toolbar 和 Context Panel 可使用第二层中性色，与内容表面保持可辨但不过度强调。

## Layout

- Responsive 是结构变化：Sidebar Collapse、Table Reflow、Breakpoint-driven Columns；不是只缩字体。
- 高频路径靠稳定位置、对齐和键盘操作降低成本。
- 数据比较优先 Table/List，编辑优先 Workspace，解释性正文优先连续 Layout。

## Components And States

- 每个实际交互组件覆盖 Default、Hover、Focus、Active、Disabled 及适用的 Loading、Error、Success。
- Loading 使用能说明内容形状的 Skeleton；简单短操作可用局部 Progress，不让页面假死。
- Empty State 解释现状并给下一步，不只写“暂无数据”。
- 同一动作在不同页面保持相同名称、形状、反馈和保存语义。
- Dropdown、Popover 和 Dialog 不被 `overflow` 容器裁切；使用合适的原生能力或 Portal。

## Motion

- 常规状态转换约 150～250ms，并由共享 Token 控制。
- 动效解释状态、反馈、加载或层级，不阻碍连续操作。
- 不为工作区制作需要等待的整页开场动画。

## 可接受的熟悉模式

Operate 可以使用 System Font、Top Bar、Side Navigation、Breadcrumb、Tab、Command Palette、Table 和高信息密度。价值来自准确、稳定和一致，而不是每屏一个惊喜；品牌特征集中在少量高质量细节。

## 交接检查

- 用户进入页面后能否立刻开始主任务？
- 当前对象、状态、筛选和未保存变化是否清楚？
- 键盘、鼠标和触控路径是否符合使用频率？
- Loading、Empty、Error、Permission、Long Content 和 Reopen 是否保持语义一致？
- 只看 Heading、Label 和 Number 能否理解工作区？
- 是否存在可以移除而不损失任务含义的 Card、Border、Icon 或 Motion？
