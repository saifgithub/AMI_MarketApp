/// CR012 (C4) — pumps each ShareCard template offscreen-sized and asserts it
/// builds without throwing and paints its key content. This exercises the
/// sealed `ShareCardData` switch and the four template bodies (the logic we
/// own); the rasterise-to-PNG path needs a real engine and is device-verified.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/share/share_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pumpCard(WidgetTester tester, ShareCardData data) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Center(
        child: FittedBox(
          child: ShareCard(
            data: data,
            disclaimer: 'Educational simulation. Not investment advice.',
          ),
        ),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  testWidgets('verdict template builds and shows ticker + stance', (t) async {
    await _pumpCard(
      t,
      const VerdictShareData(
        kicker: "THE ROOM'S VERDICT",
        accent: AmiColors.hexGreen,
        ticker: 'NVDA',
        stanceLabel: 'APPROVE',
        reason: 'Momentum and earnings both point the same way.',
      ),
    );
    expect(t.takeException(), isNull);
    expect(find.text('NVDA'), findsOneWidget);
    expect(find.text('APPROVE'), findsOneWidget);
    expect(find.text('AMI TRADE'), findsOneWidget);
  });

  testWidgets('streak template builds and shows the day count', (t) async {
    await _pumpCard(
      t,
      const StreakShareData(
        kicker: 'DAY STREAK',
        accent: AmiColors.hexGreen,
        days: 12,
        unit: 'DAY STREAK',
      ),
    );
    expect(t.takeException(), isNull);
    expect(find.text('12'), findsOneWidget);
  });

  testWidgets('unlock template builds and shows agent name', (t) async {
    await _pumpCard(
      t,
      const UnlockShareData(
        kicker: 'AGENT UNLOCKED',
        accent: AmiColors.hexPurple,
        agentName: 'Fundamentals Analyst',
        abbreviation: 'FA',
      ),
    );
    expect(t.takeException(), isNull);
    expect(find.text('Fundamentals Analyst'), findsOneWidget);
    expect(find.text('FA'), findsOneWidget);
  });

  testWidgets('promotion template builds and shows rank', (t) async {
    await _pumpCard(
      t,
      const PromotionShareData(
        kicker: 'LEAGUE STANDING',
        accent: AmiColors.hexAmber,
        tierLabel: 'FLOOR VETERAN',
        week: '2026-W28',
        rank: 3,
        outcomeLabel: 'PROMOTED',
      ),
    );
    expect(t.takeException(), isNull);
    expect(find.text('#3'), findsOneWidget);
    expect(find.text('FLOOR VETERAN'), findsOneWidget);
    expect(find.text('PROMOTED'), findsOneWidget);
  });
}
