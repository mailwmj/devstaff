# 宿主编配清单

目标宿主：**Claude Code** 与 **Codex**。本目录记录"把 `templates/AGENTS.md` 与四个 Skill 交付到这两个宿主"所需的全部事实。

**结论先说**：两个宿主**可以共用同一份 `AGENTS.md`**——Codex 原生读它，Claude Code 通过 `CLAUDE.md` 里一行 `@AGENTS.md` 读它。因此 `templates/AGENTS.md` 不需要改写，只需为 Claude Code 补一个两行的 `CLAUDE.md`。

## 1. 两家差异（均为官方文档核实，非推测）

| 维度 | Claude Code | Codex |
| --- | --- | --- |
| 指令文件名 | **`CLAUDE.md`——明确不读 `AGENTS.md`** | **`AGENTS.md`** |
| 全局位置 | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.override.md` 优先，否则 `~/.codex/AGENTS.md`；**该层只取第一个非空文件** |
| 项目位置 | `./CLAUDE.md` 或 `./.claude/CLAUDE.md`（另有 `CLAUDE.local.md`） | 项目根→cwd 逐级：`AGENTS.override.md` → `AGENTS.md` → `project_doc_fallback_filenames`；**每目录最多一个** |
| 合并语义 | 全层级**拼接**（不覆盖）；从文件系统根到 cwd 排序 | 从根到 cwd 拼接；靠近 cwd 的**覆盖**更早的 |
| 体积约束 | 建议**每文件 < 200 行**，越长遵守度越低 | `project_doc_max_bytes` **默认 32 KiB**；超限**静默截断** |
| import 语法 | `@path` **展开**（相对引用它的那个文件；最多 4 跳；跳过代码行内/围栏代码块） | **无 import**；改用 `project_doc_fallback_filenames` 或嵌套目录 |
| skill 目录 | 个人 `~/.claude/skills/<name>/SKILL.md`；项目 `.claude/skills/<name>/SKILL.md` | 用户 `~/.agents/skills/`；仓库根 `<repo>/.agents/skills`；`$CWD/.agents/skills` |
| skill frontmatter | `name`、`description`、`when_to_use`、`allowed-tools`、`disallowed-tools`；description+when_to_use **在 1,536 字符处截断** | `name`、`description` **必填**；`agents/openai.yaml` 可选（外观、调用策略、工具依赖） |
| 其他 | 块级 HTML 注释 `<!-- -->` **注入前被剥离**；`/context` 可查看已加载的 Memory files | `AGENTS.override.md` 可临时覆盖而不删base |

### 对项目的直接结论

1. **本仓库已有的 `agents/openai.yaml` 正是 Codex 的 skill 约定**（官方文档列为"Optional: appearance and dependencies"）。所以四个 Skill 在 Codex 侧已经具备元数据，不需要新增。
2. **`templates/AGENTS.md` 的 101 行 / 8.9 KB 同时满足两家**：Claude Code 的"<200 行"建议、Codex 的 32 KiB 默认上限（约占 27%）。以文件实际行数与字节数为准。
3. **但 32 KiB 是 global + project 合并计算的**。若全局装了本文件，项目里还有别的 `AGENTS.md`，要留意累计。必要时用 `project_doc_max_bytes` 提高，或把非核心章节拆到嵌套目录。

## 2. 交付形态

```text
<目标位置>/
├── AGENTS.md          ← templates/AGENTS.md 原文（Codex 直接读；Claude Code 经 import 读）
├── CLAUDE.md          ← 两行：@AGENTS.md（仅 Claude Code 需要）
└── skills/
    ├── site-builder/
    ├── site-brief/
    ├── site-design/
    └── site-check/
