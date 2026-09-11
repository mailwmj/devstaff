# 协作状态协议 v2

`.site/state.json` 是跨 Skill 恢复的最小状态，不是事实和决定的正文；正文只在 `.site/brief.md` 和必要的实施计划中维护。

状态文件只由本 Skill 的 `scripts/state.py` 写入。工具负责核对证据、原子替换和递增 `revision`；`site-brief` 判断方案是否确认，`site-design` 提供视觉判断，`site-builder` 提供开发授权、实施和交付判断，`site-check` 只返回检查结果。`site-builder` 初始化新项目时可以创建初始状态；除此之外，任何 Skill 都不得用编辑工具直接改写 `.site/state.json`、`.site/lease.json` 或 `.site/checks/`。

## 最小结构

```json
{
  "schema_version": 2,
  "project_id": "stable-id",
  "revision": 1,
  "stage": "discovering",
  "concept_confirmed": false,
  "visual_required": true,
  "visual_confirmed": false,
  "development_authorized": false,
  "delegated": false,
  "runtime": null,
  "next_action": "澄清核心用户和首版任务"
}
```

阶段只使用：`discovering`、`concept_review`、`visual_drafting`、`visual_review`、`ready_to_build`、`building`、`verifying`、`delivered`、`blocked`。

## 门禁工具

使用绝对路径调用，Windows 按实际环境换用 `py -3`：

```text
python3 /absolute/site-brief/scripts/state.py show    /absolute/PROJECT
python3 /absolute/site-brief/scripts/state.py claim   /absolute/PROJECT --owner "本轮会话"
python3 /absolute/site-brief/scripts/state.py confirm-concept /absolute/PROJECT --quote "用户原话，逐字" [--anchor /absolute/session.jsonl]
python3 /absolute/site-brief/scripts/state.py confirm-visual  /absolute/PROJECT --quote "用户原话，逐字" --prototype /absolute/PROJECT/prototype.html [--anchor /absolute/session.jsonl]
python3 /absolute/site-brief/scripts/state.py authorize-build /absolute/PROJECT --quote "用户原话，逐字" [--anchor /absolute/session.jsonl] [--delegated]
python3 /absolute/site-brief/scripts/state.py start-build /absolute/PROJECT
python3 /absolute/site-brief/scripts/state.py handoff     /absolute/PROJECT --stopped-pid 1234 --freed-port 4174 --service-json '{"owner":"正式站","pid":5678,"port":4175,"root":"/absolute/PROJECT"}'
python3 /absolute/site-brief/scripts/state.py start-verify /absolute/PROJECT
python3 /absolute/site-brief/scripts/state.py deliver     /absolute/PROJECT --check <check_id>
python3 /absolute/site-brief/scripts/state.py reopen      /absolute/PROJECT --reason "为什么旧验收作废"
python3 /absolute/site-brief/scripts/state.py block       /absolute/PROJECT --reason "阻塞事实与恢复条件"
python3 /absolute/site-brief/scripts/state.py release     /absolute/PROJECT
```

工具在依据缺失时以退出码 2 拒绝并说明缺口，只有真正写入后才报告状态改变。调用者传入 `--expect-revision` 时，文件修订不一致即拒绝，避免多 Agent 覆盖。

### 三道确认记录的是声明，不是验证

**必须说清楚能力边界：没有任何本地脚本能证明用户真的同意过。** 用户的判断在用户脑子里，而这个工具写的每个文件，被约束的 Agent 自己也能写。所以三道 `confirm-*` 记录的是**Agent 说用户说了什么**，不是已被验证的事实。

- `--quote` 必填：抄录用户原话，逐字。空话或转述会被拒绝。工具**不检查**这句话是否真是用户说的，也检查不了。
- `--anchor` 可选：指向宿主会话记录。若能在其中某条**用户**消息里找到这句原话，标注升级为 `quote-matched`；找不到就是虚假断言，直接拒绝；而**读不懂的宿主格式只降级、不阻塞**——这是刻意的，门禁不得依赖宿主内部实现。
- 两个等级的记录都带 `basis_note`，明说它不是同意的证明。
- 三道门禁按**引语内容**（`quote_sha256`）比对，不是按文件路径：复制一份会话记录不能把同一句话用两次。

因此正向流程在所有宿主上都走得通；宿主能提供可读记录只是把标注从 `agent-reported` 升到 `quote-matched`，不是运行前提。

| 命令 | 记录的判断依据 | 拒绝条件（示例） |
| --- | --- | --- |
| `confirm-concept` | `--quote` 用户原话（可选 `--anchor` 升级） | 缺 `--quote` 或为空；`--anchor` 可读但不含该原话 |
| `confirm-visual` | `--quote` 与真实存在的 `--prototype` | 方案未确认；原型文件不存在；复用方案确认那句原话 |
| `authorize-build` | `--quote` 指向明确授权 | 方案未确认；需要视觉确认却只有视觉选择；复用视觉确认那句原话 |
| `start-build` | 已有 writer lease 且三个门禁字段满足 | 无 lease；门禁缺项；已交付未 `reopen` |
| `handoff` | `--stopped-pid`、`--freed-port`、`--service-json` | 任一 PID 仍在运行；端口被未登记服务占用；登记的服务根目录不在项目内 |
| `start-verify` | `handoff` 记录与当前指纹一致 | 无 `handoff`；交接后源码再次变化 |
| `deliver` | `site-check` 的矩阵凭据 `--check <check_id>` | 非矩阵凭据；指纹与当前源码不一致；存在非 `passed` 的阻断项；阻断项没有 `artifact`/`command` 证据；证据文件在检查后被改动 |
| `reopen` | `--reason`；实质范围变化时加 `--scope-changed` | 缺少 `--reason`；未记录为什么旧验收作废 |

