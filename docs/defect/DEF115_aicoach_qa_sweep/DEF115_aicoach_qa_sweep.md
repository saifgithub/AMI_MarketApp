# DEF115 — AI Coach Q&A quality sweep

**Filed:** 2026-07-27 · **Source:** prompt (CR060 educational-material lane) · **Category:** content · **Status:** resolved (round 1)

## What was wrong

The AI Coach Q&A corpus (`content/ai_coach/*.json`, 245 EN entries, shown to users as agent-chat answers)
had never been quality-verified. First sweep found ~19 defects. Full record + method:
[`content/_authoring/cr060_aicoach_sweep.md`](../../../content/_authoring/cr060_aicoach_sweep.md).

Two are **P1** and are the AI-Coach siblings of DEF097 (lesson 355): `qa_plt_halal_flag` and
`qa_islamic_which_standard_does_ami_use` both described AMI's halal flag as a **live** interest-income /
debt-ratio / prohibited-business screen applying AAOIFI 33%/33%/5% caps, refreshed quarterly from filings.
CR069 retired that: the flag no longer computes a screen — it checks membership in a sourced, dated
AAOIFI-standard index (S&P 500 Sharia Industry Exclusions Index / SPUS) and returns PASS / SCREENED-OUT /
UNKNOWN / PAUSED. The entries were teaching a mechanism the product no longer has.

The remainder: 12 double-period typos, 2 stale `-> Coach` nav labels (pre-AT:R27 rename), a collapsed
market-cap size table, a dead ASIC scam-report URL, and one prose↔metadata crossref mismatch.

## Why it matters

User-facing. The halal P1s misrepresent a compliance feature in the Islamic-finance surface; the dead ASIC
URL sends a user reporting a scam to a 404. Same authoring root cause as the lesson corpus, swept under the
same standing lane (CR060).

## Fix (round 1, applied)

- All ~19 corrected in place. Facts (market-cap buckets, ASIC→Scamwatch) web-verified before swap
  (FINRA/Schwab/Finance Strategists; ASIC's own scams page). Typos fixed by a deterministic
  two-dots→one-dot pass. Halal P1s rewritten to the CR069 four-state model, matching the approved lesson 355.
- 5 meaning-changing edits flagged for AR/MS re-translation:
  [`content/_authoring/cr060_aicoach_retranslate.md`](../../../content/_authoring/cr060_aicoach_retranslate.md).
- The doctrinal soundness of the sourced index is unchanged product policy (CR069) and stays disclaimed
  in-copy ("confirm with your own scholar"); not a new escalation.

## Follow-up

- i18n lane: re-translate the 5 flagged AR/MS entries.
- CR060 Phase 6: generalize `locale_staleness_check.py` to the JSON surfaces (per-`id` `source_sha`) so the
  re-translation flag is produced automatically.
