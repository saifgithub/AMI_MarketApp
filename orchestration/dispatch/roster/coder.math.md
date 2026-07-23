<!-- roster entry — binds a role to a spec + addressing. Architect-owned. CR052. -->
# coder.math

```
role: coder
spec: trading math library (CR046 standing ledger)
kind: code
owns: backend/app/trading_math/** (indicators, risk, sizing — pure, no I/O), the CR046 M-ledger,
       backend/tests/unit/test_trading_math*.py
wip_cap: 2
auditor: per-lane GATE  # CR070 dropped the standing auditor.core; the lane's GATE: names its gate
live_handle: 69560e3e-1ef0-4928-b2fb-5e024398425d   # last: CR054-W0d (DONE) — claude --resume
commit_tag: AT:coder.math
worktree: .claude/worktrees/coder.math-<ITEM>
active_lanes: []   # CR054-W0d integrated 2026-07-22; idle
```

**Pure library** — zero cross-service imports; does not touch `db/models.py` or any I/O. Owns the
CR046 policy: any agent-presented number that can be computed deterministically is computed here and
injected (the LLM never does the arithmetic), each calc ledgered M01… with its guard test. Consumers
(`coder.room`, `coder.api`) import it; keep function signatures stable.
