---
name: reson-charts
description: >-
  Render research-report charts inside a Bloome widget — for any analytical report
  (business, consulting, market/industry, competitive, financial/equity). 26 types:
  line, column, clustered, stacked, table, waterfall, doughnut, scatter, combo, mekko,
  gantt, bullet, heatmap, treemap, segmented bar, lorenz, bubble, football-field,
  tornado, sensitivity grid, sources & uses, sparkline, KPI, source attribution, CAGR
  arrows, sankey. Native-Bloome rendering (brand palette, Sora, light+dark), no
  hand-written chart code. The user usually just wants their data visualized and rarely
  names a chart type — infer it from the data + question; honor a type when they ask.
  Triggers: visualize this data, make/add a chart, show these numbers visually, make it
  more intuitive, turn a report or analysis into charts or a dashboard. Do NOT use for
  non-data decorative UI (bloome-widget-design).
metadata:
  type: reference
  version: '1'
---

# reson-charts — agent-callable research chart library

A single self-contained JS library that renders **26 chart types** for **any research
report** — business, consulting, company / market / industry, competitive, financial &
equity research — with the **bloome-widget-design** tokens baked in (brand palette,
Sora, **light + dark**). You (the agent) never write chart CSS or ECharts config — you
**pick a `type` and supply `data`**. The library guarantees brand + dark-mode compliance.

Domain-agnostic: the example data below happens to be company/market numbers, but the
same types serve consulting frameworks (market sizing, share, 2×2s), product/ops
metrics, survey results, and more. Swap the data, keep the type.

> Companion to `bloome-widget-design`: that skill governs the widget shell & content
> layer; this skill fills the **data-viz** slot inside it. Charts count as the
> "genuine data" exception to the anti-dashboard rule — still keep one focal point.

## The one API

```html
<!-- Inline both scripts INTO the widget HTML so the widget is fully self-contained
     (no CDN dependency, offline-safe, one artifact). An external <script src> also
     works — the widget CSP allows it — but inlining is the more robust default. -->
<script>/* … paste the full echarts@5 UMD bundle here … */</script>
<script>/* … paste the full contents of assets/reson-charts.js here … */</script>
<div id="rev" style="height:300px"></div>
<script>
  ResonChart.render('rev', {
    type: 'cagr',
    data: { categories:['2021','2022','2023','2024','2025E'], values:[150,189,205,268,312] }
  });
</script>
```

- `ResonChart.render(elOrId, { type, data, height?, options? })` — draw one chart.
- `ResonChart.refresh()` — re-draw all charts for the current color scheme (already
  auto-wired to `prefers-color-scheme` changes; call manually only if you toggle theme
  in JS).
- `ResonChart.configure({...})` — **override the palette when the user wants their own
  colors** (or a widget defines a custom style). Default (no configure) = brand-compliant
  Bloome palette. Re-draws all live charts.
  ```js
  ResonChart.configure({
    brand:   { blue:'#0D9488', orange:'#7C3AED' }, // primary / secondary
    palette: ['#0D9488','#5EEAD4','#7C3AED','#C4B5FD','#F59E0B','#84CC16','#F87171','#CBD5E1'],
    light:   { ink:'#111', card:'#fff' },          // optional token overrides
    dark:    { ink:'#eee', card:'#161616' }        // optional (dark mode)
  });
  ```
  Rule of thumb (matches bloome-widget-design): if the user did **not** ask for a visual
  style, don't configure — keep Bloome defaults. Only configure when they specify colors
  or the widget has its own brand.
- `ResonChart.types` — array of the 26 valid `type` strings.
- ECharts-backed nodes **must have a height** (px). SVG/HTML types (table, kpi,
  sparkline, mekko, gantt, bullet, sources-uses, sensitivity, source-attribution,
  segmented) size to content.
