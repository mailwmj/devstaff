---
name: site-builder
description: Use when creating, continuing, changing, fixing, or checking-and-fixing a runnable website or web app; it is the default orchestrator and the only Skill that edits formal project code.
---
# 渐进式建站

用户只描述目标和反馈。本 Skill 编排首版收敛、设计、实施、修复、验证和通俗交付；不要把内部阶段或 Skill 名推给用户。

## 路由

- 新建、整体改版、主流程/信息结构变化：`site-brief` → `site-design` → 实施 → `site-check`。
- 局部文案、颜色、间距：读现有约定后直接修改，再检查受影响结果。
- 可复现 Bug：先复现症状，修复并覆盖原症状。
- 只梳理、只设计、只验收：调用对应 Skill，返回其结果后停止。

新建没有快速模式；模板不会跳过方案、视觉或开发授权。局部路径按影响缩短，不另设用户模式。

## 执行

1. **理解现状。** 读取用户指定工程、原生说明和已有 `.site`。有状态时先用 `site-brief/scripts/state.py show` 取得阶段、确认、租约、冻结和检查摘要；不凭旧对话猜测。
2. **确认首版。** 新建、重大变化或核心任务不清时调用 `site-brief`。至少明确最终用户、场景、核心对象、一个核心任务、可见结果、失败恢复、设备、范围和高风险未知。没有成立的方案确认就停止。
3. **取得设计交接。** 需要设计时调用 `site-design`。要求它返回 `.site/design/packet.json`、选中成果和真实渲染证据。builder 消费 DesignPacket，不重新加载整套设计手册。若包中 `gaps` 非空、语义选择未命中且没有有依据的原创/现有答案，先退回设计。
4. **通过开发授权。** 用普通话回放首版、direction、实际页面和模拟范围。已有持续建设委托在范围未实质变化时可继续；否则等待明确开工。结构确认、视觉确认和授权不得互相冒充。
5. **选择实现模式。** DesignPacket 已有任务合同和 direction 后，读取其中的 template 候选；只用 `site.py inspect-template <id>` 打开最终候选。模板属于 patterns：复制后替换真实字段、内容、grammar 和不适用状态，并把 selected/adaptations/rejected 写回设计交接。没有匹配模板就沿项目原生结构实现。
6. **初始化与计划。** 需要新工程时运行 `site.py init`；所有模板仍初始化为 `discovering`。读 [运行](references/runtime.md) 和 [实施](references/implementation.md)，按少量纵向切片写计划；第一条尽快产出可用核心任务。记录真实分发渠道和离线边界。
7. **连续实施。** 正式修改前取得 Writer 租约。沿用工程已有模式；实现成功、失败恢复、中途退出和适用状态，不因模板或规范扩大范围。原型默认 `evolve`，只有技术形态无法承载正式要求时才 `rebuild` 并写理由。
8. **自检、冻结、独立检查。** 运行项目原生命令和最小自检，停止自有服务并 handoff 冻结。调用 `site-check`，传正式入口、DesignPacket、核心任务合同、目标视口和分发条件。Checker 只读；失败后按矩阵取回 Writer，修复、重新冻结并复验。
9. **交付。** 只有当前源码上的阻断检查均通过且重要项没有 `not_run` 才能 deliver。第一句告诉用户现在能做什么，再说明入口、重开方式、已完成范围、建议体验顺序、数据位置、已检查/未检查和限制。内部矩阵术语留在文件。

## 回执

返回项目入口、完成的首版能力、DesignPacket 与 pattern lineage、检查凭据摘要、数据位置、限制和下一步。`site-builder` 是开发授权与正式交付的唯一负责人；文件存在、模板初始化、构建成功或视觉称赞都不能单独证明完成。
