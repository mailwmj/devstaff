---
name: site-design
description: Use when a website needs a visual direction, reference-driven design, structure or style prototype, semantic design selection, or read-only visual review; formal project code changes stay with site-builder.
---
# 网站设计与视觉审查

目标是得到一个能完成真实任务、并且视觉上属于这个项目的方案。不要用行业、风格名、规范或模板替项目做决定。

## 路由

- 制作体验稿或重大改版：执行完整流程。
- 已有成熟设计系统或局部视觉修改：继承现状，只记录任务差异与偏离。
- `site-check` 调用的只读审查：读取 DesignPacket 和实际页面，返回发现，不修改源码、brief 或状态。

新建/改版先读 [设计上下文](references/design-context.md) 和 [页面方向合同](references/surface-brief.md)；制作可见实验再读 [体验稿](references/prototype.md)。只读审查读 [评审协议](references/review-protocol.md)。排版、素材和构图出现具体问题时才分别读对应工艺 reference，不一次加载整套手册。

## 三个独立决定

先写 `direction`，再选择 `grammar` 和 `patterns`：

```yaml
direction:
  source: existing | reference | project-derived
  evidence: []
  motif:
  composition:
  project_signature:
grammar:
  source: existing-system | packaged-spec | project-tokens
  spec_id:
  deviations: []
patterns:
  selected: []
  adaptations: []
  rejected: []
```

`direction` 说明为什么这样表达；`grammar` 只负责一致的视觉语言；`patterns` 是实现方式。它们可以来自不同资产，没有“命中即停”。规范不能产生方向，模板不能产生范围。

旧项目的 `visual_source` 只通过 `prepare-design.mjs` 读取兼容，不手工改写；新记录只写三层。

## 执行

1. **取得事实和任务合同。** 读取 brief、现有工程/设计系统、真实内容、用户提供的参考和主要视口。执行增量素材吸纳协议：当收到用户上传的票据（如机票、酒店单据等）或视觉参考图时，给出即时轻量 ACK 回执（确认收到并简述解析出的关键要素），将解析字段沉淀至输入事实层。按 `required / recommended / confirm / excluded` 写清核心任务、成功、失败恢复、中途退出、再次打开和本地化。缺少会改变任务、结构或风险的决定时调用 `site-brief`。
2. **形成 direction。** 从现有系统、明确参考或项目事实推导视觉世界、母题、构图命题和项目签名。每项都带证据；换一个项目仍无损成立时继续推导，不进入选型。参考只在实际提供时判断可借鉴/不可借鉴，不预建外部来源清单。
3. **语义选择。** 把任务画像写成 JSON，至少包含 `task`、`content_shape` 和一个上下文维度，再运行：

   ```sh
   node tools/select.mjs --profile profile.json --kind style --limit 3
   node tools/select.mjs --profile profile.json --kind template --limit 3
   ```

   硬约束先过滤。只有行业时接受 `needs_profile`；无核心语义命中时接受 `no_match`，不强配。大师资料是 `method`，不进入 style 候选。
4. **选择 grammar。** 优先继承现有系统；否则在 style 候选中选择一份随包规范，或用项目 token。使用规范时读 [规范库](references/spec-library.md)，只加载最终选中的完整文件，补中文字体角色，记录 deviations。
5. **选择 patterns。** 只有任务合同和 direction 已存在时才采用 builder 模板。检查 fit/reject，记录 selected/adaptations/rejected；模板字段、状态和页面不得超出确认范围。
6. **生成紧凑交接。** 将事实、合同、三层、验收条件和选择画像写入一个输入 JSON：

   ```sh
   node tools/prepare-design.mjs --profile input.json --state .site/state.json --output .site/design/packet.json
   ```

   命令非零时先补 `gaps` 或选择画像。DesignPacket 最大 12,000 bytes，是 builder/checker 的首选输入。
7. **制作并真实查看。** 结构确有不确定性时先用低成本结构候选；固定结构后才比较视觉。候选使用同一真实内容，差异来自母题与构图，不是换色。明确在体验稿阶段，用户提出删除顶部大标题、追加导航链接、增加倒计时等版面微调属于体验稿自身演进（prototype evolution），直接就地更新 `prototype.html`，不触发 concept 门禁回退。适配移动与微信生态（100dvh 弹性高度、防触控手势冲突、禁止未确认境外 CDN、包含社交分享元标签）。实际打开桌面与 390px 页面并修复主要问题。
8. **验证。** `check-output.mjs` 仅作静态 grammar 预检；真实证据运行：

   ```sh
   node tools/check-render.mjs --entry <URL或HTML> --contract contract.json --output <evidence-dir>
   ```

   检查 computed style、字体/CJK、实际相邻对比、溢出、触控目标、图片、减弱动效和合同化状态/任务/reopen。构图重心、方向可追溯和项目特异性仍需独立视觉判断。
9. **展示与交接。** 用生活化场景对比说明推荐、取舍、模拟和缺失（从视觉重心、情感氛围与主行动呈现对比，不向用户输出设计学术语）。用户确认后把 DesignPacket、选中稿、实际渲染证据及 `evolve/rebuild` 建议交给 builder；只有实际分开比较过结构与视觉时才分别记录两次确认。

## 回执

返回 `draft_ready | structure_confirmed | visual_confirmed | review_complete | needs_user | blocked`，以及 DesignPacket 路径、成果/视口、选择与拒绝、deviations、渲染证据、模拟范围和下一 Skill。只读审查始终返回 `review_complete`，依据不足写 `not_run`。

`site-design` 不修改正式业务源码，不授予开发权限，不宣布交付。许可审计不属于本流程；实际引入的规范、参考和模板按用户约定默认可用。
