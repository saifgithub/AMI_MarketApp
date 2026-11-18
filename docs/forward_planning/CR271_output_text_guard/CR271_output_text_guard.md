# CR271 — Deterministic output text guard on user-visible agent text

**What:** Personal-advice phrasing and abusive-language rules, enforcing after a log-only phase measured by replaying llm_audit, plus an is-this-about-markets heuristic that only ever logs. Room hits take the scripted-fallback path; 1-on-1 and Brief replies are withheld with a labelled message. S11 plan §2 WP-13 and §3a.4.

**Why:** CR267 Beta programme; design approved by Saiful at gate S11 on 2026-11-18 (`CR267_beta_programme/S11_llm_implementation_plan.md`, §2 and §3a). Filed as a child CR of CR267.

**Scope and acceptance:** see the S11 plan section named above and CR267 §6. Built on branch `beta/cr267` by a Sonnet worker; accepted on the git diff plus test exit codes.
