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
}
