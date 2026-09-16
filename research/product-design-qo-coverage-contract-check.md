# product-design-qo 覆盖契约借鉴与检查

日期：2026-09-16。范围：当前工作区的 Skill 说明与内部交接契约；不是端到端画像评测、正式网站验收或完整版本回归。

## 本轮边界与成功条件

- 保留四个 Skill、既有 `.site` 事实源、门禁与 Writer/Checker 隔离；不增加平行上下文文件或用户确认步骤。
- 每条已确认首版承诺能从原型覆盖关系追踪到成品补齐、实际实现与矩阵项；原型可保持轻量。
- 同一问题沿用 ID，区分修复声明、Writer 自检复验与新冻结版本上的 Checker 复验。
- 次要偏差可明确保留，但实际 `failed / not_run` 不改写为通过。
- 不实现浏览器驱动、runtime 命令或自动解析需求的覆盖门禁；不更新全局安装、不提交或推送。

## 借鉴与不借鉴

来源是用户指定的本地 product-design-qo 快照：`stories` 的验收条件与设计触点、`check` 的定向来源核对表、`qa` 的差异字段与关联问题 ID、`edge` 的页面状态矩阵。

将这些机制合并进既有 brief、surface brief、实施计划和 Checker 回执。`coverage / findings` 是内部回执扩展，不是 `check.py matrix` 的新增输入字段；来源与问题 ID 通过既有 `title / evidence.summary` 保留。

不借鉴“无发现即通过”、跳过 blocker、逐阶段要求继续、强制多份上下文与看板。product-design-qo 的 QA 默认静态比对不等于真实浏览器验证。

## 输出风险与控制

- 文档表格成为凑格式任务：核对适用来源集合的差集，允许旧 brief 精确条目引用，不规定检查条数。
- 原型被误当正式实现：逐条区分 `covered / simulated / missing`，模拟和未覆盖项必须有成品补齐去向。
- “已修”或单张截图被当作验收：保留 `fixed_unverified`，以 Checker 当前冻结版本的实际复验关闭问题。
- 目录、哈希或证据缺失被补造：未定位暂停允许 `project_root=null`；仅桌面能力不推定手机、离线可执行；保留实际观察和证据限制。

## 隔离行为检查

使用虚拟场景材料，不创建或冒充 `F-*` 夹具，不生成真实网站检查凭据。两个独立评估 Agent 均只读协议、返回草案；没有启动服务或修改源码。

场景：A 原型只演示“卖1”，首版仍承诺多件卖出与离线重开；B Writer 宣称修复但尚未复验；C 桌面已操作、手机与离线缺能力，另有轻微间距偏差。

### 修改前基线

现有规则已经让评估者保留 A 的多件/离线承诺、B 的未复验状态和 C 的核心 `not_run` 阻断。没有复现用户反馈中的承诺遗漏，不将这次基线说成失败的端到端回放。

但返回的是自由文本“范围覆盖”“修复与待验”，没有共同的 `coverage / findings` 字段可直接复用。这支持收敛交接结构，而不是叠加更多用户门禁。

### 修改后应用

独立评估者使用 `coverage.source_ref / target_refs / disposition` 和 `findings` 字段组装三场景草案：A 未覆盖条件保留 `gap` 和正式责任；B 多件问题保持 `fixed_unverified`，不提前冻结；C 离线核心检查仍阻断，轻微间距保留真实 `failed`，不宣称交付。

首次应用指出未定位项目与局部浏览器能力的边界歧义，已在共享契约和验证规则中就近澄清。它也指出应保留“实际操作成功但归档证据不足”的区别，已补入行为记录规则。

最终只读复核确认这两处歧义消除，三场景遵循最新规则。保留一处既有风险：明确合同 token 值的偏差仍须结合可观察验收要求判断，不能把所有色值差异自动升级或降级；本轮不改写既有原创/参考设计判据。

## 命令证据与限制

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'`：21 项通过；未新增引擎行为，现有测试用于防止基础协议回归。
- `PYTHONDONTWRITEBYTECODE=1 python3 site-design/scripts/design.py validate`：配方、色板、gallery 与内置数据校验通过。
- `git diff --check`：通过。
- 干净副本 `/tmp/site-coverage-qa.Gz2Op0/release` 的 `verify_skills.py`：四个 Skill 通过；同副本 `install.py` 成功安装到临时 `installed-final` 目录，版本仍为 `0.16.0`。
- 原工作区打包检查仍被既有 `.DS_Store` 与未列入 manifest 的 Python 缓存阻断，未删除它们；临时副本仅排除 `.git / .DS_Store / __pycache__` 后检查。
- 通用 `skill-creator/quick_validate.py` 缺少 PyYAML，未通过执行；使用仓库自己的 frontmatter、链接、协作和 manifest 校验完成包检查。
- 仓库缺少 `tests/gate_flow.py` 和完整画像评测材料，未执行完整门禁回放或真人评测，不定级、不宣布完整回归通过。

覆盖完整性与证据语义仍由 Checker 判断；本轮没有把说明规则伪装成新增机器能力。
