/// DEF471 — backing out of a Room that is still deliberating is no longer silent.
///
/// Saiful's ruling (2026-10-20): opening the Room starts the run by design (the
/// credit line is on the Convene sheet before that), but leaving mid-run must
/// warn and keep the run going - "The run continues; you'll find the verdict in
/// Journal" - with Leave / Stay. A finished (or not-yet-running) Room leaves
/// without a prompt.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }
}

/// The live Room runs looping loaders, so `pumpAndSettle` would never return.
Future<void> _settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 600));
}

Future<void> _openRoom(WidgetTester tester, RoomState fixed) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(ProviderScope(
    overrides: [
      roomNotifierProvider('AAPL')
          .overrideWith((ref) => _FixedRoomNotifier(ref, 'AAPL', fixed)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Builder(
        builder: (context) => Scaffold(
          body: ElevatedButton(
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
              builder: (_) => const RoomScreen(ticker: 'AAPL'),
            )),
            child: const Text('open room'),
          ),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('open room'));
  await _settle(tester);
  expect(find.byType(RoomScreen), findsOneWidget);
}

void main() {
  for (final entry in {
    'streaming': const RoomState(streaming: true, runId: 'run-1'),
    'reconnecting': const RoomState(reconnecting: true, runId: 'run-1'),
  }.entries) {
    testWidgets('back while ${entry.key} asks first; STAY keeps the Room open',
        (tester) async {
      await _openRoom(tester, entry.value);

      await tester.tap(find.byIcon(Icons.arrow_back));
      await _settle(tester);

      expect(find.text('Leave the Room?'), findsOneWidget);
      expect(find.textContaining('verdict will be saved to your Journal'),
          findsOneWidget);
      expect(find.byType(RoomScreen), findsOneWidget);

      await tester.tap(find.text('STAY'));
      await _settle(tester);
      expect(find.text('Leave the Room?'), findsNothing);
      expect(find.byType(RoomScreen), findsOneWidget);
    });

    testWidgets('back while ${entry.key} then LEAVE pops the Room',
        (tester) async {
      await _openRoom(tester, entry.value);

      await tester.tap(find.byIcon(Icons.arrow_back));
      await _settle(tester);
      await tester.tap(find.text('LEAVE'));
      await _settle(tester);

      expect(find.byType(RoomScreen), findsNothing);
      expect(find.text('open room'), findsOneWidget);
    });
  }

  testWidgets('system back mid-run is intercepted too', (tester) async {
    await _openRoom(tester, const RoomState(streaming: true, runId: 'run-1'));

    final handled = await tester.binding.handlePopRoute();
    await _settle(tester);

    expect(handled, isTrue);
    expect(find.text('Leave the Room?'), findsOneWidget);
    expect(find.byType(RoomScreen), findsOneWidget);
  });

  testWidgets('a finished Room leaves without a prompt', (tester) async {
    await _openRoom(
        tester, const RoomState(done: true, runId: 'run-1', creditCost: 0));

    await tester.tap(find.byIcon(Icons.arrow_back));
    await _settle(tester);

    expect(find.text('Leave the Room?'), findsNothing);
    expect(find.byType(RoomScreen), findsNothing);
  });
}
