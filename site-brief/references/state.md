# 协作状态协议 v3

`.site/state.json` 是跨 Skill 恢复的最小状态，不是事实和决定的正文；正文只在 `.site/brief.md` 和必要的实施计划中维护。

状态文件只由本 Skill 的 `scripts/state.py` 写入。工具负责核对证据、原子替换和递增 `revision`；`site-brief` 判断方案是否确认，`site-design` 提供结构与视觉判断，`site-builder` 提供开发授权、实施和交付判断，`site-check` 只返回检查结果。`site-builder` 初始化新项目时可以创建初始状态；除此之外，任何 Skill 都不得用编辑工具直接改写 `.site/state.json`、`.site/lease.json` 或 `.site/checks/`。

## 最小结构

```json
{
  "schema_version": 3,
  "project_id": "stable-id",
  "revision": 1,
  "stage": "discovering",
  "concept_confirmed": false,
  "structure_required": false,
  "structure_confirmed": false,
  "visual_required": true,
  "visual_confirmed": false,
  "development_authorized": false,
  "delegated": false,
  "runtime": null,
  "delivery_contract": null,
  "delivery_readiness": {"status": "not_planned"},
  "prototype_handoff": null,
  "transition_history": [],
  "next_action": "澄清核心用户和首版任务"
}
```

阶段只使用：`discovering`、`concept_review`、`visual_drafting`、`visual_review`、`ready_to_build`、`building`、`verifying`、`delivered`、`blocked`。

## 只记录真实发生的决定

页面结构与视觉风格是两类决定，但不强制用户经历两轮选择。状态保留两个字段，以便确实分开比较时准确记录：

- **页面结构**（怎么组织、什么最重要、内容怎么排）——本轮让用户比较过多个结构时（`confirm-concept --structure-directions N`，N≥2），他们的选择记进 `structure_confirmed`，由 `confirm-structure` 记录；
- **视觉风格**（同一结构下的气质、排版、色彩、边界、密度、素材表达）——记进 `visual_confirmed`，由 `confirm-visual` 记录。

实际分开比较时仍遵守两条规则：

1. `structure_required=true` 时，`structure_confirmed` 为 false 之前 `confirm-visual`、`authorize-build`、`start-build` 全部拒绝——**用户只比较过结构，就还没有视觉确认**；
2. 结构选择不能冒充视觉选择；一个完整候选没有单独的结构选择时，用 `--structure-directions 1`，只记录最终方向。

同一句话若明确同时选择了当前完整候选并要求开工，可用 `confirm-visual --authorize-build` 一次记录视觉与开发授权；回执只回放一次。它不允许把“好看”推断为授权。

反过来，已经有视觉确认之后又改结构（`confirm-structure`），旧的 `visual_confirmed`、`development_authorized` 和交付状态立即失效——那份风格是为已经不存在的页面选的。已经拿到开发授权或进入实施之后再改结构，必须先 `reopen --scope-changed`：工具会拒绝在 `ready_to_build`、`building`、`verifying`、`delivered`、`blocked` 阶段静默换结构或风格——`block` 只是记录卡点，不是绕过守卫的中转站。

**声明按多结构兜底（fail-closed）。** `confirm-concept` 不写 `--structure-directions` 时按“本轮比较过多个结构”处理，风格门禁会被拦住；只给一个结构必须显式写 `--structure-directions 1`。`0` 和负数被拒绝；`--no-visual` 与多个结构不能同时声明。忘记声明只会让流程停下来问，不会把结构选择悄悄变成视觉确认——这是刻意的方向。

## 门禁工具

使用绝对路径调用，Windows 按实际环境换用 `py -3`：

