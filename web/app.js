const state = {
  data: null,
  range: 'all',
  seriesKey: null,
  seriesByDate: {},
  comparison: { fundCode: '006985', range: '60', selectedDate: null }
};
const bands = { low: '压力较低', watch: '需要关注', high: '压力较高', insufficient: '数据不足' };
const componentLabels = { rate: '利率', credit: '信用', funding: '融资' };
const bondClassLabels = { credit: '信用债', rate: '利率债', other: '其他' };
const bondTypeLabels = {
  bank_t2: '银行二级资本债',
  policy_bank: '政策性金融债',
  bank_cd: '同业存单',
  short_credit: '短期融资券',
  enterprise: '企业债'
};
const metricFallbackLabels = {
  spread_perp_cdb_5: '银行永续债 − 国开债 5Y',
  bank_perp_yield_5: '银行永续债 AAA- 5Y',
  r007: 'R007'
};
const correlationStrengthLabels = {
  very_weak: '很弱', weak: '较弱', moderate: '中等', strong: '较强',
  very_strong: '很强', insufficient: '样本不足', constant: '无法计算'
};

const fmt = (value, digits = 2) => value == null ? '—' : Number(value).toFixed(digits);
const fmtDate = value => value ? value.replaceAll('-', '.') : '—';
const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const metricLabel = key => state.data.series[key]?.label || metricFallbackLabels[key] || key;
const signedBp = value => value == null ? '较昨日暂无' : `${Number(value) > 0 ? '+' : ''}${fmt(value)} BP`;

function priceDirection(change) {
  if (change == null) return { headline: '价格方向暂无', className: 'neutral' };
  if (Number(change) > 0) return { headline: '债券价格下跌', className: 'price-down' };
  if (Number(change) < 0) return { headline: '债券价格上涨', className: 'price-up' };
  return { headline: '债券价格持平', className: 'neutral' };
}

function marketMetricPresentation(key, point, fallbackLabel = '') {
  if (!point) {
    return { label: fallbackLabel || metricLabel(key), headline: '数据暂无', className: 'neutral', details: [] };
  }
  if (key === 'dr007' || key === 'r007') {
    const change = point.change_1d_bp;
    const direction = change == null ? '融资成本方向暂无' : Number(change) > 0 ? '融资成本上升' : Number(change) < 0 ? '融资成本下降' : '融资成本持平';
    return {
      label: fallbackLabel || metricLabel(key),
      headline: direction,
      className: change == null || Number(change) === 0 ? 'neutral' : Number(change) > 0 ? 'price-down' : 'price-up',
      details: [`利率 ${fmt(point.value, 4)}% · ${signedBp(change)}`]
    };
  }

  const spreadMatch = key.match(/^spread_t2_cdb_(\d+)$/);
  if (spreadMatch) {
    const tenor = spreadMatch[1];
    const yieldKey = `bank_t2_yield_${tenor}`;
    const yieldPoint = state.seriesByDate[yieldKey]?.[point.date] || state.data.series[yieldKey]?.points?.at(-1);
    const direction = priceDirection(yieldPoint?.change_1d_bp);
    return {
      label: `二级资本债 ${tenor}Y`,
      ...direction,
      details: [
        yieldPoint ? `收益率 ${fmt(yieldPoint.value, 4)}% · ${signedBp(yieldPoint.change_1d_bp)}` : '收益率暂无',
        `信用利差 ${fmt(point.value, 2)} BP · ${signedBp(point.change_1d_bp)}`
      ]
    };
  }

  const direction = priceDirection(point.change_1d_bp);
  return {
    label: fallbackLabel || metricLabel(key),
    ...direction,
    details: [`收益率 ${fmt(point.value, 4)}% · ${signedBp(point.change_1d_bp)}`]
  };
}

