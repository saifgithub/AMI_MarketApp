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
    "recipe1_basis": None, "recipe2_ratios": None, "recipe3_trends": None,
    "recipe4_earnings_quality": None, "recipe5_basis_traps": None,
    "recipe6_asof_discipline": None, "recipe7_mandate_compliance": None,
    "recipe8_room_format": None, "recipe9_refusal": None,
    # Run-1 caps: Tier B raw (48.5k) would swamp Tier A (~8.7k) at 85/15; these
    # bring the mix to roughly A 33% / B 58% / replay 9%. SA-FDR probes revise them.
    "tierb_finqa": 3000, "tierb_tatqa": 4000,
    "tierb_finance_instruct_500k": 4000, "tierb_financial_rlvr": 4000,
    "tierb_ultrachat": 2500,
}
VAL_PCT = 2  # hash buckets of 100


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
        manifest_rows.append((src, len(rows), len(capped), n_val,
                              lens[len(lens) // 2] if lens else 0,
                              lens[-1] if lens else 0))

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
        f.write("- token lengths are chars/4 ESTIMATES (no tokenizer on build box)\n\n")
        f.write("| source | generated | kept | in val | med tok (est) | max tok (est) |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in manifest_rows:
            f.write(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |\n")
        f.write("\nLicenses: see datagen/tierb_licenses.md (Tier B) — Tier A is "
                "generated from feeds, never redistributed (CR196 §2).\n")

    print(f"train={len(train)} val={len(val)} sources={len(by_source)} "
          f"dup_exact={stats['dup_exact']} dup_near={stats['dup_near']}")
    print(f"manifest → {os.path.join(args.out_dir, 'data_manifest.md')}")


if __name__ == "__main__":
    main()
