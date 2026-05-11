import 'dart:async';

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

/// Reveals the given [text] character-by-character at [charsPerSecond] rate.
/// Used for the Concierge first message + agent log streaming.
class StreamingText extends StatefulWidget {
  const StreamingText({
    super.key,
    required this.text,
    this.style,
    this.charsPerSecond = 50,
    this.onDone,
  });

  final String text;
  final TextStyle? style;
  final int charsPerSecond;
  final VoidCallback? onDone;

  @override
  State<StreamingText> createState() => _StreamingTextState();
}

class _StreamingTextState extends State<StreamingText> {
  Timer? _timer;
  int _shown = 0;

  @override
  void initState() {
    super.initState();
    _start();
  }

  void _start() {
    final period = Duration(milliseconds: (1000 / widget.charsPerSecond).round());
    _timer = Timer.periodic(period, (t) {
      if (!mounted) {
        t.cancel();
        return;
      }
      if (_shown >= widget.text.length) {
        t.cancel();
        widget.onDone?.call();
        return;
      }
      setState(() => _shown++);
    });
  }

  @override
  void didUpdateWidget(covariant StreamingText oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.text != widget.text) {
      _timer?.cancel();
      _shown = 0;
      _start();
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Text(
      widget.text.substring(0, _shown),
      style: widget.style ?? AmiTypography.body,
    );
  }
}
