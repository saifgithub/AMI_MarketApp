"""Inline the subsetted AMI faces into the CR134 design-conformance prototype.

`game.html` is committed self-contained on purpose: it is opened as a private
claude.ai Artifact, whose CSP blocks every external host, so a
`@import url(fonts.googleapis.com)` would silently fall back and the review
would be of the wrong typeface.

The two faces are Inter + JetBrains Mono — the app's own bundled cold-launch
fallbacks (`mobile/assets/fonts/`), not Google-hosted copies. Subsetted to the
Latin range this page actually uses, they total ~48 KB.

Regenerate after editing `template.html`:

    python3 docs/forward_planning/CR134_cr109_design_conformance/prototype/build.py

(`python3`, not `python` — the bare name is not on PATH on this workstation.)

Requires `pyftsubset` (fonttools) on PATH; the subsets are cached next to this
script so the build is offline-repeatable once they exist.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FONT_SRC = REPO / "mobile" / "assets" / "fonts"
CACHE = HERE / ".fonts"

# Latin + the punctuation and marks the page sets. Hexagons are clip-paths and
# icons are inline SVG, so no ⬢/⬡ and no U+25xx geometric codepoints are needed
# — finding D23 is that reaching for those is how an icon silently vanishes.
#
# U+2212 (true minus) is in the list because the app writes losses as `−4.2%`,
# not `-4.2%`, and a hyphen substituted for a minus in a P&L figure is the
# prototype quietly disagreeing with the thing it is a prototype of.
UNICODES = (
    "U+0020-007E,U+00A0,U+00B0,U+00B7,U+00D7,U+2013,U+2014,"
    "U+2018,U+2019,U+201C,U+201D,U+2022,U+2026,U+2039,U+203A,"
    "U+2190,U+2192,U+2212,U+2264,U+2265,U+2713,U+2717"
)

FACES = [
    ("Inter/Inter-Regular", "AMI Sans", 400, "normal"),
    ("Inter/Inter-SemiBold", "AMI Sans", 600, "normal"),
    ("Inter/Inter-Bold", "AMI Sans", 700, "normal"),
    ("JetBrainsMono/JetBrainsMono-Regular", "AMI Mono", 400, "normal"),
    ("JetBrainsMono/JetBrainsMono-Bold", "AMI Mono", 700, "normal"),
]


def subset(rel: str) -> Path:
    out = CACHE / (Path(rel).name + ".woff2")
    if out.exists():
        return out
    src = FONT_SRC / f"{rel}.ttf"
    if not src.exists():
        sys.exit(f"missing source face: {src}")
    if not shutil.which("pyftsubset"):
        sys.exit("pyftsubset not on PATH — pip install fonttools[woff]")
    CACHE.mkdir(exist_ok=True)
    subprocess.run(
        [
            "pyftsubset", str(src),
            f"--output-file={out}",
            "--flavor=woff2",
            f"--unicodes={UNICODES}",
            "--layout-features=kern,liga,tnum",
            "--no-hinting",
        ],
        check=True,
    )
    return out


def main() -> None:
    blocks = []
    total = 0
    for rel, family, weight, style in FACES:
        path = subset(rel)
        raw = path.read_bytes()
        total += len(raw)
        b64 = base64.b64encode(raw).decode("ascii")
        blocks.append(
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"font-display:swap;src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
        )

    template = (HERE / "template.html").read_text(encoding="utf-8")
    if "/*@FONTS@*/" not in template:
        sys.exit("template.html has no /*@FONTS@*/ placeholder")
    out = template.replace("/*@FONTS@*/", "\n".join(blocks))
    (HERE / "game.html").write_text(out, encoding="utf-8")
    print(f"game.html written — {len(out) / 1024:.0f} KB ({total / 1024:.0f} KB of subsetted faces)")

    # The page's whole argument is that the game was drawn without the app's
    # geometry, so a build that produced zero clip-paths would be self-refuting.
    clips = out.count("clip-path")
    print(f"clip-path declarations: {clips}" + ("" if clips else "  ← FAILED"))


if __name__ == "__main__":
    main()
