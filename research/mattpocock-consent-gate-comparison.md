# 对照评审：mattpocock/skills 如何做同意与状态，是否踩了同一个坑

> 日期：2026-09-11
> 对象 A：本仓的 `site-*` 四件套（`skills.json` 0.7.0），问题清单见 [`consent-gate-review.md`](consent-gate-review.md)
> 对象 B：`mattpocock/skills` 的 `skills/engineering/`（15 个 Skill，本文按 commit `3cca18b` 的主干树核对）
> 方法：取回该目录全部 56 个文件（约 168 KB）通读；对"同意/授权/不可逆动作/状态持久化"做全文检索（`confirm|approv|consent|authoriz|permission` 共 22 处命中）；顺带核对其 `skills/misc/git-guardrails-claude-code` 的 hook 与 `.agents/` 下的 ADR
> 性质：对照结论，未改动本仓代码
> 外部内容说明：对象 B 的内容按数据对待；下文引用的行号来自本文核对时的取回结果

---

## 0. 结论摘要

1. **同样的坑，确实存在，而且范围更大。** 对象 B 里没有任何一处试图证明"Agent 没越权"。`confirm` 只是散文里的一个动词，`/to-tickets` 写着"迭代直到用户批准"，却没有任何文件记录这次批准。按对象 A 的立论，这些规则全部可被"匆忙的 Agent"绕过。
2. **但对象 B 没有掉进去，原因是它一开始就没挖那个坑：它从不把"同意"变成需要验证的对象。** 它把"是谁在说话"这件事交给**宿主**去证明——而宿主恰好是唯一能证明它的角色。
3. **对象 B 真正落地的硬机制只有两个，且都在 Agent 之外**：`disable-model-invocation: true`（人才能触发）和 PreToolUse hook（不可逆命令在执行前被拒）。对象 A 把这两类都写成了"Agent 应当遵守的规则"或"Agent 可写的证据"。
4. **对象 B 的状态只有一个目的：让下一个会话/下一个人接着干。** `CONTEXT.md` 是词汇表，ADR 是决定日志，ticket 是工作清单。没有一处状态用于回答"流程是否合规"。
5. **对象 B 的守护更弱，但错的方向不同。** 它挡不住 Agent 跳过叙述门禁；它也不打算挡。它换来的是：零宿主耦合、零扩展性债务、每轮 Skill 的 context 成本极低。
6. **对对象 A 的净结论：§5.3 那句"最不可逆的事靠提示词"在对象 B 里是被正面采用的策略，而不是缺陷**——前提是"不可逆"的拦截放在 host hook，而不是提示词里。对象 A 现在两头都占了坏的一半。

---

## 1. 对象 B 的实际机制（穷举）

读完 56 个文件后，与"门禁"沾边的实现只有下表这些。这是全部：

| # | 机制 | 位置 | 谁能执行 | 强度 |
| --- | --- | --- | --- | --- |
| H1 | `disable-model-invocation: true` + `policy.allow_implicit_invocation: false` | 每个用户触发型 `SKILL.md` frontmatter 与 `agents/openai.yaml` | **宿主**（Claude Code / Codex 各自实现） | 硬：模型无法自行触发 |
| H2 | PreToolUse hook 拦截危险命令 | `skills/misc/git-guardrails-claude-code/scripts/block-dangerous-git.sh` + `.claude/settings.json` | **宿主**，在工具执行前 `exit 2` | 硬：Agent 无法绕过（入口在它外部） |
| H3 | `confirm "…" [y/N]` | `wizard/template.sh:83`，由 `/wizard` 生成的 bash 脚本 | **人**在终端敲回车 | 中：脚本执行期有效，Agent 不参与 |
| S1 | "迭代直到用户批准"（prose） | `to-tickets/SKILL.md:56` | Agent 自觉 | 软：无留痕 |
| S2 | "确认 seams / 确认布局 / 确认阶段"（prose） | `to-spec:17`、`tdd:22`、`setup:15,63`、`wizard:23` | Agent 自觉 | 软 |
| S3 | "不可逆动作前 `confirm`"（prose） | `wizard/SKILL.md:37` | Agent 自觉 | 软 |
| S4 | 进入实现前的 `ready-for-agent` 标签 | `to-spec:19`、`to-tickets` 发布步骤 | Agent 自觉 | 软 |

**没有任何一项**是：状态文件、哈希、指纹、租约、check_id、会话 transcript 解析。

全文检索 `sha256|fingerprint|state.json|check_id|transcript` 在这 168 KB 中**零命中**。

