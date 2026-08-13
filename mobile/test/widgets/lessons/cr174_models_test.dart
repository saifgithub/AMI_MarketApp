/// CR174 §4/§7 — the six pilot models, checked against the figures their own
/// lessons publish.
///
/// This is the test that matters most, and it is not about rendering. The CR's
/// diagnosis is that today's animation *decorates* the prose:
/// `014_position_sizing_basics` argues in $20,000 / $480 / $459 / 9 shares while
/// its `BalanceScalePainter(leftValue: 2, rightValue: 2)` shows a generic scale.
/// Binding a slider to a painter only fixes that if the numbers agree — and a
/// model that quietly disagrees with the paragraph above it is worse than the
/// generic scale, because the reader will believe the picture (DEF098).
///
/// So every assertion below is a number lifted from the lesson body, cited
/// where it came from. If the content lane edits a worked example, this file is
/// where that shows up.
library;

import 'dart:io';

import 'package:ami_trade/widgets/lessons/interactive_registry.dart';
import 'package:ami_trade/widgets/lessons/lesson_play.dart';
import 'package:flutter_test/flutter_test.dart';

const _noMandate = LessonPlayCaps.unknown;

/// A mandate with every CR101 field populated, so the ceiling paths are
/// exercised rather than skipped.
const _strict = LessonPlayCaps(
  singleNameCapPct: 20,
  maxDrawdownPct: 15,
  maxOpenRiskPct: 4,
);

LessonPlayFrame _frame(String lessonId, double v,
        [LessonPlayCaps caps = _noMandate]) =>
    InteractiveRegistry.forLesson(lessonId)!.play.build(v, caps);

String _readout(LessonPlayFrame f, String label) =>
    f.readouts.firstWhere((r) => r.label == label).value;

