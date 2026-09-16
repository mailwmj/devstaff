# 与改动相称的独立验证

先从请求、`brief.md`、存在的 `surface-brief.md` 页面设计合同、实施计划和实际工程提取本轮能力、明确排除项与适用状态。页面设计合同是设计与验收共享的接口，不另写一份由 Checker 自己解释的视觉规格。上游设计检索属于 `site-design` 的内部实现；Checker 只核对合同中已记录的项目化结论与 `VA-*`，不重跑检索来替换已选方向。每项使用：

```text
前提 → 用户操作 → 可观察结果
状态：passed | failed | not_run | not_applicable
阻断交付：是 | 否（按已确认首版判断）
证据：命令、操作观察、截图或具体限制
```

## 0. 建立覆盖范围并选择检查档位

选择档位前先建立范围清单，不允许只从当前页面或已经写好的测试反推范围。清单至少包含：

- `brief.md` 中每条已确认首版能力和明确排除项；
- 交互合同中的每条 `required`、`excluded`，以及 `recommended` 的采用或偏离依据和 `confirm` 的处理结果；
- 页面设计合同中适用的页面、区块、响应式、组件状态、文案、素材和每条 `VA-*` 可观察标准；
- 每个纵向切片的成功结果、失败恢复、中途退出和适用状态；
- 本轮请求新增或修改的行为，以及实际工程暴露出的必要回归面。

把清单逐条映射到矩阵项；同一项可以有多份证据，但不能用一句“核心流程已测”吞掉多条能力。`required` 缺少实现或证据时为 `failed / not_run`；`recommended` 有项目事实支持的偏离不算失败，但理由必须可回指；未解决的 `confirm` 不得被实现或暗示，若它阻塞核心任务或风险判断则本轮不能通过；`excluded` 要核对页面、导航、数据和文案没有暗示或实现。`VA-*` 可合并进对应机器轴，但矩阵标题或证据必须保留来源 ID。新建、整体改版、主流程或信息结构变化缺少页面设计合同的适用部分时，先将“设计交接不完整”记为阻断 `failed`；Checker 保持只读，不自行补规格。确因账号、环境或能力无法执行时是 `not_run` 并写恢复条件，不能静默省略。只有明确列出且说明不适用理由的项目才能是 `not_applicable`。

优先核对项目特定的承诺，再执行适用的通用检查。沿用上游来源引用，建立以下覆盖关系；只有原型而没有正式实现的内容不能算成品通过：

| 来源引用 | 承诺 / 合同条件 | 正式实现位置 | 矩阵项 ID / 轴 | 实际输入、操作与结果 | 状态 / 证据或限制 |
| --- | --- | --- | --- | --- | --- |
| `BR-03` | 一次卖出可减多个 | 实际数量控件与扣减规则 | `sell-multiple / core_task` | 库存10，卖3，观察库存与相关计数 | 按本轮实际执行填写 |
| `VA-06` | 375px 主行动可达 | 实际核心页面 | `mobile-action / visual_mobile` | 375px 页面与主操作 | 按本轮实际执行填写 |

检查完成前核对“适用来源集合 − 已映射来源集合”。有差集就新增明确检查项：已观察缺实现为 `failed`，缺执行或证据为 `not_run`；核心承诺缺口阻断。把关系随契约的 `coverage` 返回；目标是实际矩阵项 ID，`mapped` 不替代该项结果。五轴齐全、每轴几条、未发现问题都不能推定覆盖充分；目前工具不自动解析 brief 或核对这张来源表，完整性由 Checker 承担。无状态第三方项目直接返回关系，不补写源文档或状态。

检查不是固定的全量回归，而是按本轮改动的影响范围选择档位。把选择和原因写入矩阵：

| 档位 | 适用情况 | 最低范围 |
| --- | --- | --- |
| `smoke` | 文案、颜色、间距、静态布局或不影响行为的局部修改 | 静态/构建检查及至少一个受影响 `core_task`；有浏览器时再实际打开受影响页面并检查代表性视口，入口或启动方式被改动时增加再次打开 |
| `targeted` | 单个交互、计算、导入导出局部修复或明确 Bug | `smoke` + 至少一个受影响 `core_task` 及相关错误/边界状态；有浏览器且涉及持久化时增加再次打开 |
| `full` | 新建、主流程或导航变化、结构重做、权限、隐私、共享数据、持久化、导入导出或高风险事项 | 静态/构建、核心任务和反例、视觉、适用响应式视口、再次打开，以及隐私/越权/错误输入等高价值反例 |

