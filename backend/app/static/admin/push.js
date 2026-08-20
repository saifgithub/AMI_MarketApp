/* AMI Trade — Admin console PUSH view (CR200).
   Send a push to one named user over /v1/admin/push. Preview-before-send,
   same keyed-payload guard as MESSAGES: SEND arms only after a preview and
   only while the form still matches the previewed target byte-for-byte.
   Every push outcome is shown verbatim — a "sent" toast never papers over
   not_configured / rate_limited / duplicate / failed (CR040). */

let pushPreviewedTarget = null;
let pushPreviewedUser = null;

function showPush() {
  currentUser = null;
  setTab('push');
  document.getElementById('main').innerHTML = `
    <div class="card">
      <h3><span class="accent">◇</span> TARGET</h3>
      <div class="row cols-2">
        <input type="text" id="pushEmail" placeholder="email@… (or paste user id →)" autocomplete="off" spellcheck="false" oninput="pushInvalidate()">
        <input type="text" id="pushUserId" placeholder="user id (uuid)" autocomplete="off" spellcheck="false" oninput="pushInvalidate()">
      </div>
      <button class="btn ghost" onclick="pushPreview()">PREVIEW TARGET</button>
      <div id="pushTarget" style="margin-top:10px"></div>
    </div>

    <div class="card">
      <h3><span class="accent">◇</span> NOTIFICATION</h3>
      <div class="row">
        <label class="lbl" for="pushTitle">TITLE</label>
        <input type="text" id="pushTitle" maxlength="200" placeholder="title" autocomplete="off">
      </div>
      <div class="row">
        <label class="lbl" for="pushBody">BODY</label>
        <textarea id="pushBody" maxlength="1000" placeholder="body (≤280 chars recommended)" style="min-height:70px"></textarea>
      </div>
      <div class="row cols-2">
        <div>
          <label class="lbl" for="pushType">TYPE</label>
          <input type="text" id="pushType" value="admin_message" autocomplete="off" spellcheck="false">
        </div>
        <div>
          <label class="lbl" for="pushRoute">ROUTE (deep link, optional)</label>
          <input type="text" id="pushRoute" placeholder="/room" autocomplete="off" spellcheck="false">
        </div>
      </div>
      <button class="btn" id="pushSendBtn" onclick="pushSend()" disabled>SEND PUSH</button>
      <div class="mono" id="pushResult" style="margin-top:8px;font-size:12px;color:var(--text-med)"></div>
    </div>
  `;
}

function pushInvalidate() {
  pushPreviewedTarget = null;
  pushPreviewedUser = null;
  document.getElementById('pushTarget').innerHTML = '';
  document.getElementById('pushSendBtn').disabled = true;
}

function pushTargetKey() {
  return JSON.stringify({
    email: document.getElementById('pushEmail').value.trim(),
    user_id: document.getElementById('pushUserId').value.trim(),
  });
}

async function pushPreview() {
  const email = document.getElementById('pushEmail').value.trim();
  const uid = document.getElementById('pushUserId').value.trim();
  if (!email && !uid) { toast('email or user id', 'err'); return; }
  const payload = uid ? { user_id: uid } : { email };
  try {
    const r = await api('POST', '/v1/admin/push/preview', payload);
    pushPreviewedTarget = pushTargetKey();
    pushPreviewedUser = r.user;
    const u = r.user;
    const devices = (r.devices || []).map(d =>
      `${esc(d.device_model || '?')} · ${esc(d.os_version || '?')} · ${esc(d.app_version || '?')} · ${fmtRel(d.last_seen_at)}`
    ).join('<br>') || '<span style="color:var(--amber)">no registered devices</span>';
    document.getElementById('pushTarget').innerHTML = `
      <div class="stat">
        <div class="k">recipient</div>
        <div class="v dim" style="font-size:12px;line-height:1.6">
          ${esc(u.email || '(anonymous)')} · ${u.plan} · <span class="mono">${shortId(u.id)}</span><br>
          ${devices}
          ${r.push_configured ? '' : '<br><span style="color:var(--red)">OneSignal NOT configured — the durable row would be written but no push delivered.</span>'}
        </div>
      </div>`;
    document.getElementById('pushSendBtn').disabled = false;
  } catch (e) { pushInvalidate(); toast(e.message, 'err'); }
}

async function pushSend() {
  if (!pushPreviewedTarget || pushTargetKey() !== pushPreviewedTarget) {
    pushInvalidate();
    toast('target changed since preview — preview again', 'err');
    return;
  }
  const title = document.getElementById('pushTitle').value.trim();
  const body = document.getElementById('pushBody').value.trim();
  if (!title) { toast('title?', 'err'); return; }
  if (!body) { toast('body?', 'err'); return; }
  const who = pushPreviewedUser.email || shortId(pushPreviewedUser.id);
  if (!confirm(`Send push to ${who}?`)) return;
  const payload = {
    user_id: pushPreviewedUser.id,
    title, body,
    type: document.getElementById('pushType').value.trim() || 'admin_message',
  };
  const route = document.getElementById('pushRoute').value.trim();
  if (route) payload.route = route;
  try {
    const r = await api('POST', '/v1/admin/push', payload);
    const ok = r.push_status === 'sent';
    document.getElementById('pushResult').innerHTML =
      `push_status: <span style="color:${ok ? 'var(--green)' : 'var(--red)'}">${esc(r.push_status)}</span>` +
      (r.push_detail ? ` — ${esc(r.push_detail)}` : '') +
      ` · row ${shortId(r.notification_id)}`;
    toast(ok ? `pushed to ${who}` : `NOT pushed — ${r.push_status}`, ok ? 'ok' : 'err');
  } catch (e) { toast(e.message, 'err'); }
}

registerView({ id: 'push', label: 'PUSH', show: showPush });
