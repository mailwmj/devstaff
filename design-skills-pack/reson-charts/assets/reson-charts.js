/*!
 * reson-charts — Bloome-native research chart library
 * One API:  ResonChart.render(elOrId, { type, data, title?, height?, options? })
 * Requires: echarts v5 loaded globally (window.echarts). SVG-only charts need no dep.
 * Design:   bakes in bloome-widget-design tokens (light + dark). Agents pass DATA only.
 */
(function (global) {
  'use strict';

  // ---- Bloome design tokens (brand + 8-color support palette) ----
  var BRAND = { blue: '#2556B6', orange: '#F36440' };
  var SUPPORT = ['#ADC8E6', '#F49F6A', '#FFD15C', '#BAC78D', '#7A68BF', '#D8D8D8']; // sky ochre amber olive purple grey
  var PALETTE = [
    BRAND.blue,
    '#ADC8E6',
    BRAND.orange,
    '#FFD15C',
    '#BAC78D',
    '#7A68BF',
    '#F49F6A',
    '#D8D8D8',
  ];
  var FONT = "'Sora',system-ui,-apple-system,sans-serif";

  // User/widget customization. Empty = pure Bloome defaults (brand-compliant).
  // ResonChart.configure({ palette:[...], brand:{blue,orange}, light:{...}, dark:{...} })
  var OVERRIDE = {};
  var activePAL = PALETTE; // current palette used by color(); set per-draw from theme()

  function theme() {
    var d = global.matchMedia && global.matchMedia('(prefers-color-scheme: dark)').matches;
    var pal = OVERRIDE.palette || PALETTE;
    var tk = (d ? OVERRIDE.dark : OVERRIDE.light) || {};
    var blue = (OVERRIDE.brand && OVERRIDE.brand.blue) || pal[0];
    var orange = (OVERRIDE.brand && OVERRIDE.brand.orange) || pal[2] || BRAND.orange;
    return {
      dark: d,
      ink: tk.ink || (d ? 'rgba(255,255,255,.95)' : '#000'),
      sec: tk.sec || (d ? 'rgba(255,255,255,.70)' : 'rgba(0,0,0,.75)'),
      muted: tk.muted || (d ? 'rgba(255,255,255,.45)' : 'rgba(0,0,0,.45)'),
      grid: tk.grid || (d ? 'rgba(255,255,255,.08)' : 'rgba(0,0,0,.06)'),
      card: tk.card || (d ? '#171717' : '#fff'),
      blue: blue,
      orange: orange,
      sky: pal[1] || SUPPORT[0],
      amber: pal[3] || SUPPORT[2],
      olive: pal[4] || SUPPORT[3],
      purple: pal[5] || SUPPORT[4],
      grey: pal[pal.length - 1] || SUPPORT[5],
      PAL: pal,
    };
  }

  var instances = [];
  function el(target) {
    var n = typeof target === 'string' ? document.getElementById(target) : target;
    if (!n) throw new Error('reson-charts: target element not found: ' + target);
    return n;
  }
  function ec(node, option, t) {
    if (!global.echarts) throw new Error('reson-charts: echarts not loaded');
    var inst = global.echarts.init(node);
    option.textStyle = Object.assign({ fontFamily: FONT, color: t.sec }, option.textStyle || {});
    inst.setOption(option);
    instances.push(inst);
    return inst;
  }
  function axisX(t, extra) {
    return Object.assign(
      {
        type: 'category',
        axisLine: { lineStyle: { color: t.grid } },
        axisTick: { show: false },
        axisLabel: { color: t.muted, fontSize: 11 },
      },
      extra || {},
    );
  }
  function axisY(t, extra) {
    return Object.assign(
      {
        type: 'value',
        splitLine: { lineStyle: { color: t.grid } },
        axisLabel: { color: t.muted, fontSize: 11 },
      },
      extra || {},
    );
  }
  function legend(t, data) {
    return {
      data: data,
      bottom: 0,
      textStyle: { color: t.sec, fontSize: 11 },
      icon: 'roundRect',
      itemWidth: 11,
      itemHeight: 11,
    };
  }
  function color(i) {
    return activePAL[i % activePAL.length];
  }
  // Built-in chart labels. Neutral-English defaults; agent overrides per-chart via
  // options.labels to match the widget's language (e.g. {total:'合计',inc:'量增'}).
  function lbl(o, key, def) {
    return o && o.labels && o.labels[key] != null ? o.labels[key] : def;
  }
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
    });
  }

  // ============ RENDERERS (type -> fn(node, data, options, t)) ============
  var R = {};

  // 1 line
  R.line = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: { trigger: 'axis' },
        legend: legend(
          t,
          d.series.map(function (s) {
            return s.name;
          }),
        ),
        grid: { left: 6, right: 10, top: 14, bottom: 34, containLabel: true },
        xAxis: axisX(t, { data: d.categories }),
        yAxis: axisY(t),
        series: d.series.map(function (s, i) {
          return {
            name: s.name,
            type: 'line',
            smooth: true,
            data: s.data,
            symbol: 'circle',
            symbolSize: 5,
            lineStyle: { width: 3, color: color(i) },
            itemStyle: { color: color(i) },
          };
        }),
      },
      t,
    );
  };
  // 2 column
  R.column = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: 6, right: 10, top: 20, bottom: 24, containLabel: true },
        xAxis: axisX(t, { data: d.categories }),
        yAxis: axisY(t),
        series: [
          {
            type: 'bar',
            data: d.data,
            barWidth: '52%',
            itemStyle: { color: t.blue, borderRadius: [6, 6, 0, 0] },
            label: { show: true, position: 'top', color: t.muted, fontSize: 11 },
          },
        ],
      },
      t,
    );
  };
  // 3 clustered
  R.clustered = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: legend(
          t,
          d.series.map(function (s) {
            return s.name;
          }),
        ),
        grid: { left: 6, right: 10, top: 14, bottom: 34, containLabel: true },
        xAxis: axisX(t, { data: d.categories }),
        yAxis: axisY(t),
        series: d.series.map(function (s, i) {
          return {
            name: s.name,
            type: 'bar',
            data: s.data,
            itemStyle: { color: color(i), borderRadius: [4, 4, 0, 0] },
          };
        }),
      },
      t,
    );
  };
  // 4 stacked
  R.stacked = function (n, d, o, t) {
    var last = d.series.length - 1;
    ec(
      n,
      {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: legend(
          t,
          d.series.map(function (s) {
            return s.name;
          }),
        ),
        grid: { left: 6, right: 10, top: 14, bottom: 34, containLabel: true },
        xAxis: axisX(t, { data: d.categories }),
        yAxis: axisY(t),
        series: d.series.map(function (s, i) {
          return {
            name: s.name,
            type: 'bar',
            stack: 'x',
            data: s.data,
            itemStyle: { color: color(i), borderRadius: i === last ? [4, 4, 0, 0] : 0 },
          };
        }),
      },
      t,
    );
  };
  // 5 table  data:{columns:[], rows:[[]], posCol?:index}
  R.table = function (n, d, o, t) {
    var pc = d.posCol;
    var head =
      '<tr>' +
      d.columns
        .map(function (c) {
          return '<th>' + esc(c) + '</th>';
        })
        .join('') +
      '</tr>';
    var body = d.rows
      .map(function (r, ri) {
        return (
          '<tr>' +
          r
            .map(function (cell, ci) {
              var cls = ci === pc ? ' class="rc-pos"' : '';
              return '<td' + cls + '>' + esc(cell) + '</td>';
            })
            .join('') +
          '</tr>'
        );
      })
      .join('');
    n.innerHTML =
      '<table class="rc-dt">' + '<thead>' + head + '</thead><tbody>' + body + '</tbody></table>';
  };
  // 6 waterfall  data:{steps:[{label,value,type:'total'|'inc'|'dec'}]}
  R.waterfall = function (n, d, o, t) {
    var cum = 0,
      base = [],
      tot = [],
      inc = [],
      dec = [],
      lvl = [];
    d.steps.forEach(function (s) {
      if (s.type === 'total') {
        base.push(0);
        tot.push(s.value);
        inc.push('-');
        dec.push('-');
        cum = s.value;
      } else if (s.type === 'inc') {
        base.push(cum);
        inc.push(s.value);
        tot.push('-');
        dec.push('-');
        cum += s.value;
      } else {
        cum -= s.value;
        base.push(cum);
        dec.push(s.value);
        tot.push('-');
        inc.push('-');
      }
      lvl.push(cum); // carry-over level after this step (for connectors)
    });
    // think-cell-style connectors: horizontal dotted line at each carry level,
    // spanning the gap from bar i to bar i+1.
    var connectors = lvl.slice(0, -1).map(function (y, i) {
      return [{ coord: [i, y] }, { coord: [i + 1, y] }];
    });
    var L = { show: true, position: 'top', fontSize: 10, fontWeight: 500 };
    ec(
      n,
      {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: 6, right: 10, top: 18, bottom: 20, containLabel: true },
        xAxis: axisX(t, {
          data: d.steps.map(function (s) {
            return s.label;
          }),
          axisLabel: { color: t.muted, fontSize: 10 },
        }),
        yAxis: axisY(t),
        series: [
          {
            type: 'bar',
            stack: 'a',
            itemStyle: { color: 'transparent' },
            emphasis: { itemStyle: { color: 'transparent' } },
            data: base,
            markLine: {
              silent: true,
              symbol: 'none',
              lineStyle: { type: 'dotted', color: t.muted, width: 1 },
              label: { show: false },
              data: connectors,
            },
          },
          {
            name: lbl(o, 'total', 'Total'),
            type: 'bar',
            stack: 'a',
            barWidth: '55%',
            itemStyle: { color: t.blue, borderRadius: [4, 4, 0, 0] },
            label: Object.assign({ color: t.blue }, L),
            data: tot,
          },
          {
            name: lbl(o, 'inc', 'Increase'),
            type: 'bar',
            stack: 'a',
            itemStyle: { color: t.sky, borderRadius: [4, 4, 0, 0] },
            label: Object.assign({ formatter: '+{c}', color: t.dark ? t.sky : t.blue }, L),
            data: inc,
          },
          {
            name: lbl(o, 'dec', 'Decrease'),
            type: 'bar',
            stack: 'a',
            itemStyle: { color: t.orange },
            label: {
              show: true,
              position: 'bottom',
              formatter: '-{c}',
              fontSize: 10,
              color: t.orange,
            },
            data: dec,
          },
        ],
      },
      t,
    );
  };
  // 7 doughnut  data:{data:[{name,value}]}
  R.doughnut = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: {
          trigger: 'item',
          formatter: function (p) {
            return esc(p.name) + ': ' + esc(p.percent) + '%';
          },
        },
        legend: legend(t),
        series: [
          {
            type: 'pie',
            radius: ['46%', '70%'],
            center: ['50%', '44%'],
            avoidLabelOverlap: true,
            itemStyle: { borderColor: t.card, borderWidth: 3 },
            label: { formatter: '{b}\n{d}%', fontSize: 11, color: t.sec },
            data: d.data.map(function (x, i) {
              return { value: x.value, name: x.name, itemStyle: { color: color(i) } };
            }),
          },
        ],
      },
      t,
    );
  };
  // 8 scatter  data:{points:[[x,y,label]], xName,yName}
  R.scatter = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: {
          formatter: function (p) {
            return (
              esc(p.data[2] || '') +
              '<br/>' +
              esc(d.xName || 'x') +
              ' ' +
              esc(p.data[0]) +
              ' · ' +
              esc(d.yName || 'y') +
              ' ' +
              esc(p.data[1])
            );
          },
        },
        grid: { left: 6, right: 14, top: 16, bottom: 36, containLabel: true },
        xAxis: axisX(t, {
          type: 'value',
          name: d.xName,
          nameLocation: 'middle',
          nameGap: 24,
          nameTextStyle: { color: t.muted },
          splitLine: { lineStyle: { color: t.grid } },
        }),
        yAxis: axisY(t, { name: d.yName }),
        series: [
          {
            type: 'scatter',
            symbolSize: 16,
            data: d.points,
            itemStyle: { color: t.blue, opacity: 0.85 },
            label: {
              show: true,
              formatter: function (p) {
                return p.data[2] || '';
              },
              position: 'right',
              fontSize: 10,
              color: t.muted,
            },
            markLine: {
              symbol: 'none',
              silent: true,
              lineStyle: { type: 'dashed', color: t.grid },
              label: { show: false },
              data: [
                { type: 'average', valueDim: 'y' },
                { type: 'average', valueDim: 'x' },
              ],
            },
          },
        ],
      },
      t,
    );
  };
  // 9 combo  data:{categories, bar:{name,data}, line:{name,data}}
  R.combo = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        legend: legend(t, [d.bar.name, d.line.name]),
        grid: { left: 6, right: 10, top: 14, bottom: 34, containLabel: true },
        xAxis: axisX(t, { data: d.categories }),
        yAxis: [
          axisY(t),
          {
            type: 'value',
            axisLabel: { formatter: '{value}%', color: t.muted, fontSize: 11 },
            splitLine: { show: false },
          },
        ],
        series: [
          {
            name: d.bar.name,
            type: 'bar',
            data: d.bar.data,
            barWidth: '48%',
            itemStyle: { color: t.sky, borderRadius: [6, 6, 0, 0] },
          },
          {
            name: d.line.name,
            type: 'line',
            yAxisIndex: 1,
            smooth: true,
            data: d.line.data,
            lineStyle: { width: 3, color: t.orange },
            itemStyle: { color: t.orange },
          },
        ],
      },
      t,
    );
  };
  // 10 mekko  data:{markets:[{name,size,segments:[v]}], segmentNames:[]}
  R.mekko = function (n, d, o, t) {
    var W = 1000,
      H = 320,
      mT = 6,
      mB = 42,
      mL = 4,
      mR = 4,
      pW = W - mL - mR,
      pH = H - mT - mB;
    var vc = t.PAL;
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%">';
    var x = mL;
    d.markets.forEach(function (m) {
      var w = (pW * m.size) / 100,
        y = mT;
      m.segments.forEach(function (s, i) {
        var h = (pH * s) / 100;
        svg +=
          '<rect x="' +
          x.toFixed(1) +
          '" y="' +
          y.toFixed(1) +
          '" width="' +
          (w - 2).toFixed(1) +
          '" height="' +
          (h - 1).toFixed(1) +
          '" fill="' +
          vc[i % vc.length] +
          '"/>';
        if (h >= 11 && w > 50)
          svg +=
            '<text x="' +
            (x + w / 2).toFixed(1) +
            '" y="' +
            (y + h / 2 + 4).toFixed(1) +
            '" fill="' +
            (i === 0 ? '#fff' : '#000') +
            '" font-size="11" font-weight="500" text-anchor="middle">' +
            s +
            '%</text>';
        y += h;
      });
      svg +=
        '<text x="' +
        (x + w / 2).toFixed(1) +
        '" y="' +
        (H - 24) +
        '" fill="' +
        t.ink +
        '" font-size="12" font-weight="600" text-anchor="middle">' +
        esc(m.name) +
        '</text>';
      svg +=
        '<text x="' +
        (x + w / 2).toFixed(1) +
        '" y="' +
        (H - 9) +
        '" fill="' +
        t.muted +
        '" font-size="10.5" text-anchor="middle">' +
        esc(lbl(o, 'marketSize', 'Size')) +
        ' ' +
        esc(m.size) +
        '%</text>';
      x += w;
    });
    svg += '</svg>';
    var lg =
      '<div class="rc-legend">' +
      (d.segmentNames || [])
        .map(function (v, i) {
          return '<span><i style="background:' + vc[i % vc.length] + '"></i>' + esc(v) + '</span>';
        })
        .join('') +
      '</div>';
    n.innerHTML = svg + lg;
  };
  // 11 gantt  data:{periods:[], tasks:[{name,start,end}]}
  R.gantt = function (n, d, o, t) {
    var W = 1000,
      rowH = 34,
      lblW = 150,
      padR = 12,
      headH = 24,
      nP = d.periods.length,
      colW = (W - lblW - padR) / nP;
    var svg =
      '<svg viewBox="0 0 ' + W + ' ' + (headH + d.tasks.length * rowH + 6) + '" width="100%">';
    d.periods.forEach(function (m, i) {
      var x = lblW + i * colW;
      svg +=
        '<line x1="' +
        x +
        '" y1="' +
        headH +
        '" x2="' +
        x +
        '" y2="' +
        (headH + d.tasks.length * rowH) +
        '" stroke="' +
        t.grid +
        '"/><text x="' +
        (x + colW / 2) +
        '" y="16" text-anchor="middle" font-size="11" fill="' +
        t.muted +
        '">' +
        esc(m) +
        '</text>';
    });
    d.tasks.forEach(function (tk, i) {
      var y = headH + i * rowH + 8;
      svg +=
        '<text x="' +
        (lblW - 10) +
        '" y="' +
        (y + 13) +
        '" text-anchor="end" font-size="12" fill="' +
        t.ink +
        '">' +
        esc(tk.name) +
        '</text><rect x="' +
        (lblW + tk.start * colW).toFixed(1) +
        '" y="' +
        y +
        '" width="' +
        ((tk.end - tk.start) * colW - 4).toFixed(1) +
        '" height="18" rx="6" fill="' +
        color(i) +
        '"/>';
    });
    svg += '</svg>';
    n.innerHTML = svg;
  };
  // 12 bullet  data:{rows:[{label,max,bands:[a,b],measure,target}]}
  R.bullet = function (n, d, o, t) {
    var W = 480,
      rowH = 42,
      lblW = 86,
      padR = 34,
      barH = 14,
      pW = W - lblW - padR;
    var bc = t.dark
      ? ['rgba(255,255,255,.06)', 'rgba(255,255,255,.11)', 'rgba(255,255,255,.18)']
      : ['rgba(0,0,0,.05)', 'rgba(0,0,0,.10)', 'rgba(0,0,0,.16)'];
    var svg = '<svg viewBox="0 0 ' + W + ' ' + d.rows.length * rowH + '" width="100%">';
    d.rows.forEach(function (r, i) {
      var y = i * rowH + rowH / 2,
        sx = function (v) {
          return lblW + (pW * v) / r.max;
        },
        segs = [0].concat(r.bands, [r.max]);
      for (var k = 0; k < segs.length - 1; k++)
        svg +=
          '<rect x="' +
          sx(segs[k]).toFixed(1) +
          '" y="' +
          (y - barH / 2 - 4) +
          '" width="' +
          (sx(segs[k + 1]) - sx(segs[k])).toFixed(1) +
          '" height="' +
          (barH + 8) +
          '" fill="' +
          bc[k] +
          '"/>';
      svg +=
        '<rect x="' +
        lblW +
        '" y="' +
        (y - barH / 4) +
        '" width="' +
        (sx(r.measure) - lblW).toFixed(1) +
        '" height="' +
        barH / 2 +
        '" fill="' +
        t.blue +
        '" rx="2"/>';
      svg +=
        '<rect x="' +
        (sx(r.target) - 1.5).toFixed(1) +
        '" y="' +
        (y - barH / 2 - 4) +
        '" width="3" height="' +
        (barH + 8) +
        '" fill="' +
        t.orange +
        '"/>';
      svg +=
        '<text x="' +
        (lblW - 8) +
        '" y="' +
        (y + 4) +
        '" text-anchor="end" font-size="11.5" font-weight="500" fill="' +
        t.ink +
        '">' +
        esc(r.label) +
        '</text>';
      svg +=
        '<text x="' +
        (W - padR + 5) +
        '" y="' +
        (y + 4) +
        '" font-size="11" font-weight="600" fill="' +
        t.ink +
        '">' +
        esc(r.measure) +
        '</text>';
    });
    svg += '</svg>';
    n.innerHTML =
      svg +
      '<div class="rc-legend"><span><i style="background:' +
      t.blue +
      '"></i>' +
      lbl(o, 'actual', 'Actual') +
      '</span><span><i style="background:' +
      t.orange +
      '"></i>' +
      lbl(o, 'target', 'Target') +
      '</span><span><i style="background:' +
      bc[2] +
      '"></i>' +
      lbl(o, 'range', 'Range') +
      '</span></div>';
  };
  // 13 heatmap  data:{rows:[], cols:[], values:[[]], min,max}
  R.heatmap = function (n, d, o, t) {
    var pts = [];
    for (var i = 0; i < d.rows.length; i++)
      for (var j = 0; j < d.cols.length; j++) pts.push([j, i, d.values[i][j]]);
    ec(
      n,
      {
        tooltip: {
          formatter: function (p) {
            return (
              esc(d.rows[p.data[1]]) +
              ' · ' +
              esc(d.cols[p.data[0]]) +
              '<br/><b>' +
              esc((p.data[2] > 0 ? '+' : '') + p.data[2]) +
              '</b>'
            );
          },
        },
        grid: { left: 6, right: 10, top: 8, bottom: 50, containLabel: true },
        xAxis: axisX(t, { data: d.cols }),
        yAxis: axisX(t, { data: d.rows }),
        visualMap: {
          min: d.min != null ? d.min : -8,
          max: d.max != null ? d.max : 12,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: 0,
          inRange: {
            color: [t.orange, '#F9C9B6', t.dark ? '#1D1D1D' : '#F5F5F5', '#A9C0EA', t.blue],
          },
          textStyle: { color: t.muted, fontSize: 10 },
        },
        series: [
          {
            type: 'heatmap',
            data: pts,
            label: {
              show: true,
              formatter: function (p) {
                return p.data[2];
              },
              fontSize: 10,
              color: t.ink,
            },
            itemStyle: { borderColor: t.card, borderWidth: 3, borderRadius: 4 },
          },
        ],
      },
      t,
    );
  };
  // 14 treemap  data:{data:[{name,value,children:[]}]}
  R.treemap = function (n, d, o, t) {
    var dd = d.data.map(function (x, i) {
      return Object.assign({ itemStyle: { color: color(i) } }, x);
    });
    ec(
      n,
      {
        tooltip: {
          formatter: function (p) {
            return esc(p.name) + ': ' + esc(p.value);
          },
        },
        series: [
          {
            type: 'treemap',
            roam: false,
            nodeClick: false,
            breadcrumb: { show: false },
            label: { fontSize: 12, color: '#fff', fontWeight: 500, formatter: '{b}\n{c}' },
            itemStyle: { borderColor: t.card, borderWidth: 2, gapWidth: 3 },
            levels: [{ itemStyle: { borderWidth: 0, gapWidth: 3 } }],
            data: dd,
          },
        ],
      },
      t,
    );
  };
  // 15 segmented  data:{data:[{name,value}]}
  R.segmented = function (n, d, o, t) {
    var last = d.data.length - 1;
    ec(
      n,
      {
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
          formatter: function (p) {
            return p
              .map(function (x) {
                return esc(x.seriesName) + ': ' + esc(x.value);
              })
              .join('<br/>');
          },
        },
        legend: legend(
          t,
          d.data.map(function (s) {
            return s.name;
          }),
        ),
        grid: { left: 6, right: 16, top: 6, bottom: 34, containLabel: false },
        xAxis: { type: 'value', show: false },
        yAxis: { type: 'category', data: [''], show: false },
        series: d.data.map(function (s, i) {
          return {
            name: s.name,
            type: 'bar',
            stack: 's',
            barWidth: 36,
            data: [s.value],
            itemStyle: {
              color: color(i),
              borderRadius: i === 0 ? [6, 0, 0, 6] : i === last ? [0, 6, 6, 0] : 0,
            },
            label: {
              show: true,
              formatter: s.value + '%',
              color: i === 0 ? '#fff' : '#000',
              fontSize: 11,
              fontWeight: 500,
            },
          };
        }),
      },
      t,
    );
  };
  // 16 lorenz  data:{x:[], y:[]}
  R.lorenz = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: {
          trigger: 'axis',
          formatter: function (p) {
            return p[0].data[0] + '% → <b>' + p[0].data[1] + '%</b>';
          },
        },
        grid: { left: 6, right: 16, top: 14, bottom: 30, containLabel: true },
        xAxis: axisX(t, {
          type: 'value',
          min: 0,
          max: 100,
          name: (o && o.xName) || lbl(o, 'axis', 'Cumulative %'),
          nameLocation: 'middle',
          nameGap: 24,
          nameTextStyle: { color: t.muted },
          splitLine: { show: false },
        }),
        yAxis: axisY(t, { min: 0, max: 100 }),
        series: [
          {
            type: 'line',
            data: [
              [0, 0],
              [100, 100],
            ],
            lineStyle: { type: 'dashed', color: t.grid },
            symbol: 'none',
          },
          {
            type: 'line',
            data: d.x.map(function (v, i) {
              return [v, d.y[i]];
            }),
            smooth: true,
            symbol: 'none',
            lineStyle: { color: t.blue, width: 3 },
            areaStyle: { color: 'rgba(37,86,182,.12)' },
          },
        ],
      },
      t,
    );
  };
  // 17 bubble  data:{series:[{name,points:[[x,y,size,label]]}], xName,yName}
  R.bubble = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: {
          formatter: function (p) {
            return (
              '<b>' +
              esc(p.data[3] || '') +
              '</b><br/>' +
              esc(d.xName || 'x') +
              ' ' +
              esc(p.data[0]) +
              ' · ' +
              esc(d.yName || 'y') +
              ' ' +
              esc(p.data[1])
            );
          },
        },
        legend: legend(
          t,
          d.series.map(function (s) {
            return s.name;
          }),
        ),
        grid: { left: 6, right: 18, top: 14, bottom: 40, containLabel: true },
        xAxis: axisX(t, {
          type: 'value',
          name: d.xName,
          nameGap: 22,
          nameLocation: 'middle',
          nameTextStyle: { color: t.muted },
          splitLine: { lineStyle: { color: t.grid } },
        }),
        yAxis: axisY(t, { name: d.yName }),
        series: d.series.map(function (s, i) {
          return {
            name: s.name,
            type: 'scatter',
            data: s.points,
            symbolSize: function (x) {
              return Math.sqrt(x[2]) / 1.4;
            },
            itemStyle: { color: color(i === 0 ? 0 : 2), opacity: 0.6 },
            label: {
              show: true,
              formatter: function (p) {
                return p.data[3] || '';
              },
              position: 'top',
              fontSize: 10,
              color: t.muted,
            },
          };
        }),
      },
      t,
    );
  };
  // 18 football  data:{methods:[], low:[], high:[], current}
  R.football = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
          formatter: function (p) {
            var i = p[0].dataIndex;
            return esc(d.methods[i]) + '<br/>' + esc(d.low[i]) + ' – ' + esc(d.high[i]);
          },
        },
        grid: { left: 6, right: 30, top: 10, bottom: 24, containLabel: true },
        xAxis: axisY(t, { min: o && o.min, max: o && o.max }),
        yAxis: {
          type: 'category',
          data: d.methods,
          axisLabel: { color: t.sec, fontSize: 12 },
          axisTick: { show: false },
          axisLine: { lineStyle: { color: t.grid } },
        },
        series: [
          {
            type: 'bar',
            stack: 'a',
            itemStyle: { color: 'transparent' },
            emphasis: { itemStyle: { color: 'transparent' } },
            data: d.low,
          },
          {
            type: 'bar',
            stack: 'a',
            barWidth: '52%',
            itemStyle: { color: t.sky, borderRadius: 4 },
            data: d.high.map(function (v, i) {
              return v - d.low[i];
            }),
            label: {
              show: true,
              position: 'right',
              formatter: function (p) {
                return d.high[p.dataIndex];
              },
              color: t.muted,
              fontSize: 11,
            },
            markLine:
              d.current != null
                ? {
                    symbol: 'none',
                    data: [{ xAxis: d.current }],
                    lineStyle: { color: t.orange, width: 2 },
                    label: {
                      formatter: lbl(o, 'current', 'Current') + ' ' + d.current,
                      color: t.orange,
                      position: 'insideEndTop',
                      fontWeight: 500,
                    },
                  }
                : undefined,
          },
        ],
      },
      t,
    );
  };
  // 19 tornado  data:{vars:[], down:[], up:[], xName?}
  R.tornado = function (n, d, o, t) {
    ec(
      n,
      {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: 6, right: 20, top: 10, bottom: 34, containLabel: true },
        xAxis: axisY(t, {
          name: d.xName,
          nameLocation: 'middle',
          nameGap: 24,
          nameTextStyle: { color: t.muted },
          axisLabel: {
            color: t.muted,
            fontSize: 11,
            formatter: function (v) {
              return (v > 0 ? '+' : '') + v;
            },
          },
        }),
        yAxis: {
          type: 'category',
          data: d.vars,
          axisLabel: { color: t.sec, fontSize: 12 },
          axisTick: { show: false },
          axisLine: { lineStyle: { color: t.grid } },
        },
        series: [
          {
            name: lbl(o, 'down', 'Downside'),
            type: 'bar',
            stack: 't',
            data: d.down,
            itemStyle: { color: t.orange, borderRadius: [3, 0, 0, 3] },
            label: {
              show: true,
              position: 'left',
              formatter: '{c}',
              color: t.orange,
              fontSize: 11,
            },
          },
          {
            name: lbl(o, 'up', 'Upside'),
            type: 'bar',
            stack: 't',
            data: d.up,
            itemStyle: { color: t.blue, borderRadius: [0, 3, 3, 0] },
            label: {
              show: true,
              position: 'right',
              formatter: '+{c}',
              color: t.dark ? t.sky : t.blue,
              fontSize: 11,
            },
          },
        ],
      },
      t,
    );
  };
  // 20 sensitivity  data:{rowVar:{name,vals}, colVar:{name,vals}, grid:[[]], highlight:[r,c]}
  R.sensitivity = function (n, d, o, t) {
    var flat = [].concat.apply([], d.grid),
      mn = Math.min.apply(null, flat),
      mx = Math.max.apply(null, flat);
    function col(v) {
      var k = (v - mn) / (mx - mn || 1);
      if (k < 0.5) return 'rgba(243,100,64,' + (0.2 * (1 - k * 2)).toFixed(3) + ')';
      return 'rgba(37,86,182,' + (0.22 * ((k - 0.5) * 2)).toFixed(3) + ')';
    }
    var h =
      '<table class="rc-sens"><thead><tr><td class="rc-corner">' +
      esc(d.rowVar.name) +
      ' ＼ ' +
      esc(d.colVar.name) +
      '</td>';
    d.colVar.vals.forEach(function (c) {
      h += '<th>' + esc(c) + '</th>';
    });
    h += '</tr></thead><tbody>';
    d.grid.forEach(function (row, i) {
      h += '<tr><td class="rc-rowh">' + esc(d.rowVar.vals[i]) + '</td>';
      row.forEach(function (v, j) {
        var hi = d.highlight && d.highlight[0] === i && d.highlight[1] === j;
        h +=
          '<td style="background:' +
          col(v) +
          '">' +
          (hi ? '<b>' + esc(v) + '</b>' : esc(v)) +
          '</td>';
      });
      h += '</tr>';
    });
    h += '</tbody></table>';
    n.innerHTML = h;
  };
  // 21 sources-uses  data:{sources:[{name,value}], uses:[{name,value}], total}
  R['sources-uses'] = function (n, d, o, t) {
    var W = 1000,
      barH = 54,
      gap = 26,
      lblW = 70,
      padR = 10,
      pW = W - lblW - padR,
      total = d.total;
    function bar(items, y, title) {
      var x = lblW,
        s =
          '<text x="0" y="' +
          (y + barH / 2 + 4) +
          '" font-size="13" font-weight="600" fill="' +
          t.ink +
          '">' +
          title +
          '</text>';
      items.forEach(function (it, i) {
        var w = (pW * it.value) / total,
          c = color(i);
        s +=
          '<rect x="' +
          x.toFixed(1) +
          '" y="' +
          y +
          '" width="' +
          (w - 1.5).toFixed(1) +
          '" height="' +
          barH +
          '" rx="4" fill="' +
          c +
          '"/>';
        if (w > 60) {
          var tc = c === t.blue || c === t.orange ? '#fff' : '#000';
          s +=
            '<text x="' +
            (x + w / 2).toFixed(1) +
            '" y="' +
            (y + barH / 2 - 2) +
            '" text-anchor="middle" font-size="11" font-weight="500" fill="' +
            tc +
            '">' +
            esc(it.name) +
            '</text><text x="' +
            (x + w / 2).toFixed(1) +
            '" y="' +
            (y + barH / 2 + 13) +
            '" text-anchor="middle" font-size="10.5" fill="' +
            tc +
            '" opacity=".85">' +
            esc(it.value) +
            '</text>';
        }
        x += w;
      });
      return s;
    }
    n.innerHTML =
      '<svg viewBox="0 0 ' +
      W +
      ' ' +
      (barH * 2 + gap + 12) +
      '" width="100%">' +
      bar(d.sources, 0, lbl(o, 'sources', 'Sources')) +
      bar(d.uses, barH + gap, lbl(o, 'uses', 'Uses')) +
      '<text x="' +
      (W - padR) +
      '" y="' +
      (barH + gap + barH + 10) +
      '" text-anchor="end" font-size="11" fill="' +
      t.muted +
      '">' +
      esc(lbl(o, 'balanced', 'Balances to')) +
      ' ' +
      esc(total) +
      '</text></svg>';
  };
  // 22 sparkline  data:{items:[{label,data,delta,up}]}
  R.sparkline = function (n, d, o, t) {
    function sp(a, up) {
      var w = 160,
        h = 42,
        p = 4,
        mn = Math.min.apply(null, a),
        mx = Math.max.apply(null, a),
        rg = mx - mn || 1;
      var pts = a.map(function (v, i) {
        return [p + (i * (w - 2 * p)) / (a.length - 1), h - p - ((v - mn) / rg) * (h - 2 * p)];
      });
      var path = pts
        .map(function (q, i) {
          return (i ? 'L' : 'M') + q[0].toFixed(1) + ' ' + q[1].toFixed(1);
        })
        .join(' ');
      var c = up ? t.blue : t.orange;
      var area =
        'M' +
        pts[0][0] +
        ' ' +
        h +
        ' ' +
        pts
          .map(function (q) {
            return 'L' + q[0].toFixed(1) + ' ' + q[1].toFixed(1);
          })
          .join(' ') +
        ' L' +
        pts[pts.length - 1][0] +
        ' ' +
        h +
        ' Z';
      return (
        '<svg width="' +
        w +
        '" height="' +
        h +
        '"><path d="' +
        area +
        '" fill="' +
        c +
        '" opacity=".10"/><path d="' +
        path +
        '" fill="none" stroke="' +
        c +
        '" stroke-width="2"/><circle cx="' +
        pts[pts.length - 1][0].toFixed(1) +
        '" cy="' +
        pts[pts.length - 1][1].toFixed(1) +
        '" r="2.6" fill="' +
        c +
        '"/></svg>'
      );
    }
    n.innerHTML =
      '<div style="display:grid;grid-template-columns:repeat(' +
      d.items.length +
      ',1fr);gap:16px">' +
      d.items
        .map(function (it) {
          return (
            '<div><div style="font-size:11px;color:' +
            t.muted +
            '">' +
            esc(it.label) +
            '</div><div style="font-size:14px;font-weight:600;color:' +
            (it.up ? (t.dark ? t.sky : t.blue) : t.orange) +
            '">' +
            esc(it.delta || '') +
            '</div>' +
            sp(it.data, it.up) +
            '</div>'
          );
        })
        .join('') +
      '</div>';
  };
  // 23 kpi  data:{stats:[{name,value,sub}]}
  R.kpi = function (n, d, o, t) {
    var cols = [t.blue, t.orange, t.purple, t.olive];
    n.innerHTML =
      '<div style="display:grid;grid-template-columns:repeat(' +
      d.stats.length +
      ',1fr);gap:16px">' +
      d.stats
        .map(function (s, i) {
          var c = cols[i % cols.length],
            on = c === t.olive ? '#000' : '#fff';
          return (
            '<div style="background:' +
            c +
            ';border-radius:12px;padding:18px 16px"><div style="font-size:30px;font-weight:600;letter-spacing:-1px;color:' +
            on +
            ';line-height:1.05">' +
            esc(s.value) +
            '</div><div style="font-size:11px;color:' +
            on +
            ';opacity:.85;margin-top:8px">' +
            esc(s.name) +
            (s.sub ? ' · ' + esc(s.sub) : '') +
            '</div></div>'
          );
        })
        .join('') +
      '</div>';
  };
  // 24 source-attribution  data:{parts:[{t}|{fig,src}], note?}  (auto-numbers footnotes + hover)
  R['source-attribution'] = function (n, d, o, t) {
    var notes = [],
      html = '<div class="rc-src">';
    (d.parts || []).forEach(function (p) {
      if (p.src) {
        var i = notes.length + 1;
        notes.push('[' + i + '] ' + esc(p.src));
        html +=
          '<span class="rc-fig">' +
          esc(p.fig != null ? p.fig : '') +
          '</span>' +
          '<span class="rc-mark">' +
          i +
          '<span class="rc-tip">' +
          esc(p.src) +
          '</span></span>';
      } else {
        html += esc(p.t || '');
      }
    });
    html += '</div>';
    if (notes.length) html += '<div class="rc-note">' + notes.join('　') + '</div>';
    if (d.note) html += '<div class="rc-note">' + esc(d.note) + '</div>';
    n.innerHTML = html;
  };
  // 25 cagr  data:{categories:[], values:[]}  (auto-computes CAGR + last YoY)
  R.cagr = function (n, d, o, t) {
    var rev = d.values,
      N = rev.length,
      mx = Math.max.apply(null, rev);
    var cagr = (Math.pow(rev[N - 1] / rev[0], 1 / (N - 1)) - 1) * 100;
    var yoy = (rev[N - 1] / rev[N - 2] - 1) * 100;
    ec(
      n,
      {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: 8, right: 20, top: 68, bottom: 24, containLabel: true },
        xAxis: axisX(t, { data: d.categories }),
        yAxis: axisY(t, { max: Math.ceil((mx * 1.25) / 50) * 50 }),
        series: [
          {
            type: 'bar',
            data: rev,
            barWidth: '46%',
            itemStyle: { color: t.sky, borderRadius: [6, 6, 0, 0] },
            label: { show: true, position: 'top', color: t.muted, fontSize: 11 },
            markLine: {
              silent: true,
              symbol: ['none', 'arrow'],
              symbolSize: 11,
              lineStyle: { color: t.blue, width: 2 },
              label: {
                show: true,
                position: 'middle',
                formatter: 'CAGR  +' + cagr.toFixed(1) + '%',
                color: '#fff',
                backgroundColor: t.blue,
                padding: [4, 9],
                borderRadius: 9999,
                fontSize: 12,
                fontWeight: 500,
              },
              data: [
                [{ coord: [0, rev[0] + mx * 0.15] }, { coord: [N - 1, rev[N - 1] + mx * 0.15] }],
              ],
            },
            markPoint: {
              symbol: 'rect',
              symbolSize: [1, 1],
              silent: true,
              data: [
                {
                  coord: [N - 1, rev[N - 1] + mx * 0.24],
                  label: {
                    show: true,
                    formatter: '+' + yoy.toFixed(0) + '% YoY',
                    color: '#fff',
                    backgroundColor: t.orange,
                    padding: [3, 8],
                    borderRadius: 9999,
                    fontSize: 11,
                    fontWeight: 500,
                  },
                },
              ],
            },
          },
        ],
      },
      t,
    );
  };
  // 26 sankey  data:{nodes:[{name,color?}], links:[{source,target,value}]}
  R.sankey = function (n, d, o, t) {
    var nodes = (d.nodes || []).map(function (nd, i) {
      return { name: nd.name, itemStyle: { color: nd.color || color(i), borderWidth: 0 } };
    });
    ec(
      n,
      {
        tooltip: {
          trigger: 'item',
          triggerOn: 'mousemove',
          formatter: function (p) {
            return p.dataType === 'edge'
              ? esc(p.data.source) + ' → ' + esc(p.data.target) + ': ' + esc(p.data.value)
              : esc(p.name);
          },
        },
        series: [
          {
            type: 'sankey',
            left: '4%',
            right: '13%',
            top: 12,
            bottom: 12,
            data: nodes,
            links: d.links || [],
            nodeWidth: 14,
            nodeGap: 12,
            draggable: false,
            emphasis: { focus: 'adjacency' },
            label: { color: t.ink, fontSize: 11, fontFamily: FONT },
            lineStyle: { color: 'source', opacity: 0.4, curveness: 0.5 },
            itemStyle: { borderWidth: 0 },
          },
        ],
      },
      t,
    );
  };

  // ---- public API ----
  var rendered = []; // {node, spec} — kept so we can re-draw on color-scheme change

  function draw(node, spec) {
    var fn = R[spec.type];
    if (!fn)
      throw new Error(
        'reson-charts: unknown type "' + spec.type + '". Known: ' + Object.keys(R).join(', '),
      );
    if (spec.height && spec.height !== 'auto')
      node.style.height = typeof spec.height === 'number' ? spec.height + 'px' : spec.height;
    node.innerHTML = ''; // clear before (re)draw so refresh() doesn't stack
    var t = theme();
    activePAL = t.PAL; // make color(i) use the (possibly overridden) palette
    fn(node, spec.data || {}, spec.options || {}, t);
  }

  // Override the default Bloome palette/tokens (e.g. the user asked for their own brand).
  // Pass nothing / {} to reset to Bloome defaults. Re-draws all live charts.
  function configure(opts) {
    OVERRIDE = opts || {};
    // keep HTML components (table / sensitivity / source-attribution accent) in sync
    if (typeof document !== 'undefined' && document.documentElement) {
      var blue =
        (OVERRIDE.brand && OVERRIDE.brand.blue) || (OVERRIDE.palette && OVERRIDE.palette[0]);
      if (blue) document.documentElement.style.setProperty('--rc-pos', blue);
      else document.documentElement.style.removeProperty('--rc-pos');
    }
    refresh();
  }
  function render(target, spec) {
    if (!spec || !spec.type) throw new Error('reson-charts: spec.type required');
    var node = el(target);
    draw(node, spec);
    rendered.push({ node: node, spec: spec });
    return node;
  }
  // Re-draw every chart against the CURRENT color scheme (dark tokens live-update).
  function refresh() {
    instances.forEach(function (i) {
      try {
        i.dispose();
      } catch (e) {}
    });
    instances = [];
    rendered.forEach(function (r) {
      try {
        draw(r.node, r.spec);
      } catch (e) {}
    });
  }

  // Tokens as CSS vars, with the bloome-widget-design DARK block (§4).
  var CSS = [
    ':root{',
    '--rc-ink:#000;--rc-sec:rgba(0,0,0,.75);--rc-muted:rgba(0,0,0,.45);',
    '--rc-border:rgba(0,0,0,.06);--rc-card:#fff;--rc-muted-bg:#F5F5F5;--rc-pos:#2556B6;}',
    '@media (prefers-color-scheme:dark){:root{',
    '--rc-ink:rgba(255,255,255,.95);--rc-sec:rgba(255,255,255,.70);--rc-muted:rgba(255,255,255,.45);',
    '--rc-border:rgba(255,255,255,.06);--rc-card:#171717;--rc-muted-bg:#1D1D1D;--rc-pos:#ADC8E6;}}',
    '.rc-dt{border-collapse:collapse;font-size:13px;width:100%}',
    '.rc-dt th,.rc-dt td{padding:10px 12px;border-bottom:1px solid var(--rc-border);text-align:right;font-variant-numeric:tabular-nums;color:var(--rc-sec)}',
    '.rc-dt th{color:var(--rc-muted);font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:.4px}',
    '.rc-dt td:first-child,.rc-dt th:first-child{text-align:left;color:var(--rc-ink)}',
    '.rc-dt tr:last-child td{border-bottom:none;font-weight:600;color:var(--rc-ink)}',
    '.rc-pos{color:var(--rc-pos);font-weight:500}',
    '.rc-legend{display:flex;gap:18px;margin-top:12px;font-size:12px;flex-wrap:wrap;color:var(--rc-sec)}',
    '.rc-legend i{width:11px;height:11px;border-radius:3px;display:inline-block;margin-right:6px;vertical-align:-1px}',
    '.rc-sens{border-collapse:collapse;font-size:13px;width:100%}',
    '.rc-sens th,.rc-sens td{border:1px solid var(--rc-card);padding:9px 8px;text-align:center;font-variant-numeric:tabular-nums;color:var(--rc-sec)}',
    '.rc-sens td b{color:var(--rc-ink)}',
    '.rc-sens th,.rc-sens .rc-rowh{background:var(--rc-muted-bg);color:var(--rc-muted);font-weight:500;font-size:11px}',
    '.rc-corner{font-size:11px;color:var(--rc-muted)}',
    '.rc-src{font-size:15px;line-height:1.9;color:var(--rc-ink)}',
    '.rc-fig{font-weight:600}',
    '.rc-mark{position:relative;cursor:help;font-size:11px;font-weight:600;color:var(--rc-pos);vertical-align:super;margin-left:1px}',
    '.rc-mark .rc-tip{visibility:hidden;opacity:0;transition:.15s;position:absolute;bottom:135%;left:50%;transform:translateX(-50%);background:var(--rc-ink);color:var(--rc-card);font-weight:400;font-size:12px;line-height:1.5;padding:8px 11px;border-radius:8px;width:220px;text-align:left;z-index:10;white-space:normal}',
    '.rc-mark:hover .rc-tip{visibility:visible;opacity:1}',
    '.rc-note{font-size:11px;color:var(--rc-muted);margin-top:12px;padding-top:8px;border-top:1px dashed var(--rc-border)}',
    'svg text{font-family:' + FONT + '}',
  ].join('');
  function injectCSS() {
    if (document.getElementById('rc-css')) return;
    var s = document.createElement('style');
    s.id = 'rc-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }
  if (typeof document !== 'undefined') {
    injectCSS();
    global.addEventListener('resize', function () {
      instances.forEach(function (i) {
        i.resize();
      });
    });
    if (global.matchMedia)
      global.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', refresh);
  }

  global.ResonChart = {
    render: render,
    refresh: refresh,
    configure: configure,
    types: Object.keys(R),
    tokens: { brand: BRAND, support: SUPPORT, palette: PALETTE, font: FONT },
  };
})(typeof window !== 'undefined' ? window : this);
