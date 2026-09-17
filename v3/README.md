# 渐进式建站 Skills v3

一套让 Coding Agent 把自然语言想法变成可使用网站的轻量执行协议。

## 定位

用户不需要理解 Skill、阶段或技术栈。用户只需要说清楚想做什么，Agent 负责把它收敛成一个能完成核心任务的首版，并诚实说明验证范围。

默认体验只有一条短路径：

```text
理解核心任务 → 展示一个方向 → 用户确认 → 实现 → 验证核心任务 → 交付
```

复杂度服务于风险，不服务于流程完整感。

## 三档路径

| 路径 | 适用 | 用户能感知的流程 |
| --- | --- | --- |
| `quick` | 文案、颜色、间距和明确 Bug | 修改 → 相称检查 → 说明结果 |
| `guided` | 新建小网站、普通工具和多页面首版 | 核心任务 → 一个可见方向 → 实现 → 核心检查 |
| `strict` | 权限、支付、隐私、共享数据、公开部署和多人协作 | guided + 独立检查和适用风险证据 |

`quick` 是无状态捷径；默认状态模式是 `guided`。只有真实风险或协作关系要求时才使用 `strict`。

## 执行模型

```text
site-builder-v3  唯一编排者，决定下一步并停在需要用户决定的地方
├── site-brief-v3  收敛一个核心任务和首版范围
├── site-design-v3 保留完整设计知识库，按需产出方向、体验稿和设计合同
└── site-check-v3  只读验证，返回实际证据和未验证项
```

子 Skill 不继续调用其他 Skill，也不自行宣布交付。它们完成一个任务后只返回 `status / summary / artifacts / evidence / limitations` 五个字段；`site-builder-v3` 重新读取状态后继续。

## 第一性原理

系统只解决三种失败：

1. **做错东西**：先确认核心用户、任务和方向。
2. **做不完东西**：按一条可完整体验的任务切首版。
3. **误以为做完**：验证实际核心路径，并区分 `verified` 和 `limited`。

严格模式仍使用同一个小状态接口，只额外要求独立验证和适用的风险证据；不复刻租约、源码指纹或逐项覆盖矩阵。它们只有在真实使用证明有必要后才应该加入。

## 设计能力

v3 精简的是确认流程，不是设计专业能力。`site-design-v3` 保留：

- 从项目事实形成结构和视觉方向的方法；
- 页面设计合同、流程体验稿和参考还原模板；
- 排版、色彩、素材、构图、响应式、组件状态、无障碍与工艺审查规范；
- Token、gallery、基础样式和可导出的校准配方；
- `design-intelligence` `2.13.0` 的内置检索代码、数据与 MIT 许可。

这些内容按任务分支加载。普通 guided 项目只填写设计合同的适用字段；完整模板不会变成新的用户门禁。内置 UI/UX 数据作为固定版本快照随 v3 打包，刻意不依赖 v2 目录；增加约 3.2MB，但保证 v3 可独立安装和复现。

## 安装

v3 使用独立安装器，并按带版本的 Skill 名称安装，因此可以和旧版并存：

```text
python3 v3/install.py /path/to/agent-skills
```

它会安装 `site-builder-v3`、`site-brief-v3`、`site-design-v3`、`site-check-v3`，并返回需要加入宿主项目指令的 `AGENTS.md` 路径。已有 v3 安装时，显式使用 `--replace` 整套替换。状态脚本随 `site-builder-v3` 一起安装。

## 状态接口

状态只有五种：`discovering / decided / building / blocked / delivered`。Agent 每轮执行同一个控制回路：

```text
preflight → 执行 next_action → 写入结果 → 再次 preflight
```

示例：

```text
python3 v3/site-builder/scripts/state.py init PROJECT --mode guided
python3 v3/site-builder/scripts/state.py preflight PROJECT
python3 v3/site-builder/scripts/state.py decide PROJECT \
  --task "登记库存并查看剩余数量" \
  --direction "单工作台展示当前库存和新增入口" \
  --quote "就按这个方向做"
python3 v3/site-builder/scripts/state.py start PROJECT
python3 v3/site-builder/scripts/state.py verify PROJECT \
  --status verified \
  --evidence "新增一条库存并刷新后仍可见"
```

`limited` 必须写明 `--limitation`；strict 的 `verified` 必须带 `--independent`。局部修改不初始化 `.v3`。

绝大多数项目只有一次方向确认（`decide`）。只有简报浮现出真正不同的信息拓扑（例如先做单页落地页还是多页带后台的工作台）时，才走结构选择：先用 `discover --structure choice` 登记候选，用户选定后用 `select-structure --candidate ... --quote ...` 记录，再用一句不同的原话 `decide`：

```text
python3 v3/site-builder/scripts/state.py discover PROJECT \
  --structure choice --reason "信息拓扑不同" \
  --candidate "落地页" --candidate "工作台"
python3 v3/site-builder/scripts/state.py select-structure PROJECT \
  --candidate "工作台" --quote "就选工作台结构"
```

配色、字体、圆角、阴影等只影响视觉的差异一律走 `discover --structure single`，不触发结构选择。`select-structure` 与 `decide` 的两句原话不能相同。

状态工具只防止顺序错误、空证据和不满足模式要求的跃迁。它不能判断用户原话的真实语义，也不能证明证据内容属实；strict 的 `--independent` 只能在独立 Checker 上下文实际完成检查后使用。

## 与 v2 的关系

v3 是独立实验版本，不覆盖 v2。它保留范围收敛、可见方向、真实验证和诚实限制；删除默认路径上的四类确认、九阶段状态、租约和凭据要求。

## 维护

```text
python3 -m unittest discover -s v3/tests -p 'test_*.py'
python3 -m unittest discover -s v3/site-design/scripts/tests -p 'test_*.py'
python3 v3/site-design/scripts/design.py validate
```
