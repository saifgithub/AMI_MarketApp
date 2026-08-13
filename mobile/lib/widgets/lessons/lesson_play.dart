/// CR174 §4 — the type a parameter-bound visual is authored as.
///
/// The CR's claim is that **a new visual is a registry entry — data, not painter
/// code**. This file is what makes that true: a [LessonPlay] is a control range
/// plus one pure function from the control's value to a frame (a painter, a set
/// of readouts, and whether the learner has just pushed past their own mandated
/// floor). No `LessonPlay` may contain a widget.
///
/// The diagnosis this answers is specific. `014_position_sizing_basics` line 33
/// says *"if you had set the stop at $470 instead, per-share risk drops to $10
/// and shares jump to 20"* — a slider described in prose — while the animation
/// beside it renders `BalanceScalePainter(leftValue: 2, rightValue: 2)`, a
/// generic scale that never shows the lesson's own figures. Binding the painter
/// to the lesson's real numbers is the entire fix.
///
/// **The frame is pure and takes the learner's caps as an argument** rather than
/// reading a provider. CR101 made the risk caps user-settable, and CR174 §7 asks
/// the model to teach with *the learner's* caps rather than a constant — which
/// is D-030's mandate personalisation at zero LLM cost. Purity is what lets a
/// test assert the sizing math against the lesson's published figures without
/// standing up a widget tree.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:flutter/material.dart';

/// A sentence the model wants to say, deferred until there is a locale to say
/// it in.
///
/// The frame is computed in a pure function with no `BuildContext`, but a breach
/// is prose the learner reads — it belongs in the ARB like every other sentence,
/// not baked into Dart in English. Handing back a closure over the generated
/// getter keeps the resolution type-safe (a renamed key fails to compile) and
/// avoids the alternative, a stringly-typed id plus a switch that grows a silent
/// default branch the first time someone forgets a case.
typedef LessonPlayMessage = String Function(AppLocalizations l);

/// The single-name position cap the backend falls back to when a user has set
/// none. Mirrors `SINGLE_NAME_ABSOLUTE_CAP_PCT` in
/// `backend/app/trading_math/sizing.py` — a backstop, not a default anyone
/// chose, which is why a model that hits it says so rather than silently
/// clamping.
const double kSingleNameAbsoluteCapPct = 50.0;

/// What the model is allowed to know about this learner.
///
/// Every field is nullable-with-a-stated-meaning because CR101 draws a
/// distinction the UI must not flatten: `null` on a cap means *"following your
/// risk profile"* (the server applies a preset it does not publish a number
/// for), while `null` on a limit means *OFF, not enforced at all*.
class LessonPlayCaps {
  const LessonPlayCaps({
    this.singleNameCapPct,
    this.maxDrawdownPct,
    this.maxOpenRiskPct,
  });

  /// CR101-BE1. Null → fall back to [kSingleNameAbsoluteCapPct], the backstop.
  final double? singleNameCapPct;

  /// Always set on a real mandate (defaults to 30 server-side).
  final int? maxDrawdownPct;

  /// CR101-BE2. Null means **off** — draw no ceiling rather than invent one.
  final double? maxOpenRiskPct;

  double get effectiveSingleNameCapPct =>
      singleNameCapPct ?? kSingleNameAbsoluteCapPct;

  static const LessonPlayCaps unknown = LessonPlayCaps();
}

/// One number the model wants read off the visual.
class PlayReadout {
  const PlayReadout(this.label, this.value, {this.emphasis = false});

  /// A short mono token in the same register as the on-canvas labels the seven
  /// shipped painters already use (`RISK`, `SIZE`, `STOP`). Not translated, for
  /// the same reason those are not: they are chart furniture, and the CR
  /// records Arabic glyph coverage as an open dependency rather than a solved
  /// one.
  final String label;

  /// Already formatted. Rendered LTR-isolated — a Latin-numeral run inside RTL
  /// prose reorders otherwise, and `$480 − $459 = $21` is exactly the shape
  /// that mangles.
  final String value;

  final bool emphasis;
}

/// What the control's current value produces.
class LessonPlayFrame {
  const LessonPlayFrame({
    required this.painter,
    required this.readouts,
    this.breach,
  });

  final AmiAnimPainterBuilder painter;
  final List<PlayReadout> readouts;

  /// Set when this value takes the learner past a limit **their own mandate
  /// carries**, or past the lesson's own stated falsification. Null when it
  /// does not, and null when the mandate is unknown — a warning we cannot
  /// substantiate is worse than none (CR040).
  final LessonPlayMessage? breach;
}

typedef LessonPlayBuilder = LessonPlayFrame Function(
    double value, LessonPlayCaps caps);

class LessonPlay {
  const LessonPlay({
    required this.accent,
    required this.controlLabel,
    required this.min,
    required this.max,
    required this.step,
    required this.initial,
    required this.formatValue,
    required this.build,
    this.height = 190,
  });

  final Color accent;

  /// Short mono token naming what the control moves (`STOP`, `TARGET`).
  final String controlLabel;

  final double min;
  final double max;

  /// Discrete step, so the readouts land on the lesson's published figures
  /// rather than near them.
  final double step;

  /// Where the control starts — **the lesson's own worked example**, so the
  /// first frame the learner sees reproduces the numbers the prose states.
  final double initial;

  final String Function(double) formatValue;
  final LessonPlayBuilder build;
  final double height;

  int get divisions => ((max - min) / step).round().clamp(1, 1000);
}
