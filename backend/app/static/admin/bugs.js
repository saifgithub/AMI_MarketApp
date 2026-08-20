/* AMI Trade — Admin console BUGS view (CR200).
   Triage over /v1/admin/bugs: status filter chips → list → detail with
   claim / resolve / reopen. Coexists with the /fix-bugs psql workflow —
   the server's guarded UPDATEs make double-claims impossible, so a 409
   here means "an agent got there first", not an error. All report text is
   tester-typed free text: esc() everything. */

let bugFilter = '';

function showBugs() {
  currentUser = null;
  setTab('bugs');
  document.getElementById('main').innerHTML = `
    <div class="card">
      <h3><span class="accent">◇</span> BUG REPORTS</h3>
      <div class="badges" id="bugChips" style="margin-bottom:10px"></div>
      <div class="events" id="bugList"></div>
    </div>
    <div id="bugDetail"></div>
  `;
  loadBugs();
}

// Core lifecycle statuses render first; anything else the live data holds
// ("investigating", "wont_fix", … — psql lanes write statuses freely) gets
// its own chip after them, so no row is ever invisible.
const BUG_STATUSES = ['open', 'in_progress', 'pending_review', 'resolved'];

function bugChipOrder(counts) {
  const extras = Object.keys(counts).filter(st => !BUG_STATUSES.includes(st)).sort();
  return BUG_STATUSES.concat(extras);
}

function bugChip(st, count, active) {
  const label = st === '' ? 'ALL' : st.toUpperCase();
  return `<span class="badge ${active ? 'claimed' : 'anon'}" style="cursor:pointer" onclick="setBugFilter('${st}')">${label}${count !== undefined ? ` ${count}` : ''}</span>`;
}

function setBugFilter(st) {
  bugFilter = st;
  loadBugs();
}

async function loadBugs() {
  const listEl = document.getElementById('bugList');
  try {
    const qs = bugFilter ? `?status=${bugFilter}&limit=100` : '?limit=100';
    const r = await api('GET', '/v1/admin/bugs' + qs);
    const chips = [bugChip('', r.counts ? Object.values(r.counts).reduce((a, b) => a + b, 0) : undefined, bugFilter === '')]
      .concat(bugChipOrder(r.counts).map(st => bugChip(st, r.counts[st] || 0, bugFilter === st)));
    document.getElementById('bugChips').innerHTML = chips.join('');
    listEl.innerHTML = renderBugList(r.bugs);
  } catch (e) {
    listEl.innerHTML = `<div class="empty" style="padding:20px;color:var(--red)">Failed to load bugs — ${esc(e.message)}</div>`;
  }
}

function bugStatusBadge(st) {
  const cls = { open: 'suspended', in_progress: 'trial', pending_review: 'anon', resolved: 'claimed' }[st] || 'anon';
  return `<span class="badge ${cls}">${st.replace('_', ' ')}</span>`;
}

function renderBugList(arr) {
  if (!arr || arr.length === 0) {
    return `<div class="empty" style="padding:20px">No reports${bugFilter ? ` with status ${bugFilter}` : ''}.</div>`;
  }
  return arr.map(b => `
    <div class="ev" style="cursor:pointer" onclick="loadBug('${b.id}')">
      <div class="ev-type">${esc(b.title)} ${bugStatusBadge(b.status)}${b.has_attachment ? ' 📎' : ''}</div>
      <div class="ev-vals">${esc(b.category)} · ${esc(b.platform)} · ${esc(b.app_version)}${b.assigned_branch ? ` · ${esc(b.assigned_branch)}` : ''}</div>
      <div class="ev-meta">${fmtDate(b.created_at)} · ${shortId(b.id)}</div>
    </div>
  `).join('');
}

async function loadBug(id) {
  try {
    const b = await api('GET', `/v1/admin/bugs/${id}`);
    document.getElementById('bugDetail').innerHTML = renderBugDetail(b);
    document.getElementById('bugDetail').scrollIntoView({ behavior: 'smooth' });
  } catch (e) { toast(e.message, 'err'); }
}

