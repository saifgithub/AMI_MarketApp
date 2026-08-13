/// CR133 §4 — the `YOU` tab.
///
/// The two things worth testing here are not "does it render". They are:
///
///   1. **§4.2 — a segment switch with unsaved mandate edits must prompt.**
///      The mandate has an explicit Save, so a silent switch is data loss, and
///      the whole reason the mandate is allowed to live in a segment at all is
///      that this guard holds. It is the CR040 case: it must fail visibly.
///   2. **The header is `YOU`'s, and it renders the active segment's controls.**
///      Settings' Save moved out of Settings' own header, so a build where the
///      pane thinks it is dirty and the header does not is a Save button that
///      silently is not there — invisible until someone loses an edit.
library;

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:ami_trade/features/tour/tour_providers.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/journal/journal_screen.dart';
import 'package:ami_trade/screens/settings/settings_screen.dart';
import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:ami_trade/screens/you/insights_providers.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
import 'package:ami_trade/screens/you/you_screen.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/widgets/hex/ami_segment_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref, MandateState fixed) {
    state = fixed;
  }
}

class _FixedJournalNotifier extends JournalNotifier {
  _FixedJournalNotifier(super.ref, JournalState fixed) {
    state = fixed;
  }
}

UserMandate _mandate() => const UserMandate(
      userId: 'u1',
      version: 7,
      displayName: 'Trader',
      locale: 'en',
      timezone: 'UTC',
      primaryGoal: 'long_term_wealth',
      horizon: 'long',
      path: 'long_horizon',
      riskScore: 3,
      riskComponents: RiskComponents(
        drawdownResponse: 3,
        regretAsymmetry: 0,
        concentrationTolerance: 3,
      ),
      maxDrawdownPct: 30,
      learningStyle: 'quick',
      compliance: ComplianceFlags(),
      plan: 'trial_trader',
      creditBalance: 75,
    );

