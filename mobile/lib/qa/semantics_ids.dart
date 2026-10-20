/// CR162 — the stable element-identifier contract between the app and the
/// black-box UAT harness (`qa/appium/`).
///
/// These strings are passed to `Semantics(identifier: …)`, which Flutter maps
/// to `resource-id` on Android and `accessibilityIdentifier` on iOS. They ship
/// in release builds and are never rendered — `identifier` is not a label, it
/// carries no text for a screen reader to speak.
///
/// Why this file exists rather than string literals at each call site: before
/// CR162 the harness located everything by *rendered text*, so
/// `qa/appium/config/locales.py` had to carry every EN/AR/MS string verbatim
/// just to tap a bottom-nav tab. Navigation was coupled to translation, and any
/// ARB copy edit could silently break the test suite. An identifier is
/// locale-independent by construction, so the harness navigates by ID and
/// asserts on text only where the text is the thing under test.
///
/// Convention: `ami.<area>.<thing>`, lowercase, dot-separated. Keep in sync
/// with `qa/appium/config/semantics_ids.py`; `mobile/test/qa/semantics_ids_test.dart`
/// fails if a nav identifier is dropped or renamed.
library;

import 'package:ami_trade/features/games/games_gate.dart';

/// Bottom-nav destinations. Order matches `home_shell.dart`'s `IndexedStack`.
///
/// CR133 restructured the bar: JOURNAL and SETTINGS are no longer destinations
/// (both moved inside `YOU` as segments), and GAME arrived. The old IDs are
/// deleted rather than left pointing at nothing — a stale ID the harness can
/// still ask for is worse than a missing one, because it fails on the device
/// days later instead of here.
class NavIds {
  const NavIds._();

  static const String floor = 'ami.nav.floor';
  static const String portfolio = 'ami.nav.portfolio';
  static const String game = 'ami.nav.game';
  static const String lessons = 'ami.nav.lessons';
  static const String you = 'ami.nav.you';

  /// Every destination **this binary renders**, in on-screen order — the
  /// harness asserts this exact set is addressable as its GO/NO-GO gate, so a
  /// dropped ID fails loudly on the Mac rather than as a confusing red device
  /// run days later.
  ///
  /// Conditional on the same compile-time gate the tab itself is, because the
  /// harness runs against store builds: an unconditional list would demand the
  /// harness find a GAME tab that a `--no-games` binary correctly does not
  /// have, and a gate that fires when nothing is wrong teaches the operator
  /// that firing does not mean stop.
  static const List<String> all = [
    floor,
    portfolio,
    if (kGamesEnabled) game,
    lessons,
    you,
  ];
}

/// The `YOU` tab's three segments (CR133 moved SETTINGS and JOURNAL here from
/// the bottom nav; INSIGHTS is new).
///
/// These need identifiers for the same reason the nav destinations do, and one
/// more besides. A segment's *rendered label* is a poor handle even in English:
/// the label sits on the button, so an exact-text wait is satisfied by the
/// control the moment the tab paints — before the pane behind it has rendered
/// anything. Waiting on the ID and then asserting on pane-specific content
/// separates "the segment exists" from "the pane is up", which is the race
/// `tests/test_portfolio.py` hit on the bottom nav.
///
/// Embedded panes drop their own `AmiScreenHeader` (YOU owns the header), so
/// there is no heading to wait on either — the harness must key off content
/// like SETTINGS' `MY MANDATE` section or JOURNAL's filter chips.
class YouIds {
  const YouIds._();

  static const String settings = 'ami.you.settings';
  static const String journal = 'ami.you.journal';
  static const String insights = 'ami.you.insights';

  /// In `YouSegment` order, which is the on-screen order of the segment bar.
  static const List<String> all = [settings, journal, insights];
}

/// Modal sheets. These are the DEF075 class — interactive elements that can end
/// up under the Android system nav bar or the iOS home indicator, which is the
/// one usability check CR080 was built to catch.
class SheetIds {
  const SheetIds._();

  static const String convene = 'ami.sheet.convene';
  static const String conveneCta = 'ami.sheet.convene.cta';
  static const String merge = 'ami.sheet.merge';
  static const String mergeCta = 'ami.sheet.merge.cta';
}

