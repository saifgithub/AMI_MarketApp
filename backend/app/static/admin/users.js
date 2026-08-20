/* AMI Trade — Admin console USERS view (AT:R27, split from admin.html in
   CR200). Lookup → detail → plan / trial / credits / suspend / events.
   Logic extracted verbatim; only the tab wiring moved to the registry. */

const PLANS = ['floor_pass', 'trader', 'floor_manager', 'trial_trader'];
let currentUser = null;

function viewSearch() {
  return `
    <div class="card">
      <h3><span class="accent">◇</span> LOOKUP</h3>
      <div class="row cols-2">
        <input type="text" id="searchEmail" placeholder="email@…" autocomplete="off" spellcheck="false">
        <input type="text" id="searchDeviceId" placeholder="device_user_id (uuid)" autocomplete="off" spellcheck="false">
      </div>
      <div class="row cols-2">
        <button class="btn" onclick="doSearch()">SEARCH</button>
        <input type="text" id="directId" placeholder="…or paste user id directly" autocomplete="off" spellcheck="false" onkeydown="if(event.key==='Enter')openDirect()">
      </div>
    </div>
    <div id="results"></div>
  `;
}

function renderResults(arr) {
  if (!arr || arr.length === 0) {
    return `<div class="empty"><div class="hex"></div>No matches.</div>`;
  }
  return arr.map(u => `
    <div class="card" onclick="loadUser('${u.id}')" style="cursor:pointer">
      <div class="userhdr">
        <div class="email ${u.email ? '' : 'muted'}">${u.email || '(anonymous)'}</div>
        <div class="id mono">${u.id}</div>
        <div class="badges">
          ${u.is_anonymous ? '<span class="badge anon">ANON</span>' : '<span class="badge claimed">CLAIMED</span>'}
          ${u.suspended_at ? '<span class="badge suspended">SUSPENDED</span>' : ''}
          ${u.plan === 'trial_trader' ? '<span class="badge trial">TRIAL</span>' : ''}
        </div>
        <div class="stats">
          <div class="stat"><div class="k">plan</div><div class="v">${u.plan}</div></div>
          <div class="stat"><div class="k">credits</div><div class="v">${u.credit_balance}</div></div>
          <div class="stat"><div class="k">created</div><div class="v dim">${fmtRel(u.created_at)}</div></div>
        </div>
      </div>
    </div>
  `).join('');
}

