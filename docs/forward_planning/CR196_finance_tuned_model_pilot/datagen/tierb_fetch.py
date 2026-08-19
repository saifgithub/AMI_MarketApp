#!/usr/bin/env python3
"""tierb_fetch.py — CR196 §2 Tier-B: public-dataset SFT/replay fetch + normalize.

Downloads TRAIN-SPLIT-ONLY slices of external finance/chat datasets via the `datasets`
library (Hugging Face Hub), normalizes each to the project's chat-JSONL shape used by
common.py / recipe1_basis.py — {"messages":[{role,content},...], "_meta":{...}} — and
writes one file per source under out/tierb_<source>.jsonl. `_meta` carries provenance
(recipe/source/license/split/orig_id) for QC; the final mix step strips it, same
convention as the Tier-A recipes.

License gate (CR196 §2, "per the Silent_Scout checklist"). Every source is probed
against the HF Hub dataset API BEFORE any row is downloaded:
  - no license tag on the card   -> SKIP, nothing fetched, recorded as skip_no_license
  - gated / access-restricted    -> SKIP, nothing fetched, recorded as gated
                                     (never worked around — same rule as Fin-R1-Data)
  - CC-BY-NC-* license           -> fetched, but written to out/tierb_<source>_NC.jsonl
                                     (separate file so the mix step excludes it by
                                     default; still flagged for Saiful's call)
  - any other real license       -> fetched normally (MIT, Apache-2.0, CC-BY-4.0, ...)

FinanceBench is eval-only (CR196 decontamination rule) and is never a candidate here —
it does not appear anywhere in SOURCES below, by design.

System prompt: every source uses common.load_agent_prompt() (the real production
fundamentals_analyst prompt) EXCEPT the UltraChat-200k replay slice, which keeps
whatever system message the source provides — none, for train_sft.

tierb_licenses.md (sibling file, hand-authored after a real run) is the audit trail:
per source it records the HF dataset id actually used, the license as stated on that
dataset's HF card, split, row count fetched, normalization notes, and access status.
This script prints everything needed to fill that in; it does not regenerate the .md
itself, matching the project convention that registers/reports are written, not
scripted, unless stated otherwise.

Usage:
  python3 tierb_fetch.py                  # every source; per-source try/except, one
                                            # failure never blocks the others
  python3 tierb_fetch.py --only finqa      # single source (repeatable, incremental)
  python3 tierb_fetch.py --probe           # license/access check only, no download
  python3 tierb_fetch.py --only rlvr --probe

Needs: pip install datasets requests   (requests ships with yfinance's deps already)
"""
import argparse, json, os, re, sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_agent_prompt, write_jsonl

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
HF_API = "https://huggingface.co/api/datasets/{}"
SEED = 196  # CR196 — every deterministic shuffle/slice in this file uses this seed

# FinQA's HF wrapper (ibm-research/finqa) ships only a `datasets`-library loading
# script; `datasets>=4` refuses to execute dataset scripts at all (hard RuntimeError,
# not a trust_remote_code gate — verified against datasets 5.0.1). The script's own
# `_split_generators` downloads this exact GitHub archive, so we fetch the same
# upstream file directly and apply the identical field mapping the script uses. The
# license recorded is still the one stated on the HF card (cc-by-4.0) — that's the
# actual redistribution license of this data, GitHub mirror or not. Pinned to a commit
# so reruns are stable even if the upstream repo moves.
FINQA_GITHUB_TRAIN = ("https://raw.githubusercontent.com/czyssrs/FinQA/"
                       "0f16e2867befa6840783e58be38c9efb9229d742/dataset/train.json")


# ---------------------------------------------------------------------------
# HF Hub probing — license + gating status, before any row is downloaded
# ---------------------------------------------------------------------------

def hf_info(dataset_id, timeout=15):
    r = requests.get(HF_API.format(dataset_id), timeout=timeout)
    try:
        body = r.json()
    except ValueError:
        body = {}
    return r.status_code, body


def get_license(info):
    """The license as stated on the HF card: prefer the parsed `license:` tag,
    fall back to cardData.license (some cards only set the YAML field)."""
    for t in info.get("tags", []) or []:
        if isinstance(t, str) and t.startswith("license:"):
            return t.split(":", 1)[1]
    cd = info.get("cardData") or {}
    lic = cd.get("license")
    if isinstance(lic, list):
        return lic[0] if lic else None
    return lic


def is_nc_license(lic):
    if not lic:
        return False
    parts = re.split(r"[-_]", lic.lower())
    return "nc" in parts