/// CR209 — the Concierge interview, the one surface the onboarding walk must
/// drive and the only one it had no identifier for.
///
/// The walk used to select an answer by geometry: "the bottom-most labelled
/// control". On iOS the bottom of the screen never belongs to the chips, and
/// three different controls were measured occupying that slot in three
/// consecutive runs — the keyboard's globe key (186 taps), the composer text
/// field (180), the send arrow (579). Excluding them one at a time cannot
/// converge, because the pool is the platform's, not ours.
///
/// [DEF346] is the sharp edge: giving the send button a VoiceOver label — a
/// correct accessibility fix — is what made the harness's `labelled_only`
/// filter stop excluding it, and `_live_chip`'s docstring still asserts the
/// arrow "has none". An accessibility improvement silently invalidated a test
/// heuristic. An identifier cannot rot that way: it is addressed by name, and
/// `mobile/test/qa/semantics_ids_test.dart` fails locally if it is dropped.
///
/// [answerChip] is deliberately NOT unique per chip. The harness needs "an
/// answer for the current turn", and `onboarding_screen.dart` renders only the
/// live turn's chips (`state.currentChips`), so every node carrying this id is
/// a valid answer. Numbering them would invent an ordering the interview does
/// not have — the chips are backend-authored and their count varies by turn.
class OnboardingIds {
  const OnboardingIds._();

  /// Every tappable answer chip of the current interview turn.
  static const String answerChip = 'ami.onboarding.answer_chip';

  /// The free-text composer and its send button. Named so the walk can exclude
  /// them **by name** rather than by guessing at geometry — the walk answers
  /// with chips and never types.
  static const String composer = 'ami.onboarding.composer';
  static const String send = 'ami.onboarding.send';
}

/// DEF375 — the first-run coach-mark tours.
///
/// Five tours (floor, portfolio, lessons, journal, you) all render through the
/// single `TourCard`, so one identifier addresses every one of them. They are
/// modal: until one is dismissed the tab behind it is unreachable, which on a
/// fresh install is every tab. That cost the iOS gate 7 of its 19 tests —
/// `test_portfolio_renders_heading` failed with the app parked on YOU behind
/// the *YOU* tour, never having reached Portfolio at all.
///
/// `Next` used to be deliberately unnamed, on the reasoning that skip is one
/// tap whatever the tour while Next depends on the step count. That reasoning
/// was overturned by measurement (DEF382): tapping Skip on iOS tears the
/// coach-mark overlay down mid-animation and takes the app's whole
/// accessibility tree with it — the page source collapses to an empty 1519-byte
/// shell and never recovers, with the app still alive and in the foreground.
/// Walking the same tour to "Got it" ends it with the tree intact. So the
/// harness walks; [next] is what it walks with, and the step count is
/// discovered by looping until the control is gone rather than assumed.
///
/// One identifier covers both faces of that control: the same `TextButton`
/// renders "Next" mid-tour and "Got it" on the last step.
class TourIds {
  const TourIds._();

  static const String skip = 'ami.tour.skip';
  static const String next = 'ami.tour.next';
}

/// CR232 — the exit affordances a pushed full page carries, now that a
/// top-right `Icons.close` is no longer how any of them exit.
///
/// [navBack] is the single identifier for `AmiScreenHeader`'s back chevron —
/// one id for every screen that shows it, the same reasoning [TourIds] gives
/// for sharing one id across every `TourCard`: the harness needs "go back
/// from wherever I am," not a per-screen name for a control that always does
/// the same thing. [tradeTicketCancel] is separate because the trade tickets
/// (CR232 rule 3) carry BOTH a back chevron and a text "Cancel" action in the
/// same header, and the harness must be able to address the one that does not
/// also exist on every other pushed page.
class ExitIds {
  const ExitIds._();

  static const String navBack = 'ami.nav.back';
  static const String tradeTicketCancel = 'ami.trade_ticket.cancel';
}

/// CR264 — one root identifier per screen, sheet and dialog, so the exhaustive
/// UAT crawl can name the surface it is on without matching rendered text.
///
/// The suffix is the source file's basename, so the id is derivable from the
/// file and unique by construction. `mobile/test/qa/screen_root_ids_test.dart`
/// fails if a `*_screen.dart` / `*_sheet.dart` drops its root id or an id here
/// stops being used. Mirror: `SCREEN_IDS` in `qa/appium/config/semantics_ids.py`.
class ScreenIds {
  const ScreenIds._();

