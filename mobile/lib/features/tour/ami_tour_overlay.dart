/// DEF382 — AMI's own coach-mark overlay, replacing `TutorialCoachMark`.
///
/// Why this file exists: interacting with a first-run tour from the third-party
/// coach-mark package it replaces destroyed the app's entire iOS accessibility tree, permanently, with
/// the app still in the foreground — `page_source` collapsed from ~13 KB with
/// all four bottom-nav identifiers to 1.5 KB of bare `Other` nodes. The failure
/// was inside the package's overlay, not at our call sites: two structurally
/// identical configurations, one died and one lived. Two explanations were
/// formed and refuted on controlled arms, so the package is gone rather than
/// patched.
///
/// What this replaces, one for one:
///   * `TargetFocus`            -> [AmiTourStep]
///   * `TutorialCoachMark(...)` -> [showAmiTour]
///   * `TutorialCoachMarkController` -> [AmiTourController] (only `next`/`skip`,
///     which is the whole surface `TourCard` ever used)
///   * `beforeFocus` + `Scrollable.ensureVisible` from every screen, now here.
///
/// The dimmed barrier is painted with a cutout at the target's rect via
/// `BlendMode.clear` inside a `saveLayer`, so the hole is a real hole and not a
/// faked lighter rectangle. The entry is removed on finish AND on skip AND when
/// a step's target has vanished — a leaked entry is the shape of this defect.
/// "Vanished" covers both cases (DEF395): a target already gone when the step
/// is reached, and one that disappears while its step is on screen. The second
/// was missed on the first pass and left a full-screen dim with no hole.
library;

import 'package:flutter/material.dart';

/// Shape of the spotlight cutout.
enum AmiTourShape { rect, roundedRect }

/// Where the card sits relative to the target.
enum AmiTourAlign { top, bottom }

/// The controller given to a step's builder. Exactly what `TourCard` uses.
abstract class AmiTourController {
  void next();

  void skip();
}

/// One coach-mark step: which widget to spotlight, and what to say about it.
class AmiTourStep {
  const AmiTourStep({
    required this.identify,
    required this.target,
    required this.builder,
    this.shape = AmiTourShape.rect,
    this.radius = 0,
    this.paddingFocus = 0,
    this.align = AmiTourAlign.bottom,
    this.absoluteTop,
  });

  /// Stable name for the step, kept from the old `TargetFocus.identify`.
  final String identify;

  /// The widget to spotlight.
  final GlobalKey target;

  /// The card, given the controller so its buttons can drive the tour.
  final AmiTourCardBuilder builder;

  final AmiTourShape shape;
  final double radius;
  final double paddingFocus;
  final AmiTourAlign align;

  /// Replaces the old `ContentAlign.custom` +
  /// `CustomTargetContentPosition(top: ...)`: pin the card at this absolute
  /// y instead of anchoring it to the target. Used by the Journal's list step,
  /// whose target fills the screen so neither `top` nor `bottom` fits.
  final double? absoluteTop;
}

typedef AmiTourCardBuilder =
    Widget Function(BuildContext context, AmiTourController controller);

/// Shows a tour over [context]'s root overlay.
///
/// [onFinish] fires when the last step is advanced past, not on [skip] — the
/// same distinction every screen relies on to show its completion toast.
Future<void> showAmiTour({
  required BuildContext context,
  required List<AmiTourStep> steps,
  Color barrierColor = Colors.black,
  double barrierOpacity = 0.88,
  VoidCallback? onFinish,
}) async {
  if (steps.isEmpty) return;
  final overlay = Overlay.maybeOf(context, rootOverlay: true);
  if (overlay == null) return;

  late final OverlayEntry entry;
  entry = OverlayEntry(
    builder: (_) => AmiTourOverlay(
      steps: steps,
      barrierColor: barrierColor,
      barrierOpacity: barrierOpacity,
      onFinish: onFinish,
      onDismiss: () {
        if (entry.mounted) entry.remove();
      },
    ),
  );
  overlay.insert(entry);
}

/// The overlay's own widget. Public so a test can assert it is GONE from the
/// tree after skip/finish — a leaked entry is precisely DEF382's failure mode.
class AmiTourOverlay extends StatefulWidget {
  const AmiTourOverlay({
    super.key,
    required this.steps,
    required this.barrierColor,
    required this.barrierOpacity,
    required this.onFinish,
    required this.onDismiss,
  });

