# 协作状态协议 v2

`.site/state.json` 是跨 Skill 恢复的最小状态，不是事实和决定的正文；正文只在 `.site/brief.md` 和必要的实施计划中维护。`site-brief` 是状态文件的唯一协调写入者，其他 Skill 负责作出其职责内的判断，再把结果交给 `site-brief` 记录。`site-builder` 初始化新项目时可以创建初始状态。

## 最小结构

```json
{
  "schema_version": 2,
  "project_id": "stable-id",
  "revision": 1,
  "stage": "discovering",
  "concept_confirmed": false,
  "visual_confirmed": false,
  "development_authorized": false,
  "delegated": false,
  "runtime": null,
  "next_action": "澄清核心用户和首版任务"
}
```

阶段只使用：`discovering`、`concept_review`、`visual_drafting`、`visual_review`、`ready_to_build`、`building`、`verifying`、`delivered`、`blocked`。

## 写入协议

每次记录协作结果：

1. 重新读取当前文件，核对 `project_id` 和调用者提供的实际项目；
2. 只更新本次结果涉及的字段，保留未知字段、`runtime` 和未被替换的旧信息；
3. `revision` 在当前整数上加一；
4. `next_action` 写成一个可执行下一步；`blocked` 时写恢复条件；
5. 写到同目录临时文件并原子替换；写入成功后才报告状态改变。

损坏、其他项目、修订冲突或写入期间文件发生变化时保留原件，重新读取现场，不以空状态覆盖。没有 `.site` 且当前只是简单咨询、检查或局部修改时不创建状态文件。

阶段转换还必须满足：

- `ready_to_build`：`concept_confirmed=true`、需要视觉确认的任务已有 `visual_confirmed=true`，且 `development_authorized=true`；
- `building`：沿用 `ready_to_build` 的门禁，或属于明确无需创建项目状态的简单修改；
- `verifying`：存在实际实现和真实交付入口；
- `delivered`：调用者必须提供 `site-check` 检查矩阵，所有适用且阻断交付的项目均为 `passed`；
- 条件不满足时拒绝推进，保留当前阶段并把缺口写进 `next_action`。

## 判断权与记录权

- `site-brief` 判断方案是否已确认，以及委托是否适用于当前低风险范围；
- `site-design` 判断体验稿是否已展示、视觉是否明确确认；流程体验产生的业务决定交回 `site-brief` 判断；
- `site-builder` 判断开发授权、实施阶段和是否满足交付条件；
- `site-check` 只返回检查结果，不请求写入 `delivered`。

记录请求必须带判断依据，例如用户原话、体验稿路径、检查矩阵结果或阻塞事实。`site-brief` 负责持久化，不替调用 Skill 重新作出专业判断。

## 下游失效

上游改变时必须主动清除旧确认，不能形成“新方案配旧授权”：

- 核心用户、核心任务、首版范围、角色/数据风险发生实质变化：`visual_confirmed=false`、`development_authorized=false`，旧实施计划不得继续使用；方案未同时重新确认时 `concept_confirmed=false`。阶段回到 `concept_review`，或方案已确认后进入 `visual_drafting`。
- 视觉方向或核心页面结构发生实质变化：`visual_confirmed=false`；若旧开发授权没有明确覆盖该变化，`development_authorized=false`，阶段回到 `visual_review`。
- 流程体验改变业务规则或首版范围：先按第一条处理，由 `site-brief` 更新已确认决定；它不因流程演示被选中就自动设置 `visual_confirmed=true`。
- 纯文案、局部样式或不改变确认范围的 Bug：保留现有确认字段；有状态记录时可按 `site-builder` 请求进入 `building`，没有记录时不为此创建。
- 已交付项目开始新一轮实质范围变化：按变化类型使下游确认失效；不能保留 `stage=delivered`。

## 兼容旧记录

读取 schema v1 的 `status`、`next_action`、运行信息和旧文档，再从用户最新要求及实际代码恢复事实。只有需要写入协作状态时才升级为 v2；保留可用旧字段和旧文件，不删除 `contract.md`、`work.md` 或历史证据，也不凭旧 `ready` 推断三个确认字段为真。
