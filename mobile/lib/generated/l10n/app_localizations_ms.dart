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
  String get floorFooter =>
      '⬢  AMI TRADE • SIMULASI PENDIDIKAN • BUKAN NASIHAT';

  @override
  String get floorLockedHowTo => 'CARA UNLOCK';

  @override
  String get floorLockedNoLessons =>
      'Ejen ini akan unlock secara automatik sebaik sahaja pelajaran Earn-Path tersedia. Buat masa ini, anda boleh pratonton melalui 1-on-1 jika pelan anda membenarkannya.';

  @override
  String get floorLockedEarnByLessons =>
      'Dapatkan ejen ini secara percuma dengan melengkapkan setiap pelajaran yang melibatkan mereka:';

  @override
  String get floorLockedGoToLessons => 'KE PELAJARAN';

  @override
  String floorLockedProgress(int completed, int total) {
    return '$completed / $total gateway lessons passed';
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
  String journalRetentionWarning(int days) {
    return 'Floor Pass: $days hari terakhir sahaja. Naik taraf untuk simpan semua.';
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
  String lessonsDurationMin(int min) {
    return '$min min';
  }

  @override
  String get lessonReaderLoading => 'Memuatkan…';

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
  String lessonReaderMetaDurationTrack(int min, String track) {
    return '$min min · $track';
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
  String get settingsComplianceHalal => 'Saringan Halal';

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
  String get settingsSignedOut => 'You\'ve been signed out.';

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
  String get onboardingMeetYourTeam => 'KENALI PASUKAN ANDA';

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
  String get signInWithGoogle => 'Sign in with Google';

  @override
  String get signInWithEmail => 'ATAU TERUSKAN DENGAN EMEL';

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
  String get signInGoogleFailed => 'Google sign-in failed.';

  @override
  String signInSignedInAs(String handle) {
    return 'Log masuk sebagai $handle';
  }

  @override
  String get signInLegalFootnote =>
      'AMI Trade adalah simulasi sahaja. Tiada apa-apa di sini merupakan nasihat pelaburan dan tiada dagangan sebenar dilaksanakan.';

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
      'Mandate (yours stays — we\'\'ll drop the older one)';

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
  String get tradeTicketHeading => 'DAGANGAN BARU';

  @override
  String get tradeTicketSafetyFloorBlocked => 'SAFETY FLOOR — DAGANGAN DISEKAT';

  @override
  String get tradeTicketChangeMandate =>
      'Ubah apa yang dikuatkuasakan melalui Settings → My Mandate.';

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
  String get tourFloor1Title => 'CONCIERGE ANDA';

  @override
  String get tourFloor1Body =>
      'Sentiasa tersedia. Tanya apa sahaja — pelajaran, portfolio anda, atau bacaan seterusnya.';

  @override
  String get tourFloor2Title => 'PASUKAN ANALIS ANDA';

  @override
  String get tourFloor2Body =>
      '12 pakar, setiap satu dengan domain tersendiri. Ketik mana-mana yang tidak dikunci untuk memulakan sesi satu-lawan-satu.';

  @override
  String get tourFloor3Title => 'AGEN TERKUNCI';

  @override
  String get tourFloor3Body =>
      'Selesaikan pelajaran berkaitan untuk membuka kunci setiap analis. Ketik mana-mana yang terkunci untuk melihat syaratnya.';

  @override
  String get tourFloor4Title => 'CABARAN HARIAN';

  @override
  String get tourFloor4Body =>
      'Satu cabaran sehari mengasah pertimbangan anda. Mengambil masa kurang 2 minit.';

  @override
  String get tourFloor5Title => 'CONVENE THE ROOM';

  @override
  String get tourFloor5Body =>
      'Alatan paling berkuasa anda. Semua 12 ejen menganalisis saham bersama — kemudian anda buat keputusan.';

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
      'Find any entry by ticker, agent name, or keyword across your entire history.';

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
  String get tourSettingsSectionTitle => 'PANDUAN';

  @override
  String get tourSettingsRestart => 'Mulakan semula jelajah aplikasi';

  @override
  String get tourSettingsResetDone =>
      'Jelajah akan bermula semula apabila anda melawat setiap bahagian nanti.';

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
  String get settingsAppearanceValue => 'DARK — floor standard';

  @override
  String get settingsAppearanceBody =>
      'The floor runs dark. A light theme arrives in a later release.';

  @override
  String get watchlistEmptyTitle => 'No tickers yet';

  @override
  String get alpacaNoPositions => 'No open positions';
}
