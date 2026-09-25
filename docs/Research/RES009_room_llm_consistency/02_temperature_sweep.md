# 02 — Temperature sweep, 0.2 → 1.0

## Method

`backend/scripts/ibm_temperature_sweep.py` takes both original runs' captured
(`system_prompt`, `messages`) verbatim and re-sends each, once per temperature step
{0.2, 0.4, 0.6, 0.8, 1.0}, to the live vLLM endpoint directly
(`http://192.168.20.74:8000/v1/chat/completions`) — explicitly setting `temperature`
in the request body, which production never does. One completion per temperature
per run (not a repeat cascade yet — that comes later, see
[04](04_vllm_run_a_temperature_cascade.md)). Run against `fundamentals_analyst` and
`portfolio_manager`. Full output:
[`out/02_temperature_sweep_0.2_to_1.0.json`](out/02_temperature_sweep_0.2_to_1.0.json).

## fundamentals_analyst

| | Run A | Run B |
|---|---|---|
| original stance | FOR | NEUTRAL |
| T=0.2 | NEUTRAL | NEUTRAL |
| T=0.4 | NEUTRAL | NEUTRAL |
| T=0.6 | NEUTRAL | NEUTRAL |
| T=0.8 | NEUTRAL | NEUTRAL |
| T=1.0 | FOR | NEUTRAL |

Run B is stable across every temperature tested at n=1. Run A's original response
(FOR) does not reproduce at any temperature below 1.0 — it reappears only at the
highest setting.

## portfolio_manager (the actual verdict call)

All 10 completions across both runs and all 5 temperatures agreed on
`action: PASS` — the verdict itself did not move. What did move was the **output
format**: at higher temperatures, responses drifted from the clean JSON schema
into plain prose ("Verdict: PASS Reasoning: …") or markdown-fenced pseudo-JSON with
renamed fields ("Verdict" capitalized, "Mandate compliance" as a key that does not
exist in the real schema). This is the same class of parsing fragility
[CR210](../../forward_planning/CR210_room_audit/) and
[DEF058](../../defect/def_list.md) track — this sweep ties it directly to
temperature for the first time, rather than inferring it from aggregate
`room_pm_reformat` counts.

## Read

- The verdict layer (`portfolio_manager`) is robust to temperature *in content*
  (`action` never moved) across this small sample, but its output *format*
  degrades as temperature rises — a live, concrete demonstration of exactly the
  failure mode CR210's `room_pm_reformat` fallback exists to catch.
- The analyst layer (`fundamentals_analyst`) is not robust to temperature in
  content — Run A's stance is temperature-dependent, at n=1 per point. The next
  document repeats each point 10x to see whether that single-draw picture holds up.
