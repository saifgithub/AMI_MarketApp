/// AnimationRegistry — maps `<Animation name="..." />` keys (lesson MDX →
/// `LessonBlock.animationName`) to a coded `AmiAnimation` builder.
///
/// CR013 (E3/D1, D-061): animations are coded Flutter (`CustomPainter`), not
/// Lottie — so the value type is a `WidgetBuilder` returning a parameterised
/// `AmiAnimation`, not an asset path. Per-slot params (series shapes, labels,
/// captions, accent) are authored inline here against each lesson's content.
/// Unknown names fall back to `AmiHexPlaceholder` in `AnimationBlock`.
///
/// Keys are lowercase snake_case and stable — every translation of every lesson
/// references them.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/anim/balance_scale_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/candle_anatomy_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/constellation_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/curve_draw_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/oscillator_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/sequence_painter.dart';
import 'package:ami_trade/widgets/lessons/anim/threshold_trigger_painter.dart';
import 'package:flutter/material.dart';

class AnimationRegistry {
  AnimationRegistry._();

  static final Map<String, WidgetBuilder> _builders = <String, WidgetBuilder>{
    // ── Primitive 1 — CurveDrawPainter ──────────────────────────────────
    'compounding_curve': (_) => AmiAnimation(
          accent: AmiColors.hexGreen,
          caption: 'Patience compounds',
          duration: const Duration(milliseconds: 2600),
          painterBuilder: (t, th) => CurveDrawPainter(
            t: t,
            theme: th,
            points: const [
              Offset(0, 0.03),
              Offset(0.25, 0.08),
              Offset(0.5, 0.2),
              Offset(0.7, 0.4),
              Offset(0.85, 0.66),
              Offset(1, 0.95),
            ],
            flags: const [CurveFlag(0.85, 'exponential')],
          ),
        ),
    'fomo_curve': (_) => AmiAnimation(
          accent: AmiColors.hexAmber,
          caption: 'FOMO buys the top',
          painterBuilder: (t, th) => CurveDrawPainter(
            t: t,
            theme: th,
            points: const [
              Offset(0, 0.1),
              Offset(0.3, 0.16),
              Offset(0.55, 0.28),
              Offset(0.75, 0.52),
              Offset(0.9, 0.88),
              Offset(1, 0.95),
            ],
            flags: const [CurveFlag(0.9, 'you buy here')],
          ),
        ),
    'pump_dump_curve': (_) => AmiAnimation(
          accent: AmiColors.hexRed,
          caption: 'Pump, then dump',
          painterBuilder: (t, th) => CurveDrawPainter(
            t: t,
            theme: th,
            points: const [
              Offset(0, 0.15),
              Offset(0.25, 0.22),
              Offset(0.45, 0.55),
              Offset(0.55, 0.92),
              Offset(0.7, 0.5),
              Offset(0.85, 0.2),
              Offset(1, 0.08),
            ],
            flags: const [CurveFlag(0.55, 'pump'), CurveFlag(1, 'dump')],
          ),
        ),
    'drawdown_recovery': (_) => AmiAnimation(
          accent: AmiColors.hexBlue,
          caption: 'Drawdown & recovery',
          painterBuilder: (t, th) => CurveDrawPainter(
            t: t,
            theme: th,
            points: const [
              Offset(0, 0.72),
              Offset(0.25, 0.5),
              Offset(0.45, 0.24),
              Offset(0.6, 0.3),
              Offset(0.8, 0.56),
              Offset(1, 0.78),
            ],
            flags: const [
              CurveFlag(0.45, 'drawdown'),
              CurveFlag(1, 'recovery'),
            ],
          ),
        ),

    // ── Primitive 2 — ThresholdTriggerPainter ───────────────────────────
    'stop_loss_trigger': (_) => AmiAnimation(
          accent: AmiColors.hexRed,
          caption: 'The stop protects you',
          painterBuilder: (t, th) => ThresholdTriggerPainter(
            t: t,
            theme: th,
            level: 0.26,
            triggerLabel: 'STOP',
            breach: false,
            path: const [
              Offset(0, 0.76),
              Offset(0.3, 0.6),
              Offset(0.6, 0.42),
              Offset(0.85, 0.3),
              Offset(1, 0.25),
            ],
          ),
        ),
    'support_resistance_test': (_) => AmiAnimation(
          accent: AmiColors.hexCyan,
          caption: 'Testing support',
          painterBuilder: (t, th) => ThresholdTriggerPainter(
            t: t,
            theme: th,
            level: 0.35,
            triggerLabel: 'SUPPORT',
            breach: false,
            path: const [
              Offset(0, 0.75),
              Offset(0.25, 0.55),
              Offset(0.5, 0.38),
              Offset(0.65, 0.36),
              Offset(0.82, 0.52),
              Offset(1, 0.64),
            ],
          ),
        ),
    'breakout_pattern': (_) => AmiAnimation(
          accent: AmiColors.hexGreen,
          caption: 'The breakout',
          painterBuilder: (t, th) => ThresholdTriggerPainter(
            t: t,
            theme: th,
            level: 0.6,
            triggerLabel: 'RESISTANCE',
            breach: true,
            path: const [
              Offset(0, 0.3),
              Offset(0.3, 0.45),
              Offset(0.55, 0.56),
              Offset(0.72, 0.6),
              Offset(0.85, 0.74),
              Offset(1, 0.92),
            ],
          ),
        ),

    // ── Primitive 3 — BalanceScalePainter ───────────────────────────────
    'position_size_calc': (_) => AmiAnimation(
          accent: AmiColors.hexCyan,
          caption: 'Sizing to your risk',
          painterBuilder: (t, th) => BalanceScalePainter(
            t: t,
            theme: th,
            leftLabel: 'RISK',
            leftValue: 2,
            rightLabel: 'SIZE',
            rightValue: 2,
          ),
        ),
    'risk_reward_scale': (_) => AmiAnimation(
          accent: AmiColors.hexAmber,
          caption: 'Risk vs. reward',
          painterBuilder: (t, th) => BalanceScalePainter(
            t: t,
            theme: th,
            leftLabel: 'RISK',
            leftValue: 1,
            rightLabel: 'REWARD',
            rightValue: 3,
          ),
        ),

    // ── Primitive 4 — OscillatorPainter ─────────────────────────────────
    'rsi_oscillator': (_) => AmiAnimation(
          accent: AmiColors.hexPurple,
          caption: 'RSI: overbought / oversold',
          painterBuilder: (t, th) => OscillatorPainter(
            t: t,
            theme: th,
            band: true,
            series: const [
              0.5, 0.66, 0.8, 0.62, 0.42, 0.26, 0.34, 0.56, 0.74, 0.6, 0.44, 0.5,
            ],
          ),
        ),
    'moving_average_lag': (_) => AmiAnimation(
          accent: AmiColors.hexBlue,
          caption: 'The average lags the price',
          painterBuilder: (t, th) => OscillatorPainter(
            t: t,
            theme: th,
            companionWindow: 4,
            series: const [
              0.3, 0.36, 0.31, 0.44, 0.52, 0.46, 0.6, 0.68, 0.62, 0.74, 0.82, 0.86,
            ],
          ),
        ),

    // ── Primitive 5 — CandleAnatomyPainter ──────────────────────────────
    'candlestick_anatomy': (_) => AmiAnimation(
          accent: AmiColors.hexGreen,
          caption: 'Anatomy of a candle',
          duration: const Duration(milliseconds: 2800),
          painterBuilder: (t, th) =>
              CandleAnatomyPainter(t: t, theme: th, bullish: true),
        ),

    // ── Primitive 6 — SequencePainter ───────────────────────────────────
    'bull_bear_states': (_) => AmiAnimation(
          accent: AmiColors.hexGreen,
          caption: 'Bull & bear regimes',
          duration: const Duration(milliseconds: 3000),
          painterBuilder: (t, th) => SequencePainter(
            t: t,
            theme: th,
            stages: const ['BULL', 'BEAR', 'BULL'],
          ),
        ),
    'revenge_position_escalation': (_) => AmiAnimation(
          accent: AmiColors.hexRed,
          caption: 'Revenge trading escalates',
          duration: const Duration(milliseconds: 3000),
          painterBuilder: (t, th) => SequencePainter(
            t: t,
            theme: th,
            escalate: true,
            stages: const ['1×', '2×', '4×', '8×'],
          ),
        ),

    // ── Primitive 7 — ConstellationPainter ──────────────────────────────
    'ami_constellation': (_) => AmiAnimation(
          accent: AmiColors.hexPink,
          caption: 'Your desk of 12 analysts',
          duration: const Duration(milliseconds: 3200),
          painterBuilder: (t, th) => ConstellationPainter(t: t, theme: th),
        ),
  };

  /// The builder for `name`, or null when nothing is registered (caller falls
  /// back to the hex placeholder).
  static WidgetBuilder? builderFor(String name) =>
      _builders[name.toLowerCase()];

  /// Whether a coded animation is registered for `name`.
  static bool has(String name) => _builders.containsKey(name.toLowerCase());
}
