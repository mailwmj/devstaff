# Devstaff 可直接执行的 Agent 改造计划

## 0. 任务、边界与现状

目标：让不懂代码和视觉设计的白领、老师、销售，通过少量关键决定得到能打开、能使用、能继续修改的网站。每项改动必须降低实际失败概率或用户负担，不能只增加规范数量。

仓库：`mailwmj/devstaff`。分发根：`release/`。审查基线：`e01eff8cff30e4cfdaac3dafcd6130edfb1c32be`。第一批补丁分支：`agent/devstaff-p0-hardening-20260919`，目标分支 `dev-up`。

先读取 [P0 变更说明](P0-HARDENING.md)。该分支已实现部分交付门禁和安装修复；本文件 T01 至 T14 是待实施任务，不得把计划内容当成已实现能力。接手时以 GitHub 实际提交、diff 和测试结果核对，不盲目覆盖更新后的 dev-up。

不重新选产品方向，不继续写一份泛泛分析。按下面顺序改代码、补测试、同步文档。不要把所有任务塞进一个无法审查的大提交。

### 不可改变的约束

- 保留 site-builder / site-brief / site-design / site-check 四个 Skill；builder 是唯一编排者。不要新增一串角色掩盖接口问题。
- release 必须独立打包运行；不得依赖仓库根 tests/docs 才能运行。开发测试可以留在根目录。
- 保留并按需加载现有设计知识库，不通过删除专业能力换取短提示词。
- 不修改用户已有工作树，不强推 dev-up，不合并 PR，不正式发布，不创建付费资源，不使用真实敏感数据做测试。
- 不删除失败测试来制造全绿；旧测试与批准的新行为冲突时，保留测试目的并明确更新断言。
- 指纹证明版本身份，不证明产品正确；JSON 字段合法不证明用户授权或独立检查真实。
- 没有浏览器、发布凭据或指定宿主时，用隔离 fixture 验证适配层并说明未验证范围，不伪造真实执行。

## 1. 执行顺序与交付粒度

| 批次 | 任务 | 主要结果 | 前置 |
| --- | --- | --- | --- |
| A | T00 | 集成已有 P0，获得完整基线 | 当前分支 |
| B | T01、T02 | 状态与命令接口可执行、不自相矛盾 | A |
| C | T03、T04 | 局部修改不重来，用户只做必要决定 | B |
| D | T05、T06 | 预览可达，事实源与交接稳定 | B；T06 可与 C 并行 |
| E | T07、T08 | 指纹/验证更可靠，视觉规则不过度约束 | A；相关接口沿用 B |
| F | T09、T10、T11 | 受测工程起点、真实执行证据、数据可靠性 | D、E |
| G | T12、T13、T14 | 可持续交付、Agent 实测、可发布归档 | C 至 F |

先完成一批再报告这一批的提交、测试和限制；当前工作会话有能力继续时直接进入下一批，不要求用户逐项批准技术细节。需要付费、公开发布或操作真实数据时才停。不同 Agent 可并行做 T06/T08，但共享脚本同一时间只由一个 Agent 改。

每个任务使用固定完成记录：任务 ID、基线 SHA、变更文件、失败复现、实现摘要、实际测试命令/退出码、结果文件、已知限制、提交 SHA。记录到 `docs/implementation-progress.md`，不是产品状态目录 `.site`。把通过与未运行分开写。

## T00：集成现有 P0，先获得可信基线

状态：代码已部分实现；全仓集成验收待执行。

范围：本分支的 check.py、state.py、install.py、新增回归测试，以及原有协议/安装测试的变更。不要先重构设计系统。

步骤：读取分支 diff，确认它只包含本次工作；运行第 3 节全部测试；记录环境和 SHA。若有失败，先判断是新缺陷还是旧用例刻意允许了不安全行为，修复到保留正常路径。核对 strict 报告缺 risk/reopen 被拒、字符串 false 被拒、not_run 不被 limited 掩盖、检查中变更版本被拒、安装源删除后公共协议仍在。