`claim` 是项目级单写者租约：同一项目同时只能有一个 Writer 或一个 Checker。`start-verify` 会把租约从 writer 交给 checker，`deliver` 结束后释放。绕过租约必须显式 `--force --reason`，并被记录在 `lease_overrides` 里。

检查结束后租约仍在 checker 手里：通过时用 `deliver` 释放；不通过时用 `reopen` 把租约取回 writer（同时清空 `writer_release` 和旧交付），再修复并重新交接。`reopen` 只应在独立 Checker 已经返回后调用。

## 一轮完整事务

```text
确认方案 → 确认视觉 → 开发授权
→ claim → start-build → 实施与快速自检
→ 停止自有体验稿/开发服务 → handoff（PID 已结束、端口已释放或登记为正式服务）
→ start-verify（冻结指纹，租约交给 checker）
→ site-check 产出矩阵凭据 check_id
→ deliver --check <check_id>
```

失败时保持 `verifying`：修复要先用 `reopen` 取回 writer 租约，改完源码后重新 `handoff` 与 `start-verify`；旧 `check_id` 因指纹变化自动失效，不得沿用。连续两轮没有新证据或进展时用 `block` 记录恢复条件。

## 判断权与记录权

- `site-brief` 判断方案是否已确认，以及委托是否适用于当前低风险范围；
- `site-design` 判断体验稿是否已展示、视觉是否明确确认；流程体验产生的业务决定交回 `site-brief` 判断；
- `site-builder` 判断开发授权、实施阶段和是否满足交付条件；
- `site-check` 只返回检查结果和矩阵凭据，不请求写入 `delivered`。

记录请求必须带判断依据，例如用户原话、体验稿路径、检查凭据或阻塞事实。门禁工具只负责按依据持久化，不替调用 Skill 重新作出专业判断；它也不判断那句用户原话在语义上是否真等于授权——语义判断仍由 `site-brief` 和 `site-builder` 负责，工具保证的只是"这句话被逐字记下来了，且没有被重复使用"。

**谁真正验证了同意？只有用户本人。** 工具不再假装能验证，改为把这个判断交回用户：

- **交付时回放原话。** `deliver` 的回执带 `consent_replay`，列出三道门禁各自记录的原话。`site-builder` 必须把这些话原样念回给用户，请其确认或纠正；用户否认任何一条，就必须先 `reopen` 再交付。
- **首轮就问问题。** 越门最常见的形态不是伪造，而是"Agent 在用户表态前就往前走了"。防它靠的是对话结构（先问、给出推荐项、等回答），不是快照校验。
- **高风险不可逆事项不走这套机制。** 装系统软件、付费、第三方授权、敏感数据等不在这里记声明，也不由本工具判断，走 `site-builder` 运行时规则里的宿主审批通道：那是唯一由别人维护、Agent 无法伪造的入口。

宿主是否提供可读会话记录，只影响标注等级，不影响流程能否走完；任何 Skill 都不得因为读不到会话记录而停止，也不得退回让 Agent 自己编造依据。

## 下游失效

上游改变时必须主动清除旧确认，不能形成“新方案配旧授权”：

- 核心用户、核心任务、首版范围、角色/数据风险发生实质变化：`visual_confirmed=false`、`development_authorized=false`，旧实施计划不得继续使用；方案未同时重新确认时 `concept_confirmed=false`。阶段回到 `concept_review`，或方案已确认后进入 `visual_drafting`。
- 视觉方向或核心页面结构发生实质变化：`visual_confirmed=false`；若旧开发授权没有明确覆盖该变化，`development_authorized=false`，阶段回到 `visual_review`。
- 流程体验改变业务规则或首版范围：先按第一条处理，由 `site-brief` 更新已确认决定；它不因流程演示被选中就自动设置 `visual_confirmed=true`。
- 纯文案、局部样式或不改变确认范围的 Bug：保留现有确认字段；有状态记录时按 `site-builder` 请求进入 `building`，没有记录时不为此创建。
- 已交付项目开始新一轮实质范围变化：先 `reopen` 使旧验收与旧交付失效，再按变化类型使下游确认失效；不能保留 `stage=delivered`。

## 兼容旧记录

读取 schema v1 的 `status`、`next_action`、运行信息和旧文档，再从用户最新要求及实际代码恢复事实。门禁工具在第一次写入时把 v1 记录升级为 v2：`status` 映射为 `stage`，`ready` 一类旧自由值统一落到 `concept_review`，缺失的确认字段按 `false` 补齐，其余旧字段原样保留。不删除 `contract.md`、`work.md` 或历史证据，也不凭旧 `ready` 推断三个确认字段为真。