async function loadDashboard() {
  const response = await fetch(`/data/dashboard.json?t=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`数据读取失败（${response.status}）`);
  state.data = await response.json();
  renderAll();
}

function renderAll() {
  state.seriesByDate = Object.fromEntries(
    Object.entries(state.data.series).map(([key, payload]) => [
      key,
      Object.fromEntries(payload.points.map(point => [point.date, point]))
    ])
  );
  renderFreshness();
  renderFundNavOverview();
  renderFundHoldings();
  setupSeries();
  renderChart();
  setupComparison();
  renderFunds();
  renderQuality();
  document.querySelector('#generated-at').textContent = `页面数据生成：${new Date(state.data.meta.generated_at).toLocaleString('zh-CN')}`;
}

function relatedMetricLines(fund, date) {
  const lines = [];
  const seen = new Set();
  const add = line => {
    if (line && !seen.has(line)) { seen.add(line); lines.push(line); }
  };
  (fund.metric_keys || []).forEach(key => {
    const point = state.seriesByDate[key]?.[date];
    if (!point) return;
    let match = key.match(/^cdb_yield_(\d+)$/);
    if (match) {
      add(`国开债 ${match[1]}Y 收益率 ${fmt(point.value, 4)}% · ${signedBp(point.change_1d_bp)}`);
      return;
    }
    match = key.match(/^spread_t2_cdb_(\d+)$/);
    if (match) {
      const yieldPoint = state.seriesByDate[`bank_t2_yield_${match[1]}`]?.[date];
      if (yieldPoint) add(`二级资本债 ${match[1]}Y 收益率 ${fmt(yieldPoint.value, 4)}% · ${signedBp(yieldPoint.change_1d_bp)}`);
      return;
    }
    match = key.match(/^spread_mtm_cdb_(\d+)$/);
    if (match) {
      const yieldPoint = state.seriesByDate[`mtm_aaa_yield_${match[1]}`]?.[date];
      if (yieldPoint) add(`AAA中票 ${match[1]}Y 收益率 ${fmt(yieldPoint.value, 4)}% · ${signedBp(yieldPoint.change_1d_bp)}`);
      return;
    }
    if (/^spread_perp_cdb_\d+$/.test(key)) return;
    if (key === 'dr007') add(`DR007 融资成本 ${fmt(point.value, 4)}% · ${signedBp(point.change_1d_bp)}`);
  });
  return lines;
}

function metricLineHtml(line) {
  const match = line.match(/^(.*?)([+-]?\d+(?:\.\d+)? BP)$/);
  if (!match) return `<div>${escapeHtml(line)}</div>`;
  const change = Number(match[2].replace(' BP', ''));
  const className = change > 0 ? 'bp-up' : change < 0 ? 'bp-down' : 'bp-flat';
  return `<div>${escapeHtml(match[1])}<span class="${className}">${escapeHtml(match[2])}</span></div>`;
}

function renderFundNavOverview() {
  const root = document.querySelector('#fund-nav-overview');
  const funds = Object.values(state.data.fund_nav_comparison || {});
  if (!funds.length) {
    root.innerHTML = '<article class="fund-nav-empty card">基金净值数据暂无</article>';
    return;
  }
  root.innerHTML = funds.map(fund => {
    const latest = fund.nav_points?.at(-1);
    if (!latest) {
      return `<article class="fund-nav-card card"><div class="fund-nav-code">${escapeHtml(fund.code)}</div><h3>${escapeHtml(fund.name)}</h3><div class="fund-nav-value">—</div><div class="fund-nav-change neutral">最新净值暂无</div></article>`;
    }
    const change = Number(latest.daily_return_pct || 0);
    const changeClass = change > 0 ? 'price-up' : change < 0 ? 'price-down' : 'neutral';
    const changeText = change > 0 ? '当日上涨' : change < 0 ? '当日下跌' : '当日持平';
    const metricLines = relatedMetricLines(fund, latest.date);
    return `<article class="fund-nav-card card">
      <div class="fund-nav-code">${escapeHtml(fund.code)} · 单位净值</div>
      <h3>${escapeHtml(fund.name)}</h3>
      <div class="fund-nav-value">${fmt(latest.unit_nav, 4)}</div>
      <div class="fund-nav-change ${changeClass}">${change > 0 ? '+' : ''}${fmt(change)}% · ${changeText}</div>
      <div class="fund-nav-meta">累计净值 ${fmt(latest.cumulative_nav, 4)} · ${fmtDate(latest.date)} · ${escapeHtml(latest.source)}</div>
      <div class="fund-nav-market"><div class="fund-nav-market-title">同日相关收益率</div>${metricLines.map(metricLineHtml).join('') || '<div>同日市场指标暂无</div>'}</div>
    </article>`;
  }).join('');
}

function renderFundHoldings() {
  const root = document.querySelector('#fund-holdings');
  if (!root) return;
  const funds = state.data.funds || [];
  if (!funds.length) {
    root.innerHTML = '<article class="holdings-empty card">基金持仓数据暂无</article>';
    return;
  }
  const order = ['credit', 'rate', 'other'];
  root.innerHTML = funds.map(fund => {
    const composition = order
      .map(key => [key, fund.bond_composition?.[key]])
      .filter(([, item]) => item && Number(item.weight_pct) > 0);
    const total = composition.reduce((sum, [, item]) => sum + Number(item.weight_pct), 0);
    const [defaultKey, defaultItem] = composition.reduce((best, current) => Number(current[1].weight_pct) > Number(best[1].weight_pct) ? current : best);
    const defaultShare = total ? Number(defaultItem.weight_pct) / total * 100 : 0;
    let pieCursor = 0;
    const slices = composition.map(([key, item]) => {
      const share = total ? Number(item.weight_pct) / total * 100 : 0;
      const start = pieCursor * 3.6;
      pieCursor += share;
      const end = Math.min(pieCursor * 3.6, 359.999);
      return `<path class="bond-slice ${key}${key === defaultKey ? ' is-active' : ''}" data-bond-class="${key}" d="${pieSlicePath(start, end)}" tabindex="0" role="button" aria-label="${escapeHtml(item.label)}，占债券资产 ${fmt(share, 2)}%，占基金净值 ${fmt(item.weight_pct)}%"></path>`;
    }).join('');
    const summaries = composition.map(([key, item]) => {
      const share = total ? Number(item.weight_pct) / total * 100 : 0;
      return `<button class="composition-callout ${key}${key === defaultKey ? ' is-active' : ''}" type="button" data-bond-class="${key}" aria-pressed="${key === defaultKey}">
        <span>${escapeHtml(item.label)}</span><strong>${fmt(share, 2)}%</strong><small>占基金净值 ${fmt(item.weight_pct)}%</small>
      </button>`;
    }).join('');
    const categoryRows = (fund.bond_category_details || []).map(item => `<tr>
      <td>${escapeHtml(item.name)}</td>
      <td><span class="bond-class-chip ${escapeHtml(item.classification)}">${escapeHtml(bondClassLabels[item.classification] || '其他')}</span></td>
      <td>${fmt(item.weight_pct)}%</td>
    </tr>`).join('');
    const topHoldings = (fund.top_holdings || []).map(item => `<li>
      <span class="holding-name">${escapeHtml(item.name)}</span>
      <span class="bond-class-chip ${escapeHtml(item.classification || 'other')}">${escapeHtml(bondClassLabels[item.classification] || '其他')}</span>
      <strong>${item.weight_pct == null ? '—' : `${fmt(item.weight_pct)}%`}</strong>
    </li>`).join('');
    return `<article class="holdings-card" data-fund-code="${escapeHtml(fund.code)}">
      <div class="holdings-card-head">
        <div><span>${escapeHtml(fund.code)}</span><h3>${escapeHtml(fund.name)}</h3></div>
        <strong>债券仓位 ${fmt(fund.bond_exposure_pct)}%</strong>
      </div>
      <div class="composition-visual">
        <p class="composition-title">债券资产内部构成 · 合计 100%</p>
        <div class="composition-layout">
          <div class="composition-callouts">${summaries}</div>
          <div class="composition-pie-stage">
            <svg class="composition-pie" viewBox="0 0 200 200" role="group" aria-label="${escapeHtml(fund.name)}债券资产内部构成，可悬停或聚焦扇区查看明细">${slices}</svg>
            <div class="composition-center" aria-live="polite"><strong>${fmt(defaultShare, 2)}%</strong><span>${escapeHtml(defaultItem.label)}</span></div>
          </div>
        </div>
      </div>
      <section class="composition-drilldown" aria-live="polite">${holdingsDrilldownHtml(fund, defaultKey)}</section>
      <details class="holdings-details">
        <summary>查看全部季报品种与前五大债券</summary>
        <div class="holdings-details-body">
          <h4>按债券品种 · 完整公开汇总</h4>
          <table class="holdings-table"><thead><tr><th>季报品种</th><th>归类</th><th>占净值</th></tr></thead><tbody>${categoryRows}</tbody></table>
          <h4>逐只披露 · 前五大债券</h4>
          <ol class="top-holdings">${topHoldings}</ol>
          <p><a href="${escapeHtml(fund.source_url)}" target="_blank" rel="noreferrer">查看 2026 年三季报 ↗</a></p>
        </div>
      </details>
    </article>`;
  }).join('');

  root.onclick = event => {
    const trigger = event.target.closest('[data-bond-class]');
    if (!trigger || !root.contains(trigger)) return;
    selectBondClass(trigger);
  };
  root.querySelectorAll('.composition-callout, .bond-slice').forEach(trigger => {
    trigger.addEventListener('pointerenter', event => {
      if (event.pointerType !== 'touch') selectBondClass(trigger);
    });
    trigger.addEventListener('focus', () => selectBondClass(trigger));
  });
  root.onkeydown = event => {
    if (!['Enter', ' '].includes(event.key)) return;
    const trigger = event.target.closest('.bond-slice[data-bond-class]');
    if (!trigger) return;
    event.preventDefault();
    selectBondClass(trigger);
  };
}

function piePoint(angle, radius = 96) {
  const radians = (angle - 90) * Math.PI / 180;
  return { x: 100 + radius * Math.cos(radians), y: 100 + radius * Math.sin(radians) };
}

function pieSlicePath(startAngle, endAngle) {
  const start = piePoint(endAngle);
  const end = piePoint(startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M 100 100 L ${start.x.toFixed(3)} ${start.y.toFixed(3)} A 96 96 0 ${largeArc} 0 ${end.x.toFixed(3)} ${end.y.toFixed(3)} Z`;
}

function holdingsDrilldownHtml(fund, classKey) {
  const classItem = fund.bond_composition?.[classKey];
  const classWeight = Number(classItem?.weight_pct || 0);
  const categoryRows = (fund.bond_category_details || [])
    .filter(item => item.classification === classKey)
    .map(item => `<tr><td>${escapeHtml(item.name)}</td><td>${fmt(item.weight_pct)}%</td><td>${fmt(classWeight ? Number(item.weight_pct) / classWeight * 100 : 0, 1)}%</td></tr>`)
    .join('');
  const disclosed = (fund.top_holdings || []).filter(item => item.classification === classKey);
  const disclosedRows = disclosed.length
    ? disclosed.map(item => `<li><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(bondTypeLabels[item.type] || classItem?.label || '债券')}</small></div><span>${item.weight_pct == null ? '—' : `${fmt(item.weight_pct)}%`}</span></li>`).join('')
    : `<li class="drilldown-empty">前五大持仓中暂无${escapeHtml(classItem?.label || '该类别')}债券</li>`;
  return `<div class="drilldown-head"><div><span>当前查看</span><h4>${escapeHtml(classItem?.label || bondClassLabels[classKey] || '债券')}明细</h4></div><strong>占基金净值 ${fmt(classWeight)}%</strong></div>
    <h5>季报完整品种汇总</h5>
    <table class="drilldown-table"><thead><tr><th>债券品种</th><th>占净值</th><th>类别内部</th></tr></thead><tbody>${categoryRows || '<tr><td colspan="3">暂无公开品种数据</td></tr>'}</tbody></table>
    <div class="drilldown-subhead"><h5>已披露具体债券</h5><span>仅限季报前五大持仓</span></div>
    <ul class="drilldown-holdings">${disclosedRows}</ul>`;
}

function selectBondClass(trigger) {
  const card = trigger.closest('.holdings-card');
  const classKey = trigger.dataset.bondClass;
  const fund = (state.data.funds || []).find(item => item.code === card?.dataset.fundCode);
  if (!card || !fund || !fund.bond_composition?.[classKey]) return;
  card.querySelectorAll('[data-bond-class]').forEach(item => {
    const active = item.dataset.bondClass === classKey;
    item.classList.toggle('is-active', active);
    if (item.matches('button')) item.setAttribute('aria-pressed', String(active));
  });
  const total = Object.values(fund.bond_composition || {}).reduce((sum, item) => sum + Number(item?.weight_pct || 0), 0);
  const classItem = fund.bond_composition[classKey];
  const share = total ? Number(classItem.weight_pct) / total * 100 : 0;
  const center = card.querySelector('.composition-center');
  center.querySelector('strong').textContent = `${fmt(share, 2)}%`;
  center.querySelector('span').textContent = classItem.label;
  card.querySelector('.composition-drilldown').innerHTML = holdingsDrilldownHtml(fund, classKey);
}

function renderFreshness() {
  const el = document.querySelector('#freshness');
  const update = state.data.meta.update_status || {};
  const status = update.state === 'ok' ? 'ok' : update.state === 'partial' ? 'partial' : update.state === 'failed' ? 'failed' : 'neutral';
  el.innerHTML = `<span class="status-dot ${status}"></span><span>最新数据至 ${escapeHtml(fmtDate(state.data.meta.latest_data_date))}</span>`;
}

function renderOverview() {
  const root = document.querySelector('#overview');
  const template = document.querySelector('#metric-template');
  root.textContent = '';
  state.data.overview.forEach(item => {
    const node = template.content.cloneNode(true);
    const latest = item.latest;
    const presentation = marketMetricPresentation(item.key, latest, item.label);
    node.querySelector('.metric-label').textContent = presentation.label;
    const direction = node.querySelector('.metric-direction');
    direction.textContent = presentation.headline;
    direction.classList.add(presentation.className);
    node.querySelector('.metric-details').innerHTML = presentation.details
      .map(detail => `<div>${escapeHtml(detail)}</div>`).join('');
    node.querySelector('.metric-meta').textContent = latest ? `${fmtDate(latest.date)} · ${latest.source}` : '等待可用数据';
    root.appendChild(node);
  });
}

function setupSeries() {
  const select = document.querySelector('#series-select');
  const available = Object.entries(state.data.series).filter(([, value]) => value.points.length);
  const previous = state.seriesKey;
  select.innerHTML = available.map(([key, item]) => `<option value="${escapeHtml(key)}">${escapeHtml(item.label)}</option>`).join('');
  state.seriesKey = previous && state.data.series[previous]?.points.length ? previous : 'cgb_yield_10';
  if (!state.data.series[state.seriesKey]?.points.length) state.seriesKey = available[0]?.[0];
  select.value = state.seriesKey;
  select.onchange = event => { state.seriesKey = event.target.value; renderChart(); };
  document.querySelectorAll('[data-range]').forEach(button => {
    button.onclick = () => {
      state.range = button.dataset.range;
      document.querySelectorAll('[data-range]').forEach(item => item.classList.toggle('active', item === button));
      renderChart();
    };
  });
}

function filteredPoints() {
  const points = state.data.series[state.seriesKey]?.points || [];
  if (state.range === 'all' || !points.length) return points;
  const end = new Date(`${points.at(-1).date}T00:00:00`);
  const start = new Date(end); start.setDate(start.getDate() - Number(state.range));
  return points.filter(point => new Date(`${point.date}T00:00:00`) >= start);
}

function renderChart() {
  const svg = document.querySelector('#trend-chart');
  const tooltip = document.querySelector('#chart-tooltip');
  const payload = state.data.series[state.seriesKey];
  const points = filteredPoints();
  if (!points.length) {
    svg.innerHTML = '<text x="450" y="165" text-anchor="middle" class="chart-axis-label">暂无可用数据</text>';
    document.querySelector('#chart-summary').textContent = '该指标尚未接入稳定数据源。';
    return;
  }
  const width = 900, height = 330, left = 62, right = 20, top = 18, bottom = 42;
  const plotW = width - left - right, plotH = height - top - bottom;
  const values = points.map(point => Number(point.value));
  let min = Math.min(...values), max = Math.max(...values);
  const pad = Math.max((max - min) * .12, payload.unit === 'bp' ? 1 : .02);
  min -= pad; max += pad;
  const x = index => left + (points.length === 1 ? plotW / 2 : index / (points.length - 1) * plotW);
  const y = value => top + (max - value) / (max - min) * plotH;
  const path = points.map((point, index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)},${y(point.value).toFixed(2)}`).join(' ');
  const area = `${path} L${x(points.length - 1)},${top + plotH} L${x(0)},${top + plotH} Z`;
  const grid = Array.from({length: 5}, (_, index) => {
    const value = max - index / 4 * (max - min), yy = top + index / 4 * plotH;
    return `<line class="chart-grid" x1="${left}" x2="${width-right}" y1="${yy}" y2="${yy}"/><text class="chart-axis-label" x="${left-10}" y="${yy+4}" text-anchor="end">${fmt(value, payload.unit === 'bp' ? 1 : 2)}</text>`;
  }).join('');
  const tickIndexes = [...new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])];
  const ticks = tickIndexes.map(index => `<text class="chart-axis-label" x="${x(index)}" y="${height-12}" text-anchor="${index === 0 ? 'start' : index === points.length - 1 ? 'end' : 'middle'}">${fmtDate(points[index].date)}</text>`).join('');
  svg.innerHTML = `<defs><linearGradient id="area-gradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="oklch(0.55 0.08 174)" stop-opacity=".22"/><stop offset="1" stop-color="oklch(0.55 0.08 174)" stop-opacity="0"/></linearGradient></defs>${grid}<path class="chart-area" d="${area}"/><path class="chart-line" d="${path}"/><g id="chart-focus" opacity="0"><line class="chart-grid" y1="${top}" y2="${top+plotH}"/><circle class="chart-focus" r="5"/></g>${ticks}<rect class="chart-overlay" x="${left}" y="${top}" width="${plotW}" height="${plotH}"/>`;
  const latest = points.at(-1);
  document.querySelector('#chart-summary').innerHTML = `<strong>${fmt(latest.value, payload.unit === 'bp' ? 1 : 3)} ${payload.unit === 'bp' ? 'BP' : '%'}</strong>　${fmtDate(latest.date)}　单日 ${latest.change_1d_bp == null ? '—' : `${latest.change_1d_bp > 0 ? '+' : ''}${fmt(latest.change_1d_bp)} BP`}　来源 ${escapeHtml(latest.source)}`;
  const overlay = svg.querySelector('.chart-overlay');
  const focus = svg.querySelector('#chart-focus');
  overlay.addEventListener('mousemove', event => {
    const rect = svg.getBoundingClientRect();
    const svgX = (event.clientX - rect.left) / rect.width * width;
    const index = Math.max(0, Math.min(points.length - 1, Math.round((svgX - left) / plotW * (points.length - 1))));
    const point = points[index], xx = x(index), yy = y(point.value);
    focus.setAttribute('opacity', '1');
    focus.querySelector('line').setAttribute('x1', xx); focus.querySelector('line').setAttribute('x2', xx);
    focus.querySelector('circle').setAttribute('cx', xx); focus.querySelector('circle').setAttribute('cy', yy);
    tooltip.innerHTML = `<strong>${fmt(point.value, payload.unit === 'bp' ? 1 : 3)} ${payload.unit === 'bp' ? 'BP' : '%'}</strong>${fmtDate(point.date)}<br>1日 ${point.change_1d_bp == null ? '—' : `${point.change_1d_bp > 0 ? '+' : ''}${fmt(point.change_1d_bp)} BP`}<br>${escapeHtml(point.source)}`;
    tooltip.classList.add('visible');
    const wrap = tooltip.parentElement.getBoundingClientRect();
    tooltip.style.left = `${Math.min(event.clientX - wrap.left + 12, wrap.width - 170)}px`;
    tooltip.style.top = `${Math.max(event.clientY - wrap.top - 74, 4)}px`;
  });
  overlay.addEventListener('mouseleave', () => { focus.setAttribute('opacity', '0'); tooltip.classList.remove('visible'); });
}

function currentComparison() {
  return state.data.fund_nav_comparison?.[state.comparison.fundCode] || null;
}

function setupComparison() {
  const comparisons = state.data.fund_nav_comparison || {};
  const fundSelect = document.querySelector('#comparison-fund');
  const codes = Object.keys(comparisons).filter(code => comparisons[code].nav_points.length);
  if (!codes.length) {
    document.querySelector('.comparison-panel').hidden = true;
    return;
  }
  document.querySelector('.comparison-panel').hidden = false;
  if (!codes.includes(state.comparison.fundCode)) state.comparison.fundCode = codes[0];
  fundSelect.innerHTML = codes.map(code => `<option value="${code}">${escapeHtml(comparisons[code].name)} · ${code}</option>`).join('');
  fundSelect.value = state.comparison.fundCode;
  fundSelect.onchange = event => {
    state.comparison.fundCode = event.target.value;
    state.comparison.selectedDate = comparisons[event.target.value].latest_nav_date;
    renderComparison();
  };
  document.querySelectorAll('[data-comparison-range]').forEach(button => {
    button.classList.toggle('active', button.dataset.comparisonRange === state.comparison.range);
    button.onclick = () => {
      state.comparison.range = button.dataset.comparisonRange;
      document.querySelectorAll('[data-comparison-range]').forEach(item => item.classList.toggle('active', item === button));
      renderComparison();
    };
  });
  document.querySelector('#comparison-prev').onclick = () => shiftComparisonDate(-1);
  document.querySelector('#comparison-next').onclick = () => shiftComparisonDate(1);
  document.querySelector('#comparison-date').onchange = event => selectComparisonDate(event.target.value);
  document.querySelector('#comparison-export').onclick = exportComparisonCsv;
  renderComparison();
}

function selectComparisonDate(requested) {
  const comparison = currentComparison();
  const dates = comparison.nav_points.map(point => point.date);
  if (!dates.length) return;
  if (dates.includes(requested)) {
    state.comparison.selectedDate = requested;
  } else {
    state.comparison.selectedDate = [...dates].reverse().find(date => date <= requested) || dates[0];
  }
  renderComparison();
}

function shiftComparisonDate(offset) {
  const comparison = currentComparison();
  const dates = comparison.nav_points.map(point => point.date);
  const currentIndex = Math.max(0, dates.indexOf(state.comparison.selectedDate));
  const nextIndex = Math.max(0, Math.min(dates.length - 1, currentIndex + offset));
  state.comparison.selectedDate = dates[nextIndex];
  renderComparison();
}

function comparisonNavWindow(comparison) {
  const points = comparison.nav_points;
  if (!points.length) return [];
  const selectedDate = state.comparison.selectedDate || comparison.latest_nav_date;
  const selectedIndex = Math.max(0, points.findIndex(point => point.date === selectedDate));
  if (state.comparison.range === 'all') return points.slice(0, selectedIndex + 1);
  if (state.comparison.range === '365') {
    const end = new Date(`${selectedDate}T00:00:00`);
    const start = new Date(end); start.setDate(start.getDate() - 365);
    return points.slice(0, selectedIndex + 1).filter(point => new Date(`${point.date}T00:00:00`) >= start);
  }
  const size = Number(state.comparison.range);
  return points.slice(Math.max(0, selectedIndex - size + 1), selectedIndex + 1);
}

function metricPointOnDate(key, date) {
  return state.seriesByDate[key]?.[date] || null;
}

function renderComparison() {
  const comparison = currentComparison();
  if (!comparison?.nav_points.length) return;
  if (!state.comparison.selectedDate || !comparison.nav_points.some(point => point.date === state.comparison.selectedDate)) {
    state.comparison.selectedDate = comparison.latest_nav_date;
  }
  const dates = comparison.nav_points.map(point => point.date);
  const selectedIndex = dates.indexOf(state.comparison.selectedDate);
  const dateInput = document.querySelector('#comparison-date');
  dateInput.min = dates[0]; dateInput.max = dates.at(-1); dateInput.value = state.comparison.selectedDate;
  document.querySelector('#comparison-prev').disabled = selectedIndex <= 0;
  document.querySelector('#comparison-next').disabled = selectedIndex >= dates.length - 1;
  const latestNav = comparison.nav_points.at(-1);
  const sourceLabel = latestNav?.source_tier === 'official' ? '官方净值源' : '备用净值源';
  document.querySelector('#comparison-date-note').textContent = `${sourceLabel} · 画像截止 ${fmtDate(comparison.profile_period_end)}`;
  const navWindow = comparisonNavWindow(comparison);
  renderComparisonDay(comparison);
  renderComparisonChart(comparison, navWindow);
  renderCorrelations(comparison, navWindow);
}

function renderComparisonDay(comparison) {
  const root = document.querySelector('#comparison-day');
  const nav = comparison.nav_points.find(point => point.date === state.comparison.selectedDate);
  if (!nav) { root.innerHTML = ''; return; }
  const navChange = nav.daily_return_pct;
  const navClass = navChange > 0 ? 'pressure' : navChange < 0 ? 'relief' : 'neutral';
  const navDirection = navChange > 0 ? '当日上涨' : navChange < 0 ? '当日下跌' : '当日持平';
  const metricLines = relatedMetricLines(comparison, nav.date);
  root.innerHTML = `<article class="day-card fund-day-card combined-fund-day-card">
    <div class="day-card-label">${escapeHtml(comparison.name)}<br>单位净值</div>
    <div class="day-card-value">${fmt(nav.unit_nav, 4)}</div>
    <div class="day-card-change ${navClass}">${navChange == null ? '日增长率缺失' : `${navChange > 0 ? '+' : ''}${fmt(navChange)}% · ${navDirection}`}</div>
    <div class="day-card-source">累计净值 ${fmt(nav.cumulative_nav, 4)} · ${fmtDate(nav.date)} · ${escapeHtml(nav.source)}（备用源）</div>
    <div class="day-card-related"><strong>同日相关收益率</strong>${metricLines.map(metricLineHtml).join('') || '<div>同日市场指标暂无</div>'}</div>
  </article>`;
}

function renderComparisonChart(comparison, navPoints) {
  const svg = document.querySelector('#comparison-chart');
  const rows = [
    {
      key: 'fund_return', label: `${comparison.name}日收益`, unit: '%',
      values: navPoints.map(point => point.daily_return_pct)
    },
    ...comparison.metric_keys.map(key => ({
      key,
      label: metricLabel(key),
      unit: 'BP',
      values: navPoints.map(nav => metricPointOnDate(key, nav.date)?.change_1d_bp ?? null)
    }))
  ];
  const width = 980, left = 210, right = 22, top = 28, rowHeight = 68, bottom = 34;
  const height = top + rows.length * rowHeight + bottom;
  const plotWidth = width - left - right;
  const x = index => left + (navPoints.length <= 1 ? plotWidth / 2 : index / (navPoints.length - 1) * plotWidth);
  const rowMarkup = rows.map((row, rowIndex) => {
    const center = top + rowIndex * rowHeight + rowHeight / 2;
    const finite = row.values.filter(value => value != null && Number.isFinite(Number(value))).map(Number);
    const maxAbs = Math.max(...finite.map(Math.abs), row.key === 'fund_return' ? .01 : .05);
    const amplitude = rowHeight / 2 - 10;
    let marks = '';
    if (navPoints.length <= 120) {
      const barWidth = Math.max(1.4, plotWidth / Math.max(navPoints.length, 1) * .64);
      marks = row.values.map((raw, index) => {
        if (raw == null) return '';
        const value = Number(raw), barHeight = Math.max(.7, Math.abs(value) / maxAbs * amplitude);
        const yy = value >= 0 ? center - barHeight : center;
        return `<rect class="sync-bar ${value >= 0 ? 'positive' : 'negative'}" x="${x(index) - barWidth / 2}" y="${yy}" width="${barWidth}" height="${barHeight}"/>`;
      }).join('');
    } else {
      let drawing = false;
      const path = row.values.map((raw, index) => {
        if (raw == null) { drawing = false; return ''; }
        const yy = center - Number(raw) / maxAbs * amplitude;
        const command = drawing ? 'L' : 'M'; drawing = true;
        return `${command}${x(index).toFixed(2)},${yy.toFixed(2)}`;
      }).join(' ');
      marks = `<path class="sync-line" d="${path}"/>`;
    }
    return `<line class="sync-divider" x1="0" x2="${width}" y1="${top + (rowIndex + 1) * rowHeight}" y2="${top + (rowIndex + 1) * rowHeight}"/><line class="sync-zero" x1="${left}" x2="${width - right}" y1="${center}" y2="${center}"/><text class="sync-label" x="18" y="${center - 4}">${escapeHtml(row.label)}</text><text class="sync-unit" x="18" y="${center + 13}">单日变化 · ${row.unit} · ±${fmt(maxAbs)}</text>${marks}`;
  }).join('');
  const tickIndexes = [...new Set([0, Math.floor((navPoints.length - 1) / 2), navPoints.length - 1])].filter(index => index >= 0);
  const ticks = tickIndexes.map(index => `<text class="sync-date-label" x="${x(index)}" y="${height - 10}" text-anchor="${index === 0 ? 'start' : index === navPoints.length - 1 ? 'end' : 'middle'}">${fmtDate(navPoints[index].date)}</text>`).join('');
  const selectedIndex = navPoints.findIndex(point => point.date === state.comparison.selectedDate);
  const cursor = selectedIndex >= 0 ? `<line class="sync-cursor" x1="${x(selectedIndex)}" x2="${x(selectedIndex)}" y1="${top}" y2="${height - bottom}"/>` : '';
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.innerHTML = `${rowMarkup}${ticks}${cursor}<rect class="sync-overlay" x="${left}" y="${top}" width="${plotWidth}" height="${rows.length * rowHeight}"/>`;
  const overlay = svg.querySelector('.sync-overlay');
  overlay.onclick = event => {
    const rect = svg.getBoundingClientRect();
    const svgX = (event.clientX - rect.left) / rect.width * width;
    const index = Math.max(0, Math.min(navPoints.length - 1, Math.round((svgX - left) / plotWidth * (navPoints.length - 1))));
    state.comparison.selectedDate = navPoints[index].date;
    renderComparison();
  };
  svg.onkeydown = event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault(); shiftComparisonDate(event.key === 'ArrowLeft' ? -1 : 1);
    }
  };
}