def probe_candidates(candidates):
    """Probe HF dataset ids in order (the brief's 'try X, then Y, then Z' chains).

    Stops at the first reachable + ungated + licensed candidate. A reachable-but-
    untagged candidate is kept as a fallback (skip_no_license outcome) only if no
    better-tagged candidate turns up later in the chain. Gated candidates are
    recorded and passed over — never worked around, matching the Fin-R1-Data rule
    generalized to every source.
    """
    attempts = []
    fallback = None
    for cid in candidates:
        try:
            status, info = hf_info(cid)
        except Exception as e:
            attempts.append({"id": cid, "ok": False, "error": f"{type(e).__name__}: {e}"})
            continue
        if status != 200 or info.get("error"):
            attempts.append({"id": cid, "ok": False, "http_status": status,
                              "error": info.get("error", f"HTTP {status}")})
            continue
        gated = bool(info.get("gated", False))
        lic = get_license(info)
        rec = {"id": cid, "ok": True, "http_status": 200, "gated": gated,
               "license": lic, "sha": info.get("sha")}
        attempts.append(rec)
        if gated:
            continue
        if lic:
            return {"outcome": "ok", "picked": cid, "license": lic, "sha": rec["sha"],
                     "attempts": attempts}
        if fallback is None:
            fallback = rec
    if fallback:
        return {"outcome": "skip_no_license", "picked": fallback["id"], "license": None,
                 "sha": fallback["sha"], "attempts": attempts}
    any_gated = any(a.get("gated") for a in attempts if a.get("ok"))
    return {"outcome": "gated" if any_gated else "inaccessible", "picked": None,
             "license": None, "sha": None, "attempts": attempts}


# ---------------------------------------------------------------------------
# Per-source normalization
# ---------------------------------------------------------------------------

def _render_table(rows):
    return "\n".join(" | ".join(str(c) for c in row) for row in rows)


# --- FinQA -------------------------------------------------------------------

def render_finqa_context(ex):
    parts = []
    if ex.get("pre_text"):
        parts.append(" ".join(ex["pre_text"]))
    if ex.get("table"):
        parts.append("Table:\n" + _render_table(ex["table"]))
    if ex.get("post_text"):
        parts.append(" ".join(ex["post_text"]))
    return "\n\n".join(parts)


def render_finqa_answer(qa):
    """Program/derivation folded in as shown arithmetic (per-step op(arg1,arg2)=res),
    then the answer — falling back to the last step's result when `answer` is empty
    (the HF wrapper's own rationale: ~48/6251 train rows have answer=="")."""
    steps = qa.get("steps") or []
    program = qa.get("program")
    answer = qa.get("answer")
    final_result = str(steps[-1]["res"]) if steps else None
    shown = answer if answer not in (None, "") else final_result
    lines = []
    if steps:
        lines.append("Derivation:")
        for i, s in enumerate(steps, 1):
            lines.append(f"  {i}. {s['op']}({s['arg1']}, {s['arg2']}) = {s['res']}")
    elif program:
        lines.append(f"Derivation: {program}")
    lines.append(f"Answer: {shown}")
    return "\n".join(lines)


def fetch_finqa(spec, probe, lic):
    sys_prompt = load_agent_prompt()
    r = requests.get(FINQA_GITHUB_TRAIN, timeout=60)
    r.raise_for_status()
    data = r.json()
    rows = []
    for ex in data:
        qa = ex["qa"]
        user = render_finqa_context(ex) + f"\n\nQuestion: {qa['question']}"
        assistant = render_finqa_answer(qa)
        rows.append({
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "_meta": {"recipe": "tierb", "source": probe["picked"], "license": lic,
                      "split": "train", "orig_id": ex.get("id"),
                      "fetched_via": f"github:czyssrs/FinQA@0f16e2867"},
        })
    return rows


# --- TAT-QA --------------------------------------------------------------

def render_tatqa_context(doc):
    parts = []
    tbl_rows = (doc.get("table") or {}).get("table") or []
    tbl = _render_table(tbl_rows)
    if tbl.strip():
        parts.append("Table:\n" + tbl)
    paras = doc.get("paragraphs") or []
    if paras:
        parts.append(" ".join(p.get("text", "") for p in paras))
    return "\n\n".join(parts)


def render_tatqa_answer(q):
    ans = q.get("answer")
    ans_str = ", ".join(str(a) for a in ans) if isinstance(ans, list) else str(ans)
    lines = []
    deriv = (q.get("derivation") or "").strip()
    if deriv:
        lines.append(f"Derivation: {deriv}")
    scale = (q.get("scale") or "").strip()
    scale_note = f" ({scale})" if scale else ""
    lines.append(f"Answer: {ans_str}{scale_note}")
    return "\n".join(lines)


