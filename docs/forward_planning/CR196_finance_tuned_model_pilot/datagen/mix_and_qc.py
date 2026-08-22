#!/usr/bin/env python3
"""mix_and_qc.py — CR196 final gate: recipes + Tier B → the kit's train/val JSONL.

Nothing reaches the kit except through this script. Steps, in order:
  1. load every datagen/out/*.jsonl (Tier B `_NC`-suffixed files EXCLUDED unless
     --include-nc — the CC-BY-NC call is Saiful's, not a default)
  2. exact dedup (SHA256 of the rendered messages) then near-dup (normalized-text hash)
  3. decontamination re-check: Tier A `_meta.ticker` must not be an eval ticker, and no
     example TEXT may mention an eval ticker of length >= 3 as a standalone token
     (1-2 letter tickers like T/FL would false-positive on prose; the _meta check and
     the frozen-universe gate in every generator already cover them upstream)
  4. per-source mix caps from MIX_WEIGHTS (deterministic hash-ranked downsample — a
     re-run with the same inputs picks the same rows)
  5. deterministic ~2% val split (hash-bucketed, never random)
  5b. OUTPUT-SHAPE GATE: enough targets must reach the size of the deliverable
     production actually asks for, or the build fails. The val split is drawn from
     the same generators as train, so loss cannot see this — run 1 passed every
     number and could not write the report (CR196 §9, guards-register P27).
  6. outputs: kit train.jsonl + val.jsonl with _meta STRIPPED, data_manifest.md with
     per-source counts/licenses/QC numbers, review_sample.jsonl (200 examples,
     _meta kept) for human eyeballing
Token lengths are ESTIMATED at chars/4 (no tokenizer on the build box) and labeled so.

Usage: python3 mix_and_qc.py [--out-dir ../ami_finetune_kit/data] [--include-nc]
"""
import argparse, collections, glob, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_eval_tickers

HERE = os.path.dirname(os.path.abspath(__file__))

# Per-source example caps (None = keep all). Starting mix per CR196 §2 —
# revised by the SA-FDR probe step once it has run on the training box.
MIX_WEIGHTS = {
    # Tier A substrate — uncapped. These teach reading the statements correctly and
    # are what made the basis rubric go 43/44; they are short by nature and that is
    # fine, as long as they are not the ONLY thing in the mix (which is what run 1
    # did).
    "recipe1_basis": None, "recipe2_ratios": None, "recipe3_trends": None,
    "recipe4_earnings_quality": None, "recipe5_basis_traps": None,
    "recipe6_asof_discipline": None, "recipe7_mandate_compliance": None,
    "recipe8_room_format": None, "recipe9_refusal": None,
    # The deliverable itself (recipe 10). Uncapped: it is the only source in the mix
    # that teaches the nine-section report production actually asks for, and the
    # shape gate below is unreachable without it — see the run-2 re-cap note.
    "recipe10_longform": None,
    # Run-2 caps. Run 1 used finqa 3000 / tatqa 4000 / finance_instruct 4000 /
    # rlvr 4000 / ultrachat 2500 and shipped at 3.53% deliverable.
    #
    # Measured over the real files, the re-cap ALONE reaches only 7.45% — cutting
    # the short sources cannot fix the shape, because nothing that remains is long.
    # It is still worth doing: finqa and tatqa have MEDIAN targets of 64 and 45
    # characters. They were carried as "finance skills replay", but a 45-character
    # median teaches terseness, which is the failure being repaired. So they drop to
    # a token presence that keeps the skill without setting the length prior.
    #
    # UltraChat goes the other way, to its full 4,000. It is the only long-form
    # replay in the mix and it protects general instruction-following; run 1 capped
    # away 1,500 rows of exactly the behaviour it then lost.
    "tierb_finqa": 1200, "tierb_tatqa": 1200,
    "tierb_finance_instruct_500k": 3000, "tierb_financial_rlvr": 2000,
    "tierb_ultrachat": 4000,
}
VAL_PCT = 2  # hash buckets of 100

