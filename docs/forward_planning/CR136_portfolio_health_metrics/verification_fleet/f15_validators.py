"""F15 verification prototypes — naive digit-sequence validator (Rev 3 Rule 5)
vs rendered-token allow-list validator (the review's prescribed fix).
Throwaway measurement code for CR136 Rev 4. Never imported by the repo.
"""
import json
import re
import random
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN

# ---------------------------------------------------------------- payload ----
# Realistic stripped metric context per CR136 prompt-contract rule 1
# (sufficient blocks only, raw values; renderer owns formatting).
PAYLOAD = {
    "portfolio_volatility": {"value": 0.2312, "standard_error": 0.0146,
                             "n_observations": 126, "window_days": 126,
                             "estimator": "ledoit_wolf_constant_correlation"},
    "benchmark_volatility": {"value": 0.1487, "standard_error": 0.0094,
                             "n_observations": 126, "window_days": 126,
                             "benchmark": "SPY"},
    "beta": {"value": 1.42, "r_squared": 0.6249, "standard_error": 0.13,
             "n_observations": 126, "window_days": 126,
             "low_explanatory_power": False},
    "dr2": {"value": 1.8, "n_holdings": 9, "window_days": 126},
    "top_risk_contributor": {"ticker": "NVDA", "risk_share": 0.62,
                             "weight": 0.3, "window_days": 126},
    "weight_concentration": {"hhi": 0.18, "effective_n": 5.6,
                             "basis": "weights"},
    "realised_max_drawdown": {"value": -0.183, "window_days": 94},
}

# Derived slots the rule engine itself computes (category b).
DERIVED_SLOTS = {
    "beta_x10": float(Decimal("1.42") * 10),          # R3 template slot
    "ci95_half_width_pp": float(Decimal("1.96") * Decimal("0.0146") * 100),
}

# Fixed constants (category c): citation years + JPM 30(4), sqrt-252, 95% CI,
# S&P 500, BOK M11/M12, $10,000 (separator-normalized), template literal 10,
# z=1.96.
CONSTANTS = ["1952", "2004", "2008", "30", "4", "252", "95", "500",
             "11", "12", "10000", "10", "1.96"]

# ------------------------------------------------- mandated section F3 text --
F3_TEXT = """SECTION F3 - Detailed math analysis.
Portfolio volatility: 23.1% annualised (standard error 1.5pp, n = 126,
window 126 trading days). Estimator: sample covariance with Ledoit-Wolf
constant-correlation shrinkage - Ledoit & Wolf (2004), "Honey, I Shrunk the
Sample Covariance Matrix", JPM 30(4). Foundational framework: Markowitz (1952).
Daily volatility is annualised by the square root of 252. The 95% confidence
interval on the annualised figure is about plus or minus 2.9pp.
Beta vs the S&P 500 (SPY, dividends included): 1.42 with R-squared 0.62
(n = 126, same aligned window). Estimator: OLS regression slope (CAPM).
Effective independent bets: DR-squared 1.8 over 9 holdings - Choueifaty &
Coignard (2008) diversification ratio.
Realised max drawdown: 18.3% over the 94 days observed.
Covariance estimated with Ledoit-Wolf constant-correlation shrinkage for a
short sample. Gross of fees: the simulation deducts no fees or slippage from
the $10,000 starting capital. See BOK lessons M11/M12 for the formulas behind
these metrics."""

DIGIT_RUN = re.compile(r"\d+")


# ------------------------------------------------------- naive validator ----
def payload_digit_runs(payload):
    return set(DIGIT_RUN.findall(json.dumps(payload)))


def naive_validate(text, payload, mode="substring"):
    """Rev 3 Rule 5 as written: reject any output digit sequence absent from
    the context values. Two literal readings:
      substring  - output run must appear inside some payload digit run
      exact      - output run must equal some payload digit run
    Returns (ok, rejected_runs)."""
    runs = payload_digit_runs(payload)
    rejected = []
    for tok in DIGIT_RUN.findall(text):
        if mode == "exact":
            ok = tok in runs
        else:
            ok = any(tok in r for r in runs)
        if not ok:
            rejected.append(tok)
    return (len(rejected) == 0), rejected


# --------------------------------------------------- allow-list validator ---
def canon(s):
    """Canonical decimal string: strip thousands separators + trailing zeros."""
    s = s.replace(",", "").lstrip("+")
    return format(Decimal(s).normalize(), "f")