def fetch_tatqa(spec, probe, lic):
    from datasets import load_dataset
    sys_prompt = load_agent_prompt()
    ds = load_dataset("next-tat/TAT-QA", split="train", revision=probe["sha"])
    rows = []
    for doc in ds:
        ctx = render_tatqa_context(doc)
        for q in doc.get("questions") or []:
            user = ctx + f"\n\nQuestion: {q['question']}"
            assistant = render_tatqa_answer(q)
            rows.append({
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": assistant},
                ],
                "_meta": {"recipe": "tierb", "source": probe["picked"], "license": lic,
                          "split": "train", "orig_id": q.get("uid")},
            })
    return rows


# --- financial-rlvr-10k-enterprise ----------------------------------------

def render_rlvr_answer(row):
    """Worked-solution SFT form. `is_edge_case` (the dataset's own field) decides
    trap vs normal — never our judgment. Trap cases answer with the detection
    message baked into `ground_truth`, not a hallucinated number."""
    code = (row.get("code_solution") or "").strip()
    gt = (row.get("ground_truth") or "").strip()
    if len(gt) >= 2 and gt.startswith('"') and gt.endswith('"'):
        gt = gt[1:-1]
    is_trap = bool(row.get("is_edge_case"))
    lines = ["This input is an edge/invalid case, not a standard computation. "
             "Detection logic:" if is_trap else "Worked solution:"]
    if code:
        lines += ["", "```python", code, "```", ""]
    lines.append(f"Conclusion: {gt}" if is_trap else f"Result: {gt}")
    return "\n".join(lines)


def fetch_rlvr(spec, probe, lic):
    from datasets import load_dataset
    sys_prompt = load_agent_prompt()
    ds = load_dataset("coslinedev/financial-rlvr-10k-enterprise", split="train",
                       revision=probe["sha"])
    rows = []
    for row in ds:
        assistant = render_rlvr_answer(row)
        rows.append({
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": row["prompt"]},
                {"role": "assistant", "content": assistant},
            ],
            "_meta": {"recipe": "tierb", "source": probe["picked"], "license": lic,
                      "split": "train", "orig_id": row.get("id"),
                      "domain": row.get("domain"),
                      "is_edge_case": bool(row.get("is_edge_case"))},
        })
    return rows


# --- Finance-Instruct-500k -------------------------------------------------

_ASCII_RE = re.compile(r"[\x00-\x7F]")


def _is_english(text, min_ascii_ratio=0.90):
    """No language column on this dataset (its card says 'multilingual' — Chinese
    rows from BAAI/IndustryInstruction_Finance-Economics are folded in). Heuristic:
    English/financial text is overwhelmingly ASCII; CJK and most other non-Latin
    scripts are not. Deterministic, documented, not a claim of linguistic rigor."""
    if not text:
        return False
    ascii_n = len(_ASCII_RE.findall(text))
    return (ascii_n / len(text)) >= min_ascii_ratio


def fetch_finance_instruct(spec, probe, lic):
    from datasets import load_dataset
    sys_prompt = load_agent_prompt()
    ds = load_dataset("Josephgflowers/Finance-Instruct-500k", split="train",
                       revision=probe["sha"])

    def keep(ex):
        u, a = (ex.get("user") or "").strip(), (ex.get("assistant") or "").strip()
        return bool(u) and bool(a) and _is_english(u) and _is_english(a)

    ds = ds.filter(keep)
    ds = ds.shuffle(seed=SEED)
    n = min(spec["cap"], len(ds))
    ds = ds.select(range(n))
    rows = []
    for i, ex in enumerate(ds):
        rows.append({
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": ex["user"]},
                {"role": "assistant", "content": ex["assistant"]},
            ],
            "_meta": {"recipe": "tierb", "source": probe["picked"], "license": lic,
                      "split": "train", "orig_id": f"finance-instruct-{i}"},
        })
    return rows


# --- UltraChat-200k (replay slice) -----------------------------------------

def fetch_ultrachat(spec, probe, lic):
    from datasets import load_dataset
    ds = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft",
                       revision=probe["sha"])
    ds = ds.shuffle(seed=SEED)
    n = min(spec["cap"], len(ds))
    ds = ds.select(range(n))
    rows = []
    for ex in ds:
        msgs = [{"role": m["role"], "content": m["content"]} for m in ex["messages"]]
        rows.append({
            "messages": msgs,
            "_meta": {"recipe": "tierb", "source": probe["picked"], "license": lic,
                      "split": "train_sft", "orig_id": ex.get("prompt_id")},
        })
    return rows


FETCHERS = {
    "finqa": fetch_finqa,
    "tatqa": fetch_tatqa,
    "finance_instruct": fetch_finance_instruct,
    "rlvr": fetch_rlvr,
    "ultrachat": fetch_ultrachat,
    # convfinqa, finr1: never reach FETCHERS — the license gate short-circuits them
    # (skip_no_license / gated) before any fetch is attempted.
}


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

