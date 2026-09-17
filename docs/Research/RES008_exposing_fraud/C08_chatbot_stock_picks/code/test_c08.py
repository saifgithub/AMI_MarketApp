"""C08 tests: the vectorised random-portfolio draw against a slow explicit loop,
and the ticker parser against hand-written reply snippets covering the formats
actually seen in chatbot replies (parentheses, bold, name-only, a refusal, and
lowercase/short noise words that must not become tickers).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

import importlib

_part1 = importlib.import_module("02_random_portfolios")
_part3 = importlib.import_module("03_parse_picks")

draw_portfolio_returns = _part1.draw_portfolio_returns
analytic_p_ge3_of4 = _part1.analytic_p_ge3_of4
extract_picks = _part3.extract_picks


def _slow_portfolio_returns(available_rets, n_draws, portfolio_size, seed):
    rng = np.random.default_rng(seed)
    n_available = len(available_rets)
    out = np.empty(n_draws)
    for d in range(n_draws):
        idx = rng.choice(n_available, size=portfolio_size, replace=False)
        total = 0.0
        for i in idx:
            total += available_rets[i]
        out[d] = total / portfolio_size
    return out


def test_vectorised_matches_slow_loop_same_seed_stream():
    # Both paths must consume the RNG the same way for exact reproducibility:
    # the vectorised path draws one (n_draws x n_available) uniform matrix and
    # argsorts each row; reproduce that exact sequence in the slow loop using
    # rng.random(n_available) + argsort per draw so this test checks the
    # ARITHMETIC (mean-of-selected-returns), not two different RNG algorithms.
    available_rets = np.array([0.10, -0.05, 0.20, 0.00, 0.15, -0.10, 0.30, 0.02, -0.02, 0.08, 0.01, -0.03])
    n_draws = 500
    portfolio_size = 5
    seed = 123

    rng_vec = np.random.default_rng(seed)
    vec_result = draw_portfolio_returns(available_rets, n_draws, portfolio_size, rng_vec)

    rng_slow = np.random.default_rng(seed)
    slow_result = np.empty(n_draws)
    for d in range(n_draws):
        keys = rng_slow.random(len(available_rets))
        idx = np.argsort(keys)[:portfolio_size]
        acc = 0.0
        for i in idx:
            acc += available_rets[i]
        slow_result[d] = acc / portfolio_size

    np.testing.assert_allclose(vec_result, slow_result, atol=1e-12)


def test_portfolio_returns_are_plain_equal_weight_means():
    # A small, fully-enumerable case: every possible 2-of-4 combination's
    # equal-weight mean must appear among the draws, and every draw's value
    # must equal the mean of exactly 2 of the 4 returns.
    available_rets = np.array([0.10, 0.20, 0.30, 0.40])
    rng = np.random.default_rng(7)
    result = draw_portfolio_returns(available_rets, 2000, 2, rng)

    from itertools import combinations
    possible_means = {round(sum(c) / 2, 10) for c in combinations(available_rets, 2)}
    seen = {round(v, 10) for v in result}
    assert seen.issubset(possible_means)
    assert seen == possible_means  # 2000 draws from C(4,2)=6 combos: all should appear


def test_analytic_p_ge3_of4_half():
    # P(>=3 heads in 4 fair coin flips) = C(4,3)*0.5^4 + C(4,4)*0.5^4 = 5/16
    assert analytic_p_ge3_of4(0.5) == pytest.approx(5.0 / 16.0)


# ---------------------------------------------------------------------------
# Ticker parser
# ---------------------------------------------------------------------------

KNOWN_SYMBOLS = {
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "JPM", "V", "BRK-B",
    "TSM", "GEV",
}
NAME_TO_TICKER = {
    "alphabet": "GOOGL",
    "berkshire hathaway": "BRK-B",
    "facebook": "META",
    "taiwan semiconductor": "TSM",
    "ge vernova": "GEV",
}


def test_parser_extracts_from_parenthetical_tickers():
    text = (
        "## The list\n"
        "| # | Company (Ticker) | Thesis |\n"
        "|---|---|---|\n"
        "| 1 | Microsoft (MSFT) | cloud |\n"
        "| 2 | Alphabet (GOOGL) | search |\n"
        "| 3 | Amazon (AMZN) | e-commerce |\n"
        "| 4 | Meta Platforms (META) | ads |\n"
    )
    picks = extract_picks(text, KNOWN_SYMBOLS, NAME_TO_TICKER)
    assert picks == ["MSFT", "GOOGL", "AMZN", "META"]


def test_parser_extracts_from_bold_tickers():
    text = (
        "## 10 stocks to research\n"
        "| # | Ticker | Company |\n"
        "|---|---|---|\n"
        "| 1 | **NVDA** | NVIDIA |\n"
        "| 2 | **TSM** | Taiwan Semiconductor |\n"
        "| 3 | **JPM** | JPMorgan Chase |\n"
        "| 4 | **GEV** | GE Vernova |\n"
    )
    picks = extract_picks(text, KNOWN_SYMBOLS, NAME_TO_TICKER)
    assert picks == ["NVDA", "TSM", "JPM", "GEV"]


def test_parser_maps_company_name_only_rows():
    text = (
        "## The picks\n"
        "1. Alphabet -- search and cloud\n"
        "2. Berkshire Hathaway -- diversified holding company\n"
        "3. Facebook -- social media and ads\n"
    )
    picks = extract_picks(text, KNOWN_SYMBOLS, NAME_TO_TICKER)
    assert picks == ["GOOGL", "BRK-B", "META"]


def test_parser_handles_numbered_headings_with_blank_lines_between_items():
    # A real reply format: "## 1. Company (TICKER)" headings, one paragraph
    # of thesis each, separated by blank lines -- must not stop at item 1.
    text = (
        "Some caveats before the list.\n\n"
        "## 1. Microsoft (MSFT)\n"
        "Azure growth and recurring revenue.\n\n"
        "## 2. Amazon (AMZN)\n"
        "AWS margins and advertising.\n\n"
        "## 3. Alphabet (GOOGL)\n"
        "Search and cloud optionality.\n\n"
        "## 4. JPMorgan Chase (JPM)\n"
        "Best-run large bank.\n"
    )
    picks = extract_picks(text, KNOWN_SYMBOLS, NAME_TO_TICKER)
    assert picks == ["MSFT", "AMZN", "GOOGL", "JPM"]


def test_parser_ignores_prose_bullets_with_one_incidental_company_mention():
    # A "market backdrop" bullet list earlier in the reply mentions "Apple"
    # in passing once -- that must not be mistaken for the picks block; the
    # real table further down is what counts.
    text = (
        "## Market context\n"
        "- The index fell sharply last quarter.\n"
        "- Rates rose all year on inflation fears.\n"
        "- Apple warned on revenue after the close.\n\n"
        "## The picks\n"
        "| # | Company (Ticker) | Thesis |\n"
        "|---|---|---|\n"
        "| 1 | Microsoft (MSFT) | cloud |\n"
        "| 2 | Amazon (AMZN) | e-commerce |\n"
        "| 3 | Alphabet (GOOGL) | search |\n"
        "| 4 | JPMorgan Chase (JPM) | banking |\n"
    )
    picks = extract_picks(text, KNOWN_SYMBOLS, NAME_TO_TICKER)
    assert picks == ["MSFT", "AMZN", "GOOGL", "JPM"]
    assert "AAPL" not in picks


def test_parser_returns_empty_on_refusal():
    text = (
        "I appreciate the question, but I can't recommend specific stocks for you to buy. "
        "Here's why:\n\n1. I'm not a financial advisor.\n2. No one reliably beats the market.\n\n"
        "What I'd suggest instead:\n- Consult a CFP\n- Consider index funds like the S&P 500\n"
    )
    picks = extract_picks(text, KNOWN_SYMBOLS, NAME_TO_TICKER)
    assert picks == []


def test_parser_ignores_lowercase_noise_words_as_tickers():
    text = (
        "## The list\n"
        "| # | Ticker | Company | Why |\n"
        "|---|---|---|---|\n"
        "| 1 | **NVDA** | NVIDIA | Its AI GPUs lead the market; the CUDA moat is IT infrastructure grade, a great pick |\n"
        "| 2 | **AAPL** | Apple | A safe pick |\n"
        "| 3 | **JPM** | JPMorgan Chase | A bank pick |\n"
        "| 4 | **V** | Visa | A payments pick |\n"
    )
    picks = extract_picks(text, KNOWN_SYMBOLS, NAME_TO_TICKER)
    assert picks == ["NVDA", "AAPL", "JPM", "V"]
    assert "AI" not in picks and "IT" not in picks and "A" not in picks


def test_parser_ignores_secondary_hindsight_table():
    # A back-dated reply may append a second "how it actually performed"
    # table after the picks -- only the first (picks) table counts.
    text = (
        "## The 10 picks\n"
        "| # | Stock | Thesis |\n"
        "|---|---|---|\n"
        "| 1 | Microsoft (MSFT) | cloud |\n"
        "| 2 | Amazon (AMZN) | e-commerce |\n"
        "| 3 | Alphabet (GOOGL) | search |\n"
        "| 4 | JPMorgan Chase (JPM) | banking |\n"
        "\n"
        "## How it actually went (Jan 2019 -> end of 2023)\n"
        "| Stock | Multiple | vs S&P 500 |\n"
        "|---|---|---|\n"
        "| NVDA | 14.5x | Far ahead |\n"
        "| AAPL | 4.9x | Far ahead |\n"
    )
    picks = extract_picks(text, KNOWN_SYMBOLS, NAME_TO_TICKER)
    assert picks == ["MSFT", "AMZN", "GOOGL", "JPM"]
    assert "NVDA" not in picks and "AAPL" not in picks
