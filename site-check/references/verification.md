# 验证规则

验证对象是用户可观察结果，不是代码意图。输入优先使用 `.site/design/packet.json`，避免重新读取整套设计手册。

## 1. 档位与轴

按后果和影响面推导：

| consequence | surface | profile |
| --- | --- | --- |
| low | narrow / wide | `smoke` |
| high | narrow | `targeted` |
| high | wide | `full` |

`profile_reason` 必填，但不能推翻推导结果。`full` 至少有阻断轴：`static_build / core_task / visual_desktop / visual_mobile / reopen`；smoke/targeted 至少覆盖本轮受影响的阻断 `core_task`。分发要求分享、离线或原型交接时再增加 `share / offline / prototype_lineage`。

每项使用：

```json
{
  "id": "core-save",
  "axis": "core_task",
  "capability": "保存记录",
  "precondition": "存在一条有效输入",
  "action": "填写并点击保存",
  "expected": "列表出现记录并显示成功反馈",
  "observed": "实际观察",
  "status": "passed | failed | not_run | not_applicable",
  "blocking": true,
  "evidence": {"kind": "artifact | command", "summary": "...", "paths": [], "commands": []},
  "verify_command": ["可重复命令"]
}
```

矩阵映射 DesignPacket 的核心任务、`required/excluded`、采用或偏离的 recommended、已解决 confirm、成功/失败恢复/退出/reopen 以及 pattern adaptations。缺少映射不能静默省略。

## 2. 检查顺序

1. **静态/构建**：运行项目原生命令；静态项目可用 `check.py static`。审查是否存在境外不可达外链 CDN 与社交分享元标签。成功只证明命令。
2. **核心任务**：在真实入口完成前提、操作和结果，并运行一个高价值反例；多切片时强制复验历史已交付切片（回归不变量）。未经授权不提交外站表单或修改真实数据。
3. **真实渲染**：运行 `check-render.mjs`，桌面与 390px 都检查 linked CSS/computed style、字体/CJK、相邻对比、横向溢出、裁切、触控尺寸、图片和 reduced motion。
4. **状态**：按任务合同检查 focus、hover、disabled、error、loading；不适用的状态说明原因，不机械造状态。
5. **独立视觉判断**：核对 direction 证据、项目签名、构图重心、真实内容和 grammar 一致性。自动渲染通过不能代替这一项。
6. **再次打开**：从真实交付入口关闭并重开，核对运行方式、关键数据和限制。
7. **分发**：文件必须从约定渠道在接收设备打开；URL 必须非回环且接收者可达；离线按 downloaded/after-first-visit/installed 的真实前提断网。

`check-output.mjs` 只是 grammar 静态预检，不能作为 `visual_*` 的唯一证据。

## 3. Render Contract

`check-render.mjs --contract` 接受最小浏览器合同：

```json
{
  "core_task": {
    "name": "save a record",
    "steps": [
      {"action": "fill", "selector": "#title", "value": "记录"},
      {"action": "click", "selector": "#save"},
      {"assert": "text", "selector": "#status", "value": "已保存"}
    ]
  },
  "state_probes": [
    {"name": "save focus", "kind": "focus", "selector": "#save"},
    {"name": "error", "kind": "error", "selector": "#error", "expected": "visible"}
  ],
  "reopen": {"name": "record remains", "before": [], "after": []}
}
```

动作支持 `fill/click/check/uncheck/select/hover/press/reload`；断言支持 `visible/hidden/enabled/disabled/text/value/count/url`。选择器和期望来自真实任务，不为了让检查通过而修改。合同没有提供的核心任务或 reopen 必须保留 `not_run`。

## 4. 证据

证据类型：

- `artifact`：项目内截图、JSON、HTML 或日志；记录文件哈希；
- `command`：当前源码上退出 0 的 `check.py run` check_id；
- `observation`：无法归档的人工观察，只能支撑非阻断项；
- `declared`：陈述，不算可验证证据。

阻断 passed 只接受 artifact 或 command。每项最多 3 个文件、整轮最多 24 个；截图不是点击证据。每条状态必须回指具体证据，无证据写 `not_run`。

开始 `check.py matrix` 后停止新增、覆盖或整理证据。工具将证据哈希、源码指纹和规范化内容写入 `.site/checks/<check_id>.json`；内容寻址用于发现误改，不是签名，也不证明证据语义正确。

## 5. Writer / Checker 隔离

Writer 停止自有原型与开发服务，登记 PID/端口/根目录并 handoff 冻结。Checker 之后只读，不格式化、安装会改源码的依赖、重启 Writer 或修复。检查前后重新计算指纹；任何源码变化使本轮作废。

失败后 builder 引用当前失败矩阵 `reopen` 取回 Writer，修复后重新 handoff 和检查。旧 check_id 不能沿用到新源码。

## 6. 复验

第一次探明问题可以贵；回归应尽量执行已有断言。smoke/targeted 可以对未受影响项使用 `carried_from`，但每个必需轴至少一项本轮真实重跑，并在回执披露沿用项。`full` 不允许 carried 或 reverify，必须完整重跑。

可脚本化的 passed 项应提供 `verify_command`，使用：

```sh
python3 scripts/check.py reverify <project> <prior-check-id>
```

任何新自动探针先在一组应通过和一组应失败的控制页上验证敏感性。连续两次复验没有新证据时返回 blocked，不盲目重试。

## 7. 报告与交付

先列失败/否决，再列核心任务、状态/重开、视觉、非阻断建议和 `not_run`。只有当前源码指纹一致、必需轴齐全、所有阻断项 passed 才能交给 builder deliver。

给用户只讲：现在能否使用、如何打开、已检查什么、还差什么。完整维护者生成质量评测另由根目录 `tests/` 的固定场景和双真人协议负责，不能用普通验收矩阵冒充。
