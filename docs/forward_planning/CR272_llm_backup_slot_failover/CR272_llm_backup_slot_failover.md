# CR272 — LLM provider slot kind, backup slot and automatic failover

**What:** A slot kind (vllm or openai) so a hosted endpoint gets no vLLM-only fields; a backup slot; retry 3 times then restart the whole Room on the backup with a visible label; both down gives an unavailable state and a refund. Alpha: on-prem primary, DeepInfra backup. Beta: hosted primary and backup. S11 plan §2 WP-14 and §3a.

**Why:** CR267 Beta programme; design approved by Saiful at gate S11 on 2026-11-18 (`CR267_beta_programme/S11_llm_implementation_plan.md`, §2 and §3a). Filed as a child CR of CR267.

**Scope and acceptance:** see the S11 plan section named above and CR267 §6. Built on branch `beta/cr267` by a Sonnet worker; accepted on the git diff plus test exit codes.
