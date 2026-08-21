/// CR172 §10 step 4 — the option ticket, driven by real wire payloads.
///
/// Every case here goes through `OptionProposal.fromJson`, not a hand-built
/// object, so what is proven is the path from a server payload to pixels.
/// A fixture-built proposal would prove the widget renders a Dart object,
/// which is not the thing that can go wrong.
///
/// Four obligations, one per group:
///
///   1. the card is a render of the payload, and a figure the server did not
///      send appears as an absence rather than a number;
///   2. both decision paths reach the caller;
///   3. the sell-to-open disclosure PRECEDES the confirm — the accept callback
///      is unreachable until it is acknowledged;
///   4. a refusal renders loudly, with the server's own sentence, and offers
///      no way to say yes.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/option_proposal.dart';
import 'package:ami_trade/widgets/sim/option_disclosure_dialog.dart';
import 'package:ami_trade/widgets/sim/option_proposal_ticket.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../models/option_proposal_test.dart'
    show bullCallSpreadPayload, halalAdvisory, nakedCallRefusal;

/// Everything the ticket rendered, flattened.
List<String> _texts(WidgetTester tester) => tester
    .widgetList<Text>(find.byType(Text))
    .map((t) => t.data ?? '')
    .toList();

bool _saw(WidgetTester tester, String needle) =>
    _texts(tester).any((s) => s.contains(needle));

Future<void> _pump(
  WidgetTester tester,
  OptionProposal proposal, {
  void Function(OptionProposal)? onAccept,
  void Function(OptionProposal)? onDecline,
}) async {
  // A tall surface, so every row and both buttons are laid out and hit-
  // testable at once. The default 800×600 test view scrolls the decision row
  // off the bottom, and a tap that silently misses would make "the accept
  // callback never fired" pass for the wrong reason.
  tester.view.physicalSize = const Size(1200, 3200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: OptionProposalTicket(
        proposal: proposal,
        onAccept: onAccept ?? (_) {},
        onDecline: onDecline ?? (_) {},
      ),
    ),
  ));
  await tester.pumpAndSettle();
}

Map<String, dynamic> _withCompliance(Map<String, dynamic> compliance) =>
    bullCallSpreadPayload()..['compliance'] = compliance;

