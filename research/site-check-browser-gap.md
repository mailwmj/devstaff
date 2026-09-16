# `site-check` 浏览器验证能力调研

日期：2026-09-16  
范围：仓库内 `site-brief`、`site-design`、`site-builder`、`site-check` 的脚本与 `AGENTS.md`；仅核对源码和一手文档，未修改实现。

## 结论

用户给出的核心判断基本成立，但需要两个限定：

1. 仓库的 `site-check` 工具链确实不包含浏览器驱动；`check.py static` 明确不执行 JavaScript，也不做运行时交互、完整 CSS 解析或视觉验证（`site-check/scripts/check.py:594-595`；`site-check/references/verification.md:60`）。仓库中四个主 skill 的脚本清单也没有浏览器脚本：`site-brief` 2 个、`site-design` 1 个、`site-builder` 2 个、`site-check` 1 个（`find site-*/scripts -type f`，其中 `site-design/vendor` 是第三方设计检索库，不是浏览器驱动）。
2. `full` 的机器门禁要求五个阻断轴，包含必须实际操作/渲染/重开的四类轴。`check.py` 只验证证据声明存在和指纹未变，自己不会执行这些检查（`site-check/scripts/check.py:360-365,381-405`）。因此使用者必须提供外部浏览器或等价运行环境，并把结果以 artifact/command/check 证据交给矩阵。

## 逐项证据

### 1. `full` 要求五个阻断轴

`FULL_REQUIRED_AXES` 定义为 `static_build`、`core_task`、`visual_desktop`、`visual_mobile`、`reopen`（`site-check/scripts/check.py:53-59`）。矩阵按 profile 选择完整轴或仅 `core_task`，并在缺少阻断轴时抛错（`site-check/scripts/check.py:360-366`）。文档对同一要求的说明见 `site-check/SKILL.md:12` 和 `site-check/references/verification.md:46-48`。

其中浏览器依赖不是工具推断出来的，而是验证规则明文要求：核心业务要“用浏览器或等价运行环境”完成任务及失败/边界反例（`site-check/references/verification.md:66-70`）；视觉章节要求对实际渲染执行断言而非静态阅读（`site-check/references/verification.md:74-94`）；再次打开章节要求从真实交付入口重启/打开并核对数据（`site-check/references/verification.md:96-104`）。

### 2. `check.py` 不是浏览器执行器

`static_check()` 的实现遍历 HTML/CSS、解析本地引用、ID、片段和 Emoji，最后返回静态检查结果及限制；限制明确写着没有 JavaScript 执行、运行时交互、完整 CSS 解析、安全审计或视觉验证（`site-check/scripts/check.py:479-596`，尤其 `:503-585` 和 `:587-595`）。

`matrix_check()` 只读取矩阵中的 evidence，校验 artifact 路径/sha256、历史 check_id、状态和源码指纹；它不会打开 URL、截图、执行 JS 或重开页面（`site-check/scripts/check.py:224-297,299-407`）。返回值还把这一点列为 limits（`:400-405`）。因此“矩阵强制页面轴但工具本身不跑页面”是准确的。

### 3. `not_run` 对阻断轴的实际结果

矩阵允许的状态包括 `passed`、`failed`、`not_run`、`not_applicable`（`site-check/scripts/check.py:53-56`）。所有阻断项只要状态不是 `passed` 就进入 `blocking_not_passed`（`:381-384`）；只要该列表非空，矩阵总体 `status` 就是 `failed`（`:399-400`）。所以在 `full` 中把缺少浏览器的视觉/交互/重开项诚实标为阻断 `not_run`，确实不能产生可交付的 `passed` 矩阵。

文档同时要求无浏览器时标 `not_run`（`site-check/SKILL.md:23`；`site-check/references/verification.md:32,153,175-176`），并规定只有五个轴都存在且各自阻断项通过，矩阵才可能用于交付（`site-check/references/verification.md:48`）。这不是“永远只能 full”：`smoke`/`targeted` 的最低机器轴只有阻断 `core_task`，且应按实际影响范围选择（`site-check/references/verification.md:24-32,48`）。不过文档也明确不能用降低档位掩盖本轮受影响的核心任务（`:32`），所以若本轮确属新建/结构变化/持久化等 `full` 范围，无浏览器就只能保持不完整/失败，而不是降档交付。

### 4. 反例要求存在，但工具不强制“至少一项”

验证规则要求核心业务覆盖“最可能破坏结果的反例”，并列举失败恢复、中途退出、保存失败、校验错误、重复操作、权限、离线等状态（`site-check/references/verification.md:66-70`）；`full` 的最低范围也写明“核心任务和反例”及高价值反例（`:28-32`）。

但 `matrix_check()` 的机器校验只检查 item 的字段、证据、最低轴集合和阻断状态；没有按 `core_task` 检查失败恢复/边界输入 item 是否存在（`site-check/scripts/check.py:318-366`）。因此“文档要求、工具不检查”得到源码支持。该缺口是质量/流程风险，不代表当前实现声称已验证这些反例。

## 对建议的判断

- 增加 `site-check/scripts/browser.py` 可以减少各项目重复编写浏览器启动、截图、JS 求值和进程清理代码，但这属于实现改动；本次调研未实现。
- 文档应更直白地区分：`not_run` 是诚实记录，不等于可交付通过；在 `full` 的阻断轴上会使矩阵状态失败/不能交付。现有文档已经分散表达这一机制，但没有把因果链用一句话连起来。
- 若要提高质量，给 `core_task` 增加至少一个失败恢复/边界反例的机器化要求是合理方向；需谨慎设计项目范围与可表达的证据格式，避免把所有小工具强行套入不适用场景。当前 `check.py` 没有该规则。

## 未核实或不能从仓库证明的说法

仓库无法证明用户提到的“15 分钟/30 分钟超时”“Chrome 产出后不退出”“62 个进程泄漏”“窗口宽度钳到 500px”以及其私有 `tests/chromeio.py` 等实验细节；这些需要实验日志、脚本副本或运行记录。它们不能作为本仓库实现缺口的直接证据。

