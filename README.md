# 渐进式建站 Skills

一套让 Coding Agent 把自然语言想法变成可使用网站的轻量执行协议（版本 1.0.0）。

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
site-builder  唯一编排者，决定下一步并停在需要用户决定的地方
├── site-brief  收敛一个核心任务和首版范围
├── site-design 保留完整设计知识库，按需产出方向、体验稿和设计合同
└── site-check  只读验证，返回实际证据和未验证项
```

子 Skill 不继续调用其他 Skill，也不自行宣布交付。它们完成一个任务后只返回 `status / summary / artifacts / evidence / limitations` 五个字段；`site-builder` 重新读取状态后继续。

## 第一性原理

系统只解决三种失败：

1. **做错东西**：先确认核心用户、任务和方向。
2. **做不完东西**：按一条可完整体验的任务切首版。
3. **误以为做完**：验证实际核心路径，并区分 `verified` 和 `limited`。

严格模式仍使用同一个小状态接口，只额外要求独立验证和适用的风险证据；不复刻租约、源码指纹或逐项覆盖矩阵。它们只有在真实使用证明有必要后才应该加入。

## 设计能力

系统精简的是确认流程，不是设计专业能力。`site-design` 保留：

- 从项目事实形成结构和视觉方向的方法；
- 页面设计合同、流程体验稿和参考还原模板；
- 排版、色彩、素材、构图、响应式、组件状态、无障碍与工艺审查规范；
- Token、gallery、基础样式和可导出的校准配方；
- `design-intelligence` `2.13.0` 的内置检索代码、数据与 MIT 许可。

这些内容按任务分支加载。普通 guided 项目只填写设计合同的适用字段；完整模板不会变成新的用户门禁。内置 UI/UX 数据作为固定版本快照打包，保证独立安装和复现。

## 仓库结构

分发内容与开发内容分开放置：

```text
release/          唯一分发根。整个目录可独立打包安装，不依赖仓库其他部分
├── skills.json   技能清单
├── install.py    安装器
├── AGENTS.md     需要加入宿主项目指令的协议文件
└── site-brief/ site-builder/ site-check/ site-design/
tests/            开发用测试
.github/          开发用 CI
README.md  AGENT-GUIDE.md  REVIEW-MANIFEST.md   开发用文档
```

只分发 `release/`。校验、安装与测试命令都从仓库根目录执行，路径以 `release/` 开头。

## 安装

使用安装器进行安装：

```text
python3 release/install.py /path/to/agent-skills
```

它会安装 `site-builder`、`site-brief`、`site-design`、`site-check`，并返回需要加入宿主项目指令的 `AGENTS.md` 路径。已有安装时，显式使用 `--replace` 整套替换。状态脚本随 `site-builder` 一起安装。

也可以只打包分发根：`git archive --format=tar HEAD:release | tar -xf - -C /tmp/site-skills`，解包后的目录本身就是可安装的完整包。

## 状态接口

状态只有五种：`discovering / decided / building / blocked / delivered`。Agent 每轮执行同一个控制回路：

```text
preflight → 执行 next_action → 写入结果 → 再次 preflight
```

示例：

```text
python3 release/site-builder/scripts/state.py init PROJECT --mode guided
python3 release/site-builder/scripts/state.py preflight PROJECT
python3 release/site-builder/scripts/state.py decide PROJECT \
  --task "登记库存并查看剩余数量" \
  --direction "单工作台展示当前库存和新增入口" \
  --quote "就按这个方向做"
python3 release/site-builder/scripts/state.py start PROJECT
python3 release/site-builder/scripts/state.py verify PROJECT \
  --status verified \
  --evidence "新增一条库存并刷新后仍可见"
```

`limited` 必须写明 `--limitation`；strict 的 `verified` 必须带 `--independent`。局部修改不初始化 `.site`。

新建与整体改版默认采用“骨架双选 ➔ 视觉双选（轻量且可继承）”递进确认：先用 `discover --structure choice` 登记 2 种信息架构候选并生成轻量骨架预览（优先引导客户端自带浏览器打开），用户选定后用 `select-structure --candidate ... --quote ...` 记录；随后提供 2 种视觉风格单页体验稿（轻量对比，严禁过度测试），用户微调满意后将 CSS 变量提取为 Token、核心 HTML 作为纵向切片模板，再用一句不同的原话 `decide` 锁定完整方向：

```text
python3 release/site-builder/scripts/state.py discover PROJECT \
  --structure choice --reason "信息架构差异：看板流 vs 向导流" \
  --candidate "看板全景流" --candidate "任务向导流"
python3 release/site-builder/scripts/state.py select-structure PROJECT \
  --candidate "看板全景流" --quote "选看板流"
```

视觉风格选定并微调后，执行 `decide` 锁定方向，`select-structure` 与 `decide` 的两句原话不能相同。局部修改或已有成熟规范的局部修复不触发结构选择。

状态工具只防止顺序错误、空证据和不满足模式要求的跃迁。它不能判断用户原话的真实语义，也不能证明证据内容属实；strict 的 `--independent` 只能在独立 Checker 上下文实际完成检查后使用。

## 维护与测试

```text
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s release/site-design/scripts/tests -p 'test_*.py'
python3 release/site-design/scripts/design.py validate
```
