# CR136 build — M11: Verification, audit pack + promotion

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

**Cross-cutting; the LAST module.** Runs only after M01–M10 have landed on
`main`. Its deliverable IS the checklists and scripts below — every item is a
runnable command or a yes/no check. Nothing in M11 changes app or mobile
behaviour; anything broken found here mints a `DEF###`, is fixed in its owning
module, and the affected checklist section re-runs.

## 1. Purpose

Implements the end-to-end half of Rev 4 §"Acceptance" (melehost items), the
§"Risk class" audit mandate (independent audit of M02 + M05), and the ship
gate: independent numpy cross-check of the live engine, F16 bias-test runbook,
scenario-constant re-verification against live SPY, the hostile-reader pass,
`/promote-to-alpha` + post-promote checks, the dual-store mobile release with
iPhone 13/17 device checks, and the four docs-sync deliverables (methodology
v2, SCREEN_DESIGNS consistency, i18n flags, register flip).

## 2. Files

**New** (header one-liners verbatim):

- `backend/scripts/cr136_live_crosscheck.py` —
  `"""CR136 M11 live cross-check (dev-only, run inside ami_api_alpha) — recomputes σₚ/β/R²/DR²/risk shares/TE for one real book from raw price_history_daily rows with an independent numpy implementation and diffs against the live /v1/portfolio/health payload to 2 dp. Never imported by tests or app code; must not import app.trading_math."""`
- `docs/forward_planning/CR136_portfolio_health_metrics/verification_fleet/README.md` —
  `<!-- CR136 M11 — archived Rev 4 verification-fleet scripts: the auditor's re-derivation pack for the CR136-M02 / CR136-M05 audit lanes. Index: agent → script → measured pin. -->`
  (plus the archived scripts themselves, §3.5).
- `docs/forward_planning/CR136_portfolio_health_metrics/hostile_reader_pass.md` —
  `<!-- CR136 M11 — hostile-reader pass record (Rev 4 acceptance): one full generated Finding vs the rude-PM checklist; Saiful's verdict per item, dated. -->`
- `docs/forward_planning/CR136_portfolio_health_metrics/bias_readings.md` —
  `<!-- CR136 M11 — F16 bias-test reading log: dated sd(z) readings per portfolio; band [0.911, 1.089] is decision-grade at n=252. Record, don't gate. -->`
- `docs/forward_planning/CR136_portfolio_health_metrics/i18n_retranslate.md` —
  `<!-- CR136 M11 — collected retranslate:[ar,ms] flags for every new EN string shipped by M08/M09, per the content-change rule. -->`
- `orchestration/audit/cr/CR136-M02.architect.md`, `orchestration/audit/cr/CR136-M05.architect.md`
  — audit lane files; format owned by `orchestration/audit/PROTOCOL.md` (§3.5).

**Touched:**

- `docs/forward_planning/CR136_portfolio_health_metrics/PORTFOLIO_REVIEW_METHODOLOGY.md`
  — v1.0 → v2.0 (§3.8a; exact line anchors there).
- `docs/forward_planning/_registry/CR136.row.md` + regenerated
  `docs/forward_planning/cr_list.md` (§3.8d — generated register, never
  hand-edit the table; `scripts/registers/gen_registers.py`).
- `orchestration/audit/cr/INDEX.md` — architect-owned lane index, two new rows.
- `SCREEN_DESIGNS.md` only if the §3.8b consistency check finds drift.

No backend/app or mobile source changes. `docker-compose.yml` untouched (M03/M07
already forwarded every new Settings field; `backend/tests/unit/test_config_compose_parity.py:71`
enforces).

## 3. Implementation spec

### 3.1 Independent cross-check harness (Rev 4 acceptance: "before ship")

`backend/scripts/cr136_live_crosscheck.py`. numpy is in the container
transitively via yfinance (`backend/pyproject.toml:27-37`); pandas is present
and allowed, not required. `backend/scripts/` rides the promote rsync, so run
in-container (the `scripts.cr136_bias_test` pattern, M03 §3.6):

