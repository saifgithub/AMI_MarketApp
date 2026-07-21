# DEF063 — CR023/CR024 live feeds are dark in Alpha: their API keys are never forwarded to the container

**Filed:** 2026-07-17 (AT:R59) · **Status:** Adanos half **resolved** 2026-07-21 (fresh key, verified live end-to-end — see follow-up below). Alpha Vantage half (`ALPHA_VANTAGE_API_KEY`) remains parked/unconfigured, separate open item. · **Found by:** Saiful ("I am sure CR024 had
delivered adanos. why have we not used it?") during the CR035/CR037 audit
· **Bug class:** identical to **DEF038** (OIDC audiences lived in `.env`, were never forwarded to
the container, so the feature silently ran with an empty value) — the comment recording DEF038
sits in the very same compose block.

## Symptom

The Social Media Analyst has been running on synthetic scaffolding in Alpha ever since CR024
shipped, despite the Adanos integration being fully built and the API key provisioned.
CR035's audit measured `social_source=None` on a live NVDA profile and, from that, CR037 was
originally filed on the false premise that "CR024 is pending".

## Root cause

`docker-compose.yml`'s `api-alpha` service enumerates its environment variables explicitly. It
**never references `ADANOS_API_KEY` or `ALPHA_VANTAGE_API_KEY`**, so they never reach the
container — even though:

- both keys are present and populated in the canonical `infra/alpha.env` on the Mac;
- `/promote-to-alpha` scp's that file to `melehost:~/ami_trade/.env` correctly;
- compose *does* read that `.env` for `${VAR}` interpolation — it just was never asked to.

Both features are gated on the "presence of the key turns it on" convention
(`config.py:101,108`), so an absent key means a silent, permanent fallback. There is no `.env`
inside the container (`env_file=".env"` in Settings resolves to nothing), so container env vars
are the only channel.

Verified on melehost 2026-07-17:

| Check | Result |
|---|---|
| `grep -c '^ADANOS_API_KEY=.\+' ~/ami_trade/.env` | `1` (present on host) |
| `docker exec ami_api_alpha env \| grep -c ADANOS` | `0` (absent in container) |
| `settings.adanos_api_key` in container | `False` |
| `settings.alpha_vantage_api_key` in container | `False` |
| `find / -name .env` in container | (nothing) |

## Impact

| Key | Feature | State |
|---|---|---|
| `ADANOS_API_KEY` | CR024 — Social Media Analyst live Reddit sentiment | **Dark since CR024 shipped.** Agent invents sentiment from `crc32(ticker)` scaffolding instead (see CR037's measurements: 2 distinct tone values across 32 tickers, 23/32 asserted unhedged) |
| `ALPHA_VANTAGE_API_KEY` | CR023 — News Analyst's sentiment-scored headline merge | **Dark since CR023 shipped.** Invisible because the Yahoo half works, so `news_source=live` reads healthy while the Alpha Vantage half silently never merges |
| `CONCIERGE_CONTEXT_MODE` | CR021 context router | Not forwarded either, but `alpha.env`'s value (`full_context`) equals the code default → no behavioural difference **today**; latent (editing alpha.env would do nothing) |
| `LUNARCRUSH_API_KEY` | — | Vestigial: no such setting exists in code (CR024 dropped LunarCrush, blocked on paid tier). Remove from alpha.env |

Not affected (checked, false alarms from a first-pass regex): `AMI_ENV` is forwarded under the
name `ENV` (`compose:71`), `CF_TUNNEL_TOKEN` as `TUNNEL_TOKEN` on the tunnel service
(`compose:177`).

## Fix

1. Add to the `api-alpha` environment block:
   `ADANOS_API_KEY: ${ADANOS_API_KEY:-}`, `ALPHA_VANTAGE_API_KEY: ${ALPHA_VANTAGE_API_KEY:-}`,
   `CONCIERGE_CONTEXT_MODE: ${CONCIERGE_CONTEXT_MODE:-full_context}`.
2. Drop the vestigial `LUNARCRUSH_API_KEY` from `infra/alpha.env(.example)`.
3. `/promote-to-alpha`, then verify `settings.adanos_api_key` is True in-container and that a
   live convene reports `social_source=live`.
4. **Prevention (the real fix):** a boot-time or promotion-time assertion that every key
   populated in `infra/alpha.env` is visible inside the container — this is the second time
   (DEF038, now DEF063) a shipped feature has been silently inert for want of one compose line.
   A `/v1/health`-adjacent diagnostic (`/v1/admin/config-check`) listing feature-gate keys and
   their on/off state would have surfaced both in seconds.

## Before enabling — cost gate (needs Saiful's call)

Adanos free tier is **250 calls/month** (confirmed via response headers during AT:R57).
`social_context.py` caches 24h per ticker (`_CACHE_TTL = 86_400`), so the budget is ~8 distinct
tickers/day across all users. Turning this on live is therefore a metered, outward-facing change
— it should be a deliberate act, not a side-effect of a compose cleanup. Decide the budget
posture first (accept the cap / widen the TTL / restrict to watchlist tickers).

## Acceptance

1. `settings.adanos_api_key` and `settings.alpha_vantage_api_key` both True in the Alpha container.
2. A live convene reports `social_source=live`; the Social Analyst's message cites real Reddit
   sentiment (re-measure with the CR035 transcript audit — see CR037).
3. A config-check surface exists that would fail loudly on the next unforwarded key.


---

## Follow-up (2026-07-17, `alpha-2026-07-17-1`) — plumbing fixed, key is dead

Saiful: *"turn on the key. We need to start using it."* Key uncommented in `infra/alpha.env`,
promoted, verified reaching the container. The feed is **still dark — for a new reason.**

| Check | Result |
|---|---|
| `GET /v1/admin/config-check` → `ADANOS_API_KEY` | `configured: true` (plumbing fixed ✅) |
| Live `_profile_for_ticker("NVDA")` in-container | `social_source = None` ❌ |
| Container log | `social_context_adanos_bad_status status=401 ticker=NVDA` |
| Direct probe from the Mac, `X-API-Key` | `401 {"detail":"Invalid API key."}` |
| Same probe with an obviously-fake key | **identical 401** — our key is no better than a fake one |
| `Authorization: Bearer` / `x-api-key` / `apikey` variants | all 401 — not an auth-scheme bug |
| `https://api.adanos.org/health` | `200` — service is up |
| Endpoint without auth | `401`, not `404` — URL is correct |

**Diagnosis: the key itself is invalid** (revoked, rotated, or the free tier lapsed). Our code is
correct — right URL, right header. Note CR024's module docstring records that the 250/month limit
was *"confirmed via response headers during AT:R57"* (2026-07-12), so the key **was working five
days ago** and has died since.

**Saiful's move (external account, can't be done from here):** sign in to the Adanos dashboard,
check the subscription/trial state, regenerate the key, paste it into `infra/alpha.env`, and
re-promote. That's the whole remaining step — everything downstream is verified.

**Left enabled deliberately.** The failed call logs a warning per convene and falls back to the
synthetic path, i.e. it degrades *loudly* (CR040 P2) instead of silently. Cost is one wasted
~200 ms HTTP round-trip per convene and zero quota (401s don't bill). The moment a valid key
lands, one promotion makes it real — no code change.

**Acceptance was unmet at the time:** #1 (`adanos_api_key` True) ✅, #2 (`social_source=live`) ❌ —
blocked on the key. CR037's fallback question stays live regardless: with a 250/month budget,
cold tickers hit the fallback daily even once the key works.

---

## Follow-up (2026-07-21, daily check-in) — fresh keys, Adanos half resolved

Saiful signed up 2 new Adanos accounts and put both keys in `infra/alpha.env` (already promoted —
melehost `~/ami_trade/.env` matches). Verified from scratch, not assumed:

| Check | Result |
|---|---|
| `GET /v1/admin/config-check` → `ADANOS_API_KEY` | `configured: true` |
| `docker exec ami_api_alpha env \| grep ADANOS` | primary key present, live in the running container |
| Direct probe, primary key, `AAPL` | `HTTP 200`, real data — `x-ratelimit-used-monthly: 165`, `remaining-monthly: 85`, resets `2026-08-17` |
| Direct probe, secondary key (`ADANOS_API_KEY_SECONDARY`), `MSFT` | `HTTP 200`, real data — `used-monthly: 109`, `remaining-monthly: 141`, resets `2026-08-13` |
| In-container `fetch_live_sentiment("COIN")` (uncached ticker, real code path, not a raw probe) | Returned genuine `SocialSentiment` — real buzz/sentiment scores, real subreddits (`wallstreetbets`, `investing`, `stockstobuytoday`), real post snippets |

**Both acceptance criteria now met for the Adanos half:** #1 `adanos_api_key=True` ✅, #2
`social_source=live` (confirmed via the actual `fetch_live_sentiment` call, not inference) ✅.

**Secondary key is valid but unused.** `ADANOS_API_KEY_SECONDARY` isn't referenced anywhere in
`config.py`, `social_context.py`, or `docker-compose.yml` — the code has no concept of a second
key. It's currently just spare quota (141/250 remaining) sitting idle. If Saiful wants to actually
use it (failover when the primary nears exhaustion, or split traffic to roughly double effective
monthly budget to ~500 calls), that's a small follow-up CR/DEF, not automatic from having the key
in `alpha.env`.

**Remaining, unrelated:** `ALPHA_VANTAGE_API_KEY` is still commented out in `alpha.env` — the News
Analyst's Alpha Vantage sentiment-scored merge (CR023's second half) stays dark until Saiful
decides to provision/enable that key too. Not addressed by this follow-up.