```text
python3 /absolute/site-brief/scripts/state.py show    /absolute/PROJECT
python3 /absolute/site-brief/scripts/state.py claim   /absolute/PROJECT --owner "本轮会话"
python3 /absolute/site-brief/scripts/state.py confirm-concept   /absolute/PROJECT --quote "用户原话，逐字" [--anchor /absolute/session.jsonl] [--structure-directions 3]
python3 /absolute/site-brief/scripts/state.py plan-delivery     /absolute/PROJECT --channel file|url|local|installed --audience "实际使用者" --sharing required|not_required --offline not_required|downloaded_file|after_first_visit|installed --risk low|high
python3 /absolute/site-brief/scripts/state.py confirm-structure /absolute/PROJECT --quote "用户原话，逐字" --prototype /absolute/PROJECT/prototype.html [--anchor /absolute/session.jsonl]
python3 /absolute/site-brief/scripts/state.py confirm-visual    /absolute/PROJECT --quote "用户原话，逐字" --prototype /absolute/PROJECT/prototype.html [--anchor /absolute/session.jsonl] [--authorize-build]
python3 /absolute/site-brief/scripts/state.py authorize-build /absolute/PROJECT --quote "用户原话，逐字" [--anchor /absolute/session.jsonl] [--delegated]
python3 /absolute/site-brief/scripts/state.py start-build /absolute/PROJECT --prototype-strategy evolve|rebuild --production-entry web/index.html [--reused "结构"]... [--replaced "模拟数据"]... [--removed "演示开关"]... [--prototype-reason "重写原因"]
python3 /absolute/site-brief/scripts/state.py handoff     /absolute/PROJECT --stopped-pid 1234 --freed-port 4174 --service-json '{"owner":"正式站","pid":5678,"port":4175,"root":"/absolute/PROJECT"}'
python3 /absolute/site-brief/scripts/state.py start-verify /absolute/PROJECT
python3 /absolute/site-brief/scripts/state.py deliver     /absolute/PROJECT --check <check_id> --user-action "用户现在能做的具体动作" [--shareable path/inside/project] [--delivery-url https://example.com] [--remaining "仍需用户自己做的事"]...
python3 /absolute/site-brief/scripts/state.py reopen      /absolute/PROJECT --reason "为什么旧验收作废" [--check <failed_check_id>]
python3 /absolute/site-brief/scripts/state.py block       /absolute/PROJECT --reason "阻塞事实与恢复条件"
python3 /absolute/site-brief/scripts/state.py release     /absolute/PROJECT --owner "本轮会话"
```

工具在依据缺失时以退出码 2 拒绝并说明缺口，只有真正写入后才报告状态改变。调用者传入 `--expect-revision` 时，文件修订不一致即拒绝，避免多 Agent 覆盖。

### 确认记录的是声明，不是验证

**没有任何本地脚本能证明用户真的同意过。** `confirm-*` 记录的是 Agent 对用户表达的逐字记录，不是外部证明。低风险工作不应在交付时再次打断用户；高风险项目才逐条回放核对。

- `--quote` 必填：抄录用户原话，逐字；换行与空格原样保存在 `quote`，`quote_sha256` 对精确字节取摘要。空话或转述会被拒绝。工具**不检查**这句话是否真是用户说的，也检查不了。
- `--anchor` 可选：指向宿主会话记录。若能在其中某条**用户**消息里找到这句原话，标注升级为 `quote-matched`；找不到就是虚假断言，直接拒绝；而**读不懂的宿主格式只降级、不阻塞**——这是刻意的，门禁不得依赖宿主内部实现。
- 两个等级的记录都带 `basis_note`，明说它不是同意的证明。
- 确认记录另存 `quote_normalized_sha256`，用于识别不应重复利用的同一句话；`confirm-visual --authorize-build` 是唯一显式合并例外。
- 一句话拆成两半、分别用于两道门禁也算同一句：新原话与已记录原话互为包含关系（含 `--anchor` 路径）会被拒绝。极短的口头应答（如“可以。”）如果字面重复了上一句的措辞，也会被要求换一句——那不是两种决定各自的表达。
- 每次记录都会追加到 `consent_history`。**把某道门禁重新记录一次，不会让旧那句话重新可用**：历史里属于别的门禁的原话依然被拒绝，被覆盖的原话也留在历史里可审，不会被静默抹掉。

因此正向流程在所有宿主上都走得通；宿主能提供可读记录只是把标注从 `agent-reported` 升到 `quote-matched`，不是运行前提。

