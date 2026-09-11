# 渐进式建站 Skills

一套面向非技术中文用户、作为整体安装和协作运行的 Coding Agent Skills。用户只需用自然语言描述想法、参考、现有项目或修改目标，不需要记住 Skill 名称和开发阶段。

## 协作结构

```text
site-builder（默认入口、全部正式修改和实施）
├── site-brief（调查、首版收敛及协作记录）
├── site-design（视觉/流程体验稿与只读视觉审查）
│   └── site-brief（补齐背景、记录确认结果）
└── site-check（静态、业务、视觉与再次打开验证）
    └── site-design（只读视觉审查，不重新访谈）
```

四个 Skill 应一起安装。`site-builder` 在完整建设、修改和修复请求中自动协调其余 Skill；用户明确只要需求梳理、体验稿或验收时，可由 Agent 直接选择对应 Skill。`site-brief` 集中写入 `.site/brief.md` 与 `.site/state.json`，避免多个 Skill 用旧状态覆盖彼此。

`skills.json` 只描述一个 Skill 可能调用的静态能力依赖；子 Skill 把协作回执返回原调用者不构成反向依赖。builder 根据 check 结果修复再复验属于有界工作流，连续两轮无新证据或进展即停止并标记 `blocked`。

## 整套安装

使用支持仓库级 Skill 套件的安装器时，一次选择全部四个目录。也可使用随仓库提供的标准库脚本，把它们作为一个经过校验的整体安装到宿主的 Skills 目录：

```text
python scripts/install.py /absolute/path/to/agent/skills
```

更新整套时使用 `--replace`；脚本先在临时目录复制并校验四个 manifest，成功后才整体替换，拒绝只覆盖其中一个 Skill。

## 关键约束

- 先确认首个可验证版本，再为新建或重大变化制作低成本可见实验；
- 视觉选择与开发授权是两个决定；
- 完整愿景保留方向，本轮按可独立体验的纵向切片实施；
- `site-check` 独立给出证据，只有 `site-builder` 可以宣布正式交付；
- 简单修改和 Bug 按影响跳过无关阶段；
- 系统级安装、费用、账号、密钥、真实敏感数据和高风险产品决定仍需用户授权。

详细需求见 [`REQUIREMENTS.md`](REQUIREMENTS.md)，统一术语见 [`CONTEXT.md`](CONTEXT.md)。

## 维护检查

```text
python scripts/verify_skills.py .
```

检查四个 Skill 的 frontmatter、协作依赖、相对链接、manifest 文件及哈希，并拒绝未列入包的残留文件。协作行为回放见 [`tests/scenarios.md`](tests/scenarios.md)，面向非技术用户的端到端画像、用例与评分标准见 [`tests/novice-user-evaluation.md`](tests/novice-user-evaluation.md)。
