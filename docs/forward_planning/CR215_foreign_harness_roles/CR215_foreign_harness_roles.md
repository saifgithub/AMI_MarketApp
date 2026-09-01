# CR215 — Foreign harness roles: Qwen3.8 codes, Kimi k3 audits

**Status:** done · **Owner:** Architect · **Filed:** 2026-09-01 · **Tag:** `(AT:R75 CR215)`

Closes the half of MHBP that CR057 deferred: a **non-Claude auditor**, for correlated-error
decorrelation. Protocol: [`orchestration/audit/FOREIGN_AUDIT.md`](../../../orchestration/audit/FOREIGN_AUDIT.md).

## Why

CR057 reconciled our orchestration against Saiful's heritage DeliveryOS designs, adopted MHBP's
watcher invariants, and wrote down what it was leaving behind:

> **Foreign-harness auditor** (MHBP: agy/Gemini, non-Claude, for correlated-error decorrelation). Our
> `auditor.core` is same-family Claude today. Future upgrade.

Every build and every audit since has been Claude checking Claude. That gate is structurally unable
to see a **correlated error** — a defect the builder and the auditor both miss *because they share a
model family*. Rigour inside one family does not fix it.

## What shipped

| Role | Model | Family | Config home |
|---|---|---|---|
| Coder (`TIER=local`) | `ami-vllm/qwen3.8-flash-next` | Alibaba | `~/.kimi-code-ami-coder` |
| Foreign auditor | `kimi-code/k3` | Moonshot | `~/.kimi-code` (OAuth) |
| Architect / gate | Claude | Anthropic | — |

Three families, no shared parent — a step beyond MHBP itself, which decorrelates only the audit.

- **`orchestration/harness/ami_vllm_api.json`** — the on-prem vLLM as a models.dev-shaped provider
  registry, in-repo. DEF387 last week was *"version-control the supervisors — the guard's other half
  lived on one disk"*; a provider that exists only in an untracked `~/.kimi-code/config.toml` is that
  same defect.
- **`orchestration/harness/register_ami_vllm.sh`** — imports it into a **dedicated** `KIMI_CODE_HOME`.
  Asserts `root == /models/qwen38-flash-next-nvfp4` from `/v1/models` before writing anything, because
  the `ami-llm` alias was reused across the CR211 swap and names different weights before and after.
- **`orchestration/harness/run_timeout.py`** — wall-clock watchdog. macOS ships no coreutils
  `timeout`, and `kimi -p` does not reliably exit once the model has stopped working.
- **`orchestration/audit/dispatch_foreign_audit.sh`** — the auditor launcher.
- **`orchestration/audit/foreign/AUDITOR_AGENT.md`** — Kimi's role file.
- **`TIER=local`** in `dispatch_launch.sh`, below `economy` on CR057's ladder.
- **`orchestration/audit/foreign_trail.md`** — MHBP §9/§10 pre-registration ledger, N≥5 before any
  kept/killed call.

## Design decisions

**A harness, not a curl (MHBP §1.2, not §1.3).** §1.3 has the architect write the foreign finding on
a tool-less model's behalf. That collides head-on with `ARCHITECT_LOOP_PROMPT.md:137-142` — *"The
auditor writes and pushes its own verdict. You never transcribe it… an inconvenient verdict is one
edit away from never existing."* Kimi Code reads the diff itself and commits its own file, so nothing
passes through the architect's hands.

**Advisory, never binding** (MHBP invariant 2). Three independent structural barriers, plus a
post-hoc check, because *prompt instructions are not controls*:

1. different token — `FOREIGN-VERDICT:`, which no watcher parses;
2. different file — `audit/foreign/`, which `dispatch.sh` does not read;
3. different branch — `foreign/<ITEM>.r<N>`, which never reaches `main`;
4. the launcher greps the produced file with the board's own regex and quarantines a violation.

New failure-pattern **P31** records the class. Its enforcing check pins the launcher's quarantine
regex to `dispatch.sh`'s `TOK` verbatim, so widening one without the other fails the build.

