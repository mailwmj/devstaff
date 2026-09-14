# 渐进式建站 Skills：需求基线

> 适用：`site-brief`、`site-design`、`site-builder`、`site-check` 作为一套安装
> 用户：以中国大陆使用环境为主、没有编程背景的中文创作者

## 1. 产品定位

用户只需要描述现实目标、参考、现有项目和反馈，不需要知道 Skill 名称、阶段或技术栈。系统要把模糊愿景收敛为一条可体验的核心任务，生成一个属于该项目的可运行网站，并用真实入口证明它能用。

优先级从高到低是：任务和范围正确、最终用户能完成核心任务、设计有项目依据、错误/移动/重开可靠、交付说明清楚、上下文与 token 经济。省 token 是减少重复读取和重复生成，不是减少必要事实、状态或验证。

## 2. 四个 Skill

- `site-brief`：调查事实、收敛首个可验证版本，集中维护 `.site/brief.md` 与状态门禁。
- `site-design`：建立任务合同与视觉三层，制作可见实验，提供只读视觉审查和紧凑 `DesignPacket`。
- `site-builder`：默认入口和唯一正式 Writer；编排、选择实现模式、开发、修复和交付。
- `site-check`：冻结源码后的只读 Checker；验证静态/构建、核心任务、真实渲染、移动端与再次打开。

用户明确只要梳理、设计或验收时可以直接进入对应 Skill；其余建设、修改和“检查并修复”由 builder 编排。

## 3. 单一用户流程

新建项目不提供快速分支或额外模式，始终从理解目标开始：

```text
项目事实 + 用户目标
→ 首个可验证版本与任务交互合同
→ 项目特定视觉方向
→ 语义检索样式语法与实现模式
→ 项目化适配
→ 正式生成
→ 真实浏览器渲染 + 核心任务 + 再次打开
→ 修复、复验、交付
```

局部文案/样式修改和可直接复现的 Bug 按影响跳过无关环节，但这不是“新建快速模式”。整体改版、主流程或信息结构变化仍回到方案和视觉确认。

## 4. 范围、确认与风险

完整愿景用于保留方向，本轮只实现中小型首版。首版至少明确：最终用户、场景、核心对象、一个核心任务、成功结果、失败恢复、设备、包含/排除项和高风险未知。

结构选择、视觉选择和开发授权是不同决定。只有实际分开比较过结构与视觉时才记录两句话；一个完整候选可以只确认一次视觉。已有持续建设委托可在前置决定确认后继续生效，但视觉称赞不能推断为开工。

状态只通过 `site-brief/scripts/state.py` 写入。确认记录保存用户原话，但不是同意证明；高风险动作仍需当下授权。付费、系统级安装、第三方账号/密钥、真实敏感数据和公开部署不得由全权委托隐式覆盖。

## 5. 设计模型

每次新建或重大改版都分别形成：

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

`direction` 回答为什么这个项目这样表达；`grammar` 负责一致的颜色、字体角色、边界和组件语言；`patterns` 是代码与交互实现。三层可以来自不同资产，不能“命中即停”，也不能让规范或模板替项目决定方向。

旧项目 `visual_source` 只读兼容，由 `prepare-design.mjs` 映射并标记缺失证据；不批量重写。新项目只写三层。

方向必须来自现有项目、用户指定参考或真实项目事实。母题、构图命题与项目签名通过替换检查：换成别的客户或行业仍完全成立时，说明它只是通用装饰。方向形成前，token、配色、风格名和模板都不能作为答案。

## 6. 语义选择与成熟资产

风格规范和实现模板使用同一选择画像：

```text
task / content_shape / content_subject / audience / trust_posture /
asset_conditions / interaction_intensity / primary_device
```

明暗、素材是否可用、减弱动效和视觉风险先作为硬约束过滤；其余维度评分排序。行业名称不参与选择，只有行业输入时返回 `needs_profile`；没有核心任务或内容形态命中时返回 `no_match`。候选最多三个，每个包含匹配理由、强项、代价和拒绝条件。

`site-design/assets/spec/catalog.json` 的 50 个 `style` 是 grammar 候选；20 个 `method` 只在需要特定设计方法时读取，不能当风格候选。只读取最终选中的一份完整规范。中文页面必须补可用的中文字体栈，中文标题字距为 0；规范缺陷和项目覆盖写入 `deviations`。

