"""ISS003 offline measurement: can our models write Room turns as segments + atom references?

The MAI_CODE2 and LUNA proposals both have desks stop typing numbers: a desk writes prose segments
and `{"atom": id}` references, and server code prints every figure. Whether that is practical
depends on whether the models can produce that format. This script measures it; it judges nothing
else. Read-only against Alpha (one SELECT per fetch over ssh); calls model endpoints directly.

Subcommands (run with `backend/.venv/bin/python -I`, stdlib only):
  export                      sample 40 desk turns (20 US, 20 .KL) from Alpha and freeze them
  probe   --model M           check whether the endpoint enforces response_format json_schema
  run     --model M           run arms A and B (resumable); M in qwen | ling | deepseek
  report                      aggregate all results into tables (stdout + workdir/tables.md)
  handread                    dump outputs to hand-read into workdir/handread.txt

All exported Room text and model output stays in --workdir (outside the repo).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SEED = 20261126
SINCE = "2026-11-20"
N_PER_MARKET = 20
MAIN = Path("/Volumes/Extreme Pro/AMI_MarketApp")
DEFAULT_WORKDIR = Path(
    "/private/tmp/claude-501/-Volumes-Extreme-Pro-AMI-MarketApp/"
    "ef54641e-c39e-4be2-9db8-14b07e12ba62/scratchpad/iss003_format"
)

DESKS = {
    "fundamentals_analyst": "Fundamentals Analyst: judge the company's financial health and valuation from the fact sheet.",
    "bull_researcher": "Bull Researcher: make the strongest evidence-based case for buying.",
    "bear_researcher": "Bear Researcher: make the strongest evidence-based case against buying.",
    "research_manager": "Research Manager: weigh the bull and bear cases and set the plan.",
    "trader": "Execution Desk: turn the plan into a concrete trade (side, size, risk controls).",
    "aggressive_debator": "Aggressive Risk Officer: argue for taking more risk where the evidence supports it.",
    "conservative_debator": "Conservative Risk Officer: argue for protecting capital first.",
    "neutral_debator": "Neutral Risk Officer: balance the aggressive and conservative views.",
    "portfolio_manager": "CIO: make the final call and state what would break the thesis.",
}
DESK_ORDER = list(DESKS)

# ---------- ledger ----------

MONEY_M = {  # sheet stores local-currency millions ("-RM15,433M")
    "free_cash_flow", "free_cash_flow_ttm", "capex_ttm", "capital_return_ttm", "dividends_paid_ttm",
    "market_cap", "net_cash", "operating_cash_flow_ttm", "revenue_ttm", "total_cash", "total_debt",
    "sbc_ttm", "wc_change_ttm", "wc_payables_ttm", "wc_inventory_ttm", "wc_receivables_ttm",
    "segment_revenue_total", "debt_maturity_beyond_5y",
}
SHARES_M = {"float_shares", "shares_outstanding"}
PRICE = {
    "atr14", "base_price", "bollinger_lower", "bollinger_upper", "breakout", "high", "low", "last_close",
    "sma_200", "sma_long", "sma_short", "support", "trailing_eps", "revenue_per_share", "buyback_price",
    "analyst_target_high", "analyst_target_low", "analyst_target_median", "analyst_target_price",
}
PCT = {
    "fcf_yield", "dividend_yield", "profit_margin", "operating_margin", "gross_margin", "rev_growth",
    "return_on_assets", "return_on_equity", "payout_ratio", "upside", "downside", "bear_size",
    "bull_size", "short_pct_float", "dividend_growth", "capital_return_pct_fcf",
}
MULT = {"ev_to_ebitda", "price_to_sales", "debt_to_equity", "historical_pe_median", "historical_ev_ebitda_median",
        "peer_comparison_median_pe", "peer_comparison_median_ev_ebitda", "forward_pe", "interest_coverage",
        "interest_coverage_quarter"}
SKIP = {"period_candles", "historical_pe_years", "eps_revisions_window_days", "analyst_opinion_count",
        "run_date", "fcf_history_years", "roe_history_years", "peer_comparison_basket_size",
        "peer_comparison_median_pe_n", "peer_comparison_median_ev_ebitda_n", "peer_comparison_median_net_margin_n",
        "executive_change_total", "executive_change_unverified_days"}
LABELS = {
    "free_cash_flow": "free cash flow (TTM)", "free_cash_flow_ttm": "free cash flow (TTM, cash-flow basis)",
    "fcf_yield": "FCF yield", "atr14": "ATR(14) daily range", "rsi": "RSI(14)", "beta": "beta",
    "last_close": "last close", "base_price": "base price", "sma_200": "200-day average",
    "sma_long": "long moving average", "sma_short": "short moving average",
    "price_vs_sma_200_pct": "price vs 200-day average", "change_52w_pct": "52-week change",
    "change_52w_sp500_pct": "52-week change of the benchmark", "day_change_pct": "day change",
    "return_period_pct": "return over the chart period", "relative_strength_52w_pct": "52-week relative strength vs benchmark",
    "held_pct_insiders": "insider ownership", "held_pct_institutions": "institutional ownership",
    "bear_size": "bear case size", "bull_size": "bull case size", "upside": "upside to target case",
    "downside": "downside case", "net_cash": "net cash", "total_cash": "total cash", "total_debt": "total debt",
    "market_cap": "market cap", "revenue_ttm": "revenue (TTM)", "operating_cash_flow_ttm": "operating cash flow (TTM)",
    "capex_ttm": "capex (TTM)", "dividends_paid_ttm": "dividends paid (TTM)", "capital_return_ttm": "capital returned (TTM)",
    "trailing_eps": "trailing EPS", "wacc_estimate_pct": "WACC estimate", "wacc_beta": "WACC beta",
    "wacc_erp_pct": "equity risk premium", "wacc_risk_free_pct": "risk-free rate", "roe_median_pct": "median ROE",
    "eps_revisions_pct": "EPS estimate revisions", "eps_revisions_current": "current EPS estimate",
    "bollinger_width_pct": "Bollinger band width", "net_margin_trend_bps": "net margin trend (bps)",
    "volume_ratio": "volume ratio vs average", "volume_today": "volume today", "volume_avg_3m": "3-month average volume",
}


def fmt_num(x: float, dp: int | None = None) -> str:
    if dp is None:
        dp = 0 if float(x).is_integer() else (1 if abs(x) >= 100 else (2 if abs(x) >= 1 else 3))
    return f"{x:,.{dp}f}"


def render_atom(key: str, v: float, ccy: str) -> str:
    sign = "-" if v < 0 else ""
    a = abs(v)
    if key in MONEY_M:
        return f"{sign}{ccy}{fmt_num(a, 0)}M"
    if key in SHARES_M:
        return f"{fmt_num(a, 0)}M shares"
    if key in PRICE:
        return f"{sign}{ccy}{fmt_num(a)}"
    if key in PCT or key.endswith("_pct"):
        return f"{sign}{fmt_num(a, 1)}%"
    if key.endswith("_bps"):
        return f"{sign}{fmt_num(a, 0)} bps"
    if key in MULT:
        return f"{sign}{fmt_num(a, 1)}x"
    return f"{sign}{fmt_num(a)}"


def build_ledger(sheet: dict, ticker: str) -> list[dict]:
    ccy = "RM" if ticker.endswith(".KL") else "$"
    out = []
    for k in sorted(sheet):
        v = sheet[k]
        if k in SKIP or isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        out.append({"id": f"sheet.{k}", "label": LABELS.get(k, k.replace("_", " ")), "rendered": render_atom(k, float(v), ccy)})
    return out


# ---------- checker ----------

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred hundreds "
         "thousand thousands million millions billion billions trillion trillions").split()
_ORD = ("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth "
        "fifteenth sixteenth seventeenth eighteenth nineteenth twentieth thirtieth fortieth fiftieth sixtieth "
        "seventieth eightieth ninetieth hundredth thousandth millionth billionth").split()
_FRAC = ("half halves quarter quarters thirds dozen dozens twice thrice double doubled doubles doubling triple "
         "tripled triples tripling").split()
_PCT = ["percent", "percentage", "percentages", "pct"]
NUMWORD_RE = re.compile(r"\b(?:" + "|".join(_ONES + _ORD + _FRAC + _PCT) + r"|per[\s-]cent)\b", re.I)


def has_numeral_char(s: str) -> list[str]:
    return [c for c in s if unicodedata.category(c) in ("Nd", "Nl", "No")]


def validate(raw: str, atom_ids: set[str]) -> tuple[list[dict] | None, list[str], dict]:
    """Return (segments, error_classes, details). Empty error list = valid."""
    details: dict = {"words": [], "unknown": []}
    s = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S)
    if fence:
        s = fence.group(1)
        details["fenced"] = True
    try:
        data = json.loads(s)
    except Exception as e:  # noqa: BLE001
        return None, ["bad_json"], {**details, "msg": str(e)[:120]}
    if not isinstance(data, list) or not data or not all(
        isinstance(x, dict) and len(x) == 1 and (
            (list(x)[0] == "text" and isinstance(x["text"], str)) or (list(x)[0] == "atom" and isinstance(x["atom"], str))
        ) for x in data
    ):
        return None, ["bad_schema"], details
    errs = []
    for seg in data:
        if "text" in seg:
            t = seg["text"]
            if has_numeral_char(t):
                if "numeral_in_text" not in errs:
                    errs.append("numeral_in_text")
                details.setdefault("numerals", []).append(t[:60])
            w = [m.group(0).lower() for m in NUMWORD_RE.finditer(t)]
            if w:
                details["words"].extend(w)
                if "number_word_in_text" not in errs:
                    errs.append("number_word_in_text")
        elif seg["atom"] not in atom_ids:
            details["unknown"].append(seg["atom"])
            if "unknown_atom" not in errs:
                errs.append("unknown_atom")
    return data, errs, details


def render_segments(segs: list[dict], ledger: list[dict]) -> str:
    r = {a["id"]: a["rendered"] for a in ledger}
    return "".join(s["text"] if "text" in s else f"[{r.get(s['atom'], '?')}]" for s in segs)


# ---------- DB export ----------

def run_sql(sql: str, workdir: Path) -> str:
    p = workdir / "q.sql"
    p.write_text(sql)
    subprocess.run(["scp", "-q", str(p), "melehost:/tmp/iss003_q.sql"], check=True, capture_output=True)
    r = subprocess.run(
        ["ssh", "-q", "melehost",
         'docker cp /tmp/iss003_q.sql ami_postgres:/tmp/iss003_q.sql && docker exec ami_postgres sh -c '
         '"psql -U \\"\\$POSTGRES_USER\\" -d \\"\\$POSTGRES_DB\\" -At -f /tmp/iss003_q.sql"'],
        check=True, capture_output=True, text=True)
    return "\n".join(l for l in r.stdout.splitlines() if "succeeded" not in l)


SHEET_JOIN = (
    "(select f.sheet from room_fact_sheets f where f.ticker=r.ticker and "
    "f.sheet->>'run_date'=to_char(r.triggered_at at time zone 'UTC','YYYY-MM-DD') "
    "order by abs(extract(epoch from (f.created_at - r.triggered_at))) limit 1)"
)


def strip_notes(t: str) -> str:
    return re.sub(r"\[AMI[^\]]*\]", "", t).strip()


def cmd_export(a) -> None:
    wd = a.workdir
    wd.mkdir(parents=True, exist_ok=True)
    meta_sql = (
        "select r.id, r.ticker, e.ord-1, e.v->>'agent_id', coalesce(e.v->>'scripted','false'), length(e.v->>'content') "
        "from room_runs r, jsonb_array_elements(r.transcript) with ordinality e(v, ord) "
        f"where r.status='completed' and r.triggered_at>='{SINCE}' and {SHEET_JOIN} is not null;"
    )
    rows = [l.split("|") for l in run_sql(meta_sql, wd).splitlines() if l.count("|") == 5]
    turns: dict[str, dict] = {}
    for rid, tk, idx, agent, scripted, ln in rows:
        d = turns.setdefault(rid, {"ticker": tk, "turns": []})
        if agent in DESKS and scripted != "true" and ln and int(ln) >= 400:
            d["turns"].append((int(idx), agent))
    rng = random.Random(SEED)
    chosen = []
    used_rooms: set[str] = set()
    for market, is_kl in (("US", False), ("KL", True)):
        rooms = sorted(r for r, d in turns.items() if d["ticker"].endswith(".KL") == is_kl)
        rng.shuffle(rooms)
        cycle = DESK_ORDER[:]
        rng.shuffle(cycle)
        used_tickers: set[str] = set()
        for i in range(N_PER_MARKET):
            desk = cycle[i % len(cycle)]
            pick = None
            for pass_distinct in (True, False):
                for rid in rooms:
                    d = turns[rid]
                    if rid in used_rooms or (pass_distinct and d["ticker"] in used_tickers):
                        continue
                    opts = [ix for ix, ag in d["turns"] if ag == desk]
                    if opts:
                        pick = (rid, rng.choice(opts), desk)
                        break
                if pick:
                    break
            if not pick:
                sys.exit(f"no eligible room for {desk} in {market}")
            used_rooms.add(pick[0])
            used_tickers.add(turns[pick[0]]["ticker"])
            chosen.append({"run_id": pick[0], "idx": pick[1], "agent": pick[2], "market": market})
    ids = ",".join(f"'{c['run_id']}'" for c in chosen)
    full_sql = (
        "select row_to_json(t) from (select r.id, r.ticker, r.triggered_at, r.transcript, "
        f"{SHEET_JOIN} as sheet from room_runs r where r.id in ({ids})) t;"
    )
    full = {}
    for l in run_sql(full_sql, wd).splitlines():
        if l.startswith("{"):
            j = json.loads(l)
            full[j["id"]] = j
    out = []
    for c in chosen:
        j = full[c["run_id"]]
        tr = j["transcript"]
        orig = strip_notes(tr[c["idx"]]["content"])
        prior = [{"agent": t["agent_id"], "content": strip_notes(t["content"])} for t in tr[: c["idx"]]]
        out.append({
            "tid": f"{c['market']}-{len(out):02d}-{c['agent']}", **c, "ticker": j["ticker"],
            "triggered_at": j["triggered_at"], "original": orig, "prior": prior, "sheet": j["sheet"],
        })
    (wd / "sample.json").write_text(json.dumps(out, indent=1))
    print(f"seed={SEED} wrote {len(out)} turns; desks:",
          {d: sum(1 for o in out if o["agent"] == d) for d in DESK_ORDER})


# ---------- model calls ----------

def load_env(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^\s*([A-Z0-9_]+)=(.*)$", line)
        if m:
            env[m.group(1)] = m.group(2).strip().strip("'\"")
    return env


def model_cfg(name: str, main: Path) -> dict:
    alpha = load_env(main / "infra" / "alpha.env")
    if name == "qwen":
        return {"base": alpha["VLLM_BASE_URL"].rstrip("/") + "/v1", "model": alpha["VLLM_MODEL"], "key": None,
                "thinking_kwarg": True, "workers": 1, "pause": 3.0, "timeout": 420, "max_tokens": 4000, "cap": 400}
    if name == "ling":
        return {"base": alpha["VLLM_FALLBACK_BASE_URL"].rstrip("/") + "/v1", "model": alpha["VLLM_FALLBACK_MODEL"],
                "key": alpha.get("VLLM_FALLBACK_API_KEY") or None, "thinking_kwarg": True, "workers": 1,
                "pause": 1.0, "timeout": 420, "max_tokens": 4000, "cap": 400}
    if name == "deepseek":
        key = load_env(main / ".env")["CHEAPLLM_API_KEY"]
        return {"base": "https://cheapllm.shop/v1", "model": "deepseek-v4.1-flash-1017", "key": key,
                "thinking_kwarg": False, "workers": 1, "pause": 0.0, "timeout": 900, "max_tokens": 8000, "cap": 400}
    sys.exit("unknown model")


class CapacityError(Exception):
    pass


class SchemaRejected(Exception):
    pass


class Caller:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.calls = 0
        self.lock = threading.Lock()
        self.root = None

    def _post(self, path: str, body: dict | None):
        req = urllib.request.Request(
            self.cfg["base"] + path, data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "format-compliance-measure/1.0", **({"Authorization": f"Bearer {self.cfg['key']}"} if self.cfg["key"] else {})})
        with urllib.request.urlopen(req, timeout=self.cfg["timeout"]) as r:
            return json.loads(r.read())

    def identify(self) -> str:
        data = self._post("/models", None)
        for m in data["data"]:
            if m["id"] == self.cfg["model"]:
                self.root = m.get("root") or "(no root field)"
        return self.root or "(model id not listed)"

    def chat(self, messages: list[dict], schema: dict | None, max_tokens: int | None = None) -> dict:
        """One logical call with capacity retries. Returns {content, latency_s, http_calls}."""
        body = {"model": self.cfg["model"], "messages": messages, "max_tokens": max_tokens or self.cfg["max_tokens"], "temperature": 0.3}
        if self.cfg["thinking_kwarg"]:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        if schema is not None:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "segments", "schema": schema, "strict": True}}
        delays = [15, 30, 60, 120, 240]
        for attempt in range(len(delays) + 1):
            with self.lock:
                if self.calls >= self.cfg["cap"]:
                    raise CapacityError("hard call cap reached")
                self.calls += 1
            t0 = time.time()
            try:
                data = self._post("/chat/completions", body)
                msg = data["choices"][0]["message"]
                content = msg.get("content") or ""
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.S)
                if "</think>" in content:
                    content = content.split("</think>", 1)[1]
                return {"content": content, "latency_s": time.time() - t0, "http_calls": attempt + 1,
                        "finish": data["choices"][0].get("finish_reason")}
            except urllib.error.HTTPError as e:
                txt = e.read().decode("utf-8", "replace")[:300]
                if e.code == 400 and schema is not None and re.search(r"schema|response_format|guided|grammar|regex|pattern", txt, re.I):
                    raise SchemaRejected(txt) from e
                err = f"HTTP {e.code}: {txt}"
            except Exception as e:  # noqa: BLE001  (timeouts, resets)
                err = f"{type(e).__name__}: {e}"
            if attempt < len(delays):
                time.sleep(delays[attempt])
            else:
                raise CapacityError(err)
        raise CapacityError("unreachable")


# ---------- prompt ----------

def build_prompt(t: dict, ledger: list[dict]) -> str:
    n_words = max(40, len(re.sub(r"[\d.,%$()\-+/]+", " ", t["original"]).split()))
    prior = t["prior"][-8:]
    debate = "\n\n".join(
        f"[{DESKS[p['agent']].split(':')[0] if p['agent'] in DESKS else p['agent']}] {p['content'][:600]}" for p in prior
    ) or "(you speak first)"
    atoms = "\n".join(f"{a['id']} | {a['label']} | {a['rendered']}" for a in ledger)
    ex = [a for a in ledger if a["id"] in ("sheet.last_close", "sheet.fcf_yield", "sheet.free_cash_flow", "sheet.rsi", "sheet.beta")] or ledger
    e1, e2 = ex[0]["id"], ex[min(1, len(ex) - 1)]["id"]
    return (
        f"You are the {DESKS[t['agent']]}\nRoom for {t['ticker']} ({'Bursa Malaysia' if t['market'] == 'KL' else 'US'}). Write your next turn in the debate.\n\n"
        "FIGURES ARE NOT YOURS TO TYPE. The system prints every number. The atoms below are the only figures you may refer to; "
        "you point at one by its id and the system writes the value.\n\n"
        f"ATOMS (id | label | value the reader will see)\n{atoms}\n\n"
        f"DEBATE SO FAR (context only; do not copy figures from it)\n{debate}\n\n"
        "OUTPUT FORMAT: a JSON array of segments. A segment is either {\"text\": \"...\"} (prose) or {\"atom\": \"<id>\"} (a figure). "
        "Text segments must contain no digits and no number words (no one, two, ten, hundred, million, first, second, half, quarter, "
        "double, percent and so on), not even approximately; when a figure matters, cite an atom. Markdown (bold, bullets) is allowed inside text. "
        "Only use atom ids from the list above.\n"
        "Examples:\n"
        f"[{{\"text\":\"The sheet shows \"}},{{\"atom\":\"{e1}\"}},{{\"text\":\", and the other side will lean on \"}},{{\"atom\":\"{e2}\"}},{{\"text\":\".\"}}]\n"
        f"[{{\"text\":\"**Key read:** \"}},{{\"atom\":\"{e2}\"}},{{\"text\":\" is the number that decides this, not the headline story.\"}}]\n\n"
        f"Length: about {n_words} words of prose, plus atoms. Reply with the JSON array only."
    )


def build_schema(atom_ids: list[str]) -> dict:
    return {
        "type": "array", "minItems": 1, "maxItems": 120,
        "items": {"anyOf": [
            {"type": "object", "properties": {"text": {"type": "string", "pattern": "^[^0-9]*$"}}, "required": ["text"], "additionalProperties": False},
            {"type": "object", "properties": {"atom": {"type": "string", "enum": atom_ids}}, "required": ["atom"], "additionalProperties": False},
        ]},
    }


def repair_message(errs: list[str], det: dict) -> str:
    parts = []
    if "bad_json" in errs:
        parts.append("your reply was not valid JSON")
    if "bad_schema" in errs:
        parts.append("your reply was not a non-empty JSON array of {\"text\": ...} or {\"atom\": ...} segments")
    if "numeral_in_text" in errs:
        parts.append("a text segment contained a digit (replace it with an atom, or word it without any number)")
    if "number_word_in_text" in errs:
        parts.append("text segments contained number words: " + ", ".join(sorted(set(det["words"]))[:12]) + " (remove them or use an atom)")
    if "unknown_atom" in errs:
        parts.append("these atom ids are not in the list: " + ", ".join(sorted(set(det["unknown"]))[:12]))
    return "Your reply failed validation: " + "; ".join(parts) + ". Return the corrected JSON array only."


def attempt_turn(caller: Caller, t: dict, arm: str) -> dict:
    ledger = build_ledger(t["sheet"], t["ticker"])
    ids = [a["id"] for a in ledger]
    schema = build_schema(ids) if arm == "B" else None
    prompt = build_prompt(t, ledger)
    msgs = [{"role": "user", "content": prompt}]
    rec = {"tid": t["tid"], "arm": arm, "n_atoms": len(ids), "calls": [], "status": None}
    try:
        for stage in ("first", "repair"):
            r = caller.chat(msgs, schema)
            segs, errs, det = validate(r["content"], set(ids))
            rec["calls"].append({"stage": stage, "latency_s": round(r["latency_s"], 1), "errors": errs, "details": det,
                                 "finish": r["finish"], "raw": r["content"]})
            if not errs:
                rec["status"] = "valid_first" if stage == "first" else "valid_repaired"
                rec["segments"] = segs
                return rec
            if stage == "first":
                msgs = msgs + [{"role": "assistant", "content": r["content"]}, {"role": "user", "content": repair_message(errs, det)}]
        rec["status"] = "withheld"
    except SchemaRejected as e:
        rec["status"] = "schema_rejected"
        rec["error"] = str(e)[:200]
    except CapacityError as e:
        rec["status"] = "capacity_failed"
        rec["error"] = str(e)[:200]
    return rec


def cmd_probe(a) -> None:
    cfg = model_cfg(a.model, a.main)
    c = Caller(cfg)
    root = c.identify()
    schema = {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "object",
              "properties": {"text": {"type": "string", "pattern": "^[^0-9]*$"}}, "required": ["text"], "additionalProperties": False}}
    probe = {"model": a.model, "root": root, "enforced": None, "note": ""}
    try:
        r = c.chat([{"role": "user", "content": 'Reply with exactly this JSON and nothing else: [{"text":"call 555 now 12345"}]'}], schema, max_tokens=150)
        probe["raw"] = r["content"][:200]
        probe["enforced"] = not re.search(r"\d", r["content"])
        probe["note"] = "accepted; digits blocked" if probe["enforced"] else "accepted but digits appeared: schema NOT enforced"
    except SchemaRejected as e:
        probe["enforced"] = False
        probe["note"] = "rejected: " + str(e)[:150]
    except CapacityError as e:
        probe["note"] = "capacity: " + str(e)[:150]
    a.workdir.mkdir(parents=True, exist_ok=True)
    (a.workdir / f"probe_{a.model}.json").write_text(json.dumps(probe, indent=1))
    print(json.dumps({k: v for k, v in probe.items() if k != "raw"}))


def cmd_run(a) -> None:
    cfg = model_cfg(a.model, a.main)
    c = Caller(cfg)
    root = c.identify()
    print(f"[{a.model}] root={root}", flush=True)
    sample = json.loads((a.workdir / "sample.json").read_text())
    if a.limit:
        sample = sample[: a.limit]
    if a.per_market:
        sample = [t for mk in ("US", "KL") for t in [x for x in sample if x["market"] == mk][: a.per_market]]
    pf = a.workdir / f"probe_{a.model}.json"
    arms = ["A"]
    if pf.exists() and json.loads(pf.read_text()).get("enforced"):
        arms.append("B")
    else:
        print(f"[{a.model}] arm B skipped: no enforced-schema probe", flush=True)
    outf = a.workdir / f"results_{a.model}.jsonl"
    done = set()
    if outf.exists():
        for line in outf.read_text().splitlines():
            r = json.loads(line)
            if r["status"] != "capacity_failed":
                done.add((r["tid"], r["arm"]))
    wlock = threading.Lock()
    jobs = [(t, arm) for t in sample for arm in arms if (t["tid"], arm) not in done]

    def work(job):
        t, arm = job
        rec = attempt_turn(c, t, arm)
        rec["root"] = root
        with wlock:
            with outf.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
        print(f"[{a.model}] {t['tid']} {arm} -> {rec['status']} ({c.calls} http calls)", flush=True)
        time.sleep(cfg["pause"])
        return rec

    with ThreadPoolExecutor(cfg["workers"]) as ex:
        list(ex.map(work, jobs))


# ---------- report ----------

def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "n/a"


def p90(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))] if xs else float("nan")


def numerals_in(text: str) -> int:
    t = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    return len(re.findall(r"\d[\d,]*(?:\.\d+)?", t))


def coverage(sample: list[dict]) -> tuple[int, int, dict]:
    """Share of the original turns' numerals whose value equals some ledger atom's raw value (rounded to the numeral's own decimals)."""
    hit = tot = 0
    by_mkt = {"US": [0, 0], "KL": [0, 0]}
    for t in sample:
        raws = [float(v) for k, v in t["sheet"].items() if k not in SKIP and not isinstance(v, bool) and isinstance(v, (int, float))]
        text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", t["original"])
        text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
        for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text):
            tok = m.group(0).replace(",", "")
            if re.fullmatch(r"20\d\d", tok):
                continue
            d = len(tok.split(".")[1]) if "." in tok else 0
            v = float(tok)
            ok = any(round(abs(r), d) == v for r in raws)
            tot += 1
            hit += ok
            by_mkt[t["market"]][0] += ok
            by_mkt[t["market"]][1] += 1
    return hit, tot, by_mkt


