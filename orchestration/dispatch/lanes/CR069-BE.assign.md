<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR069-BE — assign (sourced AAOIFI universe + three-state resolver + loud degrade + the DEF084 guard)

KIND: code
INSTANCE: coder.api
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Phase 1, §Design constraints 1-4, §Guard, §Acceptance 1-3)
DEPENDS-ON: — (head of CR069; unblocks CR069-MOBILE + CR069-DIVERGE)
GATE: independent    <!-- recorded upfront at decomposition. Safety floor + a user-facing observance claim = the DEF084 class, 4th occurrence of degrade-loudly. Reversibility, not size. -->
HOT-FILES: backend/app/agents/safety_floor.py (coder.api owns, frozen interface — this lane changes it, so no other lane may touch it until this one lands) · backend/app/services/sim_engine.py · backend/app/services/room_runner.py (coder.room's file — additive one-line change only, see §2) · backend/app/core/config.py

**What:** Replace the 7-ticker literal that currently enforces the `halal` flag with a universe
sourced from SPUS's published holdings (AAOIFI, screened by S&P DJI), carrying its as-of date, and
resolving to **three** states rather than two. Ship DEF084's still-unbuilt guard in the same commit.

---

## 0. Read first

`docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md` —
especially §3a (the two free sources disagree on 47.9% of names) and §Design constraints. The
research there is measured, not estimated; do not re-derive it. **G1 and G2 are RESOLVED**: the
standard is AAOIFI via SPUS, and the UI copy is approved. Build to them.

## 1. Two findings from the Architect's read of the code — the brief does not have these

**1a. There is a FOURTH hardcoded copy of the demo universe, and it is not the constant.**
[`room_runner.py:1293`](../../../backend/app/services/room_runner.py) reads:

```python
# Halal universe: tiny demo set. Real screen ships at W8+.
halal = halal_universe or {"AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AMZN"}
```

That is a **literal duplicate**, not an import of `DEFAULT_HALAL_DEMO_UNIVERSE`. Swapping the
constant in `sim_engine.py` will silently leave the Room path on the old set. Every call site:

| Site | What it is |
|---|---|
| `sim_engine.py:80` | the constant itself |
| `sim_engine.py:463`, `:624` | `halal_universe or DEFAULT_HALAL_DEMO_UNIVERSE` fallbacks |
| `api/mandate.py:274` | passes the constant in |
| **`room_runner.py:1293`** | **the literal duplicate — the trap** |
| `safety_floor.py:144-151` and `:226-234` | **two** enforcement branches, both `t not in halal_set` |

Grep `halal_universe` across `backend/app/` and prove you have them all before you start. A missed
site is not a cosmetic gap — it is the same flag enforcing two different standards.

**1b. Three states need a source the brief does not name.** Constraint 2 requires *pass* /
*screened out* / *unknown*, and SPUS alone cannot distinguish the last two: it publishes only the
compliant set, so absence means "excluded" and "never looked at" identically. You need the **parent
index membership** to tell them apart. Get it the same way and from the same kind of source — a
large-cap S&P 500 ETF's published holdings CSV (IVV or SPY; same regulatory-disclosure basis as
SPUS, no key). If you cannot source parent-index membership reliably, **do not fake the third
state** — come back `BLOCKED` with what you tried. A two-state screen that calls unknown tickers
"screened out" is constraint 2 violated and is worse than today's honest placeholder.

## 2. Build

**Fetcher + cache** (new module under `backend/app/services/`, coder.api-owned):
- Pull the SPUS holdings CSV; extract `StockTicker` and the `Date` column as the **as-of stamp**.
- Filter non-equity rows — the CSV carries cash/CVR line items (`003654100CVR`, `2602335D`). Plain
  alphabetic tickers only.
- **Assert a plausible row count.** A truncated download must raise, never yield a short universe.
  219 tickers on 2026-07-22; pick a floor with headroom and justify it in a comment.
- Cache with the as-of date. Stale beyond its rebalance window ⇒ the flag **pauses loudly**
  (constraint 3), never a silent stale read and never a fall back to the 7-ticker set.

**Source URL is config, not a literal.** If you add a setting to `core/config.py` you MUST forward
it in `docker-compose.yml`'s `api-alpha` block — `backend/tests/unit/test_config_compose_parity.py`
fails the build otherwise, and this is the exact rule DEF038/DEF063 were dark for months for want of.

