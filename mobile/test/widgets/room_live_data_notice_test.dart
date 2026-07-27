/// CR090 (D3/D4) — the Room console's live-data disclosure card.
///
/// Load-bearing behaviours proven here:
///   * `live` / `withheld_paid` / `unavailable` each render distinct copy.
///   * `withheld_paid` shows the upgrade CTA; `unavailable` shows NO CTA and
///     no upsell (D3) — getting these backwards is the CR's BLOCKER class.
///   * No `live_data_notice` event ⇒ nothing rendered at all (D4) — never a
///     defaulted "surcharge: 0" or "unavailable" card.
///   * The surcharge is rendered exactly as received, never recomputed (D5).
///
/// `RoomScreen` reads `roomNotifierProvider(ticker)` directly; this harness
/// overrides that family member with a notifier pre-seeded to a fixed
/// `RoomState` (never calling `start()`, so no real network/SSE stream is
/// touched).
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

Future<void> _pump(WidgetTester t, RoomState fixed) {
  const ticker = 'AAPL';
  return t.pumpWidget(
    ProviderScope(
      overrides: [
        roomNotifierProvider(ticker)
            .overrideWith((ref) => _FixedRoomNotifier(ref, ticker, fixed)),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const RoomScreen(ticker: ticker),
      ),
    ),
  );
}

void main() {
  testWidgets('withheld_paid renders "needs credits" + an upgrade CTA', (t) async {
    await _pump(
      t,
      const RoomState(
        liveDataNotice: RoomLiveDataNotice(
          news: 'withheld_paid',
          social: 'unavailable',
          surchargeCharged: 0,
        ),
      ),
    );
    await t.pump();

    expect(find.textContaining('needs credits'), findsOneWidget);
    expect(find.text('UPGRADE FOR LIVE DATA'), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('unavailable alone renders NO CTA and no upsell', (t) async {
    await _pump(
      t,
      const RoomState(
        liveDataNotice: RoomLiveDataNotice(
          news: 'unavailable',
          social: 'unavailable',
          surchargeCharged: 0,
        ),
      ),
    );
    await t.pump();

    expect(find.textContaining('unavailable right now'), findsWidgets);
    expect(find.text('UPGRADE FOR LIVE DATA'), findsNothing);
    expect(find.textContaining('needs credits'), findsNothing);
    expect(t.takeException(), isNull);
  });

  testWidgets('live renders confirmation + the surcharge as sent, no CTA', (t) async {
    await _pump(
      t,
      const RoomState(
        liveDataNotice: RoomLiveDataNotice(
          news: 'live',
          social: 'live',
          surchargeCharged: 4,
        ),
      ),
    );
    await t.pump();

    expect(find.textContaining('live feed used'), findsWidgets);
    expect(find.textContaining('4 extra credits'), findsOneWidget);
    expect(find.text('UPGRADE FOR LIVE DATA'), findsNothing);
    expect(t.takeException(), isNull);
  });

  testWidgets('no notice at all renders nothing — never a defaulted state (D4)', (t) async {
    await _pump(t, const RoomState());
    await t.pump();

    expect(find.text('Live data'), findsNothing);
    expect(find.text('UPGRADE FOR LIVE DATA'), findsNothing);
    expect(find.textContaining('extra credits'), findsNothing);
    expect(t.takeException(), isNull);
  });
}
