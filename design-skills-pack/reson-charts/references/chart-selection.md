# reson-charts — chart selection (the agent chooses; the user never says a chart type)

The user asks in business language ("show how margin changed", "who leads the DRAM
market", "is it cheap"). **You infer the chart.** Never ask "which chart do you want".

## Selection procedure

1. **Name the analytical question** in one phrase. Map to a verb:
   *trend · compare · compose · decompose · relate · rank · concentrate · locate-value ·
   attain-target · schedule · cite.*
2. **Check the data shape** (below) — it disambiguates when a verb has several charts.
3. **Pick the single most direct type.** One chart answers one question. If the ask has
   two questions, render two charts, each with one job.
4. **Default when unsure:** time on the x-axis → `line` (trend) or `column` (compare);
   parts of a whole → `segmented`; a bare headline number → `kpi`.

## Verb → type

| Analytical verb | Ask sounds like | type |
| --- | --- | --- |
| Trend | "how did X change over time" | `line` |
| Compare | "compare X across a few things" | `column` |
| Compare (multi-series) | "X vs Y over time" | `clustered` |
| Compose over time | "how did the mix shift" | `stacked` |
| Compose (one total) | "what's it made of" | `segmented` / `doughnut` |
| Decompose | "what drove the change from A to B" | `waterfall` |
| Auto-growth | "what's the growth rate / CAGR" | `cagr` |
| Relate (2 var) | "is valuation tied to growth" | `scatter` |
| Relate (+size) | "…and who's biggest" | `bubble` |
| Mixed units | "revenue and its growth %" | `combo` |
| Size × structure | "market size and share together" | `mekko` |
| Rank sensitivity | "what assumption matters most" | `tornado` |
| Grid sensitivity | "value under different WACC/growth" | `sensitivity` |
| Concentrate | "how concentrated are customers" | `lorenz` |
| Locate value | "is it cheap / what's it worth" | `football` |
| Attain target | "did we hit the KPI" | `bullet` |
| Locate in matrix | "which sector is hot each month" | `heatmap` |
| Nested size | "market-cap / weight breakdown" | `treemap` |
| Schedule | "product roadmap / timeline" | `gantt` |
| Headline metric | "give me the key numbers" | `kpi` |
| Micro trend | "tiny inline trend in a row/cell" | `sparkline` |
| Cite | any widget stating figures | `source-attribution` |

## Data shape → type (tie-breaker)

| You have… | Lean toward |
| --- | --- |
| categories + 1 numeric series, ordered by time | `line` (trend) |
| categories + 1 numeric series, not time | `column` |
| categories + 2–3 series | `clustered` (compare) or `stacked` (compose) |
| a set of parts summing to ~100% | `segmented` (bar) / `doughnut` (pie) |
| a start value, ± steps, an end value | `waterfall` |
| first & last value + the years between | `cagr` |
| pairs of (x, y) [+ size] | `scatter` / `bubble` |
| a 2-D grid of numbers (rows × cols) | `heatmap` / `sensitivity` |
| ranges [low, high] per method + a current value | `football` |
| items with actual + target + thresholds | `bullet` |
| items with start/end periods | `gantt` |
| markets each with a size AND an internal split | `mekko` |
| two lists that must balance to one total | `sources-uses` |

## Composition disambiguation (the most common mistake)

- Over **time** → `stacked` (bars per period).
- **One** point in time, want the eye to compare slices → `doughnut`.
- **One** point in time, want it compact / inline / to compare across rows → `segmented`.
- Size of the whole **also matters** across categories → `mekko` (width encodes size).

## Charts are domain-agnostic

A chart type is chosen by the **analytical question**, never by the domain. The same
type serves many scenarios — pick by what the user is asking, not by whether it's a
stock, a market, a consulting deck, or an ops review:

- `waterfall` = "decompose A→B" — margin bridge, funnel drop-off, budget variance, headcount change.
- `mekko` = "size × internal split" — market segments, revenue by region×product, portfolio.
- `bubble`/`scatter` = "relate two things (+size)" — valuation vs growth, effort vs impact 2×2, risk vs return.
- `bullet` = "actual vs target" — KPI attainment, quota, SLA, budget vs actual.
- `stacked`/`segmented` = "composition" — revenue mix, cost breakdown, traffic sources, vote share.

So don't file charts under a scenario. Read the verb, then the data shape.

## Worked examples (user phrasing → chosen type + why)

Organized by the analytical intent, not the domain. Domains are mixed in on purpose —
each type recurs across many kinds of report.

- "X 从 A 到 B 中间是怎么变的 / 拆一下" → `waterfall` (decompose into drivers).
- "谁的份额最大 / 占比构成" (one point in time) → `doughnut`, or `segmented` if compact/inline.
- "结构这几年怎么变的" → `stacked` (composition over time).
- "把几个东西按两个维度摆一下 / 影响 vs 难度 / 估值 vs 增长" → `scatter`, or `bubble` (+size).
- "规模和内部格局一起看" → `mekko` (size × share).
- "达没达标 / 对目标" → `bullet`.
- "哪个因素影响最大" → `tornado`; "两个变量的网格" → `sensitivity`.
- "集中度高不高 / 前 X% 占了多少" → `lorenz`.
- "贵不贵 / 值多少" (a range vs a point) → `football`.
- "增长率 / CAGR" → `cagr`; 纯趋势 → `line`.
- "几个关键数放个概览" → `kpi`; 塞进一行/单元格的迷你趋势 → `sparkline`.
- "时间安排 / 排期 / 路线图" → `gantt`.
- "两边要配平" (来源 vs 运用、预算 vs 支出) → `sources-uses`.

## Always pair figures with sources

Whenever a widget states numbers, add a `source-attribution` block (auto-numbered
footnotes + hover) so every figure is traceable. This is a compliance default, not
optional — see `chart-catalog.md`.
