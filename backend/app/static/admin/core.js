/* AMI Trade — Admin console core (CR200, split from admin.html).
   Shared plumbing every view file uses: token storage, the api() helper,
   toast, formatters, esc(), and the VIEWS tab registry. View files
   (users.js, messages.js, …) call registerView() at load time; the shell
   builds the nav from the registry, so a new module is one more file +
   one more <script> tag — no shell edits. Plain scripts, no build step. */

const TOKEN_KEY = 'ami_admin_token';
const API = ''; // same-origin

// ── token plumbing ────────────────────────────────────────────────────────
function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function logout() {
  if (!confirm('Clear admin token from this device?')) return;
  localStorage.removeItem(TOKEN_KEY);
  location.reload();
}

// ── api calls ─────────────────────────────────────────────────────────────
// Authorization is attached only when a token is stored: under Cloudflare
// Access (CR200) the edge injects Cf-Access-Jwt-Assertion and no local
// token exists at all.
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  const token = getToken();
  if (token) opts.headers['Authorization'] = 'Bearer ' + token;
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    let msg = (data && data.detail) ? data.detail : (typeof data === 'string' ? data : `HTTP ${res.status}`);
    // FastAPI 422 detail is an array of error objects — join it or it renders "[object Object]".
    if (Array.isArray(msg)) msg = msg.map(d => `${(d.loc || []).join('.')}: ${d.msg}`).join('; ');
    throw new Error(msg);
  }
  return data;
}

// ── toast helper ──────────────────────────────────────────────────────────
let toastTimer;
function toast(msg, kind) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show ' + (kind || 'ok');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}

// ── formatters ────────────────────────────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function fmtRel(iso) {
  if (!iso) return '—';
  const d = new Date(iso); const now = new Date();
  const days = Math.round((d - now) / 86400000);
  if (days === 0) return 'today';
  if (days > 0) return `in ${days}d`;
  return `${-days}d ago`;
}
function shortId(uuid) { return uuid ? uuid.substring(0, 8) : ''; }
// Free text (tester-typed replies, bug reports, …) — escape before
// interpolating into innerHTML.
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ── view registry + tabs ──────────────────────────────────────────────────
// Each view file registers { id, label, show } at load time; script order in
// admin.html is tab order.
const VIEWS = [];
function registerView(v) { VIEWS.push(v); }

function buildTabs() {
  document.getElementById('tabs').innerHTML = VIEWS.map(v =>
    `<button class="tab" id="tab-${v.id}" onclick="showView('${v.id}')">${v.label}</button>`
  ).join('');
}

function setTab(id) {
  VIEWS.forEach(v => {
    document.getElementById('tab-' + v.id).classList.toggle('active', v.id === id);
  });
}

function showView(id) {
  const v = VIEWS.find(x => x.id === id);
  if (!v) return;
  setTab(id);
  v.show();
}

// ── setup screen ──────────────────────────────────────────────────────────
function viewSetup() {
  return `
    <div class="setup">
      <div class="card">
        <h3><span class="accent">◇</span> ADMIN ACCESS</h3>
        <p class="lead">Paste the ADMIN_SECRET (64-hex from <span class="mono">infra/alpha.env</span>). Stored in localStorage on this device only.</p>
        <div class="row">
          <label class="lbl" for="tokenInput">SECRET</label>
          <input type="text" id="tokenInput" placeholder="hex…" autocomplete="off" spellcheck="false">
        </div>
        <button class="btn" onclick="saveToken()">UNLOCK</button>
      </div>
    </div>
  `;
}

function saveToken() {
  const v = document.getElementById('tokenInput').value.trim();
  if (!v) { toast('paste a value first', 'err'); return; }
  setToken(v);
  bootstrap();
}

// ── boot ──────────────────────────────────────────────────────────────────
// Probe a known-good read endpoint. Under Cloudflare Access this succeeds
// with no stored token (the edge injects the CF JWT); on 403 fall back to
// the token-setup view.
async function bootstrap() {
  buildTabs();
  try {
    await api('GET', '/v1/admin/config-check');
    document.getElementById('logoutBtn').style.display = getToken() ? '' : 'none';
    document.getElementById('tabs').style.display = '';
    showView(VIEWS[0].id);
  } catch (e) {
    if (getToken()) {
      localStorage.removeItem(TOKEN_KEY);
      toast(e.message || 'auth failed', 'err');
    }
    document.getElementById('logoutBtn').style.display = 'none';
    document.getElementById('tabs').style.display = 'none';
    document.getElementById('main').innerHTML = viewSetup();
  }
}
