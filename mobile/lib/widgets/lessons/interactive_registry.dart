/// CR174 — where a lesson becomes interactive. One entry per lesson, all data.
///
/// **This registry is also the gate.** CR174's degrade-loudly clause (CR040) is
/// that a lesson with no interactive assets must not present an empty
/// interactive mode — and CR038 says an authoring convention is not a control.
/// So the toggle is driven off [InteractiveRegistry.has]: a lesson absent from
/// this map has no interactive mode to offer and never shows the switch. There
/// is no placeholder state to get wrong because there is no placeholder.
///
/// **Anchors are section indices, not heading text.** `## The trap` is
/// `## الفخ` in Arabic and `## Perangkap` in Malay, so a text match would arm
/// the interaction in English and silently drop it in the two locales that ship
/// at v1.0. Measured 2026-08-13: all six pilot lessons carry exactly 5 `## `
/// sections in all three locales, and `test_lesson_corpus_integrity` plus this
/// CR's own guard keep that true.
///
/// **Every model reproduces its lesson's published figures at [LessonPlay
/// .initial].** That is the acceptance test, not a nicety: a slider that opens
/// on numbers the prose two lines above does not state is a second source of
/// truth for the same worked example (DEF098), and the reader will believe the
/// picture.
library;

import 'dart:math' as math;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/anim/balance_scale_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/comparison_bars_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/curve_draw_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/streak_bars_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/threshold_trigger_painter.dart';
import 'package:ami_trade/widgets/lessons/lesson_play.dart';
import 'package:flutter/material.dart';

/// What interactive mode adds to one lesson.
class LessonInteractive {
  const LessonInteractive({
    required this.play,
    this.afterSection = -1,
    this.revealSections = const {},
  });

  final LessonPlay play;

  /// The section index the play card is inserted **after**; `-1` places it
  /// immediately after the opening, before section 0.
  ///
  /// `-1` for all six pilot lessons on purpose. The measured before-state is a
  /// first interaction at the **50% mark** of the body; putting the model at
  /// card index 1 is the whole of acceptance #2's "first interaction at ≤1
  /// card", and it is a placement decision, not an authoring one.
  final int afterSection;

  /// Sections rendered commit-then-reveal rather than as open prose.
  ///
  /// Section 1 is `## The trap` in every pilot lesson, and a trap that is
  /// already visible is not a trap — the section is written as a prediction the
  /// reader is supposed to get wrong first.
  final Set<int> revealSections;
}

String _money(num v, {int decimals = 0}) {
  final neg = v < 0;
  final s = v.abs().toStringAsFixed(decimals);
  final parts = s.split('.');
  final buf = StringBuffer();
  final digits = parts[0];
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) buf.write(',');
    buf.write(digits[i]);
  }
  final tail = parts.length > 1 ? '.${parts[1]}' : '';
  return '${neg ? '-' : ''}\$$buf$tail';
}

String _pct(double v, {int decimals = 1}) => '${v.toStringAsFixed(decimals)}%';

class InteractiveRegistry {
  InteractiveRegistry._();

