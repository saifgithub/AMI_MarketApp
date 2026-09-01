# Foreign audit — the decorrelated tier (CR215)

Ported from Saiful's heritage **MHBP** design (`DeliveryOS/docs/MHBP_LAB.md`), which CR057 adopted
by halves: it took MHBP's watcher invariants and deferred the foreign auditor. This is that
deferred half.

## Why

Every audit this project has run was **Claude auditing Claude**. That gate is structurally unable to
catch a **correlated error** — a defect the builder and the auditor both miss *because they share a
model family*. No amount of rigour inside one family fixes it; the residual is only visible from
outside.

It is not hypothetical. The first run, on `94a86e77` (DEF389), found that the fix covered **two of
three** PM-path exception handlers. The commit message said "both log sites", the register row said
"both log sites", the Claude auditor accepted "both", and the enforcing test pinned
`count(...) == 2` — locking the gap in. A model from another family counted three.

## The roles

| Role | Model | Family | Home |
|---|---|---|---|
| Coder | `ami-vllm/qwen3.8-flash-next` | Alibaba | `~/.kimi-code-ami-coder` |
| Foreign auditor | `kimi-code/k3` | Moonshot | `~/.kimi-code` (OAuth) |
| Architect / gate | Claude | Anthropic | — |

Separate `KIMI_CODE_HOME`s on purpose. `[thinking] effort` is a **global** key in `config.toml` that
overrides any per-model `default_effort`, so one shared config would mean each role mutating a flag
the other reads — the shared-mutable-flag race CLAUDE.md forbids. Disjoint paths instead.

## Invariants (MHBP's six, against our reality)

1. **Decorrelation is the model family, not the tool.** An audit run on a Claude model is **void** —
   same family again, regardless of which harness ran it. `dispatch_foreign_audit.sh` asserts the
   resolved model is `kimi-code/*` and refuses otherwise. Giving the foreign tool full project
   context does *not* void a run: decorrelation comes from whose model reads the artifact.
2. **The mechanical floor stays binding; the foreign signal is advisory.** MHBP's floor is
   `npm run gate`; ours is `pytest backend/tests/unit/ -q` plus the Claude auditor's `VERDICT:`.
   The foreign tier is *additive insurance, never a replacement verifier.* See **Why it cannot move
   the gate** below.
3. **Serial.** MHBP's "one chunk in flight" is vacuous here — we have no chunks and build
   sequentially.
4. **A watcher per role.** Not needed: the harness runs synchronously under the launcher, which
   verifies the result in the same turn. (MHBP scopes invariant 4 to *separate-harness* legs with an
   asynchronous semaphore handoff; ours has neither.)
5. **Read-only / isolated.** The foreign auditor runs in a throwaway worktree on a throwaway branch
   pinned to the audited SHA. MHBP invariant 5 exists because an unscoped foreign harness silently
   edited 4 files in its first run; here the launcher machine-verifies the branch touched exactly one
   path and quarantines it otherwise.
6. **Independent verification + pre-registration.** Findings carry a verbatim `file:line` quote. Runs
   are logged in `foreign_trail.md`, and **N ≥ 5** before any kept/killed call.

## Why it cannot move the gate

Three independent barriers, because the thing writing the file is a model we neither control nor
trained, and *"prompt instructions are not controls"* (CR038: agents ignore even emphatic
instructions ~70% of the time):

1. **Different token.** It emits `FOREIGN-VERDICT:`, which no watcher parses.
2. **Different file.** `dispatch.sh` derives lane state from `orchestration/audit/cr/<ITEM>.auditor.md`;
   foreign output lives in `orchestration/audit/foreign/`, which nothing reads.
3. **Different branch.** `foreign/<ITEM>.r<N>` never reaches `main`.

Barrier 1 is additionally enforced *after* the run — the launcher greps the produced file with the
board's own regex and quarantines a violation — and `test_cr215_foreign_harness_guard.py` pins that
regex to `dispatch.sh`'s `TOK` so the two cannot drift apart.

## Running one

```sh
sh orchestration/audit/dispatch_foreign_audit.sh <ITEM> <sha> <round> "<lane-specific criteria>"
```

Automatic on **Tier A** (AMI_TRADE_BINDINGS.md gap-fill 8 — auth/crypto/secrets, credits/billing,
row-altering migrations, compliance perimeter, live infra, sourced figures); by hand elsewhere.
Exit `3` means the tier was **unavailable**, recorded in the ledger. That is a real observation, not
a gap: absence of foreign findings must never read as the foreign auditor having been satisfied
(DEF059).

## Dispositioning — the Claude auditor's duty

Read the findings with `git show foreign/<ITEM>.r<N>:orchestration/audit/foreign/<ITEM>.r<N>.foreign.md`.
**Never transcribe them** — reading from the committed branch is what keeps an inconvenient finding
from being one edit away from never existing (ARCHITECT_LOOP_PROMPT.md:137-142).

Classify **every** finding in your own lane file:

- **real** — a genuine defect. If the all-Claude review missed it, it is a **correlated-error catch**,
  the headline metric.
- **false-divergence** — a real divergence, but model-quirk or stylistic preference rather than a
  substantive defect.
- **noise** — a false alarm.

Then amend the ledger row with the counts. A foreign tier that produces `noise` at a rate that drowns
the signal is a tool to demote, not evidence that decorrelation fails (MHBP §9(h)); those are separable
only if the rates are recorded per tool.

## Known gaps

- **One family per role.** MHBP §6 wants two local families cross-checking high-blast-radius work.
  GLM-5.3-Flash (`100.94.223.38:8008`) is unreachable from here, so there is no second lens.
- **`agy`/Gemini is installed** (`~/.local/bin/agy`) and unused. A third family is available whenever
  the ledger says the second one earns its keep.
