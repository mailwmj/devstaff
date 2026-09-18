# 变更审查清单（供独立审查 Agent 使用）

本文件是交接材料，不是项目产物，审查结束后可删除。
仓库无 git，无法提供 diff；下面给的是**精确锚点**，请直接按行号读当前文件核对。

## 0. 审查前必读：基线不确定性

- 本仓库 `git status` = `fatal: not a git repository`，**没有版本历史**，无法用 diff 验证。
- 工作期间（15:52–16:01）检测到 `site-design/references/` 下多个文件被**本会话之外**的改动刷新（`craft-review.md`、`design-toolchain.md`、`surface-brief.md`、`SKILL.md`、`scripts/design.py`、`scripts/tests/test_design.py` 的 mtime 落在该区间）。
- 因此**不能假定某个文件的全部内容都是本会话所写**。下面每条都标注了本会话改动的具体位置；请只审查这些位置，其余内容视为他人改动。
- 审查者若需要严格基线，应自行从安装副本或发布包对照。

## 1. 任务背景（两个诉求）

1. **诉求一**：从第一性原理审查 `site-design/intelligence/`（内置检索数据与代码）与 `site-design/references/`（Agent 按需读的规则）是否存在"重复打架"，在不引入过度设计、对 Agent 友好的前提下处理。
2. **诉求二**：确认 `Lucide` / `Phosphor` / `lint-ui` 三者区别，并确立**默认 Lucide，用户明确指定时以用户为准**。

## 2. 改动清单

一共改了 **8 个文件**。按诉求分组。

### 诉求一：消除跨源冲突（6 处，纯文档）

| # | 文件 | 位置 | 改动 |
| --- | --- | --- | --- |
| 1.1 | `site-design/references/design-toolchain.md` | 新增 `## 授权分层：检索没有决定权`（第 44 行起，至第 58 行） | 新增总则"检索只召回候选，不制定标准；返回里的数值阈值、库选择、色值、顺序和 import 代码都不是项目标准"，并附**6 行"一个决定只有一个权威来源"表** |
| 1.2 | `site-design/references/design-toolchain.md` | `## 领域路由`表（第 59 行起） | 4 行加限定：`landing`（版式以落地页指南为准）、`typography`（不采用返回的 Google Fonts URL 与 CSS Import）、`icons`（只取语义与命名）、`gsap`（时长与实现方式以工艺审查 §5 为准） |
| 1.3 | `site-design/references/craft-review.md` | 第 76 行末 | 300ms 动效上限**加作用域**："该上限约束状态过渡与 UI 反馈；营销页的入场与滚动叙事动效不受此上限约束" |
| 1.4 | `site-design/references/craft-review.md` | 第 99 行 | 44×44px 标注为"本包的项目默认操作高度"，并写清 WCAG 2.2 AA 合规下限是 24×24 CSS px，"两者不是同一约束，不得互相替代" |
| 1.5 | `site-design/references/design-context.md` | 第 70 行 | 冲突优先级第 6 级由 `gallery、配方、示例和组件范例` 改为 `gallery、配方、检索结果、示例和组件范例`（堵住"检索结果"未列入最低优先级的缺口） |
| 1.6 | `site-design/references/surface-brief.md` | 第 198 行 | "设计方法来源"节末补一句裁决规则 + 指向授权分层表 |

### 诉求一附带：常驻上下文去重（1 处）

| # | 文件 | 位置 | 改动 |
| --- | --- | --- | --- |
| 1.7 | `AGENTS.md` | 第 63 行 | `硬红线门禁` 中与 `craft-review.md` 重复的 8 条（动词先导、单一 Filled、二次确认、paste、`scale(0.96)`、可中断 transition、同心圆角、语义 Token）**改为引用** `craft-review.md` §4-§6，不复述数值。保留 references 里没有的：≤200 行、跨 3 层透传、URL Query |

### 诉求一附带：体量标注同步（1 处）

| # | 文件 | 位置 | 改动 |
| --- | --- | --- | --- |
| 1.8 | `site-design/SKILL.md` | 第 25、37、49 行 | `craft-review.md` 由 16KB 变 17KB，同步 A5/B5 行体量标注与"单步最大 17KB"。**有测试逐行核对标注与实际文件大小**（见 §4） |

