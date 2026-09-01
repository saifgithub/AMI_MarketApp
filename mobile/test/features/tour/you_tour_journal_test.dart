/// CR190 — the app tour must cover the Journal, framed as a learning tool.
///
/// The Journal's own 3-step tour only fires once the user taps into the
/// JOURNAL segment — a learner who never taps it was never told it exists.
/// Saiful's exact ask (bug a345042c): "Tour necessary for the journal i feel,
/// journal important for the learners and to avoid seeming like signal
/// generators." So two things are under test here, and the second is the one
/// that pays for the file:
///
///   1. The YOU tour has a step that targets the JOURNAL segment, in the
///      segment bar's left-to-right order, and inserting it did not break the
///      NEXT/DONE flow (only the last step may end the tour).
///   2. The step's copy carries the *learning* frame — reasoning recorded,
///      outcomes reviewed — and names the anti-signal-feed line explicitly.
///      That framing is the CR, not a nicety; a copy edit that drops it
///      should fail here, on purpose.
library;

import 'package:ami_trade/features/tour/ami_tour_overlay.dart';
import 'package:ami_trade/features/tour/tour_card.dart';
import 'package:ami_trade/features/tour/you_tour.dart';
import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// The content builders only use the controller for button taps, which these
/// tests never perform — a no-op satisfies the interface.
class _NoopController implements AmiTourController {
  @override
  void next() {}
  @override
  void skip() {}
}

void main() {
  final segmentBarKey = GlobalKey();
  final settingsKey = GlobalKey();
  final journalKey = GlobalKey();
  final insightsKey = GlobalKey();

  /// Pumps a localized shell and returns the AppLocalizations plus the
  /// context the step builders need.
  Future<(AppLocalizations, BuildContext)> pumpShell(WidgetTester t) async {
    late BuildContext ctx;
    await t.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Builder(builder: (c) {
        ctx = c;
        return const SizedBox.shrink();
      }),
    ));
    return (AppLocalizations.of(ctx), ctx);
  }

  List<AmiTourStep> targets(AppLocalizations l) => buildYouTargets(
        l: l,
        segmentBarKey: segmentBarKey,
        settingsSegmentKey: settingsKey,
        journalSegmentKey: journalKey,
        insightsSegmentKey: insightsKey,
      );

  Future<TourCard> renderStep(
      WidgetTester t, BuildContext ctx, AmiTourStep step) async {
    final built = step.builder(ctx, _NoopController());
    await t.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: built),
    ));
    return t.widget<TourCard>(find.byType(TourCard));
  }

  testWidgets('the YOU tour covers the Journal, in segment-bar order',
      (t) async {
    final (l, _) = await pumpShell(t);
    final steps = targets(l);

    expect(steps.map((s) => s.identify).toList(),
        ['you_segments', 'you_settings', 'you_journal', 'you_insights'],
        reason: 'CR190 — a learner who never taps the JOURNAL segment is '
            'only ever told about it here; the step order is the bar order');

    final journal = steps.firstWhere((s) => s.identify == 'you_journal');
    expect(journal.target, same(journalKey),
        reason: 'the step must spotlight the JOURNAL segment cell itself');
  });

  testWidgets('the Journal step teaches the learning frame, not a signal feed',
      (t) async {
    final (l, ctx) = await pumpShell(t);
    final journal =
        targets(l).firstWhere((s) => s.identify == 'you_journal');

    final card = await renderStep(t, ctx, journal);
    expect(card.title, l.tourYouJournalTitle);
    expect(card.body, l.tourYouJournalBody,
        reason: 'the step must render the CR190 copy, not a neighbour key');
    expect(find.text(l.tourYouJournalTitle), findsOneWidget);
    expect(find.text(l.tourYouJournalBody), findsOneWidget);

    // The frame is the deliverable. Reasoning + outcome = learning tool;
    // "signals" named so the copy can *deny* it. A rewrite that keeps the
    // frame passes; one that drops it must not.
    final body = l.tourYouJournalBody.toLowerCase();
    expect(body, contains('reasoning'));
    expect(body, contains('signal'));
  });

  testWidgets('inserting the step kept the NEXT/DONE flow intact', (t) async {
    final (l, ctx) = await pumpShell(t);
    final steps = targets(l);

    for (final step in steps) {
      final card = await renderStep(t, ctx, step);
      expect(card.nextLabel, step == steps.last ? l.tourDone : l.tourNext,
          reason: '${step.identify}: only the final step may end the tour — '
              'a mid-tour DONE strands the steps behind it');
    }
  });
}