| 命令 | 记录的判断依据 | 拒绝条件（示例） |
| --- | --- | --- |
| `confirm-concept` | `--quote` 用户原话（可选 `--anchor` 升级）；`--structure-directions N` 声明本轮比较几个结构 | 缺 `--quote` 或为空；`--anchor` 可读但不含该原话；**已到 `building`/`verifying`/`delivered`/`blocked` 阶段**（须先 `unblock` 或 `reopen --scope-changed`，否则交付回放里冻结的原话会和被改写的记录对不上） |
| `confirm-structure` | `--quote` 用户对页面结构的选择 + 项目内普通文件 `--prototype` | 方案未确认；声明了不需要视觉方案（`--no-visual`）；**已到 `ready_to_build`/`building`/`verifying`/`delivered` 阶段**（须先 `reopen --scope-changed`）；原型是目录、符号链接、链接父目录或项目外文件；复用别的门禁那句原话 |
| `confirm-visual` | `--quote` 与项目内普通文件 `--prototype` | 方案未确认；**结构选择还没记录（含未声明结构数时的兜底拒绝）**；**已到 `ready_to_build`/`building`/`verifying`/`delivered` 阶段**（须先 `reopen --scope-changed`）；原型是目录、符号链接、链接父目录或项目外文件；复用方案或结构确认那句原话 |
| `authorize-build` | `--quote` 指向明确授权 | 方案未确认；结构或视觉确认缺项；**已到 `building`/`verifying`/`delivered`/`blocked` 阶段**（须先 `unblock` 或 `reopen --scope-changed`，否则项目能靠重新授权把自己从已交付状态里拿出来）；复用其他门禁那句原话 |
| `plan-delivery` | 使用者、`channel/sharing/offline/risk` | 方案未确认；本地渠道却要求分享；渠道与离线模式矛盾；已进入实施或检查 |
| `start-build` | 已有 writer lease、必要确认、分发合同和原型交接 | 无分发合同；有视觉稿却没记录 `evolve/rebuild`、正式入口与复用项；重写无理由 |
| `handoff` | `--stopped-pid`、`--freed-port`、`--service-json` | 任一应停止 PID 仍在运行；端口被未登记服务占用；登记服务缺少存活 PID、端口未监听或根目录不在项目内 |
| `start-verify` | `handoff` 记录与当前指纹一致 | 无 `handoff`；交接后源码再次变化 |
| `deliver` | 矩阵凭据、用户动作与实际入口 | 分享目标缺通过的 `share` 轴；离线目标缺 `offline` 轴；原型交接缺 `prototype_lineage` 轴；文件渠道缺 `--shareable`；URL 渠道缺非回环 `--delivery-url`；其他既有证据错误 |
| `reopen` | `--reason`；Checker 已接管时还需 `--check <failed_check_id>`；实质范围变化时加 `--scope-changed` | 缺少 `--reason`；`verifying`/checker lease 下缺少当前源码上的失败矩阵；**没有任何可作废的已发生状态**（空项目不许借 `reopen` 拿到 writer 租约和 `building`）。`--scope-changed` 会同时作废方案、结构、视觉与授权确认，之后必须重新 `confirm-concept` |

`claim` 是项目级单写者租约：同一 owner 重复 `claim` 返回原租约且不改获取时间；不同 owner 或 Writer/Checker 角色冲突会拒绝。`start-verify` 把租约从 writer 交给 checker，`deliver` 结束后释放；手动 `release` 必须提供与当前租约相同的 `--owner`，且不能释放 `verifying` 中的活跃 Checker。确需处理已确认失效的陈旧租约时，先用 `block` 记录 Checker 异常与恢复条件，再使用显式留痕路径处理；`verifying` 中的 `claim --force` 同样拒绝。

检查结束后租约仍在 checker 手里：通过时用 `deliver` 释放；不通过时用 `reopen --check <failed_check_id>` 原子取回 writer（同时清空 `writer_release` 和旧交付），再修复并重新交接。失败矩阵必须绑定当前源码；没有 Checker 结果时不能抢回租约。

每次 `save_state` 都向 `transition_history` 追加时间、动作、可用的租约 owner/role，以及固定字段的前后摘要。摘要不包含历史自身，避免递归膨胀；它帮助定位误操作和状态漂移，不构成外部可信审计日志。

冻结指纹包含正式项目文件、列出的 `.site` 文档以及 `.site/design/**` 普通文件；排除会随流程写入的 `state.json`、lease 与 `.site/checks/`。因此确认后的设计稿变化会使交接或验收失效。

`--service-json` 的 PID 存活与端口监听分别检查；跨平台实现不声称能证明该端口一定由所填 PID 占有，这个对应关系仍是调用者声明，Checker 应从实际 URL 核对。

## 一轮完整事务

