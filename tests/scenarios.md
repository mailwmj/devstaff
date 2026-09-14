# 协作与质量回放

本项目有两种闭环，不能混称：

- **用户运行时闭环**：任务合同 → 方向 → 语义选择 → 模板适配 → 正式生成 → 浏览器真实渲染 → 核心任务/状态/再次打开 → 修复后交付。它自动发生，不增加用户可见模式。
- **维护者发布闭环**：锁定 `F-*` → 运行固定 SD/MV 与 UC/RC → 两名真人独立评分 → 比较质量、token 和耗时 → 决定发布。它不在普通生成中运行。

## 回放顺序

1. `python3 tests/evaluate.py validate-catalog` 检查场景、夹具和锁。
2. 从所需 `F-*` 复制隔离副本，记录四个 Skill manifest 版本与哈希，并把模型和关键工具条件写入 `environment`。
3. 用固定输入开始同一条持续用户会话；用户只说自然语言，不提示内部流程。
4. 保存 `select.mjs` 选择/拒绝、`DesignPacket`、正式输出、`check-render.mjs` JSON 与截图。
5. 两名真人独立完成五维评分；任何未执行项写入 `not_run`。
6. 用 `evaluate.py validate-run --full` 区分单条记录是否证据完整、是否达到发布门槛；再用 `compare` 机器核对完整 25 场景集合。

## Token 对比

每个相同固定输入记录实际 `input_tokens`、`output_tokens` 与 `duration_ms`。`fixed_input_sha256` 必须匹配场景目录，`environment.model` 与 `environment.tools` 记录可复现条件。比较器会拒绝场景缺失、重复、输入变化或环境不一致：

```sh
python3 tests/evaluate.py compare before.json after.json --target 0.30
```

通过要求是中位输入 token 至少降低 30%，中位质量分不下降且不新增否决项。静态文件字节数只能作为上下文预算代理，不能冒充真实模型 token；未取得宿主 token 计数时如实记为 `not_run`。
