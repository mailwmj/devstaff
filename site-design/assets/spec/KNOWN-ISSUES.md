# 规范库已知问题

本文件记录**导入时实测发现**的问题，以及本项目对每一项的处理方式。
所有结论都可用 `node tools/catalog.mjs` 复现，数据在 `catalog.json`。

上游自己的 `lint.mjs` 对全部 70 份规范报 **0 error / 0 warning**。以下问题它检测不到，属于本轮导入新发现的。

---

## 1. 十份规范的 frontmatter 把亮/暗两套主题叠在一起（阻断级）

**表现。** 这 10 份规范的 `colors:` 块里，同一个键出现两次以上：先是完整的亮色块，紧接着又一个暗色块。

以 `styles/02-tech-minimal-DESIGN.md` 为例（前 10 行是亮色块，第 11 行起是暗色块）：

```yaml
colors:
  surface: "#FFFFFF"        # 亮色块（自洽）
  on-surface: "#0A0A0A"
  ...
  surface: "#111111"        # 暗色块，重复键
  surface-raised: "#1A1A1A"
  heading: "#EDEDED"
```

**后果。** 取「后者优先」的解析器会得到 `surface=#111111` 配 `on-surface=#0A0A0A` —— **深底深字，对比度 1.05:1**。上游的 `tools/lib/parser.mjs` 正是后者的行为，因此它导出的 token 会直接产出不可读页面。

**受影响文件**（`catalog.json` 中 `multi_theme: true`）：

| spec_id | 主题块数 | 首块 surface |
| --- | --- | --- |
| `02-tech-minimal` | 2 | `#FFFFFF` |
| `05-fintech-clean` | 2 | `#FFFFFF` |
| `06-ecommerce-energetic` | 2 | `#FFFFFF` |
| `12-ai-native` | 2 | `#FFFFFF` |
| `13-health-wellness` | 3 | `#FAF8F5` |
| `30-dark-developer` | 2 | `#0D1117` |
| `01-dieter-rams`（大师） | 2 | `#F5F3EE` |
| `02-massimo-vignelli`（大师） | 2 | `#FFFFFF` |
| `09-charles-ray-eames`（大师） | 2 | `#F7E7C6` |
| `18-neville-brody`（大师） | 2 | `#0A0A0A` |

**本项目处理。** `tools/catalog.mjs` 按**出现次序取第 1 块**作为规范主色（实测这 10 份的首块全部自洽，`text-contrast` 告警归零），并把第 2 块暴露为 `colors_dark`。
**规范正文不改**，`multi_theme` 与 `theme_blocks` 作为机读标记保留，供实现阶段选择亮/暗。

> 未采用「改 frontmatter」的修法：那会改写上游的设计数据，且本文档无法持续证明改动没有引入新偏差。取首块是可复算的，改文件不是。

---

## 2. 上游 `parser.mjs` 的明暗判定会误判

`tools/lib/parser.mjs` 的 `detectDarkTheme()` 用 `(r+g+b)/3 < 100` 判断，且正则 `background[^`]*`(#[0-9A-Fa-f]{6})`` 会跨小节贪婪匹配。

实测：`24-swiss-international`（白底）被判为 `isDark: true`。

**本项目处理。** `catalog.mjs` 不调用它，改用 frontmatter 的 `surface` + WCAG 相对亮度（阈值 0.5）。`catalog.json` 的 `is_dark` 以此为准。
上游 parser 仍原样保留供 `export.mjs` / `transform.mjs` 使用，但 **token 导出前必须用 `catalog.json` 的 `surface` 复核明暗**。

---

## 3. 规范正文自带 74 条 `FAIL` 对比度行

45 份规范第 2 节有一张自动生成的 WCAG 对照表，其中 74 行标记为 `FAIL`。逐条核对后分两类：

- **噪声（多数）**：把背景色和它自己比，例如 `Deep Dark #0D0D1A on #0D0D1A = 1:1`、`White #FFFFFF on #FFFFFF = 1:1`。这些不是文本色对，不构成缺陷。
- **真实风险（少数）**：正文色与背景确实不足，例如 `02-tech-minimal` 的 `Faint #A3A3A3 on #FFFFFF = 2.5:1`、`05-fintech-clean` 的 `Muted #94A3B8 on #FFFFFF = 2.6:1`、`07-luxury-premium` 的 `Light Gray #ABABAB on #FAFAF8 = 2.2:1`。

**本项目处理。** 不据此判定规范"不合格"。规范给出的 `muted / faint` 角色在真实页面上应只用于非关键文字。
实现阶段仍须按 `../references/review-protocol.md` 在**实际渲染**上重算相邻色对——这张表是声明，不是渲染结果。

---

## 4. 62/70 份规范没有中文字体

只有 8 份声明了 CJK 字体族：`20-new-chinese-trendy`、`31-song-dynasty-ink`、`32-tang-dynasty-splendor`、`33-republican-shanghai`、`34-ukiyo-e`、`35-zen-wabi-sabi`、`13-ikko-tanaka`、`15-kenya-hara`。

其余 62 份只声明西文字体（`Inter`、`Helvetica Neue`、`Arial`、`Playfair Display` 等）。

**本项目处理。** `catalog.json` 的 `cjk_font` 标记此状态，`INDEX.md` 以 `CJK` 列显示为 `—`。
选择这些规范时，**中文回退不是可选项**：必须在项目内补一套中文回退栈，并把该补充登记为 `deviation`。
上游规范正文不因此失效——它约束的是字体**角色**（display / heading / body / data），中文回退是角色的具体化。

---

## 5. 字体运行时依赖

规范共引用 41 个字体族（`Inter` 频次最高，其次 `Noto Serif SC`、`Helvetica Neue`、`JetBrains Mono`）。本包不随附字体二进制；实现时按真实分发条件选择已有、bundled、CDN 或系统字体，并在实际页面验证加载与回退。字体名称不构成目录拒绝条件。

---

## 6. 未收录的上游内容

| 未收录 | 原因 |
| --- | --- |
| `docs/`（13 个案例 HTML + 约 71 MB 配图 + 预览 PNG） | 案例 HTML **不自包含**，引用约 71 MB 图片。为控制安装体积与默认上下文，本包不收录；实际需要案例时逐项引入。 |
| `tools/tests/repository-content.test.mjs` | 断言上游仓库形状（根 `README.md`、`docs/cases`、`docs/index.html`），对本包不适用。 |
| `docs/index.html`、`docs/style.html` 等画廊页 | 与上一条同源，且本项目已有自己的 `assets/design/gallery.html`。 |
| ui-ux-pro-max 的 `styles.csv` / `colors.csv` / `products.csv` / `ui-reasoning.csv` | 与本源「行业名称不是项目证据」规则冲突，详见 `ATTRIBUTION.md` 第三节。 |

---

## 7. 复现方式

```sh
cd site-design
node tools/catalog.mjs           # 重新生成 catalog.json 与 INDEX.md
node tools/catalog.mjs --check   # 校验二者与规范库一致
node tools/lint.mjs              # 上游 lint：应为 0 error / 0 warning
node --test tools/tests/*.test.mjs
```