  static final Map<String, LessonInteractive> _entries = {
    // ── RISK 1 · 013 — the streak, and the ceiling it crosses ────────────
    //
    // One of the two pilot lessons with no registered animation, kept in
    // deliberately to test whether adding a visual is genuinely cheap. Its
    // argument is that losses compound faster than gains, so the control is the
    // one number that decides how fast: risk per trade.
    '013_why_risk_matters_more_than_profit': LessonInteractive(
      revealSections: {1},
      play: LessonPlay(
        accent: AmiColors.hexRed,
        controlLabel: 'RISK / TRADE',
        min: 0.5,
        max: 10,
        step: 0.5,
        initial: 1,
        formatValue: _pct,
        build: _streakFrame,
      ),
    ),

    // ── RISK 2 · 014 — the slider the prose describes ────────────────────
    //
    // Line 33 of the lesson: *"if you had set the stop at $470 instead,
    // per-share risk drops to $10 and shares jump to 20."* That sentence is
    // this control. At the initial $459 the frame reads $21 / 9 shares /
    // $4,320 / 21.6% — the lesson's own worked example, digit for digit.
    '014_position_sizing_basics': LessonInteractive(
      revealSections: {1},
      play: LessonPlay(
        accent: AmiColors.hexCyan,
        controlLabel: 'STOP',
        min: 455,
        max: 479,
        step: 1,
        initial: 459,
        formatValue: _money,
        build: _sizingFrame,
      ),
    ),

    // ── RISK 3 · 015 — the stop that is too tight to survive noise ───────
    '015_stop_loss_basics': LessonInteractive(
      revealSections: {1},
      play: LessonPlay(
        accent: AmiColors.hexBlue,
        controlLabel: 'STOP',
        min: 230,
        max: 245,
        step: 0.5,
        initial: 237.5,
        formatValue: _stopPrice,
        build: _stopFrame,
      ),
    ),

    // ── RISK 4 · 016 — moving the target, and what it costs ──────────────
    '016_risk_reward_ratio': LessonInteractive(
      revealSections: {1},
      play: LessonPlay(
        accent: AmiColors.hexAmber,
        controlLabel: 'TARGET',
        min: 418,
        max: 460,
        step: 1,
        initial: 440,
        formatValue: _money,
        build: _riskRewardFrame,
      ),
    ),

    // ── RISK 5 · 017 — five positions, one bet ───────────────────────────
    //
    // The other un-animated pilot lesson. Its falsifiable test — *"if your top
    // 3 holdings have moved together on more than 70% of red days, you do not
    // hold three positions"* — is a number the reader cannot compute from the
    // prose. Here it is the readout.
    '017_portfolio_exposure_and_correlation': LessonInteractive(
      revealSections: {1},
      play: LessonPlay(
        accent: AmiColors.hexPurple,
        controlLabel: 'CORRELATION',
        min: 0,
        max: 1,
        step: 0.05,
        initial: 0.85,
        formatValue: _rho,
        build: _correlationFrame,
      ),
    ),

    // ── RISK 6 · 018 — the hole and the climb ────────────────────────────
    '018_drawdown_management': LessonInteractive(
      revealSections: {1},
      play: LessonPlay(
        accent: AmiColors.hexBlue,
        controlLabel: 'DRAWDOWN',
        min: 5,
        max: 75,
        step: 5,
        initial: 30,
        formatValue: _pctWhole,
        build: _drawdownFrame,
      ),
    ),
  };

  static LessonInteractive? forLesson(String lessonId) => _entries[lessonId];

  /// Whether interactive mode exists for this lesson at all. The toggle's only
  /// gate — see the library docstring.
  static bool has(String lessonId) => _entries.containsKey(lessonId);

  @visibleForTesting
  static Iterable<String> get registeredLessonIds => _entries.keys;
}

String _stopPrice(double v) => _money(v, decimals: 2);
String _pctWhole(double v) => '${v.round()}%';
String _rho(double v) => v.toStringAsFixed(2);

// ── 013 ──────────────────────────────────────────────────────────────────

const int _kStreakLength = 10;

LessonPlayFrame _streakFrame(double riskPct, LessonPlayCaps caps) {
  final r = riskPct / 100;
  final equity = [
    for (var i = 1; i <= _kStreakLength; i++) math.pow(1 - r, i).toDouble(),
  ];
  final survived = equity.last;
  final drawdown = (1 - survived) * 100;
  final recover = survived <= 0 ? double.infinity : (1 / survived - 1) * 100;

  final ceilPct = caps.maxDrawdownPct;
  final ceiling = ceilPct == null ? null : 1 - ceilPct / 100;
  // Which loss in the streak first takes them past their own ceiling. Reported
  // rather than inferred from the bar colours — a greyed bar says "past the
  // line", the sentence says which decision put it there.
  int? breachAt;
  if (ceiling != null) {
    for (var i = 0; i < equity.length; i++) {
      if (equity[i] < ceiling) {
        breachAt = i + 1;
        break;
      }
    }
  }

  return LessonPlayFrame(
    painter: (t, th) => StreakBarsPainter(
      t: t,
      theme: th,
      equity: equity,
      ceilingFraction: ceiling,
      ceilingLabel: ceilPct == null ? null : 'YOUR CAP $ceilPct%',
    ),
    readouts: [
      PlayReadout('AFTER $_kStreakLength', _pct(survived * 100)),
      PlayReadout('DRAWDOWN', _pct(drawdown), emphasis: true),
      PlayReadout('TO RECOVER',
          recover.isFinite ? '+${_pct(recover)}' : '—'),
    ],
    breach: breachAt == null
        ? null
        : (l) => l.lessonPlayBreachStreak(breachAt!, _kStreakLength, ceilPct!),
  );
}