```text
确认方案 → plan-delivery →（实际分开比较时）确认结构 → 确认视觉/开发授权
→ claim → start-build（记录原型交接）→ 实施与快速自检
→ 停止自有体验稿/开发服务 → handoff（PID 已结束、端口已释放或登记为正式服务）
→ start-verify（冻结指纹，租约交给 checker）
→ site-check 产出矩阵凭据 check_id
→ deliver --check <check_id>
```

失败时保持 `verifying`：修复要先用 `reopen --check <failed_check_id>` 取回 writer 租约，改完源码后重新 `handoff` 与 `start-verify`；旧 `check_id` 因指纹变化自动失效，不得沿用。连续两轮没有新证据或进展时用 `block` 记录恢复条件。

## 交付由真实入口和可观察结果共同定义

`delivery_readiness` 区分计划、预览可用、分享可用、离线可用和正式交付。`stage=delivered` 只在分发合同要求的能力都有本轮证据时成立：

- `--user-action` 必填，写用户**现在就能做的具体一件事**，用用户的说法（"把桌面上的这个文件发到微信"），不是流程说法（"验收通过"）。说不出这句话，就说明还差关键一步，不该 `deliver`。
- `--remaining` 列出仍需用户自己完成的事（例如"跟旅馆确认晚餐最晚开始时间""在自己的手机上打开一次"）。空着表示确认没有。
- 文件渠道必须给 `--shareable`，URL 渠道必须给非回环 `--delivery-url`。
- `sharing=required` 时矩阵必须有通过且可验证的 `share` 轴；离线不是 `not_required` 时必须有 `offline` 轴。
- 有视觉原型交接时必须有 `prototype_lineage` 轴，证明正式结果兑现选中方向并移除了演示内容。

`deliver` 的回执带 `tell_the_creator`、`still_yours_to_do`、`carried_items` 和 `receipt_instruction`：**面向用户的回执第一句是那个动作**，然后是待办清单，最后才是范围与限制。`check_id`、档位、阻断项数量、指纹等术语留在机器字段里，不转述给用户。本轮有沿用项时（见 `site-check` 的增量复验），用一句普通话说明哪些项没有重新检查。

**不能把“发不出去”记成已完成。** 单文件是否能在聊天工具打开必须实测；URL 的离线能力要按“首次联网访问后再断网”等合同前提实测。只完成本地预览时如实报告较低就绪状态，不调用 `deliver`。

## 复验预算：检查不能比干活还贵

状态机记录了每次跃迁的时刻，所以「检查 vs 生产」的比率是**可测量的**，不必靠感觉。`phase_budget()` 把时间线切成两段：

- **生产**：`start-build → start-verify`，加上每个 `reopen → handoff` 之间真正在改代码的时间；
- **检查**：每个 `start-verify → deliver|reopen` 之间的时间。其中**第一轮是探明**，允许花真实时间（它要找的是还不知道的问题）；**第二轮起是复验**，应该便宜，因为它在确认已知结论。

**当复验总时长超过生产总时长（且复验超过 10 分钟这个噪声门槛）时，`deliver` 会拒绝**，除非给出 `--overrun-reason`。理由会被记进交付记录并随回执暴露，不会被静默吸收。

看真实事故的数字：生产 19.8 分钟，探明 15.3 分钟，**复验 82 分钟 = 生产的 4.13 倍**，四个周期里有一个复验周期是它所验证修复的 24 倍。这条守卫会拦下它并要求解释。

10 分钟门槛是刻意的：全程以秒计的快速项目里，比率超过 1 只是噪声，在那里报警只会训练所有人随手写个理由，反而让守卫失效。

正确的解法不是"少验"，而是**让复验变便宜**：凡能用脚本判断的结论都记成可执行断言（`verify_command`），复验时用 `site-check` 的 `reverify` 一条命令重跑，而不是重新推理一遍。

## 判断权与记录权

- `site-brief` 判断方案是否已确认，以及委托是否适用于当前低风险范围；
- `site-design` 判断体验稿是否已展示、结构是否已选定、视觉是否明确确认；只在结构选定后仍然给出风格候选，才算完成第二步；
- `site-builder` 判断开发授权、实施阶段和是否满足交付条件；
- `site-check` 只返回检查结果和矩阵凭据，不请求写入 `delivered`。

记录请求必须带判断依据，例如用户原话、体验稿路径、检查凭据或阻塞事实。门禁工具只负责按依据持久化，不替调用 Skill 重新作出专业判断；它也不判断那句用户原话在语义上是否真等于授权——语义判断仍由 `site-brief` 和 `site-builder` 负责，工具保证的只是"这句话被逐字记下来了，且没有被重复使用"。内容寻址凭据同样只对误改可见：拥有项目写权限的恶意 Agent 能重算整套 JSON，本地脚本不是对抗它的安全边界。

