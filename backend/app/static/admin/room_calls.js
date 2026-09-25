/* AMI Trade — Admin console ROOM CALLS view (CR200-R002).
   The raw request (system prompt + message list) and raw response for
   every LLM call inside a convened Room, plus an edit-and-resend sandbox
   for testing prompt-wording changes. Resend is an ISOLATED raw call — it
   never re-enters the Room pipeline, so nothing here can parse a verdict,
   spend a credit, or write the Decision Journal (see admin_room.py). */

// Canned text an operator can insert into the editable system prompt before
// resending, to see how the agent's answer shifts under a scenario that's
// rare or slow to hit by actually convening a Room. Hand-authored, clearly
// labelled as inserted test context — never dressed up as part of the
// original captured prompt, and never claims to be a real user's data.
const ROOM_CALL_PRESETS = [
  {
    id: 'cash_only',
    label: 'CASH ONLY PORTFOLIO',
    snippet:
      '\n\n[TEST CONTEXT — inserted for prompt testing, not part of the original run]\n' +
      'PORTFOLIO — SIMULATED HOLDINGS\n' +
      'No portfolio is attached to this run. You hold 0% of the ticker under discussion — ' +
      'treat any BUY as opening a NEW position. All cash, no open positions.',
  },
  {
    id: 'risk_conservative',
    label: 'CONSERVATIVE RISK SETTINGS',
    snippet:
      '\n\n[TEST CONTEXT — inserted for prompt testing, not part of the original run]\n' +
      'RISK STATE\n' +
      '- max_drawdown_pct: 8 — PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget.\n' +
      '- Drawdown USED: 1.0 pt of the 8 pt cap — 7.0 pt of headroom remains. Size against the headroom, not the cap.\n' +
      '- Mandate style: capital preservation, low turnover, small position sizes, wide margin of safety required before any BUY.',
  },
  {
    id: 'risk_aggressive',
    label: 'AGGRESSIVE RISK SETTINGS',
    snippet:
      '\n\n[TEST CONTEXT — inserted for prompt testing, not part of the original run]\n' +
      'RISK STATE\n' +
      '- max_drawdown_pct: 35 — PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget.\n' +
      '- Drawdown USED: 3.0 pt of the 35 pt cap — 32.0 pt of headroom remains. Size against the headroom, not the cap.\n' +
      '- Mandate style: aggressive growth, high conviction, larger position sizes, comfortable with wider stops for asymmetric upside.',
  },
  {
    id: 'large_drawdown',
    label: 'LARGE OPEN DRAWDOWN',
    snippet:
      '\n\n[TEST CONTEXT — inserted for prompt testing, not part of the original run]\n' +
      'RISK STATE\n' +
      '- max_drawdown_pct: 20 — PORTFOLIO-level cap on total drawdown, NOT a per-trade stop budget.\n' +
      '- Drawdown USED: 17.5 pt of the 20 pt cap — 2.5 pt of headroom remains. Size against the headroom, not the cap.\n' +
      '- The portfolio is down double digits this month; most of the risk budget is already consumed. Be explicit about ' +
      'whether a new position is prudent at this headroom before proposing one.',
  },
];

let rcSelectedRunId = null;
let rcCallsById = {};

function showRoomCalls() {
  currentUser = null;
  setTab('room-calls');
  document.getElementById('main').innerHTML = `
    <div class="card">
      <h3><span class="accent">◇</span> FIND A ROOM RUN</h3>
      <div class="row cols-3">
        <input type="text" id="rcTicker" placeholder="ticker (optional)" autocomplete="off" spellcheck="false" style="text-transform:uppercase">
        <input type="text" id="rcUserId" placeholder="user id (optional)" autocomplete="off" spellcheck="false">
        <input type="number" id="rcDays" placeholder="days" value="7" min="1" max="365">
      </div>
      <button class="btn ghost" onclick="rcLoadRuns()">SEARCH RUNS</button>
      <div id="rcRuns" style="margin-top:10px"></div>
    </div>
    <div class="card" id="rcCallsCard" style="display:none">
      <h3><span class="accent">◇</span> LLM CALLS — RUN <span id="rcRunLabel" class="mono"></span></h3>
      <div id="rcCallsList"></div>
    </div>
  `;
  rcLoadRuns();
}

