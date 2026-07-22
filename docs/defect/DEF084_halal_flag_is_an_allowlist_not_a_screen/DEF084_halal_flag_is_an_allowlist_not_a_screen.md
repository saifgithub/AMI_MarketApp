# DEF084 — The `halal` mandate flag gates on a hardcoded 7-ticker allowlist; the real Sharia screen exists but is wired to nothing

**Area:** backend (+ content) · **Source:** prompt (CR060 Wave 4) · **Round:** AT:R64 · **Status:** open
**Severity:** high — a compliance claim the product does not honour, in a religious-observance context.

---

## Summary

CR060's Wave 4 checked `355_how_amis_halal_flag_maps_to_real_screening` against the **code** rather
than against external sources — the one class of claim no web citation can verify. The lesson tells
users AMI's `halal` flag runs a real two-stage Sharia screen. It does not.

**Verified in the repo (2026-07-22):**

| | |
|---|---|
| Real screening logic **exists** | `backend/app/trading_math/screening.py` — `sharia_screen()`, `sharia_debt_ratio()`, `sharia_liquidity_ratio()`, `sharia_impermissible_income_ratio()`, `ShariaScreenResult`, `purification_amount()` |
| …and is **called nowhere** | the only reference outside `trading_math/` is the re-export at `trading_math/__init__.py:45`. Dead code. |
| What actually enforces `halal` | `sim_engine.py:457` and `:618` — `halal_universe or DEFAULT_HALAL_UNIVERSE`, also passed at `api/mandate.py:271` |
| `DEFAULT_HALAL_UNIVERSE` | `sim_engine.py:74` — `{"AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AMZN"}` |

So the flag is a **hardcoded allowlist of 7 US mega-cap tech tickers**. None has been ratio-screened.
Their actual compliance status varies by standard and by period — which is precisely what
`350_standards_differ_why_the_same_stock_flips` teaches.

## Why this is worse than a wrong number

This is the **CR040 "degrade loudly" class, fourth occurrence** (after DEF038, DEF063, DEF082): a
feature that silently does something far weaker than it claims, with nothing surfacing the gap.

The difference here is the domain. A wrong price teaches a bad fact. A halal flag that does not
screen invites a user to make an **observance decision** on an assurance the system never computed.
The user cannot detect it: the flag is on, trades are permitted, nothing degrades visibly.

It also makes lesson content actively false rather than merely inaccurate:

- `355` — states the flag maps to real screening. It maps to a list.
- `351` — its worked example says *"Run this through AMI's `purification_amount` function"*. The
  function exists but is reachable from no user-facing path.

## Related — the other 9 SHARIA lessons

Wave 4 verified all 10 SHARIA lessons for **citation integrity** (they already carried `sources:`,
so the risk was never a missing citation but a citation that does not support its claim).
**Result: 0 VERIFIED, 8 FINDING, 2 ESCALATE.** The threshold errors are systematic:

- **AAOIFI Shari'ah Standard No. 21 sets 30% / 30% / 5%** — `349` and `356` both attribute **33%**
  to it. 33% is the DJIM/S&P family figure against a different denominator.
- `350` uses a **"12-month trailing average market cap"** window matching **no** cited standard
  (DJIM = 24-month, S&P = 36-month, MSCI/FTSE/Bursa = total assets, AAOIFI = point-in-time).
- `351`'s purification formula is the **DJIM/S&P/MSCI/FTSE** method, taught as AAOIFI's.
- `352` **inverts** its source: AAOIFI's Feb-2008 statement *permits* nominal-value purchase
  undertakings in *sukuk al-ijarah* (banning them for *musharakah*/*mudarabah*); the lesson says
  the opposite.
- `348` cites a **"Bursa Malaysia SAC"**, which does not exist — the SAC belongs to the Securities
  Commission Malaysia.
- **ESCALATE `353`** — El-Gamal (2006) is cited to support the "not a cosmetic rename" claim while
  his book argues substantially the opposite. Misusing a named scholar's position is not a
  numbers fix; it needs human/SME judgement.
- **ESCALATE `347`** — the *gharar* citation is generic where AAOIFI SS 31 is specific, and two
  worked examples contradict the standard they cite.

## Mitigation currently in place (accidental, not designed)

**DEF082** means all 10 SHARIA lessons are **unreachable in the app on both platforms** — the
lessons screen iterates a hardcoded 7-entry track map and silently drops the rest. So the false
teaching is not currently being served.

**The `halal` mandate flag itself is live** (`api/mandate.py`), so the enforcement defect is real
today even while the lessons that describe it are dark.

**This creates a hard sequencing dependency:** DEF082's fix switches 64 lessons on, including these
10. Shipping DEF082 before this is resolved would begin serving content that is both factually
wrong about published standards *and* wrong about the product's own behaviour.

## Fix — direction only; the decision is Saiful's

Three options, and this is a **product decision, not a content edit**:

1. **Wire the real screen.** Route the `halal` mandate through `sharia_screen()` with a real data
   source for debt / liquid-asset / impermissible-income ratios. Honest, and the most work — it
   needs a fundamentals feed and a decision on *which standard* AMI implements (they disagree; that
   is the subject of `350`).
2. **Tell the truth about the allowlist.** Keep the 7-ticker universe, and relabel it everywhere —
   UI, mandate copy, and lesson `355` — as a *curated demonstration universe*, explicitly **not** a
   Sharia screen. Cheap and honest; removes the false assurance.
3. **Withdraw the flag** until (1) ships.

**Option 2 is the minimum acceptable state**, because the current one asserts an assurance the
system never computes. Whatever is chosen, the content fix follows the product decision — do not
correct `355` first, or the lesson will document a behaviour that is itself about to change.

**Escalation:** the ratio/standard corrections above touch religious rulings. Per CR060's standing
rule these go to **Saiful / a qualified SME**, never to the education lane and never auto-fixed.

## Guard

Per the house rule (`failure_patterns.md`), the fourth occurrence of degrade-loudly needs a
structural check, not a fix alone: **a test asserting that every mandate flag is enforced by the
mechanism its user-facing copy describes.** At minimum, assert `sharia_screen()` is reachable from
the `halal` enforcement path — a flag whose only implementation is a literal set is exactly what a
guard should refuse.
