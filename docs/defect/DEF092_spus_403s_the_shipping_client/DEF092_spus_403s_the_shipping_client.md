# DEF092 — The SPUS source 403s the HTTP client that actually ships; every prior check used curl

**Filed:** 2026-07-23 · **Track:** `AT:architect` · **Found by:** `coder.api` during CR069-BE round 2
**Sibling of:** [DEF089](../DEF089_parent_index_url_serves_html_not_csv/DEF089_parent_index_url_serves_html_not_csv.md)
**Status:** fixed in CR069-BE round 2 (`88776b3`), filed for the lesson

## What

The SPUS holdings URL — the compliant-set source, the one CR069's brief verified in detail and the
round-1 audit re-verified — **rejects the client the code ships with**:

| User-Agent | Result |
|---|---|
| `python-httpx/*`, `python-requests/*` | **HTTP 403**, 146 bytes of `<html>` |
| curl default, empty UA, `AMI-Trade/1.0` | HTTP 200, real CSV |

`coder.api` found it while fixing DEF089 and fixed it with an honest identifying UA — deliberately
**not** a `Mozilla/5.0` impersonation. It flagged the finding and declined to mint an ID, correctly.

## Why it is its own defect and not a footnote to DEF089

DEF089 was *this URL serves the wrong content*. This is *this URL serves the right content to
everything except us*. Different mechanism — and the important part is what it says about the
verification that missed it.

**Both of CR069's data sources were broken, and only one was known.** The brief's §3 "verified live"
section reported the SPUS fetch in convincing detail — HTTP 200, 23,574 bytes, 219 tickers, dated,
with named exclusions spot-checked. All true, and all obtained with **curl**, whose UA passes. The
round-1 audit re-verified the same URL the same way and reached the same conclusion.

So a source was verified twice, by two independent parties, and both verifications were invalid for
the same reason: **the tool used to verify was not the tool that ships.** A curl check proves the URL
serves CSV to curl. It says nothing about `httpx`.

That is a sharper version of DEF089's lesson. There, one of two required sources was never fetched.
Here, the source *was* fetched, repeatedly, and the check still proved nothing.

## Rule

**Verify a network dependency through the client that will make the call in production** — the
shipped fetcher, or at minimum the same library and default headers. Where that is impractical,
record the tool used, so the next reader knows what the check actually covered.

Added to the CR069 terminal go-live gate alongside DEF089: before `SHARIA_SCREEN_ENABLED=true` on any
host, **both** source URLs are fetched **through the shipped fetcher** and asserted to parse. Round
2 did exactly this — its evidence is a live run of the real `parse_holdings_csv()` against both
sources, not a curl transcript.

## Residual (carried, not fixed here)

The replacement parent-index source carries **no as-of date of its own** — membership only. A mirror
that silently froze would not trip the staleness pause, because SPUS's as-of is the only freshness
signal in the system. `coder.api` named this rather than omitting it. Closing it needs a separate
freshness signal and is new work, not a round-2 fix; it belongs in the terminal `CR069` gate.