档位只能缩小不受影响的检查，不能跳过本轮受影响的核心任务。`profile_reason` 在所有档位都必填。矩阵还必须声明 `browser.available`：有可控真实浏览器时填写 provider 并执行浏览器检查；没有时填写 limitation，不要求用户为本轮临时安装浏览器。浏览器缺口不能通过降低档位掩盖，也不能替受影响核心任务免责；只能点击、渲染或重开才能证明的核心承诺仍是阻断 `not_run`。

矩阵输入可写成：

```json
{
  "profile": "targeted",
  "profile_reason": "修复导出按钮的空数据处理，不涉及页面结构和持久化格式",
  "browser": {"available": true, "provider": "host-browser"},
  "items": []
}
```

按当前能拿到的材料选择证据模式，不把降级材料包装成更强的结论：

| 证据模式 | 可证明 | 不能证明 | 矩阵处理 |
| --- | --- | --- | --- |
| 真实浏览器运行 | 实际渲染、点击与输入、目标视口、浏览器内状态和再次打开 | 未执行的账号、设备或外部服务场景 | `browser.available=true`；按实际结果记录五轴 |
| 当前版本截图 | 截图中可见的构图、排版、内容和静态状态，可辅助人工发现问题 | 点击结果、动态状态、响应式过程、数据持久化、截图是否确由当前源码产生 | 作为补充 artifact；浏览器轴仍按 `not_run` 记录，不据此写阻断 `passed` |
| 静态检查与项目原生测试 | 构建、引用、类型、纯业务规则、数据转换及测试实际覆盖的失败恢复 | 浏览器渲染、真实交互、剪贴板/存储等浏览器能力和再次打开 | 支撑 `static_build`，并只在测试确实覆盖时支撑对应 `core_task` |

三种模式可以组合。例如没有可控浏览器但用户提供了当前页面截图时，仍可指出截图中可见的视觉问题；桌面/手机视觉与再次打开的运行结论继续诚实标为 `not_run`。选择模式由现有材料决定，不要求用户安装 Node、Playwright、Chromium 或其他验收依赖。

`browser.available=true` 表示有真实可控浏览器，不保证所有视口、离线或账号场景都能执行；能力仅覆盖桌面时不虚报完全没有浏览器。缺失场景分别记 `not_run` 和限制，`full` 下仍按可用浏览器的阻断轴规则处理，不能借整体能力声明把未执行的手机或重开检查降成通过。

长时间验证期间只报告阶段变化：开始验证、进入新检查轴、发现阻断问题、开始修复复验和最终结果。不要把每条命令都当成用户需要的进度消息。

## 1. 四类检查与五个机器轴

矩阵每项必须有非空 `axis`。`full` 始终表示 `static_build`、`core_task`、`visual_desktop`、`visual_mobile`、`reopen` 五个轴，缺一项就不是完整范围记录。真实浏览器可用时五轴均须有阻断项；不可用时 `static_build` 与 `core_task` 仍须有阻断项，三个浏览器轴分别保留至少一项非阻断 `not_run` 及恢复条件。`smoke` 和 `targeted` 至少包含阻断 `core_task`，其他轴由影响范围决定。某项核心承诺若依赖浏览器，必须在 `core_task` 中保持阻断 `not_run`，不能只把视觉轴降为非阻断。模型负责把实际场景拆到正确轴并判断是否充分，工具校验能力声明、最低覆盖和结果结构。

### 静态与构建

运行项目已有的构建、类型、lint 和相关测试。静态网页可使用：

先解析 `site-check` 的安装目录，再使用绝对脚本路径：

```text
python3 /absolute/site-check/scripts/check.py static /absolute/PROJECT [--offline] [--web-root PATH]
```

Windows 可按实际环境使用 `py -3`。该工具检查本地引用、重复 ID、ID 引用、片段和部分离线依赖，并扫描 UI 容器及常见 UI 文本注入点中的 Emoji（`emoji-in-ui` / `emoji-in-ui-sink`）；它不执行 JavaScript，不是完整 CSS、安全或视觉检查。

