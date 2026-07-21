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

## What still needs doing

### 1. Deploy website files to hosting (priority)

**Hosting:** cPanel at `server373.web-hosting.com`
**FTP:** `claude@agenticmarketintel.ai` on `ftp.agenticmarketintel.ai:21`

Run from inside `website/`:
```bash
cd "/Volumes/Extreme Pro/AMI_MarketApp/website"
python3 deploy_ftp.py YOUR_FTP_PASSWORD
```

The script lists the FTP root first. Confirm `index.html` should go to the root (or adjust `target` in the script). Do NOT deploy `deploy_ftp.py`, `WEBSITE.md`, or `website_api/` — static files only.

**Files to deploy:** `index.html`, `assets/`, `sitemap.xml`, `robots.txt`, `privacy/`, `terms/`, `ami-trade/` (the `sad-to-see-you-go` deletion page).

### CR049 go-live steps (Saiful — dashboards + .env)

The code degrades gracefully without these, so nothing breaks if they're skipped — but the
Concierge/auto-answer and bot protection stay off until they're set:

1. **melehost `.env`** — add: `VLLM_BASE_URL=http://192.168.20.74:8000` (usually already set for api-alpha), `RESEND_API_KEY=…`, `WEBSITE_NOTIFY_EMAIL=<your inbox>` (where contact escalations + data requests land), and later `TURNSTILE_SECRET=…`. Then `docker compose up -d --build api-website`.
2. **Resend** — verify `support.ai@agenticmarketintel.ai` (or the `agenticmarketintel.ai` domain) as a sender so auto-answers/acks deliver.
3. **Cloudflare Email Routing** — forward `support.ai@agenticmarketintel.ai` → your Gmail, so people who email directly (not via the form) still reach you.
4. **Cloudflare Turnstile** — create a widget; paste the **site key** into `TURNSTILE_SITEKEY` in `index.html` **and** `ami-trade/sad-to-see-you-go/index.html`, and the **secret** into `.env` as `TURNSTILE_SECRET`.
5. **Review `website_api/app/knowledge/faq.md`** — confirm the pricing wording and agent-count wording before launch (see the comment at the top of that file).

### 2. Deploy `website_api` on melehost

Three steps:

**a) Create the database:**
```bash
ssh melehost "docker exec ami_postgres psql -U postgres -c 'CREATE DATABASE ami_website;'"
```

**b) Add service to `~/ami_trade/docker-compose.yml`:**
```yaml
ami_website_api:
  build:
    context: ./website_api
  container_name: ami_website_api
  restart: unless-stopped
  environment:
    ENV: prod
    DATABASE_URL: postgresql+psycopg2://postgres:${POSTGRES_PASSWORD}@ami_postgres:5432/ami_website
    CORS_ORIGIN: https://www.agenticmarketintel.ai
  ports:
    - "8001:8000"
  depends_on:
    ami_postgres:
      condition: service_healthy
  extra_hosts:
    - "host.docker.internal:host-gateway"
```

Then rsync and start:
```bash
# rsync website_api/ to melehost
ssh melehost "cd ~/ami_trade && docker compose up -d ami_website_api"
```

**c) Add Cloudflare Tunnel route:**
- Zero Trust dashboard → Networks → Tunnels → your existing tunnel → Edit
- Public Hostname tab → Add hostname:
  - Subdomain: `api-website` · Domain: `agenticmarketintel.ai`
  - Service: `http://host.docker.internal:8001`
- No new token needed — uses the same `CF_TUNNEL_TOKEN` already in melehost `.env`

### 3. Replace iPhone placeholder frames

The app preview section (`#app-preview`) has CSS placeholder frames. Replace with real screenshots when ready:
- Drop screenshots into `website/assets/img/`
- In `index.html` find the three `.screen-placeholder` divs and replace with `<img src="assets/img/YOUR_SCREENSHOT.png">`

### 4. Create OG image

`og-image.png` (1200×630) is referenced in meta tags but doesn't exist yet.
- Dark canvas (`#0f172a`) + AMI matrix logo + "13 AI agents. One decision." headline
- Place at `website/assets/img/og-image.png`
- Update the meta tag path once done

---

## Running locally

```bash
# Serve the static site
cd "/Volumes/Extreme Pro/AMI_MarketApp/website"
python3 -m http.server 8765
# → http://localhost:8765

# Run the website_api (SQLite, no Postgres needed)
cd "/Volumes/Extreme Pro/AMI_MarketApp/website_api"
uvicorn app.main:app --reload --port 8001

# Run website_api tests
cd "/Volumes/Extreme Pro/AMI_MarketApp/website_api"
/path/to/venv/bin/pytest tests/ -v
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
| FTP password | Ask Saiful |
| FTP user | `claude@agenticmarketintel.ai` |
| FTP host | `ftp.agenticmarketintel.ai` (resolves to 69.57.162.213) |
| cPanel | `server373.web-hosting.com:2083` |
| Cloudflare tunnel token | melehost `~/ami_trade/.env` → `CF_TUNNEL_TOKEN` |
