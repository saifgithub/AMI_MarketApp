# CR136 build — M07: API + access gating

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

## 1. Purpose

Implements Rev 4's "Access gating" section and README freeze-point 4: the two
HTTP endpoints (`GET /v1/portfolio/health/{user_id}` free tiles; `POST
/v1/portfolio/health/{user_id}/finding` gated generation) plus the
config-driven gate service composing `effective_plan()` + journal-as-counter
trial accounting + a `RateLimiter` abuse bracket. Tiles are FREE in every
mode; gating applies to full Finding generation only. Also lands the five new
`Settings` knobs and their compose forwarding (CR040 /
`test_config_compose_parity.py:71`).

## 2. Files

**New:**

- `backend/app/services/health_gate.py` — header one-liner: `"""CR136
  Portfolio Health access gate — config-driven trial/plan/daily-cap gating for
  Finding generation; journal rows are the counter, no new table."""`
- `backend/tests/unit/test_cr136_health_gate.py` — header one-liner:
  `"""CR136 M07 — gate semantics (trial window/budget/daily cap/modes), route
  guards, API shapes; tiles are never gated."""`

**Touched:**

- `backend/app/api/portfolio.py` — add both routes to the existing router
  (`prefix="/v1/portfolio"`, :34). `_own` guard exists at :37-39; DI idiom =
  the sector-allocation route :48-63 (`Depends(get_current_user)`,
  `Depends(get_sim_engine)`); sync work hops through `asyncio.to_thread`
  (:68-70). Router already registered (`backend/app/main.py:261`).
- `backend/app/core/config.py` — five Settings fields (§3.1).
- `docker-compose.yml` — five lines in api-alpha `environment:` (block :60,
  `environment:` :70).
- `backend/app/services/rate_limit.py` — one module-level limiter (registry
  starts :209).
- `backend/app/api/admin.py` — non-blocking hygiene (§3.6).

## 3. Implementation spec

### 3.1 Settings (backend/app/core/config.py)

Add under a `# CR136 — Portfolio Health access gating` comment (after the
league block, config.py:252). Names, types, defaults exactly:

```python
portfolio_health_gate_mode: Literal["open", "trial", "plan"] = "trial"
portfolio_health_trial_days: int = 14
portfolio_health_trial_findings: int = 7
portfolio_health_daily_cap: int = 2
portfolio_health_plans: CsvList = Field(default_factory=lambda: ["trader", "floor_manager"])
```

- `Literal` mode: a typo fails boot loudly, never falls open (`gtm_funnel`
  idiom, config.py:222; CR040).
- Add `"portfolio_health_plans"` to the `_csv_or_json_list` validator list
  (config.py:19-22); `CsvList` per config.py:13 (as `league_eligible_plans`,
  :252).
- Non-negative field_validator over the three ints, mirroring config.py:198-210
  (message `"portfolio health gate counters must be >= 0"`). `0` is legal and
  documented: `trial_days=0`/`trial_findings=0` ⇒ trial exhausts immediately;
  `daily_cap=0` ⇒ no Findings generate — loud configurations, not clamped.
- Plan list values are the lowercase `Plan` enum values
  (`backend/app/schemas/mandate.py:43-47`); the gate normalizes on read
  (§3.2) so Rev 4's `TRADER,FLOOR_MANAGER` spelling also matches.

### 3.2 Gate service (backend/app/services/health_gate.py)

Imports `JournalEntryRow` directly — **not** `EntryType` — so M07 has no
dependency on M08's enum member (build order M07 ∥ M08;
`journal_store.append` raises on unknown strings, journal_store.py:84-86,
which is exactly why the gate reads the row table).

