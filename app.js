/* Отрисовка дашборда роли из data.json. Без внешних библиотек. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const UD = { 'млн грн': 1, 'тыс. грн': 2, '%': 1, 'дни': 1, 'x': 2, 'ТТ': 0, 'т': 0, 'чел': 0, 'шт': 0, 'раз/год': 1 };
  const nfCache = {};
  const fmt = (v, d) => {
    if (v === null || v === undefined || !isFinite(v)) return '—';
    nfCache[d] = nfCache[d] || new Intl.NumberFormat('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d });
    return nfCache[d].format(v);
  };
  const decOf = (r) => {
    let d = UD[r.unit] ?? 1;
    if (r.unit === '%' && Math.abs(r.mtd_plan ?? 10) < 10) d = 2;
    if (r.unit === 'шт' && Math.abs(r.mtd ?? 100) < 100) d = 1;
    return d;
  };
  const pct = (v) => (v === null || v === undefined ? '—' : fmt(v * 100, 1) + '%');
  const light = (x, th) => (x === null || x === undefined ? 'na' : x >= th.green ? 'green' : x >= th.yellow ? 'yellow' : 'red');
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
  const dot = (c) => el('i', 'dot ' + c);
  const dateRu = (s) => s.slice(8, 10) + '.' + s.slice(5, 7) + '.' + s.slice(0, 4);

  const COLS = [
    ['kpi', '', 'Показатель', 1, 'k'], ['section', '', 'Блок', 0, 'tx'], ['unit', '', 'Ед.', 1, 'tx'],
    ['year_plan', 'Год', 'План', 0, '', 1], ['month_plan', 'Месяц', 'План', 1, '', 1],
    ['day_plan', 'День', 'План', 0, '', 2], ['day', '', 'Факт', 0, '', 2], ['day_pct', '', '%', 0, 'p', 2],
    ['week_plan', 'Неделя', 'План', 0, '', 3], ['week', '', 'Факт', 0, '', 3], ['week_pct', '', '%', 0, 'p', 3],
    ['mtd_plan', 'Месяц нараст.', 'План', 1, '', 4], ['mtd', '', 'Факт', 1, '', 4], ['mtd_pct', '', '%', 1, 'p', 4], ['yoy', '', 'г/г', 1, 'y', 4],
    ['fc_month', 'Прогноз месяца', 'Прогноз', 1, '', 5], ['fc_month_pct', '', '% плана', 1, 'pl:light_month', 5],
    ['need_day', '', 'Нужно/день', 0, '', 5], ['run_day', '', 'Сейчас/день', 0, '', 5],
    ['ytd_plan', 'Год нараст.', 'План', 0, '', 6], ['ytd', '', 'Факт', 1, '', 6], ['ytd_pct', '', '%', 1, 'p', 6],
    ['fc_year', 'Прогноз года', 'Прогноз', 1, '', 7], ['fc_year_pct', '', '% плана', 1, 'pl:light_year', 7],
    ['best', '', 'Лучшая практика', 0, 'tx wrap'],
  ];

  function yoyCell(td, r) {
    const v = r.yoy;
    if (v === null || v === undefined) { td.textContent = '—'; return; }
    const s = v > 0 ? '+' : v < 0 ? '−' : '';
    td.textContent = r.kind === 'flow' ? s + fmt(Math.abs(v) * 100, 1) + '%'
      : r.unit === '%' ? s + fmt(Math.abs(v), 1) + ' п.п.' : s + fmt(Math.abs(v), decOf(r)) + ' ' + (r.unit === 'дни' ? 'дн.' : r.unit);
    if (v !== 0) td.classList.add((v > 0) === (r.dir === 'up') ? 'c-green' : 'c-red');
  }

  function table(data) {
    const t = $('table'); t.replaceChildren();
    const th = data.meta.thresholds;
    const hr = t.createTHead().insertRow();
    // подпись группы (День, Неделя…) — над первым видимым столбцом группы и в полном, и в компактном виде
    const gName = {}, gFull = {}, gComp = {};
    COLS.forEach(([f, g, l, c, kind, grp], i) => {
      if (!grp) return;
      if (g) gName[grp] = g;
      if (!(grp in gFull)) gFull[grp] = i;
      if (c && !(grp in gComp)) gComp[grp] = i;
    });
    COLS.forEach(([f, g, l, c, kind, grp], i) => {
      const h = el('th', [kind && kind.startsWith('k') ? 'k' : kind.includes('tx') ? kind : '', c ? '' : 'nc', grp % 2 === 0 ? 'alt' : ''].join(' '));
      const sm = el('small');
      if (grp) {
        const span = (cls) => { const x = el('span', cls, gName[grp]); sm.appendChild(x); };
        if (gFull[grp] === i && gComp[grp] === i) span('');
        else if (gFull[grp] === i) span('g-full');
        else if (gComp[grp] === i) span('g-comp');
      } else sm.textContent = g;
      h.append(sm, document.createTextNode(l));
      hr.appendChild(h);
    });
    const tb = t.createTBody();
    let prev = null;
    data.kpis.forEach((r) => {
      const tr = tb.insertRow();
      if (prev !== null && prev !== r.section) tr.className = 'sec';
      prev = r.section;
      const d = decOf(r);
      COLS.forEach(([f, g, l, c, kind, grp]) => {
        const td = tr.insertCell();
        td.className = [kind === 'k' ? 'k' : kind.includes('tx') ? kind : '', c ? '' : 'nc', grp % 2 === 0 ? 'alt' : ''].join(' ');
        if (kind === 'k' || kind.includes('tx')) td.textContent = r[f] ?? '';
        else if (kind === 'p') { td.textContent = pct(r[f]); if (r[f] != null) td.classList.add('c-' + light(r[f], th)); }
        else if (kind.startsWith('pl:')) { td.append(dot(r[kind.slice(3)] || 'na'), document.createTextNode(pct(r[f]))); }
        else if (kind === 'y') yoyCell(td, r);
        else td.textContent = fmt(r[f], d);
      });
      tr.addEventListener('click', () => {
        const nx = tr.nextElementSibling;
        if (nx && nx.classList.contains('detail')) { nx.remove(); return; }
        const dr = el('tr', 'detail'); const td = el('td'); td.colSpan = COLS.length;
        td.textContent = r.kpi + ': ' + (r.definition || '') + (r.source ? ' · Источник в 1С: ' + r.source : '') + (r.owner ? ' · Ответственный: ' + r.owner : '');
        dr.appendChild(td); tr.after(dr);
      });
    });
  }

  function tiles(data) {
    const box = $('tiles'); box.replaceChildren();
    const th = data.meta.thresholds;
    data.kpis.filter((r) => r.tile).forEach((r) => {
      const d = decOf(r);
      const t = el('div', 'tile');
      const n = el('div', 'n'); n.append(el('span', '', r.kpi));
      const v = el('div', 'v', fmt(r.mtd, d)); v.appendChild(el('span', 'u', r.unit));
      const row = (label, content, cls) => { const e = el('div', 'r'); const b = el('b'); if (cls) b.className = cls; b.append(...content); e.append(el('span', '', label), b); return e; };
      t.append(n, v,
        row('План нараст.', [document.createTextNode(fmt(r.mtd_plan, d))]),
        row('Выполнение', [document.createTextNode(pct(r.mtd_pct))], r.mtd_pct == null ? '' : 'c-' + light(r.mtd_pct, th)),
        row('Прогноз месяца', [dot(r.light_month), document.createTextNode(pct(r.fc_month_pct))]),
        row('Прогноз года', [dot(r.light_year), document.createTextNode(pct(r.fc_year_pct))]));
      box.appendChild(t);
    });
  }

  function alerts(data) {
    const ul = $('alerts'); ul.replaceChildren();
    if (!data.alerts.length) ul.appendChild(el('li', '', 'Все показатели в плане.'));
    data.alerts.slice(0, 8).forEach((a) => {
      const li = el('li'); const s = el('span'); s.append(el('b', '', a.kpi + ': '), document.createTextNode(a.text));
      li.append(dot(a.light), s); ul.appendChild(li);
    });
    if (data.ai_comment) { $('ai').hidden = false; $('ai').textContent = '🤖 ' + data.ai_comment; }
  }

  // ---------- графики (SVG) ----------
  const NS = 'http://www.w3.org/2000/svg';
  const svgEl = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  const niceMax = (v) => { const p = Math.pow(10, Math.floor(Math.log10(v || 1))); for (const m of [1, 1.2, 1.6, 2, 2.4, 3.2, 4, 6, 8, 10]) if (m * p >= v) return m * p; return 10 * p; };
  const tip = $('tip');
  const showTip = (ev, head, lines) => {
    tip.replaceChildren(el('div', 'h', head)); lines.forEach((l) => tip.appendChild(el('div', '', l)));
    tip.style.display = 'block';
    const w = tip.offsetWidth; let x = ev.clientX + 14; if (x + w > window.innerWidth - 8) x = ev.clientX - w - 14;
    tip.style.left = x + 'px'; tip.style.top = (ev.clientY - 10) + 'px';
  };
  const hideTip = () => { tip.style.display = 'none'; };
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function axis(svg, W, H, ml, mr, max) {
    const ticks = [0, .25, .5, .75, 1].map((f) => f * max);
    const y = (v) => H - 24 - (v / max) * (H - 34);
    ticks.forEach((t) => {
      svgEl('line', { x1: ml, x2: W - mr, y1: y(t), y2: y(t), stroke: css('--line') }, svg);
      const tx = svgEl('text', { x: ml - 6, y: y(t) + 4, 'text-anchor': 'end' }, svg); tx.textContent = fmt(t, max >= 10 ? 0 : 1);
    });
    return y;
  }

  function daily(ch) {
    const box = $('chart-daily'); box.replaceChildren();
    $('d-title').textContent = ch.name + ': месяц нарастающим итогом';
    $('d-note').textContent = ch.unit + ' по рабочим дням: факт, план и прогноз по текущему темпу.';
    const rows = ch.rows; if (!rows.length) return;
    const W = Math.max(300, box.clientWidth), H = 260, ml = 52;
    const lastP = rows[rows.length - 1].plan_cum;
    const fcs = rows.filter((r) => r.forecast_cum != null); const lastF = fcs.length ? fcs[fcs.length - 1].forecast_cum : null;
    const mr = 110;
    const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}` }, box);
    const max = niceMax(Math.max(...rows.map((r) => Math.max(r.plan_cum || 0, r.fact_cum || 0, r.forecast_cum || 0))) * 1.03);
    const y = axis(svg, W, H, ml, mr, max);
    const step = (W - ml - mr) / Math.max(1, rows.length - 1);
    const x = (i) => ml + i * step;
    const path = (key) => rows.map((r, i) => (r[key] == null ? null : [x(i), y(r[key])])).filter(Boolean).map((p, i) => (i ? 'L' : 'M') + p[0] + ',' + p[1]).join('');
    svgEl('path', { d: path('plan_cum'), fill: 'none', stroke: css('--ref'), 'stroke-width': 2, 'stroke-dasharray': '4 4' }, svg);
    svgEl('path', { d: path('forecast_cum'), fill: 'none', stroke: css('--acc'), 'stroke-width': 2, 'stroke-dasharray': '5 4', opacity: .8 }, svg);
    svgEl('path', { d: path('fact_cum'), fill: 'none', stroke: css('--acc'), 'stroke-width': 2.2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
    const every = Math.ceil(rows.length / Math.max(2, Math.floor((W - ml - mr) / 52)));
    rows.forEach((r, i) => { if (i % every === 0) { const t = svgEl('text', { x: x(i), y: H - 6, 'text-anchor': 'middle' }, svg); t.textContent = r.date.slice(8, 10) + '.' + r.date.slice(5, 7); } });
    let yP = y(lastP), yF = lastF != null ? y(lastF) : null;
    if (yF != null && Math.abs(yP - yF) < 14) { const m = (yP + yF) / 2; if (yP <= yF) { yP = m - 7; yF = m + 7; } else { yP = m + 7; yF = m - 7; } }
    const t1 = svgEl('text', { x: W - mr + 6, y: yP + 4 }, svg); t1.textContent = 'План ' + fmt(lastP, 1);
    if (yF != null) { const t2 = svgEl('text', { x: W - mr + 6, y: yF + 4, style: 'fill:' + css('--acc') }, svg); t2.textContent = 'Прогноз ' + fmt(lastF, 1); }
    const hit = svgEl('rect', { x: ml, y: 0, width: W - ml - mr, height: H, fill: 'transparent' }, svg);
    hit.addEventListener('mousemove', (ev) => {
      const bb = svg.getBoundingClientRect(); const mx = (ev.clientX - bb.left) * (W / bb.width);
      const i = Math.max(0, Math.min(rows.length - 1, Math.round((mx - ml) / step))); const r = rows[i];
      const lines = ['План: ' + fmt(r.plan_cum, 1)];
      if (r.fact_cum != null) lines.push('Факт: ' + fmt(r.fact_cum, 1) + ' (' + pct(r.fact_cum / r.plan_cum) + ')');
      else if (r.forecast_cum != null) lines.push('Прогноз: ' + fmt(r.forecast_cum, 1));
      showTip(ev, dateRu(r.date), lines);
    });
    hit.addEventListener('mouseleave', hideTip);
  }

  const MON = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  function monthly(ch) {
    const box = $('chart-monthly'); box.replaceChildren();
    $('m-title').textContent = ch.name + ' по месяцам года';
    $('m-note').textContent = ch.unit + ': факт (сплошные), прогноз (светлые), черта — план месяца.';
    const rows = ch.rows;
    const W = Math.max(300, box.clientWidth), H = 260, ml = 52, mr = 6;
    const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}` }, box);
    const max = niceMax(Math.max(...rows.map((r) => Math.max(r.plan || 0, r.fact || 0, r.forecast || 0))) * 1.05);
    const y = axis(svg, W, H, ml, mr, max);
    const band = (W - ml - mr) / 12, bw = Math.min(32, band * 0.62);
    rows.forEach((r, i) => {
      const bx = ml + i * band + (band - bw) / 2;
      if (r.forecast != null) svgEl('rect', { x: bx, width: bw, y: y(r.forecast), height: y(0) - y(r.forecast), rx: 4, fill: css('--muted-bar') }, svg);
      if (r.fact != null) svgEl('rect', { x: bx, width: bw, y: y(r.fact), height: y(0) - y(r.fact), rx: 4, fill: css('--acc') }, svg);
      if (r.plan != null) svgEl('line', { x1: bx - 3, x2: bx + bw + 3, y1: y(r.plan), y2: y(r.plan), stroke: css('--fg'), 'stroke-width': 2 }, svg);
      if (band >= 24 || i % 2 === 0) { const t = svgEl('text', { x: bx + bw / 2, y: H - 6, 'text-anchor': 'middle' }, svg); t.textContent = MON[i]; }
      const hit = svgEl('rect', { x: ml + i * band, y: 0, width: band, height: H, fill: 'transparent' }, svg);
      hit.addEventListener('mousemove', (ev) => {
        const v = r.forecast ?? r.fact; const lines = ['План: ' + fmt(r.plan, 1)];
        if (r.fact != null) lines.push((r.forecast != null ? 'Факт нараст.: ' : 'Факт: ') + fmt(r.fact, 1));
        if (r.forecast != null) lines.push('Прогноз: ' + fmt(r.forecast, 1));
        if (v != null && r.plan) lines.push('% плана: ' + pct(v / r.plan));
        if (v != null && r.last_year) lines.push('к прошлому году: ' + (v >= r.last_year ? '+' : '−') + fmt(Math.abs(v / r.last_year - 1) * 100, 1) + '%');
        showTip(ev, MON[i] + ' ' + r.month.slice(0, 4), lines);
      });
      hit.addEventListener('mouseleave', hideTip);
    });
  }

  function render(data) {
    const m = data.meta, s = data.summary;
    $('meta').textContent = 'Данные на ' + dateRu(m.report_date) + ' · ' + m.month_name + ': прошло ' + m.wd_elapsed + ' из ' + m.wd_month +
      ' рабочих дней, осталось ' + m.wd_left + ' · ' + m.week_label + ' · обновлено ' + data.generated_at;
    const sum = $('sum'); sum.replaceChildren();
    sum.append('По прогнозу месяца из ' + s.total + ' показателей: ', dot('green'), s.green + ' в плане, ', dot('yellow'), s.yellow + ' на грани, ', dot('red'), s.red + ' ниже плана.');
    const top = data.alerts.find((a) => a.light === 'red') || data.alerts[0];
    if (top) { sum.append(' Главный риск — '); sum.appendChild(el('b', '', top.kpi)); sum.append('.'); }
    tiles(data); alerts(data); table(data);
    if (data.charts.daily) daily(data.charts.daily);
    if (data.charts.monthly) monthly(data.charts.monthly);
    $('foot').textContent = data.company + ' · данные из 1С через шаблон импорта · сформировано ' + data.generated_at;
  }

  // ---------- вкладки ролей, данные встроены в файл ----------
  const ALL = window.KPI_DATA;
  const params = new URLSearchParams(location.search);
  let current = null;
  function show(role) {
    const rep = ALL.reports.find((r) => r.role === role) || ALL.reports[0];
    current = Object.assign({ company: ALL.company, generated_at: ALL.generated_at, meta: ALL.meta }, rep);
    document.querySelectorAll('.tabs button').forEach((b) => b.classList.toggle('on', b.dataset.role === rep.role));
    $('title').textContent = 'Дашборд: ' + rep.role_name;
    document.title = 'KPI · ' + rep.role_name + ' · ' + ALL.company;
    render(current);
  }
  const tabs = $('tabs');
  ALL.reports.forEach((r) => {
    const b = el('button', '', r.role_name); b.dataset.role = r.role;
    b.addEventListener('click', () => { show(r.role); history.replaceState(null, '', '#' + r.role); });
    tabs.appendChild(b);
  });
  $('brand').textContent = ALL.company + ' · KPI';

  document.querySelectorAll('.view button').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.view button').forEach((x) => x.classList.toggle('on', x === b));
    document.body.classList.toggle('compact', b.dataset.view === 'compact');
  }));
  if (params.get('view') === 'compact') document.querySelector('.view button[data-view="compact"]').click();
  if (params.get('shot')) document.body.classList.add('shot');
  show(params.get('role') || location.hash.slice(1) || ALL.reports[0].role);
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => current && render(current), 200); });
})();
