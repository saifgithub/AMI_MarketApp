/// CR278 (CR267 WP-36) - where the Beta thumbs card shows on the Room screen.
///
/// Under a finished Room's verdict, only when the run has a verdict and an id
/// (the rating is stored against the id), and never while a run is streaming.
/// It is a plain column child, so the verdict's actions stay reachable.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/screens/room/room_screen.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/state/room_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _FixedRoomNotifier extends RoomNotifier {
  _FixedRoomNotifier(super.ref, super.ticker, RoomState fixed) {
    state = fixed;
  }
}

class _Api extends ApiClient {
  _Api() : super(baseUrl: 'test://localhost');
  final ratings = <bool>[];

  @override
  Future<void> rateRoom({required String runId, required bool helpful}) async {
    ratings.add(helpful);
  }
}

const _verdict = RoomVerdict(
  action: 'APPROVE',
  reason: 'Fits the mandate.',
  violations: [],
  overriddenFromLlm: false,
  sizePct: 2.0,
);

Future<_Api> _open(WidgetTester t, RoomState fixed) async {
  t.view.physicalSize = const Size(390, 1600);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  final api = _Api();
  await t.pumpWidget(ProviderScope(
    overrides: [
      apiClientProvider.overrideWithValue(api),
      roomNotifierProvider('AAPL')
          .overrideWith((ref) => _FixedRoomNotifier(ref, 'AAPL', fixed)),
    ],
    child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const RoomScreen(ticker: 'AAPL'),
    ),
  ));
  await t.pump();
  await t.pump(const Duration(milliseconds: 600));
  return api;
}

Future<void> _scrollToCard(WidgetTester t) => t.scrollUntilVisible(
      find.byKey(const Key('roomRatingCard')),
      300,
      scrollable: find.byType(Scrollable).first,
    );

void main() {
  testWidgets('a finished Room with a verdict shows the card; a thumb posts',
      (t) async {
    final api = await _open(
      t,
      const RoomState(
          done: true, runId: 'run-1', verdict: _verdict, creditCost: 0),
    );
    await _scrollToCard(t);
    expect(find.byKey(const Key('roomRatingCard')), findsOneWidget);
    expect(find.text('Did the verdict and its reasons make sense?'),
        findsOneWidget);

    await t.tap(find.byKey(const Key('roomRatingDown')));
    await t.pump(const Duration(milliseconds: 200));
    expect(api.ratings, [false]);
  });

  testWidgets('dismissing the card removes it without leaving the Room',
      (t) async {
    await _open(
      t,
      const RoomState(
          done: true, runId: 'run-1', verdict: _verdict, creditCost: 0),
    );
    await _scrollToCard(t);
    await t.tap(find.byKey(const Key('roomRatingDismiss')));
    await t.pump(const Duration(milliseconds: 200));
    expect(find.byKey(const Key('roomRatingCard')), findsNothing);
    expect(find.byType(RoomScreen), findsOneWidget);
  });

  testWidgets('no card while the Room is still running', (t) async {
    await _open(t, const RoomState(streaming: true, runId: 'run-1'));
    expect(find.byKey(const Key('roomRatingCard')), findsNothing);
  });

  testWidgets('no card for a Room that ended without a verdict', (t) async {
    await _open(
        t, const RoomState(done: true, runId: 'run-1', creditCost: 0));
    expect(find.byKey(const Key('roomRatingCard')), findsNothing);
  });

  testWidgets('no card without a run id to store the answer against',
      (t) async {
    await _open(
        t, const RoomState(done: true, verdict: _verdict, creditCost: 0));
    expect(find.byKey(const Key('roomRatingCard')), findsNothing);
  });
}