### 诉求二：Lucide 默认 + 用户优先（4 处，含代码）

| # | 文件 | 位置 | 改动 |
| --- | --- | --- | --- |
| 2.1 | `site-design/scripts/design.py` | 第 974 行 | 新增常量 `LUCIDE_ICON_SYSTEM = 'lucide'`，注释明确"包默认；用户或现有工程的选择覆盖它" |
| 2.2 | `site-design/scripts/design.py` | 第 1191–1205 行 | 重写 `_scan_file` 图标判定：保留 `mixed_icon_systems` 为 **blocker**；新增 `icon_system_mismatch` 为 **warning**，期望体系 = 合同声明，未声明时回退默认 Lucide |
| 2.3 | `site-design/scripts/design.py` | 第 200–228 行 | 新增 `_ICON_VENDOR_FIELDS` 与 `_strip_icon_vendor()`，从 `icons` 域结果中**移除 `Library` 与 `Import Code` 字段**，并附 `vendor_note` |
| 2.4 | `site-design/scripts/design.py` | 第 261 行 | 在 `research()` 解析 JSON 后调用 `_strip_icon_vendor(result)` |
| 2.5 | `site-design/scripts/design.py` | 第 1525–1527 行 | `undeclared_icon_system` 文案补充"默认 Lucide；采用其他体系时显式声明即可" |
| 2.6 | `site-design/references/craft-review.md` | 第 101 行 | 图标规则重写为"默认使用 Lucide；用户或现有工程已明确指定其他体系时**以该指定为准**，并如实写入合同 `icon_system`" |
| 2.7 | `site-design/references/surface-brief.md` | 第 61 行 | `icon_system` 字段改为"项目采用的图标体系，留空按默认 `lucide`。用户或现有工程明确指定其他体系时如实填写该体系" |
| 2.8 | `site-design/scripts/tests/test_design.py` | 第 470、672、684、700、710 行 | 新增/改写 5 条测试（见 §3） |

### 2.9 重要：本会话内"引入后又移除"的东西（最终状态已不存在）

诉求二第一版实现是错的，我一度把"非 Lucide 即 blocker"写成硬约束，**与你要求的"用户指定优先"相冲突**，随后已完全回退。审查者**不要去找**这两个 code，它们不在最终代码里：

- `unsupported_icon_system`（已移除）
- `unsupported_icon_system_declaration`（已移除）

已确认全仓无残留引用。若审查者认为"包默认不应阻断用户选择"这条判断本身仍有争议，那是本次最值得复核的设计决定。

## 3. 新增测试清单

`site-design/scripts/tests/test_design.py`：

| 行 | 测试名 | 断言内容 |
| --- | --- | --- |
| 470 | `test_icon_results_withhold_vendor_and_import_code` | `icons` 域结果不含 `Library` / `Import Code`，且 `vendor_note` 同时含 "Lucide" 与 "以该指定为准" |
| 672 | `test_user_chosen_icon_system_is_honored` | 合同声明 `phosphor` + 代码用 Phosphor → **零 blocker 零 warning**（这是用户诉求的核心断言） |
| 684 | `test_undeclared_icon_system_drift_is_a_warning_not_a_blocker` | 未声明 + 用 Phosphor → 通过，但有 `icon_system_mismatch` + `undeclared_icon_system` 告警 |
| 700 | `test_declared_system_drift_is_reported` | 声明 `lucide` + 代码 Phosphor → 告警且回填 `declared` |
| 710 | `test_lucide_only_interface_passes` | 声明 `lucide` + 纯 Lucide → 通过 |
| 664 | `test_mixed_icon_systems_is_blocked` | （既有测试，未改语义）同界面混用两套仍为 blocker |

## 4. 验证证据（我实际跑过的）

```text
python3 -m unittest discover -s tests -p 'test_*.py'
  → Ran 79 tests ... OK
python3 -m unittest discover -s site-design/scripts/tests -p 'test_*.py'
  → Ran 84 tests ... OK          （改动前为 79，新增 5 条）
python3 site-design/scripts/design.py validate
  → 11 recipes and 10 palettes passed ... OK: validated 12 domain files, 22 stack files, ui-reasoning.csv
```

