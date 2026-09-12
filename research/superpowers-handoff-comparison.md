# 对照评审：superpowers 如何解决 Skill 之间的交接

> 对象 A：本仓库四个 `site-*` Skill（v0.8.0）
> 对象 B：[obra/superpowers](https://github.com/obra/superpowers)，`package.json` version **6.3.0**，main @ `b36e0829c6d0140e93cfef2ca599b1b07d4a7797`
> 方法：完整取回 B 的仓库（`skills/` 14 个 Skill、`hooks/`、6 个宿主插件清单、`docs/porting-to-a-new-harness.md`、`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`），围绕"交接"这一件事精读；A 侧逐文件核对。
> 本文只回答一个问题：**A 在"Skill 之间怎么交接"上比 B 差在哪、能拿什么、不能拿什么。**

## 0. 结论摘要

B 没有把"交接"当成一个文档问题，而是拆成互不替代的四层，每层单独解决：

| 层 | B 的解法 | 落地物 |
| --- | --- | --- |
| 1. 静态路由边：下一步该调用谁 | 正文里写死的 `REQUIRED SUB-SKILL` 硬标记 + `HARD-GATE` 禁止项 | `research` 所引的各 `SKILL.md` |
| 2. 动态触发：模型凭什么会去调用 | 会话启动**强制注入** bootstrap（`using-superpowers` 全文）+ "1% 规则" + Skill Priority + Red Flags 表 | `hooks/session-start`、`GEMINI.md`、`.opencode/plugins/` |
| 3. 载荷：交接什么 | **文件**而不是对话：spec → plan → brief → report → review-package → ledger | `docs/superpowers/plans/`、`.superpowers/sdd/<plan>/` |
| 4. 跨 agent 交接契约 | 四态回报（DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED）+ 固定提示词模板 + 报告只落文件 | `implementer-prompt.md`、`task-reviewer-prompt.md`、`re-review-prompt.md`、`scripts/task-brief` |

**A 的差距不在第 3、4 层，而在第 2 层。**

- 第 1 层：✅ 有，且比 B 更严（`skills.json` 依赖图 + 协作回执 + `state.py` 门禁）。但路由边只以散文散落在四个 `SKILL.md` 与 `site-builder` 步骤 1，没有 B 那种可机械校验的显式标记。
- 第 2 层：❌ **最大缺口**。全仓库没有任何 bootstrap / SessionStart / 会话启动注入的等价物（已 grep 核对，无 `hooks/`、无插件清单）。当前是把 4 个 frontmatter `description` 丢给宿主，由模型自行匹配。对小白用户，这是最脆的一环。解法见 [`host-injection-surfaces.md`](host-injection-surfaces.md)（结论：用宿主自动加载的指令文件承载，**不用 hook**）。
- 第 3 层：⚠️ 部分具备（`.site/brief.md`、`implementation-plan.md`、`.site/checks/`），缺 B 的 **progress ledger**——一个抗上下文压缩的进度账本。`state.json` 是引擎状态，不回答"这一轮做到第几个切片"。
- 第 4 层：✅ 规范上有（Writer/Checker 严格串行 + `handoff` 冻结指纹 + `check_id`），强度高于 B；缺的是 B 的"每任务新 subagent + 报告只落文件"执行结构。

一句话：**A 该补的是"触发前的路由"，不是"交接本身"。** 而用户侧 agent 配置文件（下称**用户侧 AGENTS.md**）正是承载第 1、2 层、又不污染 A 已有门禁机制的正确位置。

## 1. 先把两份 AGENTS.md 分开

这是本次评审最容易出的错，先固定术语，后文只按这两个名字称呼。

| | 开发侧 AGENTS.md | 用户侧 AGENTS.md |
| --- | --- | --- |
| 位置 | 本仓库根 `AGENTS.md` | 随 Skill 安装到用户的 agent 配置里（每个 agent 一份） |
| 读者 | 开发和评测这套 Skill 的人/agent | 用户的 coding agent |
| 内容 | 画像评测运行协议、`F-*` 夹具、两名真人、RC/SD/MV 用例、评分与否决项 | **路由表**（什么情况用什么 Skill）、门禁红线、能力降级规则 |
| 事实来源 | `tests/novice-user-evaluation.md`、`tests/site-design-scenarios.md` | `skills.json`、四个 `SKILL.md` 的 frontmatter、`tests/scenarios.md` 的运行时投影 |
| 生命周期 | 跟仓库版本走 | 跟宿主与项目走，可在安装时/每项目覆盖 |
| 能不能混 | **不能。** 用户侧文件里出现"两名真人评测者""夹具哈希""RC-21"会让小白莫名，而且它引用的文件在用户机器上不存在 |

两者唯一共享的是**事实来源**，不是内容。用户侧文件由 `tests/scenarios.md` 投影而来，而不是由 `AGENTS.md` 裁剪而来。

## 2. B 的交接机制（分层穷举）

### 2.1 静态路由边：写死，而且只写一条

B 在 Skill 正文里用固定字面量标注调用边：

- `skills/executing-plans/SKILL.md:37` → `- **REQUIRED SUB-SKILL:** Use superpowers:finishing-a-development-branch`
- `skills/writing-plans/SKILL.md:166,170` → `subagent-driven-development`（推荐）或 `executing-plans`
- `skills/writing-skills/SKILL.md:18` → `**REQUIRED BACKGROUND:** You MUST understand superpowers:test-driven-development`

两个设计细节值得抄：

1. **终点唯一。** `brainstorming/SKILL.md:231`：*"Do NOT invoke any other skill. writing-plans is the next step."* 路由边不允许分叉——分叉由用户选择产生（选执行方式），不由模型自由发挥。
2. **禁止项和调用边写在同一个位置。** `brainstorming` 顶部是 `<HARD-GATE>`（未获批准不得写任何代码），底部是唯一后继。门禁和前进一步在同一个文件里闭合，模型不可能只读到一半。

**A 现状：** 语义等价物齐全（`site-builder` 步骤 1/2/3/7 写明调用谁、停在哪），但：① 无统一标记，靠自然语言；② `scripts/verify_skills.py` 校验的是 `skills.json` 的依赖图与环，**不校验正文里的调用链**，所以 SKILL.md 里写错一个 Skill 名不会被 CI 抓到。

### 2.2 动态触发：bootstrap 就是整个集成

B 的判断极其直白（`docs/porting-to-a-new-harness.md`）：

> **The bootstrap is the entire integration.** Without it, the skill files are inert — present on disk, never invoked.

机制：宿主会话启动时，把 `skills/using-superpowers/SKILL.md` **全文**注入模型上下文，包在 `<EXTREMELY_IMPORTANT>` 里（`hooks/session-start`；Shape C 宿主用 `GEMINI.md` 的两行 `@`-include）。这份 bootstrap 里装的是三样东西：

1. **1% 规则**：只要有 1% 可能适用就必须先调用 Skill，且**先于任何回应**，包括澄清提问；
2. **Skill Priority**：process skill 优先于 implementation skill（"Let's build X" → 先 `brainstorming`；"Fix this bug" → 先 `systematic-debugging`）；
3. **Red Flags 表**：把"这太简单了不用查""我先看看代码""我记得这个 skill"逐条反驳成表格。

并且它有**可执行的验收测试**：干净会话发 `Let's make a react todo list`，必须在写任何代码前自动触发 `brainstorming`，PR 必须附完整 transcript。

**A 现状：** 无任何等价物。对小白用户这是致命的：小白不会说"帮我做需求梳理"，他只会说"帮我做个网站"。当前只能指望宿主把 `site-builder` 的 description 匹配上——而 `site-builder` 的 description 本身就说它会"作为默认编排入口调用 site-brief/site-design/site-check"，模型完全可能读成"我自己直接开干"。**A 的门禁比 B 严，但触发比 B 弱，这是当前结构里最大的不对称。**

### 2.3 载荷是文件，不是对话

B 明说理由（`subagent-driven-development/SKILL.md`）：

> Everything you paste into a dispatch prompt — and everything a subagent prints back — stays resident in your context for the rest of the session and is re-read on every later turn. Hand artifacts over as files.

因此每一跳都是"脚本产出文件 → 只传路径"：`scripts/task-brief PLAN_FILE N` 抽出单个任务文本；`scripts/review-package PLAN_FILE BASE HEAD` 生成 diff 包；报告写 `task-N-report.md`，回给控制器的只有状态、commit、一行测试摘要和 concerns。

**A 现状：** `.site/brief.md`、`.site/implementation-plan.md`、`.site/checks/` 已经是文件载荷，方向一致。**缺口是 progress ledger**：B 用 `.superpowers/sdd/<plan>/progress.md`，首行写归属的 plan 路径（防止读错别人的账本），每任务一行 `Task <N>: complete (commits a1b2c3d..d4e5f6a, review clean)`，fix round 单独一行。它的存在理由是：

> Conversation memory does not survive compaction. … controllers that lost their place have re-dispatched entire completed task sequences — the single most expensive failure observed.

A 的 `state.json` 记的是**门禁状态 + 租约 + 指纹**，机械强度远高于 ledger，但它不记"首版拆成 3 个切片，第 2 个已完成"。上下文压缩后，A 的模型同样会重做切片。**结论：ledger 是 state.json 的补充，不是替代，也不该合并进 state.json**（那会让唯一写入者的边界被撑破）。

### 2.4 跨 agent 交接契约

B 的四态回报与处置（`subagent-driven-development/SKILL.md` "Handle the report"）：

| 状态 | 控制器动作 |
| --- | --- |
| `DONE` | 生成 review package，派任务 reviewer |
| `DONE_WITH_CONCERNS` | 先读 concerns；涉及正确性/范围就先处理，纯观察则记录后继续 |
| `NEEDS_CONTEXT` | 补上下文，重派 |
| `BLOCKED` | 分因处置：缺上下文补上下文；要推理就升级模型；任务太大就拆小；计划本身错就 ruling 并带着结论重派 |

外加：**每任务一个新 subagent**、**fix loop 最多 5 轮且每轮必须重新过一遍 scoped re-review**、**reviewer 只能审 diff 不能看会话历史**。

**A 现状：** 回执状态枚举已有且更细（`ready|needs_user|blocked`、`draft_ready|visual_confirmed|flow_decided|review_complete|needs_user|blocked`、`passed|failed|incomplete|blocked`），语义与 B 同构。缺两点：① 报告落文件、只回传状态与凭据的纪律；② 提示词模板文件（A 完全没有模板，全靠调用者即兴组织交接内容）。

### 2.5 平台适配：Skill 正文只写动作，不写工具名

B 的第二条铁律：

> **Everything ships through the harness's own install mechanism. Never edit the user's files.** … A port **must not** reach into a user's global or personal config (`~/.gemini/config/AGENTS.md`, `settings.json`, a hand-edited `~/.bashrc`, etc.) to inject anything.

适配层单独放 `skills/using-superpowers/references/<harness>-tools.md`（现有 antigravity / codex / gemini / hermes / pi 五份），把"dispatch a subagent"翻成该宿主的真实工具名；`SKILL.md` 正文一律不改。

**A 现状：** 四个 `SKILL.md` 已经是动作式写法（"调用 `site-brief` Skill"），这点是对的。但宿主适配只有 `agents/openai.yaml` 的三个 interface 字段；README 里那张"能力与支持矩阵"是**给人读的文档，不是可执行适配**——没有对应 B 的 `references/<harness>-tools.md` 的落地物。

### 2.6 A 反而强于 B 的地方（不要为了抄而退回去）

- **同意/授权**：B 的答案只有 `<HARD-GATE>` + 会话内批准，**没有任何记录**。A 有 `--quote` 原文留存、`quote_sha256` 防复用、`consent_replay` 交付回放。这是 A 的核心资产。
- **交接冻结**：A 的 `handoff` 校验 PID 已结束、端口已释放、登记正式服务、冻结源码指纹，`start-verify` 在指纹变化时拒绝——B 没有等价机制（它靠 git commit 边界）。
- **验收凭据**：A 的 `check_id` 绑定冻结指纹，阻断项必须有 `artifact`/`command` 证据且事后不可改动。B 只有 reviewer 的文字结论。

## 3. 逐条对照表

| 维度 | B（superpowers 6.3.0） | A（本仓库 v0.8.0） | 判定 |
| --- | --- | --- | --- |
| 静态路由边 | `REQUIRED SUB-SKILL` 固定字面量，终点唯一 | 散文式写在步骤里，无标记 | ⚠️ 补标记 |
| 路由的机械校验 | 无（靠 prose 约定） | `verify_skills.py` 校验 `skills.json` 依赖图与环 | ✅ A 强，但未覆盖正文调用链 |
| 会话启动引导 | SessionStart hook 注入 bootstrap 全文（Shape A/B/C） | **无** | ❌ 最大缺口 |
| 触发反合理化 | 1% 规则 + Skill Priority + Red Flags 表 | 部分散见（`site-builder` 快速分支、`tests/scenarios.md` 的"禁止误判"） | ⚠️ 未进入运行时 |
| 触发器验收测试 | `Let's make a react todo list` 必须自动触发 | 无（`tests/scenarios.md` 是人工回放） | ❌ |
| 交接载荷 | spec / plan / brief / report / review-package / ledger，全文件 | brief.md / implementation-plan.md / checks/ | ✅ 基本一致 |
| 进度账本 | `progress.md`（首行归属校验，抗压缩） | 无（`state.json` 不记进度） | ❌ 补 |
| 层次状态 | 三态 gate + 四态回执 | 三组回执枚举，更细 | ✅ |
| 交接提示词模板 | 3 个模板文件 + 3 个脚本 | 无 | ⚠️ 可补 |
| 跨 agent 隔离 | 每任务新 subagent，reviewer 只看 diff | 规范要求 Writer/Checker 串行隔离 | ✅ A 规范更强，执行结构弱 |
| 并发写保护 | 靠"不并行派 implementation subagent"约定 | 项目级租约（`claim`，单写者，可 `--force --reason` 记录） | ✅ A 强 |
| 同意/授权记录 | 无 | `--quote` + `quote_sha256` + `consent_replay` | ✅ A 强 |
| 交接冻结 | 无（靠 git） | `handoff` PID/端口/指纹 + `start-verify` | ✅ A 强 |
| 宿主适配 | 5 份 `references/<harness>-tools.md` | 4 个 `agents/openai.yaml` interface 字段 | ⚠️ 弱 |
| 用户侧配置 | 由各宿主安装机制携带 bootstrap | 无 | ❌ 要新建 |

## 4. 对小白用户意味着什么

1. **小白不会点名 Skill。** 他的第一句话通常是"帮我做个网站""这个页面我想改改""你帮我看看哪里有问题"。路由必须由 agent 完成。B 用 bootstrap 解决，A 目前没有解。
2. **小白最容易越的门是"好看=可以做"。** B 用 HARD-GATE 挡；A 用 `state.py` + 原话留存 + 交付回放挡，更硬。**这一层不能因为"抄 B"而放松。**
3. **小白看不懂"协作回执""租约""指纹"。** 回执是给下一个 Skill 的，不是给用户的；用户侧文件要明确"回执不念给用户听"，B 的 `site-builder` 步骤 8 已经把这条写对了。
4. **小白的项目里没有评测基础设施。** 所以用户侧文件绝不能引用 `tests/`、`F-*` 夹具、评分标准——引用了就是死链加噪音。

## 5. 建议：用户侧 AGENTS.md 写什么、怎么装

### 5.1 三层内容（只写这三层，不多不少）

**第一层：路由表。** 由 `tests/scenarios.md` 的 19 个场景投影而来，但必须是 agent 可执行的判据，不是评测文本。

| 用户这样说（示意） | 进入 | 必须停在哪 |
| --- | --- | --- |
| 想做网站/应用，说不清具体功能 | `site-builder` → `site-brief` | 方案门禁 |
| 只想把需求想清楚，先不要做 | `site-brief` | 方案确认后交接即停 |
| 参考这个网址/截图做一个 | `site-builder` → `site-brief` → `site-design` | 视觉确认 |
| 只想看设计、先看看效果、分析这张图 | `site-design` | 体验稿展示后 |
| 操作顺序/状态流转拿不准，做个能点的 | `site-design` 流程分支 | 流程确认 |
| 只要验收/检查哪里有问题 | `site-check` | 报告为止，不改源码 |
| 检查并修复 | `site-builder`（内部调 `site-check`） | 修复后重新交接复验 |
| 改文案/颜色/间距/修 bug | `site-builder` 快速分支 | 不建 `.site`，不重走流程 |
| 已交付后改核心范围（登录、多人、云数据） | `site-builder` → `site-brief`，先 `reopen` | 下游确认全部失效，重新过门禁 |

**第二层：三条不可越的红线**（写成 agent 的禁止项，不是建议）：

1. 方案未确认 → 不制作正式设计、不进入正式开发；
2. 用户只说了"好看""第二个""可以" → **不构成开发授权**，不得置 `development_authorized`；
3. 没有与当前源码指纹一致、阻断项全部 `passed` 的 `check_id` → 不得宣布交付。

再加一条反合理化清单（照 B 的 Red Flags 体例，但用 A 的话术）：

| 模型的借口 | 事实 |
| --- | --- |
| "用户说了帮我做，等于授权" | 帮做是委托梳理，不是开发授权 |
| "这只是小改动，不用走流程" | 小改动走快速分支，不是不走门禁 |
| "体验稿都做好了，顺手写正式代码" | 视觉确认与开发授权是两个决定 |
| "构建成功了，可以交付" | 命令成功只证明该命令 |
| "我读不到会话记录，没法记原话" | 只降级为 `agent-reported`，不阻塞、不编造 |

**第三层：能力降级。** 宿主不能分派子 Skill / 没有浏览器 / 不能启动服务时怎么办。这段直接投影 README 的"能力与支持矩阵"，但翻译成 agent 的动作。

### 5.2 与现有资产的关系：单一事实来源

- `skills.json` 是依赖图的机器可读版本 → **扩展 `verify_skills.py`，让它同时校验用户侧 AGENTS.md 的路由表**：覆盖全部四个 Skill、无环、无指向不存在 Skill 的条目、必含三条红线。
- `tests/scenarios.md` 是人读的评测集 → 用户侧路由表是它的**运行时投影**。建议加一个脚本比对"场景数 = 路由条目覆盖"，防止两边漂移。这是 A 目前完全缺失的一致性约束。
- 四个 `SKILL.md` 的 frontmatter `description` 保持现状即可——它是宿主级发现用的；用户侧文件补的是**决策顺序**，不是替代 description。

### 5.3 装配：随安装器写，不手改用户配置

照 B 的第二条铁律：模板由 `scripts/install.py` 落到**插件的安装目录**或用户显式指定的 agent 配置目录，**绝不**去改 `~/.claude/AGENTS.md` 这类全局文件。建议给 `install.py` 加 `--agent-config <path>`，模板里留占位符（skills 安装根、项目路径、宿主能力档位）。

### 5.4 会话启动引导：A 缺的那块

按宿主能力分三档落地（形态对应 B 的 A/B/C）：

| 宿主能力 | 做法 |
| --- | --- |
| 有 SessionStart hook / 插件生命周期 | 注入**精简 routing manifest**（路由表 + 三条红线，不是四个 `SKILL.md` 全文） |
| 只有 instructions-file | 用户侧 AGENTS.md 本身就承担引导职责，内容需自包含 |
| 两者都没有 | 在 `site-builder` 步骤 1 前加一段"先声明本轮走哪条路由"的自检，并如实标注未隔离 |

**验收测试照抄 B 的思路**，换成小白的真实口吻：干净会话发「帮我做个网站」，必须在写任何代码前先进入 `site-brief` 并停在方案门禁。

## 6. 不能直接抄的地方

1. **不要引入第五种状态文件。** ledger 只作为进度账本补充 `state.json`，不能让 Skill 直接写它——`state.py` 是唯一写入者这一条不能破。
2. **不要抄自主 ruling 哲学。** B 的 `subagent-driven-development` 写 *"Rulings, not stalls. A running plan does not wait on a human."*，只有四类情况才停（不可逆操作、安全敏感、工作树外的副作用、计划彻底崩）。这与 A 的门禁哲学直接冲突：A 要求在方案、视觉、开发授权、高风险事项上必须停。**可抄 B 的文件与账本机制，不可抄它的自主度。**
3. **不要并存两套记录。** B 自动产出 `docs/superpowers/specs/YYYY-MM-DD-*.md`，A 用 `.site/brief.md`。用户侧文件里不要出现 B 的路径约定。
4. **不要把 bootstrap 写成恐吓语气给用户看。** B 的 `EXTREMELY-IMPORTANT`/"YOU MUST"是给模型的行为约束，但对小白用户，"你必须"出现在自己的配置文件里会引起误解。用户侧文件应当是 agent 指令清晰、对人类读者也体面。
5. **不要用 description 承载路由。** B 的 description 只做发现，路由靠 `REQUIRED SUB-SKILL` + bootstrap。A 若把路由塞进 description 会超长且宿主截断行为不可控。

## 7. 建议的落地顺序

| 阶段 | 交付物 | 验收 |
| --- | --- | --- |
| P0 | 用户侧 AGENTS.md 模板（路由表 + 三红线 + 反合理化表 + 能力降级） | 人工核对 19 个场景全覆盖；不含 `tests/`、`F-*`、评分标准等开发侧内容 |
| P1 | `install.py --agent-config` 装配；`verify_skills.py` 增加路由表校验 | `python scripts/verify_skills.py .` 通过；故意删一条路由 → 校验失败 |
| P2 | 会话启动引导（按宿主分档） | 干净会话「帮我做个网站」→ 先 `site-brief` 且停在方案门禁；附 transcript |
| P3 | progress ledger（`.site/progress.md`，首行写项目身份） | 长任务上下文压缩后不重做已完成切片 |

P0/P1 不动任何现有 `SKILL.md`，风险最低，收益（触发可靠性）最大。

## 附：核对记录

- B 的取回方式：`https://api.github.com/repos/obra/superpowers/tarball/main`（`github.com` 网页与 `git clone` 受网络策略限制，raw/API 可达）。
- B 版本：`package.json` `version: 6.3.0`；提交 `b36e0829c6d0140e93cfef2ca599b1b07d4a7797`。
- B 侧引用文件：`skills/using-superpowers/SKILL.md`、`skills/brainstorming/SKILL.md`、`skills/writing-plans/SKILL.md`、`skills/executing-plans/SKILL.md`、`skills/verification-before-completion/SKILL.md`、`skills/subagent-driven-development/SKILL.md`（含 `scripts/task-brief`、`scripts/review-package`、`scripts/sdd-workspace`）、`skills/dispatching-parallel-agents/SKILL.md`、`docs/porting-to-a-new-harness.md`、`hooks/session-start`、`hooks/hooks.json`、`GEMINI.md`、`CLAUDE.md`/`AGENTS.md`、`RELEASE-NOTES.md`（指令优先级层级）。
- A 侧核对命令：`cat skills.json`、四个 `site-*/SKILL.md`、`site-brief/references/state.md`、`scripts/verify_skills.py`（`load_dependencies` / `check_dependencies` / frontmatter 校验）、`scripts/install.py`、`tests/scenarios.md`、`README.md`、`REQUIREMENTS.md`；`grep -rln "SessionStart|bootstrap|EXTREMELY_IMPORTANT"` 在 `tests/runs/` 外**无命中**，确认 A 无会话启动引导等价物。
- 未取到/未验证：B 的 `tests/` 在 tarball 中与 jsDelivr 文件清单不一致（`tests/skill-triggering/` 不存在于该快照），因此本文只引用 `docs/porting-to-a-new-harness.md` 中记录的触发器验收测试，未声称实际运行过 B 的测试套件。
