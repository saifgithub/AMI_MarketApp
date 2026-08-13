// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Malay (`ms`).
class AppLocalizationsMs extends AppLocalizations {
  AppLocalizationsMs([String locale = 'ms']) : super(locale);

  @override
  String get appTitle => 'AMI Trade';

  @override
  String get tabFloor => 'Floor';

  @override
  String get tabPortfolio => 'Portfolio';

  @override
  String get tabJournal => 'Jurnal';

  @override
  String get tabLessons => 'Pengajian';

  @override
  String get tabSettings => 'Tetapan';

  @override
  String get settingsLanguage => 'Bahasa';

  @override
  String get settingsLanguageEnglish => 'Inggeris';

  @override
  String get settingsLanguageArabic => 'العربية';

  @override
  String get settingsLanguageMalay => 'Bahasa Melayu';

  @override
  String get actionRead => 'BACA';

  @override
  String get actionQuizOnly => 'KUIZ SAHAJA';

  @override
  String get watchlistHeading => 'SENARAI PENGAWAS';

  @override
  String get watchlistAdd => 'TAMBAH';

  @override
  String get watchlistEmpty =>
      'Tambah ticker yang ingin dipantau. Ketik baris untuk tindakan pantas: Ask the Market Analyst, Convene the Room, atau buka trade.';

  @override
  String get watchlistOpenTradeTicket => 'BUKA TIKET TRADE';

  @override
  String get watchlistAskMarketAnalyst => 'TANYA MARKET ANALYST';

  @override
  String get watchlistConveneRoom => 'KUMPULKAN BILIK';

  @override
  String get watchlistRemove => 'ALIHKAN DARI SENARAI PENGAWAS';

  @override
  String get watchlistRemoved => 'Dikeluarkan daripada senarai pengawas';

  @override
  String get watchlistUndo => 'BATAL';

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
  String get floorTabUpper => 'LANTAI';

  @override
  String get portfolioTabUpper => 'PORTFOLIO';

  @override
  String get journalTabUpper => 'JURNAL';

  @override
  String get lessonsTabUpper => 'PELAJARAN';

  @override
  String get settingsTabUpper => 'TETAPAN';

  @override
  String get gameTabUpper => 'GAME';

  @override
  String get youTabUpper => 'YOU';

  @override
  String get youUnsavedTitle => 'UNSAVED MANDATE EDITS';

  @override
  String get youUnsavedBody =>
      'Your mandate has changes you have not saved. Leave this segment and they are discarded.';

  @override
  String get youUnsavedKeep => 'keep editing';

  @override
  String get youUnsavedDiscard => 'discard changes';

  @override
  String get tradeTicketOpenMandate => 'OPEN MY MANDATE';

  @override
  String get settingsReportProblem => 'Report a problem';

  @override
  String get youSegmentInsights => 'INSIGHTS';

  @override
  String insightsWindowCapped(int count) {
    return 'your last $count decisions';
  }

  @override
  String insightsWindowAll(int count) {
    return 'all $count of your decisions';
  }

  @override
  String get insightsEmptyHeading => 'NOTHING TO AGGREGATE YET';

  @override
  String get insightsEmptyBody =>
      'Close a trade, run the Room, or take a daily challenge. This fills in from your own decisions — it has nothing to show until you have made some.';

  @override
  String get insightsTradesTitle => 'HOW YOUR TRADES ENDED';

  @override
  String get insightsTradesWon => 'target hit';

  @override
  String get insightsTradesLost => 'stop hit';

  @override
  String get insightsTradesManual => 'you closed it';

  @override
  String get insightsTradesNote =>
      'Closing by hand before your stop or target means overriding the plan you wrote. That is a habit, and habits are what you are here to change.';