```python
PORTFOLIO_HEALTH_ENTRY_TYPE = "portfolio_health_analysis"
# Must equal M08's EntryType.PORTFOLIO_HEALTH_ANALYSIS.value (Rev 4 journal
# plan); §5 case 13 pins it.

@dataclass(frozen=True)
class GateStatus:
    mode: str                    # "open" | "trial" | "plan"
    trial_active: bool
    trial_findings_used: int
    trial_findings_budget: int   # settings.portfolio_health_trial_findings
    trial_days_left: int
    daily_used: int
    daily_cap: int               # settings.portfolio_health_daily_cap
    plan_has_access: bool
    def as_dict(self) -> dict: ...   # dataclasses.asdict passthrough

def evaluate_gate(user_id: UUID, portfolio_id: UUID, *, now: datetime | None = None) -> GateStatus: ...
def enforce_gate(status: GateStatus) -> None: ...
```

> **Seam-register note (AT:R66).** build/README.md pins
> `JournalStore.latest_portfolio_health_entry(...)` and
> `JournalStore.portfolio_health_stats(...)` as **M08-owned, consumed here,
> never re-implemented** — retention and soft-delete filters make the generic
> `list_for_user` path wrong for both the counters and the prior-Finding read.
> The register overrides this doc's direct-`JournalEntryRow` sketch below, which
> stands only as a description of the SEMANTICS each store method must have. M06
> also carries its own `load_latest_finding`; when M08 lands the store methods,
> both callers collapse onto them. Two implementations of "the newest Finding for
> this portfolio" is how the daily cap and the hysteresis memory drift apart.

**Counter reads** (one SELECT each, `get_session()` idiom as journal_store.py):

- Trial counters are **per user** (any `reference_id`): count of rows with
  `user_id` + `entry_type == PORTFOLIO_HEALTH_ENTRY_TYPE` — **soft-deleted
  included** (no `deleted_at` filter; Rev 4 pin) — plus `min(created_at)` as
  the first Finding's timestamp. Per-user because `reset_portfolio` is
  destroy-and-recreate (sim_engine.py:394-403 — new `portfolio_id`); a
  per-portfolio trial would reset with every portfolio reset.
- Daily counter is **per portfolio** (Rev 4 "per portfolio per day"): rows
  with `user_id` + `reference_id == portfolio_id` + entry type +
  `created_at >= UTC midnight of now` — soft-deleted included
  (delete-then-regenerate must not bypass the cap). Day boundary is **UTC**.
- Naive/aware datetime normalization as entitlements.py:51-55.

**`evaluate_gate` semantics** (never raises):

- `days_elapsed = (now - first_created_at).days` (floor); no first Finding ⇒
  `trial_days_left = trial_days`, `trial_findings_used = 0`, trial untouched.
- `trial_days_left = max(0, trial_days - days_elapsed)`.
- `trial_active = (trial_findings_used < trial_findings_budget) AND
  (days_elapsed < trial_days)` — window OR budget, whichever exhausts sooner
  (Rev 4). Days 1–14 since the first Finding are inside; day 15
  (`days_elapsed >= 14`) is out.
- `plan_has_access = effective_plan_for_user(user_id).value in
  {p.strip().lower() for p in settings.portfolio_health_plans}`.
  `effective_plan_for_user` (entitlements.py:80-94) wraps `effective_plan`
  (:58-77) — trial-expiry-aware: an expired TRIAL_TRADER resolves to
  FLOOR_PASS. The two "trials" are distinct: the account trial
  (`users.trial_expires_at`) feeds `plan_has_access`; the CR136 Finding trial
  is the journal-counted window. String membership mirrors
  league_service.py:196-197. Consequence of the pinned default list: an
  active TRIAL_TRADER has no *plan* access — in `trial` mode the Finding
  trial serves them; operators may add `trial_trader` by env.
- Access by mode: `open` ⇒ always; `trial` ⇒ `trial_active OR
  plan_has_access`; `plan` ⇒ `plan_has_access`. Daily cap applies in ALL
  modes (Rev 4).

**`enforce_gate` order + errors** (structured-detail idiom as
one_on_one.py:151-158):

