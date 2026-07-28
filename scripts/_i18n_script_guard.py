"""Deterministic foreign-script leak detector shared by the LAN translate scripts.

The in-house model (Qwen3.6-35B-A3B-NVFP4, on-prem vLLM) occasionally
code-switches mid-generation: a Chinese, Cyrillic or Japanese word glued into
otherwise-correct Arabic/Malay text, sometimes cutting an Arabic word in half
to do it (e.g. "بنفس الق因为它们" instead of "بنفس القدر"). Confirmed at a
~3-4% rate across both a from-scratch corpus pass and a retranslation pass,
in prose, quiz answers, and JSON content fields alike (DEF144) — this is a
property of the model's generation, not a one-off. An LLM verifier catching
it is a matter of luck, not design; this needs none, since legitimate ar/ms
text never contains these scripts.
"""

import re

_FOREIGN_SCRIPTS = re.compile(
    "["
    "一-鿿㐀-䶿豈-﫿"  # CJK ideographs (+ compatibility)
    "぀-ヿㇰ-ㇿ"  # hiragana / katakana
    "가-힣"  # hangul
    "Ѐ-ӿ"  # cyrillic
    "฀-๿"  # thai
    "ऀ-ॿ"  # devanagari
    "]"
)
_ARABIC_SCRIPT = re.compile("[؀-ۿݐ-ݿࢠ-ࣿ]")


def foreign_script_leak(text: str, locale: str) -> str | None:
    """Return a short snippet around the first offending character, or None."""
    m = _FOREIGN_SCRIPTS.search(text)
    if not m and locale == "ms":
        m = _ARABIC_SCRIPT.search(text)
    if not m:
        return None
    start = max(0, m.start() - 6)
    return text[start : m.start() + 10]