function renderUser(u) {
  currentUser = u;
  return `
    <div class="card">
      <button class="btn ghost" onclick="showSearch()" style="margin-bottom:12px">← BACK TO SEARCH</button>
      <div class="userhdr">
        <div class="email ${u.email ? '' : 'muted'}">${u.email || '(anonymous)'}</div>
        <div class="id mono">${u.id}</div>
        <div class="badges">
          ${u.is_anonymous ? '<span class="badge anon">ANON</span>' : '<span class="badge claimed">CLAIMED</span>'}
          ${u.suspended_at ? '<span class="badge suspended">SUSPENDED</span>' : ''}
          ${u.plan === 'trial_trader' ? '<span class="badge trial">TRIAL</span>' : ''}
        </div>
        <div class="stats">
          <div class="stat"><div class="k">plan</div><div class="v">${u.plan}${u.effective_plan && u.effective_plan !== u.plan ? ` → <span style="color:#ff9d4a">${u.effective_plan}</span>` : ''}</div></div>
          <div class="stat"><div class="k">credits</div><div class="v">${u.credit_balance}</div></div>
          <div class="stat"><div class="k">trial</div><div class="v ${u.trial_active ? '' : 'dim'}">${u.trial_active ? 'ACTIVE' : (u.trial_expires_at ? 'EXPIRED' : '—')}${u.trial_expires_at ? ` · ${fmtRel(u.trial_expires_at)}` : ''}</div></div>
        </div>
        ${(u.device_model || u.os_version || u.last_app_version) ? `
        <div class="stats">
          <div class="stat"><div class="k">device</div><div class="v dim">${u.device_model || '—'}</div></div>
          <div class="stat"><div class="k">os</div><div class="v dim">${u.os_version || '—'}</div></div>
          <div class="stat"><div class="k">app</div><div class="v dim">${u.last_app_version || '—'}</div></div>
        </div>` : ''}
        ${(u.devices && u.devices.length > 0) ? `
        <div class="stat" style="margin-top:12px">
          <div class="k">devices (${u.devices.length})</div>
          <div class="v dim" style="font-size:11px;line-height:1.5">
            ${u.devices.map(d => `${d.device_model || '?'} · ${d.os_version || '?'} · ${d.app_version || '?'} · ${fmtRel(d.last_seen_at)}`).join('<br>')}
          </div>
        </div>` : ''}
      </div>
    </div>

    <div class="card">
      <h3><span class="accent">◇</span> PLAN</h3>
      <div class="row cols-2">
        <select id="planSelect">
          ${PLANS.map(p => `<option value="${p}" ${p===u.plan?'selected':''}>${p}</option>`).join('')}
        </select>
        <input type="text" id="planNote" placeholder="note (optional)">
      </div>
      <button class="btn" onclick="changePlan()">CHANGE PLAN</button>
    </div>

    <div class="card">
      <h3><span class="accent">◇</span> TRIAL</h3>
      <div class="row cols-2">
        <input type="number" id="grantDays" placeholder="days (e.g. 14)" min="1">
        <input type="text" id="grantNote" placeholder="note">
      </div>
      <button class="btn amber" onclick="grantTrial()">GRANT TRIAL</button>
      <hr class="sep">
      <div class="row cols-2">
        <input type="number" id="extendDays" placeholder="extend by N days" min="1">
        <input type="text" id="extendNote" placeholder="note">
      </div>
      <div class="row cols-2">
        <button class="btn amber" onclick="extendTrial()" ${u.trial_expires_at ? '' : 'disabled'}>EXTEND</button>
        <button class="btn ghost" onclick="revokeTrial()" ${u.trial_expires_at ? '' : 'disabled'}>REVOKE</button>
      </div>
    </div>

    <div class="card">
      <h3><span class="accent">◇</span> CREDITS <span style="float:right;color:var(--text-low)">now: <span class="mono" style="color:var(--text-high)">${u.credit_balance}</span></span></h3>
      <div class="row cols-2">
        <input type="number" id="creditDelta" placeholder="±delta (e.g. 10 or -3)">
        <input type="text" id="creditNote" placeholder="note">
      </div>
      <button class="btn green" onclick="adjustCredits()">APPLY</button>
    </div>

    <div class="card ${u.suspended_at ? '' : 'danger'}">
      <h3><span class="accent">◇</span> ${u.suspended_at ? 'REINSTATE' : 'SUSPEND'}</h3>
      <div class="row">
        <input type="text" id="suspendNote" placeholder="note (recommended)">
      </div>
      ${u.suspended_at
        ? `<button class="btn green" onclick="reinstate()">REINSTATE</button>`
        : `<button class="btn red" onclick="suspend()">SUSPEND</button>`}
    </div>

    <div class="card">
      <h3><span class="accent">◇</span> RECENT EVENTS <span style="float:right;color:var(--text-low)">${u.recent_events.length}</span></h3>
      <div class="events">${renderEvents(u.recent_events)}</div>
    </div>
  `;
}

function renderEvents(events) {
  if (!events || events.length === 0) {
    return `<div class="empty" style="padding:20px"><span style="color:var(--text-low)">No events yet.</span></div>`;
  }
  return events.map(e => `
    <div class="ev ${e.event_type}">
      <div class="ev-type">${e.event_type}</div>
      <div class="ev-vals">${e.from_value ?? '—'} → ${e.to_value ?? '—'}</div>
      <div class="ev-meta">${fmtDate(e.created_at)} · ${e.source}</div>
      ${e.note ? `<div class="ev-note">"${e.note}"</div>` : ''}
    </div>
  `).join('');
}

