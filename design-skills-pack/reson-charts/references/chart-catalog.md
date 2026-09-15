# reson-charts — data schema catalog

Every `type` and its exact `data` shape, with a copy-paste example. Call pattern is
always `ResonChart.render(el, { type, data, height?, options? })`. Colors, fonts, and
dark mode are handled by the library — **pass data only**.

ECharts-backed types need an explicit pixel `height`. SVG/HTML types size to content.

---

## Tier 1 — basics

### `line` — trend
```js
{ categories:['Q1','Q2','Q3','Q4'], series:[{name:'ASP',data:[100,82,95,124]},{name:'毛利率%',data:[42,33,40,49]}] }
```

### `column` — compare a few values
```js
{ categories:['2022','2023','2024','2025E'], data:[243,189,256,312] }
```

### `clustered` — multi-series side by side
```js
{ categories:['Q1','Q2','Q3'], series:[{name:'DRAM',data:[62,48,80]},{name:'NAND',data:[40,32,47]}] }
```

### `stacked` — composition change over time
```js
{ categories:['2023','2024','2025E'], series:[{name:'DRAM',data:[105,150,190]},{name:'NAND',data:[62,85,100]},{name:'其他',data:[22,21,22]}] }
```

### `table` — exact numbers  ·  `posCol` = index of a column to accent (positive)
```js
{ columns:['指标','2024','2025E','YoY'], rows:[['营收','256','312','+21.9%'],['毛利率','35.2%','43.1%','+7.9pp']], posCol:3 }
```

---

## Tier 2 — deeper

### `waterfall` — bridge; each step is total | inc | dec (bases auto-computed)
```js
{ steps:[{label:'23毛利',value:40,type:'total'},{label:'量增',value:12,type:'inc'},{label:'涨价',value:16,type:'inc'},{label:'成本',value:4,type:'dec'},{label:'24毛利',value:64,type:'total'}] }
```

### `doughnut` — part-to-whole
```js
{ data:[{name:'三星',value:43},{name:'海力士',value:30},{name:'美光',value:22},{name:'其他',value:5}] }
```

### `scatter` — two-variable  ·  points = [x, y, label]
```js
{ xName:'增速%', yName:'PE', points:[[28,22,'A'],[18,16,'B'],[35,30,'D']] }
```

### `combo` — bars + line on 2nd axis
```js
{ categories:['2022','2023','2024','2025E'], bar:{name:'营收',data:[243,189,256,312]}, line:{name:'增速%',data:[-18,-22,35,22]} }
```

---

## Tier 3 — advanced

### `mekko` — width = market size, height = share  ·  segments align to segmentNames
```js
{ segmentNames:['三星','海力士','美光','其他'], markets:[{name:'DRAM',size:55,segments:[43,30,22,5]},{name:'NAND',size:30,segments:[34,25,15,26]}] }
```

### `gantt` — start/end are period indexes into `periods`
```js
{ periods:['1月','2月','3月','4月','5月','6月'], tasks:[{name:'DDR5 量产',start:0,end:3},{name:'HBM3E 送样',start:1,end:4}] }
```

### `bullet` — actual vs target  ·  bands = [poor→ok, ok→good] thresholds
```js
{ rows:[{label:'营收',max:120,bands:[80,100],measure:108,target:100},{label:'良率',max:100,bands:[85,95],measure:93,target:95}] }
```

### `heatmap` — matrix  ·  values[row][col]; min/max drive the color scale
```js
{ rows:['存储','逻辑','设备'], cols:['1月','2月','3月','4月'], values:[[8,-3,5,12],[3,4,-5,6],[12,8,-2,4]], min:-8, max:12 }
```

### `treemap` — nested size
```js
{ data:[{name:'存储',value:5200,children:[{name:'三星',value:2600},{name:'海力士',value:1500}]},{name:'逻辑',value:3800,children:[{name:'台积电',value:2800}]}] }
```

---

## Tier 4 — composition / valuation

### `segmented` — one total as a single horizontal bar (values are %)
```js
{ data:[{name:'DRAM',value:55},{name:'NAND',value:30},{name:'其他',value:15}] }
```