# --- output-shape gate (CR196 §9, guards-register P27) ----------------------
# Run 1 passed every number it was measured on — eval loss 0.2384, merged held-out
# loss 0.2506 from a base of 2.2744 — and then could not produce the deliverable.
# Asked for the production nine-section brief it returned 45-244 tokens of
# recipe-shaped fragments where the untrained base returned ~1,200.
#
# The manifest is why it was invisible. It reported WHOLE-EXAMPLE length (system +
# user + assistant, chars/4), which ran a healthy 1,300-2,300 est. tokens per row
# because the briefs are long. What governs how much a model WRITES is the
# assistant target, and that was never reported. Measured after the fact:
#
#     median target 331 chars · 87% under 1,000 · >=2,000: 8.20% · >=5,000: 3.53%
#
# So the mix taught short answers almost exclusively, and the Tier-B "replay" meant
# to protect the base's long-form behaviour is itself short-answer numeric QA.
#
# DELIVERABLE_CHARS is the size of the thing production actually asks for. The first
# value here was 5,000, from a SINGLE observation of the base answering the AAPL
# brief. Measured properly on 2026-08-22 -- 20 briefs through vanilla Fastino on
# alpha-spark, every one a clean stop:
#
#     complete nine-section reports: min 3,003 · median 3,733 · max 5,009 chars
#     (871 / 1,053 / 1,382 tokens).  Only 5% reach 5,000.
#
# So 5,000 was measuring the tail of the teacher's own distribution, not the
# deliverable, and no achievable mix could ever have cleared it. 3,000 is the
# MEASURED FLOOR of a complete report, and it separates cleanly from everything
# that is not one: the highest p90 among all non-report sources is 1,370
# (recipe5), and run 1's collapse outputs were 180-970 chars. 2.2x margin.
DELIVERABLE_CHARS = 3000

# --- and the numerator matters as much as the threshold ------------------------
# Run 1 scored 3.53% deliverable. Essentially ALL of it was UltraChat: 2,500 rows x
# 37.2% over 5,000 chars = ~930, against a total of 907 such rows in the whole mix.
# Not one Tier-A example reached 5,000 at all.
#
# So the gate as first written could have been satisfied entirely by REPLAY. Adding
# UltraChat rows would have raised the number while the model still never saw a
# single finance report -- which is exactly the hole run 1 fell through. A gate that
# a replay slice can satisfy is not measuring what it claims to measure.
#
# The numerator therefore counts TASK long-form only. Replay is by definition not
# teaching our job; it is there to stop the base forgetting how to hold a
# conversation, and it does that whether or not it is long.
REPLAY_SOURCES = {"tierb_ultrachat"}

# MIN_DELIVERABLE_PCT is a floor chosen for margin, NOT a derived optimum -- there
# is no measurement saying where the collapse boundary sits, only that run 1 had
# ZERO task long-form and collapsed. Run 2's result is what will calibrate it.
MIN_DELIVERABLE_PCT = 15.0

# An absolute floor as well as a ratio, because the two fail differently: a ratio
# can be met by shrinking the mix, and a count can be met by drowning it. Run 1 had
# zero; Fastino's own successful run was 13,698 examples total.
MIN_DELIVERABLE_ROWS = 800


def target_chars(ex):
    return sum(len(m["content"]) for m in ex["messages"]
               if m.get("role") == "assistant")