function rcTable(rows, cols, onClickRow) {
  if (!rows.length) return `<div class="empty" style="padding:12px">No runs found.</div>`;
  const head = cols.map(c => `<th>${esc(c.label)}</th>`).join('');
  const body = rows.map((r, i) => `
    <tr onclick="${onClickRow ? `rcSelectRun('${esc(r.id)}')` : ''}" style="${onClickRow ? 'cursor:pointer' : ''}">
      ${cols.map(c => `<td>${c.render ? c.render(r) : esc(r[c.key] ?? '—')}</td>`).join('')}
    </tr>`).join('');
  return `<table style="width:100%;border-collapse:collapse"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

async function rcLoadRuns() {
  const ticker = document.getElementById('rcTicker').value.trim();
  const userId = document.getElementById('rcUserId').value.trim();
  const days = document.getElementById('rcDays').value.trim() || '7';
  const params = new URLSearchParams({ days });
  if (ticker) params.set('ticker', ticker);
  if (userId) params.set('user_id', userId);
  try {
    const r = await api('GET', `/v1/admin/room/runs?${params.toString()}`);
    document.getElementById('rcRuns').innerHTML = rcTable(r.runs, [
      { key: 'ticker', label: 'ticker', render: r => `<span class="mono">${esc(r.ticker)}</span>` },
      { key: 'status', label: 'status' },
      { key: 'user_id', label: 'user', render: r => shortId(r.user_id) },
      { key: 'credit_cost', label: 'credits' },
      { key: 'triggered_at', label: 'when', render: r => fmtDate(r.triggered_at) },
    ], true);
  } catch (e) {
    document.getElementById('rcRuns').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }
}

async function rcSelectRun(runId) {
  rcSelectedRunId = runId;
  const card = document.getElementById('rcCallsCard');
  card.style.display = '';
  document.getElementById('rcRunLabel').textContent = shortId(runId);
  document.getElementById('rcCallsList').innerHTML = `<div class="empty">loading…</div>`;
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  try {
    const r = await api('GET', `/v1/admin/room/runs/${encodeURIComponent(runId)}/llm-calls`);
    rcCallsById = {};
    r.calls.forEach(c => { rcCallsById[c.id] = c; });
    if (!r.calls.length) {
      document.getElementById('rcCallsList').innerHTML = `<div class="empty">No LLM calls captured for this run` +
        (r.window_open ? ' yet — run still in progress.' : '.') + `</div>`;
      return;
    }
    document.getElementById('rcCallsList').innerHTML =
      (r.window_open ? `<div style="color:var(--amber);font-size:11px;margin-bottom:8px">Run still in progress — this list may grow.</div>` : '') +
      r.calls.map(rcCallCard).join('');
  } catch (e) {
    document.getElementById('rcCallsList').innerHTML = `<div class="empty" style="color:var(--red)">${esc(e.message)}</div>`;
  }
}

function rcCallCard(c) {
  const tokens = [c.input_tokens, c.output_tokens].every(v => v == null)
    ? '—' : `${c.input_tokens ?? '?'} in / ${c.output_tokens ?? '?'} out`;
  return `
    <div class="stat" style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px">
        <div class="mono" style="font-weight:700">${esc(c.agent_id || 'unknown')}</div>
        <div style="font-size:11px;color:var(--text-med)">${esc(c.tier)} · ${esc(c.provider)} · ${c.latency_ms ?? '?'}ms · ${esc(tokens)}</div>
      </div>
      ${c.error ? `<div style="color:var(--red);font-size:12px;margin-top:4px">${esc(c.error)}</div>` : ''}
      <details style="margin-top:8px">
        <summary style="cursor:pointer;color:var(--text-med);font-size:12px">system prompt (${(c.system_prompt || '').length.toLocaleString()} chars)</summary>
        <pre class="mono" style="white-space:pre-wrap;font-size:11px;color:var(--text-med);max-height:260px;overflow:auto;margin-top:6px">${esc(c.system_prompt)}</pre>
      </details>
      <details style="margin-top:6px">
        <summary style="cursor:pointer;color:var(--text-med);font-size:12px">messages (${(c.messages || []).length})</summary>
        <pre class="mono" style="white-space:pre-wrap;font-size:11px;color:var(--text-med);max-height:260px;overflow:auto;margin-top:6px">${esc(JSON.stringify(c.messages, null, 2))}</pre>
      </details>
      <details style="margin-top:6px" open>
        <summary style="cursor:pointer;color:var(--text-med);font-size:12px">response (${(c.response_text || '').length.toLocaleString()} chars)</summary>
        <pre class="mono" style="white-space:pre-wrap;font-size:11px;color:var(--text-high);max-height:260px;overflow:auto;margin-top:6px">${esc(c.response_text || '(empty)')}</pre>
      </details>
      <button class="btn ghost" style="margin-top:8px" onclick="rcOpenResend('${esc(c.id)}')">EDIT + RESEND</button>
      <div id="rcResend-${esc(c.id)}"></div>
    </div>
  `;
}

function rcOpenResend(callId) {
  const c = rcCallsById[callId];
  const host = document.getElementById(`rcResend-${callId}`);
  if (host.dataset.open === '1') { host.innerHTML = ''; host.dataset.open = '0'; return; }
  host.dataset.open = '1';
  const presetBtns = ROOM_CALL_PRESETS.map(p =>
    `<button class="btn ghost" style="width:auto;padding:6px 10px;font-size:10px" onclick="rcInsertPreset('${callId}','${p.id}')">${esc(p.label)}</button>`
  ).join(' ');
  host.innerHTML = `
    <div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border-dim)">
      <label class="lbl">PRESETS — insert test context into the system prompt below</label>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px">${presetBtns}</div>
      <label class="lbl" for="rcSysPrompt-${callId}">SYSTEM PROMPT (editable)</label>
      <textarea id="rcSysPrompt-${callId}" style="min-height:180px;font-family:'IBM Plex Mono',monospace;font-size:12px">${esc(c.system_prompt)}</textarea>
      <label class="lbl" for="rcMessages-${callId}" style="margin-top:8px">MESSAGES (editable JSON)</label>
      <textarea id="rcMessages-${callId}" style="min-height:120px;font-family:'IBM Plex Mono',monospace;font-size:12px">${esc(JSON.stringify(c.messages, null, 2))}</textarea>
      <div class="row cols-2" style="margin-top:8px">
        <div>
          <label class="lbl" for="rcTier-${callId}">MODEL TIER</label>
          <select id="rcTier-${callId}">
            <option value="cheap" ${c.tier === 'cheap' ? 'selected' : ''}>cheap</option>
            <option value="mid" ${c.tier === 'mid' ? 'selected' : ''}>mid</option>
            <option value="premium" ${c.tier === 'premium' ? 'selected' : ''}>premium</option>
          </select>
        </div>
        <div>
          <label class="lbl" for="rcMaxTokens-${callId}">MAX TOKENS</label>
          <input type="number" id="rcMaxTokens-${callId}" value="2048" min="1" max="16384">
        </div>
      </div>
      <button class="btn" style="margin-top:10px" onclick="rcResend('${callId}')">SEND</button>
      <div id="rcResendResult-${callId}" style="margin-top:10px"></div>
    </div>
  `;
}

function rcInsertPreset(callId, presetId) {
  const preset = ROOM_CALL_PRESETS.find(p => p.id === presetId);
  if (!preset) return;
  const ta = document.getElementById(`rcSysPrompt-${callId}`);
  ta.value += preset.snippet;
  ta.scrollTop = ta.scrollHeight;
}

async function rcResend(callId) {
  const sysPromptEl = document.getElementById(`rcSysPrompt-${callId}`);
  const messagesEl = document.getElementById(`rcMessages-${callId}`);
  const resultEl = document.getElementById(`rcResendResult-${callId}`);
  let messages;
  try {
    messages = JSON.parse(messagesEl.value);
  } catch (e) {
    toast('messages is not valid JSON', 'err');
    return;
  }
  const payload = {
    system_prompt: sysPromptEl.value,
    messages,
    model_tier: document.getElementById(`rcTier-${callId}`).value,
    max_tokens: parseInt(document.getElementById(`rcMaxTokens-${callId}`).value, 10) || 2048,
  };
  resultEl.innerHTML = `<div class="empty" style="padding:12px">sending…</div>`;
  try {
    const r = await api('POST', `/v1/admin/room/llm-calls/${encodeURIComponent(callId)}/resend`, payload);
    resultEl.innerHTML = `
      <label class="lbl">NEW RESPONSE — ${esc(r.provider)} · ${r.latency_ms}ms${r.llm_audit_id ? ` · <span class="mono">${shortId(r.llm_audit_id)}</span>` : ''}</label>
      <pre class="mono" style="white-space:pre-wrap;font-size:11px;color:var(--green);max-height:320px;overflow:auto;background:var(--bg);border:1px solid var(--border-dim);border-radius:8px;padding:10px">${esc(r.response_text)}</pre>
    `;
    toast('resent', 'ok');
  } catch (e) {
    resultEl.innerHTML = `<div style="color:var(--red);font-size:12px">${esc(e.message)}</div>`;
    toast(e.message, 'err');
  }
}

registerView({ id: 'room-calls', label: 'ROOM CALLS', show: showRoomCalls });