特别检查：报告文件在 validate-report 与 _load_check_report 两次读取之间变化的竞态仍需 T07 处理；当前指纹二次比较不等于完整事务。未知状态版本拒绝但旧版合法状态仍应支持。

产物：当前提交全仓测试记录、P0 独立 diff、更新后的进度记录。验收：正常 guided/strict 交付仍可运行，新增负例拒绝，完整 CI 未被跳过。未完成这一步不得把当前分支标为正式发行版。

## T01：统一状态转移与前置条件

改动：`release/site-builder/scripts/state.py`、其随包测试、`tests/test_state.py`、`tests/test_cli.py`。

先写回归：discovering 的允许动作包含 discover；choice 未选择时允许 select-structure、不允许 decide；choice 少于两个不同候选被拒；选择不存在候选被拒；已选结构的用户在下一阶段再次回复同样的“好”应合法；非法转移不修改 state.json；状态文件损坏时输出结构化错误。

实现：用一份小型动作/前置条件定义驱动 preflight 与命令执行，避免文案允许但函数不拦。不要引入工作流框架。结构模式未评估的新 revision 应要求先评估；旧 revision 的既有 init→decide 流程通过显式兼容路径迁移，不能直接让所有旧项目失败。确认对象记录类型、目标版本、原话；宿主提供 message id 时引用，没有时不编造。删除“两个原话必须不同”的假真实性判断。

保留：主阶段名字及正常命令尽量兼容。新增状态字段必须有默认值与迁移测试。统一 .site 大小写/旧 .v3 定位行为，多状态文件报冲突，不能一个脚本选 A、另一个选 B。

验收：对所有公开状态命令生成转移表测试，允许动作与成功/拒绝结果一致；旧 fixture 可迁移，未知版本拒绝。文档和脚本同一提交更新。

## T02：稳定 Agent 命令接口与职责边界

改动：四份 `release/site-*/SKILL.md`、`release/AGENTS.md`、state/check 的 CLI 输出、相关测试。

实现：保留 next_action 字符串以兼容，在旁边增加小型 action 对象：id、owner、inputs、outputs、preconditions、recovery、needs_user。不要把整个历史和所有规范塞进去。错误增加稳定 code 与可执行 recovery，保留人读 message；stdout 只写 JSON，诊断走 stderr。

职责：brief/design/check 只回五字段回执；发现信息缺口返回给 builder，不直接调用下一个 Skill。把依赖资源与 Agent 调用链分开。当前任务只列所需 references，避免每轮重读全部文档。

测试：缺合同、旧报告、缺同级 checker、未知命令、损坏状态均给出可解析错误；状态恢复后只读摘要和未完成项就能续做。对源码/文档引用做轻量完整性检查，不用关键词数量冒充协议一致性。

验收：接手 Agent 无需猜安装路径、下一动作或错误后重做范围；没有新增用户能看到的协议术语。

## T03：建立保留已确认决定的局部修订路径

改动：state.py、builder SKILL、AGENTS、项目 journal 规则及测试。

新增明确的 revise 入口，输入 change_kind 为 local、feature、scope，并带 reason。local 保留任务、结构、视觉决定，开启新实现修订；feature 仅补充受影响范围；scope 才退回需求或方向。保留历史，不直接擦掉旧 decision。

已有 .site 的项目即使只是改颜色，也先记录修订并使旧交付证据失效；不创建状态的 quick 只用于未管理项目。不要通过手改 state.json、删除 .site 或复用旧指纹绕过。

必须测试：交付后改按钮文案不触发需求问答/结构双选；新增一页不重做已定设计；新增权限必须升级对应风险；修订后旧报告被拒；未受影响决定保留；中途退出后可恢复。不能只按文件后缀认定影响范围：CSS 也能藏掉核心操作。

验收：同一项目连续三次局部修改，任务与方向不重复确认，最终源码和新报告匹配；重要范围变化仍会停在正确决定上。

