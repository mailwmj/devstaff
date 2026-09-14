# 渐进式建站 Skills

一套面向非技术中文用户的 Coding Agent 建站能力。用户只描述目标、参考、现有项目和反馈；四个 Skill 在内部完成首版收敛、设计、正式开发、真实渲染验证和交付。

## 结构

```text
site-builder  默认入口、正式源码 Writer、修复与交付
├── site-brief   事实调查、首版范围、状态门禁
├── site-design  视觉方向、样式语法、实现模式与体验稿
└── site-check   冻结后的只读 Checker
```

四个目录与根 `AGENTS.md` 应一起安装。普通用户不需要手动选择 Skill，也不会看到“快速/高质量”等模式。

## 质量模型

设计不再使用单一 `visual_source` 或“命中即停”链，而是三个独立决定：

```text
direction  为什么这个项目这样表达
grammar    用哪套颜色、字体和组件语言保持一致
patterns   复用哪些实现与交互模式，做了什么适配
```

流程先从项目事实形成任务合同和 direction，再用语义索引选择最多三个 grammar/template 候选。行业名称不参与选择；模板只在方向确定后降低实现 token，不替用户决定范围或页面结构。

```sh
node site-design/tools/select.mjs --profile profile.json --kind style --limit 3
node site-design/tools/select.mjs --profile profile.json --kind template --limit 3
node site-design/tools/prepare-design.mjs --profile profile.json --state .site/state.json --output .site/design/packet.json
python3 site-builder/scripts/site.py list-templates
python3 site-builder/scripts/site.py inspect-template form
```

`DesignPacket` 最大 12,000 bytes，builder/checker 直接消费它；只加载最终选中的一份完整规范和实际使用的模板文件。旧 `visual_source` 在读取时映射并标记，不改写旧项目。

## 模板

随包的四个可运行模板是实现模式，不是视觉来源：

| ID | 覆盖 |
| --- | --- |
| `static` | 内容主导、连续阅读、响应式重排 |
| `browse` | 筛选、列表/详情、比较、空状态 |
| `form` | 错误恢复、草稿、提交前核对、完成状态 |
| `tool` | 本地 CRUD、持久化、导入导出、删除确认 |

新建项目始终初始化为 `discovering`、`visual_required=true`，模板不会打开快速分支。

## 两层质量闭环

普通生成自动执行轻量闭环：

```text
生成 → 真实浏览器渲染 → 核心任务/状态/移动端/重开 → 修复 → 复验 → 交付
```

`check-output.mjs` 是静态规范预检；`check-render.mjs` 才读取 linked CSS、computed style、字体、相邻对比度、溢出、触控尺寸、图片裁剪和减弱动效，并可根据合同执行核心任务与再次打开。

维护者发布 Skill 时运行完整闭环：25 个 SD/MV 固定场景、9 个锁定 `F-*` 夹具、两名真人五维评分以及 token/耗时比较。它不属于普通用户流程。条件不全时只能报告自动冒烟或不完整，不能宣布完整回归通过。

## 验证

```sh
python3 scripts/verify_skills.py .
python3 scripts/context_budget.py .
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s site-builder/tests -p 'test_*.py'
python3 site-design/scripts/design.py validate
node site-design/tools/catalog.mjs --check
node site-design/tools/lint.mjs
node --test --test-concurrency=1 site-design/tools/tests/*.test.mjs
python3 tests/evaluate.py validate-catalog
```

完整人工评测见 [`tests/novice-user-evaluation.md`](tests/novice-user-evaluation.md)，设计场景见 [`tests/site-design-scenarios.md`](tests/site-design-scenarios.md)。产品不变量见 [`REQUIREMENTS.md`](REQUIREMENTS.md)，统一术语见 [`CONTEXT.md`](CONTEXT.md)。
