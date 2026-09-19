# 渐进式建站 Skills

一套让 Coding Agent 把自然语言想法变成可使用网站的轻量执行协议（版本 1.1）。

## 定位

用户不需要理解 Skill、阶段或技术栈。用户只需要说清楚想做什么，Agent 负责把它收敛成一个能完成核心任务的首版，并诚实说明验证范围。

默认体验只有一条短路径：

```text
理解核心任务 → 展示一个方向 → 用户确认 → 实现 → 交给他看 → 他点头才验证 → 交付
```

复杂度服务于风险，不服务于流程完整感。

## 三档路径

| 路径 | 适用 | 用户能感知的流程 |
| --- | --- | --- |
| `quick` | 文案、颜色、间距和明确 Bug | 修改 → 相称检查 → 说明结果 |
| `guided` | 新建小网站、普通工具和多页面首版 | 核心任务 → 一个可见方向 → 实现 → 核心检查 |
| `strict` | 权限、支付、隐私、共享数据、公开部署和多人协作 | guided + 独立检查和适用风险证据 |

`quick` 是无状态捷径；默认状态模式是 `guided`。只有真实风险或协作关系要求时才使用 `strict`。

## 执行模型

```text
site-builder  唯一编排者，决定下一步并停在需要用户决定的地方
├── site-brief  收敛一个核心任务和首版范围
├── site-design 保留完整设计知识库，按需产出方向、体验稿和设计合同
└── site-check  只读验证，返回实际证据和未验证项
```

子 Skill 不继续调用其他 Skill，也不自行宣布交付。它们完成一个任务后只返回 `status / summary / artifacts / evidence / limitations` 五个字段；`site-builder` 重新读取状态后继续。

四个 Skill 对用户说话、以及写网站文案时，统一按 `AGENTS.md` 的《说人话》写：说清谁做了什么，不抬高、不凑三连、不用大词。文风只有这一处来源，其他文件只引用不复述。

## 第一性原理

系统只解决三种失败：

1. **做错东西**：先确认核心用户、任务和方向。
2. **做不完东西**：按一条可完整体验的任务切首版。
3. **误以为做完**：验证实际核心路径，并区分 `verified` 和 `limited`。

指纹是身份检查，不是重跑清单。合同和产品源码各有一个 SHA-256，报告必须带上当前这一份：对不上就说明报告说的不是这个产物，不能靠"只重验受影响的部分"救回来。至于改动之后要重跑哪些轴，交给判断，不交给文件后缀——一条 `display:none` 能让核心任务消失，和挪一个像素的代价一样。没重跑的轴如实记 `limited`。

指纹只覆盖产品源码，跑起来才会变的东西（数据库、日志、构建产物）排除在外，否则卖出一瓶水就能让报告过期。代价是随产品发布的只读库和运行期状态在指纹里长得一样，机器分不出来，所以 `plan` 会把排除清单列出来让人读一遍。

空样本是这套流程里唯一能静默通过的错误：选择器没命中时对象是 0 个，`every()` 对空列表恒真，手上那些断言会全部通过。报告字段拦不住它——填一个数进去没人能核对。拦得住它的只有两处：探针自己扫到 0 个对象时判失败，和另一个验证者。验证期间源码禁写也是同一个道理：对象在验证途中被移动，那轮结论就不成立。

一条规则只有当工具能不依赖 agent 配合地判定它时，才做成门禁。指纹、状态跃迁、模式要求都合格——工具自己算得出来，agent 说什么都不影响结论。

要求 agent 在报告里填字段的，按字段性质分开：**描述**留，**自证**删。`observed` 和 `evidence` 是描述，下一个读报告的人和独立验证者靠它们判断发生了什么，为空说明这份报告没话可说，值得拦。`subjects: 24` 这类数字是自证，读者无法核对，却长得像测量结果——它把未经核实的说法洗成了证据的样子，比不写更糟。拦不住存心的，只会让照做的人多填几个空，还让读报告的人以为有人核过了。

这条线以下的东西都只是文档里的一句话，而且只有一处。

严格模式仍使用同一个小状态接口，只额外要求独立验证和适用的风险证据；不复刻租约和逐项覆盖矩阵。它们只有在真实使用证明有必要后才应该加入。

## 设计能力

系统精简的是确认流程，不是设计专业能力。`site-design` 保留：

- 从项目事实形成结构和视觉方向的方法；
- 页面设计合同、流程体验稿和参考还原模板；
- 排版、色彩、素材、构图、响应式、组件状态、无障碍与工艺审查规范；
- Token、gallery、基础样式和可导出的校准配方；
- `design-intelligence` `2.13.0` 的内置检索代码、数据与 MIT 许可。

这些内容按任务分支加载。普通 guided 项目只填写设计合同的适用字段；完整模板不会变成新的用户门禁。内置 UI/UX 数据作为固定版本快照打包，保证独立安装和复现。

## 仓库结构

分发内容与开发内容分开放置：

```text
release/          唯一分发根。整个目录可独立打包安装，不依赖仓库其他部分
├── skills.json   技能清单
├── install.py    安装器
├── AGENTS.md     需要加入宿主项目指令的协议文件
└── site-brief/ site-builder/ site-check/ site-design/
tests/            开发用测试
.github/          开发用 CI
README.md  AGENT-GUIDE.md   开发用文档
```

只分发 `release/`。校验、安装与测试命令都从仓库根目录执行，路径以 `release/` 开头。

## 安装

使用安装器进行安装：

```text
python3 release/install.py /path/to/agent-skills
```

