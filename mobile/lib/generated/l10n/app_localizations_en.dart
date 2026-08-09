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
  String tickerNotFound(String ticker) {
    return '$ticker isn\'t a listed ticker — check the symbol and try again.';
  }

  @override
  String tickerNotFoundWithSuggestion(String ticker) {
    return '$ticker was not found.';
  }

  @override
  String tickerDidYouMean(String ticker, String company) {
    return 'Did you mean $ticker — $company?';
  }

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
  String get floorRestartOnboardingConfirmTitle => 'RESTART ONBOARDING?';

  @override
  String get floorRestartOnboardingConfirmBody =>
      'This runs the whole interview again from the first question. It does not replace a mandate you already have — change that in Settings → My Mandate. Your portfolio and trades are untouched.';

  @override
  String get floorRestartOnboardingConfirmCta => 'RESTART';

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
  String get floorLockedTapHint => 'Tap a lesson to start';

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
  String get portfolioTabPositions => 'POSITIONS';

  @override
  String get portfolioTabWatchlist => 'WATCHLIST';

  @override
  String get portfolioTabHistory => 'HISTORY';

  @override
  String get portfolioOpenTrades => 'OPEN TRADES';

  @override
  String portfolioClosedScope(int count) {
    return 'ACROSS ALL $count CLOSED';
  }

  @override
  String get portfolioClosed => 'CLOSED';

  @override
  String portfolioLastNClosed(int count) {
    return 'LAST $count CLOSED';
  }

  @override
  String portfolioClosedSpan(String from, String to) {
    return '$from – $to';
  }

  @override
  String portfolioShowAll(int count) {
    return 'SHOW ALL $count';
  }

  @override
  String get portfolioReviewInJournal => 'REVIEW IN JOURNAL';

  @override
  String portfolioJournalRetention(int days, int count, int total) {
    return 'Your Journal shows the last $days days — $count of these $total are older. Nothing is deleted; they stay here.';
  }

  @override
  String get portfolioJournalRetentionUnknown =>
      'Your Journal may not show all of these. Nothing is deleted; they stay here.';

  @override
  String get portfolioStatWon => 'WON';

  @override
  String get portfolioStatLost => 'LOST';

  @override
  String get portfolioStatHitRate => 'HIT RATE';

  @override
  String get portfolioStatNet => 'NET';

  @override
  String get portfolioSearchTicker => 'SEARCH TICKER…';

  @override
  String get portfolioSortNewest => 'NEWEST';

  @override
  String get portfolioSortValue => 'VALUE';

  @override
  String get portfolioSortAZ => 'A–Z';

  @override
  String get portfolioNoOpenPositions => 'No open positions';

  @override
  String get portfolioEquityCurveHeading => 'EQUITY CURVE';

  @override
  String get portfolioEquityCurveWindowReturn => 'WINDOW RETURN';

  @override
  String get portfolioEquityCurveEmpty =>
      'Your history starts building from today.';

  @override
  String get portfolioEquityCurveSimulatedNote =>
      'Dashed segments used simulated pricing, not a live quote.';

  @override
  String get gamesHomeTitle => 'THE GAME';

  @override
  String get gamesLoadError => 'Couldn\'t load your game runs.';

  @override
  String get gamesRetry => 'retry';

  @override
  String gamesDaysLeft(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count days left',
      one: '1 day left',
    );
    return '$_temp0';
  }

  @override
  String get gamesTwrLabel => 'RETURN THIS RUN';

  @override
  String get gamesTradeCta => 'trade';

  @override
  String get gamesOtherRunsHeading => 'OTHER LIVE RUNS';

  @override
  String get gamesFallbackHeading => 'Enter the next weekly field';

  @override
  String get gamesFallbackBody =>
      'A fresh 10,000 AMI Cash book, five trading days, no mandate.';

  @override
  String gamesFieldEntrantCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count traders already in',
      one: '1 trader already in',
    );
    return '$_temp0';
  }

  @override
  String get gamesEnterCta => 'enter this week\'s field';

  @override
  String get gamesDisclosureHeading => 'NO ARENA RULES';

  @override
  String get gamesDisclosureBody =>
      'No mandate, no position or sector limits, and no halal screening — names blocked on the training floor can be traded here. Real market frictions still apply: trading costs, and fills only during market hours.';

  @override
  String get gamesDisclosureChip => 'NO MANDATE · NO HALAL SCREEN';

  @override
  String get gamesEntrySheetHeading => 'Enter this field';

  @override
  String get gamesEntryStakeLine =>
      '10,000 AMI Cash, fresh for this run. Free to enter, always.';

  @override
  String get gamesEntryConfirmCta => 'enter this field';

  @override
  String get gamesEntryConfirming => 'entering…';

  @override
  String get gamesQueueFirstNote =>
      'Plan tonight, fills at the open. An order placed outside US market hours queues for the next open — free to cancel any time before it fills.';

  @override
  String get gamesTicketHeading => 'TRADE TICKET';

  @override
  String get gamesTicketStepTicker => '1 · PICK A TICKER';

  @override
  String get gamesTicketStepSize => '2 · PICK A SIZE';

  @override
  String get gamesTicketStepConfirm => '3 · CONFIRM';

  @override
  String get gamesTicketTickerHint => 'or type one';

  @override
  String get gamesTicketSizeAllIn => 'ALL-IN';

  @override
  String get gamesTicketShares => 'SHARES';

  @override
  String get gamesTicketEstFee => 'EST. TRADING COST (MODELED)';

  @override
  String get gamesTicketBookPct => '% OF YOUR BOOK';

  @override
  String get gamesTicketUnknownNote =>
      'Order sent, but AMI could not confirm what happened to it. Check your run before placing another.';

  @override
  String get gamesTicketCashAvailable => 'AVAILABLE TO DEPLOY';

  @override
  String gamesTicketSizeAmount(String pct, String amount) {
    return '$pct% · $amount AMI Cash';
  }

  @override
  String gamesTicketCashCommitted(String amount, int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count queued orders',
      one: '1 queued order',
    );
    return '$amount committed to $_temp0';
  }

  @override
  String get gamesRunTitle => 'My run';

  @override
  String get gamesRunBookValue => 'BOOK VALUE';

  @override
  String get gamesRunCashLabel => 'Cash';

  @override
  String get gamesRunCommittedLabel => 'Committed to queued orders';

  @override
  String get gamesRunAvailableLabel => 'Available to deploy';

  @override
  String get gamesRunInvestedLabel => 'Invested';

  @override
  String get gamesRunHeatHeading => 'BOOK HEAT';

  @override
  String gamesRunHeatConcentration(String pct, String ticker) {
    return '$pct% in $ticker';
  }

  @override
  String get gamesRunHeatAllCash => 'All cash. Nothing at risk yet.';

  @override
  String get gamesRunPositionsHeading => 'POSITIONS';

  @override
  String gamesRunPositionSub(String qty, String avg) {
    return '$qty @ $avg avg';
  }

  @override
  String get gamesRunQueuedHeading => 'WAITING FOR THE OPEN';

  @override
  String gamesRunQueuedSub(String qty, String total) {
    return '$qty shares · est. $total';
  }

  @override
  String get gamesRunQueuedEstimateNote =>
      'Estimated at the current price. It fills at the next open\'s price, which will differ.';

  @override
  String get gamesRunQueuedStaleNote =>
      'Prices unavailable — these estimates are simulated, not live.';

  @override
  String get gamesRunCancelCta => 'Cancel';

  @override
  String get gamesRunCancelConfirmTitle => 'Cancel this order?';

  @override
  String gamesRunCancelConfirmBody(String side, String qty, String ticker) {
    return '$side $qty $ticker will not be placed at the next open. Nothing is charged either way.';
  }

  @override
  String get gamesRunCancelKeep => 'Keep it';

  @override
  String get gamesRunCancelledToast => 'Order cancelled.';

  @override
  String get gamesRunCancelRaceToast => 'Too late — that order already filled.';

  @override
  String get gamesRunEmptyBookHeading => 'Nothing on the book yet';

  @override
  String gamesRunEmptyBookBody(String amount, String days) {
    return '$amount AMI Cash, $days to deploy it. There is no rule about how — one name or twenty, all of it or none. The clock is the only thing that is fixed.';
  }

  @override
  String gamesRunDaysToDeploy(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count days',
      one: '1 day',
    );
    return '$_temp0';
  }

  @override
  String get gamesRunMarksStaleNote =>
      'Prices unavailable — this book is marked with simulated prices.';

  @override
  String gamesRunFeesPaid(String amount, int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count trades',
      one: '1 trade',
    );
    return '$amount paid in trading costs · $_temp0';
  }

  @override
  String get gamesTicketPlacing => 'placing…';

  @override
  String get gamesTicketConfirmCta => 'place order';

  @override
  String get gamesTicketQueuedNote =>
      'Queued — fills at the next US market open. Free to cancel any time before then.';

  @override
  String get gamesTicketFilledNote => 'Filled.';

  @override
  String get gamesCloseAppBarTitle => 'THE CLOSE';

  @override
  String get gamesCloseLoadError => 'Couldn\'t load this run\'s close.';

  @override
  String get gamesCloseTitleFinished => 'RUN CLOSED';

  @override
  String get gamesCloseTitleForfeit => 'CHAPTER CLOSED';

  @override
  String get gamesCloseVoidChip => 'VOID';

  @override
  String get gamesCloseVoidHeading => 'THIS RUN DIDN\'T SCORE';

  @override
  String get gamesCloseVoidReasonUnknown =>
      'The pricing feed didn\'t produce a valid day for this field.';

  @override
  String gamesCloseStipendNote(int points) {
    return '+$points pts · finish stipend';
  }

  @override
  String gamesCloseBasisThinField(int count) {
    return 'Field of $count. Scored against the S&P 500, not against the field.';
  }

  @override
  String gamesCloseBasisRanked(int rank, int count) {
    return 'Ranked $rank of $count in your field.';
  }

  @override
  String get gamesCloseCareerPointsLabel => 'CAREER POINTS · THIS RUN';

  @override
  String get gamesCloseInsightVoidNote =>
      'Nothing to compare — this run wasn\'t scored.';

  @override
  String gamesCloseNearMissLine(String gap, String label) {
    return 'You were $gap% off $label.';
  }

  @override
  String get gamesCloseInsightIndexBeat =>
      'The index pays no fees. You beat it anyway.';

  @override
  String gamesCloseInsightIndexNeutral(String pct) {
    return 'The S&P returned $pct over the same window.';
  }

  @override
  String gamesCloseCounterfactualFirstPicks(String pct) {
    return 'If you\'d held your first picks untouched: $pct';
  }

  @override
  String gamesCloseCounterfactualIndex(String pct) {
    return 'If you\'d just held the S&P: $pct';
  }

  @override
  String get gamesCloseDebriefCta => 'full debrief';

  @override
  String get gamesCloseReentryHeading => 'THE NEXT ONE\'S OPEN';

  @override
  String get gamesCloseReentryCta => 'enter the next field';

  @override
  String get gamesDebriefHeading => 'FULL DEBRIEF';

  @override
  String get gamesDebriefBasisLabel => 'BASIS';

  @override
  String get gamesDebriefAlphaScoredLabel => 'SCORED · NET OF ENTRY FEE';

  @override
  String get gamesDebriefAlphaDisplayLabel => 'VS COSTLESS INDEX';

  @override
  String get gamesDebriefIntentLabel => 'YOU SAID';

  @override
  String get gamesDebriefWildnessLabel => 'WILDNESS INDEX';

  @override
  String get gamesDebriefFeesLabel => 'TRADING COSTS PAID';

  @override
  String get gamesDebriefTradeCountLabel => 'TRADES THIS RUN';

  @override
  String get gamesDebriefForfeitNote =>
      'This run was forfeited — capital was rescued, and the record still shows it.';

  @override
  String get gamesDebriefVoidExplainer =>
      'A VOID run never pays a placement or alpha score. Any finish stipend still applies — the feed failed, not you.';

  @override
  String get gamesIntentWild => 'WILD';

  @override
  String get gamesIntentThesis => 'TESTING A THESIS';

  @override
  String get gamesIntentDisciplined => 'DISCIPLINED';

  @override
  String get gamesRecordCta => 'your record';

  @override
  String get gamesRecordTitle => 'YOUR RECORD';

  @override
  String get gamesRecordLoadError => 'Couldn\'t load your record.';

  @override
  String get gamesRecordIdentityHeading => 'IDENTITY';

  @override
  String get gamesRecordMovementHeading => 'MOVEMENT';

  @override
  String get gamesRecordHistoryHeading => 'HISTORY';

  @override
  String get gamesRecordCareerPointsLabel => 'CAREER POINTS';

  @override
  String get gamesRecordEnteredLabel => 'ENTERED';

  @override
  String get gamesRecordFinishedLabel => 'FINISHED';

  @override
  String get gamesRecordForfeitedLabel => 'FORFEITED';

  @override
  String get gamesRecordHistoryEmpty =>
      'No runs yet — your first close will land here.';

  @override
  String get gamesRecordPrHeading => 'PERSONAL RECORDS';

  @override
  String get gamesRecordPrEmpty => 'Finish a run to set your first PR.';

  @override
  String get gamesPrBestReturn => 'BEST WEEKLY RETURN';

  @override
  String get gamesPrBestAlpha => 'BEST ALPHA VS S&P';

  @override
  String get gamesPrBestDrawdown => 'BEST DRAWDOWN CONTROL';

  @override
  String get gamesPrLongestHold => 'LONGEST HOLD';

  @override
  String get gamesPrLongestStreak => 'LONGEST FINISH STREAK';

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
  String get tickerDetailChartRejected => 'AMI can\'t chart this one.';

  @override
  String get tickerDetailChartNoHistory => 'No price history for this period.';

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
  String get tickerDetailActionSetAlert => 'ALERT';

  @override
  String priceAlertSheetTitle(String ticker) {
    return 'Set price alert — $ticker';
  }

  @override
  String get priceAlertSheetThresholdLabel => 'Alert type';

  @override
  String get priceAlertTypeStop => 'Stop — price falls below (protective)';

  @override
  String get priceAlertTypeTarget =>
      'Target — price rises above (profit-taking)';

  @override
  String get priceAlertTypeManualAbove => 'Price rises above';

  @override
  String get priceAlertTypeManualBelow => 'Price falls below';

  @override
  String get priceAlertSheetPriceLabel => 'Price';

  @override
  String get priceAlertSheetCreate => 'Create alert';

  @override
  String get priceAlertsSectionHeading => 'PRICE ALERTS';

  @override
  String get priceAlertRowCancelTooltip => 'Cancel this alert';

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
  String tickerDetailDividendExDate(String date) {
    return 'ex-div $date';
  }

  @override
  String tickerDetailDividendRate(String rate) {
    return '$rate/sh';
  }

  @override
  String get tickerDetailLotsHeading => 'COST BASIS LOTS';

  @override
  String get tickerDetailLotStatusOpen => 'OPEN';

  @override
  String get tickerDetailLotStatusPartiallyClosed => 'PARTIAL';

  @override
  String get tickerDetailLotStatusClosed => 'CLOSED';

  @override
  String tickerDetailLotEntry(String date, String price) {
    return 'Opened $date @ \$$price';
  }

  @override
  String tickerDetailLotQuantity(String open, String closed) {
    return '$open open / $closed closed';
  }

  @override
  String tickerDetailLotRealised(String pnl) {
    return 'Realised $pnl';
  }

  @override
  String tickerDetailLotUnrealised(String pnl) {
    return 'Unrealised $pnl';
  }

  @override
  String get tickerDetailLotUnrealisedUnknown => 'Unrealised —';

  @override
  String get portfolioSectorAllocationHeading => 'SECTOR ALLOCATION';

  @override
  String get portfolioSectorOtherLabel => 'Other (unclassified)';

  @override
  String portfolioSectorBreach(String sector, String pct, String limit) {
    return '$sector at $pct% exceeds your $limit% mandate limit';
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
  String get journalFilterChallenges => 'CHALLENGES';

  @override
  String journalRetentionWarning(int days) {
    return 'Floor Pass: last $days days only. Upgrade to see everything — nothing is deleted.';
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
  String get journalEntryTypeChallenge => 'CHALLENGE';

  @override
  String get journalEntryTypeHealth => 'HEALTH';

  @override
  String get journalEntryTypeUnknown => 'UNKNOWN';

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
  String get lessonReaderUnavailableTitle => 'LESSON UNAVAILABLE';

  @override
  String get lessonReaderPrerequisites => 'PREREQUISITES';

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
  String get settingsRetroAuditFailed =>
      'Couldn\'t check your holdings against the new limit — open Portfolio to verify.';

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
  String get settingsSectionRiskLimits => 'RISK LIMITS';

  @override
  String get settingsRiskLimitsProfileFollowing =>
      'Following your risk profile';

  @override
  String get settingsRiskLimitsProfileCustom => 'Custom';

  @override
  String get settingsRiskLimitsExpand => 'Set my own limits';

  @override
  String get settingsRiskLimitsOff => 'OFF';

  @override
  String get settingsRiskLimitsSectorCapLabel => 'Sector concentration cap';

  @override
  String get settingsRiskLimitsSectorCapExplain =>
      'Blocks a BUY that would push any one sector above this share of your portfolio. Unset follows your risk profile.';

  @override
  String get settingsRiskLimitsSingleNameCapLabel => 'Single-name position cap';

  @override
  String get settingsRiskLimitsSingleNameCapExplain =>
      'Blocks a BUY that would size one position above this share of your portfolio. Unset follows your risk profile.';

  @override
  String get settingsRiskLimitsCooldownLabel => 'Post-loss cooldown';

  @override
  String get settingsRiskLimitsCooldownExplain =>
      'Blocks new BUYs for this many hours after your last realised loss.';

  @override
  String get settingsRiskLimitsMaxOpenPositionsLabel => 'Max open positions';

  @override
  String get settingsRiskLimitsMaxOpenPositionsExplain =>
      'Blocks a BUY that would open a new ticker once you\'re at this many distinct positions. Adding to a position you already hold is unaffected.';

  @override
  String get settingsRiskLimitsMaxTradesPerDayLabel => 'Max trades per day';

  @override
  String get settingsRiskLimitsMaxTradesPerDayExplain =>
      'Blocks any trade once you\'ve submitted this many today (UTC calendar day).';

  @override
  String get settingsRiskLimitsMaxTradesPerWeekLabel => 'Max trades per week';

  @override
  String get settingsRiskLimitsMaxTradesPerWeekExplain =>
      'Blocks any trade once you\'ve submitted this many this week (Monday 00:00 UTC).';

  @override
  String get settingsRiskLimitsMaxOpenRiskLabel => 'Total open-risk cap';

  @override
  String get settingsRiskLimitsMaxOpenRiskExplain =>
      'Caps the sum of (position size % x stop distance %) across your open positions — your total capital at risk to stops.';

  @override
  String get settingsRiskLimitsMaxOpenRiskPreviewNote =>
      'Confirmed at trade submission — not shown as within-limits in the trade preview.';

  @override
  String get settingsRiskLimitsDisclosureFollowing =>
      'This replaces your risk-profile default with an explicit value, effective immediately.';

  @override
  String get settingsRiskLimitsDisclosureLooser =>
      'This allows more risk than your current setting.';

  @override
  String get settingsRiskLimitsDisclosureOff =>
      'This removes the limit entirely — it will not block anything.';

  @override
  String get settingsRiskLimitsDisclosure100 =>
      '100% removes any real ceiling from this limit — allowed, but it means no protection here.';

  @override
  String get settingsRiskLimitsRetroTitle =>
      'Some holdings now breach this limit';

  @override
  String get settingsRiskLimitsRetroBody =>
      'Affected holdings are flagged below. New BUYs that would add to the breach are blocked. Nothing is sold automatically.';

  @override
  String settingsRiskLimitsRetroTickers(String tickers) {
    return 'Flagged: $tickers';
  }

  @override
  String get settingsRiskLimitsRetroDismiss => 'Got it';

  @override
  String get settingsComplianceHalal => 'Sharia screen — AAOIFI';

  @override
  String get settingsComplianceHalalSubtitle =>
      'AAOIFI standard, S&P 500 Sharia index';

  @override
  String get settingsComplianceHalalExplainTitle => 'Sharia screen (AAOIFI)';

  @override
  String get settingsComplianceHalalExplainBody =>
      'Restricts trading to companies that pass the AAOIFI Sharia screen, as applied by S&P Dow Jones to the S&P 500 Sharia Industry Exclusions Index. AMI reads that index\'s published constituents — it does not run its own ruling.\n\nCoverage is the S&P 500. A company outside it hasn\'t been screened by this standard, so AMI will tell you it\'s unscreened rather than guess. Unscreened is not a ruling either way, and it does not stop the trade.\n\nSharia standards disagree. AAOIFI, DJIM, FTSE, MSCI and S&P apply different thresholds and denominators, so the same company can pass one and fail another — today, AAOIFI and FTSE differ on about half the names between them. This screen follows AAOIFI.';

  @override
  String shariaVerdictPass(
      String ticker, String standard, String source, String date) {
    return '$ticker passes the $standard screen ($source, as of $date).';
  }

  @override
  String shariaVerdictScreenedOut(
      String ticker, String standard, String source, String date) {
    return '$ticker is in the S&P 500 but does not pass the $standard screen ($source, as of $date), so this mandate won\'t trade it.';
  }

  @override
  String shariaVerdictUnknown(String ticker, String standard) {
    return '$ticker isn\'t in the S&P 500, so the $standard screen AMI uses hasn\'t reviewed it. That\'s not a ruling either way — AMI doesn\'t know.';
  }

  @override
  String shariaVerdictPaused(String date) {
    return 'AMI couldn\'t refresh the Sharia screen (last updated $date). The halal filter is paused until it can.';
  }

  @override
  String get shariaVerdictLabelPass => 'SHARIA SCREEN';

  @override
  String get shariaVerdictLabelPaused => 'SHARIA SCREEN PAUSED';

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
  String get signInUseEmailInstead => 'Use email instead';

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
  String get roomAgentThinking => 'thinking…';

  @override
  String get roomAgentInterrupted => 'INTERRUPTED';

  @override
  String get roomAgentTruncatedMark =>
      'Cut short by its length limit — open the transcript to read what landed.';

  @override
  String get roomAgentResponded => 'responded';

  @override
  String roomAgentStatusSemantic(String agent, String status) {
    return '$agent: $status';
  }

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
    return 'You\'ve used this Room — AMI\'s already topping you up. Your next Room unlocks in $countdown.';
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
    return 'Sorry — you\'re out of Room credits for now. They\'ll refresh on $date.';
  }

  @override
  String get roomServerErrorTitle => 'AMI\'s briefly offline';

  @override
  String get roomServerErrorBody =>
      'The connection dropped for a moment — nothing\'s wrong on your end. Give it a second and try again.';

  @override
  String get roomRetry => 'TRY AGAIN';

  @override
  String get roomLiveDataNoticeTitle => 'Live data';

  @override
  String roomLiveDataFeedLive(String feed) {
    return '$feed: live feed used.';
  }

  @override
  String roomLiveDataFeedWithheld(String feed) {
    return '$feed: live data available — needs credits.';
  }

  @override
  String roomLiveDataFeedUnavailable(String feed) {
    return '$feed: live data unavailable right now.';
  }

  @override
  String roomLiveDataSurchargeCharged(int surcharge) {
    return 'Live news + social cost $surcharge extra credits this run.';
  }

  @override
  String get roomLiveDataUpgradeCta => 'UPGRADE FOR LIVE DATA';

  @override
  String roomLiveDataFeedTenure(String feed) {
    return '$feed: live data available — needs a plan upgrade.';
  }

  @override
  String get roomLiveDataTenureUpgradeCta => 'UPGRADE YOUR PLAN';

  @override
  String roomAgentWithheldChairLabel(String agent) {
    return '$agent — off your roster on this plan';
  }

  @override
  String roomAgentWithheldRosterNote(String agent, int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: '$days days',
      one: '1 day',
    );
    return 'Next roster change: $agent in $_temp0.';
  }

  @override
  String get roomVerdictActionNoVerdict => 'NO VERDICT';

  @override
  String get roomVerdictOpinionsHeading => 'Not in the room';

  @override
  String get roomVerdictOpinionsNote =>
      'This verdict was reached without their input.';

  @override
  String roomVerdictIncludeAnalystCta(String agent) {
    return 'Include the $agent →';
  }

  @override
  String get upgradeSheetTitle => 'Upgrade your desk';

  @override
  String get upgradeSheetSubtitle =>
      'Unlock more Rooms and premium analysis. Prices are shown for your region.';

  @override
  String get upgradePlanTrader => 'Trader';

  @override
  String get upgradePlanFloorManager => 'Floor Manager';

  @override
  String get upgradeIntervalMonthly => 'Monthly';

  @override
  String get upgradeIntervalAnnual => 'Annual';

  @override
  String get upgradeCreditPacksTitle => 'Credit packs';

  @override
  String upgradeCreditPackCredits(int credits) {
    return '+$credits credits';
  }

  @override
  String get upgradeBuy => 'BUY';

  @override
  String get upgradeRestore => 'Restore purchases';

  @override
  String get upgradeUnavailableTitle => 'Upgrades aren\'t available yet';

  @override
  String upgradeUnavailableBody(String date) {
    return 'In-app purchases will switch on shortly. Your Room credits still refresh on $date.';
  }

  @override
  String get upgradePurchasePending =>
      'Your purchase is processing — we\'ll unlock it as soon as it clears.';

  @override
  String get upgradePurchaseFailed =>
      'That didn\'t go through. No charge was made — please try again.';

  @override
  String get upgradePurchaseSuccess => 'You\'re upgraded. Welcome to the desk.';

  @override
  String get upgradeRestoreNone => 'No purchases found to restore.';

  @override
  String get settingsSectionMembership => 'MEMBERSHIP';

  @override
  String get settingsMembershipUpgrade => 'Upgrade or manage plan';

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

  @override
  String get roomViewModeBoard => 'BOARD';

  @override
  String get roomViewModeTranscript => 'TRANSCRIPT';

  @override
  String get roomPmCardHeading => 'PORTFOLIO MANAGER';

  @override
  String get roomHeroApprove => 'THE ROOM APPROVED';

  @override
  String get roomHeroPass => 'THE ROOM PASSED';

  @override
  String get roomHeroReject => 'BLOCKED BY YOUR MANDATE';

  @override
  String get roomHeroNoVerdict => 'NO VERDICT ISSUED';

  @override
  String get roomHeroNoResult => 'THE ROOM DID NOT FINISH';

  @override
  String get roomHeroUnitPortfolio => 'OF PORTFOLIO';

  @override
  String roomHeroUnitHorizon(int days) {
    return '$days-DAY HORIZON';
  }

  @override
  String get roomHeroNoPosition => 'NO POSITION';

  @override
  String get roomHeroNotIssued => 'NOT ISSUED';

  @override
  String roomHeroBlockedCount(int count) {
    return 'BLOCKED · $count VIOLATIONS';
  }

  @override
  String get roomHeroNoResultValue => 'NO RESULT';

  @override
  String get roomHeroConveneAgain => 'CONVENE AGAIN';

  @override
  String get roomOverrideHeading =>
      'MANDATE OVERRIDE — YOUR RULES CHANGED THE PM\'S CALL';

  @override
  String roomCombVoices(int count) {
    return '$count VOICES';
  }

  @override
  String roomCombStated(int count) {
    return '$count STATED A VIEW';
  }

  @override
  String get roomCombFor => 'FOR';

  @override
  String get roomCombNeutral => 'NEUTRAL';

  @override
  String get roomCombAgainst => 'AGAINST';

  @override
  String get roomCombNotStated => 'NOT STATED';

  @override
  String get roomCombNotRecorded => 'NOT RECORDED';

  @override
  String get roomCombNotRecordedBody =>
      'Agent stances were not recorded for this run. Open the transcript to read what each one said.';

  @override
  String get roomRibbonHeading => 'RISK → REWARD';

  @override
  String roomRibbonDerived(String levels) {
    return '$levels SET BY AMI, NOT THE PM';
  }

  @override
  String get roomGeometryNoProvenance =>
      'TRADE GEOMETRY · PROVENANCE UNAVAILABLE';

  @override
  String get roomRosterGap => 'THE ROSTER GAP';

  @override
  String roomRosterGapCount(int count) {
    return '$count NOT HEARD';
  }

  @override
  String get roomRowNotHeard => 'NOT HEARD';

  @override
  String get roomRowNoResponse => 'NO RESPONSE';

  @override
  String roomTranscriptHint(int count) {
    return '$count CONTRIBUTIONS · TAP A ROW TO READ IT IN FULL';
  }

  @override
  String get roomWhyExpand => 'WHY';

  @override
  String get roomSheetStance => 'STANCE';

  @override
  String get roomSheetConviction => 'CONVICTION';

  @override
  String get roomSheetReadFullDebate => 'READ THE FULL DEBATE';

  @override
  String get roomStanceFor => 'FOR';

  @override
  String get roomStanceAgainst => 'AGAINST';

  @override
  String get roomStanceNeutral => 'NEUTRAL';

  @override
  String get roomConvictionLow => 'LOW';

  @override
  String get roomConvictionMedium => 'MEDIUM';

  @override
  String get roomConvictionHigh => 'HIGH';

  @override
  String get roomPhaseAnalysts => 'ANALYSTS';

  @override
  String get roomPhaseResearchers => 'RESEARCHERS';

  @override
  String get roomPhaseSynthesis => 'SYNTHESIS';

  @override
  String get roomPhaseExecution => 'EXECUTION';

  @override
  String get roomPhaseRisk => 'RISK';

  @override
  String get roomPhaseVerdict => 'VERDICT';

  @override
  String journalLevelsAsOf(String date) {
    return 'LEVELS AS OF $date — A RECORD, NOT A CURRENT SETUP';
  }

  @override
  String get journalRerunWithMandate => 'RE-RUN WITH CURRENT MANDATE';

  @override
  String aiCoachEmptyStateHint(int count) {
    return '$count questions and answers across platform, psychology, scams, AI meta, and beginner / intermediate topics. Type to search.';
  }

  @override
  String get pushSoftAskTitle => 'Notifications';

  @override
  String get pushSoftAskBody =>
      'AMI can notify you the moment a price alert fires or a Room verdict is ready. Turn on notifications?';

  @override
  String get pushSoftAskDecline => 'Not now';

  @override
  String get pushSoftAskAccept => 'Turn on';

  @override
  String get portfolioHealthTitle => 'PORTFOLIO HEALTH';

  @override
  String get portfolioHealthWindowSubtitle =>
      '≈66-DAY EFFECTIVE WINDOW · HOLDINGS-BASED';

  @override
  String get portfolioHealthTileVolatility => 'VOLATILITY';

  @override
  String get portfolioHealthTileVolatilityUnit => '% ANNUALISED · TOTAL BOOK';

  @override
  String portfolioHealthTileVolatilityBenchmark(String pct) {
    return 'S&P 500 $pct%';
  }

  @override
  String get portfolioHealthTileBeta => 'BETA';

  @override
  String get portfolioHealthTileBetaUnit => '× THE S&P 500 · MEASURED WINDOW';

  @override
  String portfolioHealthBetaLowR2(String pct) {
    return 'Market explains $pct% of daily moves';
  }

  @override
  String get portfolioHealthTileBets => 'EFFECTIVE BETS';

  @override
  String portfolioHealthTileBetsUnit(String n) {
    return 'INDEPENDENT BETS · OF $n HOLDINGS';
  }

  @override
  String get portfolioHealthTileMdd => 'MAX DRAWDOWN';

  @override
  String portfolioHealthTileMddUnit(String n) {
    return 'TRAILING $n-DAY WINDOW · REALISED';
  }

  @override
  String get portfolioHealthTileConcentration =>
      'INVESTED WEIGHT CONCENTRATION';

  @override
  String portfolioHealthTileConcentrationUnit(String n) {
    return 'EFFECTIVE HOLDINGS BY WEIGHT · OF $n HELD';
  }

  @override
  String get portfolioHealthEtfChip => 'ETF OVERLAP NOT COUNTED';

  @override
  String get portfolioHealthBarsHeading => 'RISK VS MONEY';

  @override
  String get portfolioHealthBarsCaption =>
      'Shares of invested risk and invested money; cash is shown on its own line. Not a forecast and not a return.';

  @override
  String get portfolioHealthBarsNegativeNote =>
      'A negative share means this holding offset risk over the window.';

  @override
  String get portfolioHealthLegendRisk => 'RISK';

  @override
  String get portfolioHealthLegendMoney => 'MONEY';

  @override
  String portfolioHealthCashLine(String pct) {
    return 'CASH · $pct% OF TOTAL BOOK';
  }

  @override
  String get portfolioHealthPartialChip => 'PARTIAL';

  @override
  String portfolioHealthPartialNote(String tickers, String covered) {
    return 'Excludes $tickers. Numbers describe $covered% of invested value.';
  }

  @override
  String get portfolioHealthInsufficientTitle => 'NOT ENOUGH HISTORY YET';

  @override
  String portfolioHealthInsufficientBody(String n) {
    return 'Price history available to AMI\'s engine covers $n trading days; 126 needed.';
  }

  @override
  String portfolioHealthInsufficientDroppedBody(String covered) {
    return 'Usable price history covers $covered% of invested value; AMI needs at least 80%.';
  }

  @override
  String get portfolioHealthInsufficientGenericBody =>
      'AMI could not measure this book\'s risk over the available window.';

  @override
  String portfolioHealthInsufficientSparseGridBody(String n, String days) {
    return 'Price history available to AMI\'s engine has gaps: $n trading days spread across $days calendar days.';
  }

  @override
  String portfolioHealthTnNote(String t, String n) {
    return '$t aligned trading days across $n holdings — too few for AMI to attribute risk reliably.';
  }

  @override
  String get portfolioHealthBenchmarkNote =>
      'S&P 500 history did not align with this book\'s window; beta is not measured.';

  @override
  String get portfolioHealthBetaUnavailableNote =>
      'AMI could not measure this book\'s beta against the S&P 500 over the available window.';

  @override
  String get portfolioHealthBetsUnavailableNote =>
      'AMI could not measure how many independent bets this book holds over the available window.';

  @override
  String get portfolioHealthVolUnavailableNote =>
      'AMI could not measure this book\'s volatility over the available window.';

  @override
  String get portfolioHealthRiskUnavailableNote =>
      'AMI could not measure how this book\'s risk splits across its holdings over the available window.';

  @override
  String portfolioHealthMddNote(String n) {
    return '$n daily snapshots so far; realised drawdown needs 21.';
  }

  @override
  String get portfolioHealthMockRefusalTitle => 'LIVE MARKET DATA IS OFF';

  @override
  String get portfolioHealthMockRefusalBody =>
      'AMI measures portfolio risk from real price history only. It will not compute these numbers from simulated prices.';

  @override
  String get portfolioHealthEmptyTitle => 'NO HOLDINGS TO MEASURE';

  @override
  String get portfolioHealthErrorBody =>
      'AMI\'s engine did not respond. Tap to retry.';

  @override
  String get portfolioHealthUnknownStatusBody =>
      'AMI\'s engine returned a result this version of the app does not recognise. Tap to retry.';

  @override
  String get portfolioHealthCtaFinding => 'FULL FINDING';

  @override
  String portfolioHealthTrialChip(String k, String n) {
    return '$k of $n trial Findings left';
  }

  @override
  String portfolioHealthDailyCapNote(String used, String cap) {
    return '$used of $cap Findings used today. Available again tomorrow.';
  }

  @override
  String get portfolioHealthUpgradeBody =>
      'Findings are included in Trader and Floor Manager plans.';

  @override
  String get portfolioHealthUpgradeCta => 'SEE PLANS';

  @override
  String get findingScreenTitle => 'Portfolio Health';

  @override
  String get findingSectionF1 => 'F1 · HEADLINES';

  @override
  String get findingSectionF2 => 'F2 · EXECUTIVE SUMMARY';

  @override
  String get findingSectionF3 => 'F3 · DETAILED ANALYSIS';

  @override
  String get findingSectionF4 => 'F4 · CONCLUSION';

  @override
  String get findingSectionF5 => 'F5 · WHAT THE NUMBERS POINT TO';

  @override
  String get findingUnavailableBody =>
      'AMI cannot generate a Finding right now — live market data is off.';

  @override
  String get versionGateScreenTitle => 'Update Required';

  @override
  String get versionGateUpdateCta => 'Update Now';

  @override
  String get versionGateNagDismissCta => 'Later';

  @override
  String get versionGateRetryCta => 'I\'ve updated — check again';

  @override
  String get versionGateOfflineRetryHint =>
      'Still on the old version, or AMI couldn\'t be reached. Try again in a moment.';
}
