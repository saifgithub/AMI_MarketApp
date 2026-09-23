/* AMI Trade — Admin console TICKER INTEREST view (CR200-R001).
   Which tickers/tickets users research (room_runs) and trade
   (sim_trades / sim_resting_orders fill state), plus watchlist adds.
   Own tab, separate from STATS (analytics.js) — different grain, per-symbol
   not platform-wide. Real-user counts only (CR035 synthetics / seed
   fixtures / probe users excluded server-side, same as every other tab). */

function showTickerInterest() {
  currentUser = null;
  setTab('ticker-interest');
  document.getElementById('main').innerHTML = `
    <div class="card"><h3><span class="accent">◇</span> MOST RESEARCHED (ROOM RUNS, 30D)</h3><div id="tiTop"></div></div>
    <div class="card"><h3><span class="accent">◇</span> ORDER FULFILMENT BY TICKER (30D)</h3><div id="tiOrders"></div></div>
    <div class="card"><h3><span class="accent">◇</span> WATCHLIST INTEREST (30D)</h3><div id="tiWatchlist"></div></div>
    <div class="card" id="tiDetailCard" style="display:none">
      <h3><span class="accent">◇</span> TICKER DETAIL — <span id="tiDetailTicker"></span></h3>
      <div id="tiDetail"></div>
    </div>
  `;
  loadTickerInterest();
}

function tiTable(rows, cols, onClickTicker) {
  if (!rows.length) return `<div class="empty" style="padding:12px">No data in this window.</div>`;
  const head = cols.map(c => `<th>${esc(c.label)}</th>`).join('');
  const body = rows.map(r => `
    <tr class="tiRow" onclick="${onClickTicker ? `loadTickerDetail('${esc(r.ticker)}')` : ''}" style="${onClickTicker ? 'cursor:pointer' : ''}">
      ${cols.map(c => `<td>${c.render ? c.render(r) : esc(r[c.key] ?? '—')}</td>`).join('')}
    </tr>`).join('');
  return `<table class="tiTable" style="width:100%;border-collapse:collapse">
    <thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

async function loadTickerInterest() {
  try {
    const t = await api('GET', '/v1/admin/ticker-interest/top?days=30&limit=25');
    document.getElementById('tiTop').innerHTML = tiTable(t.tickers, [
      { key: 'ticker', label: 'ticker', render: r => `<span class="mono">${esc(r.ticker)}</span>` },
      { key: 'runs', label: 'runs' },
      { key: 'researchers', label: 'researchers' },
      { key: 'credits_spent', label: 'credits' },
      { key: 'by_status', label: 'status', render: r => esc(Object.entries(r.by_status).map(([k, n]) => `${k}:${n}`).join(' ') || '—') },
    ], true);
  } catch (e) {
    document.getElementById('tiTop').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }

  try {
    const o = await api('GET', '/v1/admin/ticker-interest/orders?days=30&limit=25');
    document.getElementById('tiOrders').innerHTML = tiTable(o.tickers, [
      { key: 'ticker', label: 'ticker', render: r => `<span class="mono">${esc(r.ticker)}</span>` },
      { key: 'filled', label: 'filled' },
      { key: 'pending', label: 'pending' },
      { key: 'not_filled', label: 'not filled' },
    ], true);
  } catch (e) {
    document.getElementById('tiOrders').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }

  try {
    const w = await api('GET', '/v1/admin/ticker-interest/watchlist?days=30&limit=25');
    document.getElementById('tiWatchlist').innerHTML = tiTable(w.tickers, [
      { key: 'ticker', label: 'ticker', render: r => `<span class="mono">${esc(r.ticker)}</span>` },
      { key: 'watchlist_adds', label: 'adds' },
    ], true);
  } catch (e) {
    document.getElementById('tiWatchlist').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }
}

async function loadTickerDetail(ticker) {
  const card = document.getElementById('tiDetailCard');
  card.style.display = '';
  document.getElementById('tiDetailTicker').textContent = ticker;
  document.getElementById('tiDetail').innerHTML = `<div class="empty">loading…</div>`;
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  try {
    const d = await api('GET', `/v1/admin/ticker-interest/detail/${encodeURIComponent(ticker)}?days=90`);
    document.getElementById('tiDetail').innerHTML = `
      <div class="stats">
        ${statTile('room runs', d.room_runs.length)}
        ${statTile('trades', d.trades.length)}
        ${statTile('resting orders', d.resting_orders.length)}
        ${statTile('watchlist adds', d.watchlist_adds)}
      </div>
      <div style="margin-top:10px">
        <div class="k" style="font-size:10px;color:var(--text-low);letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px">recent room runs</div>
        ${tiTable(d.room_runs.slice(0, 10), [
          { key: 'user_id', label: 'user', render: r => shortId(r.user_id) },
          { key: 'status', label: 'status' },
          { key: 'credit_cost', label: 'credits' },
          { key: 'triggered_at', label: 'when', render: r => fmtDate(r.triggered_at) },
        ])}
      </div>
      <div style="margin-top:10px">
        <div class="k" style="font-size:10px;color:var(--text-low);letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px">recent orders (trades + resting)</div>
        ${tiTable(
          [...d.trades.map(t => ({ ...t, kind: 'filled', when: t.opened_at })),
           ...d.resting_orders.map(o => ({ ...o, kind: o.state, when: o.placed_at }))]
            .sort((a, b) => new Date(b.when) - new Date(a.when)).slice(0, 10),
          [
            { key: 'user_id', label: 'user', render: r => shortId(r.user_id) },
            { key: 'side', label: 'side' },
            { key: 'kind', label: 'outcome' },
            { key: 'when', label: 'when', render: r => fmtDate(r.when) },
          ],
        )}
      </div>
    `;
  } catch (e) {
    document.getElementById('tiDetail').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }
}

registerView({ id: 'ticker-interest', label: 'TICKERS', show: showTickerInterest });
