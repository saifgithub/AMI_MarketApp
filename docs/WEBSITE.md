# AMI Trade — Marketing Website

All website work lives under two folders:

| Folder | Purpose |
|---|---|
| `website/` | Static HTML marketing site — everything that gets deployed to `www.agenticmarketintel.ai` |
| `website_api/` | Standalone FastAPI micro-service — waitlist endpoint, isolated database |

**Rule:** nothing in either folder touches the main app backend (`backend/`). Zero shared code.

---

## What's built

### `website/` — static marketing site

Single-page HTML site with 10 sections:

| Section | ID | Notes |
|---|---|---|
| Header | — | Sticky glass, AMI matrix logo, mobile hamburger |
| Hero | `#hero` | "13 AI agents. One decision. No shortcuts." + 7-hex tessellation |
| Applied AI | `#applied-ai` | Company positioning — "Not a chatbot. Not a co-pilot." |
| The Problem | `#problem` | Why education apps + generic AI both fail |
| How It Works | `#how-it-works` | 5 phase panels — the agent system in motion |
| The Agents | `#agents` | 13-agent radial honeycomb — Concierge at centre |
| Comparison | `#compare` | vs Finelo / ChatGPT / Paper trading |
| App Preview | `#app-preview` | iPhone frames (placeholders — needs real screenshots) |
| Pricing | `#pricing` | 3 tiers, no exact prices yet |
| Waitlist CTA | `#waitlist` | Email capture → `website_api` |
| Footer | — | — |

**Design system:** AMI Hex-Reinforced Precision
- Fonts: IBM Plex Sans / Mono / Arabic — self-hosted in `assets/fonts/` (28 woff2 files)
- Source: `/Volumes/Extreme Pro/AMI AI Design System/` — read-only mount
- Tokens: `assets/css/tokens.css` (colours, spacing, clip-paths)
- Site styles: `assets/css/site.css`
- SVGs: `assets/svg/` — ami_logo_matrix.svg, hex_mesh.svg, logo_hex.svg, icon_ami.svg

**SEO:**
- Title + meta description set
- Structured data (SoftwareApplication + Organization schema)
- Open Graph + Twitter Card
- `sitemap.xml` + `robots.txt`
- hreflang: en (primary), ms (placeholder for future Malay)

**Agents section — hex honeycomb geometry:**
- 13 agents, absolute-positioned in a 4-5-4 radial pattern
- W=140px, H=121px (= W × √3/2), row-spacing = H × 0.75 = 91px
- Concierge (purple glow) at centre (350, 152)
- 6 ring agents (h-ring class, brighter): Fundamentals, Market, Bull, Bear, Portfolio Mgr, Trader
- 6 outer agents (darker): News, Social Media, Research Mgr, Neutral, Aggressive, Conservative
- Mobile fallback (<560px): simple flex-wrap grid

### `website_api/` — waitlist micro-service

Standalone FastAPI service. **Completely separate from the main app.**

| Item | Value |
|---|---|
| Database | `ami_website` (NOT `ami_trade`) |
| Container | `ami_website_api` |
| Port | 8001 (external) → 8000 (internal) |
| Hostname | `api-website.agenticmarketintel.ai` |
| Endpoints | `POST /waitlist`, `POST /concierge/message` (SSE), `POST /contact`, `POST /data-request`, `GET /health` |
| Tests | `website_api/tests/` — 23/23 passing |

### CR049 — support intake + Concierge chatbot

Added three public capabilities (still **zero shared code** with `backend/` — the vLLM
streaming client, rate limiter, and Resend sender are *ported copies*, not imports):

- **Concierge chatbot** — `POST /concierge/message` (SSE, `event: token|error|done`). Streams
  the on-prem model (`VLLM_BASE_URL`, LAN-direct) grounded **only** in
  `app/knowledge/faq.md`. A deterministic pre-filter (`faq_answer.classify_escalation`) routes
  advice/account/legal questions to a human and never lets them reach the model; the
  simulation-only disclaimer is appended by the server. Front-end: floating widget in
  `index.html`.
