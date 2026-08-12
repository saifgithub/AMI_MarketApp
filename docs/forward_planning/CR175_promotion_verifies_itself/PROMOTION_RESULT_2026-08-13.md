# CR175 acceptance — the first promotion through the new pipeline

**Tag:** `alpha-2026-08-13-1` · **Commit:** `c539af12` · **Round:** AT:R68

Acceptance criterion 7 says the next real promotion runs end-to-end through the new
postflight and its output is recorded here, *"including whatever it finds, which on the
evidence above is unlikely to be nothing."* It was not nothing.

---

## 1. What the gates did

| Gate | Result |
|---|---|
| Hold gate (`infra/PROMOTION_HOLD.md`) | clear |
| Audit lane (`dispatch.sh inbox`) | **exit 1** — `hot=0`, `dead=1`. Inbox genuinely clear; fired on a 12h-stale auditor heartbeat. See §5 |
| **Tree gate (new, Tier D)** | **exit 0** — 0 blocking, 27 shipped-not-runtime, recorded |
| `pytest backend/tests/unit/` | 3642 passed, 1 skipped, after fixing one drifted register table |
| `flutter analyze` | 8 infos, 0 errors |
| Manual gate | backend-only — verified by reading the one client call site, `api_client.dart:497`, which asserts `status == 'ok'` and never reads `version` |

The tree gate did the job it was built for on its first outing: the tree carried 27 dirty
paths (docs and research from three other lanes) and **none of them reach the container**,
so it passed silently instead of forcing the operator to adjudicate 27 lines. The old
`git status --short` would have printed all 27 with "must print nothing" above it.

## 2. What the promotion did

Migrations ran **before** the swap, against the live DB, with the old container still
serving — DEF215's ordering, exercised for real rather than asserted:

```
Running upgrade a109e000005d -> b109f000006e, CR109 Amendment I — the wipeout
Running upgrade b109f000006e -> c109g000007a, CR109 slice 4 — the field
```

Two migrations from another lane's work, applied cleanly, before anything swapped.

**DEF276's fix verified on a real `--delete` rsync**, not a dry run:

```
$ ssh melehost "ls ~/ami_trade/backtest_results/"
runs_r68-def230-n40.jsonl
runs_r68-postfix.jsonl
users.json
```

All three survived. Without the exclude added this session, that rsync would have
destroyed the 40-pair replay this session's DEF230 result rests on.

## 3. The deploy now identifies itself (F1, F2)

```json
GET /v1/health
{"status":"ok","version":"c539af121f5c7e97a2790507624e9446be034828",
 "alpha_tag":"alpha-2026-08-13-1","env":"staging"}
```

The field that read `"0.1.0"` on every deploy since the project began now reads the commit.

```json
GET /v1/ready   (admin bearer)
{"ready": true, "deploy_stamped": true, "failed_probes": [],
 "probes": [
   {"name":"db","ok":true,"gating":true},
   {"name":"schema","ok":true,"gating":true,
    "current_revision":"c109g000007a","head_revision":"c109g000007a"},
   {"name":"llm","ok":true,"gating":true,
    "active_provider":"vllm","has_real_provider":true},
   {"name":"redis","ok":true,"gating":false} ]}
```

## 4. What the postflight found — the part that matters

First live run: `identity`, `readiness`, `market` green; **`config` failed on six keys.**
All six were false positives, and both causes were bugs in the new tool:

1. **`SUPPRESS_ANALYST_CONSENSUS`** — reported as *"populated in alpha.env,
   `configured: false` in the container, this is the DEF038/DEF063 bug."* It is not. The
   env file carries `SUPPRESS_ANALYST_CONSENSUS=false` under its own comment *"CR035
   ablation toggle — benchmark windows only; keep false"*, the compose line is present at
   `docker-compose.yml:268`, and the container's value is `false`. For a `bool` field
   `configured` means *the feature is on*, not *the key exists*. Checked all three —
   `Settings` field, compose line, live container value — rather than filing a defect off
   the tool's word.
2. **Five keys reported as "not a Settings field"** — the three RevenueCat client SDK keys
   and the two website keys. Every one is already excused, with a written reason, in
   `test_config_compose_parity.py::_ENV_KEYS_WITHOUT_SETTINGS`. postflight was keeping its
   own shorter copy of that table.

**The second one is CR175 F3 committed by CR175's own fix.** A second hand-maintained
list, certain to drift, whose drift surfaces as a permanent false positive. Left in, both
bugs would have failed `config` on every promotion forever — a check whose failing state
is its normal state, which is exactly the F5 pathology this CR exists to remove.

Fixed: the excuse table is now **imported** from the one place that owns it, with a test
that breaks if the import path breaks rather than silently reverting to the short list;
falsey literals are treated as deliberate off-switches; and the *"is this a Settings
field"* direction is left to the static test that already asserts it at preflight, because
two verdicts on one question eventually disagree.

Two robustness bugs from the same run: an unhandled exception in one check took the other
four down behind a traceback, and the excuse-table import needed `backend/` on `sys.path`.
Both fixed; an unhandled exception now reports `COULD NOT RUN` (exit 2) and never becomes
a pass.

**Final state against the promotion:**

```
[v] identity   ok        running c539af12 == promoted c539af12, tag matches
[x] tree       FAILED    23 paths differ — see below
[v] readiness  ok
[v] config     ok
[v] market     ok
```

`tree` is correct and its failure is not the promotion's. `git diff --stat
alpha-2026-08-13-1..HEAD -- backend/` shows **12 files, 954 insertions** committed by the
games lane after the promotion landed, plus this session's own postflight edits. That is
the check answering the question it was asked — *does the box hold what this worktree
holds* — on a shared checkout that moved on. Its message now says how to tell the two
cases apart, which it did not on the first run.

## 5. What is still open

- **F7 — the audit-lane gate.** It exited 1 while printing *"inbox clear — no verdict
  awaiting integration, no submission of yours undelivered."* `hot=0`, `dead=1`: it fired
  entirely on a stale auditor heartbeat, a condition `dispatch.sh`'s own comment scopes to
  *"restart it before you **submit** anything else."* Saiful's call, taken 2026-08-13:
  **promote now, split the exit codes after.** Filed as **DEF277**; recorded here rather
  than left implicit, because a gate that was reasoned past should be written down as
  having been reasoned past.
- **A second promotion is not required** for the postflight fixes — `scripts/promotion/`
  runs on the Mac and never reaches the container. It is blocked anyway: `main` currently
  carries four red `test_cr109_slice4_rolling_starts.py` tests from another lane's
  in-flight work, and the preflight requires a green suite.
- `cr_list.md` needed regenerating **twice** in one evening, both times because the Learn
  lane committed `CR174.row.md` without the generated table (`30826dbd`, `6a775a1d`).
  Red `test_registers_no_drift.py` blocks *anyone's* promotion preflight, so this is worth
  one line to that lane rather than a third regenerate.

## 6. What this does not claim

That promotions are now incident-free. What is demonstrated is narrower and is the thing
that was actually missing: **the pipeline's checks can now fail, and on their first real
outing three of them did** — the tree gate cleanly passed 27 irrelevant dirty paths, the
tree check caught real drift, and the config check caught its own imprecision before it
could teach anyone to ignore it.
