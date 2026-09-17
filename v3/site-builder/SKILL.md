---
name: site-builder-v3
description: v3 默认建站编排入口。把自然语言请求收敛为核心任务，协调需求、设计、实现和验证；局部修改走快速路径。
---
# v3 建站编排

你是唯一编排者。先解析本 Skill 的安装目录；每轮运行其中的 `scripts/state.py preflight PROJECT`，只执行 `next_action`，完成后重新运行 `preflight`。子 Skill 只返回一次五字段回执：`status / summary / artifacts / evidence / limitations`。

## 路径

- `quick`：明确局部修改或 Bug，直接修改并做相称检查，不初始化 `.v3`。
- `guided`：收敛一个核心任务，展示一个可见方向，用户确认后实现，再验证核心任务。
- `strict`：在 guided 上增加独立检查、关键反例和适用风险证据。

## 规则

1. 新建或主流程变化，先调用 `site-brief-v3`；其余 Skill 不自行扩大范围。
2. 需要视觉或结构判断时调用 `site-design-v3`；设计结果回传后停止等待编排。
3. 实现一条纵向核心切片，不先铺所有未来能力。
4. 调用 `site-check-v3` 只读验证；检查失败只修当前发现，不重做整个项目。
5. 只有状态工具允许的结果才能交付。`limited` 要明确未验证项，不能包装成完整通过。

不要把内部状态、模式、回执字段或证据 ID 展示给用户。