项目已有 `.site` 时，`static` 返回的 `check_id` 可直接写进矩阵的 `static_build` 项：`"evidence": {"kind": "check", "summary": "静态引用检查通过", "checks": ["<static check_id>"]}`。矩阵会核对该结果为 `passed` 且属于当前源码；项目原生构建、测试仍须各自执行并取证。

项目存在 `.site` 时，静态与命令检查会把结果连同 `check_id` 和源码指纹写入 `.site/checks/`。这是本 Skill 唯一的写入位置：不编辑正式源码，也不写 `.site/state.json`；没有 `.site` 的第三方项目保持只读，不初始化也不补写。

### 核心业务

优先用宿主已有的真实浏览器完成已确认核心任务，以及最可能破坏结果的反例；没有浏览器时可使用项目原生测试、命令或其他可归档运行结果证明不依赖页面渲染的业务规则。按交互合同核对对象生命周期、设备分工、主路径、成功、失败恢复、中途退出和再次打开；根据真实范围选择首次空白、典型数据、无结果、校验错误、保存失败、重复操作、超长内容、权限或离线等状态。中国本地化按实际受众核对中文输入法组合态、日期时间、数字金额、地址电话、触屏和弱网等适用条件；不为无关小工具伪造登录、网络错误或本地渠道。

行为记录需包含实际输入、操作、观察和结果。命令退出 0、截图存在和阅读代码都不能代替必须通过页面操作才能证明的行为；但项目原生业务测试可以证明其实际覆盖的纯逻辑、数据转换和错误恢复，不必为了形式重复到浏览器里。

已经实测但缺可归档证据时，保留真实输入和观察，并说明“操作已执行，证据尚不足”；阻断矩阵项仍为 `not_run`，不能为取得凭据补造证据，也不把“缺证据”说成能力实际失败。

涉及离线交付时，从实际交付入口断网打开或重开，核对图标等所需本地资源的加载及相关操作；资源缺失或仍依赖外部请求不能记为通过。构建成功、静态外链扫描和联网缓存中的截图都不能代替断网证据。离线图标资源必须已随交付产物提供：按需构建进产物、复制所用 SVG/必要字体，或在单文件中内嵌。允许在线页面使用 CDN，但必须在检查范围中明确联网前提；不能把 CDN 当作离线资源，也不能从 Skill 安装路径运行时取资源。

### 视觉

有真实浏览器时用 `site-design` 的只读视觉审查分支，按页面设计合同列出的页面、内容、状态和视口对照已确认方向或参考。逐条核对 `VA-*`，并覆盖 `PG-* / SC-* / RP-* / CP-* / TX-* / AS-*` 中影响视觉和任务的项目。检查主任务、构图、中文排版、控件状态、真实内容和响应式；没有溢出不等于视觉通过。没有真实浏览器时，桌面和手机视觉轴分别记录非阻断 `not_run`，静态阅读不能替代。

新建或整体重做不能只检查首页：至少实际渲染核心页面与最复杂的操作表面，并用 computed style 和操作状态核对以下内容；局部修改按受影响范围选择代表表面：

- 已确认视觉意图及共享变量是否真实进入成品，同角色组件在不同页面是否一致；
- 排版、空间、控件层级、图像裁剪与图标规格是否跨页面继承；
- 适用的默认、悬停、按下、焦点、禁用、加载、成功和错误状态是否完整且可辨认；
- 动效是否使用一致的快/常规/慢节奏并服务状态变化，`prefers-reduced-motion` 下是否减弱非必要运动而不丢失反馈。

原创设计按选定方向和实际质量判断，不要求精确像素或色值复刻。只有用户明确要求还原且参考条件可比时，才把几何、色值或截图差异作为硬性标准。

视觉轴要按 `site-design` 的 [工艺审查](../../site-design/references/craft-review.md) 四条判据核对，并对**实际渲染**执行断言，而不是只做静态阅读：

- **方向有来源**：核对项目已声明的母题是否真的兑现在成品里，以及换个产品名是否还成立；
- **字面成立**：读渲染后的 computed style 核对字号、行高、行长、中文标题字距与数字对齐，并按同一工艺审查检查标点、引号与中西文混排；
- **材料真实**：核对颜色采样来源与素材的出处、许可、裁剪和用途，以及缺口是否如实显示；
- **构图有重心**：缩小到 25% 是否仍有结构与重心，是否有一处服务内容的细节签名。

