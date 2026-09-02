"""Pull the two self-report sections out of any convene, per agent.

The convene driver appends an addendum asking each agent (a) what data it lacked
and (b) where its own prompt contradicted itself, quoting both sides. Those two
sections are the finding; this pulls them out.

usage: extract_reports.py <convene.json> [contradictions|gaps|both]
"""
import json, re, sys

path = sys.argv[1]
which = sys.argv[2] if len(sys.argv) > 2 else "both"
d = json.load(open(path))
print(f"# {d.get('ticker')}  horizon={d.get('horizon','long')}  goal={d.get('goal','long_term_wealth')}"
      f"  model={d.get('model')}\n")

for t in d["turns"]:
    if "answer" not in t:
        print(f"## {t['agent']}  -- ERROR: {t.get('error','?')}\n"); continue
    out = []
    if which in ("gaps", "both"):
        m = re.search(r'DATA I LACKED:(.*?)(?=PROMPT CONTRADICTIONS:|$)', t["answer"], re.S)
        out.append("DATA I LACKED:\n" + (m.group(1).strip() if m else "(section missing)"))
    if which in ("contradictions", "both"):
        m = re.search(r'PROMPT CONTRADICTIONS:(.*)$', t["answer"], re.S)
        out.append("PROMPT CONTRADICTIONS:\n" + (m.group(1).strip() if m else "(section missing)"))
    print(f"## {t['agent']}  ({t['phase']}, {t['elapsed_s']}s, {t['tok_think']} thinking tokens)\n")
    print("\n\n".join(out) + "\n")