`consent_replay` 只列仍然生效的确认；合并的视觉选择与开发授权只列一次。

**谁真正验证了同意？只有用户本人。** 工具不再假装能验证，改为把这个判断交回用户：

- **按风险回放。** `plan-delivery --risk low` 的可逆项目只给一段当前范围摘要，不要求用户再次确认；`risk high` 才逐条回放原话并等待核对。用户主动纠正时两种模式都必须 `reopen`。
- **首轮就问问题。** 越门最常见的形态不是伪造，而是"Agent 在用户表态前就往前走了"。防它靠的是对话结构（先问、给出推荐项、等回答），不是快照校验。
- **高风险不可逆事项不走这套机制。** 装系统软件、付费、第三方授权、敏感数据等不在这里记声明，也不由本工具判断，走 `site-builder` 运行时规则里的宿主审批通道：那是唯一由别人维护、Agent 无法伪造的入口。

宿主是否提供可读会话记录，只影响标注等级，不影响流程能否走完；任何 Skill 都不得因为读不到会话记录而停止，也不得退回让 Agent 自己编造依据。

## 下游失效

上游改变时必须主动清除旧确认，不能形成“新方案配旧视觉”或“新结构配旧风格”：

- 核心用户、核心任务、首版范围、角色/数据风险或分发目标发生实质变化：用 `reopen --scope-changed`，它会清除方案、结构、视觉、授权、分发合同和原型交接，随后从当前真实范围重新记录。
- 重新确认方案时如果本轮不再比较多个结构（或改声明为 `--no-visual`），`structure_confirmed` 会随之清掉：不存在对应决定的原话不会继续出现在交付回放里。
- 页面结构发生实质变化：`visual_confirmed=false`；旧开发授权没有明确覆盖该变化时 `development_authorized=false`，阶段回到 `visual_drafting`，必须重新给出风格候选并再次记录视觉确认。
- 视觉风格发生实质变化：`visual_confirmed=false`；旧开发授权不复用，`development_authorized=false`，阶段回到 `visual_review`。已到 `ready_to_build` 及之后必须先 `reopen --scope-changed`，门禁会拒绝在这些阶段静默换风格。
- 流程体验改变业务规则或首版范围：先按第一条处理，由 `site-brief` 更新已确认决定；它不因流程演示被选中就自动设置 `visual_confirmed=true`。
- 重新记录方案确认（不带 `--scope-changed`）不会自动清除已记录的结构或视觉确认：它通常只是补记同一个决定。
  实质范围变化必须走 `reopen --scope-changed`，由它统一作废；只改措辞式的重复记录不构成新的范围确认。
- 纯文案、局部样式或不改变确认范围的 Bug：保留现有确认字段；有状态记录时按 `site-builder` 请求进入 `building`，没有记录时不为此创建。
- 已交付项目开始新一轮实质范围变化：先 `reopen` 使旧验收与旧交付失效，再按变化类型使下游确认失效；不能保留 `stage=delivered`。

## 兼容旧记录

读取 schema v1/v2 时保留旧字段并升级为 v3，新增的 `delivery_contract`、`delivery_readiness`、`prototype_handoff` 默认为空。历史交付仍可查看；再次进入实施前必须补 `plan-delivery`，有视觉稿时补原型交接。旧记录不被追溯改写。

`0.12.x` 及更早版本生成的随机 UUID 检查凭据不具备内容摘要，`show` 会保留并标为损坏，`deliver` 不接受。升级不删除旧凭据；要交付时由 Checker 在冻结源码上重新生成 `0.13.0` 内容寻址矩阵。

`0.13.x` 生成的矩阵凭据没有 `consequence` / `surface` 字段，也没有 `carried_from`：它们仍能被读取和交付（字段缺失不影响校验），但**新生成的矩阵必须声明这两个字段，且档位必须等于推导结果**；`full` 不再是可以随手选的"保险档"，只留给「高后果 + 宽影响面」，也永远不允许携带旧结论。第一次用新版工具出矩阵时，按 `site-check` 的 [验证规则](../../site-check/references/verification.md) 重新判定档位，不要沿用旧矩阵里的档位声明。