void main() {
  group('014 position sizing — the slider line 33 describes in prose', () {
    const id = '014_position_sizing_basics';

    test('opens on the lesson\'s own worked example', () {
      // "Per-share risk = $480 − $459 = $21. Shares = $200 ÷ $21 = 9 shares.
      //  Position notional = 9 × $480 = $4,320, or about 21.6% of your account."
      final f = _frame(id, 459);
      expect(_readout(f, 'RISK/SH'), '\$21.00');
      expect(_readout(f, 'SHARES'), '9');
      expect(_readout(f, 'NOTIONAL'), '\$4,320');
      expect(_readout(f, 'OF ACCOUNT'), '21.6%');
    });

    test('the sentence the CR quotes actually plays', () {
      // "if you had set the stop at $470 instead, per-share risk drops to $10
      //  and shares jump to 20"
      final f = _frame(id, 470);
      expect(_readout(f, 'RISK/SH'), '\$10.00');
      expect(_readout(f, 'SHARES'), '20');
    });

    test('shares round down, never up', () {
      // $200 ÷ $18 = 11.1. Rounding up is how a 1% rule quietly becomes 1.2%.
      expect(_readout(_frame(id, 462), 'SHARES'), '11');
    });

    test('the PM floor bites where the prototype said it does', () {
      // The reviewed prototype: "pushing the stop past ~$471 visibly hits the
      // PM floor" against the real SINGLE_NAME_ABSOLUTE_CAP_PCT = 50.
      expect(_frame(id, 470).breach, isNull);
      expect(_frame(id, 471).breach, isNotNull);
    });

    test('a tighter cap on the learner\'s own mandate bites earlier', () {
      // CR174 §7 — teach with the learner's caps, not a constant. At a 20% cap
      // the lesson's own $459 example is already over.
      expect(_frame(id, 459, _strict).breach, isNotNull);
      expect(_frame(id, 459).breach, isNull);
    });
  });

  group('015 stop-loss — the stop inside the noise', () {
    const id = '015_stop_loss_basics';

    test('opens on the ticket the lesson builds', () {
      // "entry $246, stop $237.50 …, per-share risk = $8.50"
      final f = _frame(id, 237.5);
      expect(_readout(f, 'RISK/SH'), '\$8.50');
      expect(_readout(f, 'OUTCOME'), 'EXIT ON CLOSE');
      expect(f.breach, isNull,
          reason: 'the lesson\'s own stop survives the \$239.10 wick — that is '
              'why it is the lesson\'s stop');
    });

    test('a stop above the wick fires on a day the thesis held', () {
      // "TSLA dips to $239.10 intraday, then closes at $244. The stop is not
      //  hit." — unless you put it higher.
      final f = _frame(id, 240);
      expect(_readout(f, 'OUTCOME'), 'SHAKEN OUT');
      expect(f.breach, isNotNull);
    });

    test('a stop below the invalidating close leaves you in', () {
      // Price closed at $233.80; a stop under that never triggers.
      expect(_readout(_frame(id, 232), 'OUTCOME'), 'STILL IN');
    });
  });

  group('016 risk/reward — moving the target', () {
    const id = '016_risk_reward_ratio';

    test('opens on the MSFT setup the lesson prices', () {
      // "Per-share risk = $415 − $407 = $8. Per-share reward = $440 − $415 =
      //  $25. R:R = 25 ÷ 8 = 3.1."
      final f = _frame(id, 440);
      expect(_readout(f, 'REWARD/SH'), '\$25');
      expect(_readout(f, 'R:R'), '3.1');
      expect(f.breach, isNull);
    });

    test('the flipped case reproduces the lesson\'s break-even figure', () {
      // "target is only $422 … Reward = $7, risk = $8, R:R = 0.88. You would
      //  need to win 53% of the time just to break even."
      final f = _frame(id, 422);
      expect(_readout(f, 'R:R'), '0.9');
      expect(_readout(f, 'BREAK-EVEN WIN'), '53%');
      expect(f.breach, isNotNull);
    });
  });

  group('018 drawdown — the hole and the climb', () {
    const id = '018_drawdown_management';

    test('reproduces the lesson\'s three published recoveries', () {
      // "a 20% loss needs a 25% gain; a 50% loss needs a 100% gain; a 75% loss
      //  needs a 300% gain"
      expect(_readout(_frame(id, 20), 'GAIN TO FLAT'), '+25.0%');
      expect(_readout(_frame(id, 50), 'GAIN TO FLAT'), '+100.0%');
      expect(_readout(_frame(id, 75), 'GAIN TO FLAT'), '+300.0%');
    });

    test('reproduces the worked example and its month count', () {
      // "$50,000 … drops to $35,000 — a 30% drawdown … That is 42.9% … now you
      //  need 36 months"
      final f = _frame(id, 30);
      expect(_readout(f, 'GAIN TO FLAT'), '+42.9%');
      expect(_readout(f, 'AT 1%/MONTH'), '36 mo');
    });

    test('reproduces the mandated-ceiling comparison', () {
      // "Drawdown of 15% requires only 17.6% to recover — about 16 months"
      final f = _frame(id, 15);
      expect(_readout(f, 'GAIN TO FLAT'), '+17.6%');
      expect(_readout(f, 'AT 1%/MONTH'), '16 mo');
    });

    test('says nothing about a ceiling it cannot read', () {
      // CR040 — a warning we cannot substantiate is worse than none.
      expect(_frame(id, 70, _noMandate).breach, isNull);
      expect(_frame(id, 70, _strict).breach, isNotNull);
      expect(_frame(id, 10, _strict).breach, isNull);
    });
  });

  group('013 losing streak — losses compound faster', () {
    const id = '013_why_risk_matters_more_than_profit';

    test('a 1% risk survives ten losses almost intact', () {
      // 0.99^10 = 0.9044.
      final f = _frame(id, 1);
      expect(_readout(f, 'AFTER 10'), '90.4%');
      expect(_readout(f, 'DRAWDOWN'), '9.6%');
    });

    test('a 10% risk does not', () {
      // 0.9^10 = 0.3487 — a 65.1% hole needing a +186.8% climb, which is the
      // asymmetry the whole lesson is about.
      final f = _frame(id, 10);
      expect(_readout(f, 'DRAWDOWN'), '65.1%');
      expect(_readout(f, 'TO RECOVER'), '+186.8%');
    });

    test('names which loss breaks the learner\'s own ceiling', () {
      // At 5% per trade against a 15% mandated ceiling: 0.95^3 = 0.857, the
      // first value under 0.85.
      final f = _frame(id, 5, _strict);
      expect(f.breach, isNotNull);
      expect(_frame(id, 0.5, _strict).breach, isNull);
      expect(_frame(id, 5, _noMandate).breach, isNull);
    });
  });

  group('017 correlation — five positions, one bet', () {
    const id = '017_portfolio_exposure_and_correlation';

    test('at the correlation the lesson observes, five names are ~one bet', () {
      // "these five names regularly post correlations of 0.7 to 0.9" and
      // "you do not hold three positions — you hold one position three times".
      final f = _frame(id, 0.85);
      expect(_readout(f, 'REAL RISK'), '4.7%');
      expect(_readout(f, 'EFFECTIVE BETS'), '1.1');
    });

    test('the two ends of the dial are the two textbook answers', () {
      // Independent: 1% × √5 = 2.2%. Perfectly correlated: the naive sum, 5%.
      expect(_readout(_frame(id, 0), 'REAL RISK'), '2.2%');
      expect(_readout(_frame(id, 0), 'EFFECTIVE BETS'), '5.0');
      expect(_readout(_frame(id, 1), 'REAL RISK'), '5.0%');
      expect(_readout(_frame(id, 1), 'EFFECTIVE BETS'), '1.0');
    });

    test('an unset open-risk limit draws no ceiling', () {
      // CR101-BE2 — null on this field means OFF, not "use a preset". Drawing
      // a breach against a number nobody chose is the CR040 sin in reverse.
      expect(_frame(id, 1, _noMandate).breach, isNull);
      expect(_frame(id, 1, _strict).breach, isNotNull);
    });
  });

  group('the corpus the registry is anchored to', () {
    // Acceptance #4 asks for a guard derived from the registry rather than a
    // hand-listed allowlist, so a lesson added to the registry tomorrow is
    // inside the check by construction.
    final dir = Directory('../content/lessons');

    test('the guard has a corpus to check', () {
      expect(dir.existsSync(), isTrue,
          reason: 'run from mobile/; without the corpus every check below '
              'passes vacuously');
      expect(InteractiveRegistry.registeredLessonIds, isNotEmpty);
    });

    for (final id in InteractiveRegistry.registeredLessonIds) {
      test('$id ships in every locale, with the same section skeleton', () {
        final counts = <String, int>{};
        for (final locale in const ['en', 'ar', 'ms']) {
          final f = File('${dir.path}/$id.$locale.mdx');
          expect(f.existsSync(), isTrue,
              reason: 'interactive mode is anchored to section indices, so a '
                  'missing locale is a lesson whose interactions cannot be '
                  'placed at all');
          counts[locale] = f
              .readAsLinesSync()
              .where((l) => l.startsWith('## '))
              .length;
        }
        expect(counts.values.toSet(), hasLength(1),
            reason: 'section counts differ across locales ($counts) — an '
                'index-anchored interaction would land on a different section '
                'in each language, which is exactly the failure that is '
                'invisible to an English-speaking reviewer');

        final spec = InteractiveRegistry.forLesson(id)!;
        final sections = counts['en']!;
        for (final s in spec.revealSections) {
          expect(s, lessThan(sections),
              reason: 'reveal anchored to section $s but $id has $sections');
        }
        expect(spec.afterSection, lessThan(sections));
      });
    }
  });
}
