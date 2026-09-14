# 规范库来源与许可

本目录下的规范正文**逐字取自上游仓库**，本项目不重写其设计决策。改动仅限本文件所列的机械性适配。

## 一、规范正文（`styles/`、`masters/`、`style-index.md`、`knowledge-base.md`）

| 项 | 值 |
| --- | --- |
| 上游 | [xdx888999/xdx-lab-design-skill](https://github.com/xdx888999/xdx-lab-design-skill) |
| 许可 | MIT — Copyright (c) 2026 XDX_Lab |
| 取用内容 | `references/styles/*-DESIGN.md`（50）、`references/masters/*-DESIGN.md`（20）、`references/masters/master-index.md`、`references/style-index.md`、`references/全球设计风格知识库.md` |
| 体量 | 约 670 KB / 70 份规范 |

MIT 要求保留版权声明与许可全文。上游 `LICENSE` 原文见本目录 [`LICENSE.xdx-lab-design`](LICENSE.xdx-lab-design)。

**对应的中文命名**：`references/全球设计风格知识库.md` → `knowledge-base.md`；`references/masters/master-index.md` → `masters/master-index.md`。其余文件名保持不变。

## 二、目录与校验工具（`../tools/`）

| 文件 | 上游路径 | 许可 |
| --- | --- | --- |
| `parser.mjs`、`semantic-map.mjs`、`contrast.mjs`、`yaml-writer.mjs` | `tools/lib/` | MIT（同上） |
| `lint.mjs`、`transform.mjs`、`check-output.mjs`、`export.mjs` | `tools/` | MIT（同上） |
| `tests/*.test.mjs` | `tools/tests/` | MIT（同上） |

**机械性适配**（不改逻辑）：

1. `lint.mjs`、`transform.mjs`：把 `readdirSync('references/styles')` 这类**依赖调用者工作目录**的路径改为相对工具自身定位的 `SPEC_ROOT`（`../assets/spec`）。原因是本包把规范放在 `assets/spec/`，且调用者可能从任意目录运行。
2. `check-output.mjs`：仅更新 usage 提示中的示例路径。
3. 未收录 `tools/tests/repository-content.test.mjs`：该文件断言上游仓库形状（根 `README.md`、`docs/cases`、`docs/index.html`、`references/` 目录），对本包不适用；其中「20 份大师规范均有完整 typography token」一项已由 `lint.mjs` 覆盖。
4. 未收录上游 `docs/`（含 13 个案例 HTML 与约 71 MB 配图）、`docs/assets/*.png`、`.ai/progress.md`。原因见 [KNOWN-ISSUES.md](KNOWN-ISSUES.md) 第六节。

## 三、UX 规则与 token 架构（`../assets/rules/`）

| 文件 | 上游 | 许可 |
| --- | --- | --- |
| `ux-guidelines.csv`（119 条） | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) `.claude/skills/ui-ux-pro-max/data/ux-guidelines.csv` | MIT — Copyright (c) 2024 Next Level Builder |
| `motion.csv`（17 条） | 同上 `data/motion.csv` | MIT |
| `design-tokens-starter.json` | 同上 `.claude/skills/design-system/templates/` | MIT |
| `token-architecture/*.md`（7 份） | 同上 `.claude/skills/design-system/references/` | MIT |

MIT 许可全文见 [`LICENSE.ui-ux-pro-max`](LICENSE.ui-ux-pro-max)。

**只取语言无关的部分。** 上游的 `styles.csv`（88 行风格元数据）、`colors.csv`（192 套行业色板）、`products.csv` 与 `ui-reasoning.csv`（行业 → 固定 Pattern/风格映射）**未收录**，原因是它们与本源「行业名称本身不是项目证据、不得创造首版能力」的既有规则直接冲突（见 `../../REQUIREMENTS.md` 与 `../references/design-context.md`）。这些文件是英文语料设计，其 BM25 检索层对中文不适用。

## 四、字体

上游规范大量依赖 Google Fonts（`Inter` 出现 113 次、`Helvetica Neue` 76 次等，合计 36 个字体族）。本包**不随包分发任何字体文件**。字体交付和回退规则见 [`spec-library.md`](../../references/spec-library.md) 第三节。

## 五、溯源

`catalog.json` 中每条 `spec` 的 `file` 字段指向本目录内的相对路径；`source.repo` 记录上游仓库。校验目录与规范是否一致：

```sh
node tools/catalog.mjs --check
```
