# Planning Mode Skill

> 标准化规范驱动开发与人机协同审批框架（Spec-Driven Development & Human-in-the-loop Gate）。

本 Skill 将 Antigravity 原生顶级的 **Planning Mode** 沉淀为通用的 Agent 技能规范，旨在解决 AI Agent 在编码场景中容易出现的**“盲目修改、改动发散、破坏现有逻辑、未经确认直接动手、缺乏验证证据”**等痛点。

---

## 目录结构

```text
planning-mode/
├── SKILL.md                                 # Skill 主定义文件（含状态机、判断矩阵、各平台适配）
├── README.md                                # 说明文档
└── references/
    ├── implementation_plan_template.md      # 标准实施计划模板
    └── walkthrough_template.md              # 标准验收报告（证据闭环）模板
```

---

## 核心机制

1. **判断矩阵**：区分“琐碎改动（直出）”与“非琐碎任务（进入计划）”。
2. **Phase 1: Research（只读调研）**：锁定调用链与爆炸半径，禁止修改文件。
3. **Phase 2: Plan Formulation（编制计划）**：按固定结构输出用户确认项、待解疑问、文件级改动明细、验证方案。
4. **Phase 3: Approval Gate（审批关卡）**：强制拦截写工具调用，必须等待人类确认。
5. **Phase 4: Execute & Verify（执行验证）**：执行最小一致修改，运行测试，输出 Walkthrough 证据闭环。

---

## 如何在各类 Agent 中使用

- **Antigravity**：已自动注册为用户全局 Skill（位于 `~/.gemini/config/skills/planning-mode/`），随用随调。
- **Claude Code**：将 `SKILL.md` 的规范复制至项目的 `CLAUDE.md` 或全局配置中。
- **Cursor / Windsurf**：将核心约束添加为 `.cursorrules` / `.cursor/rules/planning-mode.mdc`。
- **自研 Agent / LangChain / AutoGen**：将四阶段状态机（`Research` -> `Plan` -> `Approval Gate` -> `Execute` -> `Verify`）集成至 Agent 的 System Prompt 与 Tool 拦截器中。