def renderings(v, scales=((1, (1, 2, 3, 4)), (100, (0, 1, 2)))):
    """All display renderings of value v: half-even AND half-up, +-1 ulp,
    raw scale at 1-4 dp, percent scale at 0-2 dp. Sign-insensitive."""
    out = set()
    x0 = abs(Decimal(str(v)))
    out.add(canon(str(x0)))                      # raw value echoed verbatim
    for scale, dps in scales:
        x = x0 * scale
        for dp in dps:
            q = Decimal(1).scaleb(-dp)
            for mode in (ROUND_HALF_UP, ROUND_HALF_EVEN):
                r = x.quantize(q, rounding=mode)
                for delta in (0, q, -q):
                    val = r + delta
                    if val >= 0:
                        out.add(canon(str(val)))
    return out


def build_allowed(payload, derived, constants):
    """Two sets: PCT (percent/pp-suffixed tokens) and RAW (bare tokens).
    Constants + integer fields go in both. Derived slots go in both (their
    unit is whatever the template says)."""
    pct, raw = set(), set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    if isinstance(v, int):          # windows / counts (cat d)
                        tok = canon(str(v))
                        pct.add(tok); raw.add(tok)
                    else:                           # measured value (cat a)
                        pct.update(renderings(v, scales=((100, (0, 1, 2)),)))
                        raw.update(renderings(v, scales=((1, (1, 2, 3, 4)),)))
                        raw.add(canon(str(abs(Decimal(str(v))))))
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)
    for v in derived.values():                       # cat b — engine-computed
        r = renderings(v, scales=((1, (0, 1, 2)),))
        pct.update(r); raw.update(r)
    for c in constants:                              # cat c
        tok = canon(c)
        pct.add(tok); raw.add(tok)
    return pct, raw


NUM_TOKEN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
PCT_SUFFIX = re.compile(r"^\s*(%|pp\b|percent\b|per cent\b|percentage point)")


def allowlist_validate(text, pct, raw, scale_aware=True):
    """Returns (ok, rejected_tokens). Union mode ignores the % suffix."""
    union = pct | raw
    rejected = []
    for m in NUM_TOKEN.finditer(text):
        tok = canon(m.group(0))
        if scale_aware:
            is_pct = bool(PCT_SUFFIX.match(text[m.end():]))
            ok = tok in (pct if is_pct else raw)
        else:
            ok = tok in union
        if not ok:
            rejected.append(m.group(0))
    return (len(rejected) == 0), rejected


# ----------------------------------------------------------------- part 1 ---
def part1():
    print("=" * 72)
    print("PART 1 - NAIVE validator vs mandated F3 content")
    runs = sorted(payload_digit_runs(PAYLOAD))
    print(f"payload digit runs ({len(runs)}): {runs}")
    tokens = []
    seen = set()
    for t in DIGIT_RUN.findall(F3_TEXT):
        if t not in seen:
            seen.add(t); tokens.append(t)
    print(f"{'output run':>12} | substring | exact")
    n_sub = n_ex = 0
    for t in tokens:
        sub = any(t in r for r in runs)
        ex = t in runs
        n_sub += (not sub); n_ex += (not ex)
        print(f"{t:>12} | {'pass' if sub else 'REJECT':>9} | {'pass' if ex else 'REJECT'}")
    ok_sub, rej_sub = naive_validate(F3_TEXT, PAYLOAD, "substring")
    ok_ex, rej_ex = naive_validate(F3_TEXT, PAYLOAD, "exact")
    print(f"\nsubstring-naive verdict on mandated F3: "
          f"{'PASS' if ok_sub else 'REJECT'} ({n_sub}/{len(tokens)} unique runs rejected)")
    print(f"exact-naive     verdict on mandated F3: "
          f"{'PASS' if ok_ex else 'REJECT'} ({n_ex}/{len(tokens)} unique runs rejected)")
    print(f"substring-rejected runs: {sorted(set(rej_sub))}")


