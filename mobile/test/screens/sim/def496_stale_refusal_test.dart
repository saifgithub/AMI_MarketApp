/// DEF496 — a refusal belongs to the order that earned it.
///
/// `SimState.lastSubmit` outlives the trade ticket, so after an order the
/// safety floor refused (NFLX x100 on the AMI-DL-1 device run) the next "New
/// trade" ticket opened with the old SAFETY FLOOR banner above an empty
/// ticker. Opening a ticket must start clean.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/sim.dart';
import 'package:ami_trade/screens/sim/trade_ticket_sheet.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/sim_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FixedSim extends SimNotifier {
  _FixedSim(super.ref, SimState fixed) {
    state = fixed;
  }

  @override
  Future<void> refresh() async {}
}

SimSubmitResult _refused() => SimSubmitResult.fromJson({
      'ok': false,
      'resting': false,
      'compliance': {
        'passed': false,
        'violations': ['position size 59.8% exceeds single-name cap 3.0%'],
        'blocked_by': 'single_name_cap',
      },
    });

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('a fresh ticket does not inherit the previous refusal',
      (t) async {
    await t.binding.setSurfaceSize(const Size(700, 1600));
    addTearDown(() => t.binding.setSurfaceSize(null));
    late ProviderContainer container;
    await t.pumpWidget(ProviderScope(
      overrides: [
        simNotifierProvider.overrideWith(
            (ref) => _FixedSim(ref, SimState(lastSubmit: _refused()))),
        alpacaLinkedProvider.overrideWith((ref) async => false),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Builder(builder: (context) {
          container = ProviderScope.containerOf(context);
          return const TradeTicketSheet();
        }),
      ),
    ));
    for (var i = 0; i < 4; i++) {
      await t.pump(const Duration(milliseconds: 120));
    }

    final l = AppLocalizations.of(t.element(find.byType(TradeTicketSheet)));
    expect(find.text(l.tradeTicketSafetyFloorBlocked), findsNothing);
    expect(container.read(simNotifierProvider).lastSubmit, isNull);
  });
}
