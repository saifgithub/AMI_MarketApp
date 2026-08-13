/// CR173 §5 — the omnibox router.
///
/// The acceptance says "deterministic routing, no LLM". Determinism is what
/// makes it testable at all, so these are the whole control: every case is
/// fixed, and the one case the rule gets *wrong* is written down as a test
/// rather than discovered in the field.
library;

import 'package:ami_trade/features/floor/omnibox_router.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('a ticker arms CONVENE, upper-cased', () {
    for (final input in ['AAPL', 'aapl', ' AAPL ', r'$AAPL', r' $aapl ']) {
      final d = routeOmnibox(input);
      expect(d.route, OmniboxRoute.convene, reason: input);
      expect(d.ticker, 'AAPL', reason: input);
    }
  });

  test('one letter and five letters are both tickers', () {
    // A is Agilent; GOOGL is five. A range that excluded either would refuse a
    // real symbol, which is worse than convening on a word.
    expect(routeOmnibox('A').route, OmniboxRoute.convene);
    expect(routeOmnibox('GOOGL').route, OmniboxRoute.convene);
    expect(routeOmnibox('GOOGLE').route, OmniboxRoute.concierge);
  });

  test('a question goes to the Concierge, carrying its text', () {
    final d = routeOmnibox('  what is a P/E ratio?  ');
    expect(d.route, OmniboxRoute.concierge);
    expect(d.text, 'what is a P/E ratio?',
        reason: 'trimmed, but otherwise exactly what they typed — this becomes '
            'their first message, not a paraphrase of it');
  });

  test('an empty box is the picker, not an error', () {
    for (final input in ['', '   ', r'$', r' $ ']) {
      expect(routeOmnibox(input).route, OmniboxRoute.picker, reason: '"$input"');
    }
  });

  test('anything with a space, digit or symbol is a question', () {
    for (final input in ['buy AAPL', 'AAPL?', 'A1', 'why did NVDA drop']) {
      expect(routeOmnibox(input).route, OmniboxRoute.concierge, reason: input);
    }
  });

  test('the known-wrong case, stated', () {
    // Shape-matching cannot read intent: `HI` is a greeting and a ticker
    // (Hawaiian Electric). It arms CONVENE, and that is why the CTA renames
    // itself to name the ticker — the user reads "CONVENE THE ROOM · HI" and
    // corrects it before a credit is spent. Written down rather than left as a
    // surprise: the alternative is an LLM classifier, and CR038 measured what
    // those do to a control.
    final d = routeOmnibox('hi');
    expect(d.route, OmniboxRoute.convene);
    expect(d.ticker, 'HI');
  });

  test('routing is a pure function of the text', () {
    // No clock, no locale, no network — the same input gives the same route
    // forever, which is the property "no LLM in the routing" is protecting.
    for (var i = 0; i < 3; i++) {
      expect(routeOmnibox('nvda').ticker, 'NVDA');
      expect(routeOmnibox('tell me about nvda').route, OmniboxRoute.concierge);
    }
  });
}