function pearsonForWindow(navPoints, metricKey) {
  const pairs = navPoints.map(nav => [nav.daily_return_pct, metricPointOnDate(metricKey, nav.date)?.change_1d_bp]).filter(pair => pair[0] != null && pair[1] != null && Number.isFinite(Number(pair[0])) && Number.isFinite(Number(pair[1]))).map(pair => pair.map(Number));
  if (pairs.length < 20) return { r: null, samples: pairs.length, strength: 'insufficient' };
  const leftMean = pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length;
  const rightMean = pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length;
  const numerator = pairs.reduce((sum, pair) => sum + (pair[0] - leftMean) * (pair[1] - rightMean), 0);
  const leftSum = pairs.reduce((sum, pair) => sum + (pair[0] - leftMean) ** 2, 0);
  const rightSum = pairs.reduce((sum, pair) => sum + (pair[1] - rightMean) ** 2, 0);
  const denominator = Math.sqrt(leftSum * rightSum);
  if (denominator <= 1e-15) return { r: null, samples: pairs.length, strength: 'constant' };
  const r = Math.max(-1, Math.min(1, numerator / denominator));
  const absolute = Math.abs(r);
  const strength = absolute < .2 ? 'very_weak' : absolute < .4 ? 'weak' : absolute < .6 ? 'moderate' : absolute < .8 ? 'strong' : 'very_strong';
  return { r, samples: pairs.length, strength };
}