def load_results(wd: Path, model: str) -> list[dict]:
    f = wd / f"results_{model}.jsonl"
    latest = {}
    if f.exists():
        for line in f.read_text().splitlines():
            r = json.loads(line)
            latest[(r["tid"], r["arm"])] = r
    return list(latest.values())


def cmd_report(a) -> None:
    sample = {t["tid"]: t for t in json.loads((a.workdir / "sample.json").read_text())}
    lines = []
    ch, ct, cm = coverage(list(sample.values()))
    lines.append(f"ledger coverage of original numerals (value equals some atom): {ch}/{ct}={pct(ch, ct)}; "
                 + ", ".join(f"{k} {v[0]}/{v[1]}={pct(v[0], v[1])}" for k, v in cm.items()))
    labels = {}
    lf = a.workdir / "handread_labels.json"
    if lf.exists():
        labels = json.loads(lf.read_text())
    for model in ("qwen", "ling", "deepseek"):
        res = load_results(a.workdir, model)
        pf = a.workdir / f"probe_{model}.json"
        probe = json.loads(pf.read_text()) if pf.exists() else {}
        lines.append(f"\n### {model}  root={res[0]['root'] if res else probe.get('root')}  probe: {probe.get('note')}")
        for arm in ("A", "B"):
            rs = [r for r in res if r["arm"] == arm]
            if not rs:
                continue
            cap = [r for r in rs if r["status"] == "capacity_failed"]
            rej = [r for r in rs if r["status"] == "schema_rejected"]
            ok = [r for r in rs if r["status"] in ("valid_first", "valid_repaired", "withheld")]
            n = len(ok)
            vf = sum(r["status"] == "valid_first" for r in ok)
            vr = sum(r["status"] in ("valid_first", "valid_repaired") for r in ok)
            lat = [c["latency_s"] for r in rs for c in r["calls"]]
            first_cls: dict[str, int] = {}
            final_cls: dict[str, int] = {}
            words: dict[str, int] = {}
            for r in ok:
                for cl in r["calls"][0]["errors"]:
                    first_cls[cl] = first_cls.get(cl, 0) + 1
                for w in r["calls"][0]["details"].get("words", []):
                    words[w] = words.get(w, 0) + 1
                if r["status"] == "withheld":
                    for cl in r["calls"][-1]["errors"]:
                        final_cls[cl] = final_cls.get(cl, 0) + 1
            lat_txt = f"call latency median {statistics.median(lat):.1f}s p90 {p90(lat):.1f}s over {len(lat)} calls" if lat else "no latency"
            lines.append(
                f"- arm {arm}: n={n} (+{len(cap)} capacity-failed, {len(rej)} schema-rejected) first-pass valid {vf}/{n}={pct(vf, n)}; "
                f"after-repair valid {vr}/{n}={pct(vr, n)}; withheld {n - vr}/{n}={pct(n - vr, n)}; {lat_txt}")
            lines.append(f"    first-pass failure classes (outputs affected): {first_cls}; residual after repair: {final_cls}; "
                         f"top number words: {sorted(words.items(), key=lambda kv: -kv[1])[:8]}")
            for mk in ("US", "KL"):
                sub = [r for r in ok if sample[r["tid"]]["market"] == mk]
                if sub:
                    s1 = sum(r["status"] == "valid_first" for r in sub)
                    s2 = sum(r["status"] in ("valid_first", "valid_repaired") for r in sub)
                    lines.append(f"    {mk}: n={len(sub)} first-pass {s1}/{len(sub)} after-repair {s2}/{len(sub)}")
            valid = [r for r in ok if r["status"] != "withheld"]
            ratios, zero = [], 0
            for r in valid:
                cited = len({s["atom"] for s in r["segments"] if "atom" in s})
                zero += cited == 0
                no = numerals_in(sample[r["tid"]]["original"])
                if no:
                    ratios.append(cited / no)
            if ratios:
                lines.append(f"    content: distinct atoms/original numerals median {statistics.median(ratios):.2f} (n={len(ratios)}); "
                             f"zero-atom outputs {zero}/{len(valid)} of valid")
            by_desk: dict[str, list[int]] = {}
            for r in ok:
                d = sample[r["tid"]]["agent"]
                by_desk.setdefault(d, [0, 0])
                by_desk[d][0] += r["status"] != "withheld"
                by_desk[d][1] += 1
            lines.append("    after-repair valid by desk: " + ", ".join(f"{d} {v[0]}/{v[1]}" for d, v in sorted(by_desk.items())))
            lab = labels.get(model, {})
            if lab and arm == ("B" if any(r["arm"] == "B" for r in res) else "A"):
                cnt = {x: sum(1 for v in lab.values() if v == x) for x in ("kept", "thinned", "dodged")}
                mb = len(labels.get("_misbound", {}).get(model, []))
                lines.append(f"    hand-read ({len(lab)}): {cnt}; visibly mis-bound or dangling atoms in {mb}")
    txt = "\n".join(lines)
    (a.workdir / "tables.md").write_text(txt)
    print(txt)


