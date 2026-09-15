# UI/UX Pro Max 本地检索说明

`site-design` 直接内置 UI/UX Pro Max `2.13.0` 的检索器和数据。它提供 Style、Product、Color、Typography、UX、Icon、Motion、Landing、Chart 和技术栈候选；检索结果是研究材料，不是项目事实、用户确认或最终 Design System。

## 唯一入口

通过本项目适配器调用，不直接依赖宿主插件路径：

```text
python <site-design>/scripts/design.py research "<query>" --design-system --project-name "<name>"
python <site-design>/scripts/design.py research "<query>" --domain <domain>
python <site-design>/scripts/design.py research "<query>" --stack <stack>
```

适配器固定输出 JSON，不暴露上游 `--persist` 与 `--force`；页面设计合同是唯一长期 Design Source of Truth。

## 查询规则

1. 新页面或整体视觉方向用 `--design-system`。
2. 单个交互、可访问性或视觉问题用明确的 `--domain`。
3. 已检测到技术栈且需要实现建议时用 `--stack`；不猜测 Stack。
4. 每次 Query 围绕一个主要意图，使用 2～5 个有意义的词和一个产品、平台或情境约束。
5. 验证返回 Domain、Top Result ID 和当前项目的适配性。结果为空或偏题时只缩窄重试一次。
6. 没有 Verified Match 时记录 `no_verified_match`，回到项目通用规则，不伪造结果。

## 优先级

当项目事实允许对应能力时，依次关注：

1. Accessibility：Contrast、Alt、Keyboard、Accessible Name；
2. Touch And Interaction：44×44px、明确反馈、非 Hover-only；
3. Performance：图像格式、Lazy Loading、Layout Stability；
4. Style Selection：产品匹配、一致 Icon System；
5. Layout And Responsive：Mobile-first、无整页横向滚动；
6. Typography And Color：16px 正文、可读行高、Semantic Color；
7. Motion：有意义、共享节奏、Reduced Motion；
8. Forms And Feedback：Visible Label、Inline Error、恢复路径；
9. Navigation：可预测返回、层级清楚、关键页面可直接到达；
10. Charts And Data：匹配数据关系、非只靠颜色、提供文本替代。

## 结果如何进入项目

在 `.site/design/surface-brief.md` 记录：

- Query、Mode、Domain 或 Stack；
- 采用的 Result ID 与可见机制；
- 它对应哪些用户、任务、内容或设备事实；
- 被拒绝的高排名结果及原因；
- 最终哪些内容进入母题、Token、组件状态或 `VA-*`。

不得直接复制上游 Landing 顺序、行业 `must_have`、Palette、Font Pairing、Component 或 Code。先经过范围分类、项目匹配、反默认和交换检查。

## 内置实现

- Code：`../../vendor/ui-ux-pro-max/scripts/`
- Data：`../../vendor/ui-ux-pro-max/data/`
- License：`../../vendor/ui-ux-pro-max/LICENSE`

升级后通过项目接口验证：

```text
python <site-design>/scripts/design.py validate
```