  final List<AmiTourStep> steps;
  final Color barrierColor;
  final double barrierOpacity;
  final VoidCallback? onFinish;
  final VoidCallback onDismiss;

  @override
  State<AmiTourOverlay> createState() => _AmiTourOverlayState();
}

class _AmiTourOverlayState extends State<AmiTourOverlay>
    implements AmiTourController {
  int _index = -1;
  Rect? _rect;
  bool _closed = false;

  /// Frames spent waiting for a target to lay out before we give up on it.
  int _settleFrames = 0;
  static const _maxSettleFrames = 8;

  /// DEF395 — whether any step was ever actually put on screen. `_focus`
  /// steps OVER a target that is already gone, so a tour whose targets are all
  /// unmounted walks straight off the end and reaches the same `_close` the
  /// last "Got it" tap does. Firing `onFinish` there shows the completion
  /// toast, and marks the tour seen, for a tour the user was never shown.
  bool _shownAny = false;

  AmiTourStep? get _step => _index < 0 ? null : widget.steps[_index];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _focus(0));
  }

  @override
  void dispose() {
    _closed = true;
    super.dispose();
  }

  void _close({required bool finished}) {
    if (_closed) return;
    _closed = true;
    widget.onDismiss();
    if (finished) widget.onFinish?.call();
  }

  @override
  void next() {
    if (_closed) return;
    if (_index >= widget.steps.length - 1) {
      _close(finished: true);
    } else {
      _focus(_index + 1);
    }
  }

  @override
  void skip() => _close(finished: false);

  /// Scrolls [target] into view (behaviour carried over from the screens' old
  /// `beforeFocus`) and then focuses the step. A step whose target is gone is
  /// stepped over rather than shown with a full-screen dim.
  Future<void> _focus(int index) async {
    while (index < widget.steps.length) {
      final step = widget.steps[index];
      final ctx = step.target.currentContext;
      if (ctx != null && ctx.mounted) {
        if (Scrollable.maybeOf(ctx) != null) {
          final tooltipAbove = step.align == AmiTourAlign.top;
          try {
            await Scrollable.ensureVisible(
              ctx,
              duration: const Duration(milliseconds: 350),
              alignment: tooltipAbove ? 0.85 : 0.15,
            );
          } catch (_) {
            // A detached scrollable mid-navigation. Show the step where it is.
          }
        }
        if (!mounted || _closed) return;
        setState(() {
          _index = index;
          _rect = null;
          _settleFrames = 0;
          _shownAny = true;
        });
        _scheduleRectRefresh();
        return;
      }
      index++;
    }
    // DEF395 — `finished` means "the user reached the end", not "the loop did".
    _close(finished: _shownAny);
  }

  /// Reads the target's rect after layout and repaints if it moved. The barrier
  /// swallows every tap, so the user cannot scroll underneath; the rect moves
  /// only from our own `ensureVisible` or a late first layout.
  ///
  /// DEF395 — this re-arms itself ONLY while still waiting for a rect, so it
  /// stops once the target has settled. An earlier version of this comment
  /// claimed it re-ran on "an orientation change" too; it does not, and the
  /// cutout would keep stale coordinates across a rotation. That is currently
  /// unreachable rather than fixed: `main.dart:69` locks the app to
  /// `portraitUp` for the alpha. If that lock is ever lifted, this needs a
  /// `WidgetsBindingObserver.didChangeMetrics` re-arm — do not assume the
  /// post-frame callback covers it.
  void _scheduleRectRefresh() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || _closed) return;
      final step = _step;
      if (step == null) return;
      final next = _rectFor(step);
      final waiting = next == null && _settleFrames < _maxSettleFrames;
      if (next == null && !waiting) {
        // DEF395 — the target is gone and we have stopped waiting for it.
        // Leaving `_rect` null here paints the barrier with NO hole: a
        // full-screen dim over a step pointing at nothing. `_focus` already
        // knows how to step over a dead target, so hand back to it; it closes
        // the tour if none remain. Found by the CR215 foreign auditor —
        // `_focus`'s skip only ran at step TRANSITIONS, never mid-display.
        _focus(_index + 1);
        return;
      }
      if (next != _rect || waiting) {
        setState(() {
          _settleFrames = next == null ? _settleFrames + 1 : _settleFrames;
          _rect = next;
        });
      }
      // DEF395 — re-arm for as long as the tour is open, not only while still
      // waiting for a first rect. The old version stopped the chain the moment
      // a target settled, so NOTHING was watching afterwards and a target that
      // left the tree mid-step was never noticed — the branch above could not
      // fire because no callback was ever scheduled again. This does NOT force
      // frames: `addPostFrameCallback` runs after the next frame the app
      // produces anyway, and a vanishing target always produces one.
      _scheduleRectRefresh();
    });
  }

  /// The target's rect IN THE OVERLAY'S OWN COORDINATES. The scrim paints
  /// inside this entry, so a global rect would be wrong the moment the overlay
  /// is not fullscreen-at-origin; transforming against the entry's box keeps it
  /// right either way.
  Rect? _rectFor(AmiTourStep step) {
    final ctx = step.target.currentContext;
    if (ctx == null) return null;
    final box = ctx.findRenderObject();
    if (box is! RenderBox || !box.hasSize || !box.attached) return null;
    final origin = box.localToGlobal(Offset.zero, ancestor: _overlayBox);
    return (origin & box.size).inflate(step.paddingFocus);
  }

  /// The entry's own box, captured in `build` before any post-frame read.
  RenderBox? _overlayBox;

  @override
  Widget build(BuildContext context) {
    final step = _step;
    return LayoutBuilder(
      builder: (context, constraints) {
        final box = context.findRenderObject();
        if (box is RenderBox) _overlayBox = box;
        final size = constraints.biggest;
        return Stack(
          children: [
            Positioned.fill(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                // The dim absorbs every tap: nothing under the tour is
                // reachable until Skip or Next, which is what the harness and
                // the first-run flow both assume.
                onTap: () {},
                child: CustomPaint(
                  painter: _ScrimPainter(
                    color: widget.barrierColor,
                    opacity: widget.barrierOpacity,
                    hole: _rect,
                    shape: step?.shape ?? AmiTourShape.rect,
                    radius: step?.radius ?? 0,
                  ),
                ),
              ),
            ),
            if (step != null) _card(step, size),
          ],
        );
      },
    );
  }

  Widget _card(AmiTourStep step, Size size) {
    final gap = step.paddingFocus + 8;
    final rect = _rect;
    final double? top;
    final double? bottom;
    if (step.absoluteTop != null) {
      top = step.absoluteTop;
      bottom = null;
    } else if (rect == null) {
      top = size.height * 0.35;
      bottom = null;
    } else if (step.align == AmiTourAlign.top) {
      bottom = (size.height - rect.top + gap).clamp(8.0, size.height - 80.0);
      top = null;
    } else {
      top = (rect.bottom + gap).clamp(8.0, size.height - 80.0);
      bottom = null;
    }
    return Positioned(
      left: 0,
      right: 0,
      top: top,
      bottom: bottom,
      child: step.builder(context, this),
    );
  }
}

class _ScrimPainter extends CustomPainter {
  _ScrimPainter({
    required this.color,
    required this.opacity,
    required this.hole,
    required this.shape,
    required this.radius,
  });

  final Color color;
  final double opacity;
  final Rect? hole;
  final AmiTourShape shape;
  final double radius;

  @override
  void paint(Canvas canvas, Size size) {
    final bounds = Offset.zero & size;
    // The clear blend only erases inside this layer, which is what turns the
    // hole into a genuine gap rather than a lighter patch.
    canvas.saveLayer(bounds, Paint());
    canvas.drawRect(
      bounds,
      Paint()..color = color.withValues(alpha: opacity),
    );
    final h = hole;
    if (h != null && !h.isEmpty) {
      final path = Path();
      if (shape == AmiTourShape.roundedRect) {
        path.addRRect(
          RRect.fromRectAndRadius(
            h,
            Radius.circular(radius.clamp(0.0, double.infinity)),
          ),
        );
      } else {
        path.addRect(h);
      }
      canvas.drawPath(path, Paint()..blendMode = BlendMode.clear);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_ScrimPainter old) =>
      old.color != color ||
      old.opacity != opacity ||
      old.hole != hole ||
      old.shape != shape ||
      old.radius != radius;
}