命令退出 0、`design.py validate` 通过、色对在 token 表里达标、截图存在，都不能单独构成视觉 `passed`。半透明叠层、图片上的文字与动态状态不在自动断言范围内，必须人工查看并说明。

### 再次打开

有真实浏览器时使用交付给创作者的真实入口重新启动或打开，确认：

- 入口仍指向正确项目；
- 使用说明与实际命令一致；
- 关键能力仍可完成；
- 声称持久化的数据重新打开后仍存在；
- 数据位置、备份方式和限制与说明一致。

没有真实浏览器时，`reopen` 轴记录非阻断 `not_run`。若持久化、离线重开或启动入口本身是已确认首版核心承诺，还必须在 `core_task` 轴保留阻断 `not_run`；不能靠非阻断的浏览器轴绕过核心能力。

## 2. 产出矩阵凭据

本档位适用的检查完成后，把本轮每一项写成机器可读矩阵并交给检查工具落盘：

```text
python3 /absolute/site-check/scripts/check.py matrix /absolute/PROJECT --input /absolute/matrix.json --profile targeted --save-evidence
```

`matrix.json` 顶层必须包含 `profile`、非空 `profile_reason` 与 `browser`。`browser.available=true` 时必须提供非空 `provider`；为 `false` 时必须提供非空 `limitation`。每项包含 `id`、`axis`、`title`、`status`（`passed | failed | not_run | not_applicable`）、`blocking`（布尔）和 `evidence`。证据不是一句描述，而是说明它从哪里来：

```json
{"profile": "full", "profile_reason": "新建站正式发布前按当前环境验收",
 "browser": {"available": true, "provider": "host-browser"}, "items": [
  {"id": "core-task", "axis": "core_task", "title": "了解课程并复制微信号", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "桌面 1440x1000 实际操作并复制成功",
                "paths": ["evidence/desktop-1440.png", "evidence/clipboard-result.json"]}},
  {"id": "build", "axis": "static_build", "title": "构建与静态引用", "status": "passed", "blocking": true,
   "evidence": {"kind": "check", "summary": "check.py static 通过", "checks": ["<static check_id>"]}},
  {"id": "copy-feedback", "axis": "core_task", "title": "复制按钮的失败恢复", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "剪贴板被拒绝时的手动恢复截图",
                "paths": ["evidence/clipboard-denied.png"]}},
  {"id": "scope-no-payment", "axis": "core_task", "title": "首版明确排除在线支付", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "桌面与手机的导航、课程页和咨询流程均未出现支付入口或支付承诺",
                "paths": ["evidence/scope-desktop.png", "evidence/scope-mobile.png"]}},
  {"id": "visual-desktop", "axis": "visual_desktop", "title": "桌面核心页继承选定视觉", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "1440px 核心页和弹窗的排版、间距、控件状态与动效节奏实测一致，减弱动效模式保留结果反馈",
                "paths": ["evidence/core-page.png", "evidence/contact-dialog-states.png", "evidence/reduced-motion.json"]}},
  {"id": "visual-mobile", "axis": "visual_mobile", "title": "手机核心页布局与状态", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "390x844 实际渲染与核心操作状态",
                "paths": ["evidence/mobile-core.png"]}},
  {"id": "reopen", "axis": "reopen", "title": "按使用说明再次打开", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "冷启动后核心任务和保存数据仍可用",
                "paths": ["evidence/reopen-result.json"]}},
  {"id": "copy-tone", "axis": "core_task", "title": "复制成功提示的措辞", "status": "passed", "blocking": false,
   "evidence": {"kind": "declared", "summary": "我认为提示语够清楚，但没有单独取证"}}
]}
```

四种证据类型：

| `kind` | 含义 | 能否支撑阻断项 |
| --- | --- | --- |
| `artifact` | 项目内的真实文件（截图、结果 JSON、日志、命令输出），工具记录 sha256 | 能 |
| `command` | 之前 `check.py run` 的 `check_id`，要求退出码 0 且源码未变 | 能 |
| `check` | 之前 `check.py static/run` 的 `check_id`，要求状态通过、源码未变，命令还须退出码 0 | 能 |
| `observation` | 无法归档的操作观察，例如手工读取剪贴板 | 不能，只能非阻断项 |
| `declared` | 只是声明；纯文字 `evidence` 字符串按此处理 | 不能，只能非阻断项 |

