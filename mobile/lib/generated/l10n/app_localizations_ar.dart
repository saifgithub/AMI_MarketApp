// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class AppLocalizationsAr extends AppLocalizations {
  AppLocalizationsAr([String locale = 'ar']) : super(locale);

  @override
  String get appTitle => 'AMI Trade';

  @override
  String get tabFloor => 'Floor';

  @override
  String get tabPortfolio => 'المحفظة';

  @override
  String get tabJournal => 'السجل';

  @override
  String get tabLessons => 'الدروس';

  @override
  String get tabSettings => 'الإعدادات';

  @override
  String get settingsLanguage => 'اللغة';

  @override
  String get settingsLanguageEnglish => 'الإنجليزية';

  @override
  String get settingsLanguageArabic => 'العربية';

  @override
  String get settingsLanguageMalay => 'الملايوية';

  @override
  String get actionRead => 'قراءة';

  @override
  String get actionQuizOnly => 'اختبار فقط';

  @override
  String get watchlistHeading => 'قائمة المراقبة';

  @override
  String get watchlistAdd => 'إضافة';

  @override
  String get watchlistEmpty =>
      'أضف الرموز التي ترغب في مراقبتها. اضغط على أي صف للوصول إلى الإجراءات السريعة: Ask the Market Analyst، أو Convene the Room، أو فتح تذكرة تداول.';

  @override
  String get watchlistOpenTradeTicket => 'فتح تذكرة تداول';

  @override
  String get watchlistAskMarketAnalyst => 'اسأل محلل السوق';

  @override
  String get watchlistConveneRoom => 'جمع الغرفة';

  @override
  String get watchlistRemove => 'إزالة من قائمة المراقبة';

  @override
  String get watchlistRemoved => 'تمت الإزالة من قائمة المراقبة';

  @override
  String get watchlistUndo => 'تراجع';

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
  String get floorTabUpper => 'القاعة';

  @override
  String get portfolioTabUpper => 'المحفظة';

  @override
  String get journalTabUpper => 'السجل';

  @override
  String get lessonsTabUpper => 'الدروس';

  @override
  String get settingsTabUpper => 'الإعدادات';

  @override
  String get floorConciergeHeading => 'AMI CONCIERGE';

  @override
  String get floorConciergeTagline => 'مساعدك الشخصي — اضغط للدردشة';

  @override
  String get floorTeamHeading => 'فريقك';

  @override
  String floorUnlockedSummary(int count) {
    return 'تم فتح $count من أصل 12. اضغط على السداسي المقفل لمعرفة الطريقة.';
  }

  @override
  String get floorConveneCta => 'اجتماع';

  @override
  String get floorConveneCaption =>
      'إجراء مناظرة كاملة متعددة الوكلاء حول ticker.';

  @override
  String get floorRestartOnboarding => 'إعادة تشغيل الجولة التعريفية';

  @override
  String get floorRestartOnboardingConfirmTitle =>
      'إعادة تشغيل الجولة التعريفية؟';

  @override
  String get floorRestartOnboardingConfirmBody =>
      'This runs the whole interview again from the first question. It does not replace a mandate you already have — change that in Settings → My Mandate. Your portfolio and trades are untouched.';

  @override
  String get floorRestartOnboardingConfirmCta => 'إعادة التشغيل';

  @override
  String get floorFooter =>
      '⬢  AMI TRADE • محاكاة تعليمية • ليست نصيحة استثمارية';

  @override
  String get floorLockedHowTo => 'كيفية إلغاء القفل';

  @override
  String get floorLockedNoLessons =>
      'يتم إلغاء قفل هذا العميل تلقائياً عند توفر دروس Earn-Path الخاصة به. حالياً، يمكنك معاينتهم عبر 1-on-1 إذا كانت خطتك تسمح بذلك.';

  @override
  String floorLockedEarnByLessons(int count) {
    return 'اجتز هذه الدروس الـ $count لكسب هذا العميل:';
  }

  @override
  String get floorLockedGoToLessons => 'انتقل إلى الدروس';

  @override
  String get floorLockedTapHint => 'انقر على درس للبدء';

  @override
  String floorLockedProgress(int completed, int total) {
    return 'تم اجتياز $completed من أصل $total دروس بوابة';
  }

  @override
  String get portfolioHeading => 'المحفظة';

  @override
  String get portfolioNewTradeTooltip => 'صفقة جديدة';

  @override
  String get portfolioTotalValue => 'القيمة الإجمالية';

  @override
  String get portfolioCash => 'النقد';

  @override
  String portfolioDrawdown(String pct) {
    return 'تراجع القيمة: $pct%';
  }

  @override
  String get portfolioLive => 'مباشر';

  @override
  String get portfolioMock => 'تجريبي';

  @override
  String get portfolioStartSimTrading => 'بدء التداول التجريبي';

  @override
  String get portfolioStartSimTradingBody =>
      'قم بعمل CONVENE للغرفة للحصول على حكم، ثم افتح صفقة — أو نفذ واحدة مباشرة من هنا. يعمل الـ FLOOR الخاص بمدير المحفظة عند كل عملية إرسال.';

  @override
  String get portfolioNewTrade => 'صفقة جديدة';

  @override
  String get portfolioHoldings => 'الأصول';

  @override
  String get portfolioTrades => 'الصفقات';

  @override
  String get portfolioNoTrades => 'لا توجد صفقات بعد.';

  @override
  String get portfolioCloseTooltip => 'إغلاق';

  @override
  String get portfolioAddDialogTitle => 'إضافة إلى قائمة المتابعة';

  @override
  String get portfolioAddDialogHint => 'الرمز (مثال: NVDA)';

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
  String get tickerDetailValue => 'القيمة';

  @override
  String get tickerDetailQty => 'الكمية';

  @override
  String get tickerDetailAvgCost => 'متوسط التكلفة';

  @override
  String get tickerDetailMark => 'العلامة';

  @override
  String tickerDetailOpened(String date) {
    return 'تم الفتح في $date';
  }

  @override
  String get tickerDetailWatchingHeading => 'يتم المراقبة';

  @override
  String get tickerDetailToday => 'اليوم';

  @override
  String tickerDetailAdded(String date) {
    return 'تمت الإضافة في $date';
  }

  @override
  String tickerDetailNoPosition(String ticker) {
    return 'لا يوجد مركز مفتوح أو إدخال قائمة مراقبة لـ $ticker.';
  }

  @override
  String get tickerDetailChartUnavailable =>
      'الرسم البياني غير متاح. انقر للمحاولة مرة أخرى.';

  @override
  String get tickerDetailChartRejected => 'AMI can\'t chart this one.';

  @override
  String get tickerDetailChartNoHistory => 'No price history for this period.';

  @override
  String get tickerDetailChartExpand => 'توسيع الرسم البياني';

  @override
  String get tickerDetailChartClose => 'إغلاق الرسم البياني بملء الشاشة';

  @override
  String get tickerDetailActionTrade => 'تداول';

  @override
  String get tickerDetailActionTradeMore => 'تداول المزيد';

  @override
  String get tickerDetailActionAsk => 'استفسار';

  @override
  String get tickerDetailActionConvene => 'CONVENE';

  @override
  String get tickerDetailActionWatch => 'مراقبة';

  @override
  String get tickerDetailActionClose => 'إغلاق';

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
    return 'الصفقات لـ $ticker';
  }

  @override
  String get tickerDetailNoTrades => 'لا توجد صفقات مسجلة لهذا الرمز بعد.';

  @override
  String tickerDetailClosePositionConfirmTitle(String ticker) {
    return 'إغلاق مركز $ticker؟';
  }

  @override
  String get tickerDetailClosePositionConfirmBody =>
      'سيتم إغلاق جميع الصفقات المفتوحة لهذا الرمز عند السعر الحالي. الأرباح والخسائر المحققة نهائية.';

  @override
  String get tickerDetailClosePositionConfirmCta => 'إغلاق';

  @override
  String get tickerDetailNewsHeading => 'الأخبار';

  @override
  String tickerDetailNewsEpsEstimate(String eps) {
    return 'تقدير ربحية السهم $eps';
  }

  @override
  String tickerDetailDividendExDate(String date) {
    return 'بدون أرباح $date';
  }

  @override
  String tickerDetailDividendRate(String rate) {
    return '$rate/سهم';
  }

  @override
  String get tickerDetailLotsHeading => 'دفعات أساس التكلفة';

  @override
  String get tickerDetailLotStatusOpen => 'مفتوح';

  @override
  String get tickerDetailLotStatusPartiallyClosed => 'جزئي';

  @override
  String get tickerDetailLotStatusClosed => 'مغلق';

  @override
  String tickerDetailLotEntry(String date, String price) {
    return 'فُتحت في $date بسعر \$$price';
  }

  @override
  String tickerDetailLotQuantity(String open, String closed) {
    return '$open مفتوح / $closed مغلق';
  }

  @override
  String tickerDetailLotRealised(String pnl) {
    return 'محقق $pnl';
  }

  @override
  String tickerDetailLotUnrealised(String pnl) {
    return 'غير محقق $pnl';
  }

  @override
  String get tickerDetailLotUnrealisedUnknown => 'غير محقق —';

  @override
  String get portfolioSectorAllocationHeading => 'توزيع القطاعات';

  @override
  String get portfolioSectorOtherLabel => 'أخرى (غير مصنّف)';

  @override
  String portfolioSectorBreach(String sector, String pct, String limit) {
    return '$sector عند $pct% يتجاوز حد التفويض البالغ $limit%';
  }

  @override
  String get roomVerdictSeeChart => 'عرض الرسم البياني';

  @override
  String get actionCancel => 'إلغاء';

  @override
  String get actionAdd => 'إضافة';

  @override
  String get journalHeading => 'سجل القرارات';

  @override
  String get journalFilterAll => 'الكل';

  @override
  String get journalFilterRoom => 'الغرفة';

  @override
  String get journalFilterTrade => 'صفقة';

  @override
  String get journalFilterOneOnOne => '1-ON-1';

  @override
  String get journalFilterBrief => 'ملخص';

  @override
  String get journalFilterLessons => 'الدروس';

  @override
  String get journalFilterUnlocks => 'المحتوى المفتوح';

  @override
  String get journalFilterChallenges => 'CHALLENGES';

  @override
  String journalRetentionWarning(int days) {
    return 'Floor Pass: last $days days only. Upgrade to see everything — nothing is deleted.';
  }

  @override
  String get journalEmptyTitle => 'لا توجد مدخلات بعد.';

  @override
  String get journalEmptyBody =>
      'تحدث مع وكيل، أو مدرب، أو أكمل درساً — كل إجراء يظهر هنا تلقائياً.';

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
  String get journalEntryTypeRoom => 'غرفة';

  @override
  String get journalEntryTypeChallenge => 'CHALLENGE';

  @override
  String get journalEntryTypeHealth => 'HEALTH';

  @override
  String get journalEntryTypeUnknown => 'UNKNOWN';

  @override
  String get journalDetailHeading => 'تفاصيل الإدخال';

  @override
  String get journalDetailLoading => 'جاري التحميل...';

  @override
  String get journalDetailBlockYou => 'أنت';

  @override
  String get journalDetailBlockAgent => 'الوكيل';

  @override
  String get journalDetailBlockOverlay => 'تراكب';

  @override
  String journalDetailSavedAsVersion(int version) {
    return 'تم الحفظ كإصدار v$version';
  }

  @override
  String journalDetailVerdictLine(String action) {
    return 'القرار: $action';
  }

  @override
  String get journalNoteHeading => 'ملاحظتك';

  @override
  String get journalNoteHint =>
      'لماذا كان هذا مهماً. ماذا تعلمت. ما الذي ستفعله بشكل مختلف.';

  @override
  String get journalNoteOutcome => 'النتيجة';

  @override
  String get journalNoteOutcomeWin => 'ربح';

  @override
  String get journalNoteOutcomeLoss => 'خسارة';

  @override
  String get journalNoteOutcomePending => 'قيد الانتظار';

  @override
  String get journalNoteSave => 'حفظ الملاحظة';

  @override
  String get journalNoteSaved => 'تم حفظ الملاحظة';

  @override
  String get journalSearchHint => 'بحث في المدخلات...';

  @override
  String get journalSearchEmpty => 'لا توجد مدخلات تطابق بحثك.';

  @override
  String get journalEntryDeleted => 'تم حذف المدخل';

  @override
  String get journalUndo => 'تراجع';

  @override
  String get journalTrashHeading => 'السلة';

  @override
  String get journalTrashEmpty =>
      'لا يوجد شيء هنا. تظهر المدخلات المحذوفة في هذه القائمة.';

  @override
  String get journalTrashWindowNote =>
      'يتم إخفاء المدخلات القديمة تلقائياً بعد 30 يوماً.';

  @override
  String get journalRestoreEntry => 'استعادة';

  @override
  String get journalEntryRestored => 'تم استعادة المدخل';

  @override
  String journalDeletedAgo(String ago) {
    return 'حُذف منذ $ago';
  }

  @override
  String get lessonsHeading => 'الدروس';

  @override
  String get lessonsYourProgress => 'تقدمك';

  @override
  String lessonsCount(int done, int total) {
    return '$done / $total دروس';
  }

  @override
  String get lessonsAgents => 'الوكلاء';

  @override
  String lessonsAgentsCount(int unlocked) {
    return '$unlocked / 12';
  }

  @override
  String get lessonsNextUp => 'التالي';

  @override
  String get lessonsTierInProgress => 'قيد التقدم';

  @override
  String get lessonsTierNotStarted => 'لم تبدأ';

  @override
  String get lessonsTierCompleted => 'مكتمل';

  @override
  String get lessonsContinue => 'متابعة';

  @override
  String get lessonsUnlocksAgent => 'يفتح';

  @override
  String lessonsDurationMin(int min) {
    return '$min دقيقة';
  }

  @override
  String get lessonReaderLoading => 'جاري التحميل...';

  @override
  String get lessonReaderUnavailableTitle => 'الدرس غير متاح';

  @override
  String get lessonReaderPrerequisites => 'المتطلبات السابقة';

  @override
  String get lessonReaderQuizOnlyBadge => 'اختبار فقط';

  @override
  String get lessonReaderQuizOnlyBannerOne =>
      'سيتم الانتقال مباشرة إلى الاختبار الواحد. عند اجتيازه، سيتم احتساب الدرس ضمن عمليات فتح الوكلاء. ستظهر التوضيحات عند الإجابات الخاطئة — هذه هي مساحة التعلم الخاصة بك.';

  @override
  String lessonReaderQuizOnlyBannerMany(int count) {
    return 'سيتم الانتقال مباشرة إلى $count اختبارات. عند اجتيازها جميعاً، سيتم احتساب الدرس ضمن عمليات فتح الوكلاء. ستظهر التوضيحات عند الإجابات الخاطئة.';
  }

  @override
  String get lessonReaderQuiz => 'اختبار';

  @override
  String lessonReaderChatWith(String agent) {
    return 'دردشة مع $agent';
  }

  @override
  String get lessonReaderSubmitQuiz => 'إرسال الاختبار';

  @override
  String get lessonReaderChecking => 'جاري التحقق...';

  @override
  String get lessonReaderPassed => 'اجتزت الاختبار';

  @override
  String get lessonReaderNotQuite => 'ليس تماماً';

  @override
  String lessonReaderCorrectOf(int correct, int total) {
    return '$correct / $total إجابات صحيحة';
  }

  @override
  String get lessonReaderAgentUnlocked => 'تم فتح العميل';

  @override
  String get lessonReaderTryAgain => 'حاول مرة أخرى';

  @override
  String get lessonReaderDone => 'تم';

  @override
  String get lessonReaderBackToLessons => 'العودة إلى الدروس';

  @override
  String get settingsHeading => 'الإعدادات';

  @override
  String settingsMandateVersion(int version) {
    return 'التفويض v$version';
  }

  @override
  String get settingsSaving => 'جاري الحفظ…';

  @override
  String get settingsSave => 'حفظ';

  @override
  String get settingsMandateUpdated => 'تم تحديث التفويض.';

  @override
  String get settingsRetroAuditFailed =>
      'Couldn\'t check your holdings against the new limit — open Portfolio to verify.';

  @override
  String get settingsSectionMandate => 'التفويض الخاص بي';

  @override
  String get settingsSectionCompliance => 'الامتثال';

  @override
  String get settingsSectionProfile => 'الملف الشخصي';

  @override
  String get settingsSectionLanguageUpper => 'اللغة';

  @override
  String get settingsSectionAccount => 'الحساب';

  @override
  String get settingsSectionDeveloper => 'المطور';

  @override
  String get settingsRiskScore => 'درجة المخاطرة';

  @override
  String settingsRiskScoreValue(int value) {
    return '$value / 5';
  }

  @override
  String get settingsRiskLabel1 =>
      'الحفاظ على رأس المال. أحجام صغيرة، وقف خسارة ضيق.';

  @override
  String get settingsRiskLabel2 => 'حذر. أحجام مراكز أقل من المتوسط.';

  @override
  String get settingsRiskLabel3 => 'متوازن. مراكز قياسية بنسبة 3-5%.';

  @override
  String get settingsRiskLabel4 =>
      'هجومي. أحجام أكبر في الإعدادات ذات القناعة العالية.';

  @override
  String get settingsRiskLabel5 =>
      'أقصى قدر من تحمل المخاطر. المراهنات المركزة مسموح بها.';

  @override
  String get settingsMaxDrawdown => 'أقصى تراجع';

  @override
  String get settingsMaxDrawdownExplain =>
      'يرفض مدير المحفظة الصفقات التي قد تدفع PORTFOLIO لتجاوز هذا الحد.';

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
  String get settingsComplianceTAG => 'بدون تبغ / كحول / قمار';

  @override
  String get settingsComplianceFossil => 'بدون وقود أحفوري';

  @override
  String get settingsComplianceLongOnly => 'مراكز شراء فقط';

  @override
  String get settingsComplianceLiquidOnly => 'أصول سائلة فقط';

  @override
  String get settingsProfilePlan => 'الخطة';

  @override
  String get settingsProfileLocale => 'اللغة والمنطقة';

  @override
  String get settingsProfileTimezone => 'المنطقة الزمنية';

  @override
  String get settingsProfilePath => 'المسار';

  @override
  String get settingsProfileHorizon => 'الأفق الزمني';

  @override
  String get settingsProfilePrimaryGoal => 'الهدف الأساسي';

  @override
  String get settingsProfileCredits => 'الرصيد';

  @override
  String get settingsAccountStatus => 'الحالة';

  @override
  String get settingsAccountSignedIn => 'تم تسجيل الدخول';

  @override
  String get settingsAccountGuest => 'ضيف (مجهول)';

  @override
  String get settingsAccountHandle => 'المعرف';

  @override
  String get settingsAccountGuestNote =>
      'تظل التفويضات والسجلات و PORTFOLIO على هذا الجهاز حتى تقوم بتسجيل الدخول.';

  @override
  String get settingsManageAccount => 'إدارة الحساب';

  @override
  String get settingsSignIn => 'تسجيل الدخول';

  @override
  String get settingsSignedOut => 'تم تسجيل الخروج.';

  @override
  String get settingsLanguagePlaceholderNote =>
      'يتم شحن AR + MS كعناصر نائبة حالياً — المفاتيح المفقودة تعود للغة الإنجليزية. يقوم المترجمون بإدراج ملفات ARB المناسبة ليتم تفعيل اللغة.';

  @override
  String get settingsDeveloperActive => 'الخلفية النشطة';

  @override
  String get settingsDeveloperNoUrl => '(لا يوجد رابط URL مدمج في هذا الإصدار)';

  @override
  String get settingsDeveloperNotInBuild => '· ليس في هذا الإصدار';

  @override
  String get settingsDeveloperFootnote =>
      'هذا القسم مستبعد من إصدارات MVP / App Store. سيتم الوصول إلى PROD فقط حينها.';

  @override
  String get onboardingHeader => 'AMI TRADE';

  @override
  String get onboardingHeaderSetup => 'إعداد';

  @override
  String get onboardingHintSending => 'جاري الإرسال...';

  @override
  String get onboardingHintAnswer => 'اكتب إجابتك...';

  @override
  String get onboardingReadbackContinue => 'صحيح — متابعة';

  @override
  String get onboardingClaimPrompt => 'لنحفظ هذا حتى تتذكرك فريقك.';

  @override
  String get onboardingSaveTeam => 'حفظ فريقي';

  @override
  String get onboardingSkipForNow => 'تخطي مؤقتاً';

  @override
  String get onboardingErrorTitle => 'تعذر الاتصال بالخادم';

  @override
  String get onboardingErrorUnknown => 'خطأ غير معروف';

  @override
  String get onboardingTryAgain => 'إعادة المحاولة';

  @override
  String get signInHeading => 'تسجيل الدخول';

  @override
  String get signInIntro =>
      'سجل دخولك للحفاظ على تفويضاتك وسجلك و PORTFOLIO الخاص بك عبر جميع أجهزتك. وحتى ذلك الحين، ستبقى جميع بياناتك على هذا الجهاز فقط.';

  @override
  String get signInWithApple => 'تسجيل الدخول باستخدام Apple';

  @override
  String get signInWithGoogle => 'تسجيل الدخول عبر Google';

  @override
  String get signInWithEmail => 'أو المتابعة عبر البريد الإلكتروني';

  @override
  String get signInUseEmailInstead => 'استخدام البريد الإلكتروني بدلاً من ذلك';

  @override
  String get signInEmailHint => 'you@example.com';

  @override
  String get signInSendCode => 'إرسال الرمز';

  @override
  String get signInResendCode => 'إعادة إرسال الرمز';

  @override
  String get signInCodeHint => 'رمز مكون من 6 أرقام';

  @override
  String get signInVerify => 'تحقق ومطالبة';

  @override
  String signInDevCode(String code) {
    return 'وضع DEV — الرمز: $code';
  }

  @override
  String get signInCodeSent => 'تم إرسال الرمز. يرجى مراجعة البريد الإلكتروني.';

  @override
  String get signInCodeFailed => 'فشل التحقق من الرمز. حاول مجدداً.';

  @override
  String get signInAppleFailed => 'فشل تسجيل الدخول عبر Apple.';

  @override
  String get signInGoogleFailed => 'فشل تسجيل الدخول عبر Google.';

  @override
  String signInSignedInAs(String handle) {
    return 'تم تسجيل الدخول باسم $handle';
  }

  @override
  String get signInLegalFootnote =>
      'AMI Trade هو محاكاة فقط. لا شيء هنا يعد نصيحة استثمارية ولا يتم تنفيذ أي صفقات حقيقية.';

  @override
  String get mergeSheetTitle => 'مرحباً بعودتك';

  @override
  String get mergeSheetBody =>
      'وجدنا بيانات من جلستك السابقة على هذا الجهاز. هل ترغب في دمجها مع حسابك؟';

  @override
  String get mergeSheetEmptyBody =>
      'لقد عدت وتسجيل الدخول. لم يتم نقل أي شيء من جلستك السابقة على هذا الجهاز.';

  @override
  String mergeSheetJournalEntries(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count سجلات',
      one: 'سجل واحد',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetSimTrades(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count محاكاة صفقات',
      one: '1 محاكاة صفقة',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetWatchlist(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count رموز قائمة المراقبة',
      one: '1 رمز قائمة المراقبة',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetLessons(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count دروس بدأت',
      one: '1 درس بدأ',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetOneOnOnes(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count رسائل فردية',
      one: '1 رسالة فردية',
    );
    return '$_temp0';
  }

  @override
  String mergeSheetRoomRuns(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count تشغيل غرف',
      one: '1 تشغيل غرفة',
    );
    return '$_temp0';
  }

  @override
  String get mergeSheetMandate => 'الولاية (تبقى الخاصة بك — سنحذف الأقدم)';

  @override
  String get mergeSheetMandateMove => 'الولاية من جلستك السابقة (لا تعارض)';

  @override
  String get mergeSheetConfirm => 'دمج الكل';

  @override
  String get mergeSheetKeepSeparate => 'إبقاء منفصلة';

  @override
  String get mergeSheetClose => 'فهمت';

  @override
  String get mergeSheetSuccess => 'تم الدمج في حسابك.';

  @override
  String get mergeSheetFailed =>
      'فشل الدمج. حاول مرة أخرى من الإعدادات لاحقاً.';

  @override
  String get oneOnOneAskAnything =>
      'اسألني عن أي شيء في مجال تخصصي.\nاكتب أدناه للبدء.';

  @override
  String get oneOnOneStreaming => 'جاري البث...';

  @override
  String get oneOnOneHint => 'اسأل عن أي شيء...';

  @override
  String get oneOnOneBriefTooltip => 'تدريب هذا الوكيل';

  @override
  String briefHeading(String agent) {
    return 'تدريب $agent';
  }

  @override
  String get briefNoOverlayYet => 'لا يوجد غطاء بعد — الإعدادات الافتراضية';

  @override
  String briefOverlayActive(int version) {
    return 'الغطاء v$version نشط';
  }

  @override
  String get briefNoEditsLeft =>
      '⚠️ لا توجد تعديلات متبقية — قم بالترقية لمواصلة التدريب';

  @override
  String briefOneEditLeft(int count) {
    return '⚠️ متبقي $count تعديل واحد في فئتك';
  }

  @override
  String get briefVersionHistoryTooltip => 'سجل الإصدارات';

  @override
  String briefCurrentOverlayLabel(int version) {
    return 'الغطاء الحالي — v$version';
  }

  @override
  String get briefProtectedSafetyFloor => 'محمي — FLOOR السلامة';

  @override
  String get briefProtectedMandate => 'محمي — قاعدة التفويض';

  @override
  String get briefEditLimitReached => 'تم الوصول إلى حد التعديل';

  @override
  String get briefRefused => 'رفضه المدرب';

  @override
  String briefProposalSavedSnack(int version, String summary) {
    return 'تم الحفظ كـ v$version — $summary';
  }

  @override
  String briefAgentRefused(String agent) {
    return 'رفض $agent';
  }

  @override
  String briefAgentProposal(String agent) {
    return '$agent — مقترح';
  }

  @override
  String get briefPlainEnglish => 'اللغة الإنجليزية المبسطة:';

  @override
  String get briefOverlayAddition => 'إضافة الطبقة:';

  @override
  String get briefAccept => 'قبول';

  @override
  String get briefRefine => 'تحسين';

  @override
  String get briefReject => 'رفض';

  @override
  String get briefDismiss => 'تجاهل';

  @override
  String get briefInputHint => 'أخبرني بما يجب تغييره...';

  @override
  String get briefDrafting => 'جاري الصياغة...';

  @override
  String get briefProposeChange => 'PROPOSE CHANGE';

  @override
  String briefHistoryHeading(String agent) {
    return 'سجل $agent';
  }

  @override
  String get briefHistorySubtitle => 'جميع نسخ التدريب المحفوظة';

  @override
  String briefHistoryEditsUnlimited(int count) {
    return 'تم إجراء $count تعديل • عدد غير محدود في باقتك';
  }

  @override
  String briefHistoryEditsRemaining(int count, int remaining) {
    return 'تم إجراء $count تعديل • المتبقي $remaining';
  }

  @override
  String get briefHistoryEmpty =>
      'لا يوجد سجل تدريب بعد.\nعد للخلف واقترح تغييرك الأول.';

  @override
  String get briefHistoryActiveBadge => 'نشط';

  @override
  String briefHistoryRollbackTitle(int version) {
    return 'الرجوع إلى v$version؟';
  }

  @override
  String briefHistoryRollbackBody(int version) {
    return 'سيبدأ العميل الخاص بك في استخدام v$version على الفور. ستبقى الإصدارات الأحدث في السجل.';
  }

  @override
  String get briefHistoryRollback => 'استعادة';

  @override
  String get briefHistoryRollbackToThis => 'استعادة لهذا الإصدار';

  @override
  String get conveneHeading => 'CONVENE الغرفة';

  @override
  String get convenePickTicker =>
      'اختر رمز السهم. سيقوم فريقك بالكامل بإجراء النقاش.';

  @override
  String get conveneTickerHint => 'مثال: NVDA';

  @override
  String get conveneOrPickOne => 'أو اختر واحداً';

  @override
  String get conveneCta => 'اجتماع';

  @override
  String get roomHeadingPrefix => 'CONVENE ›';

  @override
  String get roomStandingBy => 'في الانتظار';

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
  String get roomDeliberating => 'الفريق يتداول…';

  @override
  String get roomEndedNoVerdict => 'انتهت الجلسة دون قرار.';

  @override
  String get roomSavedToJournal => 'تم الحفظ في السجل';

  @override
  String get roomClose => 'إغلاق';

  @override
  String get roomSafetyFloorPill => 'SAFETY FLOOR';

  @override
  String roomVerdictHeading(String action) {
    return 'القرار — $action';
  }

  @override
  String get roomMetricTicker => 'TICKER';

  @override
  String get roomMetricSize => 'SIZE';

  @override
  String get roomMetricEntry => 'الدخول';

  @override
  String get roomMetricStop => 'وقف الخسارة';

  @override
  String get roomMetricTarget => 'الهدف';

  @override
  String get roomMetricHorizon => 'الأفق الزمني';

  @override
  String roomHorizonDays(int days) {
    return '$days أيام';
  }

  @override
  String get roomViolations => 'المخالفات';

  @override
  String get roomOpenTradeTicket => 'فتح تذكرة تداول';

  @override
  String get roomTradeTicketCaption =>
      'يتم الإرسال بناءً على حجم/وقف/هدف الحكم. إعادة تشغيل SAFETY FLOOR الخاص بمدير المحفظة.';

  @override
  String get roomWinzipTitle => 'غرفتك في طور التهيئة';

  @override
  String roomWinzipBody(String countdown) {
    return 'لقد استخدمت هذه الغرفة — AMI بالفعل تضيف لك رصيداً. غرفتك التالية تفتح في $countdown.';
  }

  @override
  String get roomWinzipReady => 'غرفتك جاهزة للاجتماع.';

  @override
  String get roomWinzipConvene => 'اجتمع الآن';

  @override
  String get roomWinzipReviewTraining => 'راجع جلسة تدريبية أثناء الانتظار';

  @override
  String get roomWinzipVoiceLine => 'غرفتك متاحة الآن';

  @override
  String get roomPaywallTitle => 'نفدت رصيد الغرفة';

  @override
  String roomPaywallBody(String date) {
    return 'عذراً — نفد رصيد الغرفة لديك مؤقتاً. سيتم تجديده في $date.';
  }

  @override
  String get roomServerErrorTitle => 'AMI غير متصل مؤقتًا';

  @override
  String get roomServerErrorBody =>
      'انقطع الاتصال للحظة — لا توجد مشكلة من جانبك. انتظر ثانيةً وحاول مجددًا.';

  @override
  String get roomRetry => 'حاول مجددًا';

  @override
  String get roomLiveDataNoticeTitle => 'بيانات مباشرة';

  @override
  String roomLiveDataFeedLive(String feed) {
    return '$feed: تم استخدام البيانات المباشرة.';
  }

  @override
  String roomLiveDataFeedWithheld(String feed) {
    return '$feed: البيانات المباشرة متاحة — يتطلب رصيدًا.';
  }

  @override
  String roomLiveDataFeedUnavailable(String feed) {
    return '$feed: البيانات المباشرة غير متاحة حاليًا.';
  }

  @override
  String roomLiveDataSurchargeCharged(int surcharge) {
    return 'كلّفت الأخبار والتواصل الاجتماعي المباشر $surcharge رصيد إضافي في هذا التشغيل.';
  }

  @override
  String get roomLiveDataUpgradeCta => 'الترقية لبيانات مباشرة';

  @override
  String roomLiveDataFeedTenure(String feed) {
    return '$feed: البيانات المباشرة متاحة — يتطلب ترقية الخطة.';
  }

  @override
  String get roomLiveDataTenureUpgradeCta => 'ترقية خطتك';

  @override
  String roomAgentWithheldChairLabel(String agent) {
    return '$agent — خارج طاقمك في هذه الخطة';
  }

  @override
  String roomAgentWithheldRosterNote(String agent, int days) {
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: '$days يوم',
      many: '$days يومًا',
      few: '$days أيام',
      two: 'يومين',
      one: 'يوم واحد',
      zero: '0 يوم',
    );
    return 'التغيير التالي في الطاقم: $agent خلال $_temp0.';
  }

  @override
  String get roomVerdictActionNoVerdict => 'لا قرار';

  @override
  String get roomVerdictOpinionsHeading => 'لم يكونوا في الغرفة';

  @override
  String get roomVerdictOpinionsNote =>
      'تم التوصل إلى هذا القرار دون مدخلاتهم.';

  @override
  String roomVerdictIncludeAnalystCta(String agent) {
    return 'تضمين $agent ←';
  }

  @override
  String get upgradeSheetTitle => 'ترقية مكتبك';

  @override
  String get upgradeSheetSubtitle =>
      'افتح المزيد من الغرف والتحليلات المميزة. تُعرض الأسعار لمنطقتك.';

  @override
  String get upgradePlanTrader => 'Trader';

  @override
  String get upgradePlanFloorManager => 'Floor Manager';

  @override
  String get upgradeIntervalMonthly => 'شهري';

  @override
  String get upgradeIntervalAnnual => 'سنوي';

  @override
  String get upgradeCreditPacksTitle => 'حزم الرصيد';

  @override
  String upgradeCreditPackCredits(int credits) {
    return '+$credits رصيد';
  }

  @override
  String get upgradeBuy => 'BUY';

  @override
  String get upgradeRestore => 'استعادة المشتريات';

  @override
  String get upgradeUnavailableTitle => 'الترقيات غير متاحة بعد';

  @override
  String upgradeUnavailableBody(String date) {
    return 'سيتم تفعيل المشتريات داخل التطبيق قريباً. لا يزال رصيد غرفك يتجدد في $date.';
  }

  @override
  String get upgradePurchasePending =>
      'جاري معالجة طلبك — سنقوم بفتحه بمجرد اكتمال المعاملة.';

  @override
  String get upgradePurchaseFailed =>
      'لم تنجح العملية. لم يتم خصم أي مبلغ — يرجى المحاولة مرة أخرى.';

  @override
  String get upgradePurchaseSuccess => 'تمت الترقية. مرحباً بك في المكتب.';

  @override
  String get upgradeRestoreNone => 'لم يتم العثور على مشتريات لاستعادتها.';

  @override
  String get settingsSectionMembership => 'MEMBERSHIP';

  @override
  String get settingsMembershipUpgrade => 'ترقية أو إدارة الخطة';

  @override
  String get tradeTicketHeading => 'صفقة جديدة';

  @override
  String get tradeTicketSafetyFloorBlocked => 'SAFETY FLOOR — التداول محظور';

  @override
  String get tradeTicketChangeMandate =>
      'قم بتغيير القيود المفروضة عبر الإعدادات ← My Mandate.';

  @override
  String get tradeTicketLabelTicker => 'الرمز';

  @override
  String get tradeTicketLabelQuantity => 'الكمية';

  @override
  String get tradeTicketLabelStop => 'إيقاف الخسارة';

  @override
  String get tradeTicketLabelTarget => 'الهدف';

  @override
  String get tradeTicketLabelHorizon => 'المدى الزمني (بالأيام)';

  @override
  String get tradeTicketHintTicker => 'NVDA';

  @override
  String get tradeTicketHintQty => '10';

  @override
  String get tradeTicketHintOptional => 'اختياري';

  @override
  String get tradeTicketSubmitting => 'جاري الإرسال...';

  @override
  String get tradeTicketSubmit => 'إرسال الصفقة';

  @override
  String get tradeTicketFooterNote =>
      'يعمل FLOOR الأمان لمدير المحفظة عند الإرسال — علامات الامتثال + drawdown + حد الاسم الواحد.';

  @override
  String get tradeTicketSideBuy => 'شراء';

  @override
  String get tradeTicketSideSell => 'بيع';

  @override
  String tradeTicketFilled(
      String side, String qty, String ticker, String price) {
    return 'تم التنفيذ: $side $qty $ticker بسعر \$$price';
  }

  @override
  String get chatBubbleConcierge => 'الكونسيرج';

  @override
  String get tourIntroTitle => 'مرحباً بك في صالة التداول الخاصة بك.';

  @override
  String get tourIntroSubtitle => 'جولة سريعة توضح لك آلية عمل AMI Trade.';

  @override
  String get tourTakeTheTour => 'ابدأ الجولة';

  @override
  String get tourSkipForNow => 'تخطي الآن';

  @override
  String get tourNext => 'التالي ←';

  @override
  String get tourDone => 'فهمت';

  @override
  String get tourSkip => 'تخطي الجولة';

  @override
  String get tourConveneTryNow => 'جربه الآن ←';

  @override
  String get tourFloor1Title => 'مساعدك الشخصي';

  @override
  String get tourFloor1Body =>
      'متاح دائماً. اسأل عن أي شيء — الدروس، محفظتك، أو ماذا تقرأ تالياً.';

  @override
  String get tourFloor2Title => 'فريق المحللين الخاص بك';

  @override
  String get tourFloor2Body =>
      '12 متخصصاً، لكل منهم مجاله. اضغط على أي محلل متاح لبدء جلسة فردية.';

  @override
  String get tourFloor3Title => 'وكلاء مقفلون';

  @override
  String get tourFloor3Body =>
      'أكمل الدروس ذات الصلة لفتح كل محلل. اضغط على أي محلل مقفل لمعرفة المتطلبات.';

  @override
  String get tourFloor4Title => 'التحدي اليومي';

  @override
  String get tourFloor4Body =>
      'تحدٍ واحد يومياً يصقل حكمك التحليلي. يستغرق أقل من دقيقتين.';

  @override
  String get tourFloor5Title => 'عقد اجتماع الغرفة';

  @override
  String get tourFloor5Body =>
      'أقوى أدواتك. يقوم جميع الوكلاء الـ 12 بتحليل السهم معاً — ثم تتخذ أنت القرار.';

  @override
  String get tourCompletionFloor => 'اذهب لعقد أول Room لك.';

  @override
  String get tourPortfolio1Title => 'محفظة محاكاة';

  @override
  String get tourPortfolio1Body =>
      'استخدم زر + لفتح OPEN TRADE TICKET. جميع الصفقات تجريبية — بدون أموال حقيقية.';

  @override
  String get tourPortfolio2Title => 'القيمة الإجمالية والربح والخسارة';

  @override
  String get tourPortfolio2Body =>
      'تتبع قيمة محفظتك والربح والخسارة الجاري هنا. هدفك هو التفوق على السوق.';

  @override
  String get tourPortfolio3Title => 'قائمة المراقبة';

  @override
  String get tourPortfolio3Body =>
      'Add tickers you\'re watching. Tap any row for quick actions.';

  @override
  String get tourCompletionPortfolio =>
      'جرب تداولاً — محاكاة كاملة، بدون مخاطر.';

  @override
  String get tourJournal1Title => 'تصفية حسب النوع';

  @override
  String get tourJournal1Body =>
      'يتم تسجيل كل شيء — جلسات Room، الصفقات، الإيجازات، والدروس. قم بالتصفية حسب النوع.';

  @override
  String get tourJournal2Title => 'بحث';

  @override
  String get tourJournal2Body =>
      'ابحث عن أي إدخال بواسطة الرمز، أو اسم الوكيل، أو كلمة مفتاحية عبر سجلك بالكامل.';

  @override
  String get tourJournal3Title => 'سجلك';

  @override
  String get tourJournal3Body =>
      'كل إدخال دائم. قراراتك محفوظة هنا — راجعها لتحسين أدائك.';

  @override
  String get tourCompletionJournal => 'يبدأ سجلك مع أول جلسة في الغرفة.';

  @override
  String get tourLessons1Title => 'الدروس';

  @override
  String get tourLessons1Body =>
      'الدروس هي طريقك لفتح جميع المحللين الـ 12. أكمل المسارات لتوسيع فريقك.';

  @override
  String get tourLessons2Title => 'تقدمك';

  @override
  String get tourLessons2Body =>
      'تتبع الدروس المكتملة والوكلاء الذين تم فتحهم. كل درس يضيف قوة هجومية لفريقك.';

  @override
  String get tourLessons3Title => 'مسارات التعلم';

  @override
  String get tourLessons3Body =>
      'كل شكل سداسي يمثل مسار تعلم. اضغط على أي منها لاستكشاف دروسه وفتح المحللين الخاصين بك.';

  @override
  String get tourCompletionLessons => 'ابدأ بـ Foundations لفتح أول محلل لك.';

  @override
  String get tourSettingsSectionTitle => 'الجولة التعريفية';

  @override
  String get tourSettingsRestart => 'إعادة تشغيل جولة التطبيق';

  @override
  String get tourSettingsResetDone =>
      'ستبدأ الجولة مجدداً في المرة القادمة التي تزور فيها كل قسم.';

  @override
  String get agentUnlockedHeadline => 'تم فتح AGENT';

  @override
  String agentUnlockedMeet(String name) {
    return 'تعرّف على $name';
  }

  @override
  String get agentUnlockedLater => 'لاحقًا';

  @override
  String get challengeRelatedLesson => 'درس ذو صلة';

  @override
  String get challengeRelatedAgent => 'AGENT ذو صلة';

  @override
  String challengeNextIn(String time) {
    return 'التحدي التالي خلال $time';
  }

  @override
  String get challengeTapToAttempt => 'انقر للمحاولة →';

  @override
  String get challengeTapToReview => 'تمت الإجابة — انقر للمراجعة';

  @override
  String get leagueCardHeading => 'الدوري الأسبوعي';

  @override
  String get leagueTitle => 'الدوري';

  @override
  String get leagueRankLabel => 'الترتيب';

  @override
  String get leaguePts => 'النقاط';

  @override
  String get leagueRollsInLabel => 'يبدأ خلال';

  @override
  String get leagueUnassigned =>
      'يبدأ دوريك الأول يوم الاثنين — واصل كسب النقاط.';

  @override
  String get leagueError => 'تعذر تحميل الترتيب.';

  @override
  String get leagueYou => 'أنت';

  @override
  String get leagueHistoryTitle => 'أسابيع سابقة';

  @override
  String get leagueHistoryEmpty => 'لا توجد أسابيع مكتملة بعد.';

  @override
  String get leagueOutcomePromoted => 'ترقية';

  @override
  String get leagueOutcomeRelegated => 'تنزيل';

  @override
  String get leagueOutcomeStay => 'بقي';

  @override
  String get settingsSectionLeague => 'LEAGUE';

  @override
  String get leagueHandle => 'HANDLE';

  @override
  String get leagueReputation => 'REPUTATION';

  @override
  String get leagueRegenerate => 'إعادة إنشاء HANDLE';

  @override
  String get leagueRegenerateFailed =>
      'تعذر تغيير الـ HANDLE — لديك تغيير واحد فقط.';

  @override
  String get settingsAppearanceValue => 'داكن — المعيار القياسي في الـ FLOOR';

  @override
  String get settingsAppearanceBody =>
      'يعمل الـ FLOOR بالوضع الداكن. ستصل السمة الفاتحة في إصدار لاحق.';

  @override
  String get watchlistEmptyTitle => 'لا توجد رموز تداول بعد';

  @override
  String get alpacaNoPositions => 'لا توجد مراكز مفتوحة';

  @override
  String get disclaimerShort => 'محاكاة تعليمية. ليست نصيحة استثمارية.';

  @override
  String get shareTooltip => 'مشاركة';

  @override
  String get shareCardStreakUnit => 'أيام متتالية';

  @override
  String get shareCardUnlockKicker => 'تم فتح AGENT';

  @override
  String get shareCardVerdictKicker => 'حكم الغرفة';

  @override
  String get shareCardPromotedKicker => 'ترتيب LEAGUE';

  @override
  String get shareCaption =>
      'مكتب المحلل الخاص بي في AMI Trade. محاكاة تعليمية — ليست نصيحة استثمارية.';

  @override
  String get lessonReplay => 'إعادة العرض';

  @override
  String bugReportThanks(String shortId) {
    return 'تم استلام التقرير — المرجع $shortId. شكراً لك.';
  }

  @override
  String bugReportResolved(String title) {
    return 'تم الإصلاح: $title';
  }

  @override
  String get roomViewModeBoard => 'اللوحة';

  @override
  String get roomViewModeTranscript => 'النص الكامل';

  @override
  String get roomPmCardHeading => 'مدير المحفظة';

  @override
  String get roomHeroApprove => 'وافقت الغرفة';

  @override
  String get roomHeroPass => 'تجاوزت الغرفة';

  @override
  String get roomHeroReject => 'محظور بموجب تفويضك';

  @override
  String get roomHeroNoVerdict => 'لم يصدر قرار';

  @override
  String get roomHeroNoResult => 'لم تكتمل الغرفة';

  @override
  String get roomHeroUnitPortfolio => 'من المحفظة';

  @override
  String roomHeroUnitHorizon(int days) {
    return 'أفق $days يوماً';
  }

  @override
  String get roomHeroNoPosition => 'لا مركز';

  @override
  String get roomHeroNotIssued => 'لم يصدر';

  @override
  String roomHeroBlockedCount(int count) {
    return 'محظور · $count مخالفات';
  }

  @override
  String get roomHeroNoResultValue => 'لا نتيجة';

  @override
  String get roomHeroConveneAgain => 'اعقد الغرفة مجدداً';

  @override
  String get roomOverrideHeading =>
      'تجاوز التفويض — قواعدك غيّرت قرار مدير المحفظة';

  @override
  String roomCombVoices(int count) {
    return '$count أصوات';
  }

  @override
  String roomCombStated(int count) {
    return '$count أبدوا رأياً';
  }

  @override
  String get roomCombFor => 'مؤيد';

  @override
  String get roomCombNeutral => 'محايد';

  @override
  String get roomCombAgainst => 'معارض';

  @override
  String get roomCombNotStated => 'لم يُبدِ رأياً';

  @override
  String get roomCombNotRecorded => 'غير مسجّل';

  @override
  String get roomCombNotRecordedBody =>
      'لم تُسجَّل مواقف الوكلاء في هذه الجلسة. افتح النص الكامل لقراءة ما قاله كل واحد منهم.';

  @override
  String get roomRibbonHeading => 'المخاطرة ← العائد';

  @override
  String roomRibbonDerived(String levels) {
    return '$levels حدّدتها AMI، لا مدير المحفظة';
  }

  @override
  String get roomGeometryNoProvenance =>
      'هندسة الصفقة · مصدر الأسعار غير معروف';

  @override
  String get roomRosterGap => 'الفجوة في الفريق';

  @override
  String roomRosterGapCount(int count) {
    return '$count لم يُسمع لهم';
  }

  @override
  String get roomRowNotHeard => 'لم يُسمع له';

  @override
  String get roomRowNoResponse => 'لا رد';

  @override
  String roomTranscriptHint(int count) {
    return '$count مساهمة · اضغط على أي سطر لقراءته كاملاً';
  }

  @override
  String get roomWhyExpand => 'لماذا';

  @override
  String get roomSheetStance => 'الموقف';

  @override
  String get roomSheetConviction => 'درجة القناعة';

  @override
  String get roomSheetReadFullDebate => 'اقرأ النقاش كاملاً';

  @override
  String get roomStanceFor => 'مؤيد';

  @override
  String get roomStanceAgainst => 'معارض';

  @override
  String get roomStanceNeutral => 'محايد';

  @override
  String get roomConvictionLow => 'منخفضة';

  @override
  String get roomConvictionMedium => 'متوسطة';

  @override
  String get roomConvictionHigh => 'عالية';

  @override
  String get roomPhaseAnalysts => 'المحللون';

  @override
  String get roomPhaseResearchers => 'الباحثون';

  @override
  String get roomPhaseSynthesis => 'التركيب';

  @override
  String get roomPhaseExecution => 'التنفيذ';

  @override
  String get roomPhaseRisk => 'المخاطر';

  @override
  String get roomPhaseVerdict => 'القرار';

  @override
  String journalLevelsAsOf(String date) {
    return 'الأسعار بتاريخ $date — سجلّ، وليست صفقة قائمة الآن';
  }

  @override
  String get journalRerunWithMandate => 'أعد التشغيل بالتفويض الحالي';

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
}