```

`CLAUDE.md` 的全部内容：

```markdown
@AGENTS.md
```

Windows 上不要用 symlink 代替（需要管理员权限或开发者模式），用 import。

## 3. 安装位置：三个 scope 的取舍

这是本方案唯一需要拍板的地方，存在真实张力：

| scope | 位置 | 优点 | 代价 |
| --- | --- | --- | --- |
| **全局** | Codex `~/.codex/AGENTS.md`；Claude Code `~/.claude/CLAUDE.md` | 用户**第一次**说"帮我做个网站"时规则就在场 | **本机两家都已存在**（1,262 / 1,364 字节）——直接写会**覆盖用户已有配置** |
| **项目** | 项目根 `AGENTS.md` + `CLAUDE.md` | 安全、作用域正确、不动用户任何现有文件 | 用户第一次开口时项目里还没有这个文件——**正是最需要它的时刻** |
| **skill 目录内的 `SKILL.md` description** | 跟随 skill 安装 | 零额外文件 | 只提供"被发现"的机会，不保证"被遵守"（§5 另行讨论） |

**推荐：全局 + 幂等追加，绝不覆盖。** 做法：

1. 用带标记的块包裹本文件内容，写入前先检测标记：
   - 已有标记 → 替换标记内内容（可重复安装、可升级）；
   - 无标记且文件已存在 → **追加**到文件末尾，不删除任何原有内容；
   - 文件不存在 → 直接创建。
2. Claude Code 侧不要粘贴正文，只追加一行 `@<绝对路径>/AGENTS.md`——正文留在我们自己的文件里，用户升级时只动我们的文件。
3. 标记用 HTML 注释：Claude Code **注入前会剥离块级 HTML 注释**，所以标记不消耗 token，只用于文件级幂等。

**降级路径**：用户明确不想动全局配置时，只装项目级，并在交付话术里如实说明"新建项目时需要再跑一次安装"。

## 4. 每宿主适配记录（四块，必须填全）

`templates/AGENTS.md` 第六节（能力降级）是**策略**，这里逐宿主填**执行**，两者必须一一对应。

### Claude Code

| 能力项 | 实情 |
| --- | --- |
| 调用其他 Skill | 可用：`Skill` 工具按名加载；个人/项目/插件 skill 都可被模型自动调用 |
| 派独立 Agent | 可用（subagent），Writer/Checker 可真正隔离 |
| 浏览器实测 | 取决于该会话是否装了浏览器类 skill/工具；缺则 `not_run` |
| 读会话记录（`--anchor`） | 取决于宿主 transcript 格式；能读则升 `quote-matched`，读不到降级 `agent-reported`，**不阻塞** |
| 指令文件 | `CLAUDE.md`（+`@AGENTS.md` import）；`/context` 可核验是否加载 |

### Codex

| 能力项 | 实情 |
| --- | --- |
| 调用其他 Skill | 可用：从 `.agents/skills` 发现，模型选中后读完整 `SKILL.md` |
| 派独立 Agent | 可用 |
| 浏览器实测 | 同上，缺则 `not_run` |
| 读会话记录（`--anchor`） | 同上，降级不阻塞 |
| 指令文件 | `AGENTS.md`；`~/.codex/AGENTS.override.md` 可临时覆盖 |

## 5. 触发可靠性的第二个杠杆（建议，未实施）

取证时发现一个**直接改善触发问题**的机制，成本很低：

- Claude Code 的 skill frontmatter 支持 **`when_to_use`**——"触发短语或示例请求"；
- 官方明确要"把关键用例放前面"，因为 description + when_to_use **在 1,536 字符处截断**；
- 本项目四个 `description` 当前只有 103–120 字符，**离上限很远**，有充足余量；
- `verify_skills.py` 只校验 `name` 与 `description`，**允许额外 frontmatter 字段**，加上不会破坏打包校验。

**建议**：给四个 `SKILL.md` 各加一段 `when_to_use`，用小白的真实口吻写触发短语（"帮我做个网站""这页我想改改""你帮我看看哪儿有问题""先给我看看效果"），把 `templates/AGENTS.md` 的 §二/§三判据投射进去。

价值：让"被发现"这一层从"靠 description 语义匹配"升级为"匹配用户的原话"，而**不需要 hook、不需要额外文件**——正好符合本轮的约束。

**代价与风险**：要改 skill 目录 → 必须同步 `manifest.json` 哈希并升版本（`verify_skills.py` 强制）；Codex 是否识别 `when_to_use` **未验证**（未知字段通常被忽略，但需实测）。

## 6. 验收：三层，全绿才算通过

用小白口吻的一句话验收：**干净会话发「帮我做个网站」。**

| 层 | 判据 | 按宿主的具体核验方式 |
| --- | --- | --- |
| **L1 注入** | 问会话"你的路由规则里'验收'分几种情况"，能答出按运行态分两种 | Claude Code：`/context` 的 Memory files 里有 `CLAUDE.md`；Codex：问它"启动时读了哪些 AGENTS.md"（官方示例就是这个问法） |
| **L2 技能可见** | 四个 `site-*` 出现在 skill 目录 | Claude Code：`/site-builder` 能补全；Codex：skill 列表含四个 |
| **L3 行为** | 写任何代码前进入 `site-brief`，停在方案门禁 | 三个信号：① 未创建正式源码；② 出现方案/范围/核心任务的回放与提问；③ 未越过方案门禁去 `site-design` 或初始化工程 |

**L1/L2 通过而 L3 失败最值得盯**——内容在了但没被遵守，属"模型合理化"，靠 `templates/AGENTS.md` 第五节那张反合理化表压制；若仍失败，考虑把路由表从"建议语气"改成更硬的禁止项（该文件的"不得"已经很硬，届时优先检查是不是被截断了）。

## 7. 待实测（不要当成已知）

1. **Claude Code 当前版本是否真的不读 `AGENTS.md`**——官方文档明说"reads CLAUDE.md, not AGENTS.md"，但仍在演进（已有 `/import` 与 `CLAUDE_CODE_NEW_INIT` 会读 AGENTS.md）。**用 `/context` 实测**，不要只信文档。
2. **Codex 是否识别 `when_to_use`**——未知。
3. **两家同时生效时的重复 token 量**——按文档是不同机制、不冲突，但内容重叠需要实测后再决定是否裁剪其一。
4. **全局 + 项目同名指令叠加后的实际遵守度**——两家的合并语义不同（拼接 vs 覆盖），要分别验。
