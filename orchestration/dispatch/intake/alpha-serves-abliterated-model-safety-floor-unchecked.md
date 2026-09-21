# Intake — Alpha serves a refusal-stripped (abliterated) model; the safety floor has never been run against it

**Handle:** `alpha-serves-abliterated-model-safety-floor-unchecked` (pre-triage; no
`DEF###` minted — the Architect is the single ID-minter).
**Found:** 2026-09-21 (daily check-in). **Saiful, same day:** confirmed the swap is
**intentional** — *"Intentional — record it + check safety floor"*. Recording is done
(`CLAUDE.md` runtime table). The safety-floor check is what this stub asks the Architect
to mint and lane.

## What was measured (2026-09-21)

- `curl http://192.168.20.74:8000/v1/models` → both ids (`ami-llm`,
  `qwen3.8-flash-next-abliterated`) carry `root=/models/qwen38-flash-next-abliterated-nvfp4`.
- melehost `~/ami_trade/.env` and the running `ami_api_alpha` container both carry
  `VLLM_BASE_URL=http://192.168.20.74:8000`. The container started 2026-09-17 19:09Z, one
  minute after `.env` was written (19:08Z) — the same evening as the DEF413 outage, when
  `:8048` stopped answering. `:8048` still refuses (curl exit 7) from the Mac and from
  melehost; the host pings.
- `git grep -i abliterated` over the repo: **zero hits** before this stub. The previously
  recorded serve was the non-abliterated `/models/qwen38-flash-next-nvfp4`.

Not measured: *when* the abliterated build began serving `:8000`, or whether any Alpha
traffic between 09-17 19:09Z and now was produced by it. Those need the vLLM host's own
logs.

## Why it matters (and why it is a check, not a rollback)

Saiful ruled it intentional, so this is not a request to revert. The exposure is that
CLAUDE.md's own rule — *"prompt instructions are not controls"*, agents ignoring emphatic
"never present this as real" ~70% of the time (CR038) — was measured on models that
**refuse**. A refusal-stripped build removes the base model's own refusals from every
prompt-only guard. What still holds is what is structural: the deterministic PM compliance
check and the four mandate toggles that are actually enforced (DEF061: 4 of 8 are
prompt-only).

## Ask

Run the existing safety-floor / compliance evidence against the abliterated build, keyed by
`root` (never by the `ami-llm` alias), and report per control whether it holds:

1. PM mandate enforcement (uncoachable floor) — Brief Your Agent attempts to coach past it.
2. The 4 prompt-only mandate toggles (DEF061) — expect these to degrade; quantify.
3. "Never present as real / simulation-only" copy discipline in agent output.
4. Any CR038-style hedging discipline (synthetic macro / catalyst asserted as fact).

Deliverable: a per-control table (holds / degrades / fails) with the model `root` in the
header, and a recommendation on which prompt-only controls need to become structural before
the Alpha cohort widens. GATE: independent (a control that holds "in the tests" is not the
question — the question is what a refusal-stripped model does when told to cross it).