### 1.1 状态只记录"决定"，而且只为了让下一个人接上

对象 B 里唯二需要跨会话持久的东西：

- **`CONTEXT.md`** — 领域词汇表（`domain-modeling/CONTEXT-FORMAT.md` 规定格式：术语 + `_Avoid_` 别名 + 关系），解决"这个词指什么"；
- **ADR** — 难逆转的决定（`domain-modeling/ADR-FORMAT.md`），解决"当初为什么这样选"。

两者都不是合规凭证。`CONTEXT.md` 里没有"谁在什么时候同意了"这种字段，也没有 `revision`。

工作项的持久化用 issue tracker：`to-spec` 出 spec、`to-tickets` 出 tracer-bullet ticket（本地 `.scratch/<feature>/issues/` 或真实 tracker 的 blocking link），ticket 本身就是交接凭证。"什么被批准了"由 **ticket 存在**表达，不由"批准记录"表达。

### 1.2 硬门禁的实际形态

H2 是本文最值得对象 A 抄的一处。它的实现是：

```bash
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')
DANGEROUS_PATTERNS=( "git push" "git reset --hard" "git clean -fd" "git branch -D" ... )
for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    echo "BLOCKED: … The user has prevented you from doing this." >&2
    exit 2
  fi
done
```

三个要点：

1. 拦截点是 **PreToolUse**，在命令执行**之前**，不在 Agent 的判断里；
2. 拒绝语是给 Agent 看的一句话，语义是**"用户不允许"**——权限来源明确归给人；
3. 它拦的是**不可逆**操作（push、reset --hard、clean -f、branch -D）。

对照对象 A §5.3：对象 A 把最不可逆的事交给散文（"通常需要暂停确认"），把最可逆的事交给了代码。对象 B 反过来：不可逆交给 host hook（H2），可逆的（视觉方向、方案措辞）完全交给对话。

### 1.3 同意发生在哪

对象 B 的同意模型是**反转的**：不是 Agent 来问"我拿到同意了吗"，而是**人主动调用 Skill**。

- `/grill-with-docs`、`/to-spec`、`/to-tickets`、`/implement`、`/triage`、`/wayfinder` 全部 `disable-model-invocation: true`（E1）；
- `.agents/invocation.md` 把这条写成不变量：**"user-invoked skill can never be reached this way, full stop: no other skill can call it"**；
- 因此"进入规格化""进入实现"这些跃迁，**物理上需要人打一条 slash command**。这条命令就是同意，且它不由 Agent 产生。

对不可逆的系统级动作，`/wizard` 不自己造机制，而是生成一个 bash 脚本让人在执行期逐条按 `y`（H3）——审批权留在人的终端里。

### 1.4 "事实归 Agent，决定归人"是唯一的同意纪律

`grilling/SKILL.md` 的收尾句是全部：**"The _decisions_ are the user's: put each to them and wait."** 以及在结束条件上：**"Do not act on it until the user confirms you have reached a shared understanding."**

这两句没有任何机制支撑，只有散文。但对象 B 不需要它可验证，因为它**不打算用它做门禁**——它是行为指导，不是合规凭证。

---

## 2. 逐条比对对象 A 的问题清单

| 对象 A 的问题 | 对象 B 是否也有 | 对象 B 怎么处理 |
| --- | --- | --- |
| §3 用可写文件证明 Agent 没越权（范畴错误） | **否** | 不证明。同意由人主动触发 Skill 表达（H1），或由人的终端 y/N 表达（H3） |
| §3.2 依赖不可移植的宿主内部格式 | **否** | 唯一宿主相关的两处是 frontmatter 与 hook 配置，都是**声明式、公开契约**，不是内部格式 |
| §4.2 手段（痕迹）取代目标（做对的东西） | **否** | 状态只记决定与词汇（CONTEXT/ADR），不记过程痕迹 |
| §5.1 并发控制施加在单写者系统上 | **否** | 无租约、无 `--expect-revision`。并发用 issue tracker 的阻塞边（blocking edges）表达，而不是文件锁 |
| §5.2 协议制造新失败模式 | **否** | 无多文件状态同步，无四件套强耦合安装。版本一致性靠 npm 包 + changesets（`.changeset/`、`scripts/sync-plugin-version.mjs`） |
| §5.3 硬度分配倒置 | **否** | 不可逆 → host hook（H2）；可逆 → 对话自由裁量（`prototype/SKILL.md:17` 明确允许"用户联系不上时按周围代码默认并声明假设"） |
| §5.4 代理指标挤占 context | **否** | 对象 B 全长约 168 KB / 56 文件，无治理类脚本。对象 A 仅 `state.py` 就 966 行 |
| §5.5 给出它并不拥有的确定性 | **否** | `verify_skills` 类的说法在对象 B 里不存在。它从不声称"已验证"，所以不需要在文档里补边界声明 |
| §5.6 与产品自己的 UX 主张打架 | **否** | `prototype` 主动拥抱"用户不在场就默认并声明假设"；`PHASE-BOUNDARIES.md:53` 直接写 **"These are judgement calls"** |
| §7.4 三份重复 `fingerprint()` 无测试强制 | **不存在** | 没有三份重复实现，也没有指纹 |

