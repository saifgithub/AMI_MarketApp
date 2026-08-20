/* AMI Trade — Admin console MESSAGES view (CR103, split from admin.html in
   CR200). Tester broadcasts + replies, preview-before-send enforced
   client-side: SEND is keyed to the exact previewed payload, not a boolean —
   a stale form can never send (the server never orders the preview/send
   calls — scripts/messages.sh honours the same contract). */

let msgPreviewedPayload = null;
let msgPreviewCount = 0;

function viewMessages() {
  return `
    <div class="card">
      <h3><span class="accent">◇</span> COMPOSE</h3>
      <div class="row">
        <label class="lbl" for="msgTitle">TITLE</label>
        <input type="text" id="msgTitle" maxlength="200" placeholder="title" autocomplete="off" oninput="msgInvalidate()">
      </div>
      <div class="row">
        <label class="lbl" for="msgBody">BODY</label>
        <textarea id="msgBody" maxlength="4000" placeholder="message body" style="min-height:88px" oninput="msgInvalidate()"></textarea>
      </div>
      <div class="row cols-2">
        <div>
          <label class="lbl" for="msgPriority">PRIORITY</label>
          <select id="msgPriority" onchange="msgInvalidate()">
            <option value="normal" selected>normal</option>
            <option value="high">high</option>
          </select>
        </div>
        <div>
          <label class="lbl" for="audMode">AUDIENCE</label>
          <select id="audMode" onchange="msgModeChanged()">
            <option value="all" selected>all testers</option>
            <option value="build">build older than…</option>
            <option value="active">active within N days</option>
            <option value="dormant">dormant beyond N days</option>
            <option value="user">specific user ids</option>
          </select>
        </div>
      </div>
      <div class="row" id="audBuild" style="display:none">
        <label class="lbl" for="audVersion">APP VERSION LT</label>
        <input type="text" id="audVersion" placeholder="0.1.0+55" autocomplete="off" spellcheck="false" oninput="msgInvalidate()">
      </div>
      <div class="row" id="audActivity" style="display:none">
        <label class="lbl" for="audDays">DAYS</label>
        <input type="number" id="audDays" min="1" placeholder="e.g. 7" oninput="msgInvalidate()">
      </div>
      <div class="row" id="audUser" style="display:none">
        <label class="lbl" for="audUserIds">USER IDS (whitespace-separated)</label>
        <textarea id="audUserIds" placeholder="uuid uuid …" spellcheck="false" oninput="msgInvalidate()"></textarea>
      </div>
      <div class="row cols-2">
        <button class="btn ghost" onclick="msgPreview()">PREVIEW</button>
        <button class="btn" id="msgSendBtn" onclick="msgSend()" disabled>SEND</button>
      </div>
      <div class="mono" id="previewResult" style="margin-top:4px;font-size:12px;color:var(--text-med)"></div>
    </div>

    <div class="card">
      <h3><span class="accent">◇</span> BROADCASTS</h3>
      <div class="events" id="broadcastList"></div>
    </div>

    <div class="card">
      <h3><span class="accent">◇</span> REPLIES</h3>
      <div class="row cols-2">
        <input type="number" id="replyDays" min="1" placeholder="last N days (blank = all)">
        <button class="btn ghost" onclick="loadReplies()">REFRESH</button>
      </div>
      <div class="events" id="replyList"></div>
    </div>
  `;
}

function renderBroadcasts(arr) {
  if (!arr || arr.length === 0) {
    return `<div class="empty" style="padding:20px">No broadcasts yet.</div>`;
  }
  return arr.map(b => `
    <div class="ev">
      <div class="ev-type">${esc(b.title)} <span class="badge pri-${b.priority}">${b.priority}</span></div>
      <div class="ev-vals">→ ${b.recipient_count} sent · ${b.reply_count} replies</div>
      <div class="ev-meta">${fmtDate(b.created_at)} · ${shortId(b.id)} · ${esc(JSON.stringify(b.audience))}</div>
    </div>
  `).join('');
}

function renderReplies(arr) {
  if (!arr || arr.length === 0) {
    return `<div class="empty" style="padding:20px">No replies.</div>`;
  }
  return arr.map(r => `
    <div class="ev">
      <div class="ev-type"><a href="#" class="mono" style="color:var(--blue);text-decoration:none" onclick="loadUser('${r.user_id}');return false">${shortId(r.user_id)}</a>${r.broadcast_id ? ` · re ${shortId(r.broadcast_id)}` : ''}</div>
      <div class="ev-vals" style="white-space:pre-wrap">${esc(r.body)}</div>
      <div class="ev-meta">${fmtDate(r.created_at)}</div>
    </div>
  `).join('');
}

