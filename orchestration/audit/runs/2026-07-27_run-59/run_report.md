# Audit run 2026-07-27_run-59 — CR100 (coder.mobile), round 1

**Item:** CR100 — render three dark BE contracts on the mobile portfolio surface
(CR026 sector-allocation donut, CR029 per-lot cost-basis cards, CR030 dividend sub-chip).
**Branch/SHA:** `lane/CR100.coder.mobile` @ `aa88463` (base `main` @ `65adbc6`).
**Gate:** spawned (Architect-spawned auditor). **Verdict:** COMPLETE (round 1).
**Auditor worktree:** `.claude/worktrees/audit-CR100` (detached @ `aa88463`), reaped at wrap.

## Reproduced independently (own worktree, all foreground)

- **Scope.** `git diff --stat main...aa88463` → 12 files, +1170/−8. ZERO files under `backend/`. Scope claim holds; the zero-backend BLOCKER trip did not fire.
- **Contract test.** `flutter test test/models/sim_cr100_contract_test.dart` → **12/12 pass** (matches coder claim).
- **Full suite.** `flutter test` → **88/88 pass** (matches coder + Architect).
- **Analyze.** `flutter analyze` → **5 issues** (not 4). All pre-existing, none in a CR100 file: `lib/main.dart:69` ×2 (deprecated copyWith), `lib/screens/floor/floor_screen.dart:73,313` (async-gap context), `test/widgets/sign_in_email_disclosure_test.dart:27` (super-param). The coder's "4" came from `flutter analyze lib/` (lib-only, excludes the `test/` info). Precise statement: **clean on every touched file; repo carries 5 pre-existing infos**, not globally clean.
- **Register drift.** `gen_registers.py verify all` → CR OK, 96 rows, content identical to live. `CR100.row.md` present. No drift (confirmed myself, not on the Architect's word).
- **Origin.** `git branch -r --contains aa88463` → `origin/lane/CR100.coder.mobile`. SHA is on origin.

## The load-bearing claim — fixtures transcribed from BACKEND, not the model

Diffed every fixture literal in `sim_cr100_contract_test.dart` against the actual return dicts:

- **CR026** fixture keys `{allocation, total_value, compliance{max_sector, max_sector_name, max_allowed, compliant}}` ≡ `portfolio.py:81-89` exactly.
- **CR029** top `{ticker, current_price, price_source, lots, totals}` ≡ `sim.py:463-473`; lot keys (9) ≡ `Lot` NamedTuple `cost_basis_lots.py:60-71` exactly; `totals{realised_pnl, unrealised_pnl, quantity_open}` ≡ `sim.py:468-472`.
- **CR030** fixture keys (7) ≡ `sim.py:593-601` exactly, including the two dividend keys the pre-CR100 model dropped.

Fixtures agree with **both** backend and model — the correct outcome (model now reads every backend key). Nullability matches: `max_sector_name`, `unrealised_pnl` (per-lot), `ex_dividend_date`, `dividend_rate` all nullable in fixture, model and backend; `current_price` is always float (backend `current_quote` floors to `Quote(price=0.01, source="unavailable")`, never None) so the required read is safe.

## Mutation tests (production code broken, only the guard should go red, then restored)

1. **Simulate the exact original bug** — set `exDividendDate`/`dividendRate` reads to `null` in `SimEarnings.fromJson` → **only the 2 dividend tests went red** ("both present", "either alone"); all CR026/CR029 green. Proves the contract test catches the silent-key-drop this CR exists to close.
2. **`?? default` anti-pattern on a required field** — `maxAllowed: (j['max_allowed'] as num?)?.toDouble() ?? 0.40` → the **"a renamed/missing required key throws"** test went red (no longer throws). Proves the test pins the exact `?? default` mechanism the assign forbids. The "max_allowed read from wire" test (line 46) stays green because it supplies the key; the two tests together pin the rule.

Both mutations reverted; `git checkout` confirmed clean.

## The five explicit rules

1. **No `?? default` on a required field.** `grep '?? ' sim.dart` — every hit is on a nullable field (`maxSectorName`, `unrealisedPnl`, both dividend fields), a list/`?? const []`, or pre-existing code (`source ?? 'unknown'` on SimHistory/SimNews/SimEarnings — backend always sends `source`; unrelated to CR100). None on any CR100 required field. ✓
2. **Nullable renders as ABSENT, not zero.** `_LotCard` (`ticker_detail_screen.dart`): `unrealised == null` → `tickerDetailLotUnrealisedUnknown` = "Unrealised —", never $0.00. `_DividendChip`: date/rate each wrapped in `if (… != null)`. Breach line suppressed when `maxSectorName == null`. Model tests pin `unrealisedPnl`/`maxSectorName` stay null. ✓
3. **`max_allowed` read from response.** Interpolated from `compliance.maxAllowed` (`portfolio_screen.dart:500`); no literal 0.4 in donut code — the two `0.4` grep hits are unrelated comments (a `Dismissible` threshold note at :709, a comment at :493). Pinned by contract test line 46. ✓
4. **"Other" never a breach (BLOCKER check).** Structural: `_sectorColor('Other')` → `slate500` gray, never red/amber; the red breach `Text` renders only on `!compliant && maxSectorName != null`, and `max_sector_name` is computed over KNOWN sectors only (`portfolio.py:74`) so can never equal "Other". Model test asserts `maxSectorName isNot('Other')`. No path paints Other as a breach. ✓ (BLOCKER absent.)
5. **Dividend chip hidden iff both fields null.** Call site: `(!e.hasData && !e.hasDividendData) → shrink`, else `Wrap[ if hasData EarningsPill, if hasDividendData DividendChip ]`. `hasDividendData => exDividendDate != null || dividendRate != null`. Pinned by 3 model tests (both-present, both-null, either-alone). ✓

## Other checks

- **AMI naming.** No user-visible string says "the AI"; the new strings are financial labels with no AI reference, so no AMI-by-name obligation triggered. ✓
- **No invented translations.** `app_localizations_ar.dart` / `_ms.dart` carry the **English fallback** for every new key (`'COST BASIS LOTS'`, `'OPEN'`, …) — correct gen-l10n behaviour; no Arabic/Malay authored. Only `app_en.arb` carries authored strings, each with a context comment. ✓
- **API wiring.** `/v1/sim/lots/{userId}/{ticker}` and `/v1/portfolio/sector-allocation/{userId}` match the backend route decorators exactly; providers pass `DeviceUser.getOrCreate()`. ✓

## Coder's stated gaps — judged

- **No widget-pump test for the three render surfaces.** The lane's risk is rendering, yet render rules are verified by reading + model tests, not a pumped widget. Judged **acceptable, MINOR**: the defect class this CR closes is *deserialization* (silent key drop), which model-contract tests transcribed-from-source cover fully and which the mutation tests prove; the render rules (rules 2–5) are simple and **structurally enforced** (color mapping, backend field exclusion, `if`-gated widgets) — I traced each to code, not just to a claim. A widget test would strengthen coverage but its absence leaves no plausible unguarded failure path for a GATE:spawned read-only UI lane.
- **No live Alpha capture.** Not required — I diffed the fixtures against the return dicts at source, which is equivalent evidence for a key/nullability contract. Not independently re-captured from Alpha; noted, not held against the lane.

## Findings

- **MINOR-1** `_LotStatusChip` (`ticker_detail_screen.dart`) `switch(status)` `default:` → "PARTIAL": a wire `status` outside the 3-value enum silently reads as partially_closed — soft version of this CR's own defect class. Backend guarantees the enum, so low risk; defensive-coding suggestion only.
- **MINOR-2** No widget-pump test (see above). Recommend a follow-up pump test if the donut/lots layout is later touched.
- **MINOR-3** (informational) `SimEarnings.source` uses `?? 'unknown'` — pre-existing, backend always sends `source`; consistent with sibling models. Not a CR100 regression.

**BLOCKER 0 · MAJOR 0 · MINOR 3.**
