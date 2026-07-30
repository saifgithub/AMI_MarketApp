<!-- auditor lane — track U (Kimi). CR052 / orchestration/audit/PROTOCOL.md. -->
# CR129-BE — auditor

VERDICT: COMPLETE (round 1)

Audited `lane/CR129-BE.coder.api` @ `344e2b30` in scratch worktree
`.claude/worktrees/audit-CR129-BE` (never `main`, never the builder's tree).
SCOPE: `chunk` — shorter evidence list, no DoD bounce (DoD present anyway).
Tiered audit policy: targeted + registers + probe + blind mutation up front,
full suite backgrounded during the read.

**Audit incident, disclosed:** the audit worktree was deleted externally
mid-audit (a fleet cleanup swept `.claude/worktrees/` — several other stale
worktrees are gone too), killing the first background suite run with it
(exit -1, no output). Probe results captured before the deletion stand;
worktree recreated at the same SHA, suite re-run clean. Nothing about the
verdict rides on the interrupted run.

---

## Round 1

### The headline: DEF187 is dead, measured by me, not taken on the lane's word

Probe (real floor resolvers, unset `risk_score=3` mandate): the floor's
`single_name_cap_pct` now returns **3.0** — the same risk-tier preset the
Room pre-clamp and every overlay already read. Pre-CR129 that call returned
**50.0** (measured in my REL61 audit: floor 50.0 vs overlay 3.0, ~16.7x).
The shown-vs-enforced split CR101 couldn't close is closed: overlay, Room,
and ticket path now resolve one value for set AND unset users.

### The inversion is live and it binds — probed end to end

CR129's authorised inversion (`None` = "follow my risk profile", not "off")
is not just a table: my probe's unset mandate, buying 30 minutes after a
stop-out, **blocked** — `post-loss cooldown active until … (1.0h after the
last stop-out)`, the resolved tier-3 preset. The overlay converges the same
way: every `_text` helper now interpolates the resolved value; explicit `0`
cooldown narrates `off (no cooldown enforced)` and the floor's `> 0` check
agrees (off stays expressible, as an override, never as the unset state).

### Blind mutation (auditor's own): preset table integrity is pinned

`DEFAULT_POST_LOSS_COOLDOWN_HOURS[3]`: 1.0 → 9.0 → exactly **2 RED**
(`test_every_risk_score_resolves_all_five_limits_to_the_documented_table[3-…]`
and `test_preset_tables_carry_exactly_the_documented_five_scores`). Reverted,
`git status` clean, 21/21 re-green. The documented table can't drift silently.

### Read at file:line

- `risk_limits.py`: five preset tables + `resolved_*` coalesce-at-read
  functions; open-risk cap as a fraction of the user's OWN `max_drawdown_pct`
  (per-user derived, not a constant — correct); `_as_aware_utc`
  normalization is the necessary consequence of the brakes becoming
  always-active (SQLite naive vs Postgres aware), scoped to comparisons.
- `safety_floor.py`: all five blocks resolve then evaluate; the BE2-r2
  loud-fail contract preserved verbatim (missing context blocks loudly, now
  unconditionally since the limits are always active); `check_holdings_against_mandate`
  breach flags resolve identically.
- `overlay_generator.py`: converged (above).
- `api/mandate.py`: **DEF197 closed** — the BE1 caps join the journal diff
  loop (my REL61 r2 MINOR), and the unset wording is now "following your
  risk profile" — the same phrase the mobile screen uses. Day Trader PATCH
  gets its own distinct summary via `is_day_trader_preset`.
- `day_trader_preset.py`: explicit permissive overrides, no bypass flag,
  `risk_score` untouched; disclosure names Barber & Odean + Taiwan baselines.
- `risk_limit_backfill.py`: disclosure-lines builder for the one-time
  journal script (`scripts/cr129_backfill_journal.py`, present); correctly
  excludes `sector_cap_pct` (already preset-backed pre-CR129 — nothing
  changes for those users); the pre-CR129 50.0 "was" value is frozen in a
  module constant so a future edit can't rewrite the historical record.
- `agent_runner.py` / `brief_engine.py`: hydrate functions pass the seven
  fields through, `None` resolving like a stored mandate — dev/test paths
  can't silently diverge from production semantics.
- Acceptance-5 boundary tests read: permissive-side sanity (95%-of-book buy
  passes under the preset) THEN halal/blocklist/locale/allowlist each
  independently still block — the "compliance still blocks" claim means
  something because the permissive side is proven permissive first.

### The sim_reputation correction — checked

The bridge corrects the task briefing's "order-dependent pollution"
diagnosis to "real DEF187-unification regression". Verified: targeted run of
`test_sim_reputation.py` passes 4/4 on this tree; the fix (pin
`single_name_cap_pct=100.0` before submit) matches the documented 7-site
pattern from `502e96cf`; the diagnosis (default `ensure_anonymous` mandate +
1-share market order ≈ 3-4% of a $10k book against a 3.0% resolved cap) is
arithmetically consistent. The correction is honest and the fix is in-fence.

### Measured (all reproduced by me, worktree @ `344e2b30`)

| Check | Builder claimed | Auditor reproduced |
|---|---|---|
| Full suite | 1675 passed, 249.00s | **1675 passed**, 241.07s (clean tree, after incident re-run) |
| Targeted: CR129 file + sim_reputation | 21 + fixed 2 | **25 passed**; 21/21 re-green post-mutation-revert |
| `gen_registers.py verify all` | rows + tables committed together | DEF 199 / CR 128 rows, both OK |
| Probe: unset single-name resolver | DEF187 closed | **3.0** (was 50.0) |
| Probe: unset mandate, buy 30min post-stop-out | inversion live | **blocked**, resolved 1.0h preset |
| Mutation: cooldown table[3] 1.0→9.0 | n/a | exactly **2 RED**, reverted clean |

### MINORs (recorded, not blocking)

- m1. The floor's loud-fail messages still read "…is set on the mandate but
  the caller did not supply…" — under CR129 nothing needs to be "set" (the
  limit is always active via preset). Behaviour is right; the wording is a
  stale BE2-r2 artifact. Cosmetic.
- m2 (cross-lane note, not a finding against this lane): the CR101-MOBILE
  screen still renders unset BE2 fields as "OFF" — true pre-CR129, false
  now ("OFF" = explicit override). Owned by CR129-MOBILE (bridge names it
  open on DEF193); recorded so the seam is on the board.

Zero BLOCKER + zero MAJOR → **COMPLETE**.