Future<ProviderContainer> _pump(WidgetTester t) async {
  t.view.physicalSize = const Size(390, 844);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);

  final container = ProviderContainer(overrides: [
    mandateNotifierProvider.overrideWith(
        (ref) => _FixedMandateNotifier(ref, MandateState(mandate: _mandate()))),
    journalNotifierProvider.overrideWith(
        (ref) => _FixedJournalNotifier(ref, const JournalState())),
    // The INSIGHTS pane is built (not painted) by the IndexedStack, so without
    // this its fetch fires on every pump and leaves a pending timer.
    insightsProvider.overrideWith((ref) async => const InsightsData(entryCount: 0)),
  ]);
  addTearDown(container.dispose);

  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: YouScreen(),
    ),
  ));
  await t.pump();
  return container;
}

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  testWidgets('opens on SETTINGS, with JOURNAL alongside it', (t) async {
    final container = await _pump(t);
    await _settle(t);

    expect(container.read(youSegmentProvider), YouSegment.settings);
    final bar = t.widget<AmiSegmentBar>(find.byType(AmiSegmentBar));
    expect(bar.segments.map((s) => s.label).toList(),
        ['SETTINGS', 'JOURNAL', 'INSIGHTS']);
    expect(bar.selected, 0);
  });

  testWidgets('both panes stay alive across a switch', (t) async {
    // An IndexedStack, not a swap: switching back must not reload the journal
    // or drop a half-finished mandate edit. `skipOffstage: false` because
    // that is exactly the property under test — IndexedStack marks the
    // unselected child offstage while keeping it mounted, so a finder that
    // skips offstage widgets cannot tell "kept alive" from "rebuilt on
    // switch", which is the whole question.
    await _pump(t);
    await _settle(t);
    expect(find.byType(SettingsScreen, skipOffstage: false), findsOneWidget);
    expect(find.byType(JournalScreen, skipOffstage: false), findsOneWidget);
  });

  testWidgets('a clean switch does not prompt', (t) async {
    final container = await _pump(t);
    await _settle(t);

    await t.tap(find.text('JOURNAL'));
    await _settle(t);

    expect(find.byType(AlertDialog), findsNothing);
    expect(container.read(youSegmentProvider), YouSegment.journal);
  });

  testWidgets('§4.2 — leaving SETTINGS with unsaved edits prompts, and '
      '"keep editing" leaves you where you were', (t) async {
    final container = await _pump(t);
    await _settle(t);
    container.read(settingsHeaderProvider.notifier).state =
        const SettingsHeaderState(version: 7, dirty: true);
    await _settle(t);

    await t.tap(find.text('JOURNAL'));
    await _settle(t);

    expect(find.byType(AlertDialog), findsOneWidget,
        reason: 'CR040 — a switch that silently discards a mandate edit is the '
            'failure this guard exists for');
    await t.tap(find.text('keep editing'));
    await _settle(t);

    expect(container.read(youSegmentProvider), YouSegment.settings,
        reason: 'declining the prompt must not switch anyway');
  });

  testWidgets('§4.2 — "discard changes" does switch', (t) async {
    final container = await _pump(t);
    await _settle(t);
    container.read(settingsHeaderProvider.notifier).state =
        const SettingsHeaderState(version: 7, dirty: true);
    await _settle(t);

    await t.tap(find.text('JOURNAL'));
    await _settle(t);
    await t.tap(find.text('discard changes'));
    await _settle(t);

    expect(container.read(youSegmentProvider), YouSegment.journal);
  });

  testWidgets('the dirty marker appears exactly where the switch is made',
      (t) async {
    final container = await _pump(t);
    await _settle(t);

    AmiSegmentBar bar() =>
        t.widget<AmiSegmentBar>(find.byType(AmiSegmentBar));
    expect(bar().segments.first.trailing, isNull);

    container.read(settingsHeaderProvider.notifier).state =
        const SettingsHeaderState(version: 7, dirty: true);
    await _settle(t);
    expect(bar().segments.first.trailing, isNotNull);
    expect(bar().segments[1].trailing, isNull,
        reason: 'only SETTINGS holds an unsaved edit');
  });

  group('CR133 §3 — the Journal\'s tour keeps a trigger', () {
    // It used to fire on `activeTabProvider == journal`. The Journal is no
    // longer a tab, and nothing would have failed: the tour would simply never
    // have run again, silently, forever. Both halves are required — `YOU`
    // keeps its panes alive in an IndexedStack, so `JournalScreen.build` runs
    // whether or not its segment is showing, and watching the segment alone
    // would fire it while the user was on another tab entirely.
    ProviderContainer container() {
      final c = ProviderContainer();
      addTearDown(c.dispose);
      return c;
    }

    test('false on the wrong tab, even with the right segment', () {
      final c = container();
      c.read(youSegmentProvider.notifier).state = YouSegment.journal;
      expect(c.read(activeTabProvider), AmiTab.floor);
      expect(c.read(journalVisibleProvider), isFalse);
    });

    test('false on the right tab with the wrong segment', () {
      final c = container();
      c.read(activeTabProvider.notifier).state = AmiTab.you;
      expect(c.read(journalVisibleProvider), isFalse);
    });

    test('true only when both hold', () {
      final c = container();
      c.read(activeTabProvider.notifier).state = AmiTab.you;
      c.read(youSegmentProvider.notifier).state = YouSegment.journal;
      expect(c.read(journalVisibleProvider), isTrue);
    });
  });

  testWidgets('the header carries the active segment\'s controls', (t) async {
    final container = await _pump(t);
    await _settle(t);

    // SETTINGS, clean: the mandate version, no Save.
    expect(find.textContaining('7'), findsWidgets);
    expect(find.text('SAVE'), findsNothing);

    // SETTINGS, dirty: Save appears. Settings' own header is gone when
    // embedded, so if this does not render there is no Save button at all.
    container.read(settingsHeaderProvider.notifier).state =
        const SettingsHeaderState(version: 7, dirty: true);
    await _settle(t);
    expect(find.text('SAVE'), findsOneWidget);

    // JOURNAL: the trash door, and no Save for a pane that has nothing to save.
    container.read(settingsHeaderProvider.notifier).state =
        const SettingsHeaderState(version: 7);
    container.read(youSegmentProvider.notifier).state = YouSegment.journal;
    await _settle(t);
    expect(find.byIcon(Icons.delete_outline), findsOneWidget);
    expect(find.text('SAVE'), findsNothing);
  });
}
