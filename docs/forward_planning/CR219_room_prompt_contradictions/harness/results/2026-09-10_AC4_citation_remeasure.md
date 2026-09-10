# 2026-09-10 — CR219 AC4 trailing re-measure — MEASURED

Status: **measured.** The first pass this session was blocked off-LAN and committed
only its groundwork (`bd3c2567`); this revision carries the measurement. Method:
the banked `citation_rates.py` counting rules, byte-identical, pointed at a fresh
export of post-fix production traffic (see "Method + reproduction" below).

## Headline

| sheet line (all LIVE) | before (66-turn banked arm) | after (post-fix) | persona |
|---|---|---|---|
| Margin TREND | **24.2%** | **75.0%** (3/4) | denial DELETED by `46b2f745` |
| Buybacks | **13.3%** | **75.0%** (3/4) | denial DELETED by `46b2f745` |
| Margin structure | 95.5% | 100.0% (4/4) | never denied (comparator) |
| Dividend | 16.7% | 66.7% (2/3) | never denied (comparator) |
| FCF / company size | — | 100.0% (4/4) | never denied |
| Returns (ROE/ROA) | — | 50.0% (2/4) | never denied |

Replies explicitly stating the trend was unavailable: **0/4** (before-arm suppression
was by omission, so this was and stays 0 — recorded for completeness).

**The confound-free reading is the adjacent-line gap.** The before-arm's design
point was two adjacent margin lines on the identical sheet in the identical turn —
one denied, one not: 95.5% vs 24.2%, a **71.3pp** gap attributable to the denial.
Post-fix, same construction: 100% vs 75.0%, a **25pp** gap — and at n=4 that
residual is one turn. Movement is in the ruled success direction on both
previously-denied fields.

## Honesty box — read before quoting these numbers

- **n = 4** fundamentals-analyst turns whose sheet stated a LIVE margin trend
  (5 post-cutoff turns; 1 turn's sheet carried no trend line and drops out by the
  same filter the before-arm used). One turn is ±25pp on every rate. This is a
  directional reading, not a stable rate.
- The window is **~7 days** — the short side of the ruled "~1–2 weeks". A re-run
  at the 2-week mark (on/after **2026-09-17**) with the same export + runner will
  roughly double n at current traffic.
- The undenied comparators also read higher than their before-arm rates (Dividend
  16.7%→66.7%), which at this n can be turn-mix/ticker composition, not the fix.
  That inflation risk is exactly why the adjacent-line gap above, not the raw
  rates, is the number to carry.
- Per the AC4 ruling (R30): no fixed threshold, citations never verdicts, and a
  null would have been a new finding, not a revert. This is not a null.

## The cutoff — determined (unchanged from the first pass)

**Cutoff: `alpha-2026-09-03-1`, tagged 2026-09-03T01:46:27+03:00 (commit `398578db`).**

- The shipped fix is the persona-edit route — **`46b2f745`**, `fix(CR219): the four
  analyst personas stop denying data their own fact sheet carries`,
  2026-09-02T22:48:30+03:00 — not the `sheet_registry.py` generated-block design in
  `fable/02` (superseded pre-build; `b7102f43`'s body records this).
- `git tag --contains 46b2f745` filtered to `alpha-*`, earliest by creation date:
  `alpha-2026-09-03-1`. Reproduction:

```bash
git log -1 --format="%H %cI %s" 46b2f745
git tag --contains 46b2f745 --sort=creatordate | grep '^alpha-' | head -1
git for-each-ref refs/tags/alpha-2026-09-03-1 --format="%(refname) %(objectname) %(creatordate:iso-strict)"
```

## Exclusions — applied

Post-cutoff `llm_audit` rows, `agent_id='fundamentals_analyst'`: **5**, joined to
`users` and checked against the standing rule
(`admin_analytics.py::_real_users_clause`):

- `room-benchmark` synthetics: **0** matched (all 5 carry real app versions
  0.1.0+103/+104).
- Seed-fixture burst (2026-05-24 05:10, NULL device_model + NULL app version):
  **0** matched (all 5 users carry device models; creation dates 2026-05-19,
  2026-07-21, 2026-09-03).
- The 12 by-id probe users: **0** matched (all 3 distinct user ids grepped against
  the literal list in `admin_analytics.py`).
- Harness/review-generated convenes (Gemini arms, R47/R48/R58 replays, CR221 arms):
  **0** present — those rigs call vLLM directly and never write `llm_audit` rows;
  all 5 rows carry production user linkage + app versions.

**Excluded: 0 of 5. Turns measured: 4 of 5** (the drop is the script's own
"sheet stated a LIVE margin trend" filter, identical to the before-arm).
The 4 turns span 2026-09-06 → 2026-09-09, 3 distinct real users (one user
contributes 3 turns — noted as a composition caveat at this n).

## Method + reproduction

The route: melehost via its Tailscale address (`scripts/share_apk_to_tester.sh:39`;
the Mac was off-LAN — the first pass's "unverified route" caution was resolved by
verifying that address in-repo and live; it is the committed fallback, same host,
same user). SELECT-only.

```bash
# 1. Export (SELECT-only; produces 2026-09-10_AC4_post_corpus.json beside this file)
ssh saiful@100.110.14.31 "docker exec ami_postgres psql -U postgres -d ami_trade -t -A -c \
  \"SELECT json_agg(t) FROM (SELECT id, created_at, agent_id, flow, input_tokens, \
  output_tokens, response_text, system_prompt FROM llm_audit \
  WHERE agent_id='fundamentals_analyst' AND created_at >= '2026-09-03T01:46:27+03' \
  ORDER BY created_at) t;\"" > 2026-09-10_AC4_post_corpus.json

# 2. Measure — the banked counting rules, corpus path swapped, nothing else:
python3 2026-09-10_AC4_citation_rates_post.py
# Parity check of the LINES table against the before-arm script:
diff <(sed -n '/^LINES/,/^]/p' ../../evidence/analysis/citation_rates.py) \
     <(sed -n '/^LINES/,/^]/p' 2026-09-10_AC4_citation_rates_post.py)
```

## Disposition

AC4 is **logged and non-gating** (R30 ruling). Recommended follow-up, not owed to
close CR219: one re-run of the two commands above on/after **2026-09-17** appended
to this file, for a 2-week-window n.
