# 实施进度

## 第一批 P0

基线：`e01eff8cff30e4cfdaac3dafcd6130edfb1c32be`。
第一批实现：`1b28177306142698c59c38ea40769b6ddd7f0afc`。
分支：`agent/devstaff-p0-hardening-20260919`。草稿 PR：#1，目标 dev-up，未合并。

已实现：项目模式作为报告要求的权威、报告字段严格类型、not_run 聚合修复、验证轮版本核对、状态版本检查、公共协议随安装持久保存、升级异常回滚与安装路径保护。详见 P0-HARDENING.md。

本次会话本地实际执行的定向套件：30 项交付回归 + 14 项安装回归 + 36 项协议测试通过。全仓结果必须以 CI 为准。

## T00：完整集成验证

首次 PR CI：run `35452734564`，源码 `1b28177306142698c59c38ea40769b6ddd7f0afc`，Python 3.10 与 3.12 的 workflow tests 均失败；后续阶段未执行，不能称全仓通过。

Python 3.12 日志显示运行 150 项测试、2 项失败：

- test_cli.StateCliTests.test_verify_rejects_a_stale_report
- test_state.VerifyReportTests.test_verification_round_rejects_a_report_for_an_earlier_tree

两项都要求错误消息保留 `fresh report`，新门禁提前拒绝变动的验证轮，但恢复提示没有这几个字。修复仅补齐说明：取消旧轮、重新 handoff、开启新轮并写 fresh report；保留原测试和拒绝行为，不通过删除断言绕过。

本文件所在提交包含该提示修复。其 CI 结果需随后核对并记录；未获得成功结果前 T00 保持待验收。正式发布还需要本计划明确要求的安装来源删除验证及实际用户/浏览器路径，CI 脚本通过不能替代这些。

## 未开始的任务

T01 至 T14 依赖与验收见 AGENT-IMPLEMENTATION-PLAN.md。不要把这份进度记录中的“计划”当成运行能力，也不要重复实现已经落地的 P0。
