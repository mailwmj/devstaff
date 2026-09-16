# 上下文与交接契约 v1

适用于整套四个 Skill 的内部交接和会话恢复。用户看到通俗结论，调用者得到结构化回执；不要求把完整 JSON 展示给用户，也不新增每个 Skill 的上下文 JSON 文件。

## 来源与消费

| 来源 / 唯一写入者 | 消费字段与用途 | 缺失时 |
| --- | --- | --- |
| 最新请求与工程事实 | brief 校对词义；design 继承现状；builder 与 check 判断影响范围 | 先查项目，只问会改变范围、行为或风险的未知 |
| `.site/brief.md` / site-brief | 用户、场景、核心任务、可观察结果、包含/排除、事实/决定/假设 | 无状态的小修改直接依请求；重大建设缺口交回 brief |
| `.site/state.json` / 门禁工具 | stage、revision、各确认字段与原话 basis、next_action、交接与交付记录 | 不凭文档或回执推断门禁；Checker 不初始化或迁移 |
| `.site/design/surface-brief.md` / site-design | 首版承诺的原型覆盖与正式补齐事项，及 `IC-* / PG-* / SC-* / RP-* / CP-* / TX-* / AS-* / VA-*` | 新建/重大变化缺适用规格或承诺去向即交接失败；Checker 不补规格 |
| `.site/implementation-plan.md` / site-builder | 纵向切片、前提/操作/结果、状态恢复、实现位置与来源 ID，供实施与验收 | 简单修改不创建；必要计划由 Writer 交接前完成 |
| `.site/checks/` / site-check | 矩阵 check_id、指纹、profile/browser、逐项结果与证据，供修复和交付 | 无凭据不推定通过；旧指纹凭据不沿用 |

`reads / writes` 是接口说明，不是新增权限。Skill 正文分支、门禁和 Writer/Checker 隔离规则决定实际行动。

无 `.site` 的第三方只读验收仅返回结果；调用 `check.py matrix` 时不使用 `--save-evidence`，该参数会归档到 `.site/checks/`，不能用于无状态路径。

## 内部回执 schema

沿用各 Skill 既有结果枚举；以下公共字段用于交接或暂停，不在聊天中持久化一份平行规格。调用者不可读结构化返回时，用同字段的紧凑文本回执。

```text
protocol_version: "1.0"
skill: site-brief | site-design | site-builder | site-check
project_root: string | null          # 已定位的实际项目绝对路径；未定位暂停时为 null
status: string                       # 该 Skill 的回执枚举，不等于 state.stage
state_revision: integer | null       # 实际读取的修订号；无 .site 时为 null
outputs: array<{path: string, ids: array<string>}>
evidence: array<{
  ref: string,                       # 文件/命令结果/用户消息的可定位引用
  supports: string,                  # 该证据究竟支持什么，不扩张结论
  limitation: string | null
}>
unresolved: array<{issue: string, recovery: string}>
next: {skill: string | null, action: string}
check_id: string | null              # 有矩阵凭据时引用，不自造
```

`outputs`、`evidence`、`unresolved` 无适用项时为 `[]`。输出只引用现有成果与稳定 ID，不复制文档；证据引用不升级用户原话的 `agent-reported / quote-matched` 标注。`next` 只是建议，不代表用户确认或允许越过门禁。普通小修改保留无状态路径，不为满足回执创建 `.site`。

`project_root=null` 时只返回暂停与定位恢复条件，不读取猜测项目的门禁、不创建或交接正式产物；安装本套件的目录不能冒充用户项目。

各 Skill 原有回执字段仍作为扩展保留；例如 site-design 的 `result` 保存用户选择或审查发现，不改写为状态枚举。审查逐项状态与 Skill 的 `review_complete` 分开表达。

## 覆盖与问题闭环

交接时在公共回执中附以下数组；无适用项时为 `[]`。它们只引用已有 brief、合同、计划和检查项，不另建上下文文件，也不是 `check.py matrix` 的新增输入字段。

```text
coverage: array<{
  source_ref: string,                # 既有 ID 或文件/章节/精确条目；不能从原型反推需求
  target_refs: array<string>,        # 本阶段产物中的页面/控件/状态、切片或矩阵项 ID
  disposition: mapped | gap | not_applicable,
  note: string                      # 模拟边界、补齐责任，或不适用理由
}>
findings: array<{
  id: string,                       # 同一问题在修复和复验时沿用 ID
  source_refs: array<string>,        # 受影响的首版能力或合同条目
  severity: blocker | major | minor,
  blocking: boolean,                # 按核心承诺与风险判断，不仅看严重度名称
  expected: string,
  actual: string,                    # 实际观察及具体差异；未知写明，不能补造数值
  location: string,                  # 文件/页面/控件/状态/视口，按实际可定位材料填写
  resolution: open | fixed_unverified | rechecked | retained,
  recheck: {
    by: writer | checker,
    source_fingerprint: string | null,
    status: passed | failed | not_run,
    evidence_refs: array<string>
  } | null,
  next_action: string | null
}>
```

`mapped` 只表示有明确去处，不表示已实现或检查通过。设计阶段的覆盖判定以 surface brief 的原型覆盖表为准；builder 的正式实现以切片和源码为准；Checker 的结果以同一冻结指纹的矩阵为准。调用者逐条核对本轮适用来源集合与 `coverage.source_ref`：未映射的承诺进入 `gap` 并写补齐责任，不以回执数组非空、检查条数或五轴存在代替完整覆盖。

修复声明只能把问题记为 `fixed_unverified`；实际复验后才为 `rechecked`，失败或未执行的复验保持未关闭。Writer 自检与 Checker 复验分别标 `by`，Writer 的复验不能关闭独立验收问题。Checker 只以新冻结指纹上的实际复验关闭问题；旧证据保留作历史，不作为新版本通过依据。设计体验稿尚无正式冻结时指纹可为 `null`，并明确证据属于体验稿。

非阻断差异可按验证规则记为 `retained`，保留实际失败、影响、处置理由和下一步；这不把矩阵项改成 `passed`。问题 ID 与来源 ID 在矩阵 `title` 或 `evidence.summary` 中保留，详细记录可随内部回执返回；需要归档时仅写 Checker 自己的 `.site/checks/`，无状态第三方验收仍只返回结果。

## 恢复快照

成功的 `state.py` 状态跃迁会原子写入派生 `.site/session-state.json`：

```text
schema_version: 1
project_id: string
project_root: string
revision: integer
stage: string
last_action: string
updated_at: string
next_action: string
```

快照只帮 Agent 找到最近的前沿，不保存门禁布尔值、用户原话、租约或检查结论。根目录以用户指定项目和实际工程为准；快照里的路径只是提示，多个候选或路径冲突时先定位，不跟随聊天引用到另一项目创建 `.site`。

恢复时调用 `state.py show /absolute/PROJECT`，一次取得真实状态、租约、当前指纹、交接/交付凭据和快照状态 `current / stale / invalid / missing`。快照缺失、损坏或与真实状态不一致时忽略它，仍按 state 和实际工程继续；`show` 始终只读，不修快照。下次成功跃迁再生成，快照写入失败有 warning，不回滚已成功的状态跃迁。

即使快照为 `current`，也不能证明用户同意或源码仍可交付：实施前重新核对门禁和租约，验收前核对冻结指纹/PID/端口，交付前核对矩阵和原话回放。快照排除在冻结指纹之外；只读 Checker 不写它。
