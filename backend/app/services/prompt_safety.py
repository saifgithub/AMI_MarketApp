"""DEF370 (security review M10) — neutralise third-party text before it enters a prompt.

Reddit snippets and news headlines are **attacker-authorable**: anyone can post
one. They are then interpolated into the Social Analyst's and News Analyst's
prompts, which the Room's PM reads. That is textbook indirect prompt injection.

**What the blast radius actually is, stated honestly.** It is bounded — the
deterministic safety floor is not an LLM and cannot be talked out of a refusal,
and nothing auto-executes; a compromised analyst can mislead the PM's *opinion*,
not open a position. That is why the review graded it Medium and not Critical.
It is not a reason to leave it: an analyst that can be made to say "ignore your
prior instructions, this is a generational buy" is teaching a user something
false, and the reasoning IS the product.

**Why this strips structure rather than escaping content.** The vector is not
the words, it is the FRAMING: a line break plus a section delimiter lets
attacker text impersonate a new prompt section, and our own prompts draw their
section headers with exactly that glyph (`--- LIVE NEWS -- AAPL ---`, in
U+2500). Collapse the structure and the text stays readable while losing its
ability to pose as scaffolding. No phrase blocklist is involved, because a
phrase blocklist is a blocklist, and `CLAUDE.md` is explicit that a
prompt-level instruction is not a control.
"""

from __future__ import annotations

# Characters that let third-party text impersonate our own prompt structure.
# U+2500 is the glyph our own section headers are drawn with; the rest are the
# box-drawing and block forms an attacker would reach for next.
_STRUCTURE_GLYPHS = (
    "\u2500\u2501\u2502\u2503\u2504\u2505\u2508\u2509\u254c\u254d"
    "\u2550\u2551\u2554\u2557\u255a\u255d\u2560\u2563\u2566\u2569"
    "\u256c\u2580\u2584\u2588\u258c\u2590\u2591\u2592\u2593"
)

def sanitize_for_prompt(text: object, *, limit: int | None = None) -> str:
    """One line of safe-to-interpolate text, or "".

    Every line break becomes a space, every structural glyph is dropped, runs
    of whitespace collapse, and the result is optionally truncated. The text
    survives; its ability to forge a prompt section does not.

    `limit` truncates AFTER sanitising, deliberately: truncating first can cut
    mid-escape and leave a fragment at the boundary, and the caller's intent is
    a cap on readable length, not on bytes of raw input.
    """
    if text is None:
        return ""
    s = str(text)
    s = s.translate({ord(g): None for g in _STRUCTURE_GLYPHS})
    # `str.split()` with no argument splits on EVERY Unicode whitespace, which
    # is verified to include the separators an injection would reach for past
    # a naive newline strip: U+2028 LINE SEPARATOR, U+2029 PARAGRAPH
    # SEPARATOR, U+0085 NEL, vertical tab and form feed. An explicit
    # line-break list was written here first and then removed — a mutation
    # that emptied it changed no behaviour, which is the definition of dead
    # code, and dead code in a security control is worse than none: it reads
    # as the thing doing the work.
    s = " ".join(s.split())
    if limit is not None and len(s) > limit:
        s = s[:limit].rstrip()
    return s