function renderCorrelations(comparison, navPoints) {
  const root = document.querySelector('#correlation-grid');
  const firstDate = navPoints[0]?.date, lastDate = navPoints.at(-1)?.date;
  document.querySelector('#correlation-window').textContent = firstDate ? `${fmtDate(firstDate)} – ${fmtDate(lastDate)} · 窗口随所选日期结束` : '暂无范围';
  root.innerHTML = comparison.metric_keys.map(key => {
    const result = pearsonForWindow(navPoints, key);
    const label = metricLabel(key);
    if (result.r == null) {
      return `<article class="correlation-card"><h4>${escapeHtml(label)}</h4><div class="correlation-value">—</div><div class="correlation-strength">${correlationStrengthLabels[result.strength]}</div><p>${result.samples} 个共同交易日，至少需要20个有效样本。</p></article>`;
    }
    const direction = result.r < 0 ? '负相关' : result.r > 0 ? '正相关' : '无方向';
    const relation = result.r <= -.2 ? '符合常见压力方向' : result.r >= .2 ? '与常见方向相反' : '关系不明显';
    const relationClass = result.r <= -.2 ? 'expected' : result.r >= .2 ? 'opposite' : '';
    return `<article class="correlation-card"><h4>${escapeHtml(label)}</h4><div class="correlation-value">r = ${result.r > 0 ? '+' : ''}${fmt(result.r, 2)}</div><div class="correlation-strength ${relationClass}">${correlationStrengthLabels[result.strength]}${direction} · ${relation}</div><p>${result.samples} 个共同交易日；仅表示样本内同步关系。</p></article>`;
  }).join('');
}