def shape_stats(rows):
    """Length shape of a row set. `pct_deliverable` counts every long target;
    `task_rows` counts only the ones that teach OUR job -- see REPLAY_SOURCES.
    The gate reads task_rows; pct_deliverable is kept for the per-source manifest,
    where 'how long is this source' is the useful question."""
    lens = sorted(target_chars(ex) for ex in rows)
    if not lens:
        return {"n": 0, "median": 0, "p90": 0, "pct_deliverable": 0.0,
                "task_rows": 0, "pct_task_deliverable": 0.0}
    n = len(lens)
    task = sum(1 for ex in rows
               if target_chars(ex) >= DELIVERABLE_CHARS
               and ex.get("_src") not in REPLAY_SOURCES)
    return {"n": n, "median": lens[n // 2], "p90": lens[int(0.9 * n)],
            "pct_deliverable": 100.0 * sum(l >= DELIVERABLE_CHARS
                                           for l in lens) / n,
            "task_rows": task, "pct_task_deliverable": 100.0 * task / n}


def norm_text(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def source_of(path, ex):
    m = ex.get("_meta", {})
    if m.get("recipe") == "tierb":
        # keyed by the output FILE, not _meta.source (which carries the full HF id)
        return os.path.basename(path).rsplit(".", 1)[0]
    return m.get("recipe") or os.path.basename(path).rsplit(".", 1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=os.path.join(HERE, "..", "ami_finetune_kit", "data"))
    ap.add_argument("--include-nc", action="store_true")
    ap.add_argument("--allow-shape-gap", action="store_true",
                    help="ship a mix whose targets cannot reach the deliverable")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(HERE, "out", "*.jsonl")))
    if not args.include_nc:
        skipped_nc = [p for p in paths if p.endswith("_NC.jsonl")]
        paths = [p for p in paths if not p.endswith("_NC.jsonl")]
    else:
        skipped_nc = []
    if not paths:
        raise SystemExit("no input files in datagen/out/ — run the generators first")

    eval_tk = load_eval_tickers()
    eval_long = {t for t in eval_tk if len(t) >= 3}
    eval_pat = re.compile(r"\b(" + "|".join(sorted(eval_long)) + r")\b") if eval_long else None

    seen_exact, seen_near = set(), set()
    by_source = collections.defaultdict(list)
    stats = collections.Counter()
    contaminated = []

    for path in paths:
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            ex = json.loads(line)
            stats["loaded"] += 1
            src = source_of(path, ex)
            text = "\n".join(m["content"] for m in ex["messages"])

            tk = ex.get("_meta", {}).get("ticker", "")
            if tk and tk.upper() in eval_tk:
                contaminated.append((src, tk, "meta"))
                continue
            if src.startswith("recipe") and eval_pat and eval_pat.search(text):
                contaminated.append((src, eval_pat.search(text).group(0), "text"))
                continue

            he = h(text)
            if he in seen_exact:
                stats["dup_exact"] += 1
                continue
            seen_exact.add(he)
            hn = h(norm_text(text))
            if hn in seen_near:
                stats["dup_near"] += 1
                continue
            seen_near.add(hn)
            ex["_hash"] = he
            ex["_src"] = src        # the gate partitions task vs replay on this
            by_source[src].append(ex)

    if contaminated:
        for src, tk, kind in contaminated[:20]:
            print(f"CONTAMINATED ({kind}): {src} / {tk}")
        raise SystemExit(f"FAIL: {len(contaminated)} contaminated examples — fix the "
                         f"generator, do not just drop rows silently")

    train, val = [], []
    manifest_rows = []
    for src in sorted(by_source):
        rows = sorted(by_source[src], key=lambda e: e["_hash"])
        cap = MIX_WEIGHTS.get(src)
        capped = rows[:cap] if cap else rows
        n_val = 0
        for ex in capped:
            bucket = int(ex["_hash"][:8], 16) % 100
            (val if bucket < VAL_PCT else train).append(ex)
            n_val += bucket < VAL_PCT
        lens = sorted(len("".join(m["content"] for m in ex["messages"])) // 4
                      for ex in capped)
        sh = shape_stats(capped)
        manifest_rows.append((src, len(rows), len(capped), n_val,
                              lens[len(lens) // 2] if lens else 0,
                              lens[-1] if lens else 0,
                              sh["median"], sh["p90"], sh["pct_deliverable"]))

    mix_shape = shape_stats(train)

    os.makedirs(args.out_dir, exist_ok=True)
    review = []
    for name, rows in (("train.jsonl", train), ("val.jsonl", val)):
        with open(os.path.join(args.out_dir, name), "w") as f:
            for ex in sorted(rows, key=lambda e: e["_hash"]):
                if len(review) < 200 and name == "train.jsonl":
                    review.append(ex)
                f.write(json.dumps({"messages": ex["messages"]}, ensure_ascii=False) + "\n")
    with open(os.path.join(HERE, "out", "review_sample.jsonl"), "w") as f:
        for ex in review:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    with open(os.path.join(args.out_dir, "data_manifest.md"), "w") as f:
        f.write("# CR196 data manifest (generated by mix_and_qc.py — do not hand-edit)\n\n")
        f.write(f"- train: **{len(train)}** examples · val: **{len(val)}** "
                f"(deterministic {VAL_PCT}% hash split)\n")
        f.write(f"- dedup: {stats['dup_exact']} exact, {stats['dup_near']} near "
                f"of {stats['loaded']} loaded\n")
        f.write(f"- decontamination: PASS (0 eval-ticker examples; "
                f"{len(eval_tk)} exclusions)\n")
        if skipped_nc:
            f.write(f"- NC-licensed sources EXCLUDED (Saiful's call pending): "
                    f"{[os.path.basename(p) for p in skipped_nc]}\n")
        f.write("- token lengths are chars/4 ESTIMATES (no tokenizer on build box)\n")
        f.write(f"- **output shape**: **{mix_shape['task_rows']}** TASK targets reach "
                f"the {DELIVERABLE_CHARS}-char deliverable "
                f"(**{mix_shape['pct_task_deliverable']:.2f}%** of the mix; floors: "
                f"{MIN_DELIVERABLE_ROWS} rows and {MIN_DELIVERABLE_PCT:.1f}%), "
                f"median target {mix_shape['median']} chars, p90 "
                f"{mix_shape['p90']}\n")
        f.write(f"- counting ALL sources including replay it would be "
                f"{mix_shape['pct_deliverable']:.2f}% — replay is excluded because "
                f"run 1's entire 3.53% was UltraChat and the model still never saw "
                f"a finance report (CR196 §10)\n")
        f.write("  — target length is what governs how much the model WRITES; "
                "whole-example length does not (CR196 §9, P27)\n\n")
        f.write("| source | generated | kept | in val | med tok (est) | max tok (est) "
                "| med target ch | p90 target ch | % deliverable |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for r in manifest_rows:
            f.write(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} "
                    f"| {r[6]} | {r[7]} | {r[8]:.1f}% |\n")
        f.write("\nLicenses: see datagen/tierb_licenses.md (Tier B) — Tier A is "
                "generated from feeds, never redistributed (CR196 §2).\n")

    print(f"train={len(train)} val={len(val)} sources={len(by_source)} "
          f"dup_exact={stats['dup_exact']} dup_near={stats['dup_near']}")
    print(f"manifest → {os.path.join(args.out_dir, 'data_manifest.md')}")
    print(f"output shape: median target {mix_shape['median']} ch, "
          f"p90 {mix_shape['p90']} ch, {mix_shape['task_rows']} task targets "
          f">= {DELIVERABLE_CHARS} ch ({mix_shape['pct_task_deliverable']:.2f}%; "
          f"{mix_shape['pct_deliverable']:.2f}% counting replay)")

    # Written first, then enforced: a mix that fails the gate is exactly the one
    # whose manifest you need in order to see WHICH source is starving it.
    if not args.allow_shape_gap and (
            mix_shape["task_rows"] < MIN_DELIVERABLE_ROWS
            or mix_shape["pct_task_deliverable"] < MIN_DELIVERABLE_PCT):
        raise SystemExit(
            f"FAIL: only {mix_shape['task_rows']} task targets reach the "
            f"{DELIVERABLE_CHARS}-char deliverable "
            f"({mix_shape['pct_task_deliverable']:.2f}% of the mix). Floors are "
            f"{MIN_DELIVERABLE_ROWS} rows AND {MIN_DELIVERABLE_PCT:.1f}%.\n"
            f"Median target is {mix_shape['median']} chars.\n"
            f"Counting replay it would be {mix_shape['pct_deliverable']:.2f}% — "
            f"which is why replay does not count: run 1 shipped at 3.53%, almost "
            f"all of it UltraChat, and could not produce the deliverable at all "
            f"(CR196 §9/§10, guards-register P27).\n"
            f"Add long-form TASK data (recipe10_longform) or cut the short "
            f"sources; --allow-shape-gap overrides, deliberately loudly.")


if __name__ == "__main__":
    main()