`site-builder/assets/templates/catalog.json` 的模板属于 patterns。只有任务合同和 direction 已存在时才能选择；复制后必须替换业务字段、真实内容、视觉语法和不适用状态，并记录 adaptations/rejected。模板不能带入未确认页面、角色、数据或流程。新建仍走同一流程，模板只节省实现 token。

成熟参考、规范和模板在实际引入时逐项判断 fit、reject、adaptation 与验证命令；不预先维护外部来源清单，也不把外部系统设成行业默认。许可审计不属于本项目的选择或生成门禁，实际引入资产默认可用。

## 7. DesignPacket 与上下文预算

`site-design/tools/prepare-design.mjs` 是设计到实施/检查的唯一紧凑 seam。输出只含项目事实、任务合同、三层决定、验收条件、状态摘要和最多三个候选，最大 12,000 bytes。builder 和 checker 优先读取该包，不重新加载整套设计手册。

每条规则只有一个 owner：产品不变量在本文件；术语在 `CONTEXT.md`；状态事务在 `site-brief/references/state.md`；设计推导在 `site-design/references/*`；实施在 builder；验收矩阵在 checker。`SKILL.md` 只保留路由、必要不变量和按需 reference 链接。

固定场景实际 `input_tokens` 是最终指标。发布目标是在同模型、同场景和同工具条件下，中位输入 token 至少降低 30%，中位质量不下降且不新增否决项。静态字符数只是开发期代理，不能冒充真实 token。

## 8. 实施模板

首批可运行起点覆盖：

- `static`：content-led 与响应式阅读；
- `browse`：筛选、列表/详情、比较、空状态和窄屏重排；
- `form`：表单、错误汇总、草稿、提交前核对和完成状态；
- `tool`：本地 CRUD、持久化、导入导出、错误与确认。

`site.py list-templates` 查看紧凑目录，`inspect-template` 只读取一个卡片，`init --template` 复制所选实现。模板必须完整可运行并有静态与浏览器验证，不得放空壳占位。

## 9. 用户运行时质量闭环

正式生成后至少执行：

1. 项目原生静态/构建命令；
2. 核心任务的前提、操作和可见结果；
3. 桌面与 390px 真实渲染；
4. 适用的焦点、悬停、禁用、错误和加载状态；
5. 字体/CJK 回退、相邻色对比、溢出、触控目标、图片加载与裁剪、减弱动效；
6. 从真实交付入口再次打开，核对持久化和说明。

`check-output.mjs` 只做源码级规范预检，不能称为渲染证据。`check-render.mjs` 通过 Playwright 读取 linked CSS 和 computed style，并可执行合同化核心任务与 reopen。自动探针必须同时有应通过和应失败的控制页。构图重心、方向可追溯和项目特异性仍由独立视觉判断完成。

Writer 修复后必须重新冻结并由 Checker 复验。没有浏览器、账号或必要环境时完成可执行部分，其余写 `not_run`；重要项未运行或核心任务失败时不能交付。

## 10. 维护者生成质量闭环

完整评测只在 Skill、规范、索引、模板或检查器发布前运行，不增加普通用户步骤。权威协议在：

- `tests/novice-user-evaluation.md`：画像、UC、RC、评分和否决；
- `tests/site-design-scenarios.md`：SD-01～SD-17、MV-01～MV-08；
- `tests/scenarios.json` 与 `tests/fixtures.lock.json`：固定输入和夹具锁；
- `tests/evaluate.py`：运行记录、双真人门槛和 token 对比。

自动冒烟可由 Agent 执行，但只能给局部结果。完整结论需要全部固定场景、两名身份不同的真人、真实浏览器证据、无非计划 `not_run`，并记录 Skill/资产版本、选择与拒绝、产物、截图、五维得分、input/output token、耗时、评测者和否决项。

## 11. 兼容与非目标

- 不新增 Skill、用户可见阶段、快速新建模式或行业一键风格；
- 不要求一次实现完整愿景或穷尽未来需求；
- 不用模板、规范、构建成功、截图存在或自动评分代替用户任务和视觉判断；
- 不因升级清空旧 `.site`，不把旧确认倒填到新范围；
- 不要求所有网站单文件、零依赖或公开部署；
- 不把维护者完整评测放进普通生成路径。
