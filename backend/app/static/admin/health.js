/* AMI Trade — Admin console HEALTH view (CR200).
   One call to /v1/admin/overview renders the whole stack: readiness
   probes, build identity, LLM provider + prefix-cache rate, release
   floor, market-data mode, open bugs, config coverage. Blocks that
   errored server-side arrive as {error: …} and render red — a dead
   dependency is loud, never a blank card (CR040). Auto-refreshes every
   30s while the tab is visible. */

let healthTimer = null;

function showHealth() {
  currentUser = null;
  setTab('health');
  document.getElementById('main').innerHTML = `
    <div class="card">
      <h3><span class="accent">◇</span> SYSTEM HEALTH <span class="mono" id="healthStamp" style="float:right;color:var(--text-low);font-size:11px"></span></h3>
      <div id="healthGrid"></div>
    </div>
  `;
  loadHealth();
  clearInterval(healthTimer);
  healthTimer = setInterval(() => {
    // Stop polling once the user navigates to another tab.
    if (!document.getElementById('healthGrid')) { clearInterval(healthTimer); return; }
    loadHealth();
  }, 30000);
}

function dot(ok) {
  return `<span style="color:${ok ? 'var(--green)' : 'var(--red)'}">●</span>`;
}

function healthCard(title, ok, bodyHtml) {
  return `
    <div class="stat" style="margin-bottom:8px">
      <div class="k">${dot(ok)} ${title}</div>
      <div class="v dim" style="font-size:12px;line-height:1.6">${bodyHtml}</div>
    </div>
  `;
}

function errBody(block) {
  return `<span style="color:var(--red)">${esc(block.error)}</span>`;
}

async function loadHealth() {
  const el = document.getElementById('healthGrid');
  if (!el) return;
  try {
    const o = await api('GET', '/v1/admin/overview');
    document.getElementById('healthStamp').textContent = new Date().toLocaleTimeString();
    let html = '';

    const r = o.ready;
    if (r.error) {
      html += healthCard('READINESS', false, errBody(r));
    } else {
      const probes = (r.probes || []).map(p =>
        `${dot(p.ok)} ${esc(p.name)}${p.gating ? '' : ' <span style="color:var(--text-low)">(non-gating)</span>'}${p.ok ? '' : ` — <span style="color:var(--red)">${esc(JSON.stringify(p.detail))}</span>`}`
      ).join('<br>');
      html += healthCard('READINESS', r.ready, probes);
    }

    const b = o.build;
    html += healthCard('BUILD', b.git_sha !== 'unset',
      `sha <span class="mono">${esc(b.git_sha)}</span> · tag <span class="mono">${esc(b.alpha_tag)}</span> · env ${esc(b.env)}`);

    const llm = o.llm;
    html += llm.error
      ? healthCard('LLM', false, errBody(llm))
      : healthCard('LLM', llm.active_provider && llm.active_provider !== 'mock',
          Object.entries(llm).map(([k, v]) => `${esc(k)}: <span class="mono">${esc(JSON.stringify(v))}</span>`).join('<br>'));

    const c = o.llm_cache;
    html += c.error
      ? healthCard('VLLM PREFIX CACHE', false, errBody(c))
      : healthCard('VLLM PREFIX CACHE', c.status === 'ok',
          c.status === 'ok'
            ? `hit rate <span class="mono">${(c.rate * 100).toFixed(1)}%</span> (${c.hits_delta}/${c.queries_delta})`
            : `status: ${esc(c.status)} — no rate (this is a measurement gap, not 0%)`);

    const f = o.release_floor;
    html += f.error
      ? healthCard('RELEASE FLOOR', false, errBody(f))
      : healthCard('RELEASE FLOOR', true,
          f.configured ? `min build <span class="mono">${f.min_build}</span>${f.recommended_build ? ` · recommended <span class="mono">${f.recommended_build}</span>` : ''}` : 'no floor configured');

    html += healthCard('MARKET DATA', o.market_data.real,
      o.market_data.real ? 'real (Yahoo)' : '<span style="color:var(--amber)">mock random-walk</span>');

    const bugs = o.bugs;
    html += bugs.error
      ? healthCard('BUGS', false, errBody(bugs))
      : healthCard('BUGS', (bugs.open || 0) === 0,
          `${bugs.open} open · ${Object.entries(bugs.counts).map(([k, v]) => `${esc(k)} ${v}`).join(' · ') || 'none'}`);

    const cfg = o.config;
    html += cfg.error
      ? healthCard('CONFIG', false, errBody(cfg))
      : healthCard('CONFIG', (cfg.unset_annotated || []).length === 0,
          `${cfg.unset_count}/${cfg.settings_total} settings unset${cfg.unset_annotated.length ? ` · dark features: <span style="color:var(--red)">${cfg.unset_annotated.map(esc).join(', ')}</span>` : ''}`);

    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = `<div class="empty" style="padding:20px;color:var(--red)">Failed to load overview — ${esc(e.message)}</div>`;
  }
}

registerView({ id: 'health', label: 'HEALTH', show: showHealth });
