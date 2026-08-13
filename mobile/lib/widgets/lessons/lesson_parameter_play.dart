/// CR174 §4 — the card where the learner moves the number the prose asks them
/// to imagine.
///
/// **Formative, never scored.** CR174's hard rule splits interactions in two:
/// anything that moves an agent-unlock gate stays a batch submit answered by
/// the server (DEF042's posture), and everything else may resolve on device for
/// the instant loop. This is the second kind — it grades nothing, unlocks
/// nothing, and posts nothing. That is what buys it the right to respond on the
/// same frame as the drag.
///
/// **RTL is a build gate here, not a follow-up (acceptance #8).** A
/// `CustomPaint` canvas does not mirror under `dir=rtl` — and should not, since
/// time axes stay left-to-right in Arabic financial practice, which is why
/// `drawLabel` already pins `TextDirection.ltr`. A Material `Slider` *does*
/// mirror. Ship both defaults and the gesture inverts silently, in Arabic only:
/// dragging toward the "tighter stop" side moves the stop the wrong way. So the
/// control is wrapped in an explicit LTR [Directionality] — pinned to the
/// visual it drives, not to the page — and `cr174_rtl_test.dart` asserts that
/// the same drag produces the same value under `ar` as under `en`.
///
/// Numeric readouts get the same isolation for the second reason the CR
/// records: a Latin-numeral run inside RTL prose reorders, and
/// `$480 − $459 = $21` is exactly the shape that mangles.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/lessons/ami_animation.dart';
import 'package:ami_trade/widgets/lessons/lesson_play.dart';
import 'package:flutter/material.dart';

class LessonParameterPlay extends StatefulWidget {
  const LessonParameterPlay({
    super.key,
    required this.play,
    required this.caps,
  });

  final LessonPlay play;
  final LessonPlayCaps caps;

  @override
  State<LessonParameterPlay> createState() => _LessonParameterPlayState();
}

class _LessonParameterPlayState extends State<LessonParameterPlay> {
  late double _value = widget.play.initial;

  @override
  Widget build(BuildContext context) {
    final play = widget.play;
    final l = AppLocalizations.of(context);
    final frame = play.build(_value, widget.caps);
    final theme = AmiAnimTheme.forAccent(play.accent);
    final breach = frame.breach?.call(l);

    return AccentCard(
      accent: play.accent,
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
                AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, 0),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    play.controlLabel,
                    style: AmiTypography.labelMono
                        .copyWith(fontSize: 11, color: play.accent),
                  ),
                ),
                _Ltr(
                  child: Text(
                    play.formatValue(_value),
                    style: AmiTypography.statMid
                        .copyWith(fontSize: 20, color: AmiColors.textHigh),
                  ),
                ),
              ],
            ),
          ),
          SizedBox(
            height: play.height,
            width: double.infinity,
            // `t: 1` — the drawing-in reveal belongs to an animation the learner
            // watches. This one they drive, so it is always fully drawn and the
            // only thing that moves is what they moved.
            child: CustomPaint(
              painter: frame.painter(1, theme),
              size: Size.infinite,
            ),
          ),
          // The control is pinned to the canvas's direction, not the page's.
          // `width: infinity` is load-bearing rather than cosmetic: this Column
          // is `CrossAxisAlignment.start`, which hands children loose
          // constraints, and a `Slider` under loose constraints falls back to
          // its ~144pt preferred width and sits against the reading-start edge
          // — a different edge in each language, so the same drag would travel
          // a different distance in Arabic.
          _Ltr(
            child: SizedBox(
              width: double.infinity,
              child: SliderTheme(
              data: SliderTheme.of(context).copyWith(
                activeTrackColor: play.accent,
                inactiveTrackColor: AmiColors.slate700,
                thumbColor: play.accent,
                overlayColor: play.accent.withValues(alpha: 0.15),
                trackHeight: 3,
              ),
                child: Slider(
                  value: _value,
                  min: play.min,
                  max: play.max,
                  divisions: play.divisions,
                  onChanged: (v) => setState(() => _value = v),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
            child: Text(
              l.lessonPlayDragHint,
              style: AmiTypography.labelMono
                  .copyWith(fontSize: 10, color: AmiColors.textLow),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(
                AmiSpacing.m, AmiSpacing.s, AmiSpacing.m, AmiSpacing.m),
            child: Wrap(
              spacing: AmiSpacing.m,
              runSpacing: AmiSpacing.s,
              children: [
                for (final r in frame.readouts) _Readout(readout: r),
              ],
            ),
          ),
          if (breach != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AmiSpacing.m),
              decoration: const BoxDecoration(
                color: AmiColors.slate900,
                border: BorderDirectional(
                  top: BorderSide(color: AmiColors.hexAmber, width: 2),
                ),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.report_gmailerrorred,
                      color: AmiColors.hexAmber, size: 18),
                  const SizedBox(width: AmiSpacing.s),
                  Expanded(
                    child: Text(breach,
                        style: AmiTypography.caption
                            .copyWith(color: AmiColors.hexAmber)),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Readout extends StatelessWidget {
  const _Readout({required this.readout});
  final PlayReadout readout;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          readout.label,
          style: AmiTypography.labelMono
              .copyWith(fontSize: 9, color: AmiColors.textLow),
        ),
        const SizedBox(height: 2),
        _Ltr(
          child: Text(
            readout.value,
            style: AmiTypography.labelMono.copyWith(
              fontSize: readout.emphasis ? 16 : 13,
              color:
                  readout.emphasis ? AmiColors.textHigh : AmiColors.textMed,
            ),
          ),
        ),
      ],
    );
  }
}

/// Numeric isolation. A Latin-numeral run reorders inside RTL prose, so every
/// figure the model produces is rendered in its own LTR island.
class _Ltr extends StatelessWidget {
  const _Ltr({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) =>
      Directionality(textDirection: TextDirection.ltr, child: child);
}