SOURCES = [
    {"key": "finqa",
     "candidates": ["ibm-research/finqa", "dreamerdeo/finqa", "FinGPT/fingpt-finqa"],
     "out": "tierb_finqa.jsonl", "cap": None},
    {"key": "tatqa",
     "candidates": ["next-tat/TAT-QA"],
     "out": "tierb_tatqa.jsonl", "cap": None},
    {"key": "convfinqa",
     "candidates": ["FinGPT/fingpt-convfinqa"],
     "out": "tierb_convfinqa.jsonl", "cap": None},
    {"key": "finance_instruct",
     "candidates": ["Josephgflowers/Finance-Instruct-500k"],
     "out": "tierb_finance_instruct_500k.jsonl", "cap": 15000},
    {"key": "rlvr",
     "candidates": ["coslinedev/financial-rlvr-10k-enterprise"],
     "out": "tierb_financial_rlvr.jsonl", "cap": 10000},
    {"key": "finr1",
     "candidates": ["SUFE-AIFLM-Lab/Fin-R1-Data"],
     "out": "tierb_finr1.jsonl", "cap": None},
    {"key": "ultrachat",
     "candidates": ["HuggingFaceH4/ultrachat_200k"],
     "out": "tierb_ultrachat.jsonl", "cap": 4000},
]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def process_source(spec, do_fetch, results):
    key = spec["key"]
    print(f"\n=== {key} ===")
    probe = probe_candidates(spec["candidates"])
    rec = {"key": key, "out": spec["out"], "status": None, "rows": 0,
           "license": probe["license"], "nc": False, "picked_id": probe["picked"],
           "error": None}

    for a in probe["attempts"]:
        if a.get("ok"):
            print(f"  probe {a['id']}: HTTP 200  gated={a['gated']}  "
                  f"license={a['license']!r}  sha={a['sha']}")
        else:
            print(f"  probe {a['id']}: FAILED  http_status={a.get('http_status')}  "
                  f"error={a.get('error')}")

    if probe["outcome"] == "inaccessible":
        rec["status"] = "inaccessible"
        print("  -> INACCESSIBLE: no candidate reachable. Recorded, not fetched.")
        results.append(rec)
        return
    if probe["outcome"] == "gated":
        rec["status"] = "gated"
        print(f"  -> GATED: {spec['candidates'][0]} (or a later candidate) requires "
              f"access not available here. Recorded, not fetched — never worked around.")
        results.append(rec)
        return
    if probe["outcome"] == "skip_no_license":
        rec["status"] = "skip_no_license"
        print(f"  -> SKIP: {probe['picked']} has no license tag on its HF card. "
              f"Per the license gate, not fetched.")
        results.append(rec)
        return

    # outcome == "ok"
    lic = probe["license"]
    nc = is_nc_license(lic)
    out_name = spec["out"]
    if nc:
        base, ext = os.path.splitext(out_name)
        out_name = f"{base}_NC{ext}"
    rec["license"], rec["nc"], rec["out"] = lic, nc, out_name

    if not do_fetch:
        rec["status"] = "probed_ok"
        print(f"  -> OK  license={lic!r}  NC={nc}  (--probe: not downloading)")
        results.append(rec)
        return

    try:
        rows = FETCHERS[key](spec, probe, lic)
    except Exception as e:
        rec["status"] = "fetch_error"
        rec["error"] = f"{type(e).__name__}: {e}"
        print(f"  -> FETCH FAILED: {rec['error']}")
        results.append(rec)
        return

    out_path = os.path.join(OUT_DIR, out_name)
    n = write_jsonl(out_path, rows)
    rec["status"] = "ok"
    rec["rows"] = n
    print(f"  -> wrote {n} rows -> out/{out_name}  (license={lic!r}{', NC' if nc else ''})")
    results.append(rec)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="run a single source key: " +
                     ", ".join(s["key"] for s in SOURCES))
    ap.add_argument("--probe", action="store_true",
                     help="license/access check only, no download")
    args = ap.parse_args()

    specs = SOURCES
    if args.only:
        specs = [s for s in SOURCES if s["key"] == args.only]
        if not specs:
            valid = ", ".join(s["key"] for s in SOURCES)
            raise SystemExit(f"unknown source {args.only!r} — valid: {valid}")

    os.makedirs(OUT_DIR, exist_ok=True)
    results = []
    for spec in specs:
        process_source(spec, do_fetch=not args.probe, results=results)

    print("\n=== summary ===")
    for r in results:
        lic = r["license"] if r["license"] else "-"
        print(f"  {r['key']:20s} status={r['status']:16s} rows={r['rows']:<7d} "
              f"license={lic:14s} out={r['out']}")


if __name__ == "__main__":
    main()
