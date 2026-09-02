"""Re-score a banked run.json without touching the LLM.

    backend/.venv/bin/python <harness>/score_only.py <harness>/results/CAT_long/run.json

Exists because a scorer changes more often than a run does. Every run banks the
full prompts and answers, so a corrected or added scorer can be applied to every
run already on disk — for free, and without the arms drifting apart because one
was scored by an older version. `--write` updates the file's `scores` block in
place; without it the scores only print.
"""
import argparse
import json
import sys

from _paths import bootstrap

bootstrap()

from score import score_run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_json", nargs="+")
    ap.add_argument("--write", action="store_true", help="update `scores` in place")
    ap.add_argument("--brief", action="store_true", help="drop the per-agent detail")
    args = ap.parse_args()

    for path in args.run_json:
        with open(path) as fh:
            run = json.load(fh)
        scores = score_run(run)
        if args.write:
            run["scores"] = scores
            with open(path, "w") as fh:
                json.dump(run, fh, indent=1)
        shown = scores
        if args.brief:
            shown = {
                k: {kk: vv for kk, vv in v.items()
                    if kk not in ("per_agent", "proves", "unmatched_sample")}
                for k, v in scores.items()
            }
        print(f"── {path}")
        print(json.dumps(shown, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
