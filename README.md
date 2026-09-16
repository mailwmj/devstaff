# 渐进式建站 Skills

一套面向非技术中文用户、作为整体安装和协作运行的 Coding Agent Skills。用户只需用自然语言描述想法、参考、现有项目或修改目标，不需要记住 Skill 名称和开发阶段。

## 协作结构

```text
site-builder（默认入口、全部正式修改和实施）
├── site-brief（调查、首版收敛及协作记录）
├── site-design（视觉/流程体验稿与只读视觉审查）
│   └── site-brief（补齐背景、记录确认结果）
└── site-check（静态、业务、视觉与再次打开验证）
    └── site-design（只读视觉审查，不重新访谈）
```

四个 Skill 应一起安装。`site-builder` 在完整建设、修改和修复请求中自动协调其余 Skill；用户明确只要需求梳理、体验稿或验收时，可由 Agent 直接选择对应 Skill。`site-brief` 集中写入 `.site/brief.md` 与 `.site/state.json`，避免多个 Skill 用旧状态覆盖彼此。

`skills.json` 只描述一个 Skill 可能调用的静态能力依赖；子 Skill 把协作回执返回原调用者不构成反向依赖。builder 根据 check 结果修复再复验属于有界工作流，连续两轮无新证据或进展即停止并标记 `blocked`。

## 整套安装

用户侧安装交付**两个东西**，缺一不可：

1. **四个 Skill 目录**——`site-builder`、`site-brief`、`site-design`、`site-check` 必须一起复制，不能只装其中几个。`site-brief` 里放着全部协作状态的门禁脚本 `scripts/state.py`，漏装它整套都会失效；
2. **一份指令文件**——[`templates/AGENTS.md`](templates/AGENTS.md)。四个 `description` 只提供"被发现"的机会，路由和停位规则靠这份文件"被遵守"；不装它，用户第一句"帮我做个网站"就可能被直接读成"开干"。

按宿主分别放置：