## T04：减少无价值确认，分离产品接受与执行授权

改动：AGENTS、brief/builder/design SKILL、prototype.md、state.py 相应子阶段/迁移及流程测试。

默认给一个明确推荐方案。只有确有结构或视觉分歧时才给两版。已有参考直接使用；用户无想法可按推荐推进，缺少高风险决定不能代替用户拍板。参考是否存在不需要机械另问一轮，已给的信息不得重问。

把产品方向确认、版本体验反馈、外部副作用授权分开。基础静态检查和隔离测试自动执行；纯缺陷修复后自动重测，不再为“能不能测”重复索要一句话。必须为当前版本创建新验证轮，不借用旧源码指纹。用户对功能方向的接受可保留，但对某个视觉版本的接受不能被表述成对后来所有版本的接受。

公开访问、付款、真实通知、敏感数据写入、权限变化仍需要具体授权；“都按推荐”不是无限外部操作许可。旧 handoff/begin-check 的行为调整要有 schema 迁移，不能单改文档而代码继续要求旧停点。

验收案例：从一句想法到首版可见结果没有“要不要开始/继续/测试”的机械停顿；用户可说“按推荐”；修复测试缺陷不会要求重选布局；真正发布前会说明对象与访问范围并等待授权。把固定“六次”改成有条件的决定点，不用固定轮数作为成功指标。

## T05：安装后自检与用户可达预览

改动：`release/install.py`、新增 `release/site-builder/scripts/doctor.py`、builder 的运行参考、prototype.md、安装与预览适配测试。

doctor 检查 Python 版本、同级技能和公共协议、项目读写、必要运行时、浏览器/预览能力，返回 available/unavailable/unknown 及恢复办法。只检测，不擅自安装系统软件、改全局配置或收集凭据。

预览按宿主内嵌、受控可访问 URL、可打开独立文件、截图降级选择。记录用户访问范围和 artifact 版本。Agent 能访问 localhost 不代表用户能访问；open/xdg-open 命令成功不代表远端用户看到了页面。截图只证明可看，不证明交互可体验。缺少能力时给明确降级，不反复重试无法打开的路径。

安装时只整合受管理的引用块或明确协议路径，不覆盖用户指令。先实现一个实测宿主适配和 generic fallback，不宣称支持所有客户端。公网预览仍需授权，默认使用假数据。

验收：删除安装来源后 doctor 仍通过必要本地项；没有浏览器能诚实降级；有浏览器的 fixture 可打开并切换；用户访问与 Agent 访问记录不同；不能在未授权时调用外部发布动作。

## T06：减少事实重复，建立小型合同规范

改动：surface-brief.md、design.py/check.py 的合同读取、相关测试；必要时新增 release 内共享 schema/读取模块。

先列出机器真正要用的字段：任务/范围、页面与核心行为、数据/风险边界、已确认决定、验收对象、资产引用、版本。推导理由继续写 Markdown。只选择一个权威存储，别再增加一份与正文并列手工维护的大 JSON。

先实现统一 parse/validate API 与 fixtures，再迁移现有 JSON 围栏/中文表格读取。迁移必须保留原内容备份、稳定 ID 和外部引用；支持旧合同读取，未知 schema 拒绝。新旧表现等价的 fixture 生成同样检查目标，不要求原始字节指纹跨格式相同；迁移本身产生新版本并使旧报告失效。

验收：调整 Markdown 标题/说明不把验收对象静默漏掉；引用不存在 ID、重复 ID、非法状态报错；简单页面只需适用字段；不把审美解释“有一个引用”当成设计已经成立。若现有格式可通过小型解析修复达到目标，不强制全量换格式。

## T07：验证事务、扫描边界与 CLI 退出码

改动：check.py、state.py、源清单测试、CLI 测试，必要时共享读写模块。

报告应一次读取成不可变对象再校验与入状态，或验证前后校验同一报告字节哈希；避免先验证报告 A 再读取被替换的报告 B。验证使用源快照或绑定明确的 immutable worktree；无法做到就保留诚实的并发边界，至少检测模式、合同、源码与报告读取的变化。不要声称靠多算一次哈希就消除了所有 TOCTOU。