def cmd_handread(a) -> None:
    sample = {t["tid"]: t for t in json.loads((a.workdir / "sample.json").read_text())}
    out = []
    rng = random.Random(SEED)
    for model in ("qwen", "ling", "deepseek"):
        res = load_results(a.workdir, model)
        arm = "B" if any(r["arm"] == "B" for r in res) else "A"
        valid = sorted((r for r in res if r["arm"] == arm and r["status"] in ("valid_first", "valid_repaired")), key=lambda r: r["tid"])
        rng.shuffle(valid)
        for r in valid[:10]:
            t = sample[r["tid"]]
            led = build_ledger(t["sheet"], t["ticker"])
            out.append(f"=== {model} arm {arm} {r['tid']} {t['ticker']}\n--- ORIGINAL\n{t['original']}\n--- OUTPUT\n{render_segments(r['segments'], led)}\n")
    (a.workdir / "handread.txt").write_text("\n".join(out))
    print(f"wrote {len(out)} items to {a.workdir / 'handread.txt'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["export", "probe", "run", "report", "handread"])
    ap.add_argument("--model", choices=["qwen", "ling", "deepseek"])
    ap.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR)
    ap.add_argument("--main", type=Path, default=MAIN, help="checkout holding .env and infra/alpha.env")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--per-market", type=int, default=0, help="run only the first N sampled turns of each market")
    a = ap.parse_args()
    {"export": cmd_export, "probe": cmd_probe, "run": cmd_run, "report": cmd_report, "handread": cmd_handread}[a.cmd](a)


if __name__ == "__main__":
    main()
