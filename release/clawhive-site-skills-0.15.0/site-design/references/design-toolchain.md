# 内置设计工具链

本文件是四套上游设计能力在 `site-design` 中的唯一调用接口。它隐藏供应方目录与独立工作流，外部调用者只需要 `site-design`、`.site/design/surface-brief.md` 和 `scripts/design.py`。

## 什么时候加载

- 新建页面、整体改版、主流程或信息结构变化：完整执行本文件。
- 已有成熟设计系统的局部页面：继承现有方向，只查询受影响的 UX、响应式或技术栈问题。
- 单个低风险样式修复：读取 [Impeccable 工艺下限](upstream/impeccable-craft-floor.md) 中与问题有关的条目，不重新做风格检索。
- 只读审查：读取工艺下限和 [ClawHive 设计原则](upstream/clawhive-frontend-design.md) 的对应章节；缺少项目方向时把方向匹配标为 `not_run`，不启动访谈。

## 一条调用链

### 1. 建立事实与页面职责

先完成 [设计上下文](design-context.md) 与 [任务交互合同](interaction-contract.md)。把当前表面归为 `persuade | operate | read | experience`，分类只决定关注点，不决定结构或风格。

完成条件：使用者、主任务、内容主角、代表内容、主要状态、设备、风险和继承依据都有真实来源或明确缺口。

### 2. 用检索库扩大候选

新页面或新视觉世界执行一次结构化检索：

```text
python <site-design>/scripts/design.py research "<产品类型 受众 使用情境 视觉语气>" --design-system --project-name "<项目名>"
```

查询只写 2～5 个有意义的词并围绕一个主要意图。需要验证具体问题时另做一次最小查询：

```text
python <site-design>/scripts/design.py research "<可观察的 UX 结果>" --domain ux
python <site-design>/scripts/design.py research "<实现问题>" --stack <检测到的技术栈>
```

不持久化上游的 `MASTER.md`；从结果中选用的机制、查询、命中 ID、适配理由和拒绝理由写回页面设计合同。无结果时只允许缩窄查询重试一次；仍无结果就标明使用本项目通用规则，不能伪造命中。

完成条件：候选池有可追溯查询结果，或合同明确记录 `no_verified_match`。

### 3. 形成项目自己的方向

读取 [视觉方向](visual-direction.md)、[完整网页设计交付](upstream/web-design-direction.md) 与 [ClawHive 设计原则](upstream/clawhive-frontend-design.md) 中适用的 `Direction First`、页面类型、素材、反模式和检查章节。将检索结果翻译为当前项目的内容事实、视觉世界、母题、构图命题、字体角色、色彩来源和一个记忆点。

检索排名、行业映射、配色或字体预设都不是项目证据。两个候选互换配色和字体后差异消失，就回到本步重做。

完成条件：每个候选至少有两条上下文依据，且统一配色字体后仍能解释其差异。

### 4. 制作并打磨体验稿

方向确定后读取 [Impeccable 工艺下限](upstream/impeccable-craft-floor.md)；任务型、后台、工具和长阅读表面再读 [Impeccable 操作界面](upstream/impeccable-operate.md)。按 [体验流程](prototype.md) 制作可点击 HTML，并同时检查真实内容、组件状态、响应式、键盘、触控、减少动态效果和素材来源。

上游文档中的 `PRODUCT.md`、`DESIGN.md`、`.impeccable/`、独立确认页面及其 CLI 状态不进入本项目；对应职责已经由 `.site/brief.md`、`.site/design/surface-brief.md`、体验稿和 `site-brief` 门禁承担。这样直接复用工艺规则，同时保持一份状态和一份设计合同。

完成条件：体验稿在约定宽窄视口实际打开，主要问题可判断，主要缺陷已完成一次集中修正；能力不足的检查标为 `not_run`。

### 5. 交接同一份合同

视觉确认后按 [页面设计合同](surface-brief.md) 补齐 `PG-* / SC-* / RP-* / CP-* / TX-* / AS-* / VA-*`。在“设计方法来源”记录：

```text
web-design-direction: bundled-adaptation
impeccable: craft-floor [+ operate when applicable]
ui-ux-pro-max: query + domain/stack + selected result IDs
clawhive-frontend-design: sections actually applied
```

`site-builder` 只按合同 ID 实施，`site-check` 只按合同 ID 取证。上游工具输出不构成用户确认、开发授权或验收通过。

## 冲突顺序

从高到低：安全与高风险门禁 → 用户原话和已确认首版 → 真实项目及成熟设计系统 → 页面设计合同 → 上游工艺规则 → 检索结果和预设。低位规则不能覆盖高位事实。

## 来源与更新

- `web-design-direction`：用户提供的项目内版本，本文件按四 Skill 协作方式本地化。
- `impeccable`：用户提供版本 `4.3.1`，内置工艺下限和操作界面参考。
- `ui-ux-pro-max`：版本 `2.13.0`，MIT；检索代码、数据和许可位于 `../vendor/ui-ux-pro-max/`。
- `clawhive-frontend-design`：由用户提供的前端设计方法本地化，内置设计原则参考。

升级上游时先替换内置实现，再运行 `python <site-design>/scripts/design.py validate` 和整套 manifest 校验；不要让主流程直接引用仓库根的 `design-skills-pack/`。
