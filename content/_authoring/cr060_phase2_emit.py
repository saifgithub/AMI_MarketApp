"""Emit the CR060 Phase 2 classification document from the merged classifier output.

Reads cr060_phase2_merged.json (+ the re-triage overlay, if present) and writes the
P1 / P2a / P2b / P2c / ESCALATE tables that Phase 3 works from. Kept as a script
rather than hand-written markdown so the tables can be regenerated when a batch is
re-run — three of the classification batches had to be re-run at a smaller size, and
hand-merging 273 rows across four runs is exactly where a silent drop happens.
"""
import json
import pathlib
import re
from collections import Counter

HERE = pathlib.Path(__file__).parent
MERGED = HERE / "cr060_phase2_merged.json"
RETRIAGE = HERE / "cr060_retriage_results.json"

KEEPS_KEY = re.compile(r"answer stays|key stays|keys? unchanged|stays answer", re.I)
NEEDS_SRC = re.compile(r"needs sourcing", re.I)


def load():
    rows = {x["id"]: x for x in json.loads(MERGED.read_text())}
    if RETRIAGE.exists():
        for r in json.loads(RETRIAGE.read_text()):
            if r["id"] in rows:
                rows[r["id"]]["bucket"] = r["final_bucket"]
                rows[r["id"]]["retriage_why"] = r["why"]
                rows[r["id"]]["genericizable"] = r["genericizable"]
    return list(rows.values())


def cost(x):
    """What applying this fix actually costs — the number that decides sequencing."""
    if NEEDS_SRC.search(x["exact_change"]):
        return "source"
    if KEEPS_KEY.search(x["exact_change"]):
        return "rename"
    return "rewrite"


def table(rows, cols, get):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        cells = [str(c).replace("|", "\\|").replace("\n", " ") for c in get(r)]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def main():
    rows = load()
    by = lambda b: sorted([x for x in rows if x["bucket"] == b], key=lambda x: x["code"])
    p1, p2a, p2b, p2c, esc = by("P1"), by("P2a"), by("P2b"), by("P2c"), by("ESCALATE")
    costs = Counter(cost(x) for x in p1)

    print(f"rows={len(rows)}  P1={len(p1)} P2a={len(p2a)} P2b={len(p2b)} P2c={len(p2c)} ESC={len(esc)}")
    print(f"P1 quiz_affected={sum(1 for x in p1 if x['quiz_affected'])}")
    print(f"P1 fix cost: {dict(costs)}")

    doc = []
    doc.append(table(p1, ["Code", "Lesson", "Trigger", "Quiz", "Cost", "Defect", "Exact change"],
                     lambda x: (x["code"], f"`{x['id']}`", x["p1_trigger"],
                                "**yes**" if x["quiz_affected"] else "no", cost(x),
                                x["defect_summary"], x["exact_change"])))
    doc.append("")
    doc.append(table(p2a, ["Code", "Lesson", "Defect", "Genericize to"],
                     lambda x: (x["code"], f"`{x['id']}`", x["defect_summary"], x["exact_change"])))
    doc.append("")
    doc.append(table(p2b, ["Code", "Lesson", "Uncorroborable claim", "Soften / cut"],
                     lambda x: (x["code"], f"`{x['id']}`", x["defect_summary"], x["exact_change"])))
    if p2c:
        doc.append("")
        doc.append(table(p2c, ["Code", "Lesson", "Why real data is the skill", "Regenerate"],
                         lambda x: (x["code"], f"`{x['id']}`", x["defect_summary"], x["exact_change"])))
    if esc:
        doc.append("")
        doc.append(table(esc, ["Code", "Lesson", "Why it escalates"],
                         lambda x: (x["code"], f"`{x['id']}`", x["defect_summary"])))

    (HERE / "cr060_phase2_tables.md").write_text("\n".join(doc))

    # Section headings carry the counts, so they are derived from the SAME rows that
    # build the tables. Computing them from a separately-loaded copy is how the first
    # draft ended up claiming 180 P1 above a table of 149 — the summary had been built
    # before the re-triage overlay was applied.
    counts = {"P1": len(p1), "P2a": len(p2a), "P2b": len(p2b), "P2c": len(p2c), "ESCALATE": len(esc),
              "quiz": sum(1 for x in p1 if x["quiz_affected"]),
              "quiz_poisoned": sum(1 for x in p1 if x["p1_trigger"] == "quiz_poisoned"),
              "false_fact": sum(1 for x in p1 if x["p1_trigger"] == "false_fact"),
              **{k: v for k, v in costs.items()}}
    (HERE / "cr060_phase2_counts.json").write_text(json.dumps(counts, indent=1))
    print("wrote cr060_phase2_tables.md + cr060_phase2_counts.json", counts)


if __name__ == "__main__":
    main()
