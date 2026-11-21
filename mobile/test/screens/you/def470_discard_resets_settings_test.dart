// DEF470 — YOU's unsaved-changes dialog says edits "are discarded", but the
// SETTINGS pane lives in an IndexedStack, so choosing "discard changes" only
// switched segment: `_dirty` and the pending edits survived, the SAVE pip
// stayed and a later SAVE PATCHed the mandate with them. This drives the real
// pane: type a display name, leave via "discard changes", come back, and
// prove the edit is gone, the field shows the stored value, the pip/SAVE are
// gone and a save request sends nothing.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/you/insights_data.dart';
import 'package:ami_trade/screens/you/insights_providers.dart';
import 'package:ami_trade/screens/you/you_providers.dart';
import 'package:ami_trade/screens/you/you_screen.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

final List<Map<String, dynamic>> _patches = [];

class _RecordingMandateNotifier extends MandateNotifier {
  _RecordingMandateNotifier(super.ref, MandateState fixed) {
    state = fixed;
  }

  @override
  Future<bool> patch(Map<String, dynamic> updates) async {
    _patches.add(updates);
    return true;
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

Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 10; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  setUp(_patches.clear);

  testWidgets('"discard changes" really drops the pending settings edits',
      (t) async {
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    final container = ProviderContainer(overrides: [
      mandateNotifierProvider.overrideWith((ref) =>
          _RecordingMandateNotifier(ref, MandateState(mandate: _mandate()))),
      journalNotifierProvider.overrideWith(
          (ref) => _FixedJournalNotifier(ref, const JournalState())),
      insightsProvider
          .overrideWith((ref) async => const InsightsData(entryCount: 0)),
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
    await _settle(t);

    final field = find.byKey(const Key('displayNameField'));
    await t.scrollUntilVisible(field, 300,
        scrollable: find.byType(Scrollable).first);
    await t.enterText(field, 'Edited Name');
    await _settle(t);
    expect(container.read(settingsHeaderProvider).dirty, isTrue);
    expect(find.text('SAVE'), findsOneWidget);

    // Leave SETTINGS and choose "discard changes".
    await t.tap(find.text('JOURNAL'));
    await _settle(t);
    await t.tap(find.text('discard changes'));
    await _settle(t);
    expect(container.read(youSegmentProvider), YouSegment.journal);

    // The pane is still mounted (IndexedStack) — its pending state must be
    // gone, not merely hidden.
    expect(container.read(settingsHeaderProvider).dirty, isFalse,
        reason: 'the pane still thinks it is dirty after "discard"');

    await t.tap(find.text('SETTINGS'));
    await _settle(t);
    expect(find.text('SAVE'), findsNothing);

    await t.scrollUntilVisible(field, 300,
        scrollable: find.byType(Scrollable).first);
    final shown = t.widget<TextField>(field);
    expect(shown.controller!.text, 'Trader',
        reason: 'the field must show the stored value, not the discarded edit');

    // A later save request must send nothing.
    container.read(settingsSaveRequestProvider.notifier).state++;
    await _settle(t);
    expect(_patches, isEmpty,
        reason: 'a later SAVE must not PATCH the discarded edit');
  });
}
