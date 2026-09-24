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
# U+2500 is the glyph our own section headers are drawn with; the rest of the
# Unicode "Box Drawing" (U+2500-U+257F), "Block Elements" (U+2580-U+259F)
# blocks are exactly the family an attacker would reach for next.
#
# RETRO-SECURITY MINOR-2 (round 2, DEF370) \u2014 this used to be a hand-enumerated
# tuple of individual code points. The auditor threw three glyphs from the SAME
# two Unicode blocks that the list simply hadn't named \u2014 U+2506 "\u2506", U+257C
# "\u257c", U+2574 "\u2574" \u2014 and all three survived. An enumerated allowlist-of-what-
# to-strip has the identical shape as an allowlist-of-what-to-permit: it is
# only as complete as whoever typed it remembered to be. Dropping the whole
# range by CODE POINT rather than by NAME means a glyph nobody thought to type
# is caught by construction, not by being remembered.
_STRUCTURE_GLYPH_RANGES: tuple[tuple[int, int], ...] = (
    (0x2500, 0x259F),  # Box Drawing + Block Elements
)

def _is_structure_glyph(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _STRUCTURE_GLYPH_RANGES)


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
    s = "".join(ch for ch in s if not _is_structure_glyph(ch))
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