function showMessages() {
  currentUser = null;
  setTab('messages');
  document.getElementById('main').innerHTML = viewMessages();
  msgInvalidate();
  loadBroadcasts();
  loadReplies();
}

function msgModeChanged() {
  const mode = document.getElementById('audMode').value;
  document.getElementById('audBuild').style.display = mode === 'build' ? '' : 'none';
  document.getElementById('audActivity').style.display = (mode === 'active' || mode === 'dormant') ? '' : 'none';
  document.getElementById('audUser').style.display = mode === 'user' ? '' : 'none';
  msgInvalidate();
}

// Any edit kills the previewed state — SEND re-arms only after a fresh preview.
function msgInvalidate() {
  msgPreviewedPayload = null;
  msgPreviewCount = 0;
  document.getElementById('previewResult').textContent = '';
  document.getElementById('msgSendBtn').disabled = true;
}

function msgBuildPayload() {
  const title = document.getElementById('msgTitle').value.trim();
  const body = document.getElementById('msgBody').value.trim();
  if (!title) { toast('title?', 'err'); return null; }
  if (!body) { toast('body?', 'err'); return null; }
  const priority = document.getElementById('msgPriority').value;
  const mode = document.getElementById('audMode').value;
  let audience;
  if (mode === 'all') {
    audience = { mode: 'all' };
  } else if (mode === 'build') {
    const v = document.getElementById('audVersion').value.trim();
    if (!/\+\d+$/.test(v)) { toast('version needs a +<build> suffix, e.g. 0.1.0+55', 'err'); return null; }
    audience = { mode: 'build', app_version_lt: v };
  } else if (mode === 'active' || mode === 'dormant') {
    const days = parseInt(document.getElementById('audDays').value, 10);
    if (!days || days < 1) { toast('days?', 'err'); return null; }
    audience = mode === 'active'
      ? { mode: 'activity', active_within_days: days }
      : { mode: 'activity', dormant_beyond_days: days };
  } else {
    const ids = document.getElementById('audUserIds').value.trim().split(/\s+/).filter(Boolean);
    if (ids.length === 0) { toast('user ids?', 'err'); return null; }
    audience = { mode: 'user', user_ids: ids };
  }
  return { title, body, priority, audience };
}

async function msgPreview() {
  const payload = msgBuildPayload();
  if (!payload) return;
  try {
    const r = await api('POST', '/v1/admin/messages/preview', payload);
    msgPreviewedPayload = JSON.stringify(payload);
    msgPreviewCount = r.recipient_count;
    document.getElementById('previewResult').textContent = `→ ${r.recipient_count} recipients`;
    document.getElementById('msgSendBtn').disabled = r.recipient_count === 0;
    if (r.recipient_count === 0) toast('0 recipients — excluded/suspended ids preview as 0 by design', 'err');
  } catch (e) { msgInvalidate(); toast(e.message, 'err'); }
}

async function msgSend() {
  const payload = msgBuildPayload();
  if (!payload) return;
  // Even if an invalidation event slipped by, a payload that is not
  // byte-identical to the previewed one never sends.
  if (!msgPreviewedPayload || msgPreviewCount === 0 || JSON.stringify(payload) !== msgPreviewedPayload) {
    msgInvalidate();
    toast('form changed since preview — preview again', 'err');
    return;
  }
  if (!confirm(`Send to ${msgPreviewCount} recipients?`)) return;
  try {
    const r = await api('POST', '/v1/admin/messages', payload);
    toast(`sent ${shortId(r.broadcast_id)} → ${r.recipient_count} recipients`);
    showMessages();
  } catch (e) { toast(e.message, 'err'); }
}

async function loadBroadcasts() {
  const el = document.getElementById('broadcastList');
  try {
    el.innerHTML = renderBroadcasts(await api('GET', '/v1/admin/messages'));
  } catch (e) {
    el.innerHTML = `<div class="empty" style="padding:20px;color:var(--red)">Failed to load broadcasts — ${esc(e.message)}</div>`;
  }
}

async function loadReplies() {
  const el = document.getElementById('replyList');
  const days = parseInt(document.getElementById('replyDays').value, 10);
  // toISOString() ends in 'Z' — a '+00:00' offset 422s (raw '+' in a query string decodes as a space).
  const qs = days >= 1 ? '?since=' + new Date(Date.now() - days * 86400000).toISOString() : '';
  try {
    el.innerHTML = renderReplies(await api('GET', '/v1/admin/messages/replies' + qs));
  } catch (e) {
    el.innerHTML = `<div class="empty" style="padding:20px;color:var(--red)">Failed to load replies — ${esc(e.message)}</div>`;
  }
}

registerView({ id: 'messages', label: 'MESSAGES', show: showMessages });