**Three-state resolver** returning pass / screened-out / unknown plus the standard name, source and
as-of date. The verdict a caller gets is **not a bare boolean** — §Acceptance 4 checks that the
agents receive the provenance, so the type must carry it from the start.

**Enforcement** — rewire all five sites above, including `room_runner.py:1293` (that one line only;
it is `coder.room`'s file, so keep the change minimal and mechanical). `safety_floor.py`'s two
branches are the actual gate.

**G3 is RESOLVED (Saiful, 2026-07-23): an unknown ticker is PERMITTED, with the disclosure
attached.** Only a ticker that is **in the parent index and absent from the compliant set** is
blocked. Read the consequences carefully, because they are not a one-line change:

- **Unknown must not produce a violation.** `safety_floor.py` appends violations, and a violation is
  a rejection. Do not invent a "permitting violation" — if unknown reaches the violations list at
  all, the trade is blocked and the ruling is inverted. Unknown means the halal branch simply does
  not fire.
- **But the disclosure must still travel.** A permitted-unknown trade that says nothing is a silent
  pass on an observance decision, which is this CR's entire failure class in the other direction.
  The verdict object carries `unknown` plus the standard, source and as-of date, and every surface
  that renders a trade outcome has to be able to show it. The floor is not the carrier here — the
  verdict is. Design that seam deliberately.
- **The agents must receive it too.** §Acceptance 4 checks the Room prompts carry the sourced verdict
  *with provenance*. An agent told nothing about a ticker's screen status will narrate as though it
  passed — DEF084-ROOM was exactly that, three narration sites asserting a screen no code ran.
- Keep the boundary honest in copy: unknown is *"the AAOIFI screen AMI uses hasn't reviewed it —
  that's not a ruling either way"*, never a pass and never a fail.

**Do NOT wire `sharia_screen()`** (`trading_math/screening.py`). Constraint 4: the three-ratio math
stays dormant until a source supplies real debt / liquid-asset / impermissible-income figures. This
lane ships a *sourced allowlist* and every comment and docstring must describe it as one.

## 3. The guard (DEF084 specified it, nobody built it — it ships in this commit)

A test asserting **every mandate flag is enforced by the mechanism its user-facing copy describes.**
For `halal`: the enforcement path reads the sourced universe, and the ARB copy names the same
standard and source the code used. Per the `failure_patterns.md` house rule it ships with the fix.
**Prove it red before the fix lands** — record the failing output in your hand-off. A guard first
observed green is not evidence.

## 4. Tests

- Fetcher against a **checked-in CSV fixture** (do not hit the network in tests): 219 tickers
  parsed, junk rows dropped, as-of extracted; a truncated body and a 500 both **raise**.
- Enforcement: `halal` mandate rejects an in-index non-compliant ticker with a message naming the
  standard and date; a ticker outside the parent index returns **unknown**, not a rejection message.
- Note today's `DEFAULT_HALAL_DEMO_UNIVERSE` contains **META, which AAOIFI/SPUS screens out** — any
  existing test asserting META passes the halal flag is now asserting the wrong thing. Fix it and
  say so; do not delete the assertion to make the suite green.

**Self-test (targeted, NOT the full suite):**
`cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "halal or sharia or mandate or safety_floor or config_compose"`
then the specific new test files. The full suite is the auditor's job.

## 5. Constraints

- **AMI by name** in anything user-visible; `LLM` is fine in code. Never "the AI".
- **Sharia rulings are not yours.** You are reading a published constituent list, not making a
  ruling. If you find yourself deciding whether a company is compliant, stop — that escalates to
  Saiful or an SME, never an agent lane.
- Do not touch lesson content (`content/lessons/`), the ARB files, or `settings_screen.dart` — those
  are CR069-MOBILE. Do not correct the SHARIA lesson thresholds; that is G7, SME-gated.
- Commit **incrementally** — DEF083 died on budget after 31 edits and before its first commit.

## 6. Delivery

**Push to `lane/CR069-BE.coder.api`, NEVER to `main`.** Nothing reaches the shared branch except
through the Architect, who merges once the gate is satisfied. DEF084-MOBILE pushed straight to main
(`e344b27`) and bypassed both the audit and the integration step; that is why this is spelled out.

**Hand-off:** write `orchestration/dispatch/lanes/CR069-BE.coder.api.md` with
`STATUS: READY_FOR_AUDIT (round 1)`, and the audit-bridge file
`orchestration/audit/cr/CR069-BE.architect.md` with `SUBMITTED: round 1`.
(Note the path — `orchestration/audit/cr/`, not the old `audit/handshake/cr/` some older lanes cite.)

Carry the **chunk evidence list**, not the Definition of Done — the DoD is rendered once at CR level
(lane `CR069`), by a fresh agent, never by a chunk author. Your evidence: SHA(s), what/why, the test
command with its **observed output**, the guard's red-then-green proof, and anything you could not
verify named rather than omitted.

Commit tag `(AT:coder.api CR069)`. Report the SHA and the pytest exit code. **Completion is verified
by git and exit code, never by your word.**

---

# Round 2 — three fixes (auditor bounced round 1, `AWAITING_FIXES`)

Read [`orchestration/audit/cr/CR069-BE.auditor.md`](../../audit/cr/CR069-BE.auditor.md) in full
first. Round 1's resolver correctness is **confirmed and not reopened** — PASS / SCREENED_OUT /
UNKNOWN / UNAVAILABLE semantics stand, G3 stands, the guard stands. Do not redo them, do not
"improve" them. Three specific gaps, all in the provider's runtime shape.

**F2 — MAJOR. Staleness re-check is dead after process start.** The window is only evaluated when
`_cache is None`, so a process that starts with fresh data never notices it going stale — it serves
the same universe until restart. That contradicts constraint 3 for any long-running deployment,
which is every deployment. Check elapsed time against `as_of` on **every `get()`**, mirroring
`news_context.py`'s per-call TTL check, or add an explicit periodic refresh caller.

**F3 — MAJOR. The synchronous fetch blocks the async event loop** on first use, at all three call
sites, on a single-worker deployment — so the first `halal` trade after a restart stalls every other
in-flight request. Use `asyncio.to_thread(self._build, ...)` or `run_in_executor`, matching the
existing pattern at `sim.py:411`.

**DEF089 — the configured parent-index URL does not serve CSV.** New in round 2, and it is why
nothing can go live: `sharia_parent_index_url` (`config.py:171-173`, `docker-compose.yml:146`)
returns HTTP 200 with the iShares **product webpage**, carrying `content-type: text/csv` and a
`content-disposition` filename on an HTML body — an upstream bot-mitigation layer
(`server: istio-envoy`). Your `parse_holdings_csv()` handles it correctly (raises
`ShariaSourceError`, `_build()` catches it and pauses) so the code is not at fault, but as
configured `SHARIA_SCREEN_ENABLED=true` would pause the screen **permanently**, and without
parent-index membership there is no third state at all.

Spec: [`DEF089`](../../../docs/defect/DEF089_parent_index_url_serves_html_not_csv/DEF089_parent_index_url_serves_html_not_csv.md).
Two candidate shapes, in preference order:

1. **A published mirror fetched the same way HLAL already is** — the CR069 doc's §3 pattern uses a
   Google-Sheets CSV export, no key, no browser emulation. Any S&P 500 constituent list on a
   comparable plain-fetch endpoint qualifies.
2. Browser emulation / session handling for the iShares endpoint. **Weaker, and say so if you pick
   it** — it makes the screen depend on defeating a bot-mitigation layer that can change without
   notice, in a feature whose entire purpose is not to break silently.

**Fetch whichever you choose LIVE and paste the real response in your hand-off** — status, byte
count, first line, ticker count, and the as-of date. A URL nobody fetched is what produced this
defect: the brief's "verified live" section verified SPUS and never the parent index, and read as
though it had done both.

If no plain-fetch source works, come back **`BLOCKED`** with what you tried and the actual responses.
Do not ship a two-state screen. Do not quietly widen `UNKNOWN` to cover it.

## Round 2 constraints

- Keep the tests fixture-based — no network in the unit suite. The live check is evidence in your
  hand-off, not a test.
- Same boundaries as round 1: no ARB, no `settings_screen.dart`, no `overlay_generator.py`
  (CR069-ROOM), no lesson content, `sharia_screen()` stays dormant.
- Same branch: `lane/CR069-BE.coder.api`. **Commit the hand-off files this time** — round 1 wrote
  both and committed neither, and the board reported a delivered submission anyway (DEF087, now
  fixed: an uncommitted lane file renders `UNCOMMITTED`).
- Bump both round markers to **2**: `STATUS: READY_FOR_AUDIT (round 2)` and `SUBMITTED: round 2`.

ASSIGNED: coder.api round 2
DISPATCH: OPEN
