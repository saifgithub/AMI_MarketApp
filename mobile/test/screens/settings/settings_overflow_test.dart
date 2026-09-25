// DEF435 — the Settings pane overflows at 1.3x text scale.
//
// Found by the DEF427 round-2 worker (journal_empty_state_overflow_test.dart)
// while pumping the REAL `YouScreen`: `IndexedStack` lays out every pane on
// every frame regardless of which is selected, so the Settings pane's
// pre-existing overflow fired even though the test was scoped to the Journal
// segment. That file drains it with `tester.takeException()` right after the
// initial settle specifically so DEF427's own assertions stay about the
// Journal — see its comment at the `_pumpEmbeddedJournal` helper. The DEF
// itself names two sites: `_RiskSlider`/`_DrawdownPicker` (settings_screen.dart
// ~577/~635).
//
// Root cause (the ~577/~635 sites, and the shape it recurs in): a label/value
// pair rendered as `Row(children: [Text(label), const Spacer(), Text(value)])`.
// `Spacer()` only redistributes LEFTOVER space — it does not shrink the
// `Text` siblings that claim it — so once the combined intrinsic width grows
// past what the Row has left (a 1.3x text scale is enough on a narrow
// phone), the Row overflows instead of either side wrapping or eliding.
//
// Scrolling this pane's OWN full length at 1.3x (this file's whole point —
// the DEF's two named sites sit in the always-visible first section, but
// nothing upstream had ever exercised the rest of the pane at this scale)
// turned up the SAME class recurring three more times further down: the
// enum-choice rows the Profile section uses for Primary Goal / Horizon /
// Path / Learning Style (`MandateChoiceRow`, profile_fields_section.dart —
// its own comment calls it "the enum generalisation of `_DrawdownPicker`",
// i.e. copy-pasted from the exact pattern being fixed here), the native/
// English language-name pair (`_LanguageRow`), and a label with an
// unconstrained value (`_ReadOnlyRow`, e.g. "Guest (anonymous)" for account
// status). All four are fixed alongside the DEF's two named sites, plus
// defensive hardening on `_TimezoneRow`'s dropdown (its longest IANA zone
// strings are a similar risk, though not one this file's matrix actually
// triggered).
//
// Fix: `Expanded`/`Flexible` + `overflow: TextOverflow.ellipsis` on whichever
// side can safely give way, at each site — never a raw fixed-width `Text`
// competing against another for the same Row.
//
// This file pumps the real `YouScreen` (`AmiScreenHeader` + `AmiSegmentBar` +
// the embedded `SettingsScreen`, exactly the parent chain from CR133 §4 —
// mirrors `_pumpEmbeddedJournal`'s own justification) on the SETTINGS
// segment, the default, across the same size/scale matrix DEF427 used, then
// drags the pane's `ListView` all the way to its end so every section (not
// just the first screenful) has been laid out at least once, and asserts no
// render exception was thrown anywhere along the way.
//
// The Wallet & Plan `AdSlot` (`ads_models.dart`) is a sibling several
// sections down this same `ListView`. It is deliberately NOT asserted on
// here — unlike DEF427's journal ad, which sits immediately below an
// always-visible empty state, this one only resolves once scrolled into a
// `ListView`'s near-visible range, and how far a fixed drag gets it there
// varies with the row heights a 1.3x scale itself produces — asserting on it
// would make this file's pass/fail track ad-fill timing instead of the
// overflow DEF435 is actually about. The ads service is still overridden to
// an always-fill fake purely so the slot's own async gate resolves quickly
// and quietly rather than leaving a pending timer.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:ami_trade/screens/you/insights_providers.dart';
import 'package:ami_trade/screens/you/you_screen.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/ads/ads_service.dart';
import 'package:ami_trade/state/ads_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _ScriptedJournalNotifier extends JournalNotifier {
  _ScriptedJournalNotifier(super.ref) {
    state = const JournalState(entries: [], retentionLoaded: true);
  }

  @override
  Future<void> refresh({JournalEntryType? filterType, String? q}) async {}
}

class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref) {
    state = MandateState(
      mandate: UserMandate(
        userId: 'u1',
        version: 1,
        displayName: 'Trader',
        locale: 'en',
        timezone: 'America/Los_Angeles',
        primaryGoal: 'long_term_wealth',
        horizon: 'long',
        path: 'long_horizon',
        riskScore: 3,
        riskComponents: const RiskComponents(
          drawdownResponse: 3,
          regretAsymmetry: 0,
          concentrationTolerance: 3,
        ),
        maxDrawdownPct: 30,
        learningStyle: 'quick',
        compliance: const ComplianceFlags(),
        // floor_pass — the one plan the ad gate serves (ads_providers.dart's
        // `plansWithAds`), same as journal_empty_state_overflow_test.dart.
        plan: 'floor_pass',
        creditBalance: 0,
      ),
    );
  }

  @override
  Future<void> refresh() async {}
}

