/// CR015 (E4/D7 / C4) — HexToast: the AMI on-system toast. A hex-clipped,
/// mono, accent-bordered card that slides up from the bottom, holds, and slides
/// out — replacing stock `SnackBar` across the app. `HexToast.show(context, …)`
/// is the one call site helper.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/theme/hex_clipper.dart';
import 'package:flutter/material.dart';

abstract final class HexToast {
  /// Slide an on-system toast up from the bottom. [accent] tints the leading
  /// border + optional [icon]; use `hexRed` for errors, `hexGreen` for success.
  static void show(
    BuildContext context,
    String message, {
    Color accent = AmiColors.hexBlue,
    IconData? icon,
    Duration duration = const Duration(seconds: 3),
  }) {
    final overlay = Overlay.maybeOf(context, rootOverlay: true);
    if (overlay == null) return;
    late final OverlayEntry entry;
    entry = OverlayEntry(
      builder: (_) => _HexToastCard(
        message: message,
        accent: accent,
        icon: icon,
        duration: duration,
        onDismissed: entry.remove,
      ),
    );
    overlay.insert(entry);
  }
}

class _HexToastCard extends StatefulWidget {
  const _HexToastCard({
    required this.message,
    required this.accent,
    required this.icon,
    required this.duration,
    required this.onDismissed,
  });

  final String message;
  final Color accent;
  final IconData? icon;
  final Duration duration;
  final VoidCallback onDismissed;

  @override
  State<_HexToastCard> createState() => _HexToastCardState();
}

class _HexToastCardState extends State<_HexToastCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 280),
  );
  bool _dismissing = false;

  @override
  void initState() {
    super.initState();
    _controller.forward();
    Future<void>.delayed(widget.duration, _dismiss);
  }

  Future<void> _dismiss() async {
    if (_dismissing || !mounted) return;
    _dismissing = true;
    await _controller.reverse();
    widget.onDismissed();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final mq = MediaQuery.of(context);
    final anim =
        CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic);
    return Positioned(
      left: AmiSpacing.l,
      right: AmiSpacing.l,
      bottom: mq.padding.bottom + AmiSpacing.l,
      child: SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(0, 0.4),
          end: Offset.zero,
        ).animate(anim),
        child: FadeTransition(
          opacity: anim,
          child: Semantics(
            liveRegion: true,
            child: Material(
              type: MaterialType.transparency,
              child: GestureDetector(
                onTap: _dismiss,
                child: ClipPath(
                  clipper: const FlatTopHexagonClipper(cornerCut: 10),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: AmiSpacing.m, vertical: AmiSpacing.s + 2),
                    decoration: BoxDecoration(
                      color: AmiColors.slate800,
                      border: Border(
                        left: BorderSide(color: widget.accent, width: 3),
                      ),
                    ),
                    child: Row(
                      children: [
                        if (widget.icon != null) ...[
                          Icon(widget.icon, color: widget.accent, size: 18),
                          const SizedBox(width: AmiSpacing.s),
                        ],
                        Expanded(
                          child: Text(
                            widget.message,
                            style: AmiTypography.labelMono.copyWith(
                              color: AmiColors.textHigh,
                              fontSize: 12,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
