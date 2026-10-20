"""Route-driving graph for the exhaustive crawl (CR264 phase C). Pure: no driver.

The crawl discovers screens by pressing what it sees. That misses a screen when
the press that opens it was abandoned (replay failed), cut by the depth cap, or
gated by state. The control catalogue (`qa/uat/controls/*.yaml`) already says,
per control, where it leads. This module turns that into a directed graph:

    surface --control--> target        (expect = navigate | sheet | dialog)

and plans the cheapest path from a bottom-nav tab to any screen. The crawler
then replays the path, step by step, waiting for each step's target root id.

Three honest limits, all surfaced rather than hidden:

1. **Embedded widgets.** The catalogue has one file per source file, so a
   widget's controls live under the widget's own id (`floor_omnibox`) although
   they render inside a host screen (`floor`). `HOSTS` is that mapping, by hand,
   guarded by an offline test (every host is a real screen id).
2. **`when:` preconditions.** An edge with a `when` is planned (at a penalty)
   but may not exist on the device right now. The crawler tries it; a failed
   attempt re-plans without that edge, and the final reason names the `when`.
3. **Descriptive labels.** Catalogue labels are descriptions (`Inbox bell
   (notifications_outlined icon)`); the rendered label may differ. An edge whose
   id is known matches by id; otherwise by label pattern, else not at all - and
   a screen reachable only through such an edge is reported with that reason.
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field

from crawler.intents import Catalogue, Intent, label_pattern, _norm  # noqa: F401 (label_pattern re-used by the crawler)

NAV_TO_ROOTS: dict[str, tuple[str, ...]] = {
    "ami.nav.floor": ("ami.screen.floor",),
    "ami.nav.portfolio": ("ami.screen.portfolio",),
    "ami.nav.lessons": ("ami.screen.lessons",),
    "ami.nav.you": ("ami.screen.you", "ami.screen.settings"),
    "ami.nav.game": ("ami.screen.games_home",),
}

# Widget surface (catalogue `screen:`) -> the real screens that render it.
HOSTS: dict[str, tuple[str, ...]] = {
    "ami.screen.floor_omnibox": ("ami.screen.floor",),
    "ami.screen.floor_cards": ("ami.screen.floor",),
    "ami.screen.floor_carousel": ("ami.screen.floor",),
    "ami.screen.floor_reaction_card": ("ami.screen.floor",),
    "ami.screen.daily_challenge_card": ("ami.screen.floor",),
    "ami.screen.ticker_tape": ("ami.screen.floor",),
    "ami.screen.house_ad_banner_strip": ("ami.screen.floor",),
    "ami.screen.house_ad_card": ("ami.screen.floor",),
    "ami.screen.notification_bell": ("ami.screen.you", "ami.screen.settings", "ami.screen.you.settings"),
    "ami.screen.alpaca_orders_section": ("ami.screen.portfolio", "ami.screen.portfolio.orders"),
    "ami.screen.alpaca_position_card": ("ami.screen.portfolio", "ami.screen.portfolio.positions"),
    "ami.screen.portfolio_health_card": ("ami.screen.portfolio", "ami.screen.portfolio.positions"),
    "ami.screen.resting_orders_section": ("ami.screen.portfolio", "ami.screen.portfolio.orders"),
    "ami.screen.short_positions_section": ("ami.screen.portfolio", "ami.screen.portfolio.positions"),
    "ami.screen.position_card": ("ami.screen.portfolio", "ami.screen.portfolio.positions"),
    "ami.screen.portfolio_equity_chart": ("ami.screen.portfolio", "ami.screen.portfolio.positions"),
    "ami.screen.lesson_tile": ("ami.screen.track_lessons",),
    "ami.screen.lesson_markdown": ("ami.screen.lesson_reader",),
    "ami.screen.lesson_beat_deck": ("ami.screen.lesson_reader",),
    "ami.screen.term_block": ("ami.screen.lesson_reader",),
    "ami.screen.locked_agent_sheet": ("ami.screen.your_firm",),
    "ami.screen.option_verdict_cta": ("ami.screen.room",),
    "ami.screen.room_board": ("ami.screen.room",),
    "ami.screen.room_transcript_rows": ("ami.screen.room",),
    "ami.screen.room_briefing": ("ami.screen.room",),
    "ami.screen.ticker_chart": ("ami.screen.ticker_detail",),
    "ami.screen.games_queue_note": ("ami.screen.games_trade_ticket",),
    "ami.screen.profile_fields_section": ("ami.screen.settings", "ami.screen.you.settings"),
    "ami.screen.risk_limits_section": ("ami.screen.settings", "ami.screen.you.settings"),
    "ami.screen.ticker_rules_section": ("ami.screen.settings", "ami.screen.you.settings"),
    # Standalone screens that now also render as YOU / Portfolio panes (Phase C ids).
    "ami.screen.settings": ("ami.screen.settings", "ami.screen.you.settings"),
    "ami.screen.journal": ("ami.screen.journal", "ami.screen.you.journal"),
    "ami.screen.portfolio": ("ami.screen.portfolio", "ami.screen.portfolio.positions",
                             "ami.screen.portfolio.orders", "ami.screen.portfolio.history"),
    # The daily-challenge screen opens from the Floor card.
    "ami.screen.daily_challenge_card.screen": ("ami.screen.daily_challenge_card.screen",),
}

SYNTHETIC_EDGES: tuple[tuple[str, str, str], ...] = ()  # YOU / Portfolio panes are catalogue edges since the Phase C ids

# Screens with no (or a non-UI) way in. Reason text for the report.
ENTRY_NOTES: dict[str, str] = {
    "ami.screen.onboarding": "first-run interview; shown once before the shell, so it is only seen while the harness onboards (not re-enterable without a reset)",
    "ami.screen.version_gate": "forced by the server's minimum-build floor; cannot be shown on a current build without changing the server floor",
    "ami.screen.dev_preview": "debug-only entry; a release/QA-semantics build does not route to it",
    "ami.screen.house_ad_interstitial": "full-screen house ad shown after a Room run on the FREE plan only; the seeded user is on Trader",
    "ami.screen.tour_intro_sheet": "shown once, by the first-run coach-mark tour that the harness dismisses during onboarding",
    "ami.screen.nav_change_sheet": "shown only when the portfolio NAV changes through an external adjustment (no UI trigger)",
    "ami.screen.merge_sheet": "account-merge flow; needs a second claimed account to merge",
    "ami.screen.agent_unlocked": "celebration shown the moment a gateway lesson passes and unlocks an agent; transient",
    "ami.screen.option_proposal_ticket": "needs a Room verdict that proposes an option structure (LLM-dependent)",
    "ami.screen.option_disclosure_dialog": "needs the option proposal ticket first (LLM-dependent)",
    "ami.screen.option_reprice_sheet": "needs an open options position",
    "ami.screen.alpaca_connect": "needs a signed-in (non-anonymous) account; the crawl user is anonymous",
    "ami.screen.sign_in": "reached from Settings for an anonymous user",
}
GAMES_NOTE = "the GAME tab is behind the AMI_GAMES compile-time gate; the QA sim build is built with it off"
UNLOCK_BY_PREFIX = {"ami.screen.games_": GAMES_NOTE}

WHEN_PENALTY = 4


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    control: str            # human name: id or label
    ident: str = ""         # accessibility id, if the catalogue has one
    label: str = ""         # catalogue label (a description)
    when: str = ""
    kind: str = ""
    synthetic: bool = False

    @property
    def key(self) -> str:
        return f"{self.src}>{self.control}>{self.dst}"

    @property
    def cost(self) -> int:
        return 1 + (WHEN_PENALTY if self.when else 0)

    def step(self) -> dict:
        """The replay step: id first, then label pattern, else 'any unexplained row'."""
        s: dict = {"to": self.dst, "edge": self.key, "screen": self.src, "strict": True}
        if self.ident:
            s["ident"] = self.ident
        pat = label_pattern(_norm(self.label)).pattern if self.label else ""
        if pat and pat != "(?!)":
            s["pat"] = _norm(self.label)
        elif self.kind in ("list_row", "chip", "link", "menu_item", "tab") or not self.ident:
            s["row"] = True
        s["intent"] = self.control
        return s


Graph = dict[str, list[Edge]]


def real_hosts(surface: str) -> tuple[str, ...]:
    return HOSTS.get(surface, (surface,))


def build_graph(catalogue: Catalogue) -> Graph:
    g: Graph = {}
    for surface, intents in catalogue.by_screen.items():
        if surface == "ami.screen.home_shell":
            continue
        for it in intents:
            if it.expect not in ("navigate", "sheet", "dialog") or not it.target.startswith("ami.screen."):
                continue
            for host in real_hosts(surface):
                if host == it.target:
                    continue
                g.setdefault(host, []).append(Edge(host, it.target, it.name, it.ident, it.label, it.when, it.kind))
    for src, dst, ident in SYNTHETIC_EDGES:
        g.setdefault(src, []).append(Edge(src, dst, ident, ident=ident, synthetic=True))
    return g


def roots() -> dict[str, str]:
    """root screen -> bottom-nav id that shows it."""
    return {screen: nav for nav, screens in NAV_TO_ROOTS.items() for screen in screens}


def plan(graph: Graph, target: str, *, banned: frozenset[str] = frozenset(),
         start_roots: dict[str, str] | None = None) -> tuple[str, list[Edge]] | None:
    """Cheapest (nav id, edges) from a bottom-nav root to `target`. Dijkstra;
    an edge with a `when` costs more, so an unconditional route wins. None when
    no route exists without a banned edge."""
    start_roots = start_roots or roots()
    tie = itertools.count()
    heap: list = []
    for screen, nav in start_roots.items():
        heapq.heappush(heap, (0, next(tie), screen, nav, []))
    best: dict[str, int] = {}
    while heap:
        cost, _, node, nav, path = heapq.heappop(heap)
        if node == target:
            return nav, path
        if node in best and best[node] <= cost:
            continue
        best[node] = cost
        for e in graph.get(node, []):
            if e.key in banned or len(path) >= 8:
                continue
            heapq.heappush(heap, (cost + e.cost, next(tie), e.dst, nav, path + [e]))
    return None


def path_steps(nav: str, edges: list[Edge]) -> list[dict]:
    return [{"nav": nav}] + [e.step() for e in edges]


def reachable(graph: Graph, start_roots: dict[str, str] | None = None) -> set[str]:
    seen = set(start_roots or roots())
    stack = list(seen)
    while stack:
        n = stack.pop()
        for e in graph.get(n, []):
            if e.dst not in seen:
                seen.add(e.dst)
                stack.append(e.dst)
    return seen


def explain_unreachable(graph: Graph, target: str, *, banned: frozenset[str] = frozenset(),
                        failed: dict[str, str] | None = None) -> str:
    """Concrete reason a screen has no (working) route."""
    failed = failed or {}
    if target in ENTRY_NOTES:
        return ENTRY_NOTES[target]
    for prefix, note in UNLOCK_BY_PREFIX.items():
        if target.startswith(prefix):
            return note
    incoming = [e for es in graph.values() for e in es if e.dst == target]
    if not incoming:
        return "no control in the catalogue leads here (entered by a route the catalogue does not model)"
    tried = [e for e in incoming if e.key in failed]
    if tried:
        e = tried[0]
        extra = f" (precondition: {e.when})" if e.when else ""
        return f"route replay failed at {e.src} > {e.control}: {failed[e.key]}{extra}"
    reach = reachable(graph)
    live = [e for e in incoming if e.src in reach]
    if not live:
        srcs = ", ".join(sorted({e.src.replace('ami.screen.', '') for e in incoming})[:4])
        return f"only reachable from {srcs}, which are themselves unreachable"
    whens = sorted({e.when for e in live if e.when})
    if whens and all(e.when for e in live):
        return f"every route needs a state the crawl user does not have: {whens[0]}"
    return "a route exists in the catalogue but was not attempted before the time cap"
