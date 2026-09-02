# 01 — What was independently verified

Date: 2026-09-02. All commands run from the repo root on the Mac; no backend started,
no network calls made beyond what the banked evidence required.

## Reproduced green

| Check | Command | Result |
|---|---|---|
| Citations resolve | `backend/.venv/bin/python $D/analysis/verify_citations.py` | exit 0, **15/15 ok** |
| Suppression measurement | `backend/.venv/bin/python $D/analysis/citation_rates.py` | reproduces the CR table exactly: structure 95.5%, FCF 68.2%, ROE 45.5%, **trend 24.2% (denied)**, buybacks 13.3% (denied), Dividend 16.7% (n=18, undenied), **1/66 stated unavailability** |
| Class-A contradictions | `grep` over `evidence/rendered/sheets/*.txt` | `Margin trend, YoY (LIVE)`, `Buybacks (LIVE)`, `Capital returned (LIVE)`, `Window trend`, `Primary trend (LIVE)`, `Relative strength, 52w (LIVE)`, `consensus EPS est. $4.44`, `Mentions: … over 33d, trend:` — all present on the very sheets whose personas deny them |
| Guard blind spots | read `test_cr105_analyst_inputs_field_state_guard.py` | confirmed: `_NEGATIVE_CLAIMS` has 2 entries checked for verbatim presence only; `_inputs_section()` slices `## Inputs` → `## Output` only — findings 2/6/7/8 live outside that window |
| Finding #15 | read `overlay_generator.py:437-455` | confirmed: non-long horizon emits *"Emphasise momentum in fundamentals (earnings revisions, surprise history), guidance."* and no such fetch exists anywhere in `backend/app` |
| Class D | read `evidence/rendered/aggressive_debator.txt` | the full ~50-line sheet is present in a downstream agent's prompt whose `## Inputs` names only transcript prose — confirmed |
| Class B #10 | grep `rendered/bull_researcher.txt` | *"End with your CONVICTION…"* (persona, line 24) vs *"Write this line ONCE, at the top only"* (format block, line 159) — both in one assembled prompt |
| Class B #12 | read `content/agents/trader.md` + `trader_block_regex` | *"Skip the stop-loss"* denial stands; the regex's WAIT/HOLD branch (CR210, commit `49380813`) omits Stop entirely — the collision is live at HEAD |

## One stale claim found

The CR's Class-B table says of #12: *"An uncommitted `trader_block_regex` hunk in
`room_prompts.py` fixes exactly this for the Size field … The Stop field has the
identical defect and is not covered."*

**That hunk is now committed** — CR210 (`49380813`, "WAIT-branch Size line") landed
the no-position branch with **no Size/Entry/Target/Stop/R:R** at all. So:

- The Size half is fixed at HEAD.
- The **Stop half is still broken**, and the persona denial (`You DO NOT … Skip the
  stop-loss`) is now contradicted by the *grammar itself*, not just the model's
  hesitation: a WAIT/HOLD turn physically cannot carry a Stop line.
- The finding survives; its citation must be re-pointed from "uncommitted hunk" to
  `room_prompts.py::trader_block_regex` at HEAD. This is exactly the line-number
  rot `verify_citations.py` exists to catch, and this one isn't in its list —
  recommend adding a citation entry for it.

## What was NOT re-measured (and why that's fine)

- The 84 stored turns and the convene traces were spot-checked for completeness via
  the README's own integrity snippet pattern (system prompt + user message + thought
  + answer per turn) rather than re-read in full; the aggregate claims that matter to
  the review (#15 reproduction 6/6 arms, 11/12 agents reporting contradictions, the
  WITHHELD classification quote) are quoted verbatim in the CR and consistent with
  the rendered prompts.
- The `h_short` harness artifact (`convene_gemini.py:77` hardcoding
  `Path.LONG_HORIZON`) was confirmed by reading the script — the record's own
  disclosure is accurate, and four of `h_short`'s contradiction reports must be
  discounted as recommended.

## Verdict on the evidence base

The CR is unusually honest — it names its own weak spots (Dividend n=18, the PM
exclusion, the coin-toss verdict column, the `h_short` artifact) and the numbers
reproduce exactly. The diagnosis is accepted in full. The review in `02` is about
the **plan**, not the findings.