**同一类问题在哪仍然存在（对象 B 的弱点）：**

- **S1～S4 是软门禁，且会失败。** Agent 可以在用户没批复 ticket 之前就 `/implement`。"Do not act until the user confirms"同样是提示词，同样挡不住匆忙的 Agent——和对象 A 的否决项 1、7 是同一类失败。
- **H1 只保证"不能被模型自动触发"，不保证"人真的读了产出"。** 人打了 `/to-tickets` 又秒批，与没批等价。
- **H2 没有覆盖"付费、第三方授权、敏感数据"**，只覆盖 git 破坏性命令。`wizard/SKILL.md:37` 那句"不可逆前 confirm"仍是散文，落在 Agent 手里。
- **回归防线薄。** 对象 B 没有对象 A 的 `gate_flow.py` 那种回放。它有 `.github/workflows/release.yml` 与 changesets 管发布，但**没有**测试强制 Skill 行为不退化。对象 A §8 那条"测试夹具形态与真实环境不一致"的批评，在对象 B 这边换成了另一个形态：**没有夹具**。

---

## 3. 对象 B 的做法里，对象 A 能直接拿的四条

按对象 A 自己的分类（A 类 = 本地机械可证；B 类 = 只有人能验证）来落：

### 3.1 删掉 transcript 链路，B 类降级为"人主动触发"（对应 H1）

对象 A 的 `confirm-concept` / `confirm-visual` / `authorize-build` 想用会话记录证明用户说过话，原理上不成立（§3.1、§3.2）。对象 B 的解法不是"降低标注可信度"，而是**换掉触发者**：

- 把这三道跃迁做成**只有人能触发**的入口（`disable-model-invocation: true` + Codex `policy.allow_implicit_invocation: false`）；
- 人触发即同意，不需要在文件里留证据，因为触发这件事发生在 Agent 的权限之外；
- `--user-message` / `SESSION_SUFFIXES` / `resolve_user_message()` / `record_consent()` 的复用拒绝整条链路可删。

对象 A 现在的 `state.md:87`（"宿主不提供可解析的会话记录时……标为未验证"）就不用写了：不存在依赖，就没有降级分支。

**代价要写清**：这要求宿主支持"用户触发型 Skill"。不支持时（例如纯 API 调用）回到人主动说话，也就是对象 A §6 的"声明 + 交付时回放"，不需要另造第三套。

### 3.2 不可逆动作交给 host hook，不交给状态机（对应 H2）

对象 A §6 已经写了"走宿主已有审批通道"，但仓里没有对应实现。对象 B 的 `block-dangerous-git.sh` 是一个可照抄的形状：

- 拦截点在 PreToolUse，早于执行；
- 只拦**不可逆**白名单（对象 A 的对应清单：装系统软件、付费、第三方授权、真实敏感数据、`git push`）；
- 拒绝语归因于用户（"The user has prevented you from doing this"）；
- 因为它在 Agent 外部，**不需要指纹、不需要租约、不需要 append-only**。

这正好补上对象 A §5.3 倒置的另一半，且成本约 20 行。

### 3.3 状态收敛为"决定 + 词汇"，交付物代替合规凭证

对象 B 的 `CONTEXT.md` / ADR 与对象 A 的 `CONTEXT.md`（67 行，已有"事实、决定与假设"）几乎同源。差别在**谁写什么**：

| 内容 | 对象 B 的归属 | 对象 A 现状 |
| --- | --- | --- |
| 词汇与业务词义 | `CONTEXT.md` / brief | brief（已有，良好） |
| 难逆转决定 | ADR（独立文件） | `site-brief/SKILL.md:28` 明确**不建 ADR 文件**，写进 brief |
| 工作清单 | issue tracker（本地或真实） | `.site/implementation-plan.md` |
| 流程合规 | **不存在** | `.site/state.json`（9 阶段 + 12 命令） |

