/// DEF254 — the Portfolio's error state offers a retry when, and only when,
/// one could work.
///
/// Saiful, on a screenshot of a `receiveTimeout`: *"But why did we not retry?"*
/// The copy ended in *"Try again."* and there was nothing to tap — the user's
/// only recourse was to leave the tab and come back. `isRetryable` already knew
/// the answer (DEF164 extracted it so *"the copy and the retry affordance
/// cannot disagree"*) and `SimNotifier.refresh` threw that half away.
///
/// Two properties, and both matter:
///
///   * the **widget** half — a retryable failure renders a control, and a
///     rejected one renders the message alone (DEF151 in reverse: that defect
///     offered a retry over a 422 that could never succeed);
///   * the **source** half — every `friendlyError` in `sim_providers.dart`
///     states its retry decision in the same `copyWith` call. That is the
///     mechanical version of the rule two defects have now been filed against,
///     and it is what stops the next catch block from carrying a stale flag
///     from whichever error came before it.
///
/// The source assertion is deliberate, not laziness: the three write paths
/// (`submit`, `cancelRestingOrder`, `reset`) have no error surface of their own
/// on this screen, so a widget test cannot reach their decision at all — and
/// theirs is the decision with teeth, because `receiveTimeout` means the POST
/// *was* sent and a retry over it places a second order.
library;

import 'dart:io';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/journal.dart';
import 'package:ami_trade/screens/sim/portfolio_screen.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/journal_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:ami_trade/state/watchlist_providers.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FixedSimNotifier extends SimNotifier {
  _FixedSimNotifier(super.ref, SimState fixed) {
    state = fixed;
  }

  int refreshes = 0;

  @override
  Future<void> refresh() async {
    refreshes++;
  }
}

class _FixedWatchlistNotifier extends WatchlistNotifier {
  _FixedWatchlistNotifier(super.ref) {
    state = const WatchlistState();
  }

  @override
  Future<void> refresh() async {}
}

class _FixedJournalNotifier extends JournalNotifier {
  _FixedJournalNotifier(super.ref) {
    state = const JournalState();
  }

  @override
  Future<void> refresh({
    JournalEntryType? filterType,
    String plan = 'trial_trader',
    String? q,
  }) async {}
}

Future<_FixedSimNotifier> _pump(WidgetTester tester, SimState sim) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  late _FixedSimNotifier notifier;
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        simNotifierProvider.overrideWith((ref) {
          notifier = _FixedSimNotifier(ref, sim);
          return notifier;
        }),
        watchlistNotifierProvider
            .overrideWith((ref) => _FixedWatchlistNotifier(ref)),
        journalNotifierProvider
            .overrideWith((ref) => _FixedJournalNotifier(ref)),
        alpacaLinkedProvider
            .overrideWith((ref) async => false),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const PortfolioScreen(),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
  return notifier;
}

void main() {
  group('the affordance', () {
    testWidgets('a retryable failure renders a control that re-reads',
        (tester) async {
      final notifier = await _pump(
        tester,
        const SimState(
          error: "Couldn't load your portfolio — AMI took too long to "
              'answer. Try again.',
          errorRetryable: true,
        ),
      );

      final button = find.byType(HexButton);
      expect(button, findsOneWidget,
          reason: 'the sentence says "Try again" — something has to be '
              'tappable, which is the whole of DEF254');

      final before = notifier.refreshes;
      await tester.tap(button);
      await tester.pump();
      expect(notifier.refreshes, before + 1,
          reason: 'the control must actually re-read; a label that goes '
              'nowhere is the DEF151 shape');
    });

    testWidgets('a rejected failure renders the message and nothing to tap',
        (tester) async {
      await _pump(
        tester,
        const SimState(
          error: "Couldn't load your portfolio — that request wasn't accepted.",
          errorRetryable: false,
        ),
      );

      expect(find.textContaining("wasn't accepted"), findsOneWidget);
      expect(find.byType(HexButton), findsNothing,
          reason: 're-sending an identical rejected request fails '
              'identically — DEF151 shipped exactly that button');
    });

    test('clearing the error clears the affordance with it', () {
      const errored = SimState(error: 'boom', errorRetryable: true);
      expect(errored.copyWith(clearError: true).errorRetryable, isFalse,
          reason: 'a retry control outliving its error is a promise attached '
              'to nothing');
    });
  });

  group('the rule — copy and retryability are decided in one call', () {
    final source = File('lib/state/sim_providers.dart').readAsStringSync();

    /// Every `copyWith(...)` in the file that sets `error:` from
    /// `friendlyError`, as raw text, so the assertion below can look inside it.
    List<String> errorCalls() {
      final out = <String>[];
      for (final m in RegExp(r'state\.copyWith\(').allMatches(source)) {
        var depth = 0;
        var i = m.end - 1;
        for (; i < source.length; i++) {
          if (source[i] == '(') depth++;
          if (source[i] == ')') {
            depth--;
            if (depth == 0) break;
          }
        }
        final call = source.substring(m.start, i + 1);
        if (call.contains('friendlyError(')) out.add(call);
      }
      return out;
    }

    test('every friendlyError in SimNotifier states its retry decision', () {
      final calls = errorCalls();
      expect(calls, isNotEmpty,
          reason: 'the scraper found no error paths at all — it has drifted '
              'from the source it guards, which is worse than no guard');

      final silent = [
        for (final c in calls)
          if (!c.contains('errorRetryable:')) c.replaceAll(RegExp(r'\s+'), ' ')
      ];
      expect(silent, isEmpty,
          reason: 'a catch block that stores copy without deciding whether to '
              'offer a retry inherits whatever flag the previous error left '
              'behind. Decide it here, in the same call, even when the answer '
              'is a hard false (DEF254).');
    });

    test('the read path asks isRetryable and the write paths refuse', () {
      final calls = errorCalls();
      final reads = [for (final c in calls) if (c.contains('isRetryable(')) c];
      expect(reads, hasLength(1),
          reason: 'exactly one path — the portfolio read — may offer a retry. '
              'A timeout on submit/cancel/reset means the request WAS sent, '
              'and re-sending a mutation whose first attempt may have '
              'succeeded is a second order, not a recovery.');
      expect(reads.single, contains('load your portfolio'));
    });
  });
}
