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
  String get tabPortfolio => 'Portfolio';

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
  String get floorFooter =>
      '⬢  AMI TRADE • محاكاة تعليمية • ليست نصيحة استثمارية';

  @override
  String get floorLockedHowTo => 'كيفية إلغاء القفل';

  @override
  String get floorLockedNoLessons =>
      'يتم إلغاء قفل هذا العميل تلقائياً عند توفر دروس Earn-Path الخاصة به. حالياً، يمكنك معاينتهم عبر 1-on-1 إذا كانت خطتك تسمح بذلك.';

  @override
  String get floorLockedEarnByLessons =>
      'احصل على هذا العميل مجاناً عبر اجتياز كل درس يتضمنه:';

  @override
  String get floorLockedGoToLessons => 'انتقل إلى الدروس';

  @override
  String get floorLockedUpgradeSoon => 'ترقية للتخطي — قريباً';

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
  String get actionCancel => 'إلغاء';

  @override
  String get actionAdd => 'إضافة';

  @override
  String get journalHeading => 'سجل القرارات';

  @override
  String get journalFilterAll => 'الكل';

  @override
  String get journalFilterOneOnOne => '1-ON-1';

  @override
  String get journalFilterCoach => 'المدرب';

  @override
  String get journalFilterLessons => 'الدروس';

  @override
  String get journalFilterUnlocks => 'المحتوى المفتوح';

  @override
  String journalRetentionWarning(int days) {
    return 'Floor Pass: آخر $days أيام فقط. قم بالترقية للاحتفاظ بكل شيء.';
  }

  @override
  String get journalEmptyTitle => 'لا توجد مدخلات بعد.';

  @override
  String get journalEmptyBody =>
      'تحدث مع وكيل، أو مدرب، أو أكمل درساً — كل إجراء يظهر هنا تلقائياً.';

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
  String get journalEntryTypeRoom => 'غرفة';

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
  String get journalSearchHint => 'Search entries…';

  @override
  String get journalSearchEmpty => 'No entries match your search.';

  @override
  String get journalEntryDeleted => 'Entry removed';

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
  String lessonsDurationMin(int min) {
    return '$min دقيقة';
  }

  @override
  String get lessonReaderLoading => 'جاري التحميل...';

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
  String lessonReaderMetaDurationTrack(int min, String track) {
    return '$min دقيقة · $track';
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
  String get settingsComplianceHalal => 'فلتر الحلال';

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
  String get onboardingMeetYourTeam => 'تعرف على فريقك';

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
  String get signInWithEmail => 'أو المتابعة عبر البريد الإلكتروني';

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
  String signInSignedInAs(String handle) {
    return 'تم تسجيل الدخول باسم $handle';
  }

  @override
  String get signInLegalFootnote =>
      'AMI Trade هو محاكاة فقط. لا شيء هنا يعد نصيحة استثمارية ولا يتم تنفيذ أي صفقات حقيقية.';

  @override
  String get oneOnOneAskAnything =>
      'اسألني عن أي شيء في مجال تخصصي.\nاكتب أدناه للبدء.';

  @override
  String get oneOnOneStreaming => 'جاري البث...';

  @override
  String get oneOnOneHint => 'اسأل عن أي شيء...';

  @override
  String get oneOnOneCoachTooltip => 'تدريب هذا الوكيل';

  @override
  String coachHeading(String agent) {
    return 'تدريب $agent';
  }

  @override
  String get coachNoOverlayYet => 'لا يوجد غطاء بعد — الإعدادات الافتراضية';

  @override
  String coachOverlayActive(int version) {
    return 'الغطاء v$version نشط';
  }

  @override
  String get coachNoEditsLeft =>
      '⚠️ لا توجد تعديلات متبقية — قم بالترقية لمواصلة التدريب';

  @override
  String coachOneEditLeft(int count) {
    return '⚠️ متبقي $count تعديل واحد في فئتك';
  }

  @override
  String get coachVersionHistoryTooltip => 'سجل الإصدارات';

  @override
  String coachCurrentOverlayLabel(int version) {
    return 'الغطاء الحالي — v$version';
  }

  @override
  String get coachProtectedSafetyFloor => 'محمي — FLOOR السلامة';

  @override
  String get coachProtectedMandate => 'محمي — قاعدة التفويض';

  @override
  String get coachEditLimitReached => 'تم الوصول إلى حد التعديل';

  @override
  String get coachRefused => 'رفضه المدرب';

  @override
  String coachProposalSavedSnack(int version, String summary) {
    return 'تم الحفظ كـ v$version — $summary';
  }

  @override
  String coachAgentRefused(String agent) {
    return 'رفض $agent';
  }

  @override
  String coachAgentProposal(String agent) {
    return '$agent — مقترح';
  }

  @override
  String get coachPlainEnglish => 'اللغة الإنجليزية المبسطة:';

  @override
  String get coachOverlayAddition => 'إضافة الطبقة:';

  @override
  String get coachAccept => 'قبول';

  @override
  String get coachRefine => 'تحسين';

  @override
  String get coachReject => 'رفض';

  @override
  String get coachDismiss => 'تجاهل';

  @override
  String get coachInputHint => 'أخبرني بما يجب تغييره...';

  @override
  String get coachDrafting => 'جاري الصياغة...';

  @override
  String get coachProposeChange => 'PROPOSE CHANGE';

  @override
  String coachHistoryHeading(String agent) {
    return 'سجل $agent';
  }

  @override
  String get coachHistorySubtitle => 'جميع نسخ التدريب المحفوظة';

  @override
  String coachHistoryEditsUnlimited(int count) {
    return 'تم إجراء $count تعديل • عدد غير محدود في باقتك';
  }

  @override
  String coachHistoryEditsRemaining(int count, int remaining) {
    return 'تم إجراء $count تعديل • المتبقي $remaining';
  }

  @override
  String get coachHistoryEmpty =>
      'لا يوجد سجل تدريب بعد.\nعد للخلف واقترح تغييرك الأول.';

  @override
  String get coachHistoryActiveBadge => 'نشط';

  @override
  String coachHistoryRollbackTitle(int version) {
    return 'الرجوع إلى v$version؟';
  }

  @override
  String coachHistoryRollbackBody(int version) {
    return 'سيبدأ العميل الخاص بك في استخدام v$version على الفور. ستبقى الإصدارات الأحدث في السجل.';
  }

  @override
  String get coachHistoryRollback => 'استعادة';

  @override
  String get coachHistoryRollbackToThis => 'استعادة لهذا الإصدار';

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
  String get conveneCta => 'CONVENE';

  @override
  String get roomHeadingPrefix => 'CONVENE ›';

  @override
  String get roomStandingBy => 'في الانتظار';

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
}