第三行与第四行是对象 B 全部复杂度的差额来源。对象 A §7.2 已经主张把 9 阶段降级、把 B 类改为声明，这里只需再补一条：**`.site/state.json` 里凡是回答"流程走到哪"的字段，都换成"交付物是什么"的字段**——即对象 A §6 那条唯一不变量。

### 3.4 保留并发机制为可选，而不是砍掉

对象 B 没有租约，因为它假设单写者。对象 A §5.1 指出租约是为评测台服务的——但它同时是对象 A 里实现得最扎实的部分。对象 B 的空缺恰好说明：**租约不该是运行前提，但可以是评测/并行回放时的开关**（对象 A §7.2 的处置已经这么写：保留但可选）。这一条两边是一致的，不需要改。

---

## 4. 两边都解决不了的事

诚实列出，避免把对象 B 当银弹：

1. **"匆忙的 Agent 越过软门禁"防不住。** 换谁写 SKILL.md 都一样。对象 A §3.6 的判断在对象 B 身上同样成立：这类失败只能靠"首轮就问问题"的回复结构 + 交付时回放原话，靠不了门禁。
2. **对象 B 没有可机械复验的验收凭据。** 对象 A 的 `check.py` 矩阵 + `check_id` + 证据哈希（对象 A §5.5 自己也承认它只保证来源不保证正确）在对象 B 里完全没有对应物。**这是对象 A 应当保留并加码的部分**，不要因为"学对象 B"而删掉。
3. **对象 B 的弱回归防线不是优点。** 它对宿主行为差异的适配成本同样存在（frontmatter 要同时维护 Claude Code 与 Codex 两处，`invocation.md` 专门交代"keep the two in sync"），只是它选择了"两处声明"而不是"扫描宿主内部文件"。
4. **对象 B 的"人主动触发"在对象 A 的目标用户上更贵。** 林晓雨画像的用户**不记 Skill 名称**（对象 A `README.md:3` 明说"不需要记住 Skill 名称和开发阶段"）。让"进入开发"必须由人打 slash command，与这条产品定位直接冲突。**这一条是对象 A 不能照抄 H1 的地方**——落点应改为"由宿主 UI 提供的确认控件/审批提示"，而不是要求用户记命令。

---

## 5. 净结论

对象 A 在 `consent-gate-review.md` §6 得出的唯一不变量——

> **最后交出去的东西，必须等于你批准的那个东西；你授权的边界，必须可见且诚实。**

对象 B 实际上执行的是同一条，只是它把两个分句分别落到了不同地方：

- "交出去的东西 == 批准的东西" → 它不做（对象 A 的 `fingerprint` / `handoff` / `deliver` 是这边更强的地方，应保留加码）；
- "授权的边界可见且诚实" → 它交给**人的触发动作**（H1）与**人的终端**（H3），不交给文件。

所以对象 A §7.1 那三条建议，对照对象 B 之后可以更具体：

1. 删除 transcript 依赖 —— 对象 B 用"人触发"替代，且这条**不需要任何本仓脚本**；
2. 反转宿主依赖 —— 对象 B 只有声明式契约（frontmatter 两处、hook 一份），没有内部格式依赖；
3. 收敛到交付不变量 —— 对象 B 没有这一半，**对象 A 的 `check.py` 仍然是差异优势**，不要跟着一起删。

对象 A 的困境不是"门禁不够硬"，而是**把 B 类（只有人能验证）塞进了本来服务于 A 类（本地可机械验证）的那套话术**。对象 B 的存在证明：B 类完全可以不在仓里留痕，只要它的触发点落在 Agent 权限之外。而 A 类——指纹、证据哈希、矩阵——对象 B 一行都没做，那正是对象 A 该保住的部分。

---

## 附：核对记录

| 检查 | 结果 |
| --- | --- |
| 对象 B `skills/engineering/` 文件数 / 体积 | 56 个文件 / 约 168 KB |
| `confirm\|approv\|consent\|authoriz\|permission` 命中 | 22 处，全部为散文或 `wizard` 脚本内 `confirm()` |
| `sha256\|fingerprint\|state.json\|check_id\|transcript` 命中 | 0 |
| 对象 B 目录内可执行治理脚本 | 2 个：`diagnosing-bugs/scripts/hitl-loop.template.sh`、`wizard/template.sh` |
| 对象 B 目录内测试/夹具 | 无（仅 `.changeset/` 与 `.github/workflows/release.yml` 管发布） |
| 本文核对的 commit | `3cca18b368ae95cdbdebbff572ccafa662551015`（`main`） |