**Separate config homes.** `[thinking] effort` is a **global** key that overrides per-model
`default_effort`. One shared config would mean each role mutating a flag the other reads — the
shared-mutable-flag race CLAUDE.md forbids.

**`local` is a build tier only.** The launcher refuses it for an auditor-shaped instance id.
BINDINGS.md:73 *"Never economy tier for an auditor"*; DEF059 is what a gate that can fail open costs.

## Verified live (not assumed)

| Check | Result |
|---|---|
| `kimi --version` | 0.39.1 — the build MHBP §11 pins. At `~/.kimi-code/bin`, not on the default non-interactive PATH. |
| `kimi provider list` | `managed:kimi-code source=oauth`, default `kimi-code/k3`. No API key to move off melehost. |
| Registry import | `kimi provider add` needs an HTTP URL (rejects `file://`) and a `type` field models.dev lacks; `type: "openai"` is the accepted value. |
| vLLM `/v1/models` | `root=/models/qwen38-flash-next-nvfp4`, 262144 ctx |
| vLLM tool-calling | works — `finish_reason: tool_calls` with a well-formed call. Qwen can drive an agentic loop. |
| Coder round-trip | `register_ami_vllm.sh` green from a clean state |
| Permissions | `kimi -p` rejects both `--auto` and `--yolo`, and uses tools under default permissions anyway — **no auto-approve escalation was needed**. |
| GLM `100.94.223.38:8008` | unreachable — MHBP §6's two-local-family design does not port |

## The first run caught a real defect (N=1)

`dispatch_foreign_audit.sh DEF389 94a86e77 1` returned `ADVISORY-CONCERNS`, 4 findings, of which the
`blocking` one verified as **real** and filed as **DEF391**:

DEF389 fixed two PM-path exception handlers and described them as *"both log sites"*. There are
**three**. `room_pm_reformat_failed` kept `str(exc)[:200]`, so a bare `httpx.ReadTimeout` — whose
`str()` is empty — still logged `error=""` into the same DEF059 fail-safe PASS. And the enforcing pin
asserted `count(...) == 2`, which does not merely miss the third site but **locks it out**: fixing it
would have failed the test.

The builder wrote "both", the Claude auditor accepted "both", the enforcing check pinned "both". A
different model family counted three. That is precisely the defect class this CR exists to catch, and
it appeared on the first run.

## Definition of Done

| Row | Disposition |
|---|---|
| **Scope** | Matches §What shipped: registry + registration, watchdog, auditor launcher + role file, `TIER=local`, protocol doc, ledger, bindings gap-fill 9, auditor-loop step, P31. All present. |
| **Enforcing check** | `backend/tests/unit/test_cr215_foreign_harness_guard.py` — 9 pins incl. board-regex parity. Green. |
| **Degrade loudly** | `FOREIGN: unavailable` ledger row + exit 3 on every precondition failure; `TIER=local UNAVAILABLE` when the coder home is unregistered. No silent fallback to a Claude model. |
| **Live proof** | N=1 run on `94a86e77` produced a verified real catch (DEF391), mutation-proved. |
| **Model/effort/budget** | auditor `kimi-code/k3` (flat-rate subscription); coder `qwen3.8-flash-next` (free, local GPU); Claude tiers unchanged and pinned by test. |
| **Regression risk** | The three Claude tiers are byte-identical and pinned; the foreign path is additive and cannot reach `main` or the board. |

## Not in scope

- `agy`/Gemini as a third family (installed at `~/.local/bin/agy`, unused).
- GLM-5.3-Flash — unreachable.
- MHBP §7's black-box Tester loop, §4's ultracode workflow, the `HarnessProfile` registry.
- Promoting `TIER=local` above Tier C work, or near the auditor role.
- The stale `:8000` / `ami-llm` defaults in `.env.example`, `infra/alpha.env.example`,
  `infra/systemd/ami-trade.env.example`, `scripts/translate_arb_lan.py:28`,
  `backend/scripts/backtest_cutoff_probe.py:35` — same poisoned-alias hazard, separate cleanup.
