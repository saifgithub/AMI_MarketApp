"""ISS002/CR208 Layer 3 — wire models nothing on the client ever parses.

Grafted from `haiku4.5`'s proposal. A Dart model whose `fromJson` has no caller
is invisible to the capture half by construction: a parser nothing invokes
produces no observation, so it lands in `UNVERIFIED` beside surfaces that are
merely untested, and reads as ordinary missing coverage rather than dead code.

**Two corrections were needed before this could work, both measured.**

1. *The prototype's reachability test could not fail.* It searched for
   `\\bClassName\\s*\\(`, which matches the class's own constructor in its own
   declaring file, so essentially nothing was ever flagged.

2. *Tear-offs are calls.* Restricting the search to `X.fromJson(` — with
   parentheses — misses `.map(GameBoardRow.fromJson)`, which is how this
   codebase feeds list parsers. That single omission reported `GameBoardRow` as
   dead when `games.dart:1476` parses with it on every board fetch. Verified by
   hand before it was believed.

**What it finds today: nothing.** 132 Dart classes carry a `fromJson`; every one
of them has a caller. That is the honest current answer and it is recorded
rather than hidden, because a guard that has never fired is worth exactly as
much as its next firing — and knowing it currently fires zero times is what
stops a future zero from being read as proof.

**Correcting the verdict:** ISS002's `VERDICT.md` says this layer "is the only
proposal that directly catches instance 1 (`OptionProposalTicket`) by
construction". It cannot. `OptionProposalTicket` is a Flutter *Widget*
(`mobile/lib/widgets/sim/option_proposal_ticket.dart:65`) with no `fromJson`
factory at all, so no scan over wire models could ever reach it. The layer is
still worth having — it covers a real class of defect cheaply — but not for the
reason the verdict gives.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LIB = REPO / "mobile" / "lib"

_FACTORY = re.compile(r"factory\s+(\w+)\.fromJson")


def _dart_sources() -> dict[Path, str]:
    return {p: p.read_text(encoding="utf-8") for p in sorted(LIB.rglob("*.dart"))}


def declared(sources: dict[Path, str] | None = None) -> dict[str, str]:
    """class name -> declaring file name."""
    sources = sources if sources is not None else _dart_sources()
    out: dict[str, str] = {}
    for path, text in sources.items():
        for m in _FACTORY.finditer(text):
            out.setdefault(m.group(1), path.name)
    return out


def callers(cls: str, sources: dict[Path, str]) -> int:
    """How many times `cls.fromJson` is referenced as something other than its
    own declaration. `\\b…\\.fromJson\\b` with no trailing `\\(` on purpose —
    a tear-off passed to `.map` is a caller."""
    pattern = re.compile(rf"\b{re.escape(cls)}\.fromJson\b")
    total = 0
    for text in sources.values():
        for m in pattern.finditer(text):
            if text[max(0, m.start() - 30) : m.start()].rstrip().endswith("factory"):
                continue
            total += 1
    return total


def find_unreachable() -> list[str]:
    sources = _dart_sources()
    return sorted(
        cls for cls in declared(sources) if callers(cls, sources) == 0
    )


if __name__ == "__main__":
    sources = _dart_sources()
    decl = declared(sources)
    dead = find_unreachable()
    print(f"{len(decl)} Dart classes with a fromJson factory")
    print(f"{len(dead)} with no caller anywhere in mobile/lib")
    for c in dead:
        print("  ", c)