/// Always-fill network fake (mirrors `ad_slot_test.dart` and
/// `journal_empty_state_overflow_test.dart`), so the Wallet & Plan `AdSlot`
/// resolves quickly and deterministically rather than racing the real house
/// inventory service or its frequency caps and leaving a pending timer.
class _AlwaysFillAdsService implements AdsService {
  @override
  String get network => 'always-fill-fake';

  @override
  Future<AdFill?> requestFill(AdPlacement placement, HouseAdSignals signals,
          {int widthDp = 0}) async =>
      const HouseAdFill(HouseAdCreative(
          slot: HouseAdSlot.genericTrader,
          targetTier: HouseAdTargetTier.trader));
}

/// Pumps the REAL `YouScreen` — `AmiScreenHeader` + `AmiSegmentBar` + the
/// embedded `SettingsScreen`, exactly the parent chain Settings lives in
/// (CR133 §4) — pinned to [size]/[textScale]. SETTINGS is `YouSegment.settings`
/// (index 0), the provider's default, so no segment switch is needed. Settles
/// with real elapsed time, the same discipline `_pumpEmbeddedJournal` uses
/// and for the same reason (`AdSlot` resolves via `scheduleMicrotask` +
/// `await gate.request(...)`).
Future<ProviderContainer> _pumpEmbeddedSettings(
  WidgetTester tester, {
  required Size size,
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({});

  final container = ProviderContainer(overrides: [
    journalNotifierProvider.overrideWith((ref) => _ScriptedJournalNotifier(ref)),
    mandateNotifierProvider.overrideWith((ref) => _FixedMandateNotifier(ref)),
    adsServiceProvider.overrideWithValue(_AlwaysFillAdsService()),
    // The INSIGHTS pane is built (not painted) by YouScreen's IndexedStack,
    // so without this its fetch fires on every pump and leaves a pending
    // timer (same reason `you_screen_test.dart` overrides it).
    insightsProvider
        .overrideWith((ref) async => const InsightsData(entryCount: 0)),
  ]);
  addTearDown(container.dispose);

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MediaQuery(
        data: MediaQueryData(
          size: size,
          textScaler: TextScaler.linear(textScale),
        ),
        child: const MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: YouScreen(),
        ),
      ),
    ),
  );
  // Real elapsed time, not a zero-duration `pump()`.
  for (var i = 0; i < 10; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
  return container;
}

/// Drags the Settings `ListView` to its end in fixed steps, so every
/// section — not just the first screenful — is laid out at least once
/// before the test asserts on exceptions. A fixed number of large steps
/// comfortably clears Settings' ~13 sections at every size/scale this file
/// covers; `dragUntilVisible` isn't used because there's no single target
/// widget known to exist at every size (the ad may or may not fill in time,
/// which this file deliberately does not assert on).
Future<void> _scrollThroughEntirePane(WidgetTester tester) async {
  final scrollable = find.byType(Scrollable).first;
  for (var i = 0; i < 12; i++) {
    await tester.drag(scrollable, const Offset(0, -500));
    await tester.pump(const Duration(milliseconds: 50));
  }
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  group('DEF435 — Settings pane does not overflow', () {
    // Same size matrix DEF427 used: 320/375/430dp phones, the iPhone 17's own
    // simulator size, and one landscape phone.
    const sizes = <String, Size>{
      '320dp (small phone)': Size(320, 690),
      '375dp (iPhone baseline)': Size(375, 812),
      '430dp (large phone)': Size(430, 932),
      'iPhone 17 (iOS Simulator)': Size(393, 852),
      'landscape phone/844x390': Size(844, 390),
    };

    for (final entry in sizes.entries) {
      for (final scale in [1.0, 1.3]) {
        testWidgets('no overflow at ${entry.key}, scale $scale',
            (tester) async {
          await _pumpEmbeddedSettings(tester,
              size: entry.value, textScale: scale);
          // The two rows the defect names sit in the first section, visible
          // without scrolling — both must be present and unclipped.
          expect(find.text('Risk score'), findsOneWidget,
              reason: '${entry.key} @ $scale');
          expect(find.text('Max drawdown'), findsOneWidget,
              reason: '${entry.key} @ $scale');
          expect(tester.takeException(), isNull,
              reason: '${entry.key} @ $scale (initial screenful)');
          // The rest of the pane must also lay out cleanly, not just what's
          // visible before any scrolling — this is how the three additional
          // overflow sites (see the file header) were found: none of them
          // sit in the first screenful.
          await _scrollThroughEntirePane(tester);
          expect(tester.takeException(), isNull,
              reason: '${entry.key} @ $scale (after scrolling through)');
        });
      }
    }
  });
}