源码扫描改为可剪枝遍历，确认不进入依赖/构建目录；指纹规则与 Git 历史比较一致。提供可审核的项目 include/exclude 覆盖：随包只读数据库、迁移和种子数据可纳入，运行数据库排除。规则自身也绑定身份。忽略项不能由普通产品输入随意扩大。符号链接不越过根目录读文件，无法读取报错，不能静默忽略产品源码。大型 manifest 单独保存可定位 artifact，摘要不把逐文件结果塞满上下文。

退出码约定：plan 成功 0；validate-report 协议有效 0、协议无效 1；执行/输入错误 2。产品 blocked 但协议有效与非法报告是两件事，JSON 里保留 overall，调用方必须同时读协议和产品结论。同步 subprocess 调用和原有 check=True 测试，不偷偷破坏调用者。

验收：报告在两次读取间被替换的测试不能交付；state 模式在验证中改变不能降级；忽略目录的读取计数为零；只读产品数据库变动使指纹变动；运行数据库变动不影响源码；未知状态/扫描错误 fail closed；CLI 的三种退出码都有测试。

## T08：统一视觉比较规则，取消不可靠审美门禁

改动：site-design/SKILL.md、references/prototype.md、visual-direction.md、surface-brief.md、craft-review.md、design.py 与 test_design.py。

增加明确 comparison_type：structure / style / interaction。structure 固定内容和基本视觉语言，比较组织与流程；style 固定任务、内容和信息架构，允许字阶/节奏/色彩角色/材质变化，共用 DOM 合法；interaction 固定业务结果，比较操作与反馈。不再强制风格候选必须改变布局或有一版暗色，不要求所有项目都出两版。

硬阻断只负责真实可用性/结构错误；设计建议允许项目依据例外；阴影、纯黑白、圆角比例、按压缩放、破折号等具体表达进入配方层。工具型产品优先易用一致，营销型产品强调内容和辨识度。保留专业知识，不把“反默认”变成强迫偏离成熟模式。

删掉从自由文本含“换肤”推断失败的硬判断，测试“不是换肤”“差异不成立”等否定句。不要从星号字符本身断定社会证明造假；需要来源核对。基于实际截图评审层级、密度与构图，自动静态扫描只提供它确实能判断的结果。

验收：同骨架的两种有效视觉表达可通过；真正无差异方案在渲染评审被指出而不是靠改文案通关；局部修复不跑完整风格推导；工具页面不为通过规则添加装饰；现有合理 reference/Token 仍可使用。

## T09：建立最少但受测的工程起点

改动：新增 `release/site-builder/assets/starters/`、脚手架脚本/说明、builder 分支规则、独立 starter 测试。

先做一个基础 Web 工程，再根据能力配置扩展，避免三套无关技术栈。已有项目优先继承。新项目由 Agent 选已验证默认栈，不向非技术用户提框架选择题；锁定实际验证的依赖版本，记录升级办法，不在计划里凭空宣称某版本最新。

按顺序交付：内容展示站；带持久化和导出的小型个人工具；最后是有真实后端/授权的共享应用。第三类只有隔离权限用例通过后才开放，不能用 localStorage 或隐藏按钮模拟多人安全。

每个起点带启动/构建/类型检查/测试命令、错误与空状态、内容入口和 README。构建产物不能混进 release。Demo 继承 Token、布局与内容，不把硬编码成功和临时事件作为生产逻辑。

验收：在空目录只用 release 可生成、启动、构建；一条真实任务完成并刷新保留；再次生成不覆盖用户修改；缺依赖可恢复；简单项目没有无用账号、队列、权限体系。组件行数仅提示，优先单一职责和独立可测试业务规则。

## T10：提供真实检查执行器与证据采集

改动：`release/site-check/` 内执行适配、探针模板、运行规范及 fixture；与现有 plan/validate-report 连接。