写不出可归档证据时，正确做法是把该项标成 `not_run` 并写明恢复条件，而不是写一句 `passed`。把阻断项写成 `observation` 或 `declared` 会被工具直接拒绝——这是"无证据就是 `not_run`"的机械版本。

`--save-evidence` 会把引用到的证据复制到 `.site/checks/evidence/`，归档副本才是交付时核对的依据：复验时重新渲染的截图只覆盖工作文件，不会让已提交的证据失效；但归档副本或未归档的证据文件被改写，交付就会失败。

工具在检查前后重算源码指纹：指纹变化、最低轴缺失、任一阻断项不是 `passed`、或阻断项的 `artifact`/`command`/`check` 证据验证不通过时，矩阵会拒绝生成或整体 `status=failed`。成功时返回由规范化 JSON 内容计算的 SHA-256 `check_id`，凭据落在 `.site/checks/<check_id>.json`；读取时复核文件名、内部 ID、内容摘要及派生路径。报告回执必须带上这个 `check_id`；`site-builder` 只能用它换取 `delivered`，源码一变凭据自动失效。

工具能验证证据文件存在、位于项目内、未被改写、且命令证据确实退出 0，但它**无法验证一张截图是否真的证明了所写结论**。内容寻址能发现事故式手改和引用漂移，不是签名：拥有项目写权限的 Agent 可以重算 JSON 与 `check_id`，因此不能宣称防伪或防恶意写入。把无关文件当作证据仍然要靠独立 Checker 的判断，所以"这一条证据真的支持这个结论"依旧是本 Skill 的责任。

## 3. 命令记录

需要执行任意项目命令并保留结构化结果时可使用：

```text
python3 /absolute/site-check/scripts/check.py run /absolute/PROJECT -- <actual command>
```

工具将工作目录设为项目根，记录退出码、末尾输出、执行前后源码指纹和超时；源码在检查中变化会使结果 failed。输出可能含业务内容，运行前避免打印秘密，不公开上传。

## 4. 结论

- `passed`：已实际执行且观察符合预期；
- `failed`：实际结果不符合，写清位置、复现和影响；
- `not_run`：需要但因能力、账号或环境未执行，说明恢复条件；
- `not_applicable`：本轮确实不适用，说明理由。

核心任务失败、偏离确认方向、真实入口无法重开或重要检查未执行时，不得称全面通过。`site-check` 只给出检查结论；`site-builder` 修复并复验后决定是否交付。

### 差异与修复闭环

按 [上下文契约](../../site-brief/references/context-contract.md) 的 `findings` 返回具体差异：来源 ID、预期、实际、位置、严重度、是否阻断、修复状态与复验证据。文案 `TX-*`、素材 `AS-*`、交互 `IC-*` 或运行说明漂移按实际影响归入核心任务、视觉、再次打开等对应轴；`command` 是证据类型，不是文档问题的专属轴。

逐条重查上游未关闭问题，沿用问题 ID；修复后截图只能证明其可见部分，不能证明业务操作或再次打开。关闭独立验收问题须有 Checker 在本轮冻结指纹上的实际通过证据；未复验为 `fixed_unverified`，失败为 `open`。前后截图、运行结果和冻结指纹分别引用，不能从“现在没有 deviation”反推旧问题已解决。汇总按矩阵实际状态计数，未执行项继续保留，不用“无发现”推导通过。

### 非阻断失败的处置

真实偏差仍记 `failed`。只有不影响已确认能力、选定方向、可访问的核心操作和安全/数据边界的次要差异，才可非阻断保留；严重度名称或用户着急不构成降级依据。每条保留项写明实际影响、可保留理由和后续处理，并在回执记 `resolution=retained`。矩阵阻断项全通过且无证据/指纹问题时，可以附这些已披露限制交付，但不能说“全部检查通过”。是否阻断不确定时先保留阻断，交回 builder 澄清影响或修复。

缺能力、缺执行或缺证据是 `not_run`，不是这类可保留失败；核心承诺的 `not_run` 始终阻断。需要修复的失败矩阵交回 builder，走 `reopen --check`、新冻结和独立复验；Checker 不修源码，也不修改合同使偏差消失。