1. Access refused ⇒ `HTTPException(402, detail={"code":
   "portfolio_health_gate_closed", "gate": status.as_dict()})`.
2. Else `daily_used >= daily_cap` ⇒ `HTTPException(429, detail={"code":
   "portfolio_health_daily_cap_reached", "gate": …})`.

Machine codes for M09's CTA states — **no user-visible copy ships in M07**;
M09 owns the CTA/upgrade strings (AMI by name, `retranslate:[ar,ms]` there).

### 3.3 Rate limiter (backend/app/services/rate_limit.py)

Append one module-level limiter (registry starts :209):

```python
# CR136: Finding generation is one LLM call behind a 2/day gate; this brackets
# scripted hammering of the route itself. User-keyed like DEF186's chat
# limiters — the bearer identifies the billed user; an anon user rotates IPs
# trivially (rate_limit.py:250-255).
portfolio_health_finding_rate_limit = RateLimiter(
    name="portfolio_health_finding", per_minute=5,
)
```

Usage is the manual user-keyed `check()` idiom
(`…rate_limit.check(f"user:{current_user.id}")`, one_on_one.py:125; `check()`
at rate_limit.py:97-136 raises the 429 + `Retry-After` itself). 5/min matches
the LLM-heavy `room_stream` precedent (:246-248). GET gets **no** limiter —
parity with the sector-allocation route in the same file, which has none.

### 3.4 GET /v1/portfolio/health/{user_id} — tiles, never gated

```python
@router.get("/health/{user_id}")
async def portfolio_health(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    sim: SimEngine = Depends(get_sim_engine),
) -> dict:
```

1. `_own(current_user, user_id)` (portfolio.py:37-39).
2. `p = await asyncio.to_thread(sim.ensure_portfolio, user_id)`
   (sim_engine.py:378; `Portfolio.id` exists, schemas/trade.py:33-44).
3. `context = await asyncio.to_thread(build_health_context, user_id)` — M04
   engine entry point (seam, §7); sync math + DB per the portfolio.py:68-70
   idiom.
4. `gate = await asyncio.to_thread(evaluate_gate, user_id, p.id)` —
   **evaluate only, never `enforce_gate` here.** FREE in every mode.
5. Return:

```json
{ "as_of": "YYYY-MM-DD", "generated_at": "<ISO-8601 UTC>",
  "engine_version": "cr136.v1",
  "metrics": { "<M04 metric blocks, passed through verbatim>": "…" },
  "gate": { "<the 8 GateStatus keys of §3.2>": "…" } }
```

`as_of`/`generated_at`/`engine_version`/`metrics` come from M04's context
unchanged — M07 wraps, never edits, never strips (stripping is the
prompt-side context builder's job, not the tiles'). Mock-mode refusal and
`sufficient:false` blocks render as M04 emits them — GET stays 200; a 5xx
would hide the amber state from the card (CR040).

### 3.5 POST /v1/portfolio/health/{user_id}/finding — gated generation

Same DI signature, `@router.post("/health/{user_id}/finding")`. Order is
load-bearing:

1. `_own(current_user, user_id)` — 403 before anything is spent.
2. `portfolio_health_finding_rate_limit.check(f"user:{current_user.id}")`.
3. `p = ensure_portfolio(...)`; `context = build_health_context(...)` (both
   via `to_thread`) — building context is exactly the free tiles computation.
4. Context reports engine refusal (mock data, Rev 4 degrade matrix) ⇒
   `HTTPException(409, detail={"code": "portfolio_health_unavailable"})`.
5. **Shared prior-Finding read** (Rev 4: idempotency + hysteresis share one
   read): newest `JournalEntryRow` for `user_id` + entry type +
   `reference_id == p.id`, `created_at DESC LIMIT 1`, **soft-deleted
   included** (delete-regenerate must not wipe hysteresis memory nor mint
   budget-free entries — consistent with the counter pins; M07 pin, Rev 4
   silent).
