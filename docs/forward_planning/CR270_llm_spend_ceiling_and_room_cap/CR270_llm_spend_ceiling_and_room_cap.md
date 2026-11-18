# CR270 — LLM model identity, cost, daily spend ceiling, one Room per user

**What:** A model column on llm_audit (served root, never the alias), cost from tokens times a per-model price table, a daily UTC spend ceiling ($10 Beta / $5 Alpha) that degrades new requests to an honest unavailable state while running Rooms finish, and one Room in flight per user across tickers. S11 plan §2 WP-12.

**Why:** CR267 Beta programme; design approved by Saiful at gate S11 on 2026-11-18 (`CR267_beta_programme/S11_llm_implementation_plan.md`, §2 and §3a). Filed as a child CR of CR267.

**Scope and acceptance:** see the S11 plan section named above and CR267 §6. Built on branch `beta/cr267` by a Sonnet worker; accepted on the git diff plus test exit codes.
