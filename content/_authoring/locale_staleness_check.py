"""Cross-locale staleness auditor — the guard half of DEF105 (CR060 Phase 6).

DEF105's failure class: an `.en.mdx` lesson is edited *after* its `.ar`/`.ms`
siblings were translated, so the translation now teaches something the English
no longer says. It is NOT the CR083 corruption class (those fail to parse) and
NOT ordinary translation lag (new EN, no sibling → EN fallback). It is *old
translated content actively contradicting new EN content*, silently, across a
locale boundary — and the two existing gates miss it:

  - `updated_at` is useless here: the CR083 i18n sync bumped every sibling's
    `updated_at` to the sync date regardless of whether the BODY was retranslated
    (355.ar and 204.ar both read 2026-07-25 over a stale body).
  - the CR087 serving gate only compares quiz *structure* (count / option count /
    answer_index). A rewrite that keeps the same keys but changes the prose sails
    straight through — DEF105's exact words: "these parse fine and pass the
    serving-time integrity gate."

So this guard is content-based. Two mechanisms:

  1. `source_sha` (precise, going-forward). A translation should carry, in its
     frontmatter, `source_sha: "<12-hex>"` = the hash of the EN BODY it was
     translated from. This guard recomputes the EN body hash; a mismatch means
     the EN changed since translation → STALE. Language-agnostic and exact. The
     CR083 translation pipeline (`translate_*_lan.py`) should stamp it; until it
     does, siblings report as UNSTAMPED and fall to mechanism 2.

  2. Anchor divergence (heuristic, works on today's data with no pipeline change).
     Translations keep certain tokens verbatim — tickers, numbers, URLs,
     `<Lesson id>`/`<ChatWith agent>`/`<Term id>` ids, quiz `answer={n}`. If the
     EN's anchor multiset and the sibling's diverge past a threshold, the
     translation predates the current EN. This is what flags the DEF105 cohort +
     355 today.

Report-only (does not fail a build): promote to a corpus pytest once the DEF105
cohort is retranslated and stamped, per failure_patterns.md (guard lands with the
fix). Prints the `source_sha` for every EN lesson so the pipeline can adopt it.

    python3 content/_authoring/locale_staleness_check.py
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LESSONS = ROOT / "content" / "lessons"
LOCALES = ("ar", "ms")

_FM = re.compile(r"^---\n.*?\n---\n", re.S)
_SRC_SHA_KEY = re.compile(r'^source_sha:\s*"?([0-9a-f]{6,})"?', re.M)

# Structural ids a translation keeps byte-identical — divergence here is a
# near-certain staleness signal (never localized), so they carry full weight.
_ID_PATTERNS = [
    re.compile(r'<Lesson\s+id="([^"]+)"'),
    re.compile(r'<ChatWith\s+agent="([^"]+)"'),
    re.compile(r'<Term\s+id="([^"]+)"'),
    re.compile(r'<Animation\s+name="([^"]+)"'),
    re.compile(r"(https?://[^\s)\"']+)"),
]
_ANSWER = re.compile(r"answer=\{(\d)\}")
_NUM = re.compile(r"\$?\d[\d,]*\.?\d*%?")

# Curated ticker vocabulary — real symbols used across the corpus. Matching only
# these (not any ALLCAPS token) keeps English/AR/MS caps *words* out of the signal:
# "BLOCK"/"BUY"/"PASS" are prose that gets translated; "GOOGL"/"SPUS" are not.
_TICKERS = {
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "TSLA", "AMZN", "AMD", "INTC",
    "NFLX", "AVGO", "JPM", "BAC", "WFC", "KO", "PEP", "XOM", "CVX", "PG", "JNJ",
    "SPY", "QQQ", "XLK", "XLF", "VIX", "SPUS", "HLAL", "BRK", "IVV", "SCHD", "VGK",
    "MAYBANK", "PBBANK", "CIMB", "TENAGA", "PETRONAS", "PCHEM", "TOPGLOV", "AIRASIA",
    "CAPITALA", "INGN", "SERBA",
}


def body_of(text: str) -> str:
    return _FM.sub("", text, count=1)


def norm_sha(body: str) -> str:
    collapsed = re.sub(r"\s+", " ", body).strip()
    return hashlib.sha256(collapsed.encode("utf-8")).hexdigest()[:12]


def _norm_num(tok: str) -> str | None:
    s = tok.replace("$", "").replace(",", "").replace("%", "").strip(".")
    return s if s and any(c.isdigit() for c in s) else None


# snake_case code identifiers (Mandate fields, config keys) — kept verbatim in a
# faithful translation, so a token the EN dropped but the sibling keeps is the
# DEF105 signal itself (e.g. `cooldown_after_stop_minutes`, `max_position_pct`).
_CODE = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+){1,5})\b")
# lesson-id-shaped snake_case (e.g. 348_the_business_activity_screen) is already
# captured via <Lesson id>; exclude the bare-word prose false-friends.
_CODE_STOP = {"e_g", "i_e", "vs_", "profit_and", "risk_and"}


def anchors(body: str) -> set[str]:
    """Language-invariant anchors, tagged so we never compare across kinds."""
    out: set[str] = set()
    for pat in _ID_PATTERNS:
        for m in pat.findall(body):
            out.add("id:" + (m if isinstance(m, str) else m[0]))
    for a in _ANSWER.findall(body):
        out.add("ans:" + a)
    for tok in re.findall(r"\b[A-Z]{2,8}\b", body):
        if tok in _TICKERS:
            out.add("tkr:" + tok)
    for tok in _CODE.findall(body):
        if tok in _CODE_STOP or re.match(r"^\d", tok):
            continue
        out.add("code:" + tok)
    for tok in _NUM.findall(body):
        n = _norm_num(tok)
        if n is not None:
            out.add("num:" + n)
    return out


def source_sha_of(text: str) -> str | None:
    m = _SRC_SHA_KEY.search(text)
    return m.group(1) if m else None


def scan() -> int:
    stale: list[tuple[str, str, str]] = []
    unstamped: list[tuple[str, str]] = []
    en_shas: dict[str, str] = {}

    for enf in sorted(LESSONS.glob("*.en.mdx")):
        stem = enf.name[: -len(".en.mdx")]
        en_text = enf.read_text()
        en_body = body_of(en_text)
        en_sha = norm_sha(en_body)
        en_shas[stem] = en_sha
        en_anchor = anchors(en_body)

        for loc in LOCALES:
            sib = LESSONS / f"{stem}.{loc}.mdx"
            if not sib.exists():
                continue
            sib_text = sib.read_text()
            stamped = source_sha_of(sib_text)
            if stamped is not None:
                if stamped != en_sha:
                    stale.append((f"{stem}.{loc}", "source_sha mismatch",
                                  f"stamped {stamped} != EN {en_sha}"))
                continue
            # unstamped → anchor-divergence heuristic. Weight HARD anchors
            # (structural ids, tickers, code identifiers, quiz keys) above numbers,
            # whose formatting/rounding is the noise source. Flag when the EN
            # dropped or gained a hard anchor the sibling doesn't share — that only
            # happens when the EN was edited after translation.
            sib_anchor = anchors(body_of(sib_text))
            diff = (en_anchor - sib_anchor) | (sib_anchor - en_anchor)
            hard = sorted(a for a in diff if a.split(":", 1)[0] in ("id", "code", "tkr", "ans"))
            nums = sorted(a for a in diff if a.startswith("num:"))
            certain = any(a.startswith(("id:", "code:")) for a in hard)
            if certain or len(hard) >= 2 or len(nums) >= 6:
                sig = hard if hard else nums
                stale.append((f"{stem}.{loc}",
                              f"likely stale (unstamped; hard={len(hard)} num={len(nums)})",
                              "diverging anchors: [" + ", ".join(sig[:8]) + "]"))
            else:
                unstamped.append((f"{stem}.{loc}", f"unstamped; anchors align (hard={len(hard)} num={len(nums)})"))

    print(f"# Cross-locale staleness audit — {len(en_shas)} EN lessons, locales {LOCALES}\n")
    print(f"## STALE — translation contradicts current EN ({len(stale)})\n")
    for name, why, detail in stale:
        print(f"  {name}\n     {why}\n     {detail}")
    print(f"\n  siblings flagged stale: {len(stale)}")
    print(f"\n## UNSTAMPED but anchor-aligned ({len(unstamped)}) — can't prove current; adopt source_sha to close\n")
    print(f"  (count only: {len(unstamped)} siblings)")
    return len(stale)


if __name__ == "__main__":
    sys.exit(1 if scan() else 0)
