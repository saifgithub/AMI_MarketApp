// DEF482 — the Floor logged three RenderFlex overflows (1.6px, 9.4px and
// 2798px on the right). The 2798px one is the ticker tape: its doubled Row of
// fixed-width items was laid out under the screen's width constraint inside a
// ClipRect, so Flutter reported an overflow on every frame it laid out. The
// small ones are the house-ad strip's single-line row. Both are persistent
// chrome, so neither may ever overflow at any shipped width or text scale.

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/services/yahoo_finance_service.dart';
import 'package:ami_trade/state/ticker_tape_provider.dart';
import 'package:ami_trade/widgets/ads/house_ad_banner_strip.dart';
import 'package:ami_trade/widgets/ticker_tape.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

TickerTapeData _tape() => TickerTapeData(
      quotes: List.generate(
        20,
        (i) => TickerQuote(
          symbol: 'SYM$i',
          price: 100.0 + i,
          changePercent: i.isEven ? 1.2 : -0.8,
          marketState: 'REGULAR',
        ),
      ),
    );

class _FixedTapeNotifier extends TickerTapeNotifier {
  @override
  Future<TickerTapeData> build() async => _tape();
}

Widget _app(Widget child, {Locale locale = const Locale('en'), double scale = 1.0}) =>
    ProviderScope(
      overrides: [
        tickerTapeProvider.overrideWith(_FixedTapeNotifier.new),
      ],
      child: MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, c) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)),
          child: c!,
        ),
        home: Scaffold(body: Align(alignment: Alignment.bottomCenter, child: child)),
      ),
    );

void main() {
  for (final width in const [320.0, 375.0, 430.0]) {
    for (final code in const ['en', 'ar', 'ms']) {
      testWidgets('ticker tape lays out without overflow ($code, ${width}dp)',
          (tester) async {
        tester.view.physicalSize = Size(width, 800);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        await tester.pumpWidget(_app(const TickerTape(), locale: Locale(code)));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 500));

        expect(find.text('SYM0'), findsWidgets);
        expect(tester.takeException(), isNull,
            reason: 'the tape is wider than the screen by design; it must '
                'say so to the layout instead of overflowing');
      });

      for (final scale in const [1.0, 1.3, 2.0]) {
        for (final tier in HouseAdTargetTier.values) {
          testWidgets(
              'house-ad strip does not overflow ($code, ${width}dp, ${scale}x, '
              '${tier.name})', (tester) async {
            tester.view.physicalSize = Size(width, 800);
            tester.view.devicePixelRatio = 1.0;
            addTearDown(tester.view.reset);

            await tester.pumpWidget(_app(
              HouseAdBannerStrip(
                creative: HouseAdCreative(
                    slot: HouseAdSlot.genericTrader, targetTier: tier),
              ),
              locale: Locale(code),
              scale: scale,
            ));
            await tester.pump();

            expect(tester.takeException(), isNull);
          });
        }
      }
    }
  }
}
