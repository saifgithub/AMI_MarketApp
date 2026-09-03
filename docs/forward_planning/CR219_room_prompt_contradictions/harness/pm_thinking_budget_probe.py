"""Measure how many tokens the PM's REAL prompt spends on thinking, at a
deliberately generous ceiling, so the R48 B-arm budget is derived from this
agent's own behaviour rather than from the probe's toy prompt."""
import json, sys, os
sys.path.insert(0, os.path.abspath("docs/forward_planning/CR219_room_prompt_contradictions/harness"))
from _paths import bootstrap
bootstrap()
from vllm_client import VLLMClient

runs = [
    "docs/forward_planning/CR219_room_prompt_contradictions/harness/results/CAT_long/run.json",
    "docs/forward_planning/CR219_room_prompt_contradictions/harness/results/MSFT_long/run.json",
]
c = VLLMClient()
ROOT = "/Volumes/Extreme Pro/AMI_MarketApp/"
out = []
for rp in runs:
    r = json.load(open(ROOT + rp))
    t = [x for x in r["turns"] if x["agent"] == "portfolio_manager"][0]
    for i in range(3):
        d = c.chat(t["system_prompt"], t["user_message"], max_tokens=8000,
                   temperature=1.0, thinking=True)
        rec = {"ticker": r["ticker"], "i": i, "finish": d.get("finish"),
               "tok_prompt": d.get("tok_prompt"), "tok_out": d.get("tok_out"),
               "tok_reasoning": d.get("tok_reasoning"), "chars": len(d.get("answer") or ""),
               "err": d.get("error"), "elapsed": d.get("elapsed_s")}
        out.append(rec)
        print(json.dumps(rec), flush=True)
json.dump(out, open("/private/tmp/claude-501/-Volumes-Extreme-Pro-AMI-MarketApp/b01a16b8-4123-4011-b178-35deeeec515d/scratchpad/budget_probe.json", "w"), indent=1)