  @override
  String insightsTradesUnclassified(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'trades',
      one: 'trade',
    );
    return '$count closed $_temp0 could not be classified and are not in the bars above.';
  }

  @override
  String get insightsVerdictTitle => 'WHAT YOUR PM DECIDED';

  @override
  String get insightsVerdictApprove => 'approved';

  @override
  String get insightsVerdictModify => 'modified';

  @override
  String get insightsVerdictReject => 'rejected';

  @override
  String get insightsVerdictPass => 'passed';

  @override
  String get insightsVerdictNoVerdict => 'no verdict';

  @override
  String get insightsVerdictNoVerdictNote =>
      'NO VERDICT is not a rejection. The PM declined to rule because the run had no market read — your idea was never judged.';

  @override
  String insightsVerdictUnrecorded(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'runs',
      one: 'run',
    );
    return '$count $_temp0 ended before a verdict was recorded and are not counted.';
  }

  @override
  String get insightsAnalystsTitle => 'ANALYSTS YOU SOUGHT OUT';

  @override
  String get insightsAnalystsNote =>
      '1-on-1s, briefs and unlocks — who you went to. Not who spoke in the Room: all twelve speak every run.';

  @override
  String get insightsMandateTitle => 'HOW YOUR MANDATE HAS MOVED';

  @override
  String insightsMandateEdits(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count edits',
      one: '1 edit',
    );
    return '$_temp0';
  }

  @override
  String get insightsMandateLoosened => 'loosened';

  @override
  String get insightsMandateTightened => 'tightened';

  @override
  String get insightsMandateNoMoves =>
      'No limit moved. The edits changed something else.';

  @override
  String get insightsChallengeTitle => 'DAILY CHALLENGE BY TYPE';

  @override
  String insightsChallengeRow(int correct, int attempts) {
    return '$correct/$attempts correct';
  }

  @override
  String get insightsChallengeUnweighted =>
      'Not weighted by difficulty — an easy question and a hard one count the same here.';

  @override
  String insightsChallengeOmitted(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'types have',
      one: 'type has',
    );
    String _temp1 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'are',
      one: 'is',
    );
    return '$count $_temp0 fewer than 5 attempts and $_temp1 not shown.';
  }

  @override
  String get floorConciergeHeading => 'AMI CONCIERGE';

  @override
  String get floorConciergeTagline =>
      'Pembantu peribadi anda — ketik untuk sembang';

  @override
  String get floorTeamHeading => 'PASUKAN ANDA';

  @override
  String floorUnlockedSummary(int count) {
    return '$count daripada 12 dibuka. Ketik heksagon terkunci untuk maklumat lanjut.';
  }

  @override
  String get floorConveneCta => 'KUMPULKAN';

  @override
  String get floorConveneCaption =>
      'Jalankan debat pelbagai ejen sepenuhnya pada ticker.';

  @override
  String get floorRestartOnboarding => 'mulakan semula orientasi';

  @override
  String get floorRestartOnboardingConfirmTitle => 'MULAKAN SEMULA ORIENTASI?';

  @override
  String get floorRestartOnboardingConfirmBody =>
      'This runs the whole interview again from the first question. It does not replace a mandate you already have — that stays as it is, and you can edit it any time. Your portfolio and trades are untouched.';

  @override
  String get floorRestartOnboardingConfirmCta => 'MULA SEMULA';

  @override
  String get floorFooter =>
      '⬢  AMI TRADE • SIMULASI PENDIDIKAN • BUKAN NASIHAT';

  @override
  String get floorLockedHowTo => 'CARA UNLOCK';

  @override
  String get floorLockedNoLessons =>
      'Ejen ini akan unlock secara automatik sebaik sahaja pelajaran Earn-Path tersedia. Buat masa ini, anda boleh pratonton melalui 1-on-1 jika pelan anda membenarkannya.';

  @override
  String floorLockedEarnByLessons(int count) {
    return 'Lulus $count pelajaran ini untuk memperoleh ejen ini:';
  }

  @override
  String get floorLockedGoToLessons => 'KE PELAJARAN';

  @override
  String get floorLockedTapHint => 'Tekan pelajaran untuk mula';

  @override
  String floorLockedProgress(int completed, int total) {
    return '$completed / $total pelajaran gateway diluluskan';
  }

  @override
  String get portfolioHeading => 'PORTFOLIO';

  @override
  String get portfolioNewTradeTooltip => 'Dagangan baharu';

  @override
  String get portfolioTotalValue => 'NILAI KESELURUHAN';

  @override
  String get portfolioCash => 'TUNAI';

  @override
  String portfolioDrawdown(String pct) {
    return 'Drawdown: $pct%';
  }

  @override
  String get portfolioLive => 'LIVE';

  @override
  String get portfolioMock => 'MOCK';

  @override
  String get portfolioStartSimTrading => 'Mula dagangan simulasi';

  @override
  String get portfolioStartSimTradingBody =>
      'CONVENE the Room untuk dapatkan keputusan, kemudian buka dagangan — atau letakkan dagangan terus dari sini. Safety floor PM anda berjalan pada setiap hantar.';

  @override
  String get portfolioNewTrade => 'DAGANGAN BARU';

  @override
  String get portfolioHoldings => 'PEGANGAN';

  @override
  String get portfolioTrades => 'DAGANGAN';

  @override
  String get portfolioNoTrades => 'Tiada dagangan lagi.';

  @override
  String get portfolioCloseTooltip => 'Tutup';

  @override
  String get portfolioAddDialogTitle => 'TAMBAH KE SENARAI PEMANTAUAN';

  @override
  String get portfolioAddDialogHint => 'Ticker (cth. NVDA)';

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
  String get gamesQueueInfoTitle => 'When does this fill?';

  @override
  String get gamesQueueInfoTooltip => 'When does this fill?';

  @override
  String get gamesQueueInfoDismiss => 'Got it';

  @override
  String get gamesTicketPricePerShare => 'PRICE PER SHARE';

  @override
  String get gamesTicketPriceAsOfLive =>
      'Last live price. Fills at the next open, which will differ.';

  @override
  String get gamesTicketPriceSimulated =>
      'Simulated price — the live feed is unavailable.';

  @override
  String get gamesTicketNoCashHeading => 'Nothing left to deploy';

  @override
  String gamesTicketNoCashBody(String amount, int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count orders',
      one: '1 order',
    );
    return '$amount is committed to $_temp0 waiting on the next open. Cancel one to free up cash.';
  }

  @override
  String get gamesTicketNoCashCta => 'See queued orders';

  @override
  String get gamesRunRefusedHeading => 'NOT PLACED AT THE OPEN';

  @override
  String get gamesRunRefusedNote =>
      'Queued orders fill oldest first. When they add up to more than your cash, the later ones are refused whole — never shrunk to fit.';

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
  String get tickerDetailValue => 'NILAI';

  @override
  String get tickerDetailQty => 'KUANTITI';

  @override
  String get tickerDetailAvgCost => 'KOS PURATA';

  @override
  String get tickerDetailMark => 'TANDA';

  @override
  String tickerDetailOpened(String date) {
    return 'Dibuka $date';
  }

  @override
  String get tickerDetailWatchingHeading => 'MEMANTAU';

  @override
  String get tickerDetailToday => 'hari ini';

  @override
  String tickerDetailAdded(String date) {
    return 'Ditambah $date';
  }

  @override
  String tickerDetailNoPosition(String ticker) {
    return 'Tiada posisi terbuka atau entri senarai pantau untuk $ticker.';
  }

  @override
  String get tickerDetailChartUnavailable =>
      'Carta tidak tersedia. Tekan untuk cuba lagi.';

  @override
  String get tickerDetailChartRejected => 'AMI can\'t chart this one.';

  @override
  String get tickerDetailChartNoHistory => 'No price history for this period.';

  @override
  String get tickerDetailChartExpand => 'Kembangkan carta';

  @override
  String get tickerDetailChartClose => 'Tutup carta skrin penuh';

  @override
  String get tickerDetailActionTrade => 'DAGANG';

  @override
  String get tickerDetailActionTradeMore => 'DAGANG LAGI';

  @override
  String get tickerDetailActionAsk => 'SOAL';

  @override
  String get tickerDetailActionConvene => 'CONVENE';

  @override
  String get tickerDetailActionWatch => 'PANTAU';

  @override
  String get tickerDetailActionClose => 'TUTUP';

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
    return 'PERNIAGAAN UNTUK $ticker';
  }

  @override
  String get tickerDetailNoTrades =>
      'Tiada rekod perniagaan untuk ticker ini lagi.';

  @override
  String tickerDetailClosePositionConfirmTitle(String ticker) {
    return 'TUTUP POSISI $ticker?';
  }

  @override
  String get tickerDetailClosePositionConfirmBody =>
      'Ini menutup setiap perniagaan terbuka untuk ticker ini pada mark semasa. P&L direalisasi adalah muktamad.';

  @override
  String get tickerDetailClosePositionConfirmCta => 'TUTUP';

  @override
  String get tickerDetailNewsHeading => 'BERITA';

  @override
  String tickerDetailNewsEpsEstimate(String eps) {
    return 'anggaran EPS $eps';
  }

  @override
  String tickerDetailDividendExDate(String date) {
    return 'ex-dividen $date';
  }

  @override
  String tickerDetailDividendRate(String rate) {
    return '$rate/saham';
  }

  @override
  String get tickerDetailLotsHeading => 'LOT KOS ASAS';

  @override
  String get tickerDetailLotStatusOpen => 'TERBUKA';

  @override
  String get tickerDetailLotStatusPartiallyClosed => 'SEBAHAGIAN';

  @override
  String get tickerDetailLotStatusClosed => 'DITUTUP';

  @override
  String tickerDetailLotEntry(String date, String price) {
    return 'Dibuka $date @ \$$price';
  }

  @override
  String tickerDetailLotQuantity(String open, String closed) {
    return '$open terbuka / $closed ditutup';
  }

  @override
  String tickerDetailLotRealised(String pnl) {
    return 'Direalisasi $pnl';
  }

  @override
  String tickerDetailLotUnrealised(String pnl) {
    return 'Belum direalisasi $pnl';
  }

  @override
  String get tickerDetailLotUnrealisedUnknown => 'Belum direalisasi —';

  @override
  String get portfolioSectorAllocationHeading => 'AGIHAN SEKTOR';

  @override
  String get portfolioSectorOtherLabel => 'Lain-lain (tidak dikelaskan)';

  @override
  String portfolioSectorBreach(String sector, String pct, String limit) {
    return '$sector pada $pct% melebihi had mandat $limit% anda';
  }

  @override
  String get roomVerdictSeeChart => 'LIHAT CARTA';

  @override
  String get actionCancel => 'BATAL';

  @override
  String get actionAdd => 'TAMBAH';

  @override
  String get journalHeading => 'JURNAL KEPUTUSAN';

  @override
  String get journalFilterAll => 'SEMUA';

  @override
  String get journalFilterRoom => 'BILIK';

  @override
  String get journalFilterTrade => 'DAGANG';

  @override
  String get journalFilterOneOnOne => '1-LAWAN-1';

  @override
  String get journalFilterBrief => 'BRIEF';

  @override
  String get journalFilterLessons => 'PELAJARAN';

  @override
  String get journalFilterUnlocks => 'NYAHKUNCI';

  @override
  String get journalFilterChallenges => 'CHALLENGES';

  @override
  String journalRetentionWarning(int days) {
    return 'Floor Pass: last $days days only. Upgrade to see everything — nothing is deleted.';
  }

  @override
  String get journalEmptyTitle => 'Tiada entri lagi.';

  @override
  String get journalEmptyBody =>
      'Bercakap dengan ejen, bimbing seorang, atau lengkapkan pelajaran — setiap tindakan direkodkan di sini secara automatik.';

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
  String get journalDetailHeading => 'BUTIRAN ENTRI';

  @override
  String get journalDetailLoading => 'Memuatkan…';

  @override
  String get journalDetailBlockYou => 'ANDA';

  @override
  String get journalDetailBlockAgent => 'EJEN';

  @override
  String get journalDetailBlockOverlay => 'OVERLAY';

  @override
  String journalDetailSavedAsVersion(int version) {
    return 'Disimpan sebagai v$version';
  }

  @override
  String journalDetailVerdictLine(String action) {
    return 'KEPUTUSAN: $action';
  }

  @override
  String get journalNoteHeading => 'NOTA ANDA';

  @override
  String get journalNoteHint =>
      'Sebab ia penting. Apa yang dipelajari. Apa yang akan dilakukan secara berbeza.';

  @override
  String get journalNoteOutcome => 'HASIL';

  @override
  String get journalNoteOutcomeWin => 'MENANG';

  @override
  String get journalNoteOutcomeLoss => 'RUGI';

  @override
  String get journalNoteOutcomePending => 'MENUNGGU';

  @override
  String get journalNoteSave => 'SIMPAN NOTA';

  @override
  String get journalNoteSaved => 'Nota disimpan';

  @override
  String get journalSearchHint => 'Cari entri…';

  @override
  String get journalSearchEmpty => 'Tiada entri sepadan dengan carian anda.';

  @override
  String get journalEntryDeleted => 'Entri dipadam';

  @override
  String get journalUndo => 'BATAL';

  @override
  String get journalTrashHeading => 'TONG SAMPAH';

  @override
  String get journalTrashEmpty =>
      'Tiada apa-apa di sini. Entri yang dipadam akan muncul dalam senarai ini.';

  @override
  String get journalTrashWindowNote =>
      'Entri lama disembunyikan secara automatik selepas 30 hari.';

  @override
  String get journalRestoreEntry => 'KEMBALIKAN';

  @override
  String get journalEntryRestored => 'Entri dikembalikan';

  @override
  String journalDeletedAgo(String ago) {
    return 'Dipadam $ago';
  }

  @override
  String get lessonsHeading => 'PELAJARAN';

  @override
  String get lessonsYourProgress => 'KEMAJUAN ANDA';

  @override
  String lessonsCount(int done, int total) {
    return '$done / $total pelajaran';
  }

  @override
  String get lessonsAgents => 'EJEN';

  @override
  String lessonsAgentsCount(int unlocked) {
    return '$unlocked / 12';
  }

  @override
  String get lessonsNextUp => 'SETERUSNYA';

  @override
  String get lessonsTierInProgress => 'SEDANG BERJALAN';

  @override
  String get lessonsTierNotStarted => 'BELUM DIMULAKAN';

  @override
  String get lessonsTierCompleted => 'SELESAI';

  @override
  String get lessonsContinue => 'TERUSKAN';

  @override
  String get lessonsUnlocksAgent => 'BUKA';

  @override
  String lessonsDurationMin(int min) {
    return '$min min';
  }

  @override
  String get lessonReaderLoading => 'Memuatkan…';

  @override
  String get lessonReaderUnavailableTitle => 'PELAJARAN TIDAK TERSEDIA';

  @override
  String get lessonReaderPrerequisites => 'PRA-SYARAT';

  @override
  String get lessonReaderQuizOnlyBadge => 'KUIZ SAHAJA';

  @override
  String get lessonReaderQuizOnlyBannerOne =>
      'Terus ke 1 kuiz. Luluskan dan pelajaran tetap dikira untuk pembukaan ejen. Jawapan salah akan memaparkan penjelasan — itulah ruang pembelajaran anda.';

  @override
  String lessonReaderQuizOnlyBannerMany(int count) {
    return 'Terus ke $count kuiz. Luluskan semua dan pelajaran tetap dikira untuk pembukaan ejen. Jawapan salah akan memaparkan penjelasan.';
  }

  @override
  String get lessonReaderQuiz => 'KUIZ';

  @override
  String lessonReaderChatWith(String agent) {
    return 'Sembang dengan $agent';
  }

  @override
  String get lessonReaderSubmitQuiz => 'HANTAR KUIZ';

  @override
  String get lessonReaderChecking => 'MENYEMAK…';

  @override
  String get lessonReaderPassed => 'LULUS';

  @override
  String get lessonReaderNotQuite => 'TIDAK TEPAT';

  @override
  String lessonReaderCorrectOf(int correct, int total) {
    return '$correct / $total betul';
  }

  @override
  String get lessonReaderAgentUnlocked => 'AGEN DIBUKA';

  @override
  String get lessonReaderTryAgain => 'CUBA LAGI';

  @override
  String get lessonReaderDone => 'SELESAI';

  @override
  String get lessonReaderBackToLessons => 'KEMBALI KE PELAJARAN';

  @override
  String get lessonModeBook => 'BOOK';

  @override
  String get lessonModeInteractive => 'INTERACTIVE';

  @override
  String get lessonPlayDragHint => 'DRAG TO EXPLORE';

  @override
  String get lessonRevealTap => 'TAP TO REVEAL';

  @override
  String get lessonDeckNext => 'Next card';

  @override
  String get lessonDeckBack => 'Previous card';

  @override
  String get lessonDeckCheckHeading => 'CHECK YOUR ANSWERS';

  @override
  String lessonPlayBreachStreak(int n, int total, int pct) {
    return 'Loss $n of $total puts you past the $pct% drawdown ceiling on your own mandate.';
  }

  @override
  String lessonPlayBreachSingleName(String pct, String cap) {
    return 'That is $pct of the account in one name — past your $cap single-name cap. The stop got tighter; the risk did not.';
  }

  @override
  String lessonPlayBreachStopTooTight(String wick, String close) {
    return 'The stop now sits above the $wick noise wick, so it fires on a day price closed back at $close — stopped out without the thesis ever failing.';
  }

  @override
  String lessonPlayBreachRiskReward(String risk, String reward, String pct) {
    return 'Risking $risk to make $reward. You now have to be right $pct of the time just to break even.';
  }

  @override
  String lessonPlayBreachOpenRisk(int count, String real, String limit) {
    return '$count names at 1% each is $real of real open risk — past the $limit open-risk limit on your own mandate.';
  }

  @override
  String lessonPlayBreachDrawdownCeiling(int cap, int depth, int over) {
    return 'Your mandate halts new entries at $cap% down. This hole is $depth% — the PM stopped you $over points ago.';
  }

  @override
  String get settingsHeading => 'TETAPAN';

  @override
  String settingsMandateVersion(int version) {
    return 'mandat v$version';
  }

  @override
  String get settingsSaving => 'MENYIMPAN…';

  @override
  String get settingsSave => 'SIMPAN';

  @override
  String get settingsMandateUpdated => 'Mandat dikemas kini.';

  @override
  String get settingsRetroAuditFailed =>
      'Couldn\'t check your holdings against the new limit — open Portfolio to verify.';

  @override
  String get settingsSectionMandate => 'MANDAT SAYA';

  @override
  String get settingsSectionCompliance => 'Kepatuhan';

  @override
  String get settingsSectionProfile => 'PROFIL';

  @override
  String get settingsSectionLanguageUpper => 'BAHASA';

  @override
  String get settingsSectionAccount => 'AKAUN';

  @override
  String get settingsSectionDeveloper => 'PEMBANGUN';

  @override
  String get settingsRiskScore => 'Skor risiko';

  @override
  String settingsRiskScoreValue(int value) {
    return '$value / 5';
  }

  @override
  String get settingsRiskLabel1 =>
      'Pemeliharaan modal. Saiz kecil, stop ketat.';

  @override
  String get settingsRiskLabel2 => 'Berhati-hati. Saiz posisi bawah purata.';

  @override
  String get settingsRiskLabel3 => 'Seimbang. Posisi standard 3-5%.';

  @override
  String get settingsRiskLabel4 =>
      'Agresif. Saiz lebih besar untuk setup keyakinan tinggi.';

  @override
  String get settingsRiskLabel5 =>
      'Toleransi risiko tertinggi. Pertaruhan tertumpu dibenarkan.';

  @override
  String get settingsMaxDrawdown => 'Drawdown maksimum';

  @override
  String get settingsMaxDrawdownExplain =>
      'PM anda menolak dagangan yang akan menolak PORTFOLIO melebihi had ini.';

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
  String get settingsComplianceTAG => 'Tiada tembakau / alkohol / perjudian';

  @override
  String get settingsComplianceFossil => 'Tiada bahan api fosil';

  @override
  String get settingsComplianceLongOnly => 'Long-only';

  @override
  String get settingsComplianceLiquidOnly => 'Liquid-only';

  @override
  String get settingsProfilePlan => 'Pelan';

  @override
  String get settingsProfileLocale => 'Lokal';

  @override
  String get settingsProfileTimezone => 'Zon Masa';

  @override
  String get settingsProfilePath => 'Laluan';

  @override
  String get settingsProfileHorizon => 'Horizon';

  @override
  String get settingsProfilePrimaryGoal => 'Matlamat utama';

  @override
  String get settingsProfileCredits => 'Kredit';

  @override
  String get settingsAccountStatus => 'Status';

  @override
  String get settingsAccountSignedIn => 'Log masuk';

  @override
  String get settingsAccountGuest => 'Tetamu (tanpa nama)';

  @override
  String get settingsAccountHandle => 'Handle';

  @override
  String get settingsAccountGuestNote =>
      'Mandat, jurnal, dan portfolio kekal pada peranti ini sehingga anda log masuk.';

  @override
  String get settingsManageAccount => 'URUS AKAUN';

  @override
  String get settingsSignIn => 'LOG MASUK';

  @override
  String get settingsSignedOut => 'Anda telah didaftarkan keluar.';

  @override
  String get settingsLanguagePlaceholderNote =>
      'AR + MS dihantar sebagai placeholder hari ini — kunci yang hilang akan kembali ke bahasa Inggeris. Penterjemah memasukkan ARB yang betul dan lokaliti akan diaktifkan.';

  @override
  String get settingsDeveloperActive => 'Backend aktif';

  @override
  String get settingsDeveloperNoUrl => '(tiada URL terbina dalam binaan ini)';

  @override
  String get settingsDeveloperNotInBuild => '· tiada dalam binaan ini';

  @override
  String get settingsDeveloperFootnote =>
      'Bahagian ini dikeluarkan daripada binaan MVP / App Store. Hanya PROD yang boleh dicapai selepas itu.';

  @override
  String get onboardingHeader => 'AMI TRADE';

  @override
  String get onboardingHeaderSetup => 'PENYEDIAAN';

  @override
  String get onboardingHintSending => 'Menghantar...';

  @override
  String get onboardingHintAnswer => 'Taip jawapan anda…';

  @override
  String get onboardingReadbackContinue => 'BETUL — TERUSKAN';

  @override
  String get onboardingClaimPrompt =>
      'Mari simpan ini supaya pasukan anda mengenali anda.';

  @override
  String get onboardingSaveTeam => 'SIMPAN PASUKAN SAYA';

  @override
  String get onboardingSkipForNow => 'LANGKAUI SEKARANG';

  @override
  String get onboardingErrorTitle => 'GAGAL MENGHUBUNGI BACKEND';

  @override
  String get onboardingErrorUnknown => 'Ralat tidak diketahui';

  @override
  String get onboardingTryAgain => 'CUBA LAGI';

  @override
  String get signInHeading => 'LOG MASUK';

  @override
  String get signInIntro =>
      'Log masuk untuk mengekalkan mandat, jurnal, dan PORTFOLIO anda merentasi peranti. Sebelum itu, semua yang anda bina kekal pada peranti ini.';

  @override
  String get signInWithApple => 'Log masuk dengan Apple';

  @override
  String get signInWithGoogle => 'Log masuk dengan Google';

  @override
  String get signInWithEmail => 'ATAU TERUSKAN DENGAN EMEL';

  @override
  String get signInUseEmailInstead => 'Gunakan e-mel sebaliknya';

  @override
  String get signInEmailHint => 'anda@contoh.com';

  @override
  String get signInSendCode => 'HANTAR KOD';

  @override
  String get signInResendCode => 'HANTAR SEMULA KOD';

  @override
  String get signInCodeHint => 'Kod 6-digit';

  @override
  String get signInVerify => 'SAH & TUNTUT';

  @override
  String signInDevCode(String code) {
    return 'Mod DEV — kod: $code';
  }

  @override
  String get signInCodeSent => 'Kod dihantar. Semak e-mel anda.';

  @override
  String get signInCodeFailed => 'Kod tidak sah. Cuba lagi.';

  @override
  String get signInAppleFailed => 'Log masuk Apple gagal.';

  @override
  String get signInGoogleFailed => 'Log masuk Google gagal.';

  @override
  String signInSignedInAs(String handle) {
    return 'Log masuk sebagai $handle';
  }

  @override
  String get signInLegalFootnote =>
      'AMI Trade adalah simulasi sahaja. Tiada apa-apa di sini merupakan nasihat pelaburan dan tiada dagangan sebenar dilaksanakan.';

  @override
  String get mergeSheetTitle => 'SELAMAT DATANG SEMULA';

  @override
  String get mergeSheetBody =>
      'Kami menemui data dari sesi sebelumnya pada peranti ini. Adakah anda mahu membawanya ke dalam akaun anda?';

  @override
  String get mergeSheetEmptyBody =>
      'Anda telah log masuk semula. Tiada data dibawa dari sesi sebelumnya pada peranti ini.';

  @override
  String mergeSheetJournalEntries(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count entri jurnal',
      one: '1 entri jurnal',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetSimTrades(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count perdagangan simulasi',
      one: '1 perdagangan simulasi',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetWatchlist(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count penanda watchlist',
      one: '1 penanda watchlist',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetLessons(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count pelajaran dimulakan',
      one: '1 pelajaran dimulakan',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetOneOnOnes(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count mesej 1-on-1',
      one: '1 mesej 1-on-1',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetRoomRuns(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count larian Room',
      one: '1 larian Room',
    );
    return '$_temp0';
  }

  @override
  String get mergeSheetMandate =>
      'Mandate (milik anda kekal — kami akan buang yang lebih lama)';

  @override
  String get mergeSheetMandateMove =>
      'Mandate dari sesi sebelumnya (tiada konflik)';

  @override
  String get mergeSheetConfirm => 'GABUNG SEMUA';

  @override
  String get mergeSheetKeepSeparate => 'KEKAL BERBEZA';

  @override
  String get mergeSheetClose => 'PAHAM';

  @override
  String get mergeSheetSuccess => 'Dihubungkan ke akaun anda.';

  @override
  String get mergeSheetFailed =>
      'Penggabungan gagal. Cuba lagi dari Settings nanti.';

  @override
  String get oneOnOneAskAnything =>
      'Tanya saya apa sahaja dalam domain saya.\nTaip di bawah untuk bermula.';

  @override
  String get oneOnOneStreaming => 'Menstrim…';

  @override
  String get oneOnOneHint => 'Tanya apa sahaja…';

  @override
  String get oneOnOneBriefTooltip => 'Bimbing ejen ini';

  @override
  String briefHeading(String agent) {
    return 'BIMBING $agent';
  }

  @override
  String get briefNoOverlayYet => 'Tiada overlay lagi — tetapan asal kilang';

  @override
  String briefOverlayActive(int version) {
    return 'Overlay v$version aktif';
  }

  @override
  String get briefNoEditsLeft =>
      '⚠️ Tiada suntingan tinggal — naik taraf untuk terus membimbing';

  @override
  String briefOneEditLeft(int count) {
    return '⚠️ $count suntingan tinggal untuk tahap anda';
  }

  @override
  String get briefVersionHistoryTooltip => 'Sejarah versi';

  @override
  String briefCurrentOverlayLabel(int version) {
    return 'OVERLAY SEMASA — v$version';
  }

  @override
  String get briefProtectedSafetyFloor => 'DILINDUNGI — safety floor';

  @override
  String get briefProtectedMandate => 'DILINDUNGI — peraturan mandat';

  @override
  String get briefEditLimitReached => 'HAD EDIT DICAPAI';

  @override
  String get briefRefused => 'BRIEF MENOLAK';

  @override
  String briefProposalSavedSnack(int version, String summary) {
    return 'Disimpan sebagai v$version — $summary';
  }

  @override
  String briefAgentRefused(String agent) {
    return '$agent MENOLAK';
  }

  @override
  String briefAgentProposal(String agent) {
    return '$agent — CADANGAN';
  }

  @override
  String get briefPlainEnglish => 'Bahasa Mudah:';

  @override
  String get briefOverlayAddition => 'Penambahan tindanan:';

  @override
  String get briefAccept => 'TERIMA';

  @override
  String get briefRefine => 'PERHALUSI';

  @override
  String get briefReject => 'TOLAK';

  @override
  String get briefDismiss => 'KETEPIKAN';

  @override
  String get briefInputHint => 'Beritahu saya apa yang perlu diubah…';

  @override
  String get briefDrafting => 'MENYEDIAKAN…';

  @override
  String get briefProposeChange => 'CADANG PERUBAHAN';

  @override
  String briefHistoryHeading(String agent) {
    return 'SEJARAH $agent';
  }

  @override
  String get briefHistorySubtitle => 'Semua versi bimbingan yang disimpan';

  @override
  String briefHistoryEditsUnlimited(int count) {
    return '$count suntingan dibuat • tanpa had untuk tahap anda';
  }

  @override
  String briefHistoryEditsRemaining(int count, int remaining) {
    return '$count suntingan dibuat • $remaining baki';
  }

  @override
  String get briefHistoryEmpty =>
      'Tiada sejarah bimbingan lagi.\nKembali dan cadangkan perubahan pertama anda.';

  @override
  String get briefHistoryActiveBadge => 'AKTIF';

  @override
  String briefHistoryRollbackTitle(int version) {
    return 'Kembalikan ke v$version?';
  }

  @override
  String briefHistoryRollbackBody(int version) {
    return 'Agen anda akan mula menggunakan v$version serta-merta. Versi yang lebih baharu kekal dalam sejarah.';
  }

  @override
  String get briefHistoryRollback => 'KEMBALIKAN';

  @override
  String get briefHistoryRollbackToThis => 'KEMBALIKAN KE SINI';

  @override
  String get conveneHeading => 'CONVENE BILIK';

  @override
  String get convenePickTicker =>
      'Pilih ticker. Seluruh pasukan anda akan menjalankan perbahasan.';

  @override
  String get conveneTickerHint => 'cth. NVDA';

  @override
  String get conveneOrPickOne => 'ATAU PILIH SATU';

  @override
  String get conveneCta => 'CONVENE';

  @override
  String get roomHeadingPrefix => 'CONVENE ›';

  @override
  String get roomStandingBy => 'bersedia';

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
  String get roomDeliberating => 'Pasukan sedang berbincang…';

  @override
  String get roomEndedNoVerdict => 'Bilik tamat tanpa keputusan.';

  @override
  String get roomSavedToJournal => 'Disimpan ke Jurnal';

  @override
  String get roomClose => 'TUTUP';

  @override
  String get roomSafetyFloorPill => 'LANTAI KESELAMATAN';

  @override
  String roomVerdictHeading(String action) {
    return 'KEPUTUSAN — $action';
  }

  @override
  String get roomMetricTicker => 'TICKER';

  @override
  String get roomMetricSize => 'SAIZ';

  @override
  String get roomMetricEntry => 'KEMASUKAN';

  @override
  String get roomMetricStop => 'HENTIAN';

  @override
  String get roomMetricTarget => 'SASARAN';

  @override
  String get roomMetricHorizon => 'HORIZON';

  @override
  String roomHorizonDays(int days) {
    return '$days hari';
  }

  @override
  String get roomViolations => 'PELANGGARAN';

  @override
  String get roomOpenTradeTicket => 'BUKA TIKET DAGANGAN';

  @override
  String get roomTradeTicketCaption =>
      'Hantar dengan saiz / stop / target keputusan. Larian semula safety floor PM.';

  @override
  String get roomWinzipTitle => 'Room anda sedang memanaskan';

  @override
  String roomWinzipBody(String countdown) {
    return 'Anda telah guna Room ini — AMI sudah tambah kredit untuk anda. Room seterusnya akan dibuka dalam $countdown.';
  }

  @override
  String get roomWinzipReady => 'Room anda sedia untuk convene.';

  @override
  String get roomWinzipConvene => 'CONVENE SEKARANG';

  @override
  String get roomWinzipReviewTraining => 'Semak sesi Training sambil menunggu';

  @override
  String get roomWinzipVoiceLine => 'Room anda sedia sekarang';

  @override
  String get roomPaywallTitle => 'Kredit Room habis';

  @override
  String roomPaywallBody(String date) {
    return 'Maaf — kredit Room anda habis buat masa ini. Ia akan segar pada $date.';
  }

  @override
  String get roomServerErrorTitle => 'AMI sebentar tidak dalam talian';

  @override
  String get roomServerErrorBody =>
      'Sambungan terputus seketika — tiada masalah pada pihak anda. Tunggu sebentar dan cuba lagi.';

  @override
  String get roomRetry => 'CUBA LAGI';

  @override
  String get roomLiveDataNoticeTitle => 'Data langsung';

  @override
  String roomLiveDataFeedLive(String feed) {
    return '$feed: data langsung digunakan.';
  }

  @override
  String roomLiveDataFeedWithheld(String feed) {
    return '$feed: data langsung tersedia — memerlukan kredit.';
  }

  @override
  String roomLiveDataFeedUnavailable(String feed) {
    return '$feed: data langsung tidak tersedia buat masa ini.';
  }

  @override
  String roomLiveDataSurchargeCharged(int surcharge) {
    return 'Berita + media sosial langsung memerlukan $surcharge kredit tambahan untuk larian ini.';
  }

  @override
  String get roomLiveDataUpgradeCta => 'NAIK TARAF UNTUK DATA LANGSUNG';

  @override
  String roomLiveDataFeedTenure(String feed) {
    return '$feed: data langsung tersedia — memerlukan naik taraf pelan.';
  }

  @override
  String get roomLiveDataTenureUpgradeCta => 'NAIK TARAF PELAN ANDA';

  @override
  String roomAgentWithheldChairLabel(String agent) {
    return '$agent — di luar pasukan anda pada pelan ini';
  }

  @override
  String roomAgentWithheldRosterNote(String agent, int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: '$days hari',
    );
    return 'Pertukaran pasukan seterusnya: $agent dalam $_temp0.';
  }

  @override
  String get roomVerdictActionNoVerdict => 'TIADA KEPUTUSAN';

  @override
  String get roomVerdictOpinionsHeading => 'Tiada dalam Bilik';

  @override
  String get roomVerdictOpinionsNote =>
      'Keputusan ini dicapai tanpa input mereka.';

  @override
  String roomVerdictIncludeAnalystCta(String agent) {
    return 'Sertakan $agent →';
  }

  @override
  String get upgradeSheetTitle => 'Naik taraf meja dagangan anda';

  @override
  String get upgradeSheetSubtitle =>
      'Buka lebih banyak Bilik dan analisis premium. Harga dipaparkan untuk rantau anda.';

  @override
  String get upgradePlanTrader => 'Trader';

  @override
  String get upgradePlanFloorManager => 'Pengurus Lantai';

  @override
  String get upgradeIntervalMonthly => 'Bulanan';

  @override
  String get upgradeIntervalAnnual => 'Tahunan';

  @override
  String get upgradeCreditPacksTitle => 'Pakej kredit';

  @override
  String upgradeCreditPackCredits(int credits) {
    return '+$credits kredit';
  }

  @override
  String get upgradeBuy => 'BELI';

  @override
  String get upgradeRestore => 'Pulihkan pembelian';

  @override
  String get upgradeUnavailableTitle => 'Naik taraf belum tersedia';

  @override
  String upgradeUnavailableBody(String date) {
    return 'Pembelian dalam aplikasi akan diaktifkan sebentar lagi. Kredit Bilik anda masih disegarkan pada $date.';
  }

  @override
  String get upgradePurchasePending =>
      'Pembelian anda sedang diproses — kami akan membuka kunci sebaik ia selesai.';

  @override
  String get upgradePurchaseFailed =>
      'Transaksi tidak berjaya. Tiada caj dibuat — sila cuba lagi.';

  @override
  String get upgradePurchaseSuccess =>
      'Anda telah dinaik taraf. Selamat datang ke meja dagangan.';

  @override
  String get upgradeRestoreNone => 'Tiada pembelian ditemui untuk dipulihkan.';

  @override
  String get settingsSectionMembership => 'KEAHLIAN';

  @override
  String get settingsMembershipUpgrade => 'Naik taraf atau urus pelan';

  @override
  String get tradeTicketHeading => 'DAGANGAN BARU';

  @override
  String get tradeTicketSafetyFloorBlocked => 'SAFETY FLOOR — DAGANGAN DISEKAT';

  @override
  String get tradeTicketChangeMandate => 'Change what is enforced.';

  @override
  String get tradeTicketLabelTicker => 'TICKER';

  @override
  String get tradeTicketLabelQuantity => 'KUANTITI';

  @override
  String get tradeTicketLabelStop => 'STOP';

  @override
  String get tradeTicketLabelTarget => 'SASARAN';

  @override
  String get tradeTicketLabelHorizon => 'HORIZON (HARI)';

  @override
  String get tradeTicketHintTicker => 'NVDA';

  @override
  String get tradeTicketHintQty => '10';

  @override
  String get tradeTicketHintOptional => 'pilihan';

  @override
  String get tradeTicketSubmitting => 'MENGHANTAR…';

  @override
  String get tradeTicketSubmit => 'HANTAR DAGANGAN';

  @override
  String get tradeTicketFooterNote =>
      'Had keselamatan PM berjalan semasa hantar — bendera pematuhan + drawdown + had nama tunggal.';

  @override
  String get tradeTicketSideBuy => 'BELI';

  @override
  String get tradeTicketSideSell => 'JUAL';

  @override
  String tradeTicketFilled(
      String side, String qty, String ticker, String price) {
    return 'Dipenuhi: $side $qty $ticker @ \$$price';
  }

  @override
  String tradeTicketResting(String side, String ticker, String price) {
    return 'Resting: $side $ticker at \$$price';
  }

  @override
  String tradeTicketRefuseCrossZero(String held, String ticker, String qty) {
    return 'You hold $held $ticker. Selling $qty would close that position and open a short in one action — sell $held to close, or place the short separately.';
  }

  @override
  String get tradeTicketRefuseShortStop =>
      'On a short, the stop belongs above your entry — a rising price is what goes against you.';

  @override
  String get tradeTicketRefuseShortTarget =>
      'On a short, the target belongs below your entry — you profit as the price falls.';

  @override
  String get tradeTicketLabelOrderType => 'ORDER TYPE';

  @override
  String get tradeTicketOrderMarket => 'MARKET';

  @override
  String get tradeTicketOrderLimit => 'LIMIT';

  @override
  String get tradeTicketOrderStop => 'STOP';

  @override
  String get tradeTicketOrderStopLimit => 'STOP LIMIT';

  @override
  String get tradeTicketLabelTrigger => 'TRIGGER PRICE';

  @override
  String get tradeTicketLabelLimit => 'LIMIT PRICE';

  @override
  String get tradeTicketHintPrice => 'Price';

  @override
  String get tradeTicketLabelTif => 'GOOD FOR';

  @override
  String get tradeTicketTifDay => 'TODAY';

  @override
  String get tradeTicketTif30 => '30 DAYS';

  @override
  String get tradeTicketTif90 => '90 DAYS';

  @override
  String get tradeTicketHintFillsNow =>
      'Fills now — this price is already through the market.';

  @override
  String tradeTicketHintRestsBelow(String ticker, String price) {
    return 'Waits until $ticker falls to \$$price.';
  }

  @override
  String tradeTicketHintRestsAbove(String ticker, String price) {
    return 'Waits until $ticker reaches \$$price.';
  }

  @override
  String tradeTicketHintRestsStopLimit(
      String ticker, String trigger, String limit) {
    return 'Waits until $ticker reaches \$$trigger, then becomes a limit order at \$$limit.';
  }

  @override
  String get restingOrdersHeading => 'WAITING ORDERS';

  @override
  String get restingOrdersRecentHeading => 'RECENTLY CLOSED ORDERS';

  @override
  String get restingOrderWaitingFirstCheck =>
      'Waiting for the first price check';

  @override
  String restingOrderAway(String pct) {
    return '$pct% away';
  }

  @override
  String get restingOrderCancelTitle => 'Cancel this order?';

  @override
  String restingOrderCancelBody(
      String side, String qty, String ticker, String price) {
    return '$side $qty $ticker at \$$price will stop waiting and will not fill.';
  }

  @override
  String get restingOrderCancelConfirm => 'CANCEL ORDER';

  @override
  String get restingOrderKeep => 'KEEP WAITING';

  @override
  String get restingOrderCancelled => 'Order cancelled.';

  @override
  String restingOrderCancelRaced(String state) {
    return 'Too late — that order already $state.';
  }

  @override
  String get restingOrderStateWorking => 'waiting';

  @override
  String get restingOrderStateTriggered => 'triggered';

  @override
  String get restingOrderStateFilling => 'filling';

  @override
  String get restingOrderStateFilled => 'filled';

  @override
  String get restingOrderStateCancelled => 'cancelled';

  @override
  String get restingOrderStateExpired => 'expired';

  @override
  String get restingOrderStateRejected => 'refused';

  @override
  String get restingOrderStateUnknown => 'unrecognised';

  @override
  String get chatBubbleConcierge => 'CONCIERGE';

  @override
  String get tourIntroTitle => 'Selamat datang ke lantai perdagangan anda.';

  @override
  String get tourIntroSubtitle =>
      'Lawatan ringkas ini menunjukkan cara AMI Trade berfungsi.';

  @override
  String get tourTakeTheTour => 'Mulakan lawatan';

  @override
  String get tourSkipForNow => 'Langkau buat masa ini';

  @override
  String get tourNext => 'Seterusnya →';

  @override
  String get tourDone => 'Faham';

  @override
  String get tourSkip => 'Langkau lawatan';

  @override
  String get tourConveneTryNow => 'Cuba sekarang →';

  @override
  String get tourFloor1Title => 'SWIPE THE HEADER';

  @override
  String get tourFloor1Body =>
      'Your portfolio sits here, and your team\'s latest verdicts one card to the right. Swipe across — it never moves on its own.';

  @override
  String get tourFloor2Title => 'ONE BOX, TWO JOBS';

  @override
  String get tourFloor2Body =>
      'Type a ticker and the button convenes your team on it. Type anything else and AMI takes the question. Tap CONVENE with the box empty and you get a ticker picker.';

  @override
  String get tourFloor3Title => 'TWELVE ANALYSTS, ONE TAP DOWN';

  @override
  String get tourFloor3Body =>
      'Your firm is still twelve people. This row says how many seats you have unlocked; tap it to meet them, brief them, or see what a locked one is waiting on.';

  @override
  String get tourCompletionFloor => 'Pergi CONVENE Room pertama anda.';

  @override
  String get tourPortfolio1Title => 'PORTFOLIO SIMULASI';

  @override
  String get tourPortfolio1Body =>
      'Gunakan butang + untuk OPEN TRADE TICKET. Semua dagangan adalah simulasi — tiada wang sebenar.';

  @override
  String get tourPortfolio2Title => 'NILAI KESELURUHAN & P&L';

  @override
  String get tourPortfolio2Body =>
      'Jejak nilai portfolio dan P&L semasa di sini. Sasarkan untuk mengatasi pasaran.';

  @override
  String get tourPortfolio3Title => 'SENARAI PEMERHATIAN';

  @override
  String get tourPortfolio3Body =>
      'Add tickers you\'re watching. Tap any row for quick actions.';

  @override
  String get tourCompletionPortfolio =>
      'Cuba berdagang — semua simulasi, tanpa risiko.';

  @override
  String get tourJournal1Title => 'TAPIS MENGIKUT JENIS';

  @override
  String get tourJournal1Body =>
      'Semua direkodkan — sesi Room, dagangan, taklimat, pengajaran. Tapis mengikut jenis.';

  @override
  String get tourJournal2Title => 'CARI';

  @override
  String get tourJournal2Body =>
      'Cari mana-mana entri mengikut ticker, nama ejen, atau kata kunci merentasi keseluruhan sejarah anda.';

  @override
  String get tourJournal3Title => 'SEJARAH ANDA';

  @override
  String get tourJournal3Body =>
      'Setiap entri adalah kekal. Keputusan anda ada di sini — semak semula untuk penambahbaikan.';

  @override
  String get tourCompletionJournal =>
      'Sejarah anda bermula dengan sesi Room pertama anda.';

  @override
  String get tourLessons1Title => 'PENGAJARAN';

  @override
  String get tourLessons1Body =>
      'Pengajaran adalah jalan anda untuk membuka kunci semua 12 penganalisis. Lengkapkan trek untuk besarkan pasukan anda.';

  @override
  String get tourLessons2Title => 'KEMAJUAN ANDA';

  @override
  String get tourLessons2Body =>
      'Kesan pelajaran yang selesai dan ejen yang dibuka. Setiap pelajaran menambah kekuatan kepada pasukan anda.';

  @override
  String get tourLessons3Title => 'JEJAK PEMBELAJARAN';

  @override
  String get tourLessons3Body =>
      'Setiap heks adalah jejak pembelajaran. Ketik mana-mana untuk teroka pelajaran dan buka penganalisis anda.';

  @override
  String get tourCompletionLessons =>
      'Mulakan dengan Foundations untuk membuka penganalisis pertama anda.';

  @override
  String get navChangeTitle => 'The bar moved.';

  @override
  String get navChangeBody =>
      'Two things you know are in a new place, and one thing is new.';

  @override
  String get navChangeYou =>
      'Your Journal and Settings moved together into YOU — including your mandate.';

  @override
  String get navChangeInsights =>
      'INSIGHTS, in the same tab, shows what your decisions look like in aggregate.';

  @override
  String get navChangeGame => 'GAME takes the slot in the middle.';

  @override
  String get navChangeGotIt => 'Got it';

  @override
  String get tourYou1Title => 'THREE THINGS, ONE TAB';

  @override
  String get tourYou1Body =>
      'Settings, your Decision Journal and your Insights. Switch between them here — nothing is more than one tap away.';

  @override
  String get tourYou2Title => 'YOUR MANDATE LIVES HERE';

  @override
  String get tourYou2Body =>
      'Your standing order to the team — risk, limits, what is off-limits. It is the first thing in SETTINGS, and the agents read it on every run.';

  @override
  String get tourYou3Title => 'WHAT YOUR DECISIONS LOOK LIKE';

  @override
  String get tourYou3Body =>
      'How your trades ended, what your PM decided, how your mandate has moved. Your own record, not a score.';

  @override
  String get tourCompletionYou =>
      'Your mandate is the one thing worth revisiting.';

  @override
  String get tourSettingsSectionTitle => 'PANDUAN';

  @override
  String get tourSettingsRestart => 'Mulakan semula jelajah aplikasi';

  @override
  String get tourSettingsResetDone =>
      'Jelajah akan bermula semula apabila anda melawat setiap bahagian nanti.';

  @override
  String get agentUnlockedHeadline => 'AGEN DIBUKA';

  @override
  String agentUnlockedMeet(String name) {
    return 'KENALI $name';
  }

  @override
  String get agentUnlockedLater => 'Kemudian';

  @override
  String get challengeRelatedLesson => 'PELAJARAN BERKAITAN';

  @override
  String get challengeRelatedAgent => 'AGEN BERKAITAN';

  @override
  String challengeNextIn(String time) {
    return 'Cabaran seterusnya dalam $time';
  }

  @override
  String get challengeTapToAttempt => 'Ketuk untuk mencuba →';

  @override
  String get challengeTapToReview => 'Dijawab — ketuk untuk semak semula';

  @override
  String get leagueCardHeading => 'LEAGUE MINGGUAN';

  @override
  String get leagueTitle => 'LEAGUE';

  @override
  String get leagueRankLabel => 'KEDUDUKAN';

  @override
  String get leaguePts => 'MATA';

  @override
  String get leagueRollsInLabel => 'BERMULA';

  @override
  String get leagueUnassigned =>
      'League pertama anda bermula hari Isnin — teruskan mendapatkan mata.';

  @override
  String get leagueError => 'Gagal memuatkan kedudukan.';

  @override
  String get leagueYou => 'ANDA';

  @override
  String get leagueHistoryTitle => 'MINGGU LALU';

  @override
  String get leagueHistoryEmpty => 'Belum ada minggu yang tamat.';

  @override
  String get leagueOutcomePromoted => 'Dinaikkan';

  @override
  String get leagueOutcomeRelegated => 'Diturunkan';

  @override
  String get leagueOutcomeStay => 'Ditahan';

  @override
  String get settingsSectionLeague => 'LEAGUE';

  @override
  String get leagueHandle => 'HANDLE';

  @override
  String get leagueReputation => 'REPUTASI';

  @override
  String get leagueRegenerate => 'JANA SEMULA HANDLE';

  @override
  String get leagueRegenerateFailed =>
      'Gagal menukar handle anda — anda hanya diberi satu peluang.';

  @override
  String get settingsAppearanceValue => 'GELAP — piawaian lantai';

  @override
  String get settingsAppearanceBody =>
      'Lantai beroperasi dalam mod gelap. Tema cerah akan hadir dalam kemas kini akan datang.';

  @override
  String get watchlistEmptyTitle => 'Tiada ticker lagi';

  @override
  String get alpacaNoPositions => 'Tiada posisi terbuka';

  @override
  String get disclaimerShort => 'Simulasi pendidikan. Bukan nasihat pelaburan.';

  @override
  String get shareTooltip => 'Kongsi';

  @override
  String get shareCardStreakUnit => 'HARI BERKELANJUTAN';

  @override
  String get shareCardUnlockKicker => 'AGENT DIBUKA';

  @override
  String get shareCardVerdictKicker => 'HUKUMAN BILIK';

  @override
  String get shareCardPromotedKicker => 'KEDUDUKAN LEAGUE';

  @override
  String get shareCaption =>
      'Meja analis AMI Trade saya. Simulasi pendidikan — bukan nasihat pelaburan.';

  @override
  String get lessonReplay => 'Main Semula';

  @override
  String bugReportThanks(String shortId) {
    return 'Laporan diterima — ruj $shortId. Terima kasih.';
  }

  @override
  String bugReportResolved(String title) {
    return 'Dibetulkan: $title';
  }

  @override
  String get roomViewModeBoard => 'PAPAN';

  @override
  String get roomViewModeTranscript => 'TRANSKRIP';

  @override
  String get roomPmCardHeading => 'PENGURUS PORTFOLIO';

  @override
  String get roomHeroApprove => 'BILIK MELULUSKAN';

  @override
  String get roomHeroPass => 'BILIK BERLALU';

  @override
  String get roomHeroReject => 'DISEKAT OLEH MANDAT ANDA';

  @override
  String get roomHeroNoVerdict => 'TIADA KEPUTUSAN DIKELUARKAN';

  @override
  String get roomHeroNoResult => 'BILIK TIDAK SELESAI';

  @override
  String get roomHeroUnitPortfolio => 'DARIPADA PORTFOLIO';

  @override
  String roomHeroUnitHorizon(int days) {
    return 'UFUK $days HARI';
  }

  @override
  String get roomHeroNoPosition => 'TIADA POSISI';

  @override
  String get roomHeroNotIssued => 'TIDAK DIKELUARKAN';

  @override
  String roomHeroBlockedCount(int count) {
    return 'DISEKAT · $count PELANGGARAN';
  }

  @override
  String get roomHeroNoResultValue => 'TIADA KEPUTUSAN';

  @override
  String get roomHeroConveneAgain => 'HIMPUN SEMULA';

  @override
  String get roomOverrideHeading =>
      'MANDAT MENGATASI — PERATURAN ANDA MENGUBAH KEPUTUSAN PM';

  @override
  String roomCombVoices(int count) {
    return '$count SUARA';
  }

  @override
  String roomCombStated(int count) {
    return '$count MENYATAKAN PANDANGAN';
  }

  @override
  String get roomCombFor => 'SOKONG';

  @override
  String get roomCombNeutral => 'NEUTRAL';

  @override
  String get roomCombAgainst => 'BANTAH';

  @override
  String get roomCombNotStated => 'TIDAK DINYATAKAN';

  @override
  String get roomCombNotRecorded => 'TIDAK DIREKODKAN';

  @override
  String get roomCombNotRecordedBody =>
      'Pendirian ejen tidak direkodkan untuk sesi ini. Buka transkrip untuk membaca apa yang diperkatakan setiap seorang.';

  @override
  String get roomRibbonHeading => 'RISIKO → GANJARAN';

  @override
  String roomRibbonDerived(String levels) {
    return '$levels DITETAPKAN OLEH AMI, BUKAN PM';
  }

  @override
  String get roomGeometryNoProvenance =>
      'GEOMETRI DAGANGAN · SUMBER HARGA TIDAK DIKETAHUI';

  @override
  String get roomRosterGap => 'JURANG SENARAI';

  @override
  String roomRosterGapCount(int count) {
    return '$count TIDAK DIDENGARI';
  }

  @override
  String get roomRowNotHeard => 'TIDAK DIDENGARI';

  @override
  String get roomRowNoResponse => 'TIADA JAWAPAN';

  @override
  String roomTranscriptHint(int count) {
    return '$count SUMBANGAN · KETIK BARIS UNTUK MEMBACANYA PENUH';
  }

  @override
  String get roomWhyExpand => 'MENGAPA';

  @override
  String get roomSheetStance => 'PENDIRIAN';

  @override
  String get roomSheetConviction => 'KEYAKINAN';

  @override
  String get roomSheetReadFullDebate => 'BACA PERBAHASAN PENUH';

  @override
  String get roomStanceFor => 'SOKONG';

  @override
  String get roomStanceAgainst => 'BANTAH';

  @override
  String get roomStanceNeutral => 'NEUTRAL';

  @override
  String get roomConvictionLow => 'RENDAH';

  @override
  String get roomConvictionMedium => 'SEDERHANA';

  @override
  String get roomConvictionHigh => 'TINGGI';

  @override
  String get roomPhaseAnalysts => 'PENGANALISIS';

  @override
  String get roomPhaseResearchers => 'PENYELIDIK';

  @override
  String get roomPhaseSynthesis => 'SINTESIS';

  @override
  String get roomPhaseExecution => 'PELAKSANAAN';

  @override
  String get roomPhaseRisk => 'RISIKO';

  @override
  String get roomPhaseVerdict => 'KEPUTUSAN';

  @override
  String journalLevelsAsOf(String date) {
    return 'HARGA PADA $date — SATU REKOD, BUKAN PERSEDIAAN SEMASA';
  }

  @override
  String get journalRerunWithMandate => 'JALANKAN SEMULA DENGAN MANDAT SEMASA';

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

  @override
  String get gamesBoardTitle => 'Standings';

  @override
  String get gamesBoardCta => 'SEE THE FIELD';

  @override
  String gamesBoardYouAre(int rank, int count) {
    return 'You\'re #$rank of $count';
  }

  @override
  String get gamesBoardNotRankedYet => 'Not ranked yet';

  @override
  String get gamesBoardStandingsClosed =>
      'Standings open after the first US close.';

  @override
  String get gamesBoardUpdatesNote =>
      'Standings move once per US close — not tick by tick.';

  @override
  String get gamesBoardDeskChip => 'DESK';

  @override
  String get gamesBoardYouChip => 'YOU';

  @override
  String get gamesBoardNoCloseYet => 'No close yet';

  @override
  String gamesBoardEntrants(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count entrants',
      one: '1 entrant',
    );
    return '$_temp0';
  }

  @override
  String gamesBoardDeskCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'including $count house desks',
      one: 'including 1 house desk',
    );
    return '$_temp0';
  }

  @override
  String get gamesBoardEmpty => 'No one has entered this field yet.';

  @override
  String get gamesDesksTitle => 'House desks';

  @override
  String get gamesDesksIntro =>
      'Desks are AMI-run strategies, not people. Every desk\'s rule is published, and it trades real prices and pays the same costs you do.';

  @override
  String get gamesDeskRuleTitle => 'How this desk trades';

  @override
  String gamesDeskUniverse(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Selects from $count published names',
      one: 'Selects from 1 published name',
    );
    return '$_temp0';
  }

  @override
  String get gamesLobbyTitle => 'Choose a game';

  @override
  String get gamesLobbyCta => 'ALL GAMES';

  @override
  String get gamesLobbyIntro =>
      'One run of each at a time — five books, never two of a kind.';

  @override
  String get gamesCadenceWeek => 'Weekly';

  @override
  String get gamesCadenceMonth => 'Monthly';

  @override
  String get gamesCadenceQuarter => 'Quarterly';

  @override
  String get gamesCadenceHalf => 'Half-year';

  @override
  String get gamesCadenceYear => 'Annual';

  @override
  String gamesCadenceRuns(String start, String end) {
    return '$start → $end';
  }

  @override
  String get gamesCadenceYoureIn => 'You\'re in';

  @override
  String get gamesCadenceEntryClosed =>
      'Entry closed — next one opens when this run starts';

  @override
  String gamesCadenceWeightNote(String gain) {
    return 'Worth $gain× a weekly win';
  }

  @override
  String get gamesLobbyEnterCta => 'ENTER THIS FIELD';

  @override
  String get gamesTicketStepSizeSell => 'HOW MUCH OF THE POSITION';

  @override
  String gamesTicketSizeShares(String pct, String shares) {
    return '$pct% · $shares shares';
  }

  @override
  String get gamesTicketSizeCloseAll => 'Close it';

  @override
  String get gamesSellCta => 'SELL';

  @override
  String gamesSellTitle(String ticker) {
    return 'Sell $ticker';
  }

  @override
  String gamesSellHeld(String shares) {
    return 'You hold $shares shares';
  }

  @override
  String get gamesNoShortingNote =>
      'Long only — a sell closes what you hold, it never opens a short.';

  @override
  String get gamesSellClosesOnlyNote =>
      'A sell closes what you hold. To open a short, start a new trade and pick SHORT.';

  @override
  String get gamesTicketStepDirection => 'DIRECTION';

  @override
  String get gamesDirectionLong => 'LONG';

  @override
  String get gamesDirectionShort => 'SHORT';

  @override
  String get gamesShortFeeNote =>
      'Shorting costs 0.3% to open — three times the usual 0.1%.';

  @override
  String get gamesShortRiskNote =>
      'A short is bought back for you if the name climbs 90% — so you can lose everything you tie up, but normally no more. A price gap can jump that, and ends the run at zero.';

  @override
  String get gamesShortBadge => 'SHORT';

  @override
  String get gamesRunShortsHeading => 'SHORTS';

  @override
  String gamesRunShortSub(String shares, String price) {
    return '$shares shares shorted at $price';
  }

  @override
  String get gamesCoverCta => 'COVER';

  @override
  String gamesCoverTitle(String ticker) {
    return 'Cover $ticker';
  }

  @override
  String gamesCoverShortOf(String shares) {
    return 'You are short $shares shares';
  }

  @override
  String get gamesCoverWholeOnlyNote =>
      'A cover buys the whole position back. There is no partial cover.';

  @override
  String get gamesDuelHeading => 'DUEL';

  @override
  String get gamesDuelFirstRunHeading => 'YOUR FIRST RUN';

  @override
  String gamesDuelVersus(String handle) {
    return 'You vs $handle';
  }

  @override
  String gamesDuelAhead(String pct) {
    return 'You are $pct% ahead';
  }

  @override
  String gamesDuelBehind(String pct) {
    return 'You are $pct% behind';
  }

  @override
  String get gamesDuelLevel => 'Dead level';

  @override
  String get gamesDuelNotStarted =>
      'No closes yet — the gap is not measurable until both books have a close.';

  @override
  String gamesDuelAtStake(int points) {
    return '$points pts';
  }

  @override
  String gamesDuelDaysLeft(int days) {
    return '$days days left';
  }

  @override
  String gamesDuelWon(int points) {
    return 'You won. +$points career points.';
  }

  @override
  String gamesDuelLost(int points) {
    return 'You lost. −$points career points.';
  }

  @override
  String get gamesDuelDraw => 'A draw. No points either way.';

  @override
  String get gamesDuelVoid =>
      'Void — one side’s run could not be measured. No points either way.';

  @override
  String get gamesCloseDuelBeatTheMarket => 'You beat the market.';

  @override
  String get gamesCloseDuelMarketWon => 'The market beat you.';

  @override
  String gamesCloseDuelWon(String handle) {
    return 'You beat $handle.';
  }

  @override
  String gamesCloseDuelLost(String handle) {
    return '$handle beat you.';
  }

  @override
  String gamesCloseDuelDrew(String handle) {
    return 'Dead level with $handle.';
  }

  @override
  String gamesCloseDuelMargin(String pct) {
    return 'By $pct.';
  }

  @override
  String gamesCloseDuelPointsWon(int points) {
    return '+$points career points.';
  }

  @override
  String gamesCloseDuelPointsLost(int points) {
    return '−$points career points.';
  }

  @override
  String gamesBoardChase(String pct, int rank) {
    return '$pct% off $rankᵗʰ place';
  }

  @override
  String gamesBoardLeadBy(String pct) {
    return 'Leading by $pct%';
  }

  @override
  String get gamesTicketNoCashInPositionsBody =>
      'Every AMI Cash unit is in open positions. A short posts its full value as collateral — there is no leverage in this game — so close a position to free some up.';

  @override
  String get gamesTicketNoCashPositionsCta => 'See positions';

  @override
  String get gamesShortCollateralNote =>
      'A short posts its full value as collateral, exactly like a buy — no leverage. It comes back when you cover.';

  @override
  String get gamesTicketStepSizeShort => '2 · HOW MUCH TO SHORT';

  @override
  String gamesTicketSizeCollateral(String pct, String amount) {
    return '$pct% · $amount posted as collateral';
  }

  @override
  String gamesTicketFeeDrag(String pct) {
    return 'That fee is $pct% of this order — the \$1.00 minimum, not the 0.1% rate.';
  }

  @override
  String gamesRecordNextTitleRuns(int count, String title) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count more finished runs to $title',
      one: '1 more finished run to $title',
    );
    return '$_temp0';
  }

  @override
  String gamesRecordNextTitlePoints(int points, String title) {
    final intl.NumberFormat pointsNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String pointsString = pointsNumberFormat.format(points);

    return '$pointsString career points to $title';
  }

  @override
  String get gamesArcEntryOpenTitle => 'Entries close soon';

  @override
  String gamesArcEntryClosesIn(String countdown) {
    return 'Entries close in $countdown';
  }

  @override
  String get gamesArcBellTitle => 'THE BELL';

  @override
  String gamesArcBellBody(int count) {
    return 'The field is set: $count entrants. Trading starts at the open.';
  }

  @override
  String get gamesArcFinalStretchTitle => 'FINAL STRETCH';

  @override
  String gamesArcDaysLeft(int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: '$days days left',
      one: '1 day left',
      zero: 'Last day',
    );
    return '$_temp0';
  }

  @override
  String gamesArcStandingLine(String rank, int count) {
    return 'You\'re $rank of $count.';
  }

  @override
  String gamesArcGapLine(String rank, String gap) {
    return '$rank is $gap% ahead.';
  }

  @override
  String get gamesArcStandingsClosed => 'Standings open after the first close.';

  @override
  String get gamesArcSettlingTitle => 'SETTLING';

  @override
  String get gamesArcSettlingBody =>
      'The period is over. Positions are locked and results are being scored.';

  @override
  String gamesArcAttributionLine(String ticker, String points, String total) {
    return '$ticker drove $points of your $total.';
  }

  @override
  String gamesArcAttributionNoTotal(String ticker, String points) {
    return '$ticker is your biggest mover at $points.';
  }

  @override
  String get gamesWindUpTitle => 'THE WIND-UP';

  @override
  String get gamesWindUpBust =>
      'The book went below zero and the run was stopped.';

  @override
  String get gamesWindUpHeavyLoss => 'A hard run. Here is what happened.';

  @override
  String gamesWindUpShortfall(String amount) {
    return 'The book was $amount short of zero when it stopped.';
  }

  @override
  String gamesWindUpWorst(String ticker, String points) {
    return '$ticker cost you $points.';
  }

  @override
  String get gamesWindUpNextChapter => 'Next chapter';

  @override
  String get gamesMarkerFirstFinish => 'First run finished.';

  @override
  String gamesMarkerFirstPositive(String twr) {
    return 'First run in the green — $twr.';
  }

  @override
  String gamesMarkerFirstPodium(String rank) {
    return 'First podium — $rank.';
  }

  @override
  String gamesMarkerPersonalBest(String twr) {
    return 'Personal best — $twr.';
  }

  @override
  String gamesMarkerCleanStreak(int count) {
    return '$count finishes, no forfeits.';
  }

  @override
  String get gamesMarkerHeading => 'PROGRESS';

  @override
  String gamesBoardChampionTitle(String handle) {
    return 'Title: $handle';
  }

  @override
  String gamesBoardChampionDisplaced(String handle, String rank) {
    return 'Title: $handle ($rank overall)';
  }

  @override
  String get gamesBoardNoChampion =>
      'No title this period — every entrant ranks for AMI.';

  @override
  String get gamesBoardIneligibleNote => 'Ranks, but does not hold titles.';

  @override
  String get roomLiveModeBriefing => 'BRIEFING';

  @override
  String get roomLiveModeFloor => 'WATCH THE FLOOR';

  @override
  String get roomStageAnalystDesk => 'ANALYST DESK';

  @override
  String get roomStageResearchDebate => 'RESEARCH DEBATE';

  @override
  String get roomStageRiskReview => 'RISK REVIEW';

  @override
  String get roomStagePmVerdict => 'PM VERDICT';

  @override
  String get roomStageAnalystDeskSubtitle =>
      'Four independent reads on the same company — fundamentals, the chart, the news, the crowd.';

  @override
  String get roomStageResearchDebateSubtitle =>
      'Bull and Bear argue it out. The Research Manager adjudicates.';

  @override
  String get roomStageRiskReviewSubtitle =>
      'The Trader drafts a ticket. Aggressive, Conservative and Neutral stress it from both sides.';

  @override
  String get roomStagePmVerdictSubtitle =>
      'One call, checked against your mandate.';

  @override
  String roomStageReported(int reported, int total) {
    return '$reported/$total REPORTED';
  }

  @override
  String roomStageWorking(String agent) {
    return '$agent is working…';
  }

  @override
  String get roomBriefingCaption =>
      'You\'ll get one verdict. Tap a desk to see who\'s on it.';

  @override
  String roomStageStatusSemantic(String stage, String status) {
    return '$stage, $status';
  }

  @override
  String get floorCardPortfolio => 'SIM PORTFOLIO';

  @override
  String get floorCardPortfolioLoading => 'Reading your portfolio…';

  @override
  String floorCardPortfolioDayZero(String stake) {
    return '$stake to start · no positions yet';
  }

  @override
  String floorCardPortfolioSummary(String pnl, String cash, int positions) {
    return '$pnl all-time · $cash cash · $positions positions';
  }

  @override
  String get floorCardCalls => 'YOUR TEAM\'S CALLS';

  @override
  String get floorCardCallsEmpty =>
      'No verdicts yet — convene on your first ticker.';

  @override
  String get floorCardCallsUnavailable =>
      'Couldn\'t read your team\'s calls just now.';

  @override
  String get floorCallsNoReferencePrice =>
      'No entry level was named, so there is nothing to measure against.';

  @override
  String floorCallsWindow(int count) {
    return 'Last $count entries';
  }

  @override
  String get floorOmniboxHint => 'Type a ticker — or ask AMI anything…';

  @override
  String get floorOmniboxCaption =>
      'A ticker convenes your team. Anything else, AMI answers.';

  @override
  String floorConveneOn(String ticker) {
    return 'CONVENE THE ROOM · $ticker';
  }

  @override
  String get floorAskAmi => 'ASK AMI';

  @override
  String get floorFirmHeading => 'YOUR FIRM';

  @override
  String floorFirmSeats(int filled, int total) {
    return '$filled/$total seats filled';
  }

  @override
  String get roomConsensusHeading => 'CONSENSUS';

  @override
  String roomConsensusNeutral(int count) {
    return '· $count neutral';
  }

  @override
  String roomConsensusDissents(String agent) {
    return '$agent dissents:';
  }

  @override
  String roomConsensusUnanimous(int count) {
    return 'All $count who stated a view agreed with the call.';
  }

  @override
  String get roomConsensusNoCall =>
      'The PM made no call, so there is nothing to dissent from.';

  @override
  String get floorReactionPrompt => 'HOW DOES THE FLOOR FEEL?';

  @override
  String get floorReactionHint => 'Too much? Not enough? Say it plainly.';

  @override
  String get floorReactionSend => 'SEND';

  @override
  String get floorReactionSending => 'SENDING…';

  @override
  String get floorReactionThanks =>
      'Sent. Thank you — this goes straight to the people building it.';

  @override
  String get floorReactionFailed =>
      'Couldn\'t send that just now — it wasn\'t saved.';
}