- **Contact form** — `POST /contact`. Stores the message, then AI-auto-answers FAQ questions by
  email (Resend) or escalates to `NOTIFY_EMAIL`. Front-end: `#contact` section.
- **Data-request form** — `POST /data-request`. Access/deletion (GDPR/CCPA/Play-Store), logged
  with a 30-day SLA, human-actioned, never AI-answered. Front-end page:
  `ami-trade/sad-to-see-you-go/index.html` (URL `/ami-trade/sad-to-see-you-go`), linked from the
  footer + privacy page.

Security: Cloudflare Turnstile on the two form POSTs (bypassed until `TURNSTILE_SECRET` is set),
ported sliding-window rate limiter, LLM input/token caps. All settings degrade gracefully when
their env var is unset, so the site runs locally with no secrets.

`POST /waitlist` body: `{ "email": "...", "source": "marketing_site" }`
- Validates email (regex)
- Idempotent — duplicate returns `{ "ok": true, "new": false }`
- Normalises email to lowercase + trimmed

---

## Deploying

Both tiers ship by rsync over SSH. **FTP is retired** (`scripts/deploy_ftp_legacy.py`
is kept for reference only).

### Static site → cPanel

```bash
cd "/Volumes/Extreme Pro/AMI_MarketApp"
# ALWAYS dry-run first (-n) and read the deletions before removing it
rsync -avz --delete \
  --exclude='.DS_Store' --exclude='.well-known/' --exclude='.ftpquota' --exclude='cgi-bin/' \
  website/ ami-web:agenticmarketintel.ai/
```

Three things about that command are load-bearing:

- **The target is `agenticmarketintel.ai/`, the addon-domain docroot — NOT `public_html`.**
  `~/public_html` hosts a different site entirely. Deploying there would overwrite it.
- **The `.well-known/` and `.ftpquota` excludes are not optional.** They exist on the
  server and not in our source, so `--delete` would remove them; losing `.well-known/`
  can break domain verification and certificate issuance.
- **`website/` must contain deployable content only.** It is what makes `--delete` safe.
  Until CR072 it also held `Archive.zip`, `WEBSITE.md` and `deploy_ftp.py`, all of which
  were publicly served for months; CR049 deleted them from the server but left them in
  the source, so the next deploy would have restored them. Don't put anything in
  `website/` you would not publish.

**Cloudflare caches static assets for 7 days; HTML is `DYNAMIC` (served fresh).** So any
change to `assets/css/site.css` is invisible to returning visitors until the `?v=` query
on the `<link>` is bumped — in **all four** pages (`index.html`, `privacy/`, `terms/`,
`ami-trade/sad-to-see-you-go/`). Current version: `?v=cr072`. Verify a bump landed with:

```bash
curl -sSI 'https://agenticmarketintel.ai/assets/css/site.css?v=cr072' | grep -i cf-cache-status
# MISS on the first request = the new file is being fetched from origin
```

### `website_api` → melehost

```bash
cd "/Volumes/Extreme Pro/AMI_MarketApp"
rsync -avz --delete \
  --exclude='__pycache__/' --exclude='*.pyc' --exclude='.pytest_cache/' \
  --exclude='.venv/' --exclude='*.db' --exclude='.DS_Store' \
  website_api/ melehost:~/ami_trade/website_api/
ssh melehost "cd ~/ami_trade && docker compose up -d --build api-website"
curl -sS https://api-website.agenticmarketintel.ai/health     # {"ok":true}
```

Service name is `api-website`, container `ami_website_api`, port 8001, public via the
Cloudflare Tunnel hostname `api-website.agenticmarketintel.ai`.

