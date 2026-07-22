<!-- dispatch assign lane — Architect-owned. CR052. -->
# DEF084-BE — assign

KIND: code
INSTANCE: coder.api
ACCEPTANCE: docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/DEF084_halal_flag_is_an_allowlist_not_a_screen.md — **Option 2 only** (Saiful decided 2026-07-22)
DEPENDS-ON: none
HOT-FILES: backend/app/services/sim_engine.py, backend/app/agents/safety_floor.py (frozen surface — coordinate with coder.room), backend/app/api/mandate.py

**Decision already made — do not re-open it.** Saiful chose **Option 2: tell the truth about the
allowlist.** Do NOT wire `sharia_screen()` (that is Option 1 — it needs a fundamentals feed and a
ruling on *which* standard AMI implements, and it is not this lane). Do NOT withdraw the flag.

**What:** the `halal` mandate flag is enforced by `halal_universe or DEFAULT_HALAL_UNIVERSE`
(`sim_engine.py:74,457,618`; `api/mandate.py:271`) — a literal 7-ticker set
`{AAPL, MSFT, NVDA, GOOGL, META, TSLA, AMZN}`, none ratio-screened. Meanwhile `sharia_screen()`,
`sharia_debt_ratio()`, `sharia_liquidity_ratio()`, `sharia_impermissible_income_ratio()` and
`purification_amount()` in `backend/app/trading_math/screening.py` are **dead code** — verified: the
only reference outside that module is the re-export at `trading_math/__init__.py:47,51,122,126`.

Rename and relabel the set everywhere so no backend surface calls it a Sharia screen: it is a
**curated demonstration universe**, explicitly not a compliance screen. That includes the constant
name, every log key, every API field/description, and any response text a client could render.
Leave `screening.py` in place and unwired — do not delete it; add a module docstring saying plainly
that it is not reachable from the `halal` enforcement path today and naming DEF084.

**Why now, and why this is urgent:** DEF084 said "resolve this before DEF082 ships." DEF082 shipped
first (`+50`, both stores, `alpha-2026-07-22-2`), so the 10 SHARIA lessons that were accidentally
unreachable are now reachable, and the flag is live. A user toggling it on believes a ratio screen
ran. **Fourth occurrence of the CLAUDE.md degrade-loudly class** after DEF038 / DEF063 / DEF082.

**GUARD (required — the fix alone is not acceptable).** Per `failure_patterns.md`, the fourth
occurrence needs a structural check: a test asserting **every mandate flag is enforced by the
mechanism its user-facing copy describes.** At minimum it must fail if a flag's only implementation
is a literal set while its copy claims a computation. Verify the guard **red** against the current
code before you fix, and say so in your lane file with the failing output — a guard never verified
against the real gap is the exact hole DEF063 left.

**Out of scope:** mobile copy (DEF084-MOBILE), lesson content (DEF084-CONTENT). Do not touch
`content/**` or `mobile/**`. The ratio/standard corrections touch religious rulings and are
Saiful/SME-only — never yours.

ASSIGNED: coder.api round 1
DISPATCH: OPEN

DISPATCH: ACCEPTED (round 1)
