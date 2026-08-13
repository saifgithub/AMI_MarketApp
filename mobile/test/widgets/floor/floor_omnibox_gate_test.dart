/// DEF298 + DEF297 — the Floor omnibox's gate, and its way out.
///
/// The suite was already green before either fix, which is the whole reason
/// this file exists: `floor_v02_test.dart` finds `FloorOmnibox` **by type** and
/// never types into it, so nothing exercised the convene path at all. A guard
/// nothing runs is not a guard (the DEF190 shape, third time in this lineage).
///
/// The load-bearing test is `a ticker the reference table does not know never
/// reaches the Room`. Before DEF298 the Floor pushed `RoomScreen` directly, so
/// `HI` — ticker-shaped by `routeOmnibox`'s `^[A-Za-z]{1,5}$`, and deliberately
/// not checked against any symbol list — ran twelve agents and spent a credit on
/// a company that does not exist. That is bug ab1d5664, which CR128 already
/// fixed once for the other two ticker fields in the app.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/tickers.dart';
import 'package:ami_trade/widgets/floor/floor_omnibox.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/ticker_not_found_panel.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Records every symbol the widget asked about, so a test can assert that a
/// sentence bound for the Concierge spends no request.
class _FakeValidator {
  _FakeValidator({this.known = const {'AAPL'}});

  final Set<String> known;
  final List<String> asked = [];

  Future<TickerValidation> call(String ticker) async {
    asked.add(ticker);
    return TickerValidation(ticker: ticker, exists: known.contains(ticker));
  }
}

Future<_Harness> _pump(WidgetTester t, {Set<String> known = const {'AAPL'}}) async {
  final fake = _FakeValidator(known: known);
  final convened = <String>[];
  final asked = <String>[];
  var picked = 0;

  await t.pumpWidget(MaterialApp(
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: Column(
        children: [
          FloorOmnibox(
            validate: fake.call,
            onConvene: convened.add,
            onAsk: asked.add,
            onPick: () => picked++,
          ),
          // Somewhere to tap that is not the field — the thing the real Floor
          // did not have, which is DEF297.
          const SizedBox(height: 200, width: 400, child: Text('elsewhere')),
        ],
      ),
    ),
  ));
  return _Harness(fake, convened, asked, () => picked);
}

class _Harness {
  _Harness(this.fake, this.convened, this.asked, this._picked);
  final _FakeValidator fake;
  final List<String> convened;
  final List<String> asked;
  final int Function() _picked;
  int get picked => _picked();
}

void main() {
  group('DEF298 — the gate, not the label', () {
    testWidgets('a ticker the reference table does not know never reaches the Room',
        (t) async {
      final h = await _pump(t);

      await t.enterText(find.byType(TextField), 'HI');
      await t.pumpAndSettle();

      // Ticker-shaped, so the CTA arms CONVENE — that part is unchanged.
      expect(find.textContaining('HI'), findsWidgets);

      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();

      expect(h.convened, isEmpty,
          reason: 'HI does not exist; convening would burn a credit on twelve '
              'agents debating a company that is not there (bug ab1d5664)');
      expect(h.fake.asked, contains('HI'),
          reason: 'the gate must actually ask, not just decline');
    });

    testWidgets('a real ticker convenes exactly as before', (t) async {
      final h = await _pump(t);

      await t.enterText(find.byType(TextField), 'AAPL');
      await t.pumpAndSettle();
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();

      expect(h.convened, ['AAPL']);
    });

    testWidgets('the unknown symbol is answered inline, under the field (DEF208)',
        (t) async {
      await _pump(t);

      await t.enterText(find.byType(TextField), 'ZZZZZ');
      // The validator debounces 450ms so it does not fire a request per
      // keystroke. `pumpAndSettle` returns as soon as nothing is animating, and
      // a Timer is not an animation — so the clock has to be advanced past the
      // debounce explicitly or this asserts against a check that never ran.
      await t.pump(const Duration(milliseconds: 600));
      await t.pumpAndSettle();

      expect(find.byType(TickerNotFoundPanel), findsOneWidget,
          reason: 'the answer arrives as you type, not as a modal after you '
              'have already committed');
    });

    testWidgets('a question bound for the Concierge spends no existence check',
        (t) async {
      final h = await _pump(t);

      await t.enterText(find.byType(TextField), 'what should I buy today');
      await t.pumpAndSettle();
      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();

      expect(h.asked, ['what should I buy today']);
      expect(h.fake.asked, isEmpty,
          reason: 'a sentence is not a symbol; checking it would spend a '
              'request to learn nothing');
    });

    testWidgets('an empty box still opens the picker, and checks nothing',
        (t) async {
      final h = await _pump(t);

      await t.tap(find.byType(HexButton));
      await t.pumpAndSettle();

      expect(h.picked, 1, reason: 'CR173 §5 tap-first — empty is not an error');
      expect(h.fake.asked, isEmpty);
    });
  });

  group('DEF297 — a way to put the keyboard down', () {
    /// Read the field's OWN focus, not `primaryFocus`.
    ///
    /// The first version of this test asserted
    /// `!(FocusManager.instance.primaryFocus?.context?.widget is EditableText)`,
    /// which can never be false — the primary focus's context widget is a
    /// `Focus`, never an `EditableText` — so the assertion held whether or not
    /// the fix was present. Deleting `onTapOutside` left it green. Caught by
    /// mutation, not by review.
    bool fieldHasFocus(WidgetTester t) =>
        t.state<EditableTextState>(find.byType(EditableText))
            .widget
            .focusNode
            .hasFocus;

    testWidgets('tapping outside the field drops focus', (t) async {
      await _pump(t);

      await t.tap(find.byType(TextField));
      await t.pumpAndSettle();
      expect(fieldHasFocus(t), isTrue,
          reason: 'precondition: the field took focus, so the keyboard is up');

      await t.tapAt(t.getCenter(find.text('elsewhere')));
      await t.pumpAndSettle();

      expect(fieldHasFocus(t), isFalse,
          reason: "Flutter's default onTapOutside unfocuses on DESKTOP only and "
              'does nothing on iOS/Android, so without an explicit handler the '
              'keyboard has no way down — the Floor offers nothing else to '
              'focus and the only other exit leaves the screen');
    });
  });
}