**melehost's `.env` is not edited in place** — it is overwritten wholesale from
`infra/alpha.env` (Mac, gitignored) by `/promote-to-alpha`. Any new setting goes in
`infra/alpha.env` first, or it is silently lost on the next promote.

### Smoke checks after a website deploy

```bash
curl -sS https://agenticmarketintel.ai/ | grep -c 'honey-hex t-'          # 13 curriculum tracks
curl -sS https://agenticmarketintel.ai/ | grep -o 'site.css?v=[a-z0-9]*'  # cache-bust version
# nothing sensitive is served
for f in Archive.zip WEBSITE.md deploy_ftp.py; do
  curl -s -o /dev/null -w "$f %{http_code}\n" "https://agenticmarketintel.ai/$f"; done   # all 404
# the deterministic escalation floor still holds
curl -sS -N -X POST https://api-website.agenticmarketintel.ai/concierge/message \
  -H 'Content-Type: application/json' -d '{"message":"Is AAPL halal?"}' | head -3
```

---

## Open items (need Saiful)

| Item | State |
|---|---|
| **Turnstile SECRET** | Site key is live in both forms; the backend still bypasses verification because `TURNSTILE_SECRET` is unset. Forms work, bots are not blocked. Goes in `infra/alpha.env`, never melehost's `.env` directly. |
| **og-image** | A PIL-generated stopgap is live (1200x630, "13 AI agents. One decision."). Wants a designed replacement — and the site now leads on the curriculum too. |
| **Play internal-testing opt-in URL + TestFlight link** | Not yet supplied; every CTA points at the waitlist until they are. |
| **Lessons-comb screenshot** | For a fourth `#app-preview` frame showing the 13-facet Lessons screen. |
| **`Archive.zip` at the CF edge** | Origin returns 404; a cached edge copy may persist. One-click purge in the Cloudflare dashboard. |
| **Privacy policy s14** | `legal/policies/privacy_policy.md:148` and its live transcription still say "If you enable Halal/Shariah screening" — stale after DEF084's relabel. Legal track owns that document. |

## Running locally

```bash
# Serve the static site
cd "/Volumes/Extreme Pro/AMI_MarketApp/website"
python3 -m http.server 8765
# → http://localhost:8765

# Run the website_api (SQLite, no Postgres needed)
cd "/Volumes/Extreme Pro/AMI_MarketApp/website_api"
uvicorn app.main:app --reload --port 8001

# Run website_api tests (system python3 is fine — sqlite tempfile fixture)
cd "/Volumes/Extreme Pro/AMI_MarketApp/website_api"
python3 -m pytest tests/ -q     # 25 passing
```

---

## Key decisions

| Decision | Rationale |
|---|---|
| Static HTML (no framework) | No build step, SEO-native, fast |
| `website_api/` is a separate Python project | Zero shared code with app — reduces attack surface |
| `ami_website` database (not `ami_trade`) | Total separation — website compromise cannot touch app data |
| CORS locked to `agenticmarketintel.ai` | Only the real website can submit to the API |
| Self-hosted IBM Plex fonts | No Google Fonts CDN — works behind firewalls, no IP leak |
| Formspree removed | Our own DB, our own data — no third-party dependency |

---

## Contacts / credentials (DO NOT commit actual values)

| Item | Where |
|---|---|
| SSH to the web host | alias `ami-web` (`~/.ssh/config`) — key `~/.ssh/id_rsa_ami_webserver`, passphrase in the macOS Keychain. **This is the deploy path.** |
| Web docroot | `~/agenticmarketintel.ai/` on the web host — the addon domain. NOT `~/public_html` (different site). |
| cPanel | `server373.web-hosting.com:2083` |
| FTP (retired) | Superseded by SSH/rsync. `scripts/deploy_ftp_legacy.py` kept for reference; user `claude@agenticmarketintel.ai`, password from Saiful. |
| Cloudflare tunnel token | melehost `~/ami_trade/.env` → `CF_TUNNEL_TOKEN` |