| 宿主 | Skill 目录 | 指令文件 |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/`（或项目内 `.claude/skills/`） | `~/.claude/CLAUDE.md` 里**追加一行** `@<绝对路径>/AGENTS.md`；Claude Code 明确不读 `AGENTS.md` |
| Codex | `~/.agents/skills/`（或仓库根 `.agents/skills/`） | `~/.codex/AGENTS.md`（`AGENTS.override.md` 优先）；正文直接放这里 |

写指令文件时**幂等追加，绝不覆盖**用户已有配置：用带标记的块包裹内容；已有标记就只替换标记内内容（可重复安装、可升级）；无标记且文件已存在就追加到末尾；文件不存在才创建。Claude Code 侧只追加那一行 import，**不要**把正文粘进 `CLAUDE.md`——正文留在本仓库的模板里，升级时只动这一份。逐宿主的差异、体积上限与三层验收方法见 [`templates/hosts/README.md`](templates/hosts/README.md)。

## 维护者工具

`scripts/install.py` 是**开发侧**的装配校验器，**不是用户安装方法**：它只处理上面第 1 项，从不落地 `AGENTS.md`，所以它单独跑完不等于装好了。仓库维护者在自己机器上校验这套 Skill 能否原子装配时使用：

```text
python scripts/install.py /absolute/path/to/agent/skills
```

更新整套时使用 `--replace`；脚本先在临时目录复制并校验四个 manifest，成功后才整体替换，拒绝只覆盖其中一个 Skill。
正式用户仍按上表手动复制 Skill 并幂等追加指令文件；本项目不会自动写入用户的全局 Agent 配置。

## 关键约束

- 先确认首个可验证版本，再为新建或重大变化制作低成本可见实验；
- 结构选择、视觉选择与开发授权是三个决定：用户选了页面结构不等于确认了视觉风格；
- 开发授权按完整请求与相邻问答的行动含义判断，不按关键词：直接要求建设正式成果的委托可在前置决定确认后继续生效；没有既有委托时，Agent 先说清“确认后进入开发”的后果，再理解用户紧接着的自然答复。当前答复不得倒填旧门禁，也不要求用户背“开始开发”口令；
- 结构候选前先按任务形成轻量交互合同：`required / recommended / confirm / excluded` 约束对象生命周期、工作区、完整 Flow、本地化和范围；行业经验只能提出建议或待确认项，不能创造首版功能；
- `site-design` 的目标是产出**高质量视觉方案**：先从活跃代码、现有产品、品牌与真实素材提取上下文；默认给一个有依据的页面结构和两个母题层不同的风格，只有新的重要取舍才增加候选；推荐要有依据但不能替用户确认；
- `site-design` 内置经项目化改写的 `web-design-direction`、Impeccable 工艺规则、ClawHive 前端设计原则，以及 UI/UX Pro Max `2.13.0` 的 MIT 检索器和数据。统一通过 `scripts/design.py research` 调用，不依赖仓库根的参考资料或用户额外安装；
- `.site/design/surface-brief.md` 是设计、建设和验收共用的一份页面设计合同：视觉确认后补全页面地图、区块、Token、响应式、组件状态、文案、素材和可观察验收标准，`site-builder` 与 `site-check` 都按同一组 ID 工作，不再各自猜测或复制规格；
- 完整愿景保留方向，本轮按可独立体验的纵向切片实施；
- 状态跃迁只走 `site-brief` 的门禁脚本：确认记录必须原样保留用户那句原话（`--quote`），规范化摘要只用于识别空白差异下的重复，同一句不能连过两道门禁；每次写状态都追加紧凑的前后摘要与可用的租约 owner；
- **门禁记录的是声明，不是同意的证明。** 任何本地脚本都挡不住 Agent 自己写一句"用户同意了"；工具保证的是原话逐字留存、修订号递增、事后可比对。真正验证同意的是交付时把原话回放给用户本人核对（`consent_replay`），以及首轮就先提问的对话结构；
- `site-check` 独立给出内容寻址的 `check_id` 矩阵凭据；每个档位必须说明 `profile_reason`，`full` 必须覆盖静态/构建、核心任务、桌面视觉、手机视觉与再次打开五个阻断轴，`smoke` / `targeted` 也不得省略受影响核心任务；阻断项必须有截图、结果文件或命令凭据等可核验证据，交付时重新核对摘要与证据哈希；
- 内容摘要、租约和状态历史用于防漏步骤、误覆盖和状态漂移，属于**可发现误改的工作流记录**，不是防御拥有本地写权限的恶意 Agent 的安全边界；语义、产品、视觉和“证据是否真的支持结论”仍由模型、Checker 与用户判断；
- 简单修改和 Bug 按影响跳过无关阶段；
- 系统级安装、费用、账号、密钥、真实敏感数据和公开部署按宿主能力分档拦截，不由状态机记录。

## 能力与支持矩阵

诚实的能力边界，避免把"能记录"读成"能验证"：

| 能力 | 有宿主支持时 | 无宿主支持时 |
| --- | --- | --- |
| 用户原话留存 | 始终可用 | 始终可用（`--quote` 必填） |
| 标注升级为 `quote-matched` | 会话记录可读且能定位到用户消息 | 降级为 `agent-reported`，**不阻塞**；未知格式只降级 |
| 用户同意的验证 | **任何宿主都不提供** | 靠交付时回放原话 + 用户本人核对 |
| artifact 误改发现 | 内容寻址 `check_id`、文件名/内部 ID/摘要复核 | 同样可用；不防拥有写权限者重新伪造整套记录 |
| 不可逆动作拦截 | T1 审批提示 / T2 沙箱边界 | T3 停下来问并等回答，且如实标注 |

**没有任何一档能证明用户同意。** 各道确认门禁在所有宿主上都可执行，因为它们的输入是 Agent 抄录的原话，而不是宿主内部文件；因此不存在"环境不支持导致流程停摆"的分支。

详细需求见 [`REQUIREMENTS.md`](REQUIREMENTS.md)，统一术语见 [`CONTEXT.md`](CONTEXT.md)。

## 维护检查

```text
python scripts/verify_skills.py .
python tests/gate_flow.py
python site-design/scripts/design.py validate
python site-design/scripts/design.py research "productivity tool novice calm" --design-system --project-name "Example"
```

`verify_skills.py` 检查四个 Skill 的 frontmatter、协作依赖、相对链接、manifest 文件及哈希，并拒绝未列入包的残留文件。`gate_flow.py` 回放门禁事务：逐字原话与规范化防复用、结构/风格分离、owner 绑定租约、Checker 凭失败矩阵交回 Writer、项目内普通原型文件、包含 `.site/design` 的冻结指纹、正式服务 PID/端口/根目录、内容寻址 artifact、检查档位最低轴、阻断证据与交付回放。**它不测、也无法测"用户是否真的同意"或"证据在语义上是否充分"**，这些判断仍交给用户与独立 Checker。`design.py validate` 同时检查本地 Token/Gallery 和内置 UI/UX Pro Max 数据完整性；`design.py research` 是唯一检索入口，并固定返回带来源与版本的 JSON。GitHub Actions 还会在干净 `git archive` 副本中把整套 Skill 安装到临时目录，验证发布包不依赖工作区残留。协作行为回放见 [`tests/scenarios.md`](tests/scenarios.md)，面向非技术用户的端到端画像、用例与评分标准见 [`tests/novice-user-evaluation.md`](tests/novice-user-evaluation.md)，视觉工艺评测见 [`tests/site-design-scenarios.md`](tests/site-design-scenarios.md)。

**这些脚本都不能证明视觉质量。** 色对、字号与配方检查守的是目录默认值，不是渲染后的页面；工艺是否成立只能由评测者在实际渲染上按 [`site-design/references/craft-review.md`](site-design/references/craft-review.md) 的设计、任务状态与机械三路证据核对。
