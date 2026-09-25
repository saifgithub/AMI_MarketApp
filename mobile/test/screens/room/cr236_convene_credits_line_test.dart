/// CR236 — the Convene sheet shows the Room's cost and the user's balance
/// before they convene: "Room: 8 credits · you have 63 · resets 1 Oct".
///
/// Harness mirrors cr220_profile_fields_test.dart — the real `ConveneSheet`
/// with `MandateNotifier` overridden to a fixed state, no network. The sheet
/// itself never calls `DeviceUser`/`validateTicker` until a ticker is
/// actually submitted, so pumping it for a pure rendering assertion needs no
/// further stubbing.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/screens/room/convene_sheet.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FixedMandateNotifier extends MandateNotifier {
  _FixedMandateNotifier(super.ref, MandateState initial) {
    state = initial;
  }

  @override
  Future<void> refresh() async {}
}

UserMandate _mandate({int? creditBalance, int? roomCost, DateTime? creditsResetAt}) {
  return UserMandate.fromJson({
    'user_id': 'u1',
    'plan': 'trial_trader',
    if (creditBalance != null) 'credit_balance': creditBalance,
    if (roomCost != null) 'room_cost': roomCost,
    if (creditsResetAt != null)
      'credits_reset_at': creditsResetAt.toUtc().toIso8601String(),
  });
}

Future<void> _pumpSheet(
  WidgetTester tester, {
  required MandateState mandateState,
  Size size = const Size(390, 844),
  double textScale = 1.0,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        mandateNotifierProvider.overrideWith(
          (ref) => _FixedMandateNotifier(ref, mandateState),
        ),
      ],
      child: MediaQuery(
        data: MediaQueryData(
          size: size,
          textScaler: TextScaler.linear(textScale),
        ),
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => ConveneSheet.show(context),
                child: const Text('open'),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

void main() {
  group('CR236 — Convene sheet credits line', () {
    testWidgets('renders cost, balance, and reset date together', (tester) async {
      await _pumpSheet(
        tester,
        mandateState: MandateState(
          mandate: _mandate(
            creditBalance: 63,
            roomCost: 8,
            creditsResetAt: DateTime.utc(2026, 10, 1),
          ),
        ),
      );

      final l = AppLocalizations.of(
          tester.element(find.byType(ConveneSheet)));
      expect(
        find.text(l.creditsLineCostWithReset('8', '63', '1 Oct')),
        findsOneWidget,
      );
    });

    testWidgets('renders cost and balance with no reset clause when unknown',
        (tester) async {
      await _pumpSheet(
        tester,
        mandateState: MandateState(
          mandate: _mandate(creditBalance: 63, roomCost: 8),
        ),
      );

      final l = AppLocalizations.of(
          tester.element(find.byType(ConveneSheet)));
      expect(find.text(l.creditsLineCost('8', '63')), findsOneWidget);
    });

    testWidgets('says so plainly when the balance is below the cost',
        (tester) async {
      await _pumpSheet(
        tester,
        mandateState: MandateState(
          mandate: _mandate(creditBalance: 3, roomCost: 8),
        ),
      );

      final l = AppLocalizations.of(
          tester.element(find.byType(ConveneSheet)));
      expect(
        find.textContaining(l.creditsLineInsufficient),
        findsOneWidget,
      );
    });

    testWidgets('shows no number while the mandate has not loaded',
        (tester) async {
      await _pumpSheet(tester, mandateState: const MandateState());

      final l = AppLocalizations.of(
          tester.element(find.byType(ConveneSheet)));
      expect(find.text(l.creditsLineUnknown), findsOneWidget);
      // Never a guessed number in either credits-line shape.
      expect(find.textContaining('Room:'), findsNothing);
    });

    testWidgets('shows no number when balance came back null (DEF437 class)',
        (tester) async {
      await _pumpSheet(
        tester,
        mandateState: MandateState(mandate: _mandate(roomCost: 8)),
      );

      final l = AppLocalizations.of(
          tester.element(find.byType(ConveneSheet)));
      expect(find.text(l.creditsLineUnknown), findsOneWidget);
    });

    testWidgets(
        'the credits line adds no vertical overflow at 320dp / 1.3x text scale',
        (tester) async {
      // NOTE: the sheet's pre-existing heading Row ("CONVENE THE ROOM" +
      // icon) already overflows horizontally by 34px at this size/scale on
      // `main`, independent of CR236 — confirmed by running this same pump
      // against the pre-CR236 file. That overflow is out of this CR's scope
      // and untouched here. What CR236 owns is the Column's total height:
      // before this test's fix (wrapping the sheet body in a
      // SingleChildScrollView) adding the credits line pushed the Column
      // 5px past the viewport — a SECOND, distinct overflow this CR
      // introduced. This asserts that second one is gone by requiring
      // EXACTLY the one pre-existing exception, never zero (which would
      // silently mask a regression in the pre-existing bug's message) and
      // never more than one (which would mean this CR added a new one).
      await _pumpSheet(
        tester,
        size: const Size(320, 690),
        textScale: 1.3,
        mandateState: MandateState(
          mandate: _mandate(
            creditBalance: 63,
            roomCost: 8,
            creditsResetAt: DateTime.utc(2026, 10, 1),
          ),
        ),
      );
      final err = tester.takeException();
      expect(err, isA<FlutterError>());
      expect(
        (err as FlutterError).toString(),
        contains('overflowed by 34 pixels on the right'),
        reason: 'expected only the pre-existing, out-of-scope heading Row '
            'overflow — anything else means this CR introduced a new one',
      );
      // No SECOND exception queued behind the first.
      expect(tester.takeException(), isNull);
    });
  });
}
