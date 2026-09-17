---
name: site-check-v3
description: v3 只读验证。检查已实现的核心任务和相称的静态、错误、移动端或再次打开行为，不修改源码。
---
# v3 验证

先按风险选择最小充分范围。存在 `.v3/design/surface-brief.md` 时，以其中适用的页面、状态、视口和 `VA-*` 为项目特定依据；视觉检查调用 `site-design-v3` 的只读审查分支，不重新发明方向：

- 局部修改：静态检查和受影响结果。
- 普通首版：核心任务成功路径和一个最可能失败的反例。
- 严格项目：核心任务、关键反例、适用视口、再次打开、权限/隐私和独立证据。`independent` 只在宿主使用独立 Checker 上下文完成检查后成立；宿主做不到时返回 `blocked`，不能自行打标。

只记录实际执行的操作和证据。结果使用 `verified`、`limited` 或 `blocked`：

- `verified`：本轮核心任务已实际完成并有证据。
- `limited`：核心任务已实现，但有明确未验证项；允许 guided 交付，必须披露限制。
- `blocked`：核心任务失败或缺少使结论成立的关键证据。

使用五字段回执 `status / summary / artifacts / evidence / limitations` 返回发现、证据和限制后停止，不修源码、不改需求、不宣布交付。
