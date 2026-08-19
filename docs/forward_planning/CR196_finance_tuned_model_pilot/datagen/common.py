#!/usr/bin/env python3
"""common.py — shared plumbing for CR196 training-data generators.

Every recipe writes chat-format JSONL ({"messages":[{role,content},...], "_meta":{...}})
per the Silent_Scout sample shape. `_meta` carries recipe/ticker/label provenance and is
STRIPPED by the final mix step — it exists so QC can audit any example back to its facts.
"""
import hashlib, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
AGENT_PROMPT_PATH = os.path.join(REPO, "content", "agents", "fundamentals_analyst.md")


def load_agent_prompt(path=AGENT_PROMPT_PATH):
    """The real production base prompt, frontmatter stripped — distribution match."""
    text = open(path).read()
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    return text[m.end():].strip() if m else text.strip()


def load_eval_tickers():
    out = set()
    with open(os.path.join(HERE, "eval_tickers.txt")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.add(line.upper())
    return out


def load_train_universe():
    """The frozen train universe (build_universe.py output). Asserts decontamination."""
    path = os.path.join(HERE, "train_universe.txt")
    if not os.path.exists(path):
        raise SystemExit("train_universe.txt missing — run build_universe.py first")
    tickers = [l.strip().upper() for l in open(path)
               if l.strip() and not l.startswith("#")]
    overlap = set(tickers) & load_eval_tickers()
    if overlap:
        raise SystemExit(f"DECONTAMINATION VIOLATION: {sorted(overlap)} in train universe")
    return tickers


def pick(options, *keys):
    """Deterministic template variation — keyed hash, not random (reproducible builds)."""
    h = int(hashlib.sha256("|".join(str(k) for k in keys).encode()).hexdigest(), 16)
    return options[h % len(options)]


def fmt_b(v):
    """$84,344,000,000 → '$84.34B' (matches the brief's rendering)."""
    if v is None:
        return "n/a"
    v = float(v)
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(v) >= div:
            return f"${v / div:.2f}{unit}"
    return f"${v:,.0f}"


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def yf_backoff(fn, *args, attempts=5):
    """Retry a yfinance-touching callable through rate-limit windows (30s, 60s, ...).
    Added after 758/1437 tickers failed with YFRateLimitError on recipe1's first
    full sweep; the retried tail then completed with 0 errors. Non-rate-limit
    exceptions propagate unchanged."""
    import time
    for i in range(attempts):
        try:
            return fn(*args)
        except Exception as e:
            if "RateLimit" not in type(e).__name__ or i == attempts - 1:
                raise
            time.sleep(30 * (i + 1))