// ── actions ───────────────────────────────────────────────────────────────
async function doSearch() {
  const email = document.getElementById('searchEmail').value.trim();
  const did = document.getElementById('searchDeviceId').value.trim();
  if (!email && !did) { toast('email or device id', 'err'); return; }
  const qs = new URLSearchParams();
  if (email) qs.set('email', email);
  if (did) qs.set('device_user_id', did);
  try {
    const arr = await api('GET', '/v1/admin/users?' + qs.toString());
    document.getElementById('results').innerHTML = renderResults(arr);
  } catch (e) { toast(e.message, 'err'); }
}

function openDirect() {
  const id = document.getElementById('directId').value.trim();
  if (!id) return;
  loadUser(id);
}

async function loadUser(id) {
  try {
    const u = await api('GET', `/v1/admin/users/${id}`);
    document.getElementById('main').innerHTML = renderUser(u);
    setTab('users');
    window.scrollTo({ top: 0, behavior: 'instant' });
  } catch (e) { toast(e.message, 'err'); }
}

async function refreshCurrent() {
  if (!currentUser) return;
  return loadUser(currentUser.id);
}

function showSearch() {
  currentUser = null;
  setTab('users');
  document.getElementById('main').innerHTML = viewSearch();
}

async function changePlan() {
  const plan = document.getElementById('planSelect').value;
  const note = document.getElementById('planNote').value.trim() || null;
  try {
    await api('PATCH', `/v1/admin/users/${currentUser.id}/plan`, { plan, note });
    toast('plan changed');
    refreshCurrent();
  } catch (e) { toast(e.message, 'err'); }
}

async function grantTrial() {
  const days = parseInt(document.getElementById('grantDays').value, 10);
  if (!days || days < 1) { toast('days?', 'err'); return; }
  const note = document.getElementById('grantNote').value.trim() || null;
  try {
    await api('POST', `/v1/admin/users/${currentUser.id}/trial`, { days, note });
    toast(`trial granted (${days}d)`);
    refreshCurrent();
  } catch (e) { toast(e.message, 'err'); }
}

async function extendTrial() {
  const days = parseInt(document.getElementById('extendDays').value, 10);
  if (!days || days < 1) { toast('days?', 'err'); return; }
  const note = document.getElementById('extendNote').value.trim() || null;
  try {
    await api('PATCH', `/v1/admin/users/${currentUser.id}/trial`, { action: 'extend', days, note });
    toast(`extended +${days}d`);
    refreshCurrent();
  } catch (e) { toast(e.message, 'err'); }
}

async function revokeTrial() {
  if (!confirm('Revoke trial and revert plan to floor_pass?')) return;
  const note = document.getElementById('extendNote').value.trim() || null;
  try {
    await api('PATCH', `/v1/admin/users/${currentUser.id}/trial`, { action: 'revoke', note });
    toast('trial revoked');
    refreshCurrent();
  } catch (e) { toast(e.message, 'err'); }
}

async function adjustCredits() {
  const delta = parseInt(document.getElementById('creditDelta').value, 10);
  if (!delta || delta === 0) { toast('delta?', 'err'); return; }
  const note = document.getElementById('creditNote').value.trim() || null;
  try {
    await api('POST', `/v1/admin/users/${currentUser.id}/credits`, { delta, note });
    toast(`credits ${delta > 0 ? '+' : ''}${delta}`);
    refreshCurrent();
  } catch (e) { toast(e.message, 'err'); }
}

async function suspend() {
  if (!confirm('Suspend this user? They will be locked out of every authenticated route.')) return;
  const note = document.getElementById('suspendNote').value.trim() || null;
  try {
    await api('POST', `/v1/admin/users/${currentUser.id}/suspend`, { note });
    toast('suspended');
    refreshCurrent();
  } catch (e) { toast(e.message, 'err'); }
}

async function reinstate() {
  const note = document.getElementById('suspendNote').value.trim() || null;
  try {
    await api('POST', `/v1/admin/users/${currentUser.id}/reinstate`, { note });
    toast('reinstated');
    refreshCurrent();
  } catch (e) { toast(e.message, 'err'); }
}

registerView({ id: 'users', label: 'USERS', show: showSearch });