6. **Idempotency, before the gate:** prior entry's `payload["as_of"] ==
   context["as_of"]` ⇒ return it, `created: false`, HTTP 200 — no
   generation, no budget consumed, gate NOT enforced ("same-day regeneration
   returns the existing entry" is unconditional, README contract 4; the entry
   is journal-visible regardless).
7. `gate = evaluate_gate(...)`; `enforce_gate(gate)` — 402/429 per §3.2.
8. `result = await asyncio.to_thread(...)` the M06 pipeline (rules → render →
   validate → deterministic fallback → M08 persist; seam, §7).
   **RECONCILED against shipped M06 (AT:R66)** — M06 landed first, so its
   signature is the one to code against. It is keyword-only and requires the
   rule-evaluator closure, because M06 renders rules but does not own their
   inputs:

   ```python
   from functools import partial
   from app.services.portfolio_rules import evaluate_rules

   result = await asyncio.to_thread(partial(
       asyncio.run,
       generate_and_persist_finding(
           user_id=user_id, portfolio_id=p.id, as_of=context["as_of"],
           metric_blocks=list(context["metrics"]), store=journal_store,
           evaluate=lambda prior_states: evaluate_rules(
               **rule_inputs_from(context), rule_states=prior_states,
           ),
           gateway=gateway,
       ),
   ))
   ```

   It returns `FindingResult(entry, created, llm_used, llm_rejected_reason)` —
   not a dict — and the response envelope of §3.5 is assembled from
   `result.entry.payload["sections"]` (which carries `head` alongside `f1`…`f5`)
   plus `result.entry.id`.
9. Return, gate re-evaluated so `daily_used` includes the new row:

```json
{ "journal_entry_id": "<uuid>", "created": true, "as_of": "YYYY-MM-DD",
  "sections": { "head": "<md>", "f1": "<md>", "f2": "<md>",
                "f3": "<md>", "f4": "<md>", "f5": "<md>" },
  "gate": { "…": "as in GET" } }
```

The idempotent return (step 6) is the same shape with `created: false`,
`sections` read from the stored `payload["sections"]` — mobile renders STORED
sections, never regenerates (README contract 5).

### 3.6 Compose forwarding + parity + admin hygiene

Append to api-alpha `environment:` (after docker-compose.yml:246,
`LEAGUE_ELIGIBLE_PLANS`) under a `# CR136 — Portfolio Health access gate`
comment:

```yaml
      PORTFOLIO_HEALTH_GATE_MODE: ${PORTFOLIO_HEALTH_GATE_MODE:-trial}
      PORTFOLIO_HEALTH_TRIAL_DAYS: ${PORTFOLIO_HEALTH_TRIAL_DAYS:-14}
      PORTFOLIO_HEALTH_TRIAL_FINDINGS: ${PORTFOLIO_HEALTH_TRIAL_FINDINGS:-7}
      PORTFOLIO_HEALTH_DAILY_CAP: ${PORTFOLIO_HEALTH_DAILY_CAP:-2}
      PORTFOLIO_HEALTH_PLANS: ${PORTFOLIO_HEALTH_PLANS:-trader,floor_manager}
```

Defaults are mirrored into the substitutions because **an empty env var still
overrides a Settings default** (the KIMI block records this trap,
docker-compose.yml:119-123; `VLLM_MODEL` pattern :107) — a bare `:-` would
silently blank the plans list and hard-close `plan` mode. Enforcement,
verified: `test_config_compose_parity.py:71` iterates `Settings.model_fields`
(:79-83) against UPPERCASE keys regex-extracted from the api-alpha env block
(:58-68, :76); any field neither forwarded nor excused in `_NOT_FORWARDED`
(:29-55) fails the build. All five fields are forwarded ⇒ no `_NOT_FORWARDED`
entries; the existing test goes green automatically (CR040; DEF038/DEF063
class).

