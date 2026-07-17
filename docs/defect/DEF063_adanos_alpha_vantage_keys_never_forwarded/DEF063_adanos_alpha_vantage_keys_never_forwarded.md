# DEF063 — CR023/CR024 live feeds are dark in Alpha: their API keys are never forwarded to the container

**Filed:** 2026-07-17 (AT:R59) · **Status:** partially resolved (AT:R59) — compose forwarding + guard landed via CR040 (`9c699b1`); keys deliberately PARKED (commented) in `infra/alpha.env` pending Saiful's metered-tier budget call, so Alpha behaviour is unchanged and enabling is now a one-line deliberate act · **Found by:** Saiful ("I am sure CR024 had
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
