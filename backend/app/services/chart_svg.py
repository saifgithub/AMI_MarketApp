"""Hand-rolled SVG line-chart renderer for the admin chart endpoint (CR200-R003).

Dependency-free by design — the CR explicitly rejects matplotlib/plotly — and
fully deterministic so the conversational admin agent can embed the rendered
charts as image links in chat. CR040 honesty rule: empty input renders an
explicit "no data" empty state, while an all-zero series is real data and
renders as a flat line, never an empty state.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

_WIDTH = 800
_HEIGHT = 300
_PLOT_LEFT = 56
_PLOT_RIGHT = 744
_PLOT_TOP = 44
_PLOT_BOTTOM = 252

_BG = "#0d1117"
_AXIS = "#30363d"
_TEXT = "#8b949e"
_TITLE = "#c9d1d9"
_LINE = "#58a6ff"

_EMPTY_TEXT = "no data"


def _empty_svg(title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {_HEIGHT}" '
        f'width="{_WIDTH}" height="{_HEIGHT}" role="img">'
        f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG}"/>'
        f'<text x="{_PLOT_LEFT}" y="28" fill="{_TITLE}" font-size="14">{escape(title)}</text>'
        f'<text x="{_WIDTH // 2}" y="{_HEIGHT // 2}" fill="{_TEXT}" font-size="14" '
        f'text-anchor="middle">{_EMPTY_TEXT}</text>'
        f"</svg>"
    )


def render_line_chart(title: str, labels: list[str], values: list[int]) -> str:
    """Render one dark-theme line chart as an SVG string.

    Empty `labels`/`values` → the "no data" empty state. A length mismatch is
    a programming error, not a data condition — ValueError, never a guess.
    """
    if not labels or not values:
        return _empty_svg(title)
    if len(labels) != len(values):
        raise ValueError(f"labels/values length mismatch: {len(labels)} vs {len(values)}")

    n = len(values)
    vmax = max(values)
    vmin = min(values)

    def _y(v: int) -> float:
        if vmax == vmin:
            # Degenerate range: an all-zero series sits on the zero baseline,
            # a flat non-zero series centres in the plot — honest flat data
            # either way, never a fabricated shape.
            return float(_PLOT_BOTTOM) if vmin == 0 else (_PLOT_TOP + _PLOT_BOTTOM) / 2
        return _PLOT_BOTTOM - (v - vmin) * (_PLOT_BOTTOM - _PLOT_TOP) / (vmax - vmin)

    def _x(i: int) -> float:
        if n == 1:
            return (_PLOT_LEFT + _PLOT_RIGHT) / 2
        return _PLOT_LEFT + i * (_PLOT_RIGHT - _PLOT_LEFT) / (n - 1)

    points = " ".join(f"{_x(i):.1f},{_y(v):.1f}" for i, v in enumerate(values))
    max_i = values.index(vmax)
    min_i = values.index(vmin)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {_HEIGHT}" '
        f'width="{_WIDTH}" height="{_HEIGHT}" role="img">',
        f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG}"/>',
        f'<text x="{_PLOT_LEFT}" y="28" fill="{_TITLE}" font-size="14">{escape(title)}</text>',
        f'<line x1="{_PLOT_LEFT}" y1="{_PLOT_TOP}" x2="{_PLOT_LEFT}" y2="{_PLOT_BOTTOM}" stroke="{_AXIS}"/>',
        f'<line x1="{_PLOT_LEFT}" y1="{_PLOT_BOTTOM}" x2="{_PLOT_RIGHT}" y2="{_PLOT_BOTTOM}" stroke="{_AXIS}"/>',
        f'<text x="{_PLOT_LEFT - 6}" y="{_PLOT_TOP + 4}" fill="{_TEXT}" font-size="10" text-anchor="end">{vmax}</text>',
        f'<text x="{_PLOT_LEFT - 6}" y="{_PLOT_BOTTOM}" fill="{_TEXT}" font-size="10" text-anchor="end">{vmin}</text>',
        f'<polyline points="{points}" fill="none" stroke="{_LINE}" stroke-width="2"/>',
        f'<text x="{_x(max_i):.1f}" y="{_y(vmax) - 8:.1f}" fill="{_TEXT}" font-size="10" text-anchor="middle">max {vmax}</text>',
        f'<text x="{_x(min_i):.1f}" y="{_y(vmin) + 16:.1f}" fill="{_TEXT}" font-size="10" text-anchor="middle">min {vmin}</text>',
    ]
    if n == 1:
        parts.append(f'<circle cx="{_x(0):.1f}" cy="{_y(values[0]):.1f}" r="3" fill="{_LINE}"/>')
        parts.append(
            f'<text x="{_x(0):.1f}" y="{_PLOT_BOTTOM + 18}" fill="{_TEXT}" '
            f'font-size="10" text-anchor="middle">{escape(labels[0])}</text>'
        )
    else:
        parts.append(
            f'<text x="{_x(0):.1f}" y="{_PLOT_BOTTOM + 18}" fill="{_TEXT}" '
            f'font-size="10" text-anchor="start">{escape(labels[0])}</text>'
        )
        parts.append(
            f'<text x="{_x(n - 1):.1f}" y="{_PLOT_BOTTOM + 18}" fill="{_TEXT}" '
            f'font-size="10" text-anchor="end">{escape(labels[-1])}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)
