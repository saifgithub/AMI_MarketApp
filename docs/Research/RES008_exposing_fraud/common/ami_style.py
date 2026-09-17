"""
AMI "Hex-Reinforced Precision" chart style for the RES008 video chart packs.

Every figure that goes on screen is drawn through this module so the series has
one look: dark slate canvas, the design system's semantic colours, Inter for
text and JetBrains Mono for numbers, 16:9 at 1920x1080. Tokens are copied from
the AMI design system's colors_and_type.css; fonts are the two families the
mobile app already bundles (both are in the design system's fallback stack).

Rules the chart packs follow (enforced by convention, checked in review):
  * a chart shows measured numbers only, read from the claim's out/ files;
  * every figure carries a source footer naming the file the numbers came from;
  * post-hoc or not-pre-registered material is stamped with `stamp()`;
  * no channel, creator, platform interface or third-party thumbnail, ever.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# -- design tokens (colors_and_type.css) --------------------------------------
BG = "#0f172a"
PANEL = "#111827"
CARD = "#152845"
BORDER = "#374151"
TEXT = "#f3f4f6"
MUTED = "#94a3b8"
DIM = "#64748b"
BLUE = "#3b82f6"
CYAN = "#06b6d4"
GREEN = "#10b981"
AMBER = "#f59e0b"
RED = "#ef4444"
PURPLE = "#8b5cf6"
PINK = "#ec4899"

# Semantic roles, so every episode uses the same colour for the same idea.
CLAIM = AMBER        # the number as advertised
MEASURED = BLUE      # what we measured
BENCHMARK = MUTED    # buy-and-hold, "no change", the placebo band
GOOD = GREEN
BAD = RED
SERIES = [BLUE, CYAN, PURPLE, PINK, AMBER, GREEN, RED]

FIGSIZE = (16, 9)
DPI = 120  # 16 x 9 in at 120 dpi = 1920 x 1080

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FONT_DIR = _REPO_ROOT / "mobile" / "assets" / "fonts"
FONT_UI = "Inter"
FONT_MONO = "JetBrains Mono"


def _register_fonts() -> tuple[str, str]:
    ui, mono = "DejaVu Sans", "DejaVu Sans Mono"
    for ttf in sorted(_FONT_DIR.glob("*/*.ttf")):
        font_manager.fontManager.addfont(str(ttf))
    names = {f.name for f in font_manager.fontManager.ttflist}
    if FONT_UI in names:
        ui = FONT_UI
    if FONT_MONO in names:
        mono = FONT_MONO
    return ui, mono


def apply() -> None:
    """Set matplotlib rcParams. Call once at the top of a chart script."""
    ui, _ = _register_fonts()
    plt.rcParams.update(
        {
            "figure.figsize": FIGSIZE,
            "figure.dpi": DPI,
            "savefig.dpi": DPI,
            "figure.facecolor": BG,
            "savefig.facecolor": BG,
            "axes.facecolor": BG,
            "axes.edgecolor": BORDER,
            "axes.labelcolor": MUTED,
            "axes.titlecolor": TEXT,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.prop_cycle": matplotlib.cycler(color=SERIES),
            "grid.color": BORDER,
            "grid.alpha": 0.45,
            "grid.linewidth": 0.8,
            "text.color": TEXT,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "font.family": ui,
            "font.size": 20,
            "axes.titlesize": 30,
            "axes.titleweight": "bold",
            "axes.labelsize": 20,
            "xtick.labelsize": 18,
            "ytick.labelsize": 18,
            "legend.fontsize": 18,
            "legend.frameon": False,
            "lines.linewidth": 3.0,
        }
    )


def mono() -> str:
    """Font family for numbers on screen."""
    names = {f.name for f in font_manager.fontManager.ttflist}
    return FONT_MONO if FONT_MONO in names else "DejaVu Sans Mono"


LEFT, RIGHT = 0.10, 0.95


def _shrink_to_fit(fig, text_obj, max_width_frac: float, min_size: int = 16) -> None:
    renderer = fig.canvas.get_renderer()
    while (
        text_obj.get_window_extent(renderer).width > max_width_frac * fig.bbox.width
        and text_obj.get_fontsize() > min_size
    ):
        text_obj.set_fontsize(text_obj.get_fontsize() - 1)


def new_figure(title: str, subtitle: str | None = None, nrows: int = 1, ncols: int = 1, **kwargs):
    """A 1920x1080 figure with the series' title block. Returns (fig, axes).
    Title and subtitle shrink to fit the frame; keep titles to one short sentence anyway."""
    fig, axes = plt.subplots(nrows, ncols, figsize=FIGSIZE, **kwargs)
    fig.subplots_adjust(left=LEFT, right=RIGHT, top=0.80, bottom=0.17)
    head = fig.text(LEFT, 0.93, title, fontsize=36, fontweight="bold", color=TEXT, ha="left", va="center")
    _shrink_to_fit(fig, head, RIGHT - LEFT)
    if subtitle:
        sub = fig.text(LEFT, 0.865, subtitle, fontsize=22, color=MUTED, ha="left", va="center")
        _shrink_to_fit(fig, sub, RIGHT - LEFT)
    return fig, axes


def footer(fig, source: str, note: str | None = None) -> None:
    """Source line (bottom-left) and the standing disclaimer (bottom-right)."""
    fig.text(LEFT, 0.055, f"Source: {source}", fontsize=13, color=DIM, ha="left", va="center", family=mono())
    if note:
        fig.text(LEFT, 0.025, note, fontsize=13, color=DIM, ha="left", va="center")
    fig.text(RIGHT, 0.055, "AMI Trade · simulation-only · not investment advice", fontsize=13, color=DIM, ha="right", va="center")


def stamp(fig, text: str = "AFTER THE FACT — NOT PRE-REGISTERED", x: float = RIGHT, y: float = 0.988) -> None:
    """Label for post-hoc or descriptive material. Stays on for as long as the chart is shown.
    Sits in the strip above the title block, fully inside the frame."""
    fig.text(
        x, y, text, fontsize=15, fontweight="bold", color=BG, ha="right", va="top",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": AMBER, "edgecolor": "none"},
    )


def big_number(ax, x: float, y: float, text: str, color: str = TEXT, size: int = 64, **kwargs) -> None:
    """A KPI-style number in the data face, in axes coordinates."""
    ax.text(x, y, text, transform=ax.transAxes, fontsize=size, fontweight="bold", color=color, family=mono(), **kwargs)


def save(fig, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor=BG)
    plt.close(fig)
    return path
