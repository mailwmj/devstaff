# 与改动相称的独立验证

先从请求、`brief.md`、存在的 `surface-brief.md` 中的交互合同、实施计划和实际工程提取本轮能力、明确排除项与适用状态。每项使用：

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
- 每个纵向切片的成功结果、失败恢复、中途退出和适用状态；
- 本轮请求新增或修改的行为，以及实际工程暴露出的必要回归面。

把清单逐条映射到矩阵项；同一项可以有多份证据，但不能用一句“核心流程已测”吞掉多条能力。`required` 缺少实现或证据时为 `failed / not_run`；`recommended` 有项目事实支持的偏离不算失败，但理由必须可回指；未解决的 `confirm` 不得被实现或暗示，若它阻塞核心任务或风险判断则本轮不能通过；`excluded` 要核对页面、导航、数据和文案没有暗示或实现。缺少映射时，该项必须是 `failed`；确因账号、环境或能力无法执行时是 `not_run` 并写恢复条件，不能静默省略。只有明确列出且说明不适用理由的项目才能是 `not_applicable`。

检查不是固定的全量回归，而是按本轮改动的影响范围选择档位。把选择和原因写入矩阵：

| 档位 | 适用情况 | 最低范围 |
| --- | --- | --- |
| `smoke` | 文案、颜色、间距、静态布局或不影响行为的局部修改 | 受影响页面实际打开、静态/构建检查、一个代表性视口；若入口或启动方式被改动，增加一次再次打开 |
| `targeted` | 单个交互、计算、导入导出局部修复或明确 Bug | `smoke` + 受影响的核心操作、相关错误/边界状态，以及涉及持久化时的再次打开 |
| `full` | 新建、主流程或导航变化、结构重做、权限、隐私、共享数据、持久化、导入导出或高风险事项 | 静态/构建、核心任务和反例、视觉、适用响应式视口、再次打开，以及隐私/越权/错误输入等高价值反例 |

档位只能缩小不受影响的检查，不能跳过本轮受影响的核心任务。没有浏览器、运行环境或必要账号时，缺口必须记录为 `not_run`，不能通过降低档位掩盖。

矩阵输入可写成：

```json
{
  "profile": "targeted",
  "profile_reason": "修复导出按钮的空数据处理，不涉及页面结构和持久化格式",
  "items": []
}
```

长时间验证期间只报告阶段变化：开始验证、进入新检查轴、发现阻断问题、开始修复复验和最终结果。不要把每条命令都当成用户需要的进度消息。

## 1. 四个检查轴

### 静态与构建

运行项目已有的构建、类型、lint 和相关测试。静态网页可使用：

先解析 `site-check` 的安装目录，再使用绝对脚本路径：

```text
python3 /absolute/site-check/scripts/check.py static /absolute/PROJECT [--offline] [--web-root PATH]
```

Windows 可按实际环境使用 `py -3`。该工具检查本地引用、重复 ID、ID 引用、片段和部分离线依赖；它不执行 JavaScript，不是完整 CSS、安全或视觉检查。

项目存在 `.site` 时，静态与命令检查会把结果连同 `check_id` 和源码指纹写入 `.site/checks/`。这是本 Skill 唯一的写入位置：不编辑正式源码，也不写 `.site/state.json`；没有 `.site` 的第三方项目保持只读，不初始化也不补写。

### 核心业务

用浏览器或等价运行环境完成已确认核心任务，以及最可能破坏结果的反例。按交互合同核对对象生命周期、设备分工、主路径、成功、失败恢复、中途退出和再次打开；根据真实范围选择首次空白、典型数据、无结果、校验错误、保存失败、重复操作、超长内容、权限或离线等状态。中国本地化按实际受众核对中文输入法组合态、日期时间、数字金额、地址电话、触屏和弱网等适用条件；不为无关小工具伪造登录、网络错误或本地渠道。

行为记录需包含实际输入、操作、观察和结果。命令退出 0、截图存在和阅读代码都不能代替操作。

### 视觉

用 `site-design` 的只读视觉审查分支，按相近页面、内容、状态和视口对照已确认方向或参考。检查主任务、构图、中文排版、控件状态、真实内容和响应式。主要问题修复后重新渲染；没有溢出不等于视觉通过。

新建或整体重做不能只检查首页：至少实际渲染核心页面与最复杂的操作表面，并用 computed style 和操作状态核对以下内容；局部修改按受影响范围选择代表表面：

- 已确认视觉意图及共享变量是否真实进入成品，同角色组件在不同页面是否一致；
- 排版、空间、控件层级、图像裁剪与图标规格是否跨页面继承；
- 适用的默认、悬停、按下、焦点、禁用、加载、成功和错误状态是否完整且可辨认；
- 动效是否使用一致的快/常规/慢节奏并服务状态变化，`prefers-reduced-motion` 下是否减弱非必要运动而不丢失反馈。

原创设计按选定方向和实际质量判断，不要求精确像素或色值复刻。只有用户明确要求还原且参考条件可比时，才把几何、色值或截图差异作为硬性标准。

