<!--
CR098-ROOM.auditor.md — auditor lane file (track U owns). State derives from
round numbers here vs CR098-ROOM.architect.md (see PROTOCOL.md).
-->

# CR098-ROOM — audit lane (auditor)

**Item:** Room analyst pull-back — withhold analysts on plan + account tenure, disclose it
honestly, strip synthetic stand-ins for the withheld domain, and terminate in `NO_VERDICT` when
Market is withheld. Fundamentals unwithholdable.

**Gate:** independent — changes what a user is charged (D2), adds a new `VerdictAction` on the
safety-adjacent PM verdict path, adds a 4th `LiveDataState`.

**Audited SHA:** `908119d`, off `main` @ `2f22a7e`. Isolated worktree
`.claude/worktrees/audit-CR098-ROOM/`, own venv. **Provenance:** two budget deaths; both workers
failed well (incremental commits, honest gap lists); round 2 caught a real acceptance-#13
violation in round 1's branch. The Architect committed round 2's uncommitted hand-off as found
and closed the verification gaps. No production code changed after round 2.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff 2f22a7e 908119d --stat` — 15 files, **+1224/−38**, exact match. |
| Full suite | **1359 passed** in 201s — exactly the Architect's re-measured figure. |
| Compose parity | All three `ROOM_PULLBACK_DAYS_*` forwarded in the `api-alpha` block; `field_validator` already imported at `config.py:6`. |

### What holds — mutation-tested, not read

Every mutation reverted individually; the CR098 file re-confirmed 21/21 green after each.

| Probe | Result |
|---|---|
| **Fundamentals made withholdable** (added to `_WITHHOLDABLE_ORDER` + a threshold + removed the unconditional prepend) | **3 tests red** — the code-not-config guarantee is real |
| **`n_available` counts a `WITHHELD_TENURE` feed** (D2 money) | **1 test red** — `test_aged_floor_pass_social_withheld_debited_strictly_less` |
| **Roster-withhold routed through `WITHHELD_PAID`** (the D3 inversion) | **2 tests red** |
| **`threshold >= 1` dropped** — 0 stops meaning "never" | **1 test red** (see MINOR 2 — not the test you'd expect) |

Read directly and confirmed:

- **#10 is structural.** The `if AgentId.MARKET_ANALYST in ctx.withheld:` branch is **first** in the
  VERDICT if/elif/else, so `_stream_pm_response`, `_parse_pm_verdict` and `enforce_safety_floor`
  are all bypassed — there is no code path from a withheld-Market run to a parsed LLM verdict.
  `_WellFormedApproveGateway.pm_called is False` proves it by execution.
- **#8's single insertion point** sits after the whole if/elif/else, so `opinions_not_included` is
  stamped on all four verdict paths (NO_VERDICT / APPROVE / PASS / fail-safe).
- **D3 has no inversion at the finalisation point** — `_final_state` (`room_runner.py:1575`) only
  maps `LIVE → WITHHELD_PAID` when unentitled; `WITHHELD_TENURE` passes through untouched.
- **D4 symmetry is preserved by non-modification** — CR098 gates News/Social *upstream* in
  `_resolve_and_charge_feeds`; `_profile_for_ticker`'s news/social branches are untouched and
  `profile["news_state"]/["social_state"]` are set unconditionally from the feed. Proved the old
  patch-based tests are **not** vacuous: disabling the social overlay turned
  `test_profile_overlays_live_sentiment_when_enabled` red (the exact test CR090's asymmetry
  silently voided), plus 2 parity tests.
- **#6 asserts on rendered output**, not fetch counts — the tests poison the profile with
  `"SHOULD NOT APPEAR"` / `rsi: 999` and assert against `_format_profile`'s string. Correct.

### MAJOR 1 — `agent_withheld` never reaches the wire

`backend/app/api/room.py`'s SSE dispatcher is an explicit if/elif over exactly seven kinds —
`started`, `live_data_notice`, `phase`, `agent_token`, `agent_done`, `verdict`, `error` — with
**no `agent_withheld` branch and no `else`**. The event the runner emits at `room_runner.py:1988`
is silently dropped at the API boundary and never becomes an SSE frame. Grep across the worktree:
`agent_withheld` appears in exactly three places in backend source, **all inside
`room_runner.py`**, and zero times under `app/api/`.

So the three `RoomEvent` fields added expressly for the client countdown (`reason`,
`next_step_agent`, `next_step_days`) are unreachable from outside the process, and the entire FOMO
surface has no wire format at all.

**This corrects the hand-off's framing.** It states CR090-MOBILE's switch has a logging `default:`
"so it will not crash on the unknown value — it will render nothing." That presumes the value
reaches the client. It does not. Scope item 8 is not blocked on UI work — it has nothing to
consume. CR090's own `live_data_notice` **is** wired in this same file (`room.py:225`), so the
pattern was established one CR earlier and one branch was missed here.

Partial mitigation: the closing disclosure does survive — `Verdict.opinions_not_included` rides
`ev.verdict.model_dump_json()` on the `verdict` event. The verdict-level disclosure works; the
per-analyst locked chair and countdown do not.

This is the DEF038 / DEF063 / CR100 shipped-but-dark class, and it is inside this lane's own
backend scope (item 3, "phase-loop filter + `agent_withheld` event"), not the out-of-scope mobile
half. Fix is one `elif` branch.

### MAJOR 2 — nothing tests the defining behaviour: that a withheld analyst does not run

Two mutations, each run against the **full** suite, not just the CR098 file:

| Mutation | Full suite |
|---|---|
| `phase_agents = tuple(a for a in phase.agents if a not in ctx.withheld)` → `phase_agents = phase.agents` — the withheld analyst **speaks anyway** | **1359 passed** |
| `zip(phase_agents, results)` → `zip(phase.agents, results)` — each analyst's text attributed to the **wrong agent** | **1359 passed** |

Both are undetected. The first makes the app emit `agent_withheld` for an analyst that then speaks
in the transcript and appears in `opinions_not_included` — directly self-contradicting output, and
the withheld analyst's decode is billed to the operator. The second is silent misattribution.

All 21 new tests assert *around* the mechanism — the fetch is skipped, the event is emitted, the
verdict lists it — and none asserts the withheld analyst's voice is **absent from the transcript**.
That is the CR's defining behaviour.

This is not hypothetical exposure. `phase_agents` has three separate uses (the `asyncio.gather`
comprehension, the emit-order `zip`, the sequential loop) sitting inside CR077's parallel/sequential
branch split, and this exact seam is about to be rebased under DEF116. A merge that drops one of
the three restores full-roster behaviour — or misattribution — with a green suite.

Fix is small: assert no `agent_token`/`agent_done` event carries a withheld `agent_id`, and that
each analyst's text lands under its own id.

### MINOR 1 — the respawn path resolves the roster but not the feeds

`_respawn_run_from_row` (production — wired at `main.py:132` via `resume_pending_retries`) calls
`run()` with no `roster`, `news_feed` or `social_feed`. `run()` resolves the roster fresh, so
analysts *are* filtered and `NO_VERDICT` can fire — but the feed fallback resolves news/social at
`entitled=True` **ungated by that roster**. A withheld News/Social analyst's real data is then
fetched and rendered in the fact sheet, and `live_data_notice` reports `news: "live"` for an
analyst that was withheld. Market is gated correctly (it reads `withheld` directly), so the path
is internally asymmetric — the D4 concern one layer up. Zero users affected today (thresholds ship
at 0). Fix: gate the two fallbacks the same way `_resolve_and_charge_feeds` does.

*(Checked and cleared: `credit_cost=None` on this path is guarded at `room_runner.py:1807`.)*

### MINOR 2 — acceptance #2's own test does not test acceptance #2

**Answering the hand-off's question directly: the "practical form" is not equivalent, and it is
weaker in exactly the dimension the criterion names.** `test_default_roster_is_full_no_op` runs
with `user_id=uuid4()` — a **nonexistent** user, which takes `resolve_roster_for_user`'s
missing-row full-roster fallback. It therefore never exercises the real no-op case (an aged
`FLOOR_PASS` user with all three thresholds at 0), never captures a transcript, and never compares
against a pre-CR098 baseline.

Measured: the realistic off-by-one that breaks the no-op guarantee — `threshold >= 1 and
account_age_days >= threshold` → `account_age_days >= threshold`, making 0 mean *always* instead of
*never* — is caught **only** by `test_aged_floor_pass_social_withheld_debited_strictly_less`, the
D2 **money** test. The guarantee D5 called "the acceptance that matters most" survives incidentally,
through a test written for something else.

### MINOR 3 — the fact-sheet disclosure header still describes stripped fields

Rendered a Market-withheld profile: the header still carries *"RSI, trend, volume,
support/breakout: alpha simulation scaffolding — NOT computed from real price history"*
immediately above *"Market technicals: not included in this session."* Same shape for Social. Low
impact (prompt copy, not user copy) but it is contradictory text fed to every agent, and CR038's
own finding is that inconsistent prompt copy degrades compliance.

### FLAGS

1. **D6 integration hazard — measured, and worse-shaped than D6 describes.** Trial-merged DEF116
   (`d68a028`) into this SHA. Git **auto-merged DEF116's hoisted call without CR098's `withheld=`
   kwarg** (no conflict marker there at all) and raised a conflict only inside the
   `_RoomContext(...)` kwargs. Taking HEAD re-opens the blocking call — DEF116's AST guard catches
   that, as D6 says. Taking DEF116's side silently **drops `withheld=`**, disabling the Market
   fact-sheet strip — and that direction is caught by **nothing**, because CR098's tests call
   `_profile_for_ticker` and `_format_profile` directly rather than through `run()`. The correct
   resolution is a single call carrying both:
   ```python
   profile = await asyncio.to_thread(
       _profile_for_ticker, ticker, news_feed=news_feed, social_feed=social_feed,
       withheld=frozenset(roster.withheld),
   )
   ```
2. **DEF098 parity blind spot — measured, confirming the coder's flag.** With Market withheld the
   synthetic `rsi` is still *produced* in the profile dict (58 in my probe) and no longer
   *rendered*. DEF098's "every produced field is rendered or declared" guard would flag that if it
   ever ran against a withheld profile; no test constructs one. Real, quantified, and correctly
   left untouched by this lane.
3. **The fixed-copy `NO_VERDICT` simplification — no pushback, I agree.** Structural beats
   prompt-dependent (CR038's ~70% non-compliance) and it satisfies #10/#11 by construction. The
   honest cost — identical wording every time — is acceptable for a rare wall state.
4. **Trader + Risk still burn ~25s producing nothing actionable** at the NO_VERDICT step —
   built per the spec's recommendation. Saiful's call, Phase C.

### Not verified

- **Acceptance #14 live smoke** — untestable from a pure-editor Mac. Post-promote.
- **Not merged onto current `main`** — I measured only the DEF116 seam (FLAG 1), not a full
  integration.

### Findings

1. **MAJOR** — `agent_withheld` is emitted by the runner but has no branch in `room.py`'s SSE
   dispatcher, so it never reaches the wire; the countdown fields are unreachable. Shipped-dark.
2. **MAJOR** — no test asserts a withheld analyst is absent from the transcript. Removing the
   phase filter, and mismatching the emit-order `zip`, each leave the **full suite at 1359 passed**.
3. **MINOR** — the production respawn path resolves the roster but leaves the News/Social feed
   fallback ungated by it.
4. **MINOR** — acceptance #2's test uses a nonexistent user and never exercises the real no-op
   path; the guarantee is held only incidentally by the D2 money test.
5. **MINOR** — the fact-sheet disclosure header still describes fields the withhold stripped.

### Verdict

**VERDICT: AWAITING_FIXES (round 2)** — two MAJOR, three MINOR.

The mechanism itself is well built. The resolver, the money path, the fourth `LiveDataState`, the
`NO_VERDICT` short-circuit and the fact-sheet stripping all survive mutation, and D4's symmetry is
preserved in the strongest possible way — by not touching the seam. Both MAJORs are about the
edges: the disclosure that never leaves the process, and the one behaviour the test file walks all
the way around without ever asserting. Both fixes are small.

Run report: [`../runs/2026-07-27_run-65/run_report.md`](../runs/2026-07-27_run-65/run_report.md)