先实现已选 Web 起点的一套执行器，不承诺任意栈全自动。探针覆盖启动、路由、核心任务、主要失败输入、控制台错误、保存刷新、窄屏、关键权限反例。零对象命中必须在探针中失败。等待可观察条件而不是固定 sleep。

划分权限：源码只读；隔离测试数据允许写；真实生产数据默认不写。任何真实发送/收费/删除都需要授权，不因为名字叫 check 就免授权。

证据保存执行命令、退出码、环境/构建标识、截图/trace 路径、检查对象与结果。宿主独立上下文不可用时不填写 independent:true。稳定探针的测量可由 runner 输出；手写 observed 仍是说明，不冒充测量。

验收：故意把选择器改成不存在会失败；后端返回错误不能显示已保存；仅截图不使 core_task 通过；缺浏览器返回未运行而非成功；测试结束不留下真实副作用；失败证据可定位同一版本。

## T11：数据可靠性与后续内容维护

改动：个人工具/共享应用起点、数据适配、领域逻辑测试、brief 的数据边界提问。

持久化必须说明关闭、刷新、换设备、清缓存后的行为。导入提供字段映射、错误预览、去重策略，失败不能半写无提示；导出字段稳定并可恢复。金额、数量、日期计算放到独立纯函数测试，不能在多处 UI 各算一次。重复提交做适合业务的幂等控制。共享权限必须在数据访问层执行。

内容维护采用最轻方案：低频内容集中配置，高频内容才加管理入口；不能每个展示站都引入 CMS。用户说修改课程/报价/联系方式时应有明确入口。测试用合成资料，不使用真实学生或客户信息。

验收：导出再导入可恢复关键记录；错误行不污染数据；跨账号直接请求越权对象被拒；刷新保存存在；离线/失败不会假成功；后续改一个内容值不触发整站重新生成。

## T12：区分交付范围与风险，补齐发布和恢复

改动：项目风险记录、state/check 交付规则、builder 发布参考、运行与 handoff 文档。

交付范围：preview / personal / shared / public。风险另记敏感数据、资金、权限、外部写入和不可逆操作。public 永远需要发布授权，但静态展示页不机械继承资金系统全部测试；内部共享应用也不能因为不公开而免权限检查。

先定义交付语义，再迁移旧 delivered/limited。核心任务未验证只能交为 preview 或明确不可用成果，不能以 limited 说“可以放心用”。非关键设备覆盖不足才允许带具体限制的可用交付。

发布前核对访问范围、费用、资源归属、环境变量、备份/回退版本；发布后检查真实入口和核心任务。没有凭据时用 mock provider 测试计划，不执行真实发布。交付说明给出再次打开、内容修改、数据导出、恢复办法、费用及限制。

验收：部署命令成功但入口失败不算交付；未授权不能公开；内部系统执行权限反例；回退 fixture 可恢复上一版本；用户能找到如何再打开和如何改内容。

## T13：建立真实 Agent 评测，不只测试脚本

改动：新增 `evals/`，固定案例输入、成功断言、合成数据、执行记录 schema 与人工评分说明。

先固定六条任务：白领表格台账；老师课程/报名工具；销售展示/报价；交付后改一个按钮和一处规则；新会话恢复旧项目；缺浏览器或依赖时恢复。每条包含模糊首问、后续回答、范围禁止项、核心成功路径、一个失败反例和后续小修改。

记录首次用户可见产物、阻塞用户的有效/无效问题、任务完成、局部修改保真、恢复是否重问、越权/虚假交付、运行成本。先跑基线，再比较候选，不凭空设“提升 50%”。脚本单测和实际 Agent 运行结果分开。

验收：同一输入可重跑，失败能定位回放；至少有一次真实 Agent+浏览器执行，不把模拟用户对话当成用户研究；展示前后核心路径结果和盲评视觉发现；关键权限/虚假交付出现一次就不能称该案例通过。

## T14：整包发行验收与兼容性

