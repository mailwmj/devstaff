# ClawHive 网站建站 Skills

这是可直接分发的正式版本（`0.15.0`）。它面向没有编程背景的中文用户：用户只需描述目标、参考和修改意见，Agent 会自行调度需求梳理、视觉设计、正式开发和独立检查。

## 目录说明

- `AGENTS.md`：总控规则。它规定 Skill 调度、确认门禁、交接顺序和项目文件位置，是本包最重要的指令文件。
- `agent.md`：兼容指针，内容很短；正式规则以同目录的 `AGENTS.md` 为准。
- `CLAUDE.md`：Claude Code 的导入文件，内容是 `@AGENTS.md`。
- `site-builder/`：默认入口，负责正式开发、修复和交付编排。
- `site-brief/`：梳理需求、首版范围和用户确认记录。
- `site-design/`：生成视觉方案、体验稿和页面设计合同，内置设计检索数据。
- `site-check/`：独立、只读地检查构建、核心任务、视觉、响应式和再次打开。
- `skills.json`：四个 Skill 的版本和依赖关系。
- `scripts/install.py`：原子安装四个 Skill 的安装器。
- `scripts/verify_skills.py`：发布包完整性校验器。

## 安装

安装器只写入 Skill 目录，不会覆盖宿主已有的指令文件。先在本目录运行：

```text
python3 scripts/verify_skills.py .
```

### Codex

```text
python3 scripts/install.py ~/.agents/skills
```

将本包的 `AGENTS.md` 放到 Codex 能读取的位置：

- 全局：`~/.codex/AGENTS.md`；
- 项目级：正在开发的网站项目根目录下的 `AGENTS.md`。

已有文件时请追加内容，不要覆盖原有规则。更新整套 Skill 时使用：

```text
python3 scripts/install.py ~/.agents/skills --replace
```

### Claude Code

```text
python3 scripts/install.py ~/.claude/skills
```

将本包的 `AGENTS.md` 放在 Claude Code 可访问的位置，并在同一层级的 `CLAUDE.md` 中保留：

```text
@AGENTS.md
```

已有 `CLAUDE.md` 时只追加这一行或等价的导入，不要覆盖原有内容。

## 项目内交接文件

四个 Skill 处理具体网站项目时，所有交接资料都放在**被开发项目根目录**的 `.site/` 下，不放回本发布包：

```text
<项目>/
├── .site/
│   ├── brief.md                       需求事实、首版范围和已确认事项
│   ├── state.json                     协作阶段与确认门禁（只由 site-brief 写入）
│   ├── design/
│   │   ├── surface-brief.md           页面设计合同，设计/开发/检查共用
│   │   ├── prototype.html             可点击体验稿（如本轮制作）
│   │   └── assets/                    体验稿所需的项目内素材（如有）
│   ├── implementation-plan.md         正式开发计划和合同 ID 映射（如需要）
│   ├── lease.json                     Writer / Checker 交接租约（工具维护）
│   └── checks/
│       ├── <check_id>.json            检查矩阵凭据
│       └── evidence/                  已归档的截图、日志和结果文件
└── <正式网站源码>/
```

`site-brief` 负责写 `brief.md`、`state.json` 和门禁历史；`site-design` 负责 `surface-brief.md` 与体验稿；`site-builder` 负责正式源码和实施计划；`site-check` 只在 `.site/checks/` 写检查凭据。不要手动编辑 `state.json`、`lease.json` 或已生成的检查凭据。

## 使用时的最短路径

1. 用户说“帮我做个网站”或要求整体改版：进入 `site-builder`，先经 `site-brief` 明确首版范围。
2. 需要新结构或新视觉：进入 `site-design`，生成体验稿；结构和视觉分别等待用户确认。
3. 视觉确认且开发授权明确后：`site-builder` 才能创建正式源码和实施计划。
4. 开发完成：停止体验稿和 Writer 服务，登记正式服务，冻结源码后交给 `site-check`。
5. 检查有失败项：回到 `site-builder` 修复，再重新交接和检查。
6. 检查通过：交付前把方案、结构、视觉和开发授权的用户原话逐条回放给用户核对，再交付。

以下情况不能被默认推断：用户只选了结构不等于确认视觉；用户称赞体验稿不等于授权开发；构建成功或截图存在不等于验收通过。

## 运行入口

Agent 需要调用脚本时，从实际安装位置解析 Skill 路径，不要依赖本发布包仍然存在：

```text
python3 <site-brief>/scripts/state.py <action> <项目路径>
python3 <site-design>/scripts/design.py research <查询> [--design-system | --domain <域> | --stack <技术栈>]
python3 <site-builder>/scripts/site.py <action> <项目路径>
python3 <site-check>/scripts/check.py <static | run | matrix> <项目路径>
```

设计检索由 `site-design` 统一调用；`site-builder` 和 `site-check` 不直接重新选择设计预设。发布包不需要也不应引用仓库根目录的外部参考包。

## 分发边界

- 本目录可以单独复制和分发；不需要携带原项目的测试、研究、CI、版本库或上游参考源。
- 四个 `site-*` Skill 必须作为一组安装，不能只安装其中一个。
- 正式网站源码、用户内容、截图和检查证据属于具体项目，不应复制回本目录。
- 公开部署、付费服务、账号授权、密钥、共享数据和真实敏感数据仍需用户明确授权；本包不会替用户执行这些不可逆动作。
