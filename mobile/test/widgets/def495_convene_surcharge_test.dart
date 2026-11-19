/// DEF495 — the Convene sheet showed "Room: 8 credits - you have 13" and the
/// run then charged 10, because CR090 adds 2 credits per live News/Social feed
/// that fires. The mandate now advertises the ceiling
/// (`room_live_data_surcharge_max`) and the credits line must show it before
/// the user confirms, as "up to", since which feeds fire is only known during
/// the run.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/mandate.dart';
import 'package:ami_trade/widgets/credits_line.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _host(Locale locale, Widget child) => MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: child),
    );

void main() {
  test('the mandate parses the advertised ceiling, null when absent', () {
    final m = UserMandate.fromJson({
      'user_id': 'u1',
      'plan': 'floor_pass',
      'room_cost': 8,
      'room_live_data_surcharge_max': 4,
    });
    expect(m.roomLiveDataSurchargeMax, 4);
    final old = UserMandate.fromJson({'user_id': 'u1', 'plan': 'floor_pass'});
    expect(old.roomLiveDataSurchargeMax, isNull);
  });

  testWidgets('shows the surcharge ceiling before the charge', (t) async {
    await t.pumpWidget(_host(
      const Locale('en'),
      const ConveneCreditsLine(cost: 8, balance: 13, liveDataSurchargeMax: 4),
    ));
    final l = AppLocalizations.of(t.element(find.byType(ConveneCreditsLine)));
    expect(
      find.text('${l.creditsLineCost('8', '13')} · '
          '${l.creditsLineLiveSurcharge('4')}'),
      findsOneWidget,
    );
    expect(find.textContaining('up to +4'), findsOneWidget);
  });

  testWidgets('no surcharge clause when none is advertised or Rooms are free',
      (t) async {
    for (final (cost, max) in [(8, null), (8, 0), (0, 4)]) {
      await t.pumpWidget(_host(
        const Locale('en'),
        ConveneCreditsLine(cost: cost, balance: 13, liveDataSurchargeMax: max),
      ));
      expect(find.textContaining('live news'), findsNothing,
          reason: 'cost $cost, max $max');
    }
  });

  for (final code in ['ar', 'ms']) {
    testWidgets('the line is translated in $code', (t) async {
      await t.pumpWidget(_host(
        Locale(code),
        const ConveneCreditsLine(cost: 8, balance: 13, liveDataSurchargeMax: 4),
      ));
      expect(find.textContaining('live news'), findsNothing);
      expect(find.textContaining('credits'), findsNothing);
    });
  }
}