视觉轴要按 `site-design` 的 [设计质量](../../site-design/references/design-quality.md) 四条判据核对，并对**实际渲染**执行断言，而不是只做静态阅读：

- **方向有来源**：核对项目已声明的母题是否真的兑现在成品里，以及换个产品名是否还成立；
- **字面成立**：读渲染后的 computed style 核对字号、行高、行长、中文标题字距与数字对齐，并按 [排版](../../site-design/references/typography.md) 检查标点、引号与中西文混排；
- **材料真实**：核对颜色采样来源与素材的出处、许可、裁剪和用途，以及缺口是否如实显示；
- **构图有重心**：缩小到 25% 是否仍有结构与重心，是否有一处服务内容的细节签名。

命令退出 0、`design.py validate` 通过、色对在 token 表里达标、截图存在，都不能单独构成视觉 `passed`。半透明叠层、图片上的文字与动态状态不在自动断言范围内，必须人工查看并说明。

### 再次打开

使用交付给创作者的真实入口重新启动或打开，确认：

- 入口仍指向正确项目；
- 使用说明与实际命令一致；
- 关键能力仍可完成；
- 声称持久化的数据重新打开后仍存在；
- 数据位置、备份方式和限制与说明一致。

## 2. 产出矩阵凭据

本档位适用的检查完成后，把本轮每一项写成机器可读矩阵并交给检查工具落盘：

```text
python3 /absolute/site-check/scripts/check.py matrix /absolute/PROJECT --input /absolute/matrix.json --profile targeted --save-evidence
```

`matrix.json` 的每项包含 `id`、`title`、`status`（`passed | failed | not_run | not_applicable`）、`blocking`（布尔）和 `evidence`。证据不是一句描述，而是说明它从哪里来：

```json
{"items": [
  {"id": "core-task", "title": "了解课程并复制微信号", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "桌面 1440x1000 实际操作并复制成功",
                "paths": ["evidence/desktop-1440.png", "evidence/clipboard-result.json"]}},
  {"id": "build", "title": "构建与静态引用", "status": "passed", "blocking": true,
   "evidence": {"kind": "command", "summary": "check.py run 退出 0", "commands": ["<command check_id>"]}},
  {"id": "copy-feedback", "title": "复制按钮的失败恢复", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "剪贴板被拒绝时的手动恢复截图",
                "paths": ["evidence/clipboard-denied.png"]}},
  {"id": "scope-no-payment", "title": "首版明确排除在线支付", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "桌面与手机的导航、课程页和咨询流程均未出现支付入口或支付承诺",
                "paths": ["evidence/scope-desktop.png", "evidence/scope-mobile.png"]}},
  {"id": "visual-inheritance", "title": "核心页与咨询弹窗继承选定视觉", "status": "passed", "blocking": true,
   "evidence": {"kind": "artifact", "summary": "1440px 核心页和弹窗的排版、间距、控件状态与动效节奏实测一致，减弱动效模式保留结果反馈",
                "paths": ["evidence/core-page.png", "evidence/contact-dialog-states.png", "evidence/reduced-motion.json"]}},
  {"id": "copy-tone", "title": "复制成功提示的措辞", "status": "passed", "blocking": false,
   "evidence": {"kind": "declared", "summary": "我认为提示语够清楚，但没有单独取证"}}
]}
```

四种证据类型：

| `kind` | 含义 | 能否支撑阻断项 |
| --- | --- | --- |
| `artifact` | 项目内的真实文件（截图、结果 JSON、日志、命令输出），工具记录 sha256 | 能 |
| `command` | 之前 `check.py run` 的 `check_id`，要求退出码 0 且源码未变 | 能 |
| `observation` | 无法归档的操作观察，例如手工读取剪贴板 | 不能，只能非阻断项 |
| `declared` | 只是声明；纯文字 `evidence` 字符串按此处理 | 不能，只能非阻断项 |

写不出可归档证据时，正确做法是把该项标成 `not_run` 并写明恢复条件，而不是写一句 `passed`。把阻断项写成 `observation` 或 `declared` 会被工具直接拒绝——这是"无证据就是 `not_run`"的机械版本。

`--save-evidence` 会把引用到的证据复制到 `.site/checks/evidence/`，归档副本才是交付时核对的依据：复验时重新渲染的截图只覆盖工作文件，不会让已提交的证据失效；但归档副本或未归档的证据文件被改写，交付就会失败。

工具在检查前后重算源码指纹：指纹变化、任一阻断项不是 `passed`、或阻断项的 `artifact`/`command` 证据验证不通过时整体 `status=failed`，并列出 `blocking_not_passed` 与 `evidence_failures`。成功时返回 `check_id`，凭据落在 `.site/checks/<check_id>.json`。报告回执必须带上这个 `check_id`；`site-builder` 只能用它换取 `delivered`，源码一变凭据自动失效。

工具能验证证据文件存在、位于项目内、未被改写、且命令证据确实退出 0，但它**无法验证一张截图是否真的证明了所写结论**。手写一份矩阵 JSON 冒充凭据会在交付时被拒绝；把无关文件当作证据仍然要靠检查者的判断，所以"这一条证据真的支持这个结论"依旧是本 Skill 的责任。

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