### `lorenz` — concentration  ·  paired cumulative arrays; options.xName optional
```js
{ x:[0,20,40,60,80,100], y:[0,5,15,34,65,100] }
```

### `bubble` — relationship + size  ·  points = [x, y, size, label]
```js
{ xName:'增速%', yName:'利润率%', series:[{name:'半导体',points:[[28,42,1800,'A'],[12,30,420,'C']]},{name:'软件',points:[[35,25,1200,'D']]}] }
```

### `football` — valuation ranges  ·  options {min,max} set the x-axis; current = price line
```js
// data
{ methods:['目标价','52周','先例','可比','DCF'], low:[125,92,118,110,105], high:[150,160,152,138,145], current:122 }
// options
{ min:80, max:170 }
```

### `tornado` — single-factor sensitivity, order rows most→least impactful
```js
{ xName:'对每股价值影响(基准132)', vars:['资本开支','永续增长','毛利率','WACC','营收CAGR'], down:[-5,-8,-10,-15,-18], up:[4,9,12,14,22] }
```

### `sensitivity` — DCF grid  ·  grid[row][col]; highlight = [rowIdx, colIdx] base case
```js
{ rowVar:{name:'WACC',vals:['8%','9%','10%','11%','12%']}, colVar:{name:'永续增长',vals:['2%','2.5%','3%','3.5%','4%']},
  grid:[[150,158,166,175,184],[138,145,153,161,169],[127,134,141,148,156],[118,124,131,138,145],[110,116,122,128,135]], highlight:[2,2] }
```

### `sources-uses` — funding balance  ·  both sides should sum to `total`
```js
{ total:500, sources:[{name:'银行贷款',value:260},{name:'夹层债',value:90},{name:'股权',value:130},{name:'现金',value:20}],
  uses:[{name:'收购股权',value:430},{name:'偿还旧债',value:45},{name:'费用',value:25}] }
```

---

## Tier 5 — micro / interaction / compliance

### `sparkline` — inline mini-trends  ·  up drives color (blue up / orange down)
```js
{ items:[{label:'营收',data:[88,98,109,132],delta:'+21%',up:true},{label:'净利润',data:[23,22,21.8,21.4],delta:'-3.2%',up:false}] }
```

### `kpi` — headline metrics as bold color blocks (Bloome color-field stat)
```js
{ stats:[{name:'营收',value:'¥312亿',sub:'+21.9%'},{name:'毛利率',value:'43.1%',sub:'+7.9pp'},{name:'EPS',value:'$8.90',sub:'+64.8%'}] }
```

### `source-attribution` — cite a source per number  ·  parts = text {t} + cited {fig,src}
Footnotes auto-number; each `{fig,src}` gets a hover tooltip showing `src`.
```js
{ parts:[
    {t:'2026 营收预计 '},
    {fig:'¥132亿', src:'瑞银研报《XX科技深度》 2026-03-14 · P.42'},
    {t:',同比 '},
    {fig:'+21%', src:'公司 2025 年度报告 · P.18 经审计'},
    {t:'。'}
  ], note:'口径 Non-GAAP,采集 2026-06-29' }
```

### `cagr` — column chart with an auto-computed CAGR arrow + last-period YoY tag
```js
{ categories:['2021','2022','2023','2024','2025E'], values:[150,189,205,268,312] }
```

### `sankey` — flow / value-stream; band width ∝ value (how a total splits across stages)
`nodes` are unique names; `links` connect them by name. Multi-layer is fine (source → hub → sinks).
```js
{ nodes:[{name:'硬件'},{name:'订阅'},{name:'服务'},{name:'营收'},{name:'研发'},{name:'销售'},{name:'管理'},{name:'经营利润'}],
  links:[{source:'硬件',target:'营收',value:40},{source:'订阅',target:'营收',value:35},{source:'服务',target:'营收',value:25},
         {source:'营收',target:'研发',value:30},{source:'营收',target:'销售',value:22},{source:'营收',target:'管理',value:12},{source:'营收',target:'经营利润',value:36}] }
```