它会安装 `site-builder`、`site-brief`、`site-design`、`site-check`，并返回需要加入宿主项目指令的 `AGENTS.md` 路径。已有安装时，显式使用 `--replace` 整套替换。状态脚本随 `site-builder` 一起安装。

也可以只打包分发根：`git archive --format=tar HEAD:release | tar -xf - -C /tmp/site-skills`，解包后的目录本身就是可安装的完整包。

## 状态接口

状态只有五种：`discovering / decided / building / blocked / delivered`。Agent 每轮执行同一个控制回路：

```text
preflight → 执行 next_action → 写入结果 → 再次 preflight
```

示例：

```text
python3 release/site-builder/scripts/state.py init PROJECT --mode guided
python3 release/site-builder/scripts/state.py preflight PROJECT
python3 release/site-builder/scripts/state.py decide PROJECT \
  --task "登记库存并查看剩余数量" \
  --direction "单工作台展示当前库存和新增入口" \
  --quote "就按这个方向做"
python3 release/site-builder/scripts/state.py start PROJECT
python3 release/site-builder/scripts/state.py handoff PROJECT
python3 release/site-builder/scripts/state.py begin-check PROJECT --quote "看着没问题，测吧"
python3 release/site-builder/scripts/state.py verify PROJECT --report .site/check/report.json
```

`handoff` 把这一版交到用户手上并停下等他回话；`begin-check` 只能开在他点头之后，要带上他的原话。页面在他看过之后又改过（源码或合同任一变动），这一轮就开不起来，得重新交一次。这一轮关掉之前源码是禁写的，要回去修就先 `cancel-check --reason`，修完重新交给他看。

`verify` 只收检查报告，不收手写的 `--status`：状态由报告里的轴算出来，报告先过 `check.py validate-report` 这一关，指纹对不上当前源码、或某条轴没写清自己查了什么，都不算数。没重跑的轴在报告里如实记 `limited` 并写明是哪条，strict 的 `limited` 不能交付。局部修改不初始化 `.site`。

新建与整体改版先判断是否存在真实的信息拓扑分歧：没有分歧时用 `discover --structure single`，跳过结构选择进入方向准备；有分歧时才用 `choice` 登记 2 种候选并复制 `site-design/assets/design/preview-shell.html` 写成单文件骨架预览（色板与深色切换条用现成的，正文按项目自己搭，两版只在结构上不同，优先引导客户端自带浏览器打开），用户选定后用 `select-structure --candidate ... --quote ...` 记录。之后提供 2 种视觉风格单页体验稿（同一骨架、同一顶栏，轻量对比，严禁过度测试），用户微调满意后将 CSS 变量提取为 Token、核心 HTML 作为纵向切片模板，再用一句不同的原话 `decide` 锁定完整方向：

```text
python3 release/site-builder/scripts/state.py discover PROJECT \
  --structure choice --reason "信息架构差异：看板流 vs 向导流" \
  --candidate "看板全景流" --candidate "任务向导流"
python3 release/site-builder/scripts/state.py select-structure PROJECT \
  --candidate "看板全景流" --quote "选看板流"
```

视觉风格选定并微调后，执行 `decide` 锁定方向，`select-structure` 与 `decide` 的两句原话不能相同。局部修改或已有成熟规范的局部修复不触发结构选择。

状态工具只防止顺序错误、空证据和不满足模式要求的跃迁。它不能判断用户原话的真实语义，也不能证明证据内容属实；strict 的 `--independent` 只能在独立 Checker 上下文实际完成检查后使用。

## 1.1 变更

验证轮之前多了一道停：构建完成后先 `handoff` 把这一版交到用户手上，他看过并点头，才用 `begin-check --quote "他的原话"` 开验证轮。理由是一轮验证比他自己翻一遍贵得多，而报告只对写它的那一版成立，他看完再让你改一次，刚跑完的那轮就白跑了。`handoff` 记下当时的合同与源码指纹，之后动过其中任何一个，开轮会被拒，要求重新交付。`cancel-check` 之后同理：修完要重新交付，并拿到一句新的原话。

检查协议修了一处 fail-open：合同文件读不出来时，`validate-report` 原先是跳过指纹比对，结果是删掉合同就能拿旧报告交付；现在直接判报告无效。

源码指纹的排除规则改了。`AGENTS.md`、`CLAUDE.md`、声明了 `skills.json` 时的工具链目录、`skills.json`、`install.py`、`.playwright-cli` 都不进指纹；状态文件后缀（`.db` 之类）改成任意层级都忽略，不再只限根目录。检查器自己所在的 `site-check` 目录仍留在指纹里：能被中途放松的检查说不了算数。

`plan` 去掉了 `--full-manifest`，源码清单始终输出。site-builder 与 site-check 现在随包分发自己的测试。

## 维护与测试

```text
python3 -m unittest discover -s tests -p 'test_*.py'                              # 开发用测试
python3 -m unittest discover -s release/site-design/scripts/tests -p 'test_*.py'  # 随包分发
python3 -m unittest discover -s release/site-builder/scripts/tests -p 'test_*.py'
python3 -m unittest discover -s release/site-check/scripts/tests -p 'test_*.py'
python3 release/site-design/scripts/design.py validate
```

`release/site-*/scripts/tests/` 下的是随包分发的测试，装到宿主项目后也能跑；仓库根 `tests/` 是开发用测试，跟着仓库走。`.github/workflows/verify.yml` 在 Python 3.10 与 3.12 上跑这几条，并从 `git archive HEAD:release` 解出的干净归档里再装一次，确认分发包自带的东西是完整的。