  static const String agentActionSheet = 'ami.screen.agent_action_sheet';
  static const String agentUnlockedScreen = 'ami.screen.agent_unlocked';
  static const String aiCoachScreen = 'ami.screen.ai_coach';
  static const String alpacaConnectScreen = 'ami.screen.alpaca_connect';
  static const String briefHistoryScreen = 'ami.screen.brief_history';
  static const String briefScreen = 'ami.screen.brief';
  static const String bugReportSheet = 'ami.screen.bug_report_sheet';
  static const String chartFullscreenScreen = 'ami.screen.chart_fullscreen';
  static const String companyReviewScreen = 'ami.screen.company_review';
  static const String confirmRestartOnboarding = 'ami.screen.confirm_restart_onboarding';
  static const String conveneSheet = 'ami.screen.convene_sheet';
  static const String dayTraderDisclosureDialog = 'ami.screen.day_trader_disclosure_dialog';
  static const String devPreviewScreen = 'ami.screen.dev_preview';
  static const String floorScreen = 'ami.screen.floor';
  static const String gamesBoardScreen = 'ami.screen.games_board';
  static const String gamesCloseScreen = 'ami.screen.games_close';
  static const String gamesEntrySheet = 'ami.screen.games_entry_sheet';
  static const String gamesHomeScreen = 'ami.screen.games_home';
  static const String gamesLobbyScreen = 'ami.screen.games_lobby';
  static const String gamesRecordScreen = 'ami.screen.games_record';
  static const String gamesRunScreen = 'ami.screen.games_run';
  static const String gamesTradeTicketScreen = 'ami.screen.games_trade_ticket';
  static const String houseAdInterstitial = 'ami.screen.house_ad_interstitial';
  static const String inboxScreen = 'ami.screen.inbox';
  static const String journalDetailScreen = 'ami.screen.journal_detail';
  static const String journalScreen = 'ami.screen.journal';
  static const String journalTrashScreen = 'ami.screen.journal_trash';
  static const String legalScreen = 'ami.screen.legal';
  static const String lessonReaderScreen = 'ami.screen.lesson_reader';
  static const String lessonsScreen = 'ami.screen.lessons';
  static const String mergeSheet = 'ami.screen.merge_sheet';
  static const String messageDetailScreen = 'ami.screen.message_detail';
  static const String navChangeSheet = 'ami.screen.nav_change_sheet';
  static const String noRulesDisclosure = 'ami.screen.no_rules_disclosure';
  static const String notificationCentreScreen = 'ami.screen.notification_centre';
  static const String notificationPreferencesScreen = 'ami.screen.notification_preferences';
  static const String onboardingScreen = 'ami.screen.onboarding';
  static const String oneOnOneScreen = 'ami.screen.one_on_one';
  static const String optionDisclosureDialog = 'ami.screen.option_disclosure_dialog';
  static const String optionProposalTicket = 'ami.screen.option_proposal_ticket';
  static const String optionRepriceSheet = 'ami.screen.option_reprice_sheet';
  static const String portfolioHealthFindingScreen = 'ami.screen.portfolio_health_finding';
  static const String portfolioScreen = 'ami.screen.portfolio';
  static const String priceAlertSheet = 'ami.screen.price_alert_sheet';
  static const String roomScreen = 'ami.screen.room';
  static const String settingsScreen = 'ami.screen.settings';
  static const String signInScreen = 'ami.screen.sign_in';
  static const String teamCallsScreen = 'ami.screen.team_calls';
  static const String tickerDetailScreen = 'ami.screen.ticker_detail';
  static const String tourIntroSheet = 'ami.screen.tour_intro_sheet';
  static const String trackLessonsScreen = 'ami.screen.track_lessons';
  static const String tradeTicketSheet = 'ami.screen.trade_ticket_sheet';
  static const String upgradePaywall = 'ami.screen.upgrade_paywall';
  static const String versionGateScreen = 'ami.screen.version_gate';
  static const String watchlistSheet = 'ami.screen.watchlist_sheet';
  static const String yourFirmScreen = 'ami.screen.your_firm';
  static const String youScreen = 'ami.screen.you';

  static const List<String> all = [
    agentActionSheet,
    agentUnlockedScreen,
    aiCoachScreen,
    alpacaConnectScreen,
    briefHistoryScreen,
    briefScreen,
    bugReportSheet,
    chartFullscreenScreen,
    companyReviewScreen,
    confirmRestartOnboarding,
    conveneSheet,
    dayTraderDisclosureDialog,
    devPreviewScreen,
    floorScreen,
    gamesBoardScreen,
    gamesCloseScreen,
    gamesEntrySheet,
    gamesHomeScreen,
    gamesLobbyScreen,
    gamesRecordScreen,
    gamesRunScreen,
    gamesTradeTicketScreen,
    houseAdInterstitial,
    inboxScreen,
    journalDetailScreen,
    journalScreen,
    journalTrashScreen,
    legalScreen,
    lessonReaderScreen,
    lessonsScreen,
    mergeSheet,
    messageDetailScreen,
    navChangeSheet,
    noRulesDisclosure,
    notificationCentreScreen,
    notificationPreferencesScreen,
    onboardingScreen,
    oneOnOneScreen,
    optionDisclosureDialog,
    optionProposalTicket,
    optionRepriceSheet,
    portfolioHealthFindingScreen,
    portfolioScreen,
    priceAlertSheet,
    roomScreen,
    settingsScreen,
    signInScreen,
    teamCallsScreen,
    tickerDetailScreen,
    tourIntroSheet,
    trackLessonsScreen,
    tradeTicketSheet,
    upgradePaywall,
    versionGateScreen,
    watchlistSheet,
    yourFirmScreen,
    youScreen,
  ];
}
