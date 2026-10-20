"""Mirror of `mobile/lib/qa/semantics_ids.dart` — the app<->harness element
contract (CR162).

The app sets these via Flutter's `Semantics(identifier: …)`, which the engine
maps to **`resource-id` on Android** and **`accessibilityIdentifier` on iOS**.
They ship in release builds and render nothing, so the same release artifact
CR080 already tests is addressable by ID on both platforms — no instrumented
build, no `enableFlutterDriverExtension()`.

Why this matters beyond iOS: before CR162 this harness located everything by
*rendered text*, so `config/locales.py` had to carry every EN/AR/MS string
verbatim just to tap a bottom-nav tab. Navigation was coupled to translation and
any ARB copy edit could break the suite. Navigate by ID; assert on text only
where the text is the thing under test (that is what `test_locale_matrix.py` is
for).

Keep in sync with the Dart file. `mobile/test/qa/semantics_ids_test.dart` fails
if the app side drops one; `tests/test_00_smoke_hierarchy.py` fails if the
running build does not expose them.
"""

from __future__ import annotations

# Bottom-nav destinations, in on-screen order. Keys are the same
# locale-independent semantic names `pages/base_page.py::TAB_LABELS` uses.
#
# CR133 restructured the bar. Journal and Settings are no longer destinations —
# both are now segments inside YOU — and GAME arrived at slot 3. The retired
# IDs are deleted rather than left in place: an ID the harness can still ask
# for, pointing at nothing, fails on the device days later instead of here.
NAV_IDS: dict[str, str] = {
    "Floor": "ami.nav.floor",
    "Portfolio": "ami.nav.portfolio",
    "Lessons": "ami.nav.lessons",
    "You": "ami.nav.you",
}

# GAME is deliberately NOT in NAV_IDS. It sits behind the app's compile-time
# `AMI_GAMES` gate, and this harness runs against store builds, which are built
# with the gate off and therefore correctly show four tabs. Putting it in the
# required set would make the GO/NO-GO gate fail on a perfectly good binary —
# and a gate that fires when nothing is wrong teaches the operator that firing
# does not mean stop. Use it explicitly when driving a gated build.
NAV_ID_GAME = "ami.nav.game"

# The YOU tab's segments. CR133 moved SETTINGS and JOURNAL off the bottom nav
# and into here, which is why `open_tab(driver, "Settings")` asserts out — it is
# no longer a destination. Reach them with `pages/base_page.py::open_you_segment`.
#
# These carry their own IDs rather than being tapped by label because the label
# sits on the segment *button*: an exact-text wait on "SETTINGS" is satisfied the
# instant YOU paints, before the pane behind it has rendered anything. And an
# embedded pane drops its own header (YOU owns it), so there is no heading to
# wait on either. Tap the ID, then assert on pane content — "MY MANDATE" for
# SETTINGS, the filter chips for JOURNAL.
YOU_SEGMENT_IDS: dict[str, str] = {
    "Settings": "ami.you.settings",
    "Journal": "ami.you.journal",
    "Insights": "ami.you.insights",
}

# Modal sheets — the DEF075 class the nav-bar/bottom-inset check exists for.
SHEET_CONVENE = "ami.sheet.convene"
SHEET_CONVENE_CTA = "ami.sheet.convene.cta"
SHEET_MERGE = "ami.sheet.merge"
SHEET_MERGE_CTA = "ami.sheet.merge.cta"

# CR209 — the Concierge interview. See `OnboardingIds` in the Dart mirror for
# why the chips share one identifier rather than carrying an index.
ONBOARDING_ANSWER_CHIP = "ami.onboarding.answer_chip"
ONBOARDING_COMPOSER = "ami.onboarding.composer"
ONBOARDING_SEND = "ami.onboarding.send"

# DEF375 — the shared coach-mark card's controls, on all five tours.
#
# TOUR_SKIP is the PRESENCE probe, not the dismissal control. DEF382: tapping
# Skip on iOS removes the coach-mark overlay mid-animation and the app's whole
# accessibility tree goes with it — the page source collapses to an empty
# 1519-byte shell and never recovers, with the app still alive and in the
# foreground. Tours are dismissed by walking TOUR_NEXT to the end instead,
# which was measured to leave all four nav ids resolving.
TOUR_SKIP = "ami.tour.skip"
# One id for both faces of one button: "Next" mid-tour, "Got it" on the last
# step. The step count is discovered by tapping until it is gone.
TOUR_NEXT = "ami.tour.next"

# CR264 — one root identifier per screen / sheet / dialog (mirror of `ScreenIds`
# in the Dart file; suffix = the source file's basename). Lets the exhaustive
# crawl name the surface it is on without matching rendered text.
SCREEN_IDS: tuple[str, ...] = (
    "ami.screen.agent_action_sheet",
    "ami.screen.agent_unlocked",
    "ami.screen.ai_coach",
    "ami.screen.alpaca_connect",
    "ami.screen.brief_history",
    "ami.screen.brief",
    "ami.screen.bug_report_sheet",
    "ami.screen.chart_fullscreen",
    "ami.screen.company_review",
    "ami.screen.confirm_restart_onboarding",
    "ami.screen.convene_sheet",
    "ami.screen.day_trader_disclosure_dialog",
    "ami.screen.dev_preview",
    "ami.screen.floor",
    "ami.screen.games_board",
    "ami.screen.games_close",
    "ami.screen.games_entry_sheet",
    "ami.screen.games_home",
    "ami.screen.games_lobby",
    "ami.screen.games_record",
    "ami.screen.games_run",
    "ami.screen.games_trade_ticket",
    "ami.screen.house_ad_interstitial",
    "ami.screen.inbox",
    "ami.screen.journal_detail",
    "ami.screen.journal",
    "ami.screen.journal_trash",
    "ami.screen.legal",
    "ami.screen.lesson_reader",
    "ami.screen.lessons",
    "ami.screen.merge_sheet",
    "ami.screen.message_detail",
    "ami.screen.nav_change_sheet",
    "ami.screen.no_rules_disclosure",
    "ami.screen.notification_centre",
    "ami.screen.notification_preferences",
    "ami.screen.onboarding",
    "ami.screen.one_on_one",
    "ami.screen.option_disclosure_dialog",
    "ami.screen.option_proposal_ticket",
    "ami.screen.option_reprice_sheet",
    "ami.screen.portfolio_health_finding",
    "ami.screen.portfolio",
    "ami.screen.price_alert_sheet",
    "ami.screen.room",
    "ami.screen.settings",
    "ami.screen.sign_in",
    "ami.screen.team_calls",
    "ami.screen.ticker_detail",
    "ami.screen.tour_intro_sheet",
    "ami.screen.track_lessons",
    "ami.screen.trade_ticket_sheet",
    "ami.screen.upgrade_paywall",
    "ami.screen.version_gate",
    "ami.screen.watchlist_sheet",
    "ami.screen.your_firm",
    "ami.screen.you",
)
