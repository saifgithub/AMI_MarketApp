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
| Endpoints | `POST /waitlist`, `GET /health` |
| Tests | `website_api/tests/test_waitlist.py` — 5/5 passing |

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

**Files to deploy:** `index.html`, `assets/`, `sitemap.xml`, `robots.txt`

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
