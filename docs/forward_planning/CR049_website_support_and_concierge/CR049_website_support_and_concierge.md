# CR049 — Website go-live: support intake + Concierge chatbot + security

**Status:** in_progress · **Opened:** 2026-07-21 · **Track:** R64
**Owner split:** Claude ships code + drafts FAQ; Saiful reviews FAQ copy, provisions dashboards (Turnstile, Email Routing, Resend sender), gates deploy.

---

## Why

We're preparing the marketing site (`www.agenticmarketintel.ai`) to go live. Today the site
(`website/`) + its API (`website_api/`) ship almost nothing dynamic — only a waitlist form.
Saiful (as webmaster brief) wants, before launch:

1. Customers can reach `support.ai@agenticmarketintel.ai` and get questions handled automatically.
2. A "Concierge" chatbot on the site to help visitors.
3. Reuse as much existing code as possible.
4. Security appropriate to a public, finance-adjacent surface.

## Hard constraint (preserved)

`website/` and `website_api/` touch **zero** app-backend (`backend/`) code — WEBSITE.md's core
security decision: a website compromise must not reach `ami_trade` data. We honor it by
**porting** proven code into `website_api` (the vLLM streaming client, the rate limiter, the
Resend sender), never importing from `backend/`.

## Decisions (locked with Saiful, 2026-07-21)

| Question | Decision |
|---|---|
| Email intake | Contact form + Cloudflare Email Routing (mailbox → Gmail) for general inquiries; a **separate DB-backed form** for username / data-deletion requests. |
| Auto-handling | **AI auto-answers FAQs.** → guardrails must be structural (CR038), not prompt-only. |
| Chatbot backend | **Isolated in `website_api`**, calling the on-prem model directly over the LAN. |
| Support address | `support.ai@agenticmarketintel.ai`. Also fix footer `hello@agenticmarketintel.com` → `.ai`. |

## Scope

### A. Concierge chatbot (isolated)
- Port `VLLMProvider.stream_chat` (backend `llm_gateway.py`) → `website_api/app/services/llm_client.py`.
- `faq_answer.py` shared engine: KB-grounded, deterministic escalation pre-filter (advice-seeking /
  account / legal → never auto-answer), server-appended simulation-only disclaimer, scripted
  fallback on vLLM outage (degrade loudly, CR040).
- `POST /concierge/message` SSE route (`event: token|error|done`), caps: msg ≤ 2000 chars,
  history ≤ 8 turns, `max_tokens` ≤ 512.
- Front-end floating widget in `index.html`, vanilla-JS SSE + typewriter, site design tokens.

### B. General-inquiry contact form + AI auto-answer
- `ContactMessage` table (auto-created via `Base.metadata.create_all`; no Alembic in website_api).
- `POST /contact`: Turnstile + rate-limit + validate → store → `faq_answer` → auto-reply (Resend)
  or ack + notify Saiful. Store-first, tolerant intake (never lose a message).
- CF Email Routing forwards `support.ai@` → Gmail for people who email directly.

### C. Data-request form (compliance intake)
- `DataRequest` table (email, request_type deletion|access|correction|other, status, created_at,
  due_at = +30d). `POST /data-request`: store → ack → notify. **No AI answer.**
- Dedicated `website/data-request/index.html`, linked from footer + privacy page.

### D. Security
- Cloudflare Turnstile on all public POSTs + concierge (closes the no-bot-protection gap).
- Ported sliding-window `RateLimiter` (concierge 5/min, contact 3/min, data-request 3/min).
- LLM abuse caps; KB-only grounding; no raw model/provider exposure; audit log.
- New settings (`vllm_*`, `resend_*`, `turnstile_secret`, `notify_email`) in website_api config +
  forwarded in the compose `api-website` env block. PII retention noted.
- `httpx` promoted from dev-only to runtime dep.

### E. Copy fixes / wiring
- Footer + waitlist error email → `support.ai@agenticmarketintel.ai`.
- Front-end fetch targets → `https://api-website.agenticmarketintel.ai/{concierge/message,contact,data-request}`.

## Acceptance

- `pytest website_api/tests/ -v` green, including: escalation filter refuses advice-seeking input;
  contact auto-answer vs escalate paths; data-request row + due_at; rate-limit 429; Turnstile
  bypass when secret unset (local).
- Local: uvicorn + curl exercises `/health`, `/concierge/message` (SSE stream), `/contact`,
  `/data-request`; static site served, widget + both forms drive the local API.
- `pytest backend/tests/unit/ -q` unaffected (isolation intact).
- No import from `backend/` anywhere under `website_api/` or `website/`.

## Out of scope / Saiful-owned
- Dashboard: Turnstile keys, Email Routing, tunnel hostname (code degrades gracefully without them).
- `faq.md` content review; Resend sender/domain verification for `support.ai@`.
- Deploy timing (FTP push + `ami_website_api` rebuild) gated on Saiful's go-ahead.
