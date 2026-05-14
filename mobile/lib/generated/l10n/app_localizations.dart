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

  /// No description provided for @floorTabUpper.
  ///
  /// In en, this message translates to:
  /// **'FLOOR'**
  String get floorTabUpper;

  /// No description provided for @portfolioTabUpper.
  ///
  /// In en, this message translates to:
  /// **'PORTFOLIO'**
  String get portfolioTabUpper;

  /// No description provided for @journalTabUpper.
  ///
  /// In en, this message translates to:
  /// **'JOURNAL'**
  String get journalTabUpper;

  /// No description provided for @lessonsTabUpper.
  ///
  /// In en, this message translates to:
  /// **'LESSONS'**
  String get lessonsTabUpper;

  /// No description provided for @settingsTabUpper.
  ///
  /// In en, this message translates to:
  /// **'SETTINGS'**
  String get settingsTabUpper;

  /// No description provided for @floorConciergeHeading.
  ///
  /// In en, this message translates to:
  /// **'AMI CONCIERGE'**
  String get floorConciergeHeading;

  /// No description provided for @floorConciergeTagline.
  ///
  /// In en, this message translates to:
  /// **'Your personal assistant — tap to chat'**
  String get floorConciergeTagline;

  /// No description provided for @floorTeamHeading.
  ///
  /// In en, this message translates to:
  /// **'YOUR TEAM'**
  String get floorTeamHeading;

  /// Header summary above the 12-agent grid. {count} is the number of unlocked agents.
  ///
  /// In en, this message translates to:
  /// **'{count} of 12 unlocked. Tap a locked hex to see how.'**
  String floorUnlockedSummary(int count);

  /// No description provided for @floorConveneCta.
  ///
  /// In en, this message translates to:
  /// **'CONVENE THE ROOM'**
  String get floorConveneCta;

  /// No description provided for @floorConveneCaption.
  ///
  /// In en, this message translates to:
  /// **'Run a full multi-agent debate on a ticker.'**
  String get floorConveneCaption;

  /// No description provided for @floorRestartOnboarding.
  ///
  /// In en, this message translates to:
  /// **'restart onboarding'**
  String get floorRestartOnboarding;

  /// No description provided for @floorFooter.
  ///
  /// In en, this message translates to:
  /// **'⬢  AMI TRADE • EDUCATIONAL SIMULATION • NOT ADVICE'**
  String get floorFooter;

  /// No description provided for @floorLockedHowTo.
  ///
  /// In en, this message translates to:
  /// **'HOW TO UNLOCK'**
  String get floorLockedHowTo;

  /// No description provided for @floorLockedNoLessons.
  ///
  /// In en, this message translates to:
  /// **'This agent unlocks automatically once the Earn-Path lessons for them ship. For now you can preview them via 1-on-1 if your plan allows.'**
  String get floorLockedNoLessons;

  /// No description provided for @floorLockedEarnByLessons.
  ///
  /// In en, this message translates to:
  /// **'Earn this agent free by passing every lesson that involves them:'**
  String get floorLockedEarnByLessons;

  /// No description provided for @floorLockedGoToLessons.
  ///
  /// In en, this message translates to:
  /// **'GO TO LESSONS'**
  String get floorLockedGoToLessons;

  /// No description provided for @floorLockedUpgradeSoon.
  ///
  /// In en, this message translates to:
  /// **'UPGRADE TO SKIP — coming soon'**
  String get floorLockedUpgradeSoon;

  /// No description provided for @portfolioHeading.
  ///
  /// In en, this message translates to:
  /// **'PORTFOLIO'**
  String get portfolioHeading;

  /// No description provided for @portfolioNewTradeTooltip.
  ///
  /// In en, this message translates to:
  /// **'New trade'**
  String get portfolioNewTradeTooltip;

  /// No description provided for @portfolioTotalValue.
  ///
  /// In en, this message translates to:
  /// **'TOTAL VALUE'**
  String get portfolioTotalValue;

  /// No description provided for @portfolioCash.
  ///
  /// In en, this message translates to:
  /// **'CASH'**
  String get portfolioCash;

  /// Drawdown line under total value. {pct} is the formatted percentage (one decimal).
  ///
  /// In en, this message translates to:
  /// **'Drawdown: {pct}%'**
  String portfolioDrawdown(String pct);

  /// No description provided for @portfolioLive.
  ///
  /// In en, this message translates to:
  /// **'LIVE'**
  String get portfolioLive;

  /// No description provided for @portfolioMock.
  ///
  /// In en, this message translates to:
  /// **'MOCK'**
  String get portfolioMock;

  /// No description provided for @portfolioStartSimTrading.
  ///
  /// In en, this message translates to:
  /// **'Start sim trading'**
  String get portfolioStartSimTrading;

  /// No description provided for @portfolioStartSimTradingBody.
  ///
  /// In en, this message translates to:
  /// **'Convene the Room to get a verdict, then open a trade — or place one directly from here. Your PM\'\'s safety floor runs on every submit.'**
  String get portfolioStartSimTradingBody;

  /// No description provided for @portfolioNewTrade.
  ///
  /// In en, this message translates to:
  /// **'NEW TRADE'**
  String get portfolioNewTrade;

  /// No description provided for @portfolioHoldings.
  ///
  /// In en, this message translates to:
  /// **'HOLDINGS'**
  String get portfolioHoldings;

  /// No description provided for @portfolioTrades.
  ///
  /// In en, this message translates to:
  /// **'TRADES'**
  String get portfolioTrades;

  /// No description provided for @portfolioNoTrades.
  ///
  /// In en, this message translates to:
  /// **'No trades yet.'**
  String get portfolioNoTrades;

  /// No description provided for @portfolioCloseTooltip.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get portfolioCloseTooltip;

  /// No description provided for @portfolioAddDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'ADD TO WATCHLIST'**
  String get portfolioAddDialogTitle;

  /// No description provided for @portfolioAddDialogHint.
  ///
  /// In en, this message translates to:
  /// **'Ticker (e.g. NVDA)'**
  String get portfolioAddDialogHint;

  /// Generic cancel button in dialogs and sheets.
  ///
  /// In en, this message translates to:
  /// **'CANCEL'**
  String get actionCancel;

  /// Generic add button used in watchlist add dialog.
  ///
  /// In en, this message translates to:
  /// **'ADD'**
  String get actionAdd;

  /// No description provided for @journalHeading.
  ///
  /// In en, this message translates to:
  /// **'DECISION JOURNAL'**
  String get journalHeading;

  /// No description provided for @journalFilterAll.
  ///
  /// In en, this message translates to:
  /// **'ALL'**
  String get journalFilterAll;

  /// No description provided for @journalFilterOneOnOne.
  ///
  /// In en, this message translates to:
  /// **'1-ON-1'**
  String get journalFilterOneOnOne;

  /// No description provided for @journalFilterCoach.
  ///
  /// In en, this message translates to:
  /// **'COACH'**
  String get journalFilterCoach;

  /// No description provided for @journalFilterLessons.
  ///
  /// In en, this message translates to:
  /// **'LESSONS'**
  String get journalFilterLessons;

  /// No description provided for @journalFilterUnlocks.
  ///
  /// In en, this message translates to:
  /// **'UNLOCKS'**
  String get journalFilterUnlocks;

  /// Amber notice on Journal when the user is on Floor Pass. {days} is the retention window.
  ///
  /// In en, this message translates to:
  /// **'Floor Pass: last {days} days only. Upgrade to keep everything.'**
  String journalRetentionWarning(int days);

  /// No description provided for @journalEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'No entries yet.'**
  String get journalEmptyTitle;

  /// No description provided for @journalEmptyBody.
  ///
  /// In en, this message translates to:
  /// **'Talk to an agent, coach one, or complete a lesson — every action lands here automatically.'**
  String get journalEmptyBody;

  /// No description provided for @journalEntryTypeOneOnOne.
  ///
  /// In en, this message translates to:
  /// **'1-ON-1'**
  String get journalEntryTypeOneOnOne;

  /// No description provided for @journalEntryTypeCoach.
  ///
  /// In en, this message translates to:
  /// **'COACH'**
  String get journalEntryTypeCoach;

  /// No description provided for @journalEntryTypeLesson.
  ///
  /// In en, this message translates to:
  /// **'LESSON'**
  String get journalEntryTypeLesson;

  /// No description provided for @journalEntryTypeUnlock.
  ///
  /// In en, this message translates to:
  /// **'UNLOCK'**
  String get journalEntryTypeUnlock;

  /// No description provided for @journalEntryTypeTrade.
  ///
  /// In en, this message translates to:
  /// **'TRADE'**
  String get journalEntryTypeTrade;

  /// No description provided for @journalEntryTypeMandate.
  ///
  /// In en, this message translates to:
  /// **'MANDATE'**
  String get journalEntryTypeMandate;

  /// No description provided for @journalEntryTypeDrift.
  ///
  /// In en, this message translates to:
  /// **'DRIFT'**
  String get journalEntryTypeDrift;

  /// No description provided for @journalEntryTypeRoom.
  ///
  /// In en, this message translates to:
  /// **'ROOM'**
  String get journalEntryTypeRoom;

  /// No description provided for @journalDetailHeading.
  ///
  /// In en, this message translates to:
  /// **'ENTRY DETAIL'**
  String get journalDetailHeading;

  /// No description provided for @journalDetailLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading…'**
  String get journalDetailLoading;

  /// No description provided for @journalDetailBlockYou.
  ///
  /// In en, this message translates to:
  /// **'YOU'**
  String get journalDetailBlockYou;

  /// No description provided for @journalDetailBlockAgent.
  ///
  /// In en, this message translates to:
  /// **'AGENT'**
  String get journalDetailBlockAgent;

  /// No description provided for @journalDetailBlockOverlay.
  ///
  /// In en, this message translates to:
  /// **'OVERLAY'**
  String get journalDetailBlockOverlay;

  /// Coach proposal detail — shows which overlay version was saved. {version} is the integer version.
  ///
  /// In en, this message translates to:
  /// **'Saved as v{version}'**
  String journalDetailSavedAsVersion(int version);

  /// Room run verdict line in the journal detail. {action} is the verdict action (e.g. APPROVE).
  ///
  /// In en, this message translates to:
  /// **'VERDICT: {action}'**
  String journalDetailVerdictLine(String action);

  /// No description provided for @journalNoteHeading.
  ///
  /// In en, this message translates to:
  /// **'YOUR NOTE'**
  String get journalNoteHeading;

  /// No description provided for @journalNoteHint.
  ///
  /// In en, this message translates to:
  /// **'Why this mattered. What you learned. What you\'\'d do differently.'**
  String get journalNoteHint;

  /// No description provided for @journalNoteOutcome.
  ///
  /// In en, this message translates to:
  /// **'OUTCOME'**
  String get journalNoteOutcome;

  /// No description provided for @journalNoteOutcomeWin.
  ///
  /// In en, this message translates to:
  /// **'WIN'**
  String get journalNoteOutcomeWin;

  /// No description provided for @journalNoteOutcomeLoss.
  ///
  /// In en, this message translates to:
  /// **'LOSS'**
  String get journalNoteOutcomeLoss;

  /// No description provided for @journalNoteOutcomePending.
  ///
  /// In en, this message translates to:
  /// **'PENDING'**
  String get journalNoteOutcomePending;

  /// No description provided for @journalNoteSave.
  ///
  /// In en, this message translates to:
  /// **'SAVE NOTE'**
  String get journalNoteSave;

  /// No description provided for @journalNoteSaved.
  ///
  /// In en, this message translates to:
  /// **'Note saved'**
  String get journalNoteSaved;

  /// No description provided for @journalSearchHint.
  ///
  /// In en, this message translates to:
  /// **'Search entries…'**
  String get journalSearchHint;

  /// No description provided for @journalSearchEmpty.
  ///
  /// In en, this message translates to:
  /// **'No entries match your search.'**
  String get journalSearchEmpty;

  /// No description provided for @journalEntryDeleted.
  ///
  /// In en, this message translates to:
  /// **'Entry removed'**
  String get journalEntryDeleted;

  /// No description provided for @journalUndo.
  ///
  /// In en, this message translates to:
  /// **'UNDO'**
  String get journalUndo;

  /// No description provided for @journalTrashHeading.
  ///
  /// In en, this message translates to:
  /// **'TRASH'**
  String get journalTrashHeading;

  /// No description provided for @journalTrashEmpty.
  ///
  /// In en, this message translates to:
  /// **'Nothing here. Deleted entries appear in this list.'**
  String get journalTrashEmpty;

  /// No description provided for @journalTrashWindowNote.
  ///
  /// In en, this message translates to:
  /// **'Older entries are auto-hidden after 30 days.'**
  String get journalTrashWindowNote;

  /// No description provided for @journalRestoreEntry.
  ///
  /// In en, this message translates to:
  /// **'RESTORE'**
  String get journalRestoreEntry;

  /// No description provided for @journalEntryRestored.
  ///
  /// In en, this message translates to:
  /// **'Entry restored'**
  String get journalEntryRestored;

  /// Caption under a deleted journal entry in the Trash view. {ago} is a relative time string like '2h ago' or '3d ago'.
  ///
  /// In en, this message translates to:
  /// **'Deleted {ago}'**
  String journalDeletedAgo(String ago);

  /// No description provided for @lessonsHeading.
  ///
  /// In en, this message translates to:
  /// **'LESSONS'**
  String get lessonsHeading;

  /// No description provided for @lessonsYourProgress.
  ///
  /// In en, this message translates to:
  /// **'YOUR PROGRESS'**
  String get lessonsYourProgress;

  /// Progress card body — {done} lessons completed of {total}.
  ///
  /// In en, this message translates to:
  /// **'{done} / {total} lessons'**
  String lessonsCount(int done, int total);

  /// No description provided for @lessonsAgents.
  ///
  /// In en, this message translates to:
  /// **'AGENTS'**
  String get lessonsAgents;

  /// Progress card — {unlocked} of 12 agents unlocked.
  ///
  /// In en, this message translates to:
  /// **'{unlocked} / 12'**
  String lessonsAgentsCount(int unlocked);

  /// No description provided for @lessonsNextUp.
  ///
  /// In en, this message translates to:
  /// **'NEXT UP'**
  String get lessonsNextUp;

  /// Lesson card duration label. {min} is the integer duration in minutes.
  ///
  /// In en, this message translates to:
  /// **'{min} min'**
  String lessonsDurationMin(int min);

  /// No description provided for @lessonReaderLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading…'**
  String get lessonReaderLoading;

  /// No description provided for @lessonReaderQuizOnlyBadge.
  ///
  /// In en, this message translates to:
  /// **'QUIZ ONLY'**
  String get lessonReaderQuizOnlyBadge;

  /// No description provided for @lessonReaderQuizOnlyBannerOne.
  ///
  /// In en, this message translates to:
  /// **'Skipping straight to the 1 quiz. Pass it and the lesson still counts toward agent unlocks. Wrong answers will show the explanation — that\'\'s your teaching surface.'**
  String get lessonReaderQuizOnlyBannerOne;

  /// Banner shown when the user enters quiz-only mode and there are 2+ quizzes. {count} is the integer number of quiz blocks.
  ///
  /// In en, this message translates to:
  /// **'Skipping straight to the {count} quizzes. Pass them all and the lesson still counts toward agent unlocks. Wrong answers will show the explanation.'**
  String lessonReaderQuizOnlyBannerMany(int count);

  /// Lesson meta bar — duration in minutes + track name.
  ///
  /// In en, this message translates to:
  /// **'{min} min · {track}'**
  String lessonReaderMetaDurationTrack(int min, String track);

  /// No description provided for @lessonReaderQuiz.
  ///
  /// In en, this message translates to:
  /// **'QUIZ'**
  String get lessonReaderQuiz;

  /// Chat-with block label inside a lesson. {agent} is the agent display name (upper-cased before insertion is fine).
  ///
  /// In en, this message translates to:
  /// **'CHAT WITH {agent}'**
  String lessonReaderChatWith(String agent);

  /// No description provided for @lessonReaderSubmitQuiz.
  ///
  /// In en, this message translates to:
  /// **'SUBMIT QUIZ'**
  String get lessonReaderSubmitQuiz;

  /// No description provided for @lessonReaderChecking.
  ///
  /// In en, this message translates to:
  /// **'CHECKING…'**
  String get lessonReaderChecking;

  /// No description provided for @lessonReaderPassed.
  ///
  /// In en, this message translates to:
  /// **'PASSED'**
  String get lessonReaderPassed;

  /// No description provided for @lessonReaderNotQuite.
  ///
  /// In en, this message translates to:
  /// **'NOT QUITE'**
  String get lessonReaderNotQuite;

  /// Quiz result — {correct} of {total} questions correct.
  ///
  /// In en, this message translates to:
  /// **'{correct} / {total} correct'**
  String lessonReaderCorrectOf(int correct, int total);

  /// No description provided for @lessonReaderAgentUnlocked.
  ///
  /// In en, this message translates to:
  /// **'AGENT UNLOCKED'**
  String get lessonReaderAgentUnlocked;

  /// No description provided for @lessonReaderTryAgain.
  ///
  /// In en, this message translates to:
  /// **'TRY AGAIN'**
  String get lessonReaderTryAgain;

  /// No description provided for @lessonReaderDone.
  ///
  /// In en, this message translates to:
  /// **'DONE'**
  String get lessonReaderDone;

  /// No description provided for @lessonReaderBackToLessons.
  ///
  /// In en, this message translates to:
  /// **'BACK TO LESSONS'**
  String get lessonReaderBackToLessons;

  /// No description provided for @settingsHeading.
  ///
  /// In en, this message translates to:
  /// **'SETTINGS'**
  String get settingsHeading;

  /// Header label showing the active mandate version. {version} is the integer version.
  ///
  /// In en, this message translates to:
  /// **'mandate v{version}'**
  String settingsMandateVersion(int version);

  /// No description provided for @settingsSaving.
  ///
  /// In en, this message translates to:
  /// **'SAVING…'**
  String get settingsSaving;

  /// No description provided for @settingsSave.
  ///
  /// In en, this message translates to:
  /// **'SAVE'**
  String get settingsSave;

  /// No description provided for @settingsMandateUpdated.
  ///
  /// In en, this message translates to:
  /// **'Mandate updated.'**
  String get settingsMandateUpdated;

  /// No description provided for @settingsSectionMandate.
  ///
  /// In en, this message translates to:
  /// **'MY MANDATE'**
  String get settingsSectionMandate;

  /// No description provided for @settingsSectionCompliance.
  ///
  /// In en, this message translates to:
  /// **'COMPLIANCE'**
  String get settingsSectionCompliance;

  /// No description provided for @settingsSectionProfile.
  ///
  /// In en, this message translates to:
  /// **'PROFILE'**
  String get settingsSectionProfile;

  /// No description provided for @settingsSectionLanguageUpper.
  ///
  /// In en, this message translates to:
  /// **'LANGUAGE'**
  String get settingsSectionLanguageUpper;

  /// No description provided for @settingsSectionAccount.
  ///
  /// In en, this message translates to:
  /// **'ACCOUNT'**
  String get settingsSectionAccount;

  /// No description provided for @settingsSectionDeveloper.
  ///
  /// In en, this message translates to:
  /// **'DEVELOPER'**
  String get settingsSectionDeveloper;

  /// No description provided for @settingsRiskScore.
  ///
  /// In en, this message translates to:
  /// **'Risk score'**
  String get settingsRiskScore;

  /// Risk slider value caption — current score out of 5.
  ///
  /// In en, this message translates to:
  /// **'{value} / 5'**
  String settingsRiskScoreValue(int value);

  /// No description provided for @settingsRiskLabel1.
  ///
  /// In en, this message translates to:
  /// **'Capital preservation. Small sizes, tight stops.'**
  String get settingsRiskLabel1;

  /// No description provided for @settingsRiskLabel2.
  ///
  /// In en, this message translates to:
  /// **'Cautious. Below-average position sizing.'**
  String get settingsRiskLabel2;

  /// No description provided for @settingsRiskLabel3.
  ///
  /// In en, this message translates to:
  /// **'Balanced. Standard 3-5% positions.'**
  String get settingsRiskLabel3;

  /// No description provided for @settingsRiskLabel4.
  ///
  /// In en, this message translates to:
  /// **'Aggressive. Larger sizes on high-conviction setups.'**
  String get settingsRiskLabel4;

  /// No description provided for @settingsRiskLabel5.
  ///
  /// In en, this message translates to:
  /// **'Highest risk tolerance. Concentrated bets allowed.'**
  String get settingsRiskLabel5;

  /// No description provided for @settingsMaxDrawdown.
  ///
  /// In en, this message translates to:
  /// **'Max drawdown'**
  String get settingsMaxDrawdown;

  /// No description provided for @settingsMaxDrawdownExplain.
  ///
  /// In en, this message translates to:
  /// **'Your PM refuses trades that would push the portfolio past this.'**
  String get settingsMaxDrawdownExplain;

  /// No description provided for @settingsComplianceHalal.
  ///
  /// In en, this message translates to:
  /// **'Halal screen'**
  String get settingsComplianceHalal;

  /// No description provided for @settingsComplianceEsgLite.
  ///
  /// In en, this message translates to:
  /// **'ESG-lite'**
  String get settingsComplianceEsgLite;

  /// No description provided for @settingsComplianceTAG.
  ///
  /// In en, this message translates to:
  /// **'No tobacco / alcohol / gambling'**
  String get settingsComplianceTAG;

  /// No description provided for @settingsComplianceFossil.
  ///
  /// In en, this message translates to:
  /// **'No fossil fuels'**
  String get settingsComplianceFossil;

  /// No description provided for @settingsComplianceLongOnly.
  ///
  /// In en, this message translates to:
  /// **'Long-only'**
  String get settingsComplianceLongOnly;

  /// No description provided for @settingsComplianceLiquidOnly.
  ///
  /// In en, this message translates to:
  /// **'Liquid-only'**
  String get settingsComplianceLiquidOnly;

  /// No description provided for @settingsProfilePlan.
  ///
  /// In en, this message translates to:
  /// **'Plan'**
  String get settingsProfilePlan;

  /// No description provided for @settingsProfileLocale.
  ///
  /// In en, this message translates to:
  /// **'Locale'**
  String get settingsProfileLocale;

  /// No description provided for @settingsProfileTimezone.
  ///
  /// In en, this message translates to:
  /// **'Timezone'**
  String get settingsProfileTimezone;

  /// No description provided for @settingsProfilePath.
  ///
  /// In en, this message translates to:
  /// **'Path'**
  String get settingsProfilePath;

  /// No description provided for @settingsProfileHorizon.
  ///
  /// In en, this message translates to:
  /// **'Horizon'**
  String get settingsProfileHorizon;

  /// No description provided for @settingsProfilePrimaryGoal.
  ///
  /// In en, this message translates to:
  /// **'Primary goal'**
  String get settingsProfilePrimaryGoal;

  /// No description provided for @settingsProfileCredits.
  ///
  /// In en, this message translates to:
  /// **'Credits'**
  String get settingsProfileCredits;

  /// No description provided for @settingsAccountStatus.
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get settingsAccountStatus;

  /// No description provided for @settingsAccountSignedIn.
  ///
  /// In en, this message translates to:
  /// **'Signed in'**
  String get settingsAccountSignedIn;

  /// No description provided for @settingsAccountGuest.
  ///
  /// In en, this message translates to:
  /// **'Guest (anonymous)'**
  String get settingsAccountGuest;

  /// No description provided for @settingsAccountHandle.
  ///
  /// In en, this message translates to:
  /// **'Handle'**
  String get settingsAccountHandle;

  /// No description provided for @settingsAccountGuestNote.
  ///
  /// In en, this message translates to:
  /// **'Mandate, journal, and portfolio stay on this device until you sign in.'**
  String get settingsAccountGuestNote;

  /// No description provided for @settingsManageAccount.
  ///
  /// In en, this message translates to:
  /// **'MANAGE ACCOUNT'**
  String get settingsManageAccount;

  /// No description provided for @settingsSignIn.
  ///
  /// In en, this message translates to:
  /// **'SIGN IN'**
  String get settingsSignIn;

  /// No description provided for @settingsLanguagePlaceholderNote.
  ///
  /// In en, this message translates to:
  /// **'AR + MS ship as placeholders today — missing keys fall back to English. Translators drop in proper ARBs and the locale lights up.'**
  String get settingsLanguagePlaceholderNote;

  /// No description provided for @settingsDeveloperActive.
  ///
  /// In en, this message translates to:
  /// **'Active backend'**
  String get settingsDeveloperActive;

  /// No description provided for @settingsDeveloperNoUrl.
  ///
  /// In en, this message translates to:
  /// **'(no URL baked into this build)'**
  String get settingsDeveloperNoUrl;

  /// No description provided for @settingsDeveloperNotInBuild.
  ///
  /// In en, this message translates to:
  /// **'· not in this build'**
  String get settingsDeveloperNotInBuild;

  /// No description provided for @settingsDeveloperFootnote.
  ///
  /// In en, this message translates to:
  /// **'This section is compiled out of MVP / App Store builds. Only PROD will be reachable then.'**
  String get settingsDeveloperFootnote;

  /// No description provided for @onboardingHeader.
  ///
  /// In en, this message translates to:
  /// **'AMI TRADE'**
  String get onboardingHeader;

  /// No description provided for @onboardingHeaderSetup.
  ///
  /// In en, this message translates to:
  /// **'SETUP'**
  String get onboardingHeaderSetup;

  /// No description provided for @onboardingHintSending.
  ///
  /// In en, this message translates to:
  /// **'Sending...'**
  String get onboardingHintSending;

  /// No description provided for @onboardingHintAnswer.
  ///
  /// In en, this message translates to:
  /// **'Type your answer…'**
  String get onboardingHintAnswer;

  /// No description provided for @onboardingReadbackContinue.
  ///
  /// In en, this message translates to:
  /// **'LOOKS RIGHT — CONTINUE'**
  String get onboardingReadbackContinue;

  /// No description provided for @onboardingMeetYourTeam.
  ///
  /// In en, this message translates to:
  /// **'MEET YOUR TEAM'**
  String get onboardingMeetYourTeam;

  /// No description provided for @onboardingErrorTitle.
  ///
  /// In en, this message translates to:
  /// **'CAN\'\'T REACH THE BACKEND'**
  String get onboardingErrorTitle;

  /// No description provided for @onboardingErrorUnknown.
  ///
  /// In en, this message translates to:
  /// **'Unknown error'**
  String get onboardingErrorUnknown;

  /// No description provided for @onboardingTryAgain.
  ///
  /// In en, this message translates to:
  /// **'TRY AGAIN'**
  String get onboardingTryAgain;

  /// No description provided for @signInHeading.
  ///
  /// In en, this message translates to:
  /// **'SIGN IN'**
  String get signInHeading;

  /// No description provided for @signInIntro.
  ///
  /// In en, this message translates to:
  /// **'Sign in to keep your mandate, journal, and portfolio across devices. Until then, everything you build stays on this device.'**
  String get signInIntro;

  /// No description provided for @signInWithApple.
  ///
  /// In en, this message translates to:
  /// **'Sign in with Apple'**
  String get signInWithApple;

  /// No description provided for @signInWithEmail.
  ///
  /// In en, this message translates to:
  /// **'OR CONTINUE WITH EMAIL'**
  String get signInWithEmail;

  /// No description provided for @signInEmailHint.
  ///
  /// In en, this message translates to:
  /// **'you@example.com'**
  String get signInEmailHint;

  /// No description provided for @signInSendCode.
  ///
  /// In en, this message translates to:
  /// **'SEND CODE'**
  String get signInSendCode;

  /// No description provided for @signInResendCode.
  ///
  /// In en, this message translates to:
  /// **'RESEND CODE'**
  String get signInResendCode;

  /// No description provided for @signInCodeHint.
  ///
  /// In en, this message translates to:
  /// **'6-digit code'**
  String get signInCodeHint;

  /// No description provided for @signInVerify.
  ///
  /// In en, this message translates to:
  /// **'VERIFY & CLAIM'**
  String get signInVerify;

  /// Dev-mode debug code echo in the sign-in screen. {code} is the literal 6-digit code returned by the backend.
  ///
  /// In en, this message translates to:
  /// **'DEV mode — code: {code}'**
  String signInDevCode(String code);

  /// No description provided for @signInCodeSent.
  ///
  /// In en, this message translates to:
  /// **'Code sent. Check your email.'**
  String get signInCodeSent;

  /// No description provided for @signInCodeFailed.
  ///
  /// In en, this message translates to:
  /// **'Code did not verify. Try again.'**
  String get signInCodeFailed;

  /// No description provided for @signInAppleFailed.
  ///
  /// In en, this message translates to:
  /// **'Apple sign-in failed.'**
  String get signInAppleFailed;

  /// Confirmation card on the sign-in screen for already-claimed users. {handle} is the display handle.
  ///
  /// In en, this message translates to:
  /// **'Signed in as {handle}'**
  String signInSignedInAs(String handle);

  /// No description provided for @signInLegalFootnote.
  ///
  /// In en, this message translates to:
  /// **'AMI Trade is simulation-only. Nothing here is investment advice and no real trades are executed.'**
  String get signInLegalFootnote;

  /// No description provided for @oneOnOneAskAnything.
  ///
  /// In en, this message translates to:
  /// **'Ask me anything in my domain.\nType below to start.'**
  String get oneOnOneAskAnything;

  /// No description provided for @oneOnOneStreaming.
  ///
  /// In en, this message translates to:
  /// **'Streaming…'**
  String get oneOnOneStreaming;

  /// No description provided for @oneOnOneHint.
  ///
  /// In en, this message translates to:
  /// **'Ask anything…'**
  String get oneOnOneHint;

  /// No description provided for @oneOnOneCoachTooltip.
  ///
  /// In en, this message translates to:
  /// **'Coach this agent'**
  String get oneOnOneCoachTooltip;

  /// Coach Your Agent screen header. {agent} is the agent's display name in upper case.
  ///
  /// In en, this message translates to:
  /// **'COACH {agent}'**
  String coachHeading(String agent);

  /// No description provided for @coachNoOverlayYet.
  ///
  /// In en, this message translates to:
  /// **'No overlay yet — factory defaults'**
  String get coachNoOverlayYet;

  /// Header subtitle when an overlay is active. {version} is the integer version.
  ///
  /// In en, this message translates to:
  /// **'Overlay v{version} active'**
  String coachOverlayActive(int version);

  /// No description provided for @coachNoEditsLeft.
  ///
  /// In en, this message translates to:
  /// **'⚠️ No edits left — upgrade to keep coaching'**
  String get coachNoEditsLeft;

  /// Amber notice when only 1 edit is left. {count} is the number remaining (typically 1).
  ///
  /// In en, this message translates to:
  /// **'⚠️ {count} edit left at your tier'**
  String coachOneEditLeft(int count);

  /// No description provided for @coachVersionHistoryTooltip.
  ///
  /// In en, this message translates to:
  /// **'Version history'**
  String get coachVersionHistoryTooltip;

  /// Banner label above the active overlay summary. {version} is the integer version.
  ///
  /// In en, this message translates to:
  /// **'CURRENT OVERLAY — v{version}'**
  String coachCurrentOverlayLabel(int version);

  /// No description provided for @coachProtectedSafetyFloor.
  ///
  /// In en, this message translates to:
  /// **'PROTECTED — safety floor'**
  String get coachProtectedSafetyFloor;

  /// No description provided for @coachProtectedMandate.
  ///
  /// In en, this message translates to:
  /// **'PROTECTED — mandate rule'**
  String get coachProtectedMandate;

  /// No description provided for @coachEditLimitReached.
  ///
  /// In en, this message translates to:
  /// **'EDIT LIMIT REACHED'**
  String get coachEditLimitReached;

  /// No description provided for @coachRefused.
  ///
  /// In en, this message translates to:
  /// **'COACH REFUSED'**
  String get coachRefused;

  /// Snackbar after a coach proposal is accepted. {version} is the new overlay version; {summary} is the plain-English summary.
  ///
  /// In en, this message translates to:
  /// **'Saved as v{version} — {summary}'**
  String coachProposalSavedSnack(int version, String summary);

  /// Diff card title when an agent refuses a proposal. {agent} is the agent display name in upper case.
  ///
  /// In en, this message translates to:
  /// **'{agent} REFUSED'**
  String coachAgentRefused(String agent);

  /// Diff card title when an agent has drafted a proposal. {agent} is the agent display name in upper case.
  ///
  /// In en, this message translates to:
  /// **'{agent} — PROPOSAL'**
  String coachAgentProposal(String agent);

  /// No description provided for @coachPlainEnglish.
  ///
  /// In en, this message translates to:
  /// **'Plain English:'**
  String get coachPlainEnglish;

  /// No description provided for @coachOverlayAddition.
  ///
  /// In en, this message translates to:
  /// **'Overlay addition:'**
  String get coachOverlayAddition;

  /// No description provided for @coachAccept.
  ///
  /// In en, this message translates to:
  /// **'ACCEPT'**
  String get coachAccept;

  /// No description provided for @coachRefine.
  ///
  /// In en, this message translates to:
  /// **'REFINE'**
  String get coachRefine;

  /// No description provided for @coachReject.
  ///
  /// In en, this message translates to:
  /// **'REJECT'**
  String get coachReject;

  /// No description provided for @coachDismiss.
  ///
  /// In en, this message translates to:
  /// **'DISMISS'**
  String get coachDismiss;

  /// No description provided for @coachInputHint.
  ///
  /// In en, this message translates to:
  /// **'Tell me what to change…'**
  String get coachInputHint;

  /// No description provided for @coachDrafting.
  ///
  /// In en, this message translates to:
  /// **'DRAFTING…'**
  String get coachDrafting;

  /// No description provided for @coachProposeChange.
  ///
  /// In en, this message translates to:
  /// **'PROPOSE CHANGE'**
  String get coachProposeChange;

  /// Coach history screen title. {agent} is the agent's display name in upper case.
  ///
  /// In en, this message translates to:
  /// **'{agent} HISTORY'**
  String coachHistoryHeading(String agent);

  /// No description provided for @coachHistorySubtitle.
  ///
  /// In en, this message translates to:
  /// **'All saved coaching versions'**
  String get coachHistorySubtitle;

  /// Footer summary for unlimited-tier users. {count} is the edit count.
  ///
  /// In en, this message translates to:
  /// **'{count} edits made • unlimited at your tier'**
  String coachHistoryEditsUnlimited(int count);

  /// Footer summary showing remaining edits. {count} edits made, {remaining} edits left.
  ///
  /// In en, this message translates to:
  /// **'{count} edits made • {remaining} remaining'**
  String coachHistoryEditsRemaining(int count, int remaining);

  /// No description provided for @coachHistoryEmpty.
  ///
  /// In en, this message translates to:
  /// **'No coaching history yet.\nGo back and propose your first change.'**
  String get coachHistoryEmpty;

  /// No description provided for @coachHistoryActiveBadge.
  ///
  /// In en, this message translates to:
  /// **'ACTIVE'**
  String get coachHistoryActiveBadge;

  /// Confirm dialog title. {version} is the target version.
  ///
  /// In en, this message translates to:
  /// **'Rollback to v{version}?'**
  String coachHistoryRollbackTitle(int version);

  /// Confirm dialog body. {version} is the target version.
  ///
  /// In en, this message translates to:
  /// **'Your agent will start using v{version} immediately. The newer versions stay in history.'**
  String coachHistoryRollbackBody(int version);

  /// No description provided for @coachHistoryRollback.
  ///
  /// In en, this message translates to:
  /// **'ROLLBACK'**
  String get coachHistoryRollback;

  /// No description provided for @coachHistoryRollbackToThis.
  ///
  /// In en, this message translates to:
  /// **'ROLLBACK TO THIS'**
  String get coachHistoryRollbackToThis;

  /// No description provided for @conveneHeading.
  ///
  /// In en, this message translates to:
  /// **'CONVENE THE ROOM'**
  String get conveneHeading;

  /// No description provided for @convenePickTicker.
  ///
  /// In en, this message translates to:
  /// **'Pick a ticker. Your full team runs the debate.'**
  String get convenePickTicker;

  /// No description provided for @conveneTickerHint.
  ///
  /// In en, this message translates to:
  /// **'e.g. NVDA'**
  String get conveneTickerHint;

  /// No description provided for @conveneOrPickOne.
  ///
  /// In en, this message translates to:
  /// **'OR PICK ONE'**
  String get conveneOrPickOne;

  /// No description provided for @conveneCta.
  ///
  /// In en, this message translates to:
  /// **'CONVENE'**
  String get conveneCta;

  /// No description provided for @roomHeadingPrefix.
  ///
  /// In en, this message translates to:
  /// **'CONVENE ›'**
  String get roomHeadingPrefix;

  /// No description provided for @roomStandingBy.
  ///
  /// In en, this message translates to:
  /// **'standing by'**
  String get roomStandingBy;

  /// No description provided for @roomDeliberating.
  ///
  /// In en, this message translates to:
  /// **'Team deliberating…'**
  String get roomDeliberating;

  /// No description provided for @roomEndedNoVerdict.
  ///
  /// In en, this message translates to:
  /// **'Room ended without a verdict.'**
  String get roomEndedNoVerdict;

  /// No description provided for @roomSavedToJournal.
  ///
  /// In en, this message translates to:
  /// **'Saved to Journal'**
  String get roomSavedToJournal;

  /// No description provided for @roomClose.
  ///
  /// In en, this message translates to:
  /// **'CLOSE'**
  String get roomClose;

  /// No description provided for @roomSafetyFloorPill.
  ///
  /// In en, this message translates to:
  /// **'SAFETY FLOOR'**
  String get roomSafetyFloorPill;

  /// Verdict card title. {action} is the action string (e.g. APPROVE, REJECT).
  ///
  /// In en, this message translates to:
  /// **'VERDICT — {action}'**
  String roomVerdictHeading(String action);

  /// No description provided for @roomMetricTicker.
  ///
  /// In en, this message translates to:
  /// **'TICKER'**
  String get roomMetricTicker;

  /// No description provided for @roomMetricSize.
  ///
  /// In en, this message translates to:
  /// **'SIZE'**
  String get roomMetricSize;

  /// No description provided for @roomMetricEntry.
  ///
  /// In en, this message translates to:
  /// **'ENTRY'**
  String get roomMetricEntry;

  /// No description provided for @roomMetricStop.
  ///
  /// In en, this message translates to:
  /// **'STOP'**
  String get roomMetricStop;

  /// No description provided for @roomMetricTarget.
  ///
  /// In en, this message translates to:
  /// **'TARGET'**
  String get roomMetricTarget;

  /// No description provided for @roomMetricHorizon.
  ///
  /// In en, this message translates to:
  /// **'HORIZON'**
  String get roomMetricHorizon;

  /// Horizon metric in days. {days} is the integer day count.
  ///
  /// In en, this message translates to:
  /// **'{days} days'**
  String roomHorizonDays(int days);

  /// No description provided for @roomViolations.
  ///
  /// In en, this message translates to:
  /// **'VIOLATIONS'**
  String get roomViolations;

  /// No description provided for @roomOpenTradeTicket.
  ///
  /// In en, this message translates to:
  /// **'OPEN TRADE TICKET'**
  String get roomOpenTradeTicket;

  /// No description provided for @roomTradeTicketCaption.
  ///
  /// In en, this message translates to:
  /// **'Submits with the verdict\'\'s size / stop / target. PM safety floor reruns.'**
  String get roomTradeTicketCaption;

  /// No description provided for @tradeTicketHeading.
  ///
  /// In en, this message translates to:
  /// **'NEW TRADE'**
  String get tradeTicketHeading;

  /// No description provided for @tradeTicketSafetyFloorBlocked.
  ///
  /// In en, this message translates to:
  /// **'SAFETY FLOOR — TRADE BLOCKED'**
  String get tradeTicketSafetyFloorBlocked;

  /// No description provided for @tradeTicketChangeMandate.
  ///
  /// In en, this message translates to:
  /// **'Change what is enforced via Settings → My Mandate.'**
  String get tradeTicketChangeMandate;

  /// No description provided for @tradeTicketLabelTicker.
  ///
  /// In en, this message translates to:
  /// **'TICKER'**
  String get tradeTicketLabelTicker;

  /// No description provided for @tradeTicketLabelQuantity.
  ///
  /// In en, this message translates to:
  /// **'QUANTITY'**
  String get tradeTicketLabelQuantity;

  /// No description provided for @tradeTicketLabelStop.
  ///
  /// In en, this message translates to:
  /// **'STOP'**
  String get tradeTicketLabelStop;

  /// No description provided for @tradeTicketLabelTarget.
  ///
  /// In en, this message translates to:
  /// **'TARGET'**
  String get tradeTicketLabelTarget;

  /// No description provided for @tradeTicketLabelHorizon.
  ///
  /// In en, this message translates to:
  /// **'HORIZON (DAYS)'**
  String get tradeTicketLabelHorizon;

  /// No description provided for @tradeTicketHintTicker.
  ///
  /// In en, this message translates to:
  /// **'NVDA'**
  String get tradeTicketHintTicker;

  /// No description provided for @tradeTicketHintQty.
  ///
  /// In en, this message translates to:
  /// **'10'**
  String get tradeTicketHintQty;

  /// No description provided for @tradeTicketHintOptional.
  ///
  /// In en, this message translates to:
  /// **'optional'**
  String get tradeTicketHintOptional;

  /// No description provided for @tradeTicketSubmitting.
  ///
  /// In en, this message translates to:
  /// **'SUBMITTING…'**
  String get tradeTicketSubmitting;

  /// No description provided for @tradeTicketSubmit.
  ///
  /// In en, this message translates to:
  /// **'SUBMIT TRADE'**
  String get tradeTicketSubmit;

  /// No description provided for @tradeTicketFooterNote.
  ///
  /// In en, this message translates to:
  /// **'PM safety floor runs on submit — compliance flags + drawdown + single-name cap.'**
  String get tradeTicketFooterNote;

  /// No description provided for @tradeTicketSideBuy.
  ///
  /// In en, this message translates to:
  /// **'BUY'**
  String get tradeTicketSideBuy;

  /// No description provided for @tradeTicketSideSell.
  ///
  /// In en, this message translates to:
  /// **'SELL'**
  String get tradeTicketSideSell;

  /// Snackbar after a trade fills. {side}=BUY/SELL, {qty}=quantity, {ticker}=symbol, {price}=entry price formatted to 2dp.
  ///
  /// In en, this message translates to:
  /// **'Filled: {side} {qty} {ticker} @ \\\${price}'**
  String tradeTicketFilled(
      String side, String qty, String ticker, String price);

  /// Label above a Concierge chat bubble in the conversation surfaces (Onboarding, 1-on-1).
  ///
  /// In en, this message translates to:
  /// **'CONCIERGE'**
  String get chatBubbleConcierge;
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
