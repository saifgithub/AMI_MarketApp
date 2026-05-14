// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'AMI Trade';

  @override
  String get tabFloor => 'Floor';

  @override
  String get tabPortfolio => 'Portfolio';

  @override
  String get tabJournal => 'Journal';

  @override
  String get tabLessons => 'Lessons';

  @override
  String get tabSettings => 'Settings';

  @override
  String get settingsLanguage => 'Language';

  @override
  String get settingsLanguageEnglish => 'English';

  @override
  String get settingsLanguageArabic => 'العربية';

  @override
  String get settingsLanguageMalay => 'Bahasa Melayu';

  @override
  String get actionRead => 'READ';

  @override
  String get actionQuizOnly => 'QUIZ ONLY';

  @override
  String get watchlistHeading => 'WATCHLIST';

  @override
  String get watchlistAdd => 'ADD';

  @override
  String get watchlistEmpty =>
      'Add tickers you want to watch. Tap a row for quick actions: Ask the Market Analyst, Convene the Room, or open a trade.';

  @override
  String get watchlistOpenTradeTicket => 'OPEN TRADE TICKET';

  @override
  String get watchlistAskMarketAnalyst => 'ASK THE MARKET ANALYST';

  @override
  String get watchlistConveneRoom => 'CONVENE THE ROOM';

  @override
  String get watchlistRemove => 'REMOVE FROM WATCHLIST';

  @override
  String get floorTabUpper => 'FLOOR';

  @override
  String get portfolioTabUpper => 'PORTFOLIO';

  @override
  String get journalTabUpper => 'JOURNAL';

  @override
  String get lessonsTabUpper => 'LESSONS';

  @override
  String get settingsTabUpper => 'SETTINGS';

  @override
  String get floorConciergeHeading => 'AMI CONCIERGE';

  @override
  String get floorConciergeTagline => 'Your personal assistant — tap to chat';

  @override
  String get floorTeamHeading => 'YOUR TEAM';

  @override
  String floorUnlockedSummary(int count) {
    return '$count of 12 unlocked. Tap a locked hex to see how.';
  }

  @override
  String get floorConveneCta => 'CONVENE THE ROOM';

  @override
  String get floorConveneCaption =>
      'Run a full multi-agent debate on a ticker.';

  @override
  String get floorRestartOnboarding => 'restart onboarding';

  @override
  String get floorFooter =>
      '⬢  AMI TRADE • EDUCATIONAL SIMULATION • NOT ADVICE';

  @override
  String get floorLockedHowTo => 'HOW TO UNLOCK';

  @override
  String get floorLockedNoLessons =>
      'This agent unlocks automatically once the Earn-Path lessons for them ship. For now you can preview them via 1-on-1 if your plan allows.';

  @override
  String get floorLockedEarnByLessons =>
      'Earn this agent free by passing every lesson that involves them:';

  @override
  String get floorLockedGoToLessons => 'GO TO LESSONS';

  @override
  String get floorLockedUpgradeSoon => 'UPGRADE TO SKIP — coming soon';

  @override
  String get portfolioHeading => 'PORTFOLIO';

  @override
  String get portfolioNewTradeTooltip => 'New trade';

  @override
  String get portfolioTotalValue => 'TOTAL VALUE';

  @override
  String get portfolioCash => 'CASH';

  @override
  String portfolioDrawdown(String pct) {
    return 'Drawdown: $pct%';
  }

  @override
  String get portfolioLive => 'LIVE';

  @override
  String get portfolioMock => 'MOCK';

  @override
  String get portfolioStartSimTrading => 'Start sim trading';

  @override
  String get portfolioStartSimTradingBody =>
      'Convene the Room to get a verdict, then open a trade — or place one directly from here. Your PM\'\'s safety floor runs on every submit.';

  @override
  String get portfolioNewTrade => 'NEW TRADE';

  @override
  String get portfolioHoldings => 'HOLDINGS';

  @override
  String get portfolioTrades => 'TRADES';

  @override
  String get portfolioNoTrades => 'No trades yet.';

  @override
  String get portfolioCloseTooltip => 'Close';

  @override
  String get portfolioAddDialogTitle => 'ADD TO WATCHLIST';

  @override
  String get portfolioAddDialogHint => 'Ticker (e.g. NVDA)';

  @override
  String get actionCancel => 'CANCEL';

  @override
  String get actionAdd => 'ADD';

  @override
  String get journalHeading => 'DECISION JOURNAL';

  @override
  String get journalFilterAll => 'ALL';

  @override
  String get journalFilterOneOnOne => '1-ON-1';

  @override
  String get journalFilterCoach => 'COACH';

  @override
  String get journalFilterLessons => 'LESSONS';

  @override
  String get journalFilterUnlocks => 'UNLOCKS';

  @override
  String journalRetentionWarning(int days) {
    return 'Floor Pass: last $days days only. Upgrade to keep everything.';
  }

  @override
  String get journalEmptyTitle => 'No entries yet.';

  @override
  String get journalEmptyBody =>
      'Talk to an agent, coach one, or complete a lesson — every action lands here automatically.';

  @override
  String get journalEntryTypeOneOnOne => '1-ON-1';

  @override
  String get journalEntryTypeCoach => 'COACH';

  @override
  String get journalEntryTypeLesson => 'LESSON';

  @override
  String get journalEntryTypeUnlock => 'UNLOCK';

  @override
  String get journalEntryTypeTrade => 'TRADE';

  @override
  String get journalEntryTypeMandate => 'MANDATE';

  @override
  String get journalEntryTypeDrift => 'DRIFT';

  @override
  String get journalEntryTypeRoom => 'ROOM';

  @override
  String get journalDetailHeading => 'ENTRY DETAIL';

  @override
  String get journalDetailLoading => 'Loading…';

  @override
  String get journalDetailBlockYou => 'YOU';

  @override
  String get journalDetailBlockAgent => 'AGENT';

  @override
  String get journalDetailBlockOverlay => 'OVERLAY';

  @override
  String journalDetailSavedAsVersion(int version) {
    return 'Saved as v$version';
  }

  @override
  String journalDetailVerdictLine(String action) {
    return 'VERDICT: $action';
  }

  @override
  String get journalNoteHeading => 'YOUR NOTE';

  @override
  String get journalNoteHint =>
      'Why this mattered. What you learned. What you\'\'d do differently.';

  @override
  String get journalNoteOutcome => 'OUTCOME';

  @override
  String get journalNoteOutcomeWin => 'WIN';

  @override
  String get journalNoteOutcomeLoss => 'LOSS';

  @override
  String get journalNoteOutcomePending => 'PENDING';

  @override
  String get journalNoteSave => 'SAVE NOTE';

  @override
  String get journalNoteSaved => 'Note saved';

  @override
  String get journalSearchHint => 'Search entries…';

  @override
  String get journalSearchEmpty => 'No entries match your search.';

  @override
  String get journalEntryDeleted => 'Entry removed';

  @override
  String get journalUndo => 'UNDO';

  @override
  String get journalTrashHeading => 'TRASH';

  @override
  String get journalTrashEmpty =>
      'Nothing here. Deleted entries appear in this list.';

  @override
  String get journalTrashWindowNote =>
      'Older entries are auto-hidden after 30 days.';

  @override
  String get journalRestoreEntry => 'RESTORE';

  @override
  String get journalEntryRestored => 'Entry restored';

  @override
  String journalDeletedAgo(String ago) {
    return 'Deleted $ago';
  }

  @override
  String get lessonsHeading => 'LESSONS';

  @override
  String get lessonsYourProgress => 'YOUR PROGRESS';

  @override
  String lessonsCount(int done, int total) {
    return '$done / $total lessons';
  }

  @override
  String get lessonsAgents => 'AGENTS';

  @override
  String lessonsAgentsCount(int unlocked) {
    return '$unlocked / 12';
  }

  @override
  String get lessonsNextUp => 'NEXT UP';

  @override
  String lessonsDurationMin(int min) {
    return '$min min';
  }

  @override
  String get lessonReaderLoading => 'Loading…';

  @override
  String get lessonReaderQuizOnlyBadge => 'QUIZ ONLY';

  @override
  String get lessonReaderQuizOnlyBannerOne =>
      'Skipping straight to the 1 quiz. Pass it and the lesson still counts toward agent unlocks. Wrong answers will show the explanation — that\'\'s your teaching surface.';

  @override
  String lessonReaderQuizOnlyBannerMany(int count) {
    return 'Skipping straight to the $count quizzes. Pass them all and the lesson still counts toward agent unlocks. Wrong answers will show the explanation.';
  }

  @override
  String lessonReaderMetaDurationTrack(int min, String track) {
    return '$min min · $track';
  }

  @override
  String get lessonReaderQuiz => 'QUIZ';

  @override
  String lessonReaderChatWith(String agent) {
    return 'CHAT WITH $agent';
  }

  @override
  String get lessonReaderSubmitQuiz => 'SUBMIT QUIZ';

  @override
  String get lessonReaderChecking => 'CHECKING…';

  @override
  String get lessonReaderPassed => 'PASSED';

  @override
  String get lessonReaderNotQuite => 'NOT QUITE';

  @override
  String lessonReaderCorrectOf(int correct, int total) {
    return '$correct / $total correct';
  }

  @override
  String get lessonReaderAgentUnlocked => 'AGENT UNLOCKED';

  @override
  String get lessonReaderTryAgain => 'TRY AGAIN';

  @override
  String get lessonReaderDone => 'DONE';

  @override
  String get lessonReaderBackToLessons => 'BACK TO LESSONS';

  @override
  String get settingsHeading => 'SETTINGS';

  @override
  String settingsMandateVersion(int version) {
    return 'mandate v$version';
  }

  @override
  String get settingsSaving => 'SAVING…';

  @override
  String get settingsSave => 'SAVE';

  @override
  String get settingsMandateUpdated => 'Mandate updated.';

  @override
  String get settingsSectionMandate => 'MY MANDATE';

  @override
  String get settingsSectionCompliance => 'COMPLIANCE';

  @override
  String get settingsSectionProfile => 'PROFILE';

  @override
  String get settingsSectionLanguageUpper => 'LANGUAGE';

  @override
  String get settingsSectionAccount => 'ACCOUNT';

  @override
  String get settingsSectionDeveloper => 'DEVELOPER';

  @override
  String get settingsRiskScore => 'Risk score';

  @override
  String settingsRiskScoreValue(int value) {
    return '$value / 5';
  }

  @override
  String get settingsRiskLabel1 =>
      'Capital preservation. Small sizes, tight stops.';

  @override
  String get settingsRiskLabel2 => 'Cautious. Below-average position sizing.';

  @override
  String get settingsRiskLabel3 => 'Balanced. Standard 3-5% positions.';

  @override
  String get settingsRiskLabel4 =>
      'Aggressive. Larger sizes on high-conviction setups.';

  @override
  String get settingsRiskLabel5 =>
      'Highest risk tolerance. Concentrated bets allowed.';

  @override
  String get settingsMaxDrawdown => 'Max drawdown';

  @override
  String get settingsMaxDrawdownExplain =>
      'Your PM refuses trades that would push the portfolio past this.';

  @override
  String get settingsComplianceHalal => 'Halal screen';

  @override
  String get settingsComplianceEsgLite => 'ESG-lite';

  @override
  String get settingsComplianceTAG => 'No tobacco / alcohol / gambling';

  @override
  String get settingsComplianceFossil => 'No fossil fuels';

  @override
  String get settingsComplianceLongOnly => 'Long-only';

  @override
  String get settingsComplianceLiquidOnly => 'Liquid-only';

  @override
  String get settingsProfilePlan => 'Plan';

  @override
  String get settingsProfileLocale => 'Locale';

  @override
  String get settingsProfileTimezone => 'Timezone';

  @override
  String get settingsProfilePath => 'Path';

  @override
  String get settingsProfileHorizon => 'Horizon';

  @override
  String get settingsProfilePrimaryGoal => 'Primary goal';

  @override
  String get settingsProfileCredits => 'Credits';

  @override
  String get settingsAccountStatus => 'Status';

  @override
  String get settingsAccountSignedIn => 'Signed in';

  @override
  String get settingsAccountGuest => 'Guest (anonymous)';

  @override
  String get settingsAccountHandle => 'Handle';

  @override
  String get settingsAccountGuestNote =>
      'Mandate, journal, and portfolio stay on this device until you sign in.';

  @override
  String get settingsManageAccount => 'MANAGE ACCOUNT';

  @override
  String get settingsSignIn => 'SIGN IN';

  @override
  String get settingsLanguagePlaceholderNote =>
      'AR + MS ship as placeholders today — missing keys fall back to English. Translators drop in proper ARBs and the locale lights up.';

  @override
  String get settingsDeveloperActive => 'Active backend';

  @override
  String get settingsDeveloperNoUrl => '(no URL baked into this build)';

  @override
  String get settingsDeveloperNotInBuild => '· not in this build';

  @override
  String get settingsDeveloperFootnote =>
      'This section is compiled out of MVP / App Store builds. Only PROD will be reachable then.';

  @override
  String get onboardingHeader => 'AMI TRADE';

  @override
  String get onboardingHeaderSetup => 'SETUP';

  @override
  String get onboardingHintSending => 'Sending...';

  @override
  String get onboardingHintAnswer => 'Type your answer…';

  @override
  String get onboardingReadbackContinue => 'LOOKS RIGHT — CONTINUE';

  @override
  String get onboardingMeetYourTeam => 'MEET YOUR TEAM';

  @override
  String get onboardingErrorTitle => 'CAN\'\'T REACH THE BACKEND';

  @override
  String get onboardingErrorUnknown => 'Unknown error';

  @override
  String get onboardingTryAgain => 'TRY AGAIN';

  @override
  String get signInHeading => 'SIGN IN';

  @override
  String get signInIntro =>
      'Sign in to keep your mandate, journal, and portfolio across devices. Until then, everything you build stays on this device.';

  @override
  String get signInWithApple => 'Sign in with Apple';

  @override
  String get signInWithEmail => 'OR CONTINUE WITH EMAIL';

  @override
  String get signInEmailHint => 'you@example.com';

  @override
  String get signInSendCode => 'SEND CODE';

  @override
  String get signInResendCode => 'RESEND CODE';

  @override
  String get signInCodeHint => '6-digit code';

  @override
  String get signInVerify => 'VERIFY & CLAIM';

  @override
  String signInDevCode(String code) {
    return 'DEV mode — code: $code';
  }

  @override
  String get signInCodeSent => 'Code sent. Check your email.';

  @override
  String get signInCodeFailed => 'Code did not verify. Try again.';

  @override
  String get signInAppleFailed => 'Apple sign-in failed.';

  @override
  String signInSignedInAs(String handle) {
    return 'Signed in as $handle';
  }

  @override
  String get signInLegalFootnote =>
      'AMI Trade is simulation-only. Nothing here is investment advice and no real trades are executed.';

  @override
  String get oneOnOneAskAnything =>
      'Ask me anything in my domain.\nType below to start.';

  @override
  String get oneOnOneStreaming => 'Streaming…';

  @override
  String get oneOnOneHint => 'Ask anything…';

  @override
  String get oneOnOneCoachTooltip => 'Coach this agent';

  @override
  String coachHeading(String agent) {
    return 'COACH $agent';
  }

  @override
  String get coachNoOverlayYet => 'No overlay yet — factory defaults';

  @override
  String coachOverlayActive(int version) {
    return 'Overlay v$version active';
  }

  @override
  String get coachNoEditsLeft => '⚠️ No edits left — upgrade to keep coaching';

  @override
  String coachOneEditLeft(int count) {
    return '⚠️ $count edit left at your tier';
  }

  @override
  String get coachVersionHistoryTooltip => 'Version history';

  @override
  String coachCurrentOverlayLabel(int version) {
    return 'CURRENT OVERLAY — v$version';
  }

  @override
  String get coachProtectedSafetyFloor => 'PROTECTED — safety floor';

  @override
  String get coachProtectedMandate => 'PROTECTED — mandate rule';

  @override
  String get coachEditLimitReached => 'EDIT LIMIT REACHED';

  @override
  String get coachRefused => 'COACH REFUSED';

  @override
  String coachProposalSavedSnack(int version, String summary) {
    return 'Saved as v$version — $summary';
  }

  @override
  String coachAgentRefused(String agent) {
    return '$agent REFUSED';
  }

  @override
  String coachAgentProposal(String agent) {
    return '$agent — PROPOSAL';
  }

  @override
  String get coachPlainEnglish => 'Plain English:';

  @override
  String get coachOverlayAddition => 'Overlay addition:';

  @override
  String get coachAccept => 'ACCEPT';

  @override
  String get coachRefine => 'REFINE';

  @override
  String get coachReject => 'REJECT';

  @override
  String get coachDismiss => 'DISMISS';

  @override
  String get coachInputHint => 'Tell me what to change…';

  @override
  String get coachDrafting => 'DRAFTING…';

  @override
  String get coachProposeChange => 'PROPOSE CHANGE';

  @override
  String coachHistoryHeading(String agent) {
    return '$agent HISTORY';
  }

  @override
  String get coachHistorySubtitle => 'All saved coaching versions';

  @override
  String coachHistoryEditsUnlimited(int count) {
    return '$count edits made • unlimited at your tier';
  }

  @override
  String coachHistoryEditsRemaining(int count, int remaining) {
    return '$count edits made • $remaining remaining';
  }

  @override
  String get coachHistoryEmpty =>
      'No coaching history yet.\nGo back and propose your first change.';

  @override
  String get coachHistoryActiveBadge => 'ACTIVE';

  @override
  String coachHistoryRollbackTitle(int version) {
    return 'Rollback to v$version?';
  }

  @override
  String coachHistoryRollbackBody(int version) {
    return 'Your agent will start using v$version immediately. The newer versions stay in history.';
  }

  @override
  String get coachHistoryRollback => 'ROLLBACK';

  @override
  String get coachHistoryRollbackToThis => 'ROLLBACK TO THIS';

  @override
  String get conveneHeading => 'CONVENE THE ROOM';

  @override
  String get convenePickTicker =>
      'Pick a ticker. Your full team runs the debate.';

  @override
  String get conveneTickerHint => 'e.g. NVDA';

  @override
  String get conveneOrPickOne => 'OR PICK ONE';

  @override
  String get conveneCta => 'CONVENE';

  @override
  String get roomHeadingPrefix => 'CONVENE ›';

  @override
  String get roomStandingBy => 'standing by';

  @override
  String get roomDeliberating => 'Team deliberating…';

  @override
  String get roomEndedNoVerdict => 'Room ended without a verdict.';

  @override
  String get roomSavedToJournal => 'Saved to Journal';

  @override
  String get roomClose => 'CLOSE';

  @override
  String get roomSafetyFloorPill => 'SAFETY FLOOR';

  @override
  String roomVerdictHeading(String action) {
    return 'VERDICT — $action';
  }

  @override
  String get roomMetricTicker => 'TICKER';

  @override
  String get roomMetricSize => 'SIZE';

  @override
  String get roomMetricEntry => 'ENTRY';

  @override
  String get roomMetricStop => 'STOP';

  @override
  String get roomMetricTarget => 'TARGET';

  @override
  String get roomMetricHorizon => 'HORIZON';

  @override
  String roomHorizonDays(int days) {
    return '$days days';
  }

  @override
  String get roomViolations => 'VIOLATIONS';

  @override
  String get roomOpenTradeTicket => 'OPEN TRADE TICKET';

  @override
  String get roomTradeTicketCaption =>
      'Submits with the verdict\'\'s size / stop / target. PM safety floor reruns.';

  @override
  String get tradeTicketHeading => 'NEW TRADE';

  @override
  String get tradeTicketSafetyFloorBlocked => 'SAFETY FLOOR — TRADE BLOCKED';

  @override
  String get tradeTicketChangeMandate =>
      'Change what is enforced via Settings → My Mandate.';

  @override
  String get tradeTicketLabelTicker => 'TICKER';

  @override
  String get tradeTicketLabelQuantity => 'QUANTITY';

  @override
  String get tradeTicketLabelStop => 'STOP';

  @override
  String get tradeTicketLabelTarget => 'TARGET';

  @override
  String get tradeTicketLabelHorizon => 'HORIZON (DAYS)';

  @override
  String get tradeTicketHintTicker => 'NVDA';

  @override
  String get tradeTicketHintQty => '10';

  @override
  String get tradeTicketHintOptional => 'optional';

  @override
  String get tradeTicketSubmitting => 'SUBMITTING…';

  @override
  String get tradeTicketSubmit => 'SUBMIT TRADE';

  @override
  String get tradeTicketFooterNote =>
      'PM safety floor runs on submit — compliance flags + drawdown + single-name cap.';

  @override
  String get tradeTicketSideBuy => 'BUY';

  @override
  String get tradeTicketSideSell => 'SELL';

  @override
  String tradeTicketFilled(
      String side, String qty, String ticker, String price) {
    return 'Filled: $side $qty $ticker @ \\\$$price';
  }

  @override
  String get chatBubbleConcierge => 'CONCIERGE';
}
