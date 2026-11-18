# CR269 — Pin LLM sampling (temperature) in config

**What:** Explicit desk and judge temperature settings, applied in the gateway request body for every provider and in the research harness. No temperature is sent today, so desks run at the server default (usually 1.0). S11 plan §2 WP-11.

**Why:** CR267 Beta programme; design approved by Saiful at gate S11 on 2026-11-18 (`CR267_beta_programme/S11_llm_implementation_plan.md`, §2 and §3a). Filed as a child CR of CR267.

**Scope and acceptance:** see the S11 plan section named above and CR267 §6. Built on branch `beta/cr267` by a Sonnet worker; accepted on the git diff plus test exit codes.
