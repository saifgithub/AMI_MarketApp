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
  String get watchlistRemoved => 'Removed from watchlist';

  @override
  String get watchlistUndo => 'UNDO';

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
  String floorLockedEarnByLessons(int count) {
    return 'Pass these $count lessons to earn this agent:';
  }

  @override
  String get floorLockedGoToLessons => 'GO TO LESSONS';

  @override
  String floorLockedProgress(int completed, int total) {
    return '$completed / $total gateway lessons passed';
  }

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
      'Convene the Room to get a verdict, then open a trade — or place one directly from here. Your PM\'s safety floor runs on every submit.';

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
  String get tickerDetailValue => 'VALUE';

  @override
  String get tickerDetailQty => 'QTY';

  @override
  String get tickerDetailAvgCost => 'AVG COST';

  @override
  String get tickerDetailMark => 'MARK';

  @override
  String tickerDetailOpened(String date) {
    return 'Opened $date';
  }

  @override
  String get tickerDetailWatchingHeading => 'WATCHING';

  @override
  String get tickerDetailToday => 'today';

  @override
  String tickerDetailAdded(String date) {
    return 'Added $date';
  }

  @override
  String tickerDetailNoPosition(String ticker) {
    return 'No open position or watchlist entry for $ticker.';
  }

  @override
  String get tickerDetailChartUnavailable => 'Chart unavailable. Tap to retry.';

  @override
  String get tickerDetailChartExpand => 'Expand chart';

  @override
  String get tickerDetailChartClose => 'Close fullscreen chart';

  @override
  String get tickerDetailActionTrade => 'TRADE';

  @override
  String get tickerDetailActionTradeMore => 'TRADE MORE';

  @override
  String get tickerDetailActionAsk => 'ASK';

  @override
  String get tickerDetailActionConvene => 'CONVENE';

  @override
  String get tickerDetailActionWatch => 'WATCH';

  @override
  String get tickerDetailActionClose => 'CLOSE';

  @override
  String tickerDetailTradesHeading(String ticker) {
    return 'TRADES FOR $ticker';
  }

  @override
  String get tickerDetailNoTrades => 'No trades on record for this ticker yet.';

  @override
  String tickerDetailClosePositionConfirmTitle(String ticker) {
    return 'CLOSE $ticker POSITION?';
  }

  @override
  String get tickerDetailClosePositionConfirmBody =>
      'This closes every open trade for this ticker at the current mark. Realised P&L is final.';

  @override
  String get tickerDetailClosePositionConfirmCta => 'CLOSE';

  @override
  String get tickerDetailNewsHeading => 'NEWS';

  @override
  String tickerDetailNewsEpsEstimate(String eps) {
    return 'est. EPS $eps';
  }

  @override
  String get roomVerdictSeeChart => 'SEE CHART';

  @override
  String get actionCancel => 'CANCEL';

  @override
  String get actionAdd => 'ADD';

  @override
  String get journalHeading => 'DECISION JOURNAL';

  @override
  String get journalFilterAll => 'ALL';

  @override
  String get journalFilterRoom => 'ROOM';

  @override
  String get journalFilterTrade => 'TRADE';

  @override
  String get journalFilterOneOnOne => '1-ON-1';

  @override
  String get journalFilterBrief => 'BRIEF';

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
      'Talk to an agent, brief one, or complete a lesson — every action lands here automatically.';

  @override
  String get journalEntryTypeOneOnOne => '1-ON-1';

  @override
  String get journalEntryTypeBrief => 'BRIEF';

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
      'Why this mattered. What you learned. What you\'d do differently.';

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
  String get lessonsTierInProgress => 'IN PROGRESS';

  @override
  String get lessonsTierNotStarted => 'NOT STARTED';

  @override
  String get lessonsTierCompleted => 'COMPLETED';

  @override
  String get lessonsContinue => 'CONTINUE';

  @override
  String get lessonsUnlocksAgent => 'UNLOCKS';

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
      'Skipping straight to the 1 quiz. Pass it and the lesson still counts toward agent unlocks. Wrong answers will show the explanation — that\'s your teaching surface.';

  @override
  String lessonReaderQuizOnlyBannerMany(int count) {
    return 'Skipping straight to the $count quizzes. Pass them all and the lesson still counts toward agent unlocks. Wrong answers will show the explanation.';
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
  String get settingsSignedOut => 'You\'ve been signed out.';

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
  String get onboardingClaimPrompt =>
      'Let\'s save this so your team remembers you.';

  @override
  String get onboardingSaveTeam => 'SAVE MY TEAM';

  @override
  String get onboardingSkipForNow => 'SKIP FOR NOW';

  @override
  String get onboardingErrorTitle => 'CAN\'T REACH THE BACKEND';

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
  String get signInWithGoogle => 'Sign in with Google';

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
  String get signInGoogleFailed => 'Google sign-in failed.';

  @override
  String signInSignedInAs(String handle) {
    return 'Signed in as $handle';
  }

  @override
  String get signInLegalFootnote =>
      'AMI Trade is simulation-only. Nothing here is investment advice and no real trades are executed.';

  @override
  String get mergeSheetTitle => 'WELCOME BACK';

  @override
  String get mergeSheetBody =>
      'We found data from your previous session on this device. Would you like to bring it into your account?';

  @override
  String get mergeSheetEmptyBody =>
      'You\'ve signed back in. Nothing carried over from your previous session on this device.';

  @override
  String mergeSheetJournalEntries(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count journal entries',
      one: '1 journal entry',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetSimTrades(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count simulated trades',
      one: '1 simulated trade',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetWatchlist(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count watchlist tickers',
      one: '1 watchlist ticker',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetLessons(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count lessons started',
      one: '1 lesson started',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetOneOnOnes(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count 1-on-1 messages',
      one: '1 1-on-1 message',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetRoomRuns(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Room runs',
      one: '1 Room run',
    );
    return '$_temp0';
  }

  @override
  String get mergeSheetMandate =>
      'Mandate (yours stays — we\'ll drop the older one)';

  @override
  String get mergeSheetMandateMove =>
      'Mandate from your previous session (no conflict)';

  @override
  String get mergeSheetConfirm => 'MERGE EVERYTHING';

  @override
  String get mergeSheetKeepSeparate => 'KEEP SEPARATE';

  @override
  String get mergeSheetClose => 'GOT IT';

  @override
  String get mergeSheetSuccess => 'Merged into your account.';

  @override
  String get mergeSheetFailed => 'Merge failed. Try again from Settings later.';

  @override
  String get oneOnOneAskAnything =>
      'Ask me anything in my domain.\nType below to start.';

  @override
  String get oneOnOneStreaming => 'Streaming…';

  @override
  String get oneOnOneHint => 'Ask anything…';

  @override
  String get oneOnOneBriefTooltip => 'Brief this agent';

  @override
  String briefHeading(String agent) {
    return 'BRIEF $agent';
  }

  @override
  String get briefNoOverlayYet => 'No overlay yet — factory defaults';

  @override
  String briefOverlayActive(int version) {
    return 'Overlay v$version active';
  }

  @override
  String get briefNoEditsLeft => '⚠️ No edits left — upgrade to keep briefing';

  @override
  String briefOneEditLeft(int count) {
    return '⚠️ $count edit left at your tier';
  }

  @override
  String get briefVersionHistoryTooltip => 'Version history';

  @override
  String briefCurrentOverlayLabel(int version) {
    return 'CURRENT OVERLAY — v$version';
  }

  @override
  String get briefProtectedSafetyFloor => 'PROTECTED — safety floor';

  @override
  String get briefProtectedMandate => 'PROTECTED — mandate rule';

  @override
  String get briefEditLimitReached => 'EDIT LIMIT REACHED';

  @override
  String get briefRefused => 'BRIEF REFUSED';

  @override
  String briefProposalSavedSnack(int version, String summary) {
    return 'Saved as v$version — $summary';
  }

  @override
  String briefAgentRefused(String agent) {
    return '$agent REFUSED';
  }

  @override
  String briefAgentProposal(String agent) {
    return '$agent — PROPOSAL';
  }

  @override
  String get briefPlainEnglish => 'Plain English:';

  @override
  String get briefOverlayAddition => 'Overlay addition:';

  @override
  String get briefAccept => 'ACCEPT';

  @override
  String get briefRefine => 'REFINE';

  @override
  String get briefReject => 'REJECT';

  @override
  String get briefDismiss => 'DISMISS';

  @override
  String get briefInputHint => 'Tell me what to change…';

  @override
  String get briefDrafting => 'DRAFTING…';

  @override
  String get briefProposeChange => 'PROPOSE CHANGE';

  @override
  String briefHistoryHeading(String agent) {
    return '$agent HISTORY';
  }

  @override
  String get briefHistorySubtitle => 'All saved briefings';

  @override
  String briefHistoryEditsUnlimited(int count) {
    return '$count edits made • unlimited at your tier';
  }

  @override
  String briefHistoryEditsRemaining(int count, int remaining) {
    return '$count edits made • $remaining remaining';
  }

  @override
  String get briefHistoryEmpty =>
      'No briefings yet.\nGo back and propose your first change.';

  @override
  String get briefHistoryActiveBadge => 'ACTIVE';

  @override
  String briefHistoryRollbackTitle(int version) {
    return 'Rollback to v$version?';
  }

  @override
  String briefHistoryRollbackBody(int version) {
    return 'Your agent will start using v$version immediately. The newer versions stay in history.';
  }

  @override
  String get briefHistoryRollback => 'ROLLBACK';

  @override
  String get briefHistoryRollbackToThis => 'ROLLBACK TO THIS';

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
      'Submits with the verdict\'s size / stop / target. PM safety floor reruns.';

  @override
  String get roomWinzipTitle => 'Your Room is warming up';

  @override
  String roomWinzipBody(String countdown) {
    return 'You\'ve used this Room. AMI\'s topping you up — your next Room unlocks in $countdown.';
  }

  @override
  String get roomWinzipReady => 'Your Room is ready to convene.';

  @override
  String get roomWinzipConvene => 'CONVENE NOW';

  @override
  String get roomWinzipReviewTraining =>
      'Review a Training session while you wait';

  @override
  String get roomWinzipVoiceLine => 'Your Room is available now';

  @override
  String get roomPaywallTitle => 'Out of Room credits';

  @override
  String roomPaywallBody(String date) {
    return 'You\'ve used your Room credits. They reset on $date.';
  }

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

  @override
  String get tourIntroTitle => 'Welcome to your trading floor.';

  @override
  String get tourIntroSubtitle => 'A quick tour shows you how AMI Trade works.';

  @override
  String get tourTakeTheTour => 'Take the tour';

  @override
  String get tourSkipForNow => 'Skip for now';

  @override
  String get tourNext => 'Next →';

  @override
  String get tourDone => 'Got it';

  @override
  String get tourSkip => 'Skip tour';

  @override
  String get tourConveneTryNow => 'Try it now →';

  @override
  String get tourFloor1Title => 'YOUR CONCIERGE';

  @override
  String get tourFloor1Body =>
      'Always available. Ask anything — lessons, your portfolio, what to read next.';

  @override
  String get tourFloor2Title => 'YOUR ANALYST TEAM';

  @override
  String get tourFloor2Body =>
      '12 specialists, each with a domain. Tap any unlocked one to start a one-on-one.';

  @override
  String get tourFloor3Title => 'LOCKED AGENTS';

  @override
  String get tourFloor3Body =>
      'Complete the related lessons to unlock each analyst. Tap any locked one to see what you need.';

  @override
  String get tourFloor4Title => 'DAILY CHALLENGE';

  @override
  String get tourFloor4Body =>
      'One challenge a day sharpens your judgement. Takes under 2 minutes.';

  @override
  String get tourFloor5Title => 'CONVENE THE ROOM';

  @override
  String get tourFloor5Body =>
      'Your most powerful tool. All 12 agents analyze a stock together — then you decide.';

  @override
  String get tourCompletionFloor => 'Go convene your first Room.';

  @override
  String get tourPortfolio1Title => 'SIMULATION PORTFOLIO';

  @override
  String get tourPortfolio1Body =>
      'Use the + button to open a trade ticket. All trades are paper — no real money.';

  @override
  String get tourPortfolio2Title => 'TOTAL VALUE & P&L';

  @override
  String get tourPortfolio2Body =>
      'Track your portfolio value and running P&L here. Aim to beat the market.';

  @override
  String get tourPortfolio3Title => 'WATCHLIST';

  @override
  String get tourPortfolio3Body =>
      'Add tickers you\'re watching. Tap any row for quick actions: ask an analyst, convene, or open a trade.';

  @override
  String get tourCompletionPortfolio =>
      'Try a trade — all simulation, no risk.';

  @override
  String get tourJournal1Title => 'FILTER BY TYPE';

  @override
  String get tourJournal1Body =>
      'Everything gets logged — Room sessions, trades, briefings, lessons. Filter by type.';

  @override
  String get tourJournal2Title => 'SEARCH';

  @override
  String get tourJournal2Body =>
      'Find any entry by ticker, agent name, or keyword across your entire history.';

  @override
  String get tourJournal3Title => 'YOUR HISTORY';

  @override
  String get tourJournal3Body =>
      'Every entry is permanent. Your decisions live here — review them to improve.';

  @override
  String get tourCompletionJournal =>
      'Your history starts with your first Room session.';

  @override
  String get tourLessons1Title => 'LESSONS';

  @override
  String get tourLessons1Body =>
      'Lessons are your path to unlocking all 12 analysts. Complete tracks to grow your team.';

  @override
  String get tourLessons2Title => 'YOUR PROGRESS';

  @override
  String get tourLessons2Body =>
      'Track lessons completed and agents unlocked. Every lesson adds firepower to your team.';

  @override
  String get tourLessons3Title => 'LEARNING TRACKS';

  @override
  String get tourLessons3Body =>
      'Each hex is a learning track. Tap any to explore its lessons and unlock your analysts.';

  @override
  String get tourCompletionLessons =>
      'Start with Foundations to unlock your first analyst.';

  @override
  String get tourSettingsSectionTitle => 'WALKTHROUGH';

  @override
  String get tourSettingsRestart => 'Restart app tour';

  @override
  String get tourSettingsResetDone =>
      'Tour restarts next time you visit each section.';

  @override
  String get agentUnlockedHeadline => 'AGENT UNLOCKED';

  @override
  String agentUnlockedMeet(String name) {
    return 'MEET $name';
  }

  @override
  String get agentUnlockedLater => 'Later';

  @override
  String get challengeRelatedLesson => 'RELATED LESSON';

  @override
  String get challengeRelatedAgent => 'RELATED AGENT';

  @override
  String challengeNextIn(String time) {
    return 'Next challenge in $time';
  }

  @override
  String get challengeTapToAttempt => 'Tap to attempt →';

  @override
  String get challengeTapToReview => 'Answered — tap to review';

  @override
  String get leagueCardHeading => 'WEEKLY LEAGUE';

  @override
  String get leagueTitle => 'LEAGUE';

  @override
  String get leagueRankLabel => 'RANK';

  @override
  String get leaguePts => 'PTS';

  @override
  String get leagueRollsInLabel => 'ROLLS IN';

  @override
  String get leagueUnassigned =>
      'Your first league starts Monday — keep earning.';

  @override
  String get leagueError => 'Couldn\'t load standings.';

  @override
  String get leagueYou => 'YOU';

  @override
  String get leagueHistoryTitle => 'PAST WEEKS';

  @override
  String get leagueHistoryEmpty => 'No finished weeks yet.';

  @override
  String get leagueOutcomePromoted => 'Promoted';

  @override
  String get leagueOutcomeRelegated => 'Relegated';

  @override
  String get leagueOutcomeStay => 'Held';

  @override
  String get settingsSectionLeague => 'LEAGUE';

  @override
  String get leagueHandle => 'HANDLE';

  @override
  String get leagueReputation => 'REPUTATION';

  @override
  String get leagueRegenerate => 'REGENERATE HANDLE';

  @override
  String get leagueRegenerateFailed =>
      'Couldn\'t change your handle — you get only one change.';

  @override
  String get settingsAppearanceValue => 'DARK — floor standard';

  @override
  String get settingsAppearanceBody =>
      'The floor runs dark. A light theme arrives in a later release.';

  @override
  String get watchlistEmptyTitle => 'No tickers yet';

  @override
  String get alpacaNoPositions => 'No open positions';

  @override
  String get disclaimerShort =>
      'Educational simulation. Not investment advice.';

  @override
  String get shareTooltip => 'Share';

  @override
  String get shareCardStreakUnit => 'DAY STREAK';

  @override
  String get shareCardUnlockKicker => 'AGENT UNLOCKED';

  @override
  String get shareCardVerdictKicker => 'THE ROOM\'S VERDICT';

  @override
  String get shareCardPromotedKicker => 'LEAGUE STANDING';

  @override
  String get shareCaption =>
      'My AMI Trade analyst desk. Educational simulation — not investment advice.';

  @override
  String get lessonReplay => 'Replay';

  @override
  String bugReportThanks(String shortId) {
    return 'Report received — ref $shortId. Thank you.';
  }

  @override
  String bugReportResolved(String title) {
    return 'Fixed: $title';
  }
}
