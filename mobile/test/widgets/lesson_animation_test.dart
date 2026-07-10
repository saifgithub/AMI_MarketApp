/// CR013 (E3/D1) — every registered lesson-animation slot builds its coded
/// `AmiAnimation` (not the grey placeholder) and throws nothing; an unknown
/// name falls back to `AmiHexPlaceholder`. Exercises the registry + all seven
/// primitives through the real `AnimationBlock` entry point.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/animation_block.dart';
import 'package:ami_trade/widgets/lessons/animation_registry.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _slots = <String>[
  'compounding_curve',
  'fomo_curve',
  'pump_dump_curve',
  'drawdown_recovery',
  'stop_loss_trigger',
  'support_resistance_test',
  'breakout_pattern',
  'position_size_calc',
  'risk_reward_scale',
  'rsi_oscillator',
  'moving_average_lag',
  'candlestick_anatomy',
  'bull_bear_states',
  'revenge_position_escalation',
  'ami_constellation',
];

Future<void> _pump(WidgetTester t, String name) async {
  await t.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: ListView(children: [AnimationBlock(name: name)]),
      ),
    ),
  );
  await t.pump(const Duration(milliseconds: 300));
}

void main() {
  test('all 15 lesson slots are registered', () {
    for (final s in _slots) {
      expect(AnimationRegistry.has(s), isTrue, reason: 'missing slot: $s');
    }
    expect(_slots.length, 15);
  });

  testWidgets('every slot builds its animation without throwing', (t) async {
    for (final s in _slots) {
      await _pump(t, s);
      expect(t.takeException(), isNull, reason: 'threw building: $s');
      expect(find.byType(AmiAnimation), findsOneWidget, reason: 'no anim: $s');
      expect(find.byType(AmiHexPlaceholder), findsNothing,
          reason: 'fell back to placeholder: $s');
    }
  });

  testWidgets('an unknown slot falls back to the hex placeholder', (t) async {
    await _pump(t, 'not_a_real_animation');
    expect(t.takeException(), isNull);
    expect(find.byType(AmiHexPlaceholder), findsOneWidget);
    expect(find.byType(AmiAnimation), findsNothing);
  });
}