图标行为矩阵（我用临时项目 `/tmp/iconcheck` 实测，已删除）：

| 情形 | 结果 |
| --- | --- |
| 合同 `phosphor` + 代码 Phosphor | passed=True，无 blocker 无 warning |
| 合同 `heroicons` + 代码 Heroicons | passed=True，无 blocker 无 warning |
| 未声明 + 代码 Phosphor | passed=True，2 条 warning |
| 声明 `lucide` + 代码 Phosphor | passed=True，1 条 warning |
| 声明 `lucide` + 混用两套 | passed=False，blocker `mixed_icon_systems` |
| 未声明 + 纯 Lucide | passed=True，1 条 warning |
| 声明 `phosphor` + 代码 Lucide | passed=True，反向漂移 1 条 warning |

## 5. 明确没做的事（审查时不要误判为遗漏）

以下都是**刻意不做**，理由一并给出，供审查者判断是否成立：

1. **没有跨源一致性 linter**。intelligence 与 references 的重复仍然只靠文档规则约束，没有机械检查。理由：两套目录的价值是召回广度，硬编码映射表会把维护成本转成误报。
2. **`intelligence/` 下一切数据文件零改动**，包括 `icons.csv`（内部仍是 Phosphor 的 `Library`/`Import Code`）。理由：`catalog-summary.json` 对 `icons.csv` 有 sha256 完整性锁（`validate_data.py:673` 校验），改数据必须同步改哈希，等于把可复现的上游快照变成私有分支，且上游同步会被静默覆盖。因此拦截放在 wrapper 层（`_strip_icon_vendor`）。
3. **没有删除任何 intelligence 数据**。其中约 23 条 UX 规则是 references 未覆盖的净增信息（Breadcrumbs、Skip Links、Lazy Loading、Code Splitting、Caching、Autofill、Bulk Actions、AI Disclaimer/Streaming、Gaze Hover、Auto-Play Video、Redundant Entry 等）。
4. **`ux-guidelines.csv` #8 / #22 / #104 原文未改**（它们分别反对把 300ms 当通用上限、反对把 44/48 当普适最小值、指出 WCAG 是 24px）。冲突现由 1.1 的授权分层表兜住，而非改数据。
5. **`check-contract` 未增加 `icon_system` 校验**，该字段只在 `lint-ui` 阶段被处理。
6. **`AGENTS.md` 只做了去重**，未改任何流程/状态机语义。

## 6. 已知开放问题（建议审查者重点复核）

1. ~~**`surface-brief.md` 已贴死上限**：当前 **15911 字节**，测试 `test_contract_template_stays_a_fill_in_skeleton` 硬卡 16000。**只剩 89 字节**。该文件是要复制进每个项目的填空骨架，再加一句话就会测试失败。治本需把说明句外移到对应 reference，属于结构改动，我未擅自做。~~ **【已解决，非本次改动】** 上限已由 16000 放宽到 **20000**（`test_contract_template_stays_a_fill_in_skeleton`），并在注释里写明"是边界不是预算，说明仍归对应的 reference"。文件本身**一个字节未改**，仍为 15911。治本（说明句外移）仍**未做**，只是不再被 89 字节卡住。
2. **`_strip_icon_vendor` 是字段白名单外的黑名单**：它按字段名（`Library`、`Import Code`）删除。若上游快照改名或新增同类字段（如 `Package`、`Npm`），会静默失效。审查者可判断是否改为白名单更稳。
3. **`_strip_icon_vendor` 只对 `domain == 'icons'` 生效**。其他域若也含库/import 类字段（例如 stack 指南里的 import 示例）不在拦截范围。
4. **`icon_system` 仍是自由文本**：合同写 `Lucide`（大写）会被 `.lower()` 归一，但写 `lucide-react` 或 `Lucide Icons` 这类别名不会命中，会退化为"与声明不一致"的告警。审查者可判断是否值得收敛取值。
5. **1.1 的授权分层表把"落地页信息顺序与版式"的权威给了 `landing-page.md`**，而 `landing.csv`（34 patterns）与 `products.csv`/`--design-system` 的 `pattern` 字段降级为"命名与备选"。这是本次对 B 类竞争性重复的核心裁决，**请重点复核该裁决是否过强**——它可能削弱搜索在落地页场景的召回价值。
6. **`build --standalone` 无使用痕迹以外的约束**：闸门只保证"走闸门时方向齐备"，不能阻止反复用 `--standalone` 绕过。产出会标记 `{"mode": "standalone"}` 且 `intent.md` 顶部写明未读合同，但**没有下游强制**（例如 `site-check` 或 `state.py` 拒绝消费 standalone 的选择）。审查者可判断是否需要收紧。