// ── 014 ──────────────────────────────────────────────────────────────────

const double _kSizingAccount = 20000;
const double _kSizingRiskPct = 1;
const double _kSizingEntry = 480;

LessonPlayFrame _sizingFrame(double stop, LessonPlayCaps caps) {
  final budget = _kSizingAccount * _kSizingRiskPct / 100;
  final perShare = _kSizingEntry - stop;
  // Round DOWN, never up — the lesson says so, and rounding up is how a 1%
  // rule quietly becomes a 1.2% rule.
  final shares = perShare <= 0 ? 0 : (budget / perShare).floor();
  final notional = shares * _kSizingEntry;
  final ofAccount = notional / _kSizingAccount * 100;
  final cap = caps.effectiveSingleNameCapPct;

  return LessonPlayFrame(
    painter: (t, th) => BalanceScalePainter(
      t: t,
      theme: th,
      leftLabel: 'RISK/SH',
      leftValue: perShare,
      rightLabel: 'SHARES',
      rightValue: shares.toDouble(),
    ),
    readouts: [
      PlayReadout('RISK/SH', _money(perShare, decimals: 2)),
      PlayReadout('SHARES', '$shares', emphasis: true),
      PlayReadout('NOTIONAL', _money(notional)),
      PlayReadout('OF ACCOUNT', _pct(ofAccount)),
    ],
    breach: ofAccount > cap
        ? (l) => l.lessonPlayBreachSingleName(
            _pct(ofAccount), _pct(cap, decimals: 0))
        : null,
  );
}

// ── 015 ──────────────────────────────────────────────────────────────────

const double _kStopEntry = 246;
const double _kStopWickLow = 239.10;
const double _kStopInvalidationClose = 233.80;
const double _kStopFloor = 230;
const double _kStopCeil = 250;

/// The lesson's own two days: a dip to $239.10 that closes back at $244, then a
/// gap down that closes at $233.80.
const List<double> _kStopPath = [246, 244.5, 239.10, 244, 235, 233.80];

LessonPlayFrame _stopFrame(double stop, LessonPlayCaps caps) {
  double norm(double p) =>
      ((p - _kStopFloor) / (_kStopCeil - _kStopFloor)).clamp(0.0, 1.0);

  final perShare = _kStopEntry - stop;
  final shakenOut = stop >= _kStopWickLow;
  final thesisDead = stop >= _kStopInvalidationClose;

  return LessonPlayFrame(
    painter: (t, th) => ThresholdTriggerPainter(
      t: t,
      theme: th,
      level: norm(stop),
      triggerLabel: 'STOP',
      breach: false,
      path: [
        for (var i = 0; i < _kStopPath.length; i++)
          Offset(i / (_kStopPath.length - 1), norm(_kStopPath[i])),
      ],
    ),
    readouts: [
      PlayReadout('RISK/SH', _money(perShare, decimals: 2)),
      PlayReadout('WICK LOW', _money(_kStopWickLow, decimals: 2)),
      PlayReadout(
        'OUTCOME',
        shakenOut
            ? 'SHAKEN OUT'
            : (thesisDead ? 'EXIT ON CLOSE' : 'STILL IN'),
        emphasis: true,
      ),
    ],
    // Not a mandate breach — this one is the lesson's own falsification. A stop
    // above the noise wick fires on a day the thesis survived, which is the
    // exact failure the section calls "tighter than the stock's normal noise".
    breach: shakenOut
        ? (l) => l.lessonPlayBreachStopTooTight(
            _money(_kStopWickLow, decimals: 2), _money(244))
        : null,
  );
}

// ── 016 ──────────────────────────────────────────────────────────────────

const double _kRrEntry = 415;
const double _kRrStop = 407;

