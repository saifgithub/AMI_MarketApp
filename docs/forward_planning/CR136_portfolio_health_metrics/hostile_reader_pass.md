<!-- CR136 M11 — hostile-reader pass record (Rev 4 acceptance): one full generated Finding vs the rude-PM checklist; Saiful's verdict per item, dated. -->

# CR136 — hostile-reader pass

The standard Saiful set: the audience is the user **and their human portfolio
manager**, and that manager is *"extremely critical, to the point of being
rude"*. The Finding has to survive being read by someone actively looking for a
number to tear apart.

**This is a human gate, and only Saiful can close it.** The eight items below
are yes/no. Any "no" mints a `DEF###`, is fixed in its owning module, and a
fresh Finding is generated and re-read from item 1. The recorded all-yes is a
ship precondition.

## Procedure

1. Pick a **real** book (the §3.1 cross-check book is ideal — no
   `room-benchmark` synthetics, no 05-24 05:10 seed rows). Record which.
2. On device or via the API, generate a Finding: `POST
   /v1/portfolio/health/{user_id}/finding`.
3. Read the whole artefact. Fill the table. Date it.
4. **Do the same read a second time against a deterministic-fallback Finding**
   — item 8 has to hold on the path where the LLM was refused or rejected, not
   only on the happy one. Force it by taking the LLM gateway out (or use a
   book whose validator rejects the LLM draft) and note which path produced
   the artefact.

## Checklist

| # | Item | Verdict | Note |
|---|---|---|---|
| 1 | Every number carries method, window and n — §F3 blocks show value, SE with `t_eff` stated, `n_observations`, `window_days`, estimator + citation | ☐ | |
| 2 | The disclosure block sits at the HEAD, before §F1, with all five lines (F19): short disclaimer, gross-of-fees + zero-cost simulation, backcast line, window + estimator line, standing non-stationarity caveat | ☐ | |
| 3 | No judgement adjectives anywhere | ☐ | |
| 4 | Every claim is payload-traceable — the validator enforces the tokens; this pass checks the *statements* | ☐ | |
| 5 | §F5 keeps the conditional-educational speech act: no imperative on the user's own tickers, no "you should", no severity bands; the section is titled "What the numbers point to" | ☐ | |
| 6 | §F1/§F2/§F5 stay plain-language: the literal "R²" never appears outside §F3 (it renders as "the market explains only X% of this book's day-to-day moves"); no register-lexicon term leaks | ☐ | |
| 7 | Window and backcast are stated — today's weights applied to past returns is labelled as such | ☐ | |
| 8 | §F5 spot-checked against the live site's compliance line — *"It does not and will not give investment advice"* (`website_api/app/knowledge/faq.md:45`) — and it stays true on the LLM path **and** the deterministic fallback | ☐ | |

## Record

| Field | Value |
|---|---|
| Date | _(not yet run)_ |
| Book (portfolio id) | |
| Finding journal entry id | |
| Path (LLM / deterministic fallback) | |
| Engine version | |
| Verdict | ☐ all-yes / ☐ DEFs minted: |

## Why this is not automatable

M06's validator already enforces what a machine can check: every rendered
number must be a token that appears in the payload, the register lexicon is
screened, and §F5's template set contains no imperative. What it cannot check
is whether a *true, traceable, correctly-hedged* sentence still reads as advice
to a hostile human — which is the only failure mode that matters here, and the
reason CR038's rule ("prompt instructions are not controls") did not end the
problem when the prompt was fixed.