## 6.5 本次新增的改动（另一会话，与 §2 独立）

| # | 文件 | 位置 | 改动 |
| --- | --- | --- | --- |
| 3.1 | `site-design/scripts/design.py` | 新增 `_design_judgment_blockers()`（约 822 行）、`direction_gate()`（约 976 行） | 把 prebuild 分支里的四项设计判断判定抽出复用；`direction_gate` = direction 阶段合同检查 + 四项判断接地，**刻意不用 prebuild 阶段**（prebuild 还要求 scope target / constraint impact / 可执行 VA，方向校准期尚未写完） |
| 3.2 | `site-design/scripts/design.py` | `build` 分支（约 1755、1813 行） | 新增 `--project-root`（缺省 cwd）与 `--standalone`；拒绝发生在写盘之前，**不留半成品**；`selection.json` 新增 `direction_evidence`（`direction-gate` + contract sha256 ／ `standalone`） |
| 3.3 | `site-design/scripts/design.py` | `intent_text()`（约 453 行） | `--standalone` 产出在 `intent.md` 顶部写明"未读取任何项目合同，不得作为已确认方向使用" |
| 3.4 | `site-design/references/design-toolchain.md` | 第 54 行 | 授权分层表 "`tokens.json` 只给变量名" → "给出可直接落地的候选值，采用某个配方不构成方向决定"（原文与事实不符：它给的是完整 hex 色板与 px 值） |
| 3.5 | `site-design/references/design-tokens.md` | 第 5、44-50 行 | 补闸门行为、逃生舱语义、带 `--project-root` 的命令示例 |
| 3.6 | `site-design/SKILL.md` | 第 25、27、36 行 | A4 行 8KB→9KB；正文 "63KB"→64KB、"单步最大 17KB"→18KB、"（15KB）"→16KB（后两个中"单步最大"的漂移**非本会话引入**，是并发写入者改 `craft-review.md` 到 18KB 时漏改的） |
| 3.7 | `site-design/scripts/tests/test_design.py` | 新增 `BuildDirectionGateTests`（6 条）、`test_entrypoint_prose_sizes_match_the_files` | 闸门行为覆盖；新守卫把正文里的三个体量数字与文件实际大小绑定（已做变异验证：改回旧值即失败）。**注意：`test_reading_sequence_step_sizes_match_the_files` 与 `_uncited_motif` 所在的 `CheckContractTests` 已被并发改动刷新** |
| 3.8 | `site-design/scripts/tests/test_design.py` | 约 737 行 | 骨架上限 16000 → 20000 |

本轮验证：`site-design` 套件 97 passed、根套件 79 passed、`design.py validate` 通过、闸门三条路径（无合同／方向齐备／`--standalone`）端到端实测。

## 7. 影响面与回归风险

- 改的都是**文档与检查器**，没有触碰 `site-builder` / `site-brief` / `site-check` 的状态机、`state.py` 协议或安装逻辑。
- `install.py` 已验证仍可正常安装四个 skill（`/tmp` 目标目录）。
- 唯一的**行为变更**是 `lint-ui`：原本非 Lucide 与 Lucide 混用时的判定结果有变（新增告警维度、移除会误伤用户选择的阻断）。若其他项目/测试依赖旧的 `icon_system_mismatch` 行为，需复核。

## 8. 建议审查者执行的命令

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s site-design/scripts/tests -p 'test_*.py'
python3 site-design/scripts/design.py validate
```

建议补充的独立验证（我未做）：

- 用一个真实含图标的前端项目跑 `lint-ui`，确认无假阳性。
- 构造合同 `icon_system: "Lucide Icons"` 之类的别名，复核 §6.4 的降级行为。
- 复核 §6.5 的落地页权威裁决是否与 `visual-direction.md` 的"检索只帮助扩展候选"表述自洽。
