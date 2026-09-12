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

## 关键约束

- 先确认首个可验证版本，再为新建或重大变化制作低成本可见实验；
- 结构选择、视觉选择与开发授权是三个决定：用户选了页面结构不等于确认了视觉风格；
- 完整愿景保留方向，本轮按可独立体验的纵向切片实施；
- 状态跃迁只走 `site-brief` 的门禁脚本：确认记录必须带用户那句原话（`--quote`），同一句不能连过两道门禁；
- **门禁记录的是声明，不是同意的证明。** 任何本地脚本都挡不住 Agent 自己写一句"用户同意了"；工具保证的是原话逐字留存、修订号递增、事后可比对。真正验证同意的是交付时把原话回放给用户本人核对（`consent_replay`），以及首轮就先提问的对话结构；
- `site-check` 独立给出带 `check_id` 的矩阵凭据；阻断项必须有截图、结果文件或命令凭据等可核验证据，交付时重新核对哈希，手写矩阵或改动过的证据都会被拒绝；
- 简单修改和 Bug 按影响跳过无关阶段；
- 系统级安装、费用、账号、密钥、真实敏感数据和公开部署按宿主能力分档拦截，不由状态机记录。

## 能力与支持矩阵

诚实的能力边界，避免把"能记录"读成"能验证"：

| 能力 | 有宿主支持时 | 无宿主支持时 |
| --- | --- | --- |
| 用户原话留存 | 始终可用 | 始终可用（`--quote` 必填） |
| 标注升级为 `quote-matched` | 会话记录可读且能定位到用户消息 | 降级为 `agent-reported`，**不阻塞**；未知格式只降级 |
| 用户同意的验证 | **任何宿主都不提供** | 靠交付时回放原话 + 用户本人核对 |
| 不可逆动作拦截 | T1 审批提示 / T2 沙箱边界 | T3 停下来问并等回答，且如实标注 |

**没有任何一档能证明用户同意。** 各道确认门禁在所有宿主上都可执行，因为它们的输入是 Agent 抄录的原话，而不是宿主内部文件；因此不存在"环境不支持导致流程停摆"的分支。

详细需求见 [`REQUIREMENTS.md`](REQUIREMENTS.md)，统一术语见 [`CONTEXT.md`](CONTEXT.md)。

## 维护检查

```text
python scripts/verify_skills.py .
python tests/gate_flow.py
```

`verify_skills.py` 检查四个 Skill 的 frontmatter、协作依赖、相对链接、manifest 文件及哈希，并拒绝未列入包的残留文件。`gate_flow.py` 回放门禁事务：无依据跃迁、空的原话、`--anchor` 读不懂时的降级、按内容比对的原话复用（结构那句用不成视觉那句）、声明了多结构却想直接记视觉确认时的拒绝、只有结构没有风格时的拦截、交付前重新核对四道确认门禁、空项目不能借 reopen 拿到 building、以及 block/重新授权绕过阶段守卫、并发租约、Writer 未退出的交接、无证据或证据被改动的阻断项、阻断失败与源码变化后的交付，以及交付回放每条原话。**它不测、也无法测"用户是否真的同意"**——那条只能由交付回放交给用户本人判断。协作行为回放见 [`tests/scenarios.md`](tests/scenarios.md)，面向非技术用户的端到端画像、用例与评分标准见 [`tests/novice-user-evaluation.md`](tests/novice-user-evaluation.md)。