- **Built-in labels are English by default; localize them to the widget's language
  via `options.labels`.** A few types render fixed words (waterfall/tornado series
  names, bullet legend, football "Current", mekko "Size", sources-uses "Sources/Uses",
  lorenz axis). Match them to the conversation's language — for a Chinese widget pass
  Chinese, etc. Your `data` values are never translated; only these structural words are.
  ```js
  // Chinese widget: localize the waterfall's built-in series names
  ResonChart.render('bridge', { type:'waterfall', data:{...}, height:'300px',
    options:{ labels:{ total:'合计', inc:'量增', dec:'成本' } } });
  ```
  Label keys per type: `waterfall` total/inc/dec · `tornado` down/up · `bullet`
  actual/target/range · `football` current · `mekko` marketSize · `lorenz` axis ·
  `sources-uses` sources/uses/balanced.

## Pick the chart by intent (decision table)

**The user never names a chart type — you infer it from their business question + the
data shape.** Never ask "which chart do you want". Quick map below; the full selection
procedure (verb map, data-shape tie-breakers, composition disambiguation, worked
examples of user phrasing → chosen type) is in
[`references/chart-selection.md`](./references/chart-selection.md) — read it whenever
the choice isn't obvious.

| The analytical job | `type` |
| --- | --- |
| Trend over time (ASP, margin, rate) | `line` |
| Compare a few values | `column` |
| Compare 2–3 series side by side (DRAM vs NAND) | `clustered` |
| How a total's composition changes over time | `stacked` |
| Composition of ONE total, single bar | `segmented` |
| Part-to-whole share at one point | `doughnut` |
| Financial numbers, exact values | `table` |
| Decompose A→B (profit/revenue bridge) | `waterfall` |
| Two-variable relationship | `scatter` |
| Relationship + a 3rd size dimension | `bubble` |
| Bars + a line on 2nd axis (revenue + growth%) | `combo` |
| Market size × internal share (2D) | `mekko` |
| Project / product-launch timeline | `gantt` |
| Actual vs target (KPI attainment) | `bullet` |
| Matrix of values, sector rotation | `heatmap` |
| Nested size (market cap, portfolio weight) | `treemap` |
| Concentration / inequality (top X% → Y%) | `lorenz` |
| Valuation range across methods | `football` |
| Single-factor sensitivity ranked | `tornado` |
| DCF grid (WACC × growth) | `sensitivity` |
| M&A / LBO funding balance | `sources-uses` |
| Inline mini-trend, no axes | `sparkline` |
| Headline metrics as bold color blocks | `kpi` |
| Cite a source per number (compliance) | `source-attribution` |
| Auto-computed CAGR / difference arrows | `cagr` |
| Flow / value-stream (revenue → cost buckets → profit, "where the money goes") | `sankey` |

## Per-type data schemas

Full `data` shape + a copy-paste example for **every** type is in
[`references/chart-catalog.md`](./references/chart-catalog.md). Read it before
composing `data`. Do not invent fields — match the schema exactly.

## Embedding into a widget (source of truth: bloome-widget-design + widget.md)

1. Build the widget shell per `bloome-widget-design` (calm shell, one focal point).
2. **Inline** `assets/reson-charts.js` and the ECharts bundle into the widget HTML so
   the widget is self-contained (no CDN dependency, offline-safe). External `<script
   src>` also works — the widget CSP only restricts `frame-ancestors` — but inlining
   is the more robust default.
3. Add a `<div id>` with a height for each chart, then one `ResonChart.render(...)` call.
4. Feed real, sourced numbers — pair value charts with a `source-attribution` block
   when the widget makes claims.

## Rules

- **Data only (+ labels).** Never pass colors/CSS; the library owns the palette and dark
  mode. The one exception is `options.labels` — pass those to match the widget's language.
- **Localize built-in labels.** Non-English widget → pass `options.labels` (see The one
  API). Defaults are English; a Chinese widget with no labels leaks English words.
- **Match the schema.** Unknown `type` or missing fields throw — check
  `references/chart-catalog.md`.
- **Height for ECharts types.** No height → the chart renders 0px tall.
- **One focal point.** A widget is not a 3×3 chart grid; lead with one chart/number.
- **Every number needs a source.** Use `source-attribution`; don't ship unsourced figures.
