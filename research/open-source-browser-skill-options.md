# 开源浏览器 Skill 补位调研

日期：2026-09-16  
目标：寻找可补齐 `site-check` 浏览器实测能力的开源 Agent Skill/CLI，重点覆盖核心任务、桌面/手机视觉、再次打开、证据产物和进程回收。

## 结论

有可直接利用的成熟开源底座，不建议本项目继续自造 Chrome 进程管道。首选是微软官方 [`microsoft/playwright-cli`](https://github.com/microsoft/playwright-cli)，备选是 [`vercel-labs/agent-browser`](https://github.com/vercel-labs/agent-browser)。

但没有一个外部 Skill 能单独解决本项目全部问题。它们解决“怎样可靠操作浏览器”，不理解本项目的 `full` 五轴、页面设计合同、Writer/Checker 冻结、证据哈希和 `check_id`。本项目仍需保留一层很薄的适配协议，把外部浏览器产生的截图和 JSON 结果转换为 `site-check` 可接受的 artifact。

推荐架构：

```text
site-check（决定测什么、是否通过、如何归档）
    ↓ browser capability adapter（探测、会话命名、产物路径、清理）
Microsoft Playwright CLI（负责真实浏览器执行）
    ↓
截图 / DOM与JS结果 / console / trace / reopen结果
```

## 候选比较

| 候选 | 适配度 | 优点 | 主要代价 | 建议 |
| --- | --- | --- | --- | --- |
| [Microsoft Playwright CLI](https://github.com/microsoft/playwright-cli) | 高 | 官方 Agent Skill；支持截图、JS `eval`、移动设备、持久 profile、命名 session、console/network/trace 和显式 close；Apache-2.0 | 需要 Node/npm 和浏览器安装；原始产物仍需转换成本站矩阵 | **首选底座** |
| [Vercel agent-browser](https://github.com/vercel-labs/agent-browser) | 高 | Agent 优先的紧凑 CLI；支持 screenshot、eval、viewport、session、网络、HAR、a11y、diff、doctor；Apache-2.0 | 能力面和守护进程更复杂，项目会承担更多升级与兼容面 | 高级备选，不作为默认依赖 |
| [lackeyjb/playwright-skill](https://github.com/lackeyjb/playwright-skill) | 中 | 标准 Agent Skill；可写完整 Playwright 程序，适合循环、断言、多 context、网络拦截、视频；MIT | 会让 Agent 为每个项目生成脚本，正好可能重现当前重复造轮子的成本 | 只用于超出 CLI 的复杂场景 |
| [fugazi/test-automation-skills-agents](https://github.com/fugazi/test-automation-skills-agents) | 中低 | 有测试计划、E2E、回归、a11y 和调查方法；MIT | 官方说明它主要是文档/知识库，不提供自身运行系统；范围远大于本站首版交付 | 借鉴流程，不作为执行底座 |
| [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp) | 中 | 持久浏览器状态和丰富交互；Apache-2.0 | MCP 强依赖宿主配置，工具 schema/context 开销更大，不符合四 Skill 跨宿主、低安装认知的目标 | 作为宿主已有能力时的可选 provider |

## 为什么首选 Playwright CLI

官方仓库把 CLI 明确定位给 coding agents，并自带可安装 Skill：

```text
npm install -g @playwright/cli@latest
playwright-cli install --skills
```

它覆盖当前缺口：

- 核心任务：`open`、`click`、`fill`、键盘操作、snapshot 与等待；
- 桌面/手机视觉：`screenshot`、`open --mobile`、`open --device="iPhone 15"`；
- 运行时断言：`eval`，可输出 DOM、computed style 或应用状态 JSON；
- 再次打开：`--persistent` 或 `--profile` 保存浏览器数据，显式 `close` 后重开；
- 调试证据：console、network、trace、截图；
- 生命周期：命名 session、`close`、`list`，headless session 有 idle timeout。

这比直接调用 Chrome `--dump-dom`/`--screenshot` 更接近本项目所需抽象，也把浏览器退出、等待和协议细节交给上游维护。

截至调研时 GitHub API 显示该仓库未归档、Apache-2.0、近期仍有提交；仓库约 13.3k stars。活跃度只能作为维护信号，不构成功能保证。

## 不能直接“安装一个 Skill 就结束”的原因

外部工具不知道以下本站语义：

1. 哪些 `IC-* / PG-* / SC-* / RP-* / VA-*` 必须映射进本轮矩阵；
2. 哪个行为属于核心任务，哪个是高价值反例；
3. Writer 已退出、源码已冻结，Checker 必须只读；
4. 截图和 JSON 应保存到哪个项目内路径并由 `check.py` 计算哈希；
5. 什么条件下 `reopen` 才算真正从交付入口重开；
6. 浏览器不可用时应返回 `incomplete/not_run`，而不是伪造通过。

因此边界应当是：外部 Skill/CLI 提供浏览器能力，`site-check` 继续拥有验收语义。

## 最小集成方案

不把 Playwright 源码复制进仓库，也不在 Checker 阶段临时安装依赖。增加一个薄适配层，例如 `site-check/scripts/browser_capability.py`：

1. `probe`：检测 `playwright-cli` 是否可执行、版本、浏览器是否已安装；只读探测，不自动安装。
2. `run`：以项目 ID + check ID 创建唯一 session，固定 evidence 目录和超时。
3. `desktop` / `mobile`：使用明确设备/视口，生成 PNG 与包含 URL、viewport、关键断言的 JSON。
4. `reopen`：关闭指定 session，再从真实交付入口启动；需要持久化时使用项目隔离 profile。
5. `cleanup`：只关闭本轮命名 session，记录 PID/session/结束状态，不使用全局 `kill-all`。
6. `manifest`：输出统一 evidence manifest，交给现有 `check.py matrix` 哈希归档。

适配层不要暴露通用 `open_page()` 句柄。句柄会把具体 Playwright API 泄漏回每个项目，继续诱发自写脚本。更合适的是稳定的命令/结果协议，让 Agent 根据矩阵步骤调用底座，同时强制统一产物和清理。

## 与项目定位的冲突及处理

项目面向非技术用户，并承诺由 Agent 处理依赖和验证；但 `REQUIREMENTS.md` 同时把安装浏览器、Node.js 等列为系统级高风险动作。因此不能在交付末尾发现缺浏览器后静默安装。

建议把浏览器能力提升为安装期或 60 秒预检中的显式能力：

- 整套安装时声明“完整建站验收需要一个受支持的 browser provider”；
- 运行前 `probe`，缺失就尽早说明完整交付能力不可用；
- 宿主已提供可靠浏览器能力时允许 provider 适配，不重复安装；
- 没有 provider 时，新建/重大改版不能进入声称可完整交付的路径；可以完成草稿或实现，但结论保持 incomplete；
- 固定测试过的 CLI 版本范围，升级通过本仓库回归后再放行，而不是永远追 `latest`。

这能避免最差体验：实现完成后才发现 `full` 永远无法通过。

## 仍需本项目补的质量约束

引入 Playwright CLI 只能解决“能跑”，不能解决“测得够不够”。还应在本站矩阵 schema 中补两项：

- `full` 的 `core_task` 至少包含一个正向任务和一个适用的失败恢复/边界反例，或带理由的 `not_applicable`；
- 浏览器 evidence manifest 必须记录实际 URL、viewport/device、步骤、观察结果、产物路径、provider 版本和 session 清理结果。

否则仍可能出现“截图和五个轴都存在，但两个 P0 数据丢失问题完全没测”的情况。

## 最终建议

采用 Microsoft Playwright CLI 作为默认受支持 browser provider，但不要把它变成第五个业务 Skill，也不要让 `site-check` 依赖一个不可控的全局 Skill 路由。项目内新增薄适配层和能力协议；安装/预检阶段负责确认 provider；`site-check` 只负责生成测试步骤、调用 provider、归档证据和判定。

`agent-browser` 可以作为未来第二 provider。先支持一个官方、稳定、覆盖足够的底座，更符合本项目“小而完整、面向非技术用户”的定位。

## 一手来源

- [Microsoft Playwright CLI repository](https://github.com/microsoft/playwright-cli)
- [Microsoft Playwright CLI Skill](https://github.com/microsoft/playwright-cli/blob/main/skills/playwright-cli/SKILL.md)
- [Vercel agent-browser repository](https://github.com/vercel-labs/agent-browser)
- [Vercel agent-browser Skill](https://github.com/vercel-labs/agent-browser/blob/main/skills/agent-browser/SKILL.md)
- [lackeyjb/playwright-skill](https://github.com/lackeyjb/playwright-skill)
- [fugazi/test-automation-skills-agents](https://github.com/fugazi/test-automation-skills-agents)
- [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp)
- GitHub repository API metadata，读取于 2026-09-16。