```bash
ssh melehost "docker exec ami_api_alpha python -m scripts.cr136_live_crosscheck \
  --user-id <uuid> --api-base http://localhost:8000 --token <bearer-for-that-user>"
```

Algorithm:

1. `GET {api-base}/v1/portfolio/health/{user_id}` (M07 tiles route, `_own`-guarded
   — the token must belong to the target user). Take from the payload ONLY:
   the holding set, `dropped_holdings`, `n_observations`, `window_days`, and
   the values under test. Dropping/hygiene decisions are M01/M04 policy already
   unit-tested at their boundaries; the harness cross-checks the **math**.
2. Read raw adjusted closes for the surviving tickers + SPY **directly from
   `price_history_daily`** (M01's table) with its own `SELECT` (read-only) —
   not via M01's series functions. Re-do the date inner-join, simple returns,
   and window trim (up to 504 returns, newest last) itself.
3. Recompute in numpy — an independent implementation, `import app.trading_math`
   forbidden (same independence stance as M02's fixture generator): EWMA
   λ=0.97 weighted-demeaned population covariance over risky holdings + SPY
   leg; cash zero-row appended after estimation; then σₚ (annualised √252),
   β + R² (joint-matrix form), TE `√(σₚ² + σ_b² − 2βσ_b²)`, DR², Euler risk
   shares per holding (invested-sleeve display basis, per the payload's
   `basis`).
4. Print a diff table `metric | api | recomputed | diff` and exit non-zero
   unless every |diff| ≤ 0.005 in the rendered unit — 2 dp agreement, Rev 4
   verbatim ("to 2dp"): σₚ/TE in pp; risk shares in pp; β/R²/DR² unitless.
5. Guards: unknown user, `sufficient: false` σₚ block, or `partial: true`
   with the API's dropped set unavailable ⇒ print why and exit 2 (distinct
   from a numeric FAIL exit 1). Never writes to the DB.

**Book selection:** one REAL tester book — exclude the 13 CR035 room-benchmark
synthetics and the 10 seed rows (deterministic filter in
`memory/feedback_user_report_exclusions.md`: `last_app_version <> 'room-benchmark'`
+ the 05-24 05:10 seed batch). Prefer ≥ 4 risky holdings with T ≥ 126; if no
real book qualifies at ship time, Saiful's own account book is acceptable and
the choice is recorded in the run output pasted into the lane/acceptance notes.

### 3.2 Bias-test runbook (F16 — record readings, never gate launch)

- Command (M03's script, wired here):
  `ssh melehost "docker exec ami_api_alpha python -m scripts.cr136_bias_test"`
  — prints per portfolio `n`, `mean_z`, `sd_z` vs `BIAS_SD_BAND = (0.911, 1.089)`.
- Append every reading to `bias_readings.md`: date, portfolio id (real books
  only, same exclusion filter), `n`, `mean_z`, `sd_z`, in/out of band.
- **Maturation schedule (pinned):** z-pairs need a prior-day
  `predicted_vol_ann`, and M10-backfilled rows carry null vol columns — so
  the clock starts at ship. First reading once any real book has n ≥ 21
  pairs (~1 month); repeat monthly (~21 new pairs each). The band
  `[0.911, 1.089]` is Rev 4's acceptance band **at T=252** — readings before
  ~12 months of live snapshots are recorded as immature, not judged.
- An out-of-band `sd_z` at n ≈ 252 on a real book mints a DEF against the
  estimator (Tier 2 is Tier 1's validation layer, F16). Launch is never
  gated on this.

### 3.3 Scenario-constant verification (fix stale, never ship stale)

- From the Mac (dev-only network, per M02 §3):
  `"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" backend/scripts/cr136_generate_fixtures.py --verify-scenarios`
  — refetches the live SPY **price** series (`auto_adjust=False`
  — amended 2026-08-02 AT:R66; see Rev 4's amendments section: the pinned
  constants are S&P 500 PRICE-index returns and miss a total-return series by
  up to 0.91pp over the 2022 episode), recomputes COVID crash
  2020-02-19→03-23 and 2022 drawdown 2022-01-03→10-12 episode returns, diffs
  against `SCENARIO_EPISODES` in `app/services/portfolio_health_constants.py`
  (−0.339 / −0.254); exits non-zero when |diff| > 0.5 pp.
- Non-zero exit ⇒ update the two `benchmark_return` values in
  `portfolio_health_constants.py` to the recomputed figures, re-run M02/M04
  tests, re-run `--verify-scenarios` to exit 0. Adjusted-close series drift
  with dividend adjustments — the constants module is the single home; fix it
  there, nowhere else.

### 3.4 Hostile-reader pass (Rev 4 acceptance; Saiful, rude-PM hat)

One full generated Finding from a live real book (the §3.1 book is fine),
reviewed against the standard. Each item is yes/no; record per-item verdicts,
date, and book in `hostile_reader_pass.md`:

1. Every number carries method, window, and n (§F3 blocks: value, SE with
   `t_eff` stated, `n_observations`, `window_days`, estimator + citation).
2. Disclosure block at the HEAD, before §F1, all five lines (F19):
   `disclaimerShort`, gross-of-fees + zero-cost sim, backcast line,
   window + estimator line, and the standing non-stationarity caveat
   verbatim per Rev 4 §F3.
3. No judgement adjectives anywhere.
4. Every claim payload-traceable (validator enforces tokens; the human pass
   checks the *statements*).
5. §F5 conditional-educational speech act: no imperative on the user's
   tickers, no "you should", no severity bands; section renamed "What the
   numbers point to".
6. §F1/§F2/§F5 plain language: the literal "R²" never appears outside §F3
   (renders as "the market explains only X% of this book's day-to-day
   moves"); no register-lexicon term.
7. Window + backcast stated (today's-weights-on-past-returns labelling).
8. §F5 spot-checked against the live site's compliance line — *"It does not
   and will not give investment advice"* (`website_api/app/knowledge/faq.md:45`)
   — stays true on the LLM path AND the deterministic fallback.

Any "no" ⇒ mint a DEF, fix in the owning module, regenerate a fresh Finding,
repeat until all-yes. The recorded all-yes is a ship precondition.

### 3.5 Audit submissions — M02 + M05 (Rev 4 "Risk class")

Mechanics per `orchestration/audit/PROTOCOL.md` + `AMI_TRADE_BINDINGS.md`,
summarised:

- **Lane ids:** `CR136-M02` and `CR136-M05` under `orchestration/audit/cr/`
  (compound-id precedent: `CR054-W0a`, `CR098-MOBILE-LIVE`). `SCOPE: chunk`
  (module of a larger CR). `depends-on: none` — the lanes verify disjoint
  logic; both must be COMPLETE before promote regardless.
- **Architect side (the builder):** write `<ITEM>.architect.md` carrying the
  commit SHA, what/why, the test command **and its observed output**
  (measured against the committed SHA in a scratch worktree, NOT the shared
  tree — DEF159), the real measurement as run, revert-proof QA, and a
  `SUBMITTED: round 1` line (the token must OPEN the line — an indented or
  quoted token is prose, not state). Add both rows to `cr/INDEX.md`.
  Pathspec-commit only own lane paths, push, and confirm origin advanced
  (`git branch -r --contains <sha>`) — delivery is on origin, not local.
- **Auditor side:** independent session/agent; checks out the SHA into
  `.claude/worktrees/audit-<ITEM>/`; runs the independent regression suite
  with the absolute interpreter
  (`"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q`
  from the worktree's `backend/` — never bare `pytest`); reproduces the
  measurements; returns `VERDICT: COMPLETE | AWAITING_FIXES (round N)` where
  N = the round audited. AWAITING_FIXES ⇒ fix and bump to
  `SUBMITTED: round 2`. COMPLETE = zero BLOCKER + zero MAJOR. DoD-table
  enforcement is waived (bindings gap-fill 7) — recorded, not bounced.
  Auditor-authored pins go into `backend/tests/unit/test_<item>_<topic>_pin.py`
  + the `MIGRATED_PINS` tuple (DEF141).
- **The re-derivation pack:** the Rev 4 7-agent verification-fleet scripts.
  Archive them from the Rev 4 session scratchpad into
  `verification_fleet/` (with the README index) BEFORE submitting the lanes.
  What they cover, by agent: **estimator** (EWMA vs LW Monte Carlo — R2
  detection 89.0% vs 30.1%, δ\* = 0.4371, EWMA flip rate 21.3% vs 8.9%,
  T_eff-SE ~27% understatement); **rules** (R1 band flip 7.7% / detection
  95.6%, R2 band 5.5% / 99.3%, R3 0.6·SE band 8.0% / 96.0%, CI-gating
  rejection 50.8%); **closed forms** (Lo Eq. 9 CI [−2.28, +4.28],
  970/971/1,982-day power, bad-month 2.71/6.07/12.44, MDD walk-table
  provenance); **cash artefact** (×(1−c) scaling, share invariance to 3e-16,
  HHI non-monotonicity 2.63→3.53→3.37→2.38); **ETF see-through** (live data:
  DR² 1.261/1.024, ρ(SPY,QQQ) = 0.952, ~5pp look-through understatement);
  **repo source checks** (file:line cites); **validator prototypes**
  (allow-list 0 false accepts/rejects on 20 cases, digit-rule rejecting
  10–13/25 of mandated content, register lexicon 0/10 FP). If the scratchpad
  has been reaped (it is session-tmp), record that in both lane files; the
  fallback pack is M02's `cr136_generate_fixtures.py` + the per-module test
  suites — every measured pin above has a named test in M02/M05 §5.

### 3.6 Promotion runbook + post-promote checks

Backend ships via `/promote-to-alpha` (`.claude/commands/promote-to-alpha.md`
owns the detail; `docs/initial_specs/10_delivery/promotion_protocol.md` owns
the design). Summary of its ordered steps: (1) preflight blocking checks —
the `infra/PROMOTION_HOLD.md` ACTIVE-HOLDS gate, clean `git status --short`,
`pytest backend/tests/unit/ -q` green, `flutter analyze --no-fatal-infos`,
then Saiful's explicit y/n smoke confirmation; (2) tag `alpha-YYYY-MM-DD-N`
(Asia/Kuala_Lumpur); (3) rsync to `melehost:~/ami_trade/` with the pinned
excludes (`.env`, `mobile/`, `.claude/`, and `audit/` + `reports/` — DEF081,
`--delete` protection); (4) `scp infra/alpha.env` + six-key verify; (5)
recreate only `api-alpha` (`docker compose --profile tunnel up -d --build
api-alpha`), poll healthy; (6) `alembic upgrade head` — CR136 applies TWO
migrations (M01 `price_history_daily`, M03 `portfolio_value_snapshots`); (7)
smoke `/v1/health`, `/v1/llm/status`, `/v1/sim/quote/AAPL`; (7b) admin
config-check; (8) report. Never auto-rollback; surface and let Saiful decide.

**No PROMOTION_HOLD entry is needed for CR136 itself:** the new routes are
additive (old clients never call them) and the one shared surface — the
journal — degrades on old clients to the DEF210 UNKNOWN card (Rev 4 journal
plan, verified). Still honour the hold gate for unrelated active holds.

Post-promote checks, each runnable:

```bash
# P1 health
curl -fsS https://api-alpha.agenticmarketintel.ai/v1/health
# P2 new routes live — auth-guarded, so expect 401/403, NEVER 404
curl -s -o /dev/null -w '%{http_code}\n' https://api-alpha.agenticmarketintel.ai/v1/portfolio/health/00000000-0000-0000-0000-000000000000
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api-alpha.agenticmarketintel.ai/v1/portfolio/health/00000000-0000-0000-0000-000000000000/finding
# P3 new settings reached the container (CR040; compose parity ran statically in P0/preflight)
ssh melehost "docker exec ami_api_alpha env | grep -c PORTFOLIO_HEALTH_"   # expect 5
ssh melehost "docker exec ami_api_alpha env | grep PORTFOLIO_SNAPSHOT_INTERVAL_SECONDS"
ADMIN=$(grep '^ADMIN_SECRET=' infra/alpha.env | cut -d= -f2-)
curl -fsS -H "Authorization: Bearer ${ADMIN}" https://api-alpha.agenticmarketintel.ai/v1/admin/config-check
#   → portfolio_health_gate_mode: "trial" (field added by M07; admin.py:220-243 route)
# P4 migrations at head
ssh melehost "cd ~/ami_trade && docker compose exec -T api-alpha alembic current"
# P5 snapshot tick idempotent no-op on the second same-day run:
#    wait one interval (≤1 h) or `docker restart ami_api_alpha` (lifespan re-runs the tick);
#    the second completion line must show written=0
ssh melehost "docker logs ami_api_alpha --since 24h 2>&1 | grep portfolio_snapshot_tick_complete | tail -2"
```

Then, in order: **M10 backfill** (dry-run → spot-check → `--apply`, per M10's
doc), **§3.1 cross-check harness PASS**, **§3.3 scenario verify exit 0**,
**§3.2 first bias reading recorded**.

### 3.7 Mobile release + device checks (standing convention)

Sequential, same build number to both stores — **never in parallel, never
with mismatched bump flags**:

```bash
scripts/build_testflight.sh          # bumps pubspec +N, builds, uploads to TestFlight
scripts/publish_playstore.sh --no-bump   # same +N to the Play internal track
```

Cable install is the local-dev fallback only; testers go via stores. Device
checks on **both iPhone 13 and iPhone 17** (release builds):

- The five card states of SCREEN_DESIGNS §07b — insufficient / partial /
  refusal / empty / loading — plus the populated card; goldens cover all
  states + the three Rev-2 edge fixtures (negative risk share, >100% share,
  100% cash), on-device verify at minimum populated, insufficient (young
  book), empty, and loading. Insufficient/refusal show no numeric glyph;
  insufficient copy names OUR data limit when that is the cause (F20).
- Finding render: head disclosure block first, then §F1–§F5.
- Journal: a `portfolio_health_analysis` entry renders its stored five
  sections via the markdown branch; older entry types unaffected.
- Gate CTA states: trial chip counts down after a generation; daily-cap
  state appears after 2 same-day Findings; upgrade state under `plan` mode.
- `mobile/test/l10n_key_parity_test.dart` green (en/ar/ms parity), AR/MS
  entries present pending retranslation (§3.8c).

### 3.8 Docs sync tasks (each a small deliverable)

**(a) `PORTFOLIO_REVIEW_METHODOLOGY.md` v2** — update the external-review doc
to Rev 4, **keeping it patent-free** (Saiful's standing instruction; v1
verified to carry zero patent citations — keep it that way, do not import the
F12/F18 patent discussion). Version line → *"Version 2.0 — <month> 2026"*.
Edits, at v1 anchors: §3 table `:49` LW → **EWMA λ=0.97 weighted-demeaned**
(*RiskMetrics Technical Document* 4th ed. §5.3.2); add rows for tracking
error, MCR, typical bad month (historical-dispersion phrasing), scenario
panel (backcast what-if), and re-base weight concentration to the invested
sleeve; `:54` realised MDD → rolling trailing 252-trading-day window,
≥ 21-snapshot floor; §5 `:78–` estimation methodology → EWMA (no shrinkage —
state why: no roll-off echo, no alarm suppression, ESS ≈ 66 disclosed) with
**t_eff-based SEs** (`σ̂ₚ/√(2·T_eff)`, WLS `SE(β̂)`); §6 add backcast
labelling + the standing non-stationarity caveat + head placement of
disclosures; §7 → §F5 renamed "What the numbers point to" with the
conditional-educational speech act; §8 add the F16 bias test as the standing
validation; references `:163` drop Ledoit & Wolf, add RiskMetrics.

**(b) `SCREEN_DESIGNS.md` Rev-2 consistency check** — walk amendments 1–10
against the shipped M09 (bar basis + caption, edge cases, invested-weight
tile + ETF chip, head disclosures, "≈66-DAY EFFECTIVE WINDOW" subtitle, §F5
rename, plain-language R², F20 copy, gate CTA states, golden fixtures). Each
a yes/no. Drift ⇒ amend the doc (docs-only commit) or mint a DEF if the code
is wrong.

**(c) i18n flags** — `i18n_retranslate.md`: list EVERY new EN key shipped by
M08/M09 (Finding section labels `findingSectionF1`–`F5`, rule templates
R0–R5 + R2b, ETF-overlap disclosure, `portfolioHealthMockRefusalTitle` + the
state-copy set, tile labels/captions, gate CTA strings, journal card
strings), each flagged `retranslate:[ar,ms]` with its `source_sha` per the
content-change rule (DEF105-generalised staleness guard). Verify copy says
**AMI** by name, never "the AI": `grep -rn "the AI" mobile/lib/l10n/app_en.arb`
returns nothing for the new keys. Translation itself is the i18n lane's job —
M11 only flags.

**(d) Register flip** — after both audit lanes are COMPLETE and Saiful's
hands-on acceptance (bindings gap-fill 4): edit
`docs/forward_planning/_registry/CR136.row.md` status `proposed` → `done`
(append a one-sentence build-completion note), then
`python scripts/registers/gen_registers.py gen cr`, then
`git commit -m "docs(CR136): row flip proposed→done after M11 verification (AT:R<N> CR136)" -- docs/forward_planning/_registry/CR136.row.md docs/forward_planning/cr_list.md`.
Never hand-edit `cr_list.md` (CR081); pathspec-commit only.

## 4. Out of scope for this module

- Backfill mechanics and its dry-run/apply commands — **M10** (M11 only
  sequences it in the runbook).
- Any code fix discovered by these checks — mint a DEF, fix in the owning
  module (M01–M09), then re-run the affected section here.
- ETF constituent look-through (follow-up CR), CR137 Portfolio Room, any
  factor model — Rev 4 out-of-scope list.
- Actual AR/MS translation — i18n lane; M11 collects flags only.
- Store-account operations (TestFlight review notes, Play track config) —
  Saiful's side of `you_do_i_do.md`.
- The bias-test *verdict* — matures with data (§3.2); only the runbook and
  log ship now.

## 5. Tests

M11 ships **no new pytest units** — the deliverable is the runbook: each §6
item is a runnable command or a yes/no check, and full-suite green
(`pytest backend/tests/unit/ -q`, which includes every M01–M08 suite, the
updated `test_journal_entry_type_parity.py`, and
`test_config_compose_parity.py`) is a *precondition* M11 consumes, not a
deliverable it owns. Script-level guards stand in for tests, matching the
`cr136_generate_fixtures.py` / `cr136_bias_test.py` precedent (dev scripts,
never imported by tests or app code — acceptance greps enforce):

- `cr136_live_crosscheck.py`: read-only DB access; exit 0 = all diffs ≤ 2 dp
  tolerance, exit 1 = numeric FAIL (table printed), exit 2 = preconditions
  unmet (unknown user / insufficient σₚ) — a FAIL is never silent.
- `cr136_generate_fixtures.py --verify-scenarios`: non-zero exit outside
  ±0.5 pp (M02-owned; M11 re-runs it against the live series).

## 6. Acceptance — the ship runbook (ordered; run top to bottom)

Phase 0 — Mac preconditions:

- [ ] `pytest backend/tests/unit/ -q` green at the ship SHA (measured in a
      scratch worktree of that SHA, not the dirty shared tree — DEF159).
- [ ] `flutter analyze --no-fatal-infos` + `flutter test` (mobile/) green.
- [ ] `python scripts/registers/gen_registers.py verify` passes (no register
      drift, no untracked row files).

Phase 1 — audit lanes (§3.5):

- [ ] `verification_fleet/` archived + committed (or its absence recorded in
      both lane files with the fallback pack named).
- [ ] `CR136-M02.architect.md` and `CR136-M05.architect.md` submitted
      (`SUBMITTED: round N` opens the line), INDEX rows added, pushed, origin
      confirmed via `git branch -r --contains <sha>`.
- [ ] Both lanes read `VERDICT: COMPLETE` (zero BLOCKER + zero MAJOR).

Phase 2 — promote + live verification (§3.6, §3.1–§3.3):

- [ ] `/promote-to-alpha` completed through step 8; both CR136 migrations
      applied (`alembic current` at head).
- [ ] P1–P5 checks pass as printed in §3.6 (health 200; routes 401/403 not
      404; 5 gate vars + snapshot interval in container env; config-check
      shows `portfolio_health_gate_mode: "trial"`; second same-day tick logs
      `written=0`).
- [ ] M10 backfill: dry-run → spot-check → `--apply` (per M10 doc).
- [ ] `scripts.cr136_live_crosscheck` exits 0 on one real book (§3.1
      selection rule); output pasted into the CR136-M02 lane as the live
      measurement.
- [ ] `cr136_generate_fixtures.py --verify-scenarios` exits 0 against the
      live SPY series (constants fixed first if not — never ship stale).
- [ ] First bias reading recorded in `bias_readings.md` (immature is fine —
      record, don't gate).

Phase 3 — mobile (§3.7):

- [ ] `build_testflight.sh` then `publish_playstore.sh --no-bump`, same +N,
      sequential.
- [ ] iPhone 13 AND iPhone 17 device checklist all-yes (card states, Finding,
      journal markdown, gate CTAs); `l10n_key_parity_test.dart` green.

Phase 4 — human gate + docs (§3.4, §3.8):

- [ ] Hostile-reader pass recorded all-yes in `hostile_reader_pass.md`
      (items 1–8, incl. the live-site compliance spot-check, faq.md:45).
- [ ] `PORTFOLIO_REVIEW_METHODOLOGY.md` v2 committed; `grep -in "ledoit\|patent" …/PORTFOLIO_REVIEW_METHODOLOGY.md`
      returns nothing.
- [ ] SCREEN_DESIGNS Rev-2 consistency walk recorded (drift resolved).
- [ ] `i18n_retranslate.md` committed; every new key flagged
      `retranslate:[ar,ms]`; no "the AI" in new EN strings.
- [ ] Saiful's hands-on acceptance (bindings gap-fill 4).
- [ ] Register flip committed per §3.8d.

All commits: pathspec-only, tagged `(AT:R<N> CR136)` (docs-only commits may
carry plain `(AT:R<N>)` per the exemption; the row-flip commit keeps the CR
id).

## 7. Hand-off

CR136 is **done** when §6 is fully checked. CR137 (Portfolio Room) and any
future session may then assume: the metrics engine is live on Alpha and
independently cross-checked to 2 dp against raw stored prices; M02 and M05
carry COMPLETE audit verdicts with the fleet pack archived beside the CR for
re-audit; the scenario constants match the live SPY series to ±0.5 pp; the
bias log accumulates monthly toward the T=252 band with the runbook in this
doc; `PORTFOLIO_REVIEW_METHODOLOGY.md` v2 is the patent-free external
reference for the shipped estimator; every user-facing EN string is flagged
for AR/MS; and the register records CR136 `done`. The stripped metric context
consumed by CR137's agents is exactly the validated payload these checks
exercised — agents narrate and debate, they never compute.
