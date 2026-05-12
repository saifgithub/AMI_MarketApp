import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';
import 'app_localizations_ms.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en'),
    Locale('ms')
  ];

  /// Application title. Used in MaterialApp and system places. Keep as 'AMI Trade' across all locales — it's a product name, not translatable.
  ///
  /// In en, this message translates to:
  /// **'AMI Trade'**
  String get appTitle;

  /// Bottom-nav label for the Floor tab (Concierge + 12 agents + Convene the Room CTA).
  ///
  /// In en, this message translates to:
  /// **'Floor'**
  String get tabFloor;

  /// Bottom-nav label for the Sim Portfolio tab (cash, holdings, trades, watchlist).
  ///
  /// In en, this message translates to:
  /// **'Portfolio'**
  String get tabPortfolio;

  /// Bottom-nav label for the Decision Journal tab.
  ///
  /// In en, this message translates to:
  /// **'Journal'**
  String get tabJournal;

  /// Bottom-nav label for the Lessons tab.
  ///
  /// In en, this message translates to:
  /// **'Lessons'**
  String get tabLessons;

  /// Bottom-nav label for the Settings tab (mandate editor + account).
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get tabSettings;

  /// Settings section label for the locale switcher.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get settingsLanguage;

  /// No description provided for @settingsLanguageEnglish.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get settingsLanguageEnglish;

  /// Native name of Arabic — stays Arabic across all locales.
  ///
  /// In en, this message translates to:
  /// **'العربية'**
  String get settingsLanguageArabic;

  /// Native name of Malay — stays Malay across all locales.
  ///
  /// In en, this message translates to:
  /// **'Bahasa Melayu'**
  String get settingsLanguageMalay;

  /// Lesson card button — opens the full read flow.
  ///
  /// In en, this message translates to:
  /// **'READ'**
  String get actionRead;

  /// Lesson card button — opens the reader with quiz blocks only (A19 skip-to-quiz).
  ///
  /// In en, this message translates to:
  /// **'QUIZ ONLY'**
  String get actionQuizOnly;

  /// No description provided for @watchlistHeading.
  ///
  /// In en, this message translates to:
  /// **'WATCHLIST'**
  String get watchlistHeading;

  /// No description provided for @watchlistAdd.
  ///
  /// In en, this message translates to:
  /// **'ADD'**
  String get watchlistAdd;

  /// No description provided for @watchlistEmpty.
  ///
  /// In en, this message translates to:
  /// **'Add tickers you want to watch. Tap a row for quick actions: Ask the Market Analyst, Convene the Room, or open a trade.'**
  String get watchlistEmpty;

  /// No description provided for @watchlistOpenTradeTicket.
  ///
  /// In en, this message translates to:
  /// **'OPEN TRADE TICKET'**
  String get watchlistOpenTradeTicket;

  /// No description provided for @watchlistAskMarketAnalyst.
  ///
  /// In en, this message translates to:
  /// **'ASK THE MARKET ANALYST'**
  String get watchlistAskMarketAnalyst;

  /// No description provided for @watchlistConveneRoom.
  ///
  /// In en, this message translates to:
  /// **'CONVENE THE ROOM'**
  String get watchlistConveneRoom;

  /// No description provided for @watchlistRemove.
  ///
  /// In en, this message translates to:
  /// **'REMOVE FROM WATCHLIST'**
  String get watchlistRemove;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ar', 'en', 'ms'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return AppLocalizationsAr();
    case 'en':
      return AppLocalizationsEn();
    case 'ms':
      return AppLocalizationsMs();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
