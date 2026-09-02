# CR218 — hand the analyst the capital-allocation arithmetic, not the operands

**Filed:** 2026-09-02 · **Track:** R · **Status:** in_progress

## Why

Found while reading GLM-5.3's reasoning trace during the [CR217](../CR217_glm_room_headtohead/CR217_glm_room_headtohead.md)
head-to-head. Saiful: *"did it do any calculations that we should add to the prompt?"*

The Fundamentals Analyst's role brief names **capital allocation** as its lane. The fact
sheet gave it buybacks in **dollars** and dividends as a **yield**:

```
Buybacks (LIVE): $5,910M repurchased (trailing 4 quarters), 3.1% of market cap
Dividend (LIVE): yield 1.4% (trailing)
Company size (LIVE): market cap $193,390M, FCF $8,961M (TTM)
```

Reaching the actual finding took three steps that were nowhere in the sheet: convert the
yield to dollars against market cap, add it to buybacks, divide by FCF. GLM did exactly
that inside its reasoning, and it is the sharpest line in its answer — CAT returned
**~96% of TTM free cash flow** to shareholders while revenue shrank 1% and operating
margin fell 360bps.

**The argument for precomputing is not that GLM needed help — it is that the incumbent
never got there.** Given the identical prompt, `ami-llm` read the buyback line and stopped:
*"$5,910M in recent buybacks (3.1% of cap) indicate capacity for shareholder returns."* It
never connected buybacks + dividends to FCF. Precomputing hands the weaker reader the
finding for free, which is a far better trade than adopting a 17×-slower model to get it.

Two further reasons, both from this project's own rules:

- **CR179 Leg 4 already states the rule** — *"hand over the derived figure rather than the
  two operands and an instruction"* — and `buyback_yield` on the very next line obeys it.
  This is that rule applied one field over.
- **Model arithmetic is an unguarded error surface.** GLM's derivation used
  `yield × market cap` and reached $2,707M against the statement's actual **$2,812M** — a
  3.9% error, because a *trailing* yield times a *current* market cap is not the trailing
  payment. It was right about the conclusion and wrong about the number, and nothing
  downstream could have caught either.

## What ships

**1. Three new fields**, computed where the operands already live:

| field | source |
|---|---|
| `dividends_paid_ttm` | `Cash Dividends Paid` / `Common Stock Dividend Paid`, the cash-flow statement already fetched for buybacks — no extra call |
| `capital_return_ttm` | buybacks + dividends |
| `capital_return_pct_fcf` | that total ÷ TTM FCF |

Rendered by a new `capital_return_line()` on **both** surfaces (Room sheet and 1-on-1),
per the CR166/CR179 parity rule that one analyst must not see a poorer sheet on one than
the other:

```
Capital returned (LIVE): $8,617M (trailing 4 quarters) — buybacks $5,910M + dividends $2,707M, 96% of TTM FCF
```

Both components are named beside the total deliberately: a company returning $8B entirely
through buybacks and one splitting it with a dividend are different capital-allocation
stories, and the total alone cannot tell them apart.

Added to **`edgar_pit.py` as well as `fundamentals.py`** — the as-of path is the one the
backtest renders and the one this observation came from, and it already resolves both
operands exactly from EDGAR.

**2. A stale disclaimer removed.** `dividend_line` ended with
`(buybacks/M&A: not available, not claimed)`. That had been wrong since **CR145 Tier D**
added the `.quarterly_cashflow` call that backs buybacks — the function's own docstring
anticipated it (*"CR145 Tier D owns the `.cashflow` call that would"*) and was never
updated when Tier D shipped. So the Room sheet stated `Buybacks (LIVE): $5,910M
repurchased` and then, two lines later, declared buybacks unavailable.

That matters because of how hard the rest of the sheet works to police available-vs-not.
An agent that believed the disclaimer would **suppress a real number it had been handed** —
the mirror image of the fabrication the disclaimer exists to prevent. M&A genuinely has no
yfinance field and stays disclaimed.

## Guards

- `test_cr218_capital_return.py` — the line's shape, the absent-is-not-zero split, the
  withheld-ratio path, the disclaimer's new intent, provenance registration, and that
  **both** render sites call the builder.
- `test_prompt_data_parity.py` — the existing DEF074/DEF096 guard. Its mocked cash-flow
  frame now carries a dividends row, so the derivation is exercised end to end rather than
  only its buyback half. Without registration in
  `_FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS` the fields compute on every convene and reach
  no agent — the CR040 silently-dark shape — and this guard fails if that regresses.

## Deliberate non-goals

- **No percentage against non-positive FCF.** A company returning capital while burning
  cash funds it from the balance sheet or new borrowing; a ratio against a small or
  negative denominator asserts precision it does not have. The dollars still render; only
  the ratio is withheld.
- **No payout-quality judgement.** The sheet states what was returned and what share of
  FCF it consumed. Whether that is prudent is the analyst's call, not the fact sheet's.