function exportComparisonCsv() {
  const comparison = currentComparison();
  const navPoints = comparisonNavWindow(comparison);
  const rows = [['日期','基金代码','基金名称','单位净值','日收益率%','指标代码','指标名称','指标值','指标单位','指标单日变化BP','净值来源','指标来源']];
  navPoints.forEach(nav => comparison.metric_keys.forEach(key => {
    const point = metricPointOnDate(key, nav.date), payload = state.data.series[key];
    rows.push([nav.date, comparison.code, comparison.name, nav.unit_nav, nav.daily_return_pct ?? '', key, metricLabel(key), point?.value ?? '', payload?.unit || '', point?.change_1d_bp ?? '', nav.source, point?.source || '']);
  }));
  const quote = value => `"${String(value ?? '').replaceAll('"','""')}"`;
  const csv = '\ufeff' + rows.map(row => row.map(quote).join(',')).join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = `${comparison.code}-同日对照-${state.comparison.range}.csv`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function renderFunds() {
  const root = document.querySelector('#funds');
  root.innerHTML = state.data.funds.map(fund => {
    const componentRows = Object.entries(fund.components).map(([key, item]) => `<div class="component"><span>${componentLabels[key]}</span><div class="component-track"><div class="component-fill" style="width:${item.score ?? 0}%"></div></div><strong>${item.score == null ? '—' : Math.round(item.score)}</strong></div>`).join('');
    const detailsRows = Object.entries(fund.components).flatMap(([component, item]) => Object.entries(item.weights).map(([key, weight]) => {
      const metric = item.metrics[key];
      return `<tr><td>${componentLabels[component]} · ${escapeHtml(metricLabel(key))}</td><td>${metric?.latest?.change_1d_bp == null ? '缺失' : `${metric.latest.change_1d_bp > 0 ? '+' : ''}${fmt(metric.latest.change_1d_bp)} BP`}</td><td>${Math.round(weight * 100)}%</td></tr>`;
    })).join('');
    const holdings = fund.top_holdings.map(item => `<li>${escapeHtml(item.name)}${item.weight_pct == null ? '' : ` · ${fmt(item.weight_pct)}%`}</li>`).join('');
    return `<article class="fund-card"><div class="fund-main"><div class="fund-top"><div><span class="fund-code">${fund.code} · ${escapeHtml(fund.manager)}</span><h3 class="fund-name">${escapeHtml(fund.name)}</h3></div><span class="pressure-badge ${fund.band}">${bands[fund.band]}</span></div><div class="score-row"><strong class="score">${fund.score == null ? '—' : Math.round(fund.score)}</strong><span class="score-caption">/ 100<br>综合压力</span></div><div class="component-list">${componentRows}</div><p class="fund-summary">${escapeHtml(fund.holdings_summary)}</p><div class="profile-meta"><span class="meta-chip">画像 ${fmtDate(fund.report_period_end)}</span><span class="meta-chip">可信度 ${fund.confidence === 'high' ? '高' : fund.confidence === 'medium' ? '中' : '低'}</span><span class="meta-chip">债券 ${fmt(fund.bond_exposure_pct)}%</span></div></div><details class="fund-details"><summary>查看计算依据</summary><div class="details-body"><h4>指标权重与当日变化</h4><table class="weight-table"><thead><tr><th>指标</th><th>变化</th><th>权重</th></tr></thead><tbody>${detailsRows}</tbody></table><h4>公开前五大持仓</h4><ul>${holdings}</ul><p class="muted">报告发布日期 ${fmtDate(fund.published_at)} · ${escapeHtml(fund.source_note)}<br><a href="${escapeHtml(fund.source_url)}" target="_blank" rel="noreferrer">查看公开来源 ↗</a></p></div></details></article>`;
  }).join('');
}

function renderQuality() {
  const labels = { bank_perp_yield_5: '银行永续债 AAA- 5Y 行权曲线', r007: 'R007 加权利率历史序列' };
  const missing = state.data.quality.missing_required;
  document.querySelector('#missing-list').innerHTML = missing.length ? missing.map(key => `<li>${escapeHtml(labels[key] || key)}：尚无稳定接入</li>`).join('') : '<li>核心指标完整</li>';
  document.querySelector('#quality-notes').innerHTML = state.data.quality.notes.map(note => `<li>${escapeHtml(note)}</li>`).join('');
}

async function refreshData() {
  const button = document.querySelector('#refresh-button');
  button.disabled = true; button.querySelector('span:last-child').textContent = '更新中';
  try {
    const response = await fetch('/refresh', { method: 'POST' });
    if (!response.ok && response.status !== 409) throw new Error(`更新请求失败（${response.status}）`);
    await pollStatus();
    await loadDashboard();
  } catch (error) {
    document.querySelector('#freshness').innerHTML = `<span class="status-dot failed"></span><span>${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false; button.querySelector('span:last-child').textContent = '立即更新';
  }
}

async function pollStatus() {
  for (let attempt = 0; attempt < 120; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 1000));
    const response = await fetch(`/status?t=${Date.now()}`, { cache: 'no-store' });
    const status = await response.json();
    document.querySelector('#freshness').innerHTML = `<span class="status-dot ${status.state === 'running' ? 'partial' : status.state}"></span><span>${status.state === 'running' ? '正在抓取与校验…' : '更新完成'}</span>`;
    if (status.state !== 'running') {
      if (status.state === 'failed') throw new Error(status.errors?.[0] || '更新失败');
      return;
    }
  }
  throw new Error('更新仍在运行，请稍后刷新页面');
}

document.querySelector('#refresh-button').addEventListener('click', refreshData);
loadDashboard().catch(error => {
  document.querySelector('#main').innerHTML = `<section class="panel"><h2>数据暂时无法读取</h2><p>${escapeHtml(error.message)}</p><p>请先运行 <code>python3 app.py update</code>。</p></section>`;
});