Admin hygiene (pattern verified; **non-blocking**, CR027 follow-up):
`/v1/admin/config-check` (admin.py:220-243) echoes non-secret operational
values (`one_on_one_credit_cost`, :242). Add `portfolio_health_gate_mode:
str` to `AdminConfigCheckResponse` and populate it the same way. The
`_FEATURE_GATES` list (:200-217) is for presence-gated silent fallbacks — the
gate mode is a loud `Literal` and does not belong there.

## 4. Out of scope for this module

- Metric math, Σ, sufficiency, block schema — M02/M04 (context passed through
  verbatim).
- Rules + hysteresis — M05. Rendering, validator, LLM path, fallback — M06.
- `EntryType.PORTFOLIO_HEALTH_ANALYSIS`, wire mapping,
  `test_journal_entry_type_parity.py` update, payload write — M08 (M07 reads
  rows by string constant only).
- Mobile card + CTA/trial/upgrade copy and its `retranslate:[ar,ms]` — M09.
- Credit metering — not wired; Rev 4 names `credit_service.py` only as the
  future hook *if* generation is ever credit-metered.
- Snapshots, backfill, promotion — M03/M10/M11.

## 5. Tests

`backend/tests/unit/test_cr136_health_gate.py`. Idiom: small FastAPI app +
`app.dependency_overrides[get_current_user] = lambda: _U(id=user_id)`,
`TestClient(app, raise_server_exceptions=False)`
(test_cr026_sector_allocation.py:308-323). Seed journal rows by inserting
`JournalEntryRow` via `get_session()` directly (bypasses the store's enum
guard, journal_store.py:84-86 — tests run before M08 lands). Monkeypatch the
M04/M06 seams (`build_health_context`, `generate_and_persist_finding`).
Reset `portfolio_health_finding_rate_limit` between tests (`reset()`,
rate_limit.py:79). Inject `now`; freeze time via seeded `created_at` values.

Cases (Rev 4 acceptance "Gate logic", boundaries at ±):

1. **`_own` 403** — GET and POST with a different authenticated user.
2. **Tiles never gated** — each mode `open|trial|plan`, trial exhausted (7
   entries) AND plan `floor_pass`: GET 200 with `metrics` + full `gate`.
3. **Trial by days** — first entry at `now − 13d23h` ⇒ POST generates (day
   14, inside); at `now − 14d` ⇒ 402 `portfolio_health_gate_closed` (day 15).
