/* AMI Trade — Admin console ANALYTICS view (CR200).
   Live KPIs over /v1/admin/analytics/* plus persona segments from the
   existing CR181 endpoint. Charts are inline SVG (daily_report.py's
   approach) — no chart library, no build step. User counts are
   real-human counts (CR035 synthetics / seed fixtures / probe users
   excluded server-side). */

function showAnalytics() {
  currentUser = null;
  setTab('analytics');
  document.getElementById('main').innerHTML = `
    <div class="card"><h3><span class="accent">◇</span> USERS</h3><div id="anSummary"></div></div>
    <div class="card"><h3><span class="accent">◇</span> LAST 30 DAYS</h3><div id="anCharts"></div></div>
    <div class="card"><h3><span class="accent">◇</span> PERSONA SEGMENTS (30D)</h3><div id="anSegments"></div></div>
    <div class="card"><h3><span class="accent">◇</span> REVENUECAT (30D)</h3><div id="anRevenue"></div></div>
  `;
  loadAnalytics();
}

function statTile(k, v, dim) {
  return `<div class="stat"><div class="k">${esc(k)}</div><div class="v ${dim ? 'dim' : ''}">${v}</div></div>`;
}

// Inline-SVG bar chart: values only, no axes — the daily numbers are small
// and the shape is the signal. Hover title carries the exact value + day.
function barChart(days, values, color) {
  const w = 640, h = 80, max = Math.max(1, ...values);
  const bw = w / values.length;
  const bars = values.map((v, i) => {
    const bh = Math.round((v / max) * (h - 4));
    return `<rect x="${(i * bw + 1).toFixed(1)}" y="${h - bh}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${bh}" fill="${color}" opacity="${v ? 1 : 0.15}"><title>${days[i]}: ${v}</title></rect>`;
  }).join('');
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:64px;display:block">${bars}</svg>`;
}

function chartRow(label, days, values, color) {
  const total = values.reduce((a, b) => a + b, 0);
  return `
    <div style="margin-bottom:14px">
      <div class="k" style="font-size:10px;color:var(--text-low);letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px">
        ${esc(label)} <span class="mono" style="color:var(--text-high)">${total}</span>
      </div>
      ${barChart(days, values, color)}
    </div>`;
}

async function loadAnalytics() {
  try {
    const s = await api('GET', '/v1/admin/analytics/summary');
    const u = s.users;
    document.getElementById('anSummary').innerHTML = `
      <div class="stats">
        ${statTile('real users', u.total)}
        ${statTile('claimed', u.claimed)}
        ${statTile('anonymous', u.anonymous, true)}
      </div>
      <div class="stats">
        ${statTile('DAU', s.active.dau)}
        ${statTile('WAU', s.active.wau)}
        ${statTile('MAU', s.active.mau)}
      </div>
      <div class="stats">
        ${statTile('in trial', u.in_trial)}
        ${statTile('suspended', u.suspended, true)}
        ${statTile('credits held', u.credit_balance_sum)}
      </div>
      <div class="stat" style="margin-top:8px"><div class="k">by plan</div>
        <div class="v dim" style="font-size:12px">${Object.entries(u.by_plan).map(([p, n]) => `${esc(p)} <span class="mono">${n}</span>`).join(' · ') || '—'}</div>
      </div>`;
  } catch (e) {
    document.getElementById('anSummary').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }

  try {
    const t = await api('GET', '/v1/admin/analytics/timeseries?days=30');
    document.getElementById('anCharts').innerHTML =
      chartRow('signups / day', t.days, t.signups, 'var(--blue)') +
      chartRow('active users / day', t.days, t.active_users, 'var(--cyan)') +
      chartRow('room runs / day', t.days, t.room_runs, 'var(--purple)') +
      chartRow('credits spent / day', t.days, t.credits_spent, 'var(--amber)');
  } catch (e) {
    document.getElementById('anCharts').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }

  try {
    const until = new Date().toISOString();
    const since = new Date(Date.now() - 30 * 86400000).toISOString();
    const g = await api('GET', `/v1/telemetry/segments?since=${since}&until=${until}`);
    document.getElementById('anSegments').innerHTML = `
      <div class="stats">
        ${statTile('users seen', g.users)}
        ${statTile('bounce', g.bounce)}
        ${statTile('convene', g.convene)}
      </div>
      <div class="stats">
        ${statTile('depth', g.depth)}
        ${statTile('dropped events', g.dropped_events, true)}
        ${statTile('locales', Object.entries(g.locales).map(([l, n]) => `${esc(l)} ${n}`).join(' · ') || '—', true)}
      </div>`;
  } catch (e) {
    document.getElementById('anSegments').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }

  try {
    const rc = await api('GET', '/v1/admin/analytics/revenuecat?days=30');
    const counts = Object.entries(rc.counts);
    document.getElementById('anRevenue').innerHTML = counts.length === 0
      ? `<div class="empty" style="padding:12px">No RevenueCat events in the window.</div>`
      : `<div class="stat"><div class="k">events by type</div>
           <div class="v dim" style="font-size:12px">${counts.map(([t, n]) => `${esc(t)} <span class="mono">${n}</span>`).join(' · ')}</div>
         </div>
         <div class="events" style="margin-top:8px">${rc.recent.slice(0, 15).map(e =>
           `<div class="ev"><div class="ev-type">${esc(e.event_type)}</div><div class="ev-meta">${fmtDate(e.received_at)}</div></div>`
         ).join('')}</div>`;
  } catch (e) {
    document.getElementById('anRevenue').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }
}

registerView({ id: 'analytics', label: 'STATS', show: showAnalytics });