# ----------------------------------------------------------------- part 2 ---
def part2():
    print("=" * 72)
    print("PART 2 - rounding non-determinism 0.6249 vs 0.6251")
    for r2 in (0.6249, 0.6251):
        p = json.loads(json.dumps(PAYLOAD))
        p["beta"]["r_squared"] = r2
        pct = (Decimal(str(r2)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        text = f"The market explains {pct}% of this portfolio's movement."
        ok_sub, rej_sub = naive_validate(text, p, "substring")
        ok_ex, rej_ex = naive_validate(text, p, "exact")
        print(f"r_squared={r2} -> rendered '{pct}%' | substring: "
              f"{'PASS' if ok_sub else 'REJECT ' + str(rej_sub)} | exact: "
              f"{'PASS' if ok_ex else 'REJECT ' + str(rej_ex)}")


# ----------------------------------------------------------------- part 3 ---
def part3():
    print("=" * 72)
    print("PART 3 - R3 template {beta_x10} vs the naive validator")
    p0 = json.loads(json.dumps(PAYLOAD))
    lit_ok = any("10" in r for r in payload_digit_runs(p0))
    print(f"template literal '10% market move' digit run '10' in payload: {lit_ok}")

    betas = [round(1.30 + 0.01 * i, 2) for i in range(71)]
    rej_sub = rej_ex = 0
    examples = []
    for b in betas:
        p = json.loads(json.dumps(PAYLOAD))
        p["beta"]["value"] = b
        bx10 = canon(str(Decimal(str(b)) * 10))
        token_text = f"~{bx10}%"
        ok_s, _ = naive_validate(token_text, p, "substring")
        ok_e, _ = naive_validate(token_text, p, "exact")
        rej_sub += (not ok_s); rej_ex += (not ok_e)
        if len(examples) < 4 and not ok_s:
            examples.append((b, bx10))
    print(f"beta swept over [1.30, 2.00] step 0.01 (n=71), slot rendered at 1dp:")
    print(f"  {{beta_x10}} token alone rejected: substring {rej_sub}/71, exact {rej_ex}/71")
    print(f"  first substring-rejected examples: {examples}")

    p = json.loads(json.dumps(PAYLOAD))  # beta = 1.42 (the payload value)
    sent = ("A 10% market move has historically meant ~14.2% for this book "
            "over the window.")
    ok_s, r_s = naive_validate(sent, p, "substring")
    ok_e, r_e = naive_validate(sent, p, "exact")
    print(f"full R3 sentence at beta=1.42: substring "
          f"{'PASS' if ok_s else 'REJECT ' + str(r_s)} | exact "
          f"{'PASS' if ok_e else 'REJECT ' + str(r_e)}")


# ----------------------------------------------------------------- part 4 ---
def compose_good(rng, pct, raw):
    """A plausible model output built ONLY from payload renderings, derived
    slots, and constants — random dp / rounding mode / separators."""
    def fmt(v, scale, dp, mode):
        x = (abs(Decimal(str(v))) * scale).quantize(
            Decimal(1).scaleb(-dp), rounding=mode)
        return str(x)                     # keeps trailing zeros sometimes

    mode = rng.choice([ROUND_HALF_UP, ROUND_HALF_EVEN])
    frags = [
        f"Portfolio volatility is "
        f"{fmt(0.2312, 100, rng.choice([0, 1, 2]), mode)}% annualised versus "
        f"{fmt(0.1487, 100, rng.choice([0, 1]), mode)}% for the benchmark.",
        f"NVDA is {fmt(0.62, 100, 0, mode)}% of the risk at "
        f"{fmt(0.3, 100, 0, mode)}% of the money.",
        f"Beta is {fmt(1.42, 1, 2, mode)} against the S&P 500.",
        f"You hold 9 positions but only {fmt(1.8, 1, 1, mode)} effective "
        f"independent bets.",
        f"A 10% market move has historically meant "
        f"~{fmt(DERIVED_SLOTS['beta_x10'], 1, 1, mode)}% for this book.",
        "Estimates use 126 trading days, annualised by the square root of 252,"
        " per Ledoit & Wolf (2004), JPM 30(4).",
        "The simulation deducts no fees from the $10,000 starting capital "
        "(Markowitz (1952); Choueifaty & Coignard (2008); BOK lessons M11/M12).",
        f"The 95% confidence interval spans about "
        f"{fmt(DERIVED_SLOTS['ci95_half_width_pp'], 1, 1, mode)}pp either way.",
        f"Realised max drawdown was {fmt(0.183, 100, 1, mode)}% over the "
        f"94 days observed.",
    ]
    rng.shuffle(frags)
    return " ".join(frags[: rng.randint(3, 5)])


FABRICATIONS = [
    ("Roughly 47% of your risk sits in one name.", "47"),
    ("Your book fell 31% in the crash of 1997.", "31/1997"),
    ("That is about $12,400 of value.", "12,400"),
    ("A correlation of 0.35 links the top pair.", "0.35"),
    ("You hold 27 positions in total.", "27"),
    ("The window covers 200 trading days.", "200"),
    ("A beta of 2.6 would amplify moves further.", "2.6"),
    ("The market returned 8.5% annualised.", "8.5"),
    ("An HHI of 0.44 shows concentration.", "0.44"),
    ("Volatility of 39% is elevated.", "39"),
]


def part4():
    print("=" * 72)
    print("PART 4 - ALLOW-LIST validator")
    pct, raw = build_allowed(PAYLOAD, DERIVED_SLOTS, CONSTANTS)
    print(f"allowed-set sizes: pct={len(pct)}, raw={len(raw)}, "
          f"union={len(pct | raw)}")

    for aware in (True, False):
        label = "scale-aware" if aware else "union"
        ok, rej = allowlist_validate(F3_TEXT, pct, raw, aware)
        print(f"(i) mandated F3 content [{label}]: "
              f"{'PASS' if ok else 'REJECT ' + str(rej)}")

    bad = F3_TEXT + " Roughly 47% of your risk sits in a single position."
    for aware in (True, False):
        label = "scale-aware" if aware else "union"
        ok, rej = allowlist_validate(bad, pct, raw, aware)
        print(f"(ii) F3 + fabricated '47%' [{label}]: "
              f"{'REJECTED tokens ' + str(rej) if not ok else 'FALSE-ACCEPT'}")

    rng = random.Random(42)
    goods = [compose_good(rng, pct, raw) for _ in range(10)]
    bads = []
    for i in range(10):
        g = compose_good(rng, pct, raw)
        fab, _ = FABRICATIONS[i]
        bads.append(g + " " + fab)

    for aware in (True, False):
        label = "scale-aware" if aware else "union"
        fr = fa = 0
        fr_detail, fa_detail = [], []
        for i, g in enumerate(goods):
            ok, rej = allowlist_validate(g, pct, raw, aware)
            if not ok:
                fr += 1; fr_detail.append((i, rej))
        for i, b in enumerate(bads):
            ok, rej = allowlist_validate(b, pct, raw, aware)
            if ok:
                fa += 1; fa_detail.append(i)
        print(f"(iii) randomized seed=42 [{label}]: "
              f"false-reject {fr}/10 good {fr_detail}, "
              f"false-accept {fa}/10 bad {fa_detail}")

    # residual risk: number-level allow-listing cannot bind value to metric
    for aware in (True, False):
        label = "scale-aware" if aware else "union"
        ok, rej = allowlist_validate("Your beta is 62.", pct, raw, aware)
        print(f"(adversarial mis-binding) 'Your beta is 62.' [{label}]: "
              f"{'ACCEPTED (cross-metric collision)' if ok else 'rejected ' + str(rej)}")
    ok, rej = allowlist_validate("Your beta is 62%.", pct, raw, True)
    print(f"(adversarial) 'Your beta is 62%.' [scale-aware]: "
          f"{'ACCEPTED (62% is a legit r-squared rendering; binding unchecked)' if ok else 'rejected'}")


# ----------------------------------------------------------------- part 5 ---
FORBIDDEN_PLAIN = [
    r"\bshrinkage\b", r"\bcovariance\b", r"\bOLS\b", r"R²",
    r"\bR-squared\b", r"\bstandard error\b", r"\bestimator\b",
    r"\bregression\b", r"\bconfidence interval\b", r"\bkurtosis\b",
    r"\bLedoit\b", r"\bMarkowitz\b", r"\bChoueifaty\b", r"\bCAPM\b",
    r"\bpro[- ]forma\b", r"\beigen\w*", r"\bquadratic\b",
    r"\bsampling error\b", r"\bheteroskedastic\w*", r"\bJPM\b",
]
HEADLINE_WORD_CAP = 16


def register_check(section_id, text):
    """Structural register check: forbidden technical lexicon in plain
    sections (F1/F2/F5) + word cap per F1 headline. Returns list of hits."""
    hits = []
    if section_id in ("F1", "F2", "F5"):
        for pat in FORBIDDEN_PLAIN:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                hits.append(f"lexicon:{m.group(0)}")
    if section_id == "F1":
        for line in text.splitlines():
            if line.strip() and len(line.split()) > HEADLINE_WORD_CAP:
                hits.append(f"headline>{HEADLINE_WORD_CAP}w: '{line.strip()[:50]}...'")
    return hits


GOOD_F2 = [
    "Your portfolio has moved about 23% a year, versus 15% for the market. "
    "Nine holdings behave like roughly two independent bets - they tend to "
    "rise and fall together. NVDA alone accounts for 62% of the swings at "
    "30% of the money. These figures come from the last 126 trading days of "
    "each holding's own history, so treat them as estimates.",

    "This book swings harder than the market: about 23% a year against the "
    "benchmark's 15%. Diversification is thinner than the holding count "
    "suggests - 9 names, but closer to 2 independent bets. One position, "
    "NVDA, drives 62% of the risk. All numbers describe the last 126 "
    "trading days.",

    "Day to day, this portfolio moves about one and a half times as much as "
    "the market. Most of that movement comes from a single name. Your nine "
    "holdings largely rise and fall together, so they spread the risk less "
    "than the count implies. The window behind these numbers is 126 trading "
    "days; shorter histories were excluded.",

    "Risk sits well above the market's: 23% annualised versus 15%. The book "
    "is concentrated - NVDA carries 62% of the risk with 30% of the value. "
    "Spreading money across similar names has not added real variety: 1.8 "
    "effective independent bets from 9 positions. Figures cover 126 trading "
    "days and are estimates, not guarantees.",

    "Your holdings moved together through most of the window, so the "
    "portfolio swung about 23% at an annual pace. The market swung 15% over "
    "the same days. A tenth of the book is cash, which softens every number "
    "slightly. The window is 126 trading days - long enough to be useful, "
    "short enough to deserve caution.",

    "The headline: more risk than the market, most of it from one name. "
    "Volatility runs near 23% a year against the market's 15%. NVDA "
    "contributes 62% of the total swing. With nine names acting like two "
    "bets, adding lookalike positions will not calm the book. Based on 126 "
    "trading days of history.",

    "We have limited confidence in the beta reading because the market "
    "explains only 62% of this book's day-to-day moves; read it with care. "
    "Overall risk is about 23% a year, versus 15% for the market. NVDA is "
    "the dominant source of swing. Numbers reflect the last 126 trading "
    "days only.",

    "This portfolio takes noticeably more risk than the index it tracks. "
    "The gap - 23% versus 15% annualised - comes mostly from one large "
    "position rather than from the market itself. Nine holdings, but they "
    "act like two. The figures use 126 trading days of history and will "
    "firm up as more data accumulates.",

    "Concentration is the story here: 62% of your risk sits in 30% of your "
    "money. Total movement runs around 23% a year, half again the market's "
    "15%. The rest of the book adds little variety. All estimates are drawn "
    "from a 126-trading-day window.",

    "Your risk level is elevated but explainable: one large position and a "
    "cluster of similar names. Expect swings near 23% a year while the "
    "market does 15%. Effective diversification is about 2 bets, not 9. "
    "These are estimates over 126 trading days; they carry sampling wobble.",
]


def part5():
    print("=" * 72)
    print("PART 5 - structural register check (F19)")
    fp = 0
    for i, para in enumerate(GOOD_F2):
        hits = register_check("F2", para)
        if hits:
            fp += 1
            print(f"  good F2 #{i}: FLAGGED {hits}")
    print(f"false positives on 10 plausible good F2 paragraphs: {fp}/10")

    tech_leak = ("Covariance was estimated with Ledoit-Wolf shrinkage; the "
                 "OLS beta has R² of 0.62.")
    print(f"true-positive sanity (tech leak into F2): "
          f"{register_check('F2', tech_leak)}")

    f1_naive = "Beta 1.42 (R² = 0.62, low explanatory power)"
    f1_plain = ("Beta 1.42 - the market explains only 62% of this book's "
                "day-to-day moves")
    print(f"CR-mandated F1 'R² flag surfaced', technical rendering: "
          f"{register_check('F1', f1_naive) or 'PASS'}")
    print(f"same flag, plain-language rendering: "
          f"{register_check('F1', f1_plain) or 'PASS'}")

    f1_long = ("Your portfolio volatility of 23.1% annualised over the last "
               "126 trading days is higher than the benchmark volatility of "
               "14.9% annualised over the same window")
    print(f"overlong F1 headline ({len(f1_long.split())} words): "
          f"{register_check('F1', f1_long) or 'PASS'}")

    f3_tech = "F3 text carrying every technical term"
    print(f"F3 exempt from lexicon (technical register allowed): "
          f"{register_check('F3', F3_TEXT) or 'PASS'}")


if __name__ == "__main__":
    part1()
    part2()
    part3()
    part4()
    part5()