LessonPlayFrame _riskRewardFrame(double target, LessonPlayCaps caps) {
  final risk = _kRrEntry - _kRrStop;
  final reward = target - _kRrEntry;
  final rr = reward / risk;
  final breakEven = risk / (risk + reward) * 100;

  return LessonPlayFrame(
    painter: (t, th) => BalanceScalePainter(
      t: t,
      theme: th,
      leftLabel: 'RISK',
      leftValue: risk,
      rightLabel: 'REWARD',
      rightValue: reward,
    ),
    readouts: [
      PlayReadout('REWARD/SH', _money(reward)),
      PlayReadout('R:R', rr.toStringAsFixed(1), emphasis: true),
      PlayReadout('BREAK-EVEN WIN', _pct(breakEven, decimals: 0)),
    ],
    breach: rr < 1
        ? (l) => l.lessonPlayBreachRiskReward(
            _money(risk), _money(reward), _pct(breakEven, decimals: 0))
        : null,
  );
}

// ── 017 ──────────────────────────────────────────────────────────────────

const int _kCorrPositions = 5;
const double _kCorrPerPositionPct = 1;

LessonPlayFrame _correlationFrame(double rho, LessonPlayCaps caps) {
  const n = _kCorrPositions;
  final naive = n * _kCorrPerPositionPct;
  // Portfolio risk of n equal bets at pairwise correlation rho.
  final real = _kCorrPerPositionPct * math.sqrt(n + n * (n - 1) * rho);
  final independent = _kCorrPerPositionPct * math.sqrt(n.toDouble());
  final effectiveBets = n / (1 + (n - 1) * rho);
  final ceiling = caps.maxOpenRiskPct;

  return LessonPlayFrame(
    painter: (t, th) => ComparisonBarsPainter(
      t: t,
      theme: th,
      maxValue: naive,
      bars: [
        ComparisonBar(
          label: 'POSITION COUNT SAYS',
          value: naive,
          display: _pct(naive),
          muted: true,
        ),
        ComparisonBar(
          label: 'CORRELATION SAYS',
          value: real,
          display: _pct(real),
        ),
      ],
    ),
    readouts: [
      PlayReadout('REAL RISK', _pct(real), emphasis: true),
      PlayReadout('EFFECTIVE BETS', effectiveBets.toStringAsFixed(1)),
      PlayReadout('IF INDEPENDENT', _pct(independent)),
    ],
    // `max_open_risk_pct` is null-means-OFF (CR101-BE2), so an unset limit
    // draws no warning rather than one against a number nobody chose.
    breach: ceiling != null && real > ceiling
        ? (l) => l.lessonPlayBreachOpenRisk(
            _kCorrPositions, _pct(real), _pct(ceiling))
        : null,
  );
}

// ── 018 ──────────────────────────────────────────────────────────────────

LessonPlayFrame _drawdownFrame(double depthPct, LessonPlayCaps caps) {
  final d = depthPct / 100;
  final trough = 1 - d;
  final recover = trough <= 0 ? double.infinity : d / trough * 100;
  // Months at the lesson's 1%-per-month grind.
  final months =
      trough <= 0 ? double.infinity : math.log(1 / trough) / math.log(1.01);
  final ceilPct = caps.maxDrawdownPct;

  return LessonPlayFrame(
    painter: (t, th) => CurveDrawPainter(
      t: t,
      theme: th,
      points: [
        const Offset(0, 1),
        const Offset(0.16, 0.97),
        Offset(0.44, trough),
        Offset(0.58, trough + d * 0.18),
        Offset(0.8, 1 - d * 0.45),
        const Offset(1, 1),
      ],
      flags: [
        CurveFlag(0.44, '-${depthPct.round()}%'),
        CurveFlag(1, recover.isFinite ? '+${_pct(recover, decimals: 0)}' : '—'),
      ],
    ),
    readouts: [
      PlayReadout('GAIN TO FLAT',
          recover.isFinite ? '+${_pct(recover)}' : '—', emphasis: true),
      PlayReadout('AT 1%/MONTH',
          months.isFinite ? '${months.round()} mo' : '—'),
      PlayReadout('LEFT OF PEAK', _pct(trough * 100)),
    ],
    breach: ceilPct != null && depthPct > ceilPct
        ? (l) => l.lessonPlayBreachDrawdownCeiling(
            ceilPct, depthPct.round(), (depthPct - ceilPct).round())
        : null,
  );
}