改动：verify.yml、安装测试、VERSION/skills.json、变更日志和各宿主适配说明。

从实际 Git 提交导出 release 干净归档，安装到新目录，删除来源归档，再跑包内必要测试、doctor 和参考项目。把关键交付回归的最小集带进 release，而不是让安装后的验证依赖仓库根 tests。不把完整 eval 历史与开发文档塞进分发包。

运行既有 Python 3.10/3.12 CI；新声明支持的操作系统需对应测试，不凭 Linux 通过宣称全部客户端兼容。检查协议路径、非 ASCII/空格目录、升级普通异常回滚、崩溃恢复说明和旧状态迁移。

依赖和各类 schema 分开版本化；版本号只在内容与测试确认后同步，不为“升级”改名。最终只创建待审查发行 PR，不自动合并或上传正式发布。

验收：干净归档独立工作，旧项目可续做，用户原文件不被覆盖，四技能版本一致，所有已声明兼容项有执行记录。详细列出剩余不支持能力。

## 2. 每个任务的停止条件

完成实现和指定测试后才能标 completed。工具不可用标 blocked_tool，依赖任务未完成标 blocked_dependency，真实风险需要授权标 needs_authorization。不要因任务大就只写 TODO；完成当前可验证的小切片并留下可继续的提交。不要为通过门禁篡改报告、复用旧指纹或降低项目风险模式。

遇到与本计划冲突的已有用户改动，保留用户改动，在进度中说明冲突并选择最小兼容实现；只有实质性产品取舍无法从现有材料判断时才问维护者。对技术细节自行做有依据的决定并记录。

## 3. 运行命令

从完整仓库根目录执行，先确认工作区干净并记录提交：

```bash
git status --short
git rev-parse HEAD
python3 --version
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s release/site-design/scripts/tests -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s release/site-builder/scripts/tests -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s release/site-check/scripts/tests -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 release/site-design/scripts/design.py validate
```

测试命令逐条执行并保存退出码，不用最后一个命令覆盖前面失败。更改退出码协议后相应更新调用测试。

验证真正将要发行的已提交 release，而不是未提交工作区：

```bash
set -eu
ARCHIVE_FILE="$(mktemp)"
RELEASE_DIR="$(mktemp -d)"
INSTALL_DIR="$(mktemp -d)"
git archive --format=tar HEAD:release --output="$ARCHIVE_FILE"
tar -xf "$ARCHIVE_FILE" -C "$RELEASE_DIR"
python3 "$RELEASE_DIR/install.py" "$INSTALL_DIR"
test -f "$INSTALL_DIR/site-builder/references/AGENTS.md"
# The source archive and extraction directory are deliberately removed.
rm -f "$ARCHIVE_FILE"
rm -rf "$RELEASE_DIR"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$INSTALL_DIR/site-builder/scripts/tests" -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$INSTALL_DIR/site-check/scripts/tests" -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$INSTALL_DIR/site-design/scripts/tests" -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python3 "$INSTALL_DIR/site-design/scripts/design.py" validate
```

上述删除只针对本命令新建的临时路径。不要改为用户工作目录。安装目录保留用于检查，结束后再自行清理临时目录。

## 4. 给接手 Agent 的执行指令

```text
继续改造 mailwmj/devstaff。先读取 docs/P0-HARDENING.md 和
 docs/AGENT-IMPLEMENTATION-PLAN.md，核对实际分支与提交。
已有补丁在 agent/devstaff-p0-hardening-20260919，目标为 dev-up。
不要重写分析报告；先执行 T00 全仓集成验证，再按批次实施。
每项先补回归测试，再改代码，同步协议文档，并记录真实命令、
退出码、结果与限制。保留四 Skill 架构与 release 独立分发。
不要删除设计知识库、跳过失败测试、覆盖用户修改、强推主分支、
自动合并或公开部署。局部任务完成后留下独立提交和可继续记录。
已做的 P0 不重复实现，未做的流程与视觉任务不宣称已经完成。
```
