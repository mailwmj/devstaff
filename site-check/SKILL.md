---
name: site-check
description: Use when independently checking a website or web app for build, core-task, rendered visual, mobile, state, distribution, or reopen behavior; it reports evidence and never fixes formal source.
---
# 网站独立检查

检查用户实际能否完成任务，不从代码意图、文件存在、截图或构建成功推断通过。此 Skill 始终只读；修复交回 `site-builder`。

## 执行

1. **锁定对象。** 读取正式入口、源码、brief/计划、`.site/design/packet.json`、分发合同和 prototype lineage。没有 `.site` 也可检查第三方项目，但不初始化或迁移它。
2. **建立矩阵。** 读 [验证规则](references/verification.md)，按后果与影响面选择 `smoke | targeted | full`。每项写成“前提 → 操作 → 可观察结果”，映射 DesignPacket 的 `required / excluded`、核心任务、失败恢复、状态、视口和 reopen。缺证据写 `not_run`。
3. **静态与构建。** 沿用项目原生命令；普通静态页可用 `scripts/check.py static`。命令成功只证明该命令。
4. **真实任务与渲染。** 在正式运行入口执行核心任务和高价值反例。调用 `site-design` 只读审查，并运行：

   ```sh
   node ../site-design/tools/check-render.mjs \
     --entry <URL或HTML> --contract <contract.json> --output <evidence-dir>
   ```

   真实渲染至少覆盖桌面和 390px，检查 linked CSS/computed style、字体/CJK、相邻对比、溢出、触控目标、图片、减弱动效，以及适用的焦点、悬停、禁用、错误和加载状态。构图、direction 可追溯和项目特异性由只读视觉审查判断。
5. **分发与再次打开。** 从约定接收者实际得到的文件、URL 或安装入口打开；需要离线时按真实前提断网；需要持久化时关闭并重开。回环开发地址不能证明可分享。
6. **保存证据。** 每项只保留能改变判定的最小 artifact/command 证据。开始生成矩阵后停止写入正式源码和证据；用 `check.py matrix` 生成绑定当前指纹的 `check_id`。阻断项不能只靠散文或截图名称。
7. **报告。** 按影响排序失败项，说明本轮档位、真实入口、已运行、`not_run` 与恢复条件。可脚本化结论给 `verify_command`；窄档修复可用 `reverify`，`full` 必须重新完整执行。

## 隔离

Writer 必须先停止自有服务并冻结；Checker 检查前后核对源码指纹。Checker 不编辑、格式化、安装会改写源码的依赖或替 Writer 修复。源码变化使本轮作废，必须重新 handoff。

## 回执

返回 `passed | failed | incomplete | blocked`、检查矩阵与 `check_id`、阻断发现、非阻断建议、真实入口和未执行项。给用户只说“能不能用、还差什么、下一步是什么”；档位、轴、指纹和矩阵保留给 builder 与文件。

没有浏览器、账号或必要环境时完成其余检查并诚实降级。完整维护者生成质量评测不属于本 Skill 的普通验收；它由根目录 `tests/evaluate.py` 和双真人协议负责。
