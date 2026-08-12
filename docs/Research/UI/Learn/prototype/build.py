"""Inline the subsetted AMI faces into the Learn-surface research prototype.

Same mechanism and same reason as the UI v0.2 prototypes' build.py: the built
file is opened as a private claude.ai Artifact, whose CSP blocks every external
host, so a hosted-font @import would silently fall back and the review would be
of the wrong typeface.

The two faces are Inter + JetBrains Mono — the app's own bundled cold-launch
fallbacks (`mobile/assets/fonts/`), subsetted to the Latin range this page sets.
Family names are `AMI Sans` / `AMI Mono`, matching the sibling prototypes.

Source of truth is `template_lesson_modes.html`; never hand-edit the output.
Regenerate after editing the template:

    python "docs/Research/UI/Learn/prototype/build.py"

Subsets are cached in `.fonts/` (seeded from the UI v0.2 prototype), so the
build is offline-repeatable and needs `pyftsubset` only when the cache is cold.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
FONT_SRC = REPO / "mobile" / "assets" / "fonts"
CACHE = HERE / ".fonts"

# Latin + the punctuation this page sets. Arrows for the deck nav, ✓ for the
# finish state, × / − for the arithmetic, ≥ for the density table.
UNICODES = (
    "U+0020-007E,U+00A0,U+00B0,U+00B7,U+00D7,U+2013,U+2014,"
    "U+2018,U+2019,U+201C,U+201D,U+2022,U+2026,"
    "U+2190,U+2192,U+2212,U+2264,U+2265,U+25CF,U+2713,U+2717"
)

FACES = [
    ("Inter/Inter-Regular", "AMI Sans", 400, "normal"),
    ("Inter/Inter-SemiBold", "AMI Sans", 600, "normal"),
    ("Inter/Inter-Bold", "AMI Sans", 700, "normal"),
    ("JetBrainsMono/JetBrainsMono-Regular", "AMI Mono", 400, "normal"),
    ("JetBrainsMono/JetBrainsMono-Bold", "AMI Mono", 700, "normal"),
]

PAGES = [
    ("template_lesson_modes.html", "lesson_modes.html"),
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
    fonts = "\n".join(blocks)

    for tpl_name, out_name in PAGES:
        template = (HERE / tpl_name).read_text(encoding="utf-8")
        if "/*@FONTS@*/" not in template:
            sys.exit(f"{tpl_name} has no /*@FONTS@*/ placeholder")
        out = template.replace("/*@FONTS@*/", fonts)
        (HERE / out_name).write_text(out, encoding="utf-8")
        print(f"{out_name} written — {len(out) / 1024:.0f} KB "
              f"({total / 1024:.0f} KB of subsetted faces)")


if __name__ == "__main__":
    main()
