/// CR013 (E3/D1) — the shared chassis for coded lesson animations (D-061:
/// CustomPainter, no Lottie). `AmiAnimation` frames a fixed-height canvas in an
/// `AccentCard`, drives a single controller, plays once when scrolled ≥60% into
/// view, and offers tap / icon replay. `AmiAnimTheme` bundles the on-system
/// palette + label style so every primitive renders in the design language
/// without each painter reaching into `ami_theme.dart`.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:flutter/material.dart';

/// Palette + metrics handed to every primitive so painters stay on-system.
class AmiAnimTheme {
  const AmiAnimTheme({
    required this.accent,
    required this.grid,
    required this.surface,
    required this.textHigh,
    required this.textMed,
    required this.textLow,
    required this.label,
    this.stroke = 3.0,
    this.thinStroke = 1.5,
  });

  /// The lesson's dominant accent (role/family colour or a semantic accent).
  final Color accent;

  /// Axes / gridlines / dashed levels.
  final Color grid;
  final Color surface;
  final Color textHigh;
  final Color textMed;
  final Color textLow;

  /// `labelMono` — use for on-canvas callouts.
  final TextStyle label;

  final double stroke;
  final double thinStroke;

  factory AmiAnimTheme.forAccent(Color accent) => AmiAnimTheme(
        accent: accent,
        grid: AmiColors.slate700,
        surface: AmiColors.slate800,
        textHigh: AmiColors.textHigh,
        textMed: AmiColors.textMed,
        textLow: AmiColors.textLow,
        label: AmiTypography.labelMono,
      );
}

/// Signature every primitive is built through: given the eased progress `t`
/// (0→1) and the theme, return the `CustomPainter` for this frame.
typedef AmiAnimPainterBuilder = CustomPainter Function(
    double t, AmiAnimTheme theme);

class AmiAnimation extends StatefulWidget {
  const AmiAnimation({
    super.key,
    required this.painterBuilder,
    required this.accent,
    this.caption,
    this.duration = const Duration(milliseconds: 2400),
    this.curve = Curves.easeInOutCubic,
    this.height = 200,
  });

  final AmiAnimPainterBuilder painterBuilder;
  final Color accent;
  final String? caption;
  final Duration duration;
  final Curve curve;
  final double height;

  @override
  State<AmiAnimation> createState() => _AmiAnimationState();
}

class _AmiAnimationState extends State<AmiAnimation>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller =
      AnimationController(vsync: this, duration: widget.duration);
  late final Animation<double> _curved =
      CurvedAnimation(parent: _controller, curve: widget.curve);

  ScrollPosition? _position;
  bool _played = false;

  @override
  void initState() {
    super.initState();
    // Play once for animations already on-screen at first layout.
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybePlay());
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Attach to the enclosing scrollable so we can detect scroll-into-view
    // without a visibility-detector dependency.
    final newPos = Scrollable.maybeOf(context)?.position;
    if (newPos != _position) {
      _position?.removeListener(_maybePlay);
      _position = newPos;
      _position?.addListener(_maybePlay);
    }
  }

  void _maybePlay() {
    if (_played || !mounted) return;
    final box = context.findRenderObject() as RenderBox?;
    if (box == null || !box.hasSize) return;
    final screenH = MediaQuery.of(context).size.height;
    final top = box.localToGlobal(Offset.zero).dy;
    final h = box.size.height;
    final visible =
        (top + h).clamp(0.0, screenH) - top.clamp(0.0, screenH);
    if (visible >= 0.6 * h) {
      _played = true;
      _controller.forward(from: 0);
    }
  }

  void _replay() => _controller.forward(from: 0);

  @override
  void dispose() {
    _position?.removeListener(_maybePlay);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = AmiAnimTheme.forAccent(widget.accent);
    return AccentCard(
      accent: widget.accent,
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          GestureDetector(
            onTap: _replay,
            child: SizedBox(
              height: widget.height,
              width: double.infinity,
              child: Stack(
                children: [
                  Positioned.fill(
                    child: AnimatedBuilder(
                      animation: _curved,
                      builder: (_, __) => CustomPaint(
                        painter: widget.painterBuilder(_curved.value, theme),
                        size: Size.infinite,
                      ),
                    ),
                  ),
                  Positioned(
                    top: 4,
                    right: 4,
                    child: IconButton(
                      tooltip: AppLocalizations.of(context).lessonReplay,
                      icon: const Icon(Icons.replay, size: 18),
                      color: AmiColors.textLow,
                      visualDensity: VisualDensity.compact,
                      onPressed: _replay,
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (widget.caption != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(
                  AmiSpacing.m, 0, AmiSpacing.m, AmiSpacing.s),
              child: Text(
                widget.caption!,
                textAlign: TextAlign.center,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.textMed, fontSize: 11),
              ),
            ),
        ],
      ),
    );
  }
}