function renderBugDetail(b) {
  return `
    <div class="card">
      <h3><span class="accent">◇</span> ${esc(b.title)}</h3>
      <div class="badges" style="margin-bottom:10px">
        ${bugStatusBadge(b.status)}
        <span class="badge anon">${esc(b.category)}</span>
        <span class="badge anon">${esc(b.platform)} · ${esc(b.app_version)}</span>
      </div>
      <div class="stats">
        <div class="stat"><div class="k">filed</div><div class="v dim">${fmtDate(b.created_at)}</div></div>
        <div class="stat"><div class="k">reporter</div><div class="v dim">${b.user_id ? `<a href="#" style="color:var(--blue);text-decoration:none" onclick="loadUser('${b.user_id}');return false">${shortId(b.user_id)}</a>` : '—'}</div></div>
        <div class="stat"><div class="k">branch</div><div class="v dim">${b.assigned_branch ? esc(b.assigned_branch) : '—'}</div></div>
      </div>
      ${b.steps ? `<div class="stat" style="margin-top:10px"><div class="k">steps</div><div class="v dim" style="font-size:12px;white-space:pre-wrap">${esc(b.steps)}</div></div>` : ''}
      ${b.route ? `<div class="stat" style="margin-top:10px"><div class="k">route</div><div class="v dim mono" style="font-size:12px">${esc(b.route)}</div></div>` : ''}
      ${b.has_attachment ? `<div style="margin-top:10px"><a href="/v1/admin/bugs/${b.id}/attachment" target="_blank" style="color:var(--blue)">View attachment (${esc(b.attachment_mime || 'file')})</a>${getToken() ? '<div class="ev-meta">Opens same-origin; if it 403s, use the CF-protected console.</div>' : ''}</div>` : ''}
      ${b.resolution_note ? `<div class="stat" style="margin-top:10px"><div class="k">resolution ${b.acknowledged_at ? '(seen by reporter)' : '(not yet seen)'}</div><div class="v dim" style="font-size:12px;white-space:pre-wrap">${esc(b.resolution_note)}</div></div>` : ''}
      <hr class="sep">
      ${b.status === 'open' ? `
      <div class="row cols-2">
        <input type="text" id="claimBranch" placeholder="branch (e.g. fix/${shortId(b.id)})" autocomplete="off" spellcheck="false">
        <button class="btn amber" onclick="claimBug('${b.id}')">CLAIM</button>
      </div>` : ''}
      ${b.status !== 'resolved' ? `
      <div class="row">
        <textarea id="resolveNote" placeholder="resolution note — shown to the reporter verbatim" style="min-height:60px"></textarea>
      </div>
      <button class="btn green" onclick="resolveBug('${b.id}')">RESOLVE</button>` : ''}
      ${b.status !== 'open' ? `<button class="btn ghost" style="margin-top:8px" onclick="reopenBug('${b.id}')">REOPEN${b.assigned_branch ? ' (releases claim)' : ''}</button>` : ''}
    </div>
  `;
}

async function claimBug(id) {
  const branch = document.getElementById('claimBranch').value.trim();
  if (!branch) { toast('branch name?', 'err'); return; }
  try {
    await api('POST', `/v1/admin/bugs/${id}/claim`, { branch });
    toast('claimed');
    loadBugs(); loadBug(id);
  } catch (e) { toast(e.message, 'err'); loadBug(id); }
}

async function resolveBug(id) {
  const note = document.getElementById('resolveNote').value.trim();
  if (!note) { toast('resolution note is required — the reporter sees it', 'err'); return; }
  try {
    await api('POST', `/v1/admin/bugs/${id}/resolve`, { note });
    toast('resolved');
    loadBugs(); loadBug(id);
  } catch (e) { toast(e.message, 'err'); loadBug(id); }
}

async function reopenBug(id) {
  if (!confirm('Reopen this report? Any claim is released.')) return;
  try {
    await api('POST', `/v1/admin/bugs/${id}/reopen`);
    toast('reopened');
    loadBugs(); loadBug(id);
  } catch (e) { toast(e.message, 'err'); loadBug(id); }
}

registerView({ id: 'bugs', label: 'BUGS', show: showBugs });