void main() {
  group('renders from the server payload', () {
    testWidgets('the structure, its legs and its figures', (tester) async {
      await _pump(tester, OptionProposal.fromJson(bullCallSpreadPayload()));

      expect(_saw(tester, 'BULL CALL SPREAD · AAPL'), isTrue);
      // The long leg and the short leg, each with its own action word.
      expect(_saw(tester, 'BUY 1 × CALL \$250.00 · exp 2026-01-16'), isTrue);
      expect(_saw(tester, 'SELL 1 × CALL \$260.00 · exp 2026-01-16'), isTrue);
      expect(_saw(tester, 'premium \$9.40 per share'), isTrue);
      // Server figures, verbatim.
      expect(_saw(tester, '\$540.00'), isTrue, reason: 'net debit / max loss');
      expect(_saw(tester, '\$460.00'), isTrue, reason: 'max gain');
      expect(_saw(tester, '\$255.40'), isTrue, reason: 'break-even');
      expect(_saw(tester, '45'), isTrue, reason: 'days to expiry');
      expect(_saw(tester, '-0.0812'), isTrue, reason: 'net theta per day');
      expect(_saw(tester, 'NET DEBIT'), isTrue);
    });

    testWidgets('a credit structure is labelled CREDIT, not DEBIT',
        (tester) async {
      final j = bullCallSpreadPayload();
      (j['metrics'] as Map)['net_cost'] = -460.0;
      await _pump(tester, OptionProposal.fromJson(j));

      expect(_saw(tester, 'NET CREDIT'), isTrue);
      expect(_saw(tester, 'NET DEBIT'), isFalse);
      expect(_saw(tester, '−\$460.00'), isTrue);
    });

    testWidgets('a figure the server did not send reads "not computed"',
        (tester) async {
      final j = bullCallSpreadPayload();
      (j['metrics'] as Map)
        ..['max_loss'] = null
        ..['collateral_required'] = null;
      j['days_to_expiry'] = null;
      await _pump(tester, OptionProposal.fromJson(j));

      final rendered = _texts(tester);
      expect(rendered.where((s) => s.contains('not computed')).length, 3,
          reason: 'max loss, collateral and days to expiry');
      // None of the three became a zero on the way to the screen. A real
      // \$0.00 collateral and an absent one must never render alike.
      expect(_saw(tester, '\$0.00'), isFalse);
    });

    testWidgets('an unbounded loss says UNBOUNDED, never a number',
        (tester) async {
      final j = bullCallSpreadPayload();
      (j['metrics'] as Map)
        ..['max_loss'] = null
        ..['unbounded_loss'] = true;
      await _pump(tester, OptionProposal.fromJson(j));

      expect(_saw(tester, 'UNBOUNDED'), isTrue);
    });

    testWidgets('a covered call says the shares bound it, not "not computed"',
        (tester) async {
      final j = bullCallSpreadPayload();
      (j['metrics'] as Map)
        ..['max_loss'] = null
        ..['covered_by_shares'] = true
        ..['shares_locked'] = 100.0;
      await _pump(tester, OptionProposal.fromJson(j));

      expect(_saw(tester, 'Bounded by shares you already hold'), isTrue);
      expect(_saw(tester, '100 shares locked'), isTrue);
    });

    testWidgets('absent greeks say so and estimate nothing in their place',
        (tester) async {
      final j = bullCallSpreadPayload()
        ..remove('net_greeks')
        ..['greeks_reason'] = 'no risk-free rate available';
      await _pump(tester, OptionProposal.fromJson(j));

      expect(_saw(tester, 'Greeks not computed — no risk-free rate available'),
          isTrue);
      expect(_saw(tester, 'DELTA'), isFalse);
    });

    testWidgets('an unpriceable structure offers nothing to accept',
        (tester) async {
      final j = bullCallSpreadPayload()..remove('metrics');
      await _pump(tester, OptionProposal.fromJson(j));

      expect(_saw(tester, 'AMI could not price this structure'), isTrue);
      expect(find.text('YES — OPEN IT'), findsNothing);
      expect(find.text('NO'), findsOneWidget);
    });
  });

  group('both decision paths', () {
    testWidgets('YES reaches the caller with the proposal', (tester) async {
      OptionProposal? accepted;
      var declines = 0;
      await _pump(
        tester,
        OptionProposal.fromJson(bullCallSpreadPayload()),
        onAccept: (p) => accepted = p,
        onDecline: (_) => declines++,
      );

      await tester.tap(find.text('YES — OPEN IT'));
      await tester.pumpAndSettle();

      expect(accepted, isNotNull);
      expect(accepted!.structureId, 2);
      expect(declines, 0);
    });

    testWidgets('NO reaches the caller and accepts nothing', (tester) async {
      var accepts = 0;
      OptionProposal? declined;
      await _pump(
        tester,
        OptionProposal.fromJson(bullCallSpreadPayload()),
        onAccept: (_) => accepts++,
        onDecline: (p) => declined = p,
      );

      await tester.tap(find.text('NO'));
      await tester.pumpAndSettle();

      expect(declined, isNotNull);
      expect(accepts, 0);
    });
  });

  group('the sell-to-open disclosure precedes the confirm', () {
    Map<String, dynamic> sellToOpenWithAdvisory() =>
        _withCompliance(<String, dynamic>{
          'passed': true,
          'violations': <String>[],
          'blocked_by': null,
          'not_evaluated': <String>[],
          'advisories': <String>[halalAdvisory],
        });

    testWidgets('YES opens the disclosure and does NOT accept', (tester) async {
      var accepts = 0;
      await _pump(
        tester,
        OptionProposal.fromJson(sellToOpenWithAdvisory()),
        onAccept: (_) => accepts++,
      );

      await tester.tap(find.text('YES — OPEN IT'));
      await tester.pumpAndSettle();

      expect(find.byType(OptionDisclosureDialog), findsOneWidget);
      expect(accepts, 0,
          reason: 'the trade must not be accepted behind the disclosure');
    });

    testWidgets('the dialog body is the SERVER sentence, verbatim',
        (tester) async {
      await _pump(tester, OptionProposal.fromJson(sellToOpenWithAdvisory()));
      await tester.tap(find.text('YES — OPEN IT'));
      await tester.pumpAndSettle();

      expect(
        find.descendant(
          of: find.byType(OptionDisclosureDialog),
          matching: find.text(halalAdvisory),
        ),
        findsOneWidget,
      );
    });

    testWidgets('acknowledging it lets the accept through', (tester) async {
      OptionProposal? accepted;
      await _pump(
        tester,
        OptionProposal.fromJson(sellToOpenWithAdvisory()),
        onAccept: (p) => accepted = p,
      );

      await tester.tap(find.text('YES — OPEN IT'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('I UNDERSTAND — CONTINUE'));
      await tester.pumpAndSettle();

      expect(accepted, isNotNull);
    });

    testWidgets('backing out of it accepts nothing', (tester) async {
      var accepts = 0;
      await _pump(
        tester,
        OptionProposal.fromJson(sellToOpenWithAdvisory()),
        onAccept: (_) => accepts++,
      );

      await tester.tap(find.text('YES — OPEN IT'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('GO BACK'));
      await tester.pumpAndSettle();

      expect(accepts, 0);
      expect(find.byType(OptionDisclosureDialog), findsNothing);
      // And the ticket is still there to answer.
      expect(find.text('YES — OPEN IT'), findsOneWidget);
    });

    testWidgets('the advisory is also on the card, before any tap',
        (tester) async {
      await _pump(tester, OptionProposal.fromJson(sellToOpenWithAdvisory()));

      expect(_saw(tester, 'BEFORE YOU DECIDE'), isTrue);
      expect(_saw(tester, halalAdvisory), isTrue);
    });

    testWidgets('no advisory ⇒ no dialog stands between YES and the caller',
        (tester) async {
      OptionProposal? accepted;
      await _pump(
        tester,
        OptionProposal.fromJson(bullCallSpreadPayload()),
        onAccept: (p) => accepted = p,
      );

      await tester.tap(find.text('YES — OPEN IT'));
      await tester.pumpAndSettle();

      expect(find.byType(OptionDisclosureDialog), findsNothing);
      expect(accepted, isNotNull);
    });
  });

  group('refusal states render loudly', () {
    testWidgets('the naked call: the server sentence, and no YES',
        (tester) async {
      final p = OptionProposal.fromJson(_withCompliance(<String, dynamic>{
        'passed': false,
        'violations': <String>[nakedCallRefusal],
        'blocked_by': 'compliance',
        'not_evaluated': <String>[],
        'advisories': <String>[],
      }));
      var accepts = 0;
      await _pump(tester, p, onAccept: (_) => accepts++);

      expect(_saw(tester, 'AMI WILL NOT OPEN THIS'), isTrue);
      expect(_saw(tester, nakedCallRefusal), isTrue);
      expect(_saw(tester, 'Refused by: COMPLIANCE'), isTrue);
      expect(find.text('YES — OPEN IT'), findsNothing);
      expect(accepts, 0);
      expect(find.text('NO'), findsOneWidget);
    });

    testWidgets('the long-only floor block', (tester) async {
      // DEF353 — the server's own sentence, kept verbatim so this fixture
      // cannot drift into asserting copy the floor no longer sends.
      const longOnly =
          'your mandate is long-only, and selling an option to open is a '
          'short position — including the short leg of a debit spread, where '
          'the premium received is still a sale. Long calls and long puts '
          'are not short positions and remain available.';
      await _pump(
        tester,
        OptionProposal.fromJson(_withCompliance(<String, dynamic>{
          'passed': false,
          'violations': <String>[longOnly],
          'blocked_by': 'long_only',
        })),
      );

      expect(_saw(tester, 'AMI WILL NOT OPEN THIS'), isTrue);
      expect(_saw(tester, longOnly), isTrue);
      expect(_saw(tester, 'Refused by: LONG_ONLY'), isTrue);
      expect(find.text('YES — OPEN IT'), findsNothing);
    });

    testWidgets('a refusal whose reasons did not arrive is never blank',
        (tester) async {
      await _pump(
        tester,
        OptionProposal.fromJson(_withCompliance(<String, dynamic>{
          'passed': false,
          'violations': <String>[],
          'blocked_by': null,
        })),
      );

      expect(_saw(tester, 'AMI WILL NOT OPEN THIS'), isTrue);
      expect(
        _saw(tester, 'AMI refused this structure and the reason did not reach'),
        isTrue,
        reason: 'CR040 — an error state is never an empty state',
      );
      expect(find.text('YES — OPEN IT'), findsNothing);
    });

    testWidgets('"could not check" is kept apart from "refused"',
        (tester) async {
      const gap = 'option structure could not be costed (no legs, mixed '
          'expiries, or a malformed leg) — the uncovered-call check could not '
          'run';
      await _pump(
        tester,
        OptionProposal.fromJson(_withCompliance(<String, dynamic>{
          'passed': true,
          'violations': <String>[],
          'not_evaluated': <String>[gap],
        })),
      );

      expect(_saw(tester, 'COULD NOT BE CHECKED'), isTrue);
      expect(_saw(tester, gap), isTrue);
      expect(_saw(tester, 'AMI WILL NOT OPEN THIS'), isFalse);
    });
  });
}