4. **Trial by findings** — 6 seeded entries (distinct `as_of` ≠ today's) ⇒
   7th generates; 7 seeded ⇒ 8th 402. ≥1 seeded row soft-deleted — still
   counted.
5. **Whichever sooner** — 7 findings in 3 days ⇒ refused with
   `trial_days_left > 0`; 2 findings, first at −15d ⇒ refused with
   `trial_findings_used < 7`.
6. **Daily cap, all modes** — 2 entries created today (UTC, `as_of` ≠
   today's) ⇒ third POST 429 `portfolio_health_daily_cap_reached`; repeat
   under `mode=open`. Boundary: 1 entry today ⇒ second POST generates.
7. **Idempotent same-day** — seeded entry with `payload["as_of"] ==` today's
   context `as_of` ⇒ 200, `created: false`, same `journal_entry_id`, row
   count + `gate.daily_used` unchanged; works with the gate exhausted (step
   6-before-7 ordering pinned).
8. **mode=open bypasses trial** — exhausted counters + `floor_pass` ⇒
   generates (subject only to cap).
9. **mode=plan gates immediately** — zero findings: `floor_pass` ⇒ 402;
   `trader` ⇒ generates; `trial_trader` with past `trial_expires_at` ⇒ 402
   (trial-expiry-awareness through entitlements.py:58-77).
10. **Plan list parsing** — list from `"TRADER, floor_manager"` matches
    `trader`; empty list ⇒ `plan_has_access` false for every plan (mode=plan
    then hard-closed — loud, documented).
11. **Gate status shape** — exactly the 8 §3.2 keys, correct types, present
    in GET and both POST outcomes.
12. **Rate limiter** — 6th POST in the window ⇒ 429 `rate_limit_exceeded:
    portfolio_health_finding` (limiter's own 429, rate_limit.py:127-131).
13. **Entry-type string pin** — `PORTFOLIO_HEALTH_ENTRY_TYPE ==
    "portfolio_health_analysis"`; if `EntryType.PORTFOLIO_HEALTH_ANALYSIS`
    exists (M08 landed), assert equality with its `.value` (skip-if-absent).
14. **Mock-refusal path** — refusing context ⇒ POST 409
    `portfolio_health_unavailable`; GET still 200.
15. **Compose parity** — no new test: the existing
    `test_config_compose_parity.py` green ⇔ all five fields forwarded.

## 6. Acceptance

- [ ] `pytest backend/tests/unit/test_cr136_health_gate.py -q` green (sqlite
      tempfile; Mac is pure editor — no live backend).
- [ ] `pytest backend/tests/unit/test_config_compose_parity.py -q` green.
- [ ] `pytest backend/tests/unit/ -q` green (no regression).
- [ ] `grep -n "portfolio_health_" backend/app/core/config.py` — exactly the
      five §3.1 fields with §3.1 defaults.
- [ ] `grep -n "PORTFOLIO_HEALTH_" docker-compose.yml` — the five §3.6 lines,
      mirrored defaults (no bare `:-` on GATE_MODE/PLANS).
- [ ] `grep -n "enforce_gate" backend/app/api/portfolio.py` — exactly one
      call site (POST); GET calls `evaluate_gate` only.
- [ ] `grep -n "EntryType" backend/app/services/health_gate.py` — no matches.
- [ ] GET/POST responses match §3.4/§3.5 shapes verbatim.
- [ ] No new user-visible strings (machine codes only) — nothing to flag
      `retranslate:[ar,ms]` in this module.
- [ ] Commit tagged `(AT:R<N> CR136)`, pathspec-commit only M07's files.

## 7. Hand-off

**M09 may assume frozen:** the GET/POST URLs + JSON envelopes of §3.4/§3.5;
the 8-key gate dict (CTA states render from it); error codes `403` (_own),
`402 portfolio_health_gate_closed`, `429 portfolio_health_daily_cap_reached`,
`429 rate_limit_exceeded: portfolio_health_finding`, `409
portfolio_health_unavailable` — every gate error carries the full `gate`
dict.

**M11 may assume:** launch `trial` → full `plan` gating is a pure env change
(`PORTFOLIO_HEALTH_GATE_MODE=plan`) + container recreate — no code path
differs; `/v1/admin/config-check` echoes the live mode.

**Seams this doc asserts** (Rev 4/README pin shapes, not callables —
reconcile at build time; if names differ when M04/M06 land, the doc that
landed first wins and the other is amended):

- M04 exposes `build_health_context(user_id: UUID) -> dict` returning
  `{as_of, generated_at, engine_version, metrics: {…blocks…}}` with a
  machine-readable mock-mode refusal marker.
- ~~M06 exposes `generate_and_persist_finding(user_id, portfolio, context,
  prior_entry) -> {journal_entry_id, created, as_of, sections}`~~ — **superseded
  by shipped M06 (AT:R66)**, per this section's own rule that the doc which
  landed first wins: the name is right, but the call is keyword-only
  (`user_id, portfolio_id, as_of, metric_blocks, store, evaluate, gateway=None`)
  and it returns a `FindingResult` dataclass. It persists via M08 with
  `reference_id = portfolio_id` as stated. See the corrected call in §3.5 step 8.
- Finding journal payload carries at least `as_of`, `portfolio_id`,
  `sections` (`head`,`f1`…`f5` markdown), `rule_states` (README contract 5);
  M07 reads `as_of` + `sections`.
