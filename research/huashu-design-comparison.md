# 对照评审：alchaincyf/huashu-design 有哪些机制值得本仓吸收

> 日期：2026-09-12
> 对象 A：本仓的 `site-*` 四件套（`skills.json` 0.9.0，工艺层已在 0.10.0 补入）
> 对象 B：[`alchaincyf/huashu-design`](https://github.com/alchaincyf/huashu-design)，按 commit [`a790f704d85f277cc93d2081b0840d00036969bb`](https://github.com/alchaincyf/huashu-design/commit/a790f704d85f277cc93d2081b0840d00036969bb)（2026-08-25）核对，MIT，约 2.4 万 star
> 方法：`git clone --depth 1` 取回全仓（63 MB，`SKILL.md` 579 行 + 30 个 `references/` + `scripts/` + `assets/` + `demos/` + `test-prompts.json`），通读 `SKILL.md`、`references/workflow.md`、`references/verification.md`、`references/critique-guide.md`、`references/content-guidelines.md`、`scripts/design-gate-hook.sh`、`scripts/verify.py`、`SECURITY.md`、`README.md`、`test-prompts.json`；本仓侧核对 `site-brief/references/state.md`、`site-brief/scripts/state.py`、`site-design/references/{prototype,review-protocol,design-quality,design-tokens}.md`、`site-check/scripts/check.py`、`research/SITE-DESIGN-RESEARCH.md`、`research/host-injection-surfaces.md`、`AGENTS.md`
> 性质：对照分析与建议，未改动本仓任何 Skill、脚本或状态
> 外部内容说明：对象 B 的内容按数据对待；下文行号来自本文核对时的取回结果

---

## 0. 结论摘要

1. **有启发，但不在门禁强度上。** 对象 B 的 gate 是"项目目录里存在某个 md 文件"，由 Agent 自己写、无原话绑定、无修订号、无租约、无指纹。本仓 `state.py` 在这条线上严格更强，整体照搬是回退。
2. **真正可吸收的是三类东西：候选可见性的记录、"用户看过才能选"的停轮纪律、以及把规则依据和降级路径写清楚。** 这三类恰好是本仓当前偏弱或只写在散文里的部分。
3. **最值得做的一件事：`confirm-structure` / `confirm-visual` 目前只记"比较过几个"和一个 prototype 路径，Agent 声明 3 个却只做 1 个，脚本发现不了。** 对象 B 的 `direction-approved.md` 要求记下"展示了哪几版 + 截图路径 + 用户选择原话"，并有"`design-demos/` 下真有 3 个 .html 才算走完"的产出自检。这是纯增益的补强。
4. **第二件：方向必须在动手前声明"form 来自内容的哪里"。** 对象 B 的 form 推导五问 + "写不出来就是在套模板"（`SKILL.md:365-373`），能把本仓 `review-protocol.md` 的"项目标志检查"从评审时的临时发现，变成"事先声明 → 成品核对"。
5. **第三件：把机械检查从 token 色对推进到实际渲染。** 本仓 `design.py` 只校验 `tokens.json` 里指定的不透明色对，并明确声明不检查实际字体与叠层；对象 B 给了一组可执行数字下限和两个"安静派做过头输给普通 baseline"的实测（`SKILL.md:315`）。本仓已有 44px 触控 token，缺的是把它变成断言。
6. **明确不采纳：60 种风格库 + `date +%S` 秒数轮盘抽签。** 这正是本仓 [`SITE-DESIGN-RESEARCH.md`](SITE-DESIGN-RESEARCH.md) 诊断为同质化诱因的机制，而且用挂钟抽签决定方向不可复现、不可审计，与本仓的指纹与证据纪律冲突。可取的是它的**意图**（打破模型"每次都偷选安全极简"的确定性），达成手段应该用本仓已有的"结构必须真正不同 + 事先声明母题"。
7. **也不采纳：把"反 AI slop"提到最高优先级。** 对象 B 的交付标准是"让人认不出是 AI 做的"；本仓的第一硬下限是真实性与主任务可达，审美属于**可覆盖启发式**（`design-quality.md` 的三强度分级）。顺序倒过来会出现"为了不像 AI 而牺牲诚实 placeholder"。
8. **两处对象 B 更值得学的表达方式**：每条硬规则都带日期与实测案例（2026-07-17 B00 整片返工、2026-06-06 PPT 翻车、2026-04-20 DJI 事实错误），以及 `SECURITY.md` 把网络目的地、密钥、子进程、删除行为穷举成表并明说"hook 永不自装"。

---

## 1. 对象 B 的实际机制（与门禁/设计流程相关的全部）

`SKILL.md` 之外还有 30 个 `references/`，但能被称为"机制"的只有下表这些：

| # | 机制 | 位置 | 强度 | 执行者 |
| --- | --- | --- | --- | --- |
| M1 | 三方向硬门：任何新视觉设计先出三个差异化真实初稿，用户选定后才执行；指定风格/给了品牌名**同样不豁免** | `SKILL.md:219-235`、`:359` | 软（提示词）+ 展示后停轮 | Agent 自觉 + 用户 |
| M2 | 唯一豁免三种（用户本次明说跳过 / 已选定方向后的迭代 / 非设计机械操作），且必须落档 `direction-approved.md` | `SKILL.md:224-227` | 软 | Agent |
| M3 | 选择无效铁律：只有文字、没有真实视觉时不让用户选 | `SKILL.md:290` | 软 | Agent |
| M4 | Gate 文件协议：`brand-spec.md` / `direction-approved.md` / `导演稿.md` 不存在的环节视为没做 | `SKILL.md:406-417` | 软（文件存在=环节做了） | Agent |
| M5 | PreToolUse hook：≥45s 长片渲染缺 `direction-approved.md` → `exit 2` 阻断；`SKIP_DESIGN_GATE=1` 显式可审计放行；**永不自装**，需用户手动配 `settings.json` | `scripts/design-gate-hook.sh`、`SECURITY.md` "Hooks" 节 | 硬（宿主侧） | 宿主 |
| M6 | 三套逻辑并行 subagent 各出一版真实视觉；不支持 spawn 时改串行 + 三个不同 anchor 物理隔离趋同 | `SKILL.md:286-304`、`:548` | 软 | Agent |
| M7 | 三版布局骨架必须互异；少于 3 个 `.html` 就是没走完 | `SKILL.md:314`、`:320` | 软，但产物可数 | Agent |
| M8 | form 推导五问（叙事角色/观众距离/视觉温度/容量估算/视觉母题）+「写不出 form 来自内容的哪里 = 在套模板」 | `SKILL.md:365-373` | 软 | Agent |
| M9 | 可读性硬底线：正文 ≥14px、标签 ≥12px、对比度 ≥4.5:1、命中区 ≥44×44px、留白必须是构图不是缺席 | `SKILL.md:315`、`content-guidelines.md:169-178` | 软（无脚本断言） | Agent |
| M10 | 核心资产协议：出现可识别的品牌/产品名 → 官方 logo 是**必需**资产（出现几个取几个），base64 内嵌，不足=STOP | `SKILL.md:115-132`、`:275` | 软 + 自检门 | Agent |
| M11 | 弱 runtime 降级五步（并行→串行→1 主版+2 轻量变体→只读 1 个 reference→跳过检查点问答改 assumption），并点名**绝不降级**的一项 | `SKILL.md:543-554` | 软 | Agent |
| M12 | 版本自检：读 `.last-update-check`，30 天内静默跳过；到期才比较 `rev-parse HEAD` vs `ls-remote`，且不主动更新 | `SKILL.md:570-579` | 半自动 | Agent |
| M13 | 交付产物硬校验：`verify-video.sh` 断言分辨率/帧率/时长 ±2%/音轨存在/首尾黑帧/LUFS，`exit code 非 0 不许交付` | `references/verification.md` 末节 | 硬（脚本） | 脚本 |
| M14 | 5 维度评审 + 概念维一票否决（概念 ≤5 分则总评封顶 6.0），配"盖住文字和 logo 还认得出主题吗""换个客户名还成立吗？成立=模板" | `references/critique-guide.md` | 软 | Agent |
| M15 | 显式能力边界与安全声明：网络目的地穷举、密钥只读自己的 `.env`、云脚本需 `--yes`/`HUASHU_CLOUD_OK=1`、递归删除只限自建临时目录 | `SECURITY.md` | 文档 | 人 |
| M16 | `test-prompts.json`：`prompt → expected → tests` 三元组，6 条 | 仓库根 | 人工回放 | 人 |
| M17 | 风格库自带「色彩推导协议」：条目里的 hex 只是示例锚点，必须先采样→收敛→论证，直接复制条目 hex 等于"生产品味更好的 slop"；温度体系故意让"大胆"款占多数（"模型的确定性偏差天然偏安静极简，库的配比要把它往大胆推"） | `references/design-styles.md:8-19`、`:22-60` | 软 | Agent |

**没有任何一项**是状态机、原话哈希、修订号、租约、指纹或证据再哈希。全文检索这些概念在对象 B 中零命中。

---

## 2. 对象 A 的对应现状（判断的基线）

- **四道确认 + 原话绑定**：`confirm-concept / confirm-structure / confirm-visual / authorize-build` 各自必填 `--quote`，按 `quote_sha256` 内容比对防止一话两用，`--anchor` 可把标注升到 `quote-matched`，读不懂只降级不阻塞（[`state.md`](../site-brief/references/state.md)）。
- **结构与视觉是两道门、fail-closed**：`structure_required=true` 时 `structure_confirmed=false` 会拦住 `confirm-visual`/`authorize-build`/`start-build`；不写 `--structure-directions` 按"比较过多个"处理。
- **同意只能由用户本人验证**：`deliver` 回执带 `consent_replay`，交付前把四道原话逐条念回。
- **Writer/Checker 严格串行**：`handoff` 校验 PID 已结束与端口已释放并记录冻结指纹，`start-verify` 后源码再变直接拒绝，`deliver` 只接受 `check.py matrix` 凭据且会重新核对证据哈希。
- **已有但偏弱的三处**：
  1. `confirm-structure` 只用 `--structure-directions N` 记**数量**，`confirm-structure`/`confirm-visual` 只收**一个** `--prototype` 路径（`state.py:1291-1297`）。候选集合本身不留痕。
  2. 方向合同（`surface-brief.md`）没有"这一页的视觉母题来自哪条业务事实"的强制句；项目特异性是 `review-protocol.md` 在评审时才要求"至少指出一个"。
  3. 机械检查只有一条 DOM 断言（横向溢出）+ token 色对比对；`design-tokens.md:61` 自己声明"不检查…实际字体"。
- **已明确排除的**：`research/host-injection-surfaces.md` 决定**不用 hook**——但那是为 bootstrap 注入排除的，与对象 B 用 hook 做**阻断**不是同一件事，本仓的排除结论不被对象 B 推翻。

---

## 3. 建议吸收（按优先级）

### P0-1 记录"用户对比过什么"，不只记录数量

[事实] 对象 B 的 `direction-approved.md` 要求写入"展示了哪几版、截图路径、用户选择原话"，并要求自检 `design-demos/` 下真有 3 个 `.html`（`SKILL.md:320`、`:326`）。
[判断] 本仓当前的"声明了 3 个方向"是无法核验的计数；Agent 声明 3 却只做 1 个，`state.py` 与 `check.py` 都不会发现。这与本仓"每条 passed/failed 都要能回指证据"的标准不一致。
[建议] `confirm-structure` 与 `confirm-visual` 增加可重复的 `--candidate <path>`：每个候选必须真实存在，数量与 `--structure-directions` 一致；候选路径连同哈希进入状态，交付时沿用现有 `verify_delivery_evidence` 的再核对机制。**边界不变**：这仍然只是"记录声明"，不证明用户真的看过；但它把可编造的数量声明变成文件可核验。

### P0-2 方向必须在动手前声明"form 来自内容的哪里"

[事实] 对象 B 要求每个页面/镜头开工前答 form 五问，其中第五问是"这个内容独有的视觉母题是什么"，交付时必须写出一句"form 来自内容的哪里"，写不出即判定在套模板（`SKILL.md:365-373`）。
[判断] 本仓 `review-protocol.md` 的"项目标志检查"方向正确，但它是**评审时**才去找项目特异性，等于事后自证。`site-design-baseline.md` 已经实测到"三方向部分依赖现成风格范式"这一缺口。
[建议] 在 `surface-brief.md` 增加五问字段（叙事角色/观看距离/视觉温度/容量估算/视觉母题）与一句必填的"form 来自哪条业务事实"；`confirm-structure` 时把该句带入状态；`site-check` 的"方向匹配"轴改为**核对事先声明的母题是否真的出现在成品里**，而不是临时发现一个特异性。这样方向匹配失败也有了可指认的对象。

### P0-3 机械检查从 token 色对扩展到实际渲染

[事实] 对象 B 给出一组数字下限（正文 ≥14px、标签 ≥12px、对比度 ≥4.5:1、命中区 ≥44px），并附实测反例：安静派留白做过头 = "大片死白 + 微缩字号，第一眼像页面渲染坏了"，直接输给普通 baseline（`SKILL.md:315`）。
[判断] 本仓 [硬下限/条件性风险/可覆盖启发式] 的三强度分级比对象 B 的单一硬底线更成熟，但落到**可执行断言**的只有横向溢出。`design.py` 校验的是 token 色对，不是渲染后的实际文字与相邻背景。
[建议] 在 `review-protocol.md` §2C 增加可执行 DOM 断言：正文/标签的 computed `font-size` 下限、实际文字与其背景的对比度、命中区尺寸。分级要遵守本仓已有分层——对比度与命中区按硬下限；字号下限标注为可覆盖启发式（成熟设计系统或项目 token 可覆盖，且必须说明依据）。不得让数字断言冒充设计通过，§2 的三轴判断保持独立。

### P1-1 越门逃生门统一成"带原因的显式声明"，并进入交付回放

[事实] 对象 B 的 `SKIP_DESIGN_GATE=1` 是唯一逃生门：显式、单用途、可在命令里审计；豁免还必须把"用户明示跳过"写进对应 gate 文件（`SKILL.md:416`、`design-gate-hook.sh`）。它还明确"用户说继续，授权的是进入下一步，不是跳过该步内部的 gate"（`SKILL.md:416`）。
[判断] 本仓的机制更细（`--no-visual`、`--structure-directions 1`、租约 `--force --reason`、`block --reason`），但 `--no-visual` 是一次性字段，跳过所依据的原话不保留、也不进 `consent_replay`。结果是"用户让我跳过"和"我自己跳过了"在交付时无法同样核对。
[建议] 在状态里增加 `gate_exemptions[]`：记"跳过哪道门 / 依据原话 / 记录时间"，并在 `show` 与 `deliver` 的 `consent_replay` 里与四道确认一起念回。

### P1-2 弱宿主降级阶梯写成一节，并点名"绝不降级"的那一项

[事实] 对象 B 用一节写清触发判定、五步降级顺序，并以一句收尾："降级牺牲多样性和流程，绝不牺牲反 slop 底线和真实资产协议"（`SKILL.md:543-554`）。
[判断] 本仓把宿主能力差异分散在 README 矩阵与各 Skill 正文里；读者（尤其维护者）要拼出"缺能力时先放弃什么"。
[建议] 集中一节写降级顺序，并点名本仓唯一不降级项——应当是"无证据即 `not_run`、核心任务必须实测、四道确认不做推断"。README 能力矩阵可加一列"缺失时的降级动作"，与对象 B 的 `references/` 路由表同一作用。

### P1-3 交付形态的资产完整性

[事实] 对象 B 有实测教训：交付单文件 HTML 时相对路径的资源挪个目录就全员裂图（`../assets/google.svg` 六个按钮全裂直接输掉评审），因此单文件交付必须 base64 内嵌（`SKILL.md:275`）。
[判断] 本仓交付的是真实工程而非单文件，但 `site-design` 产出的隔离体验稿（`prototype.html` + `assets/`）与 `site-builder` 的 starter 交付同样存在"换目录就裂"的形态。`site-check` 的"再次打开"轴目前覆盖从真实入口重启，未覆盖**迁移路径后入口是否仍可用**。
[建议] 在再次打开轴补一条"变更绝对路径/迁移目录后入口仍可用"，或扩展现有 `check.py static` 对相对资源引用做存在性断言，并把图片缺失列为阻断项（`design-quality.md` 目前只要求"不把色块标成真实图片"）。

### P2-1 已安装副本的版本/哈希自检

[事实] 对象 B 的 `.last-update-check` 机制：30 天内静默跳过，到期才比较本地 HEAD 与远端，且**不主动更新**，只在任务结束后附一句（`SKILL.md:570-579`）。
[判断] `AGENTS.md` 的 60 秒预检要求"记录实际加载的安装路径和版本；发现不一致先标记风险"——这是纯人工步骤；`scripts/install.py` 只校验仓库侧 manifest。
[建议] `install.py` 在目标目录写 `.installed.json`（bundle 版本 + 各 Skill manifest 哈希 + 安装时间），让"装的那份 ≠ 仓库这份"能一条命令比出来。这正好服务评测预检的人工项。

### P2-2 给场景表加一列"由哪条断言覆盖"

[事实] 对象 B 的 `test-prompts.json` 是 `prompt → expected → tests` 三元组，明确每条 prompt 覆盖哪些机制（workflow 提问 / variations / 反 slop / deck_stage / ios_frame…）。
[判断] 本仓 `tests/scenarios.md` 已有"输入/应调用/应停位置/禁止误判"，但新增的机械与视觉约束（如 P0-2、P0-3）没有对应的回归入口。
[建议] 给 `scenarios.md` 每例加一列"覆盖的断言/门禁"，并补 2～3 条针对新增约束的回归例（例如"只做一个结构候选却声称比较过多个"应被拒绝、"把类别模板换个 logo 就交付"应在方向匹配轴判 `failed`）。

---

## 4. 明确不采纳

| 机制 | 位置 | 不采纳的理由 |
| --- | --- | --- |
| 60 种 HTML 原生风格库 + `date +%S` 秒数轮盘抽签 | `SKILL.md:296-304`、`references/design-styles.md` | **要把库和选库方式分开看**：该库的「色彩推导协议」与"大胆款故意占多数"配比（M17）与本仓反同质化的关切同向，比"复制风格标签"成熟。不采纳的是**用它来驱动方向选择**——本仓 [`SITE-DESIGN-RESEARCH.md`](SITE-DESIGN-RESEARCH.md) 已诊断"可复制资产把方向暗示成换色换字体"是同质化根因，再叠 60 项清单与 recipe 会放大这个断层；挂钟抽签不可复现、不可审计，与指纹/证据纪律冲突。可取的是意图（打破保守极简的确定性），手段应用"结构必须真正不同 + 事先声明母题" |
| Gate 文件协议本身 | `SKILL.md:406-417` | 文件存在只证明 Agent 写过这个文件。本仓 `state.py` 的原话哈希、修订号、租约、指纹严格更强；整体照搬是回退。只借 3.1/3.4 的信息设计 |
| 把"反 AI slop"当最高优先级 | `SKILL.md:6-16`、`165-210` | 本仓第一硬下限是真实性与主任务可达，审美是可覆盖启发式。把反 slop 提到真实性之上，会推出"为了不像 AI 而牺牲诚实 placeholder"的倒挂 |
| 按产品类型自动切"高密度/克制"档 | `SKILL.md:439` | 这是风格先于任务事实的判断，与本仓"任务事实优先、不把颜色与行业或人群刻板绑定"冲突（`design-tokens.md` 第 5 条已明确反对） |
| 单体 579 行 `SKILL.md` + 30 个 references + 63 MB 资产 | 全仓 | 本仓"每 Skill ~30 行 + 按需 references + 机器脚本分工"在上下文预算上更优；对象 B 自己的降级第 3 条（只读当前任务那一个文件）也在承认这个问题 |
| 5 维度评分与一票否决 | `references/critique-guide.md` | 本仓刻意用 `passed / failed / not_run / not_applicable` 而非打分，避免把"像 AI 的分数"当验收结论。但"换个客户名还成立 = 模板"这个**可证伪问法**值得直接借来当方向匹配的 `failed` 判据 |
| 水印、云 TTS、AI 生图、视频导出链 | `SKILL.md:9`、`565-567`、`scripts/cloud/` | 与本仓范围（网站与 Web 应用建设）无关 |

---

## 5. 两套体系的强弱对照

| 维度 | huashu-design | 本仓 site-* | 更强的一侧 |
| --- | --- | --- | --- |
| 门禁强度 | 文件存在（Agent 可写） | 四道确认 + 原话哈希 + 修订 + 租约 + 指纹 | 本仓 |
| 同意验证 | 记选择原话 + 展示后必须停轮 | `consent_replay` 交付回放 + `basis` 分级 | 本仓（"展示后必须停轮"值得吸收） |
| 候选可见性 | 记展示版本 + 截图路径 + 3 文件自检 | 只记数量与单个 prototype 路径 | **对象 B** |
| 方向生成方法 | 风格库 + 秒数抽签 + 三套逻辑 | 结构差异 + 项目特定表现 + 方向合同 | 各半（本仓方法对，缺事先声明母题） |
| 视觉下限 | 数字硬底线 + 实测反例 | 三强度分级 + token 色对校验 + 1 条 DOM 断言 | 各半（规范本仓强，断言对象 B 全） |
| 产物与证据校验 | `verify.py` 截图 + `verify-video.sh` 阈值 | `check.py matrix` + 证据再哈希 + 阻断项 | 本仓 |
| 独立验证 | 无（自己验自己） | Writer/Checker 串行隔离 | 本仓 |
| 降级策略 | 显式五步 + 点名不降级项 | 能力矩阵 + 分散说明 | 对象 B（表达） |
| 安全/能力边界声明 | `SECURITY.md` 穷举网络、密钥、子进程、删除 | README 能力矩阵 + 运行时分级 | 对象 B（穷举度） |
| 规则依据 | 每条硬规则带日期与实测案例 | 研究文档带证据，Skill 正文不带 | 对象 B |
| 上下文经济 | 579 行 SKILL + 路由表 | 每 Skill ~30 行 + references | 本仓 |
| 交付物形态 | 单文件 HTML / deck / 视频 | 可再次运行的网站工程 | 不构成比较（目标不同） |

---

## 6. 若采纳，最小落地清单

1. `state.py`：`confirm-structure` / `confirm-visual` 增加 `--candidate`（可重复、路径必须存在、数量与 `--structure-directions` 一致），候选哈希进入状态并在 `deliver` 时再核对。
2. `surface-brief.md`：增加 form 五问与"form 来自哪条业务事实"必填句；`review-protocol.md` 的"方向匹配"改为核对该句在成品中的兑现。
3. `review-protocol.md` §2C：增加渲染后可执行断言（字号下限按可覆盖启发式，对比度与命中区按硬下限）。
4. `state.py`：增加 `gate_exemptions[]`，并入 `show` 与 `consent_replay`。
5. `templates/AGENTS.md` 或各 Skill：集中一节弱宿主降级顺序，并点名唯一不降级项。
6. `install.py`：写 `.installed.json`（版本 + manifest 哈希 + 时间），供评测预检一条命令比对。
7. `tests/gate_flow.py` + `tests/scenarios.md`：为新门禁与断言补回归例，场景表加"覆盖的断言"列。

**验收方式**：沿用本仓既有纪律——每一条新门禁都要能在 `tests/gate_flow.py` 里被回放（含反向用例），每一项新断言都要能引用真实渲染证据；新增规则若无法写出反向用例，就不应升级为阻断项。

---

## 7. 限制与未核实

- 对象 B 的"实测实锤"（B00 210s 返工、五大 Coding Agent PPT 翻车、DJI Pocket 4 事实错误、盲测评审）均取自其文档自述，本文未独立复核，引用时只作为其规则依据的**呈现方式**示例，不作为事实结论。
- 对象 B 的 star 数、commit 时间取自 GitHub API 与本地克隆，随时会变。
- 本文通读了对象 B 的流程与门禁相关文件；`references/design-styles.md` 只读了头部（用法、色彩推导协议、分区结构）与分区标题，未逐条核对 60 项风格内容；`slide-decks.md`、`voiceover-pipeline.md`、`animation-*.md` 等表现层长文只确认了结构。第 4 节对风格库的判断针对"用它驱动方向选择"这一用法，不是对该库 60 项内容质量的评价；若要评估库本身，需单独一轮通读。
- 第 3 节各项建议均未实施，也未做反向验证；按本仓纪律，采纳前应先写反向用例再改门禁。
