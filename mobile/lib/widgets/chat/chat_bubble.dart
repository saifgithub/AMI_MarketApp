import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

enum ChatAuthor { user, concierge, agent }

/// A single chat bubble. Author-side aware (Concierge bubbles are on the left,
/// user bubbles on the right). Agent bubbles (used in 1-on-1 and Convene)
/// take a role color for the accent + label.
class ChatBubble extends StatelessWidget {
  const ChatBubble({
    super.key,
    required this.content,
    required this.author,
    this.agentLabel,
    this.agentColor,
    this.streaming = false,
  });

  /// The message text. If [streaming] is true, the parent is expected
  /// to update [content] character-by-character.
  final String content;

  final ChatAuthor author;

  /// Required for [ChatAuthor.agent]; ignored otherwise.
  final String? agentLabel;
  final Color? agentColor;

  final bool streaming;

  bool get _isUser => author == ChatAuthor.user;

  Color get _accentColor {
    if (author == ChatAuthor.concierge) return AmiColors.hexPink;
    if (author == ChatAuthor.agent && agentColor != null) return agentColor!;
    return AmiColors.hexBlue; // user
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AmiSpacing.xs),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_isUser) const Spacer(),
          Flexible(
            flex: 4,
            child: _Bubble(
              accentColor: _accentColor,
              isUser: _isUser,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Label row — Concierge/Agent get a label; user doesn't
                  if (!_isUser)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AmiSpacing.xs),
                      child: Text(
                        _labelText(context),
                        style: AmiTypography.labelMono.copyWith(
                          color: _accentColor,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  // Body text
                  Text(
                    content,
                    style: AmiTypography.body.copyWith(color: AmiColors.textHigh),
                  ),
                  if (streaming)
                    const Padding(
                      padding: EdgeInsets.only(top: 4),
                      child: _CaretBlink(),
                    ),
                ],
              ),
            ),
          ),
          if (!_isUser) const Spacer(),
        ],
      ),
    );
  }

  String _labelText(BuildContext context) {
    if (author == ChatAuthor.concierge) {
      return AppLocalizations.of(context).chatBubbleConcierge;
    }
    if (author == ChatAuthor.agent) return (agentLabel ?? 'AGENT').toUpperCase();
    return '';
  }
}


class _Bubble extends StatelessWidget {
  const _Bubble({
    required this.child,
    required this.accentColor,
    required this.isUser,
  });

  final Widget child;
  final Color accentColor;
  final bool isUser;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: isUser
            ? AmiColors.slate800
            : AmiColors.glass,
        border: Border.all(color: AmiColors.slate700, width: 1),
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(AmiRadii.card),
          topRight: const Radius.circular(AmiRadii.card),
          bottomLeft: Radius.circular(isUser ? AmiRadii.card : 2),
          bottomRight: Radius.circular(isUser ? 2 : AmiRadii.card),
        ),
      ),
      // 3px accent line on the left side for non-user (Concierge / agent)
      foregroundDecoration: isUser
          ? null
          : BoxDecoration(
              border: Border(left: BorderSide(color: accentColor, width: 3)),
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(AmiRadii.card),
                bottomLeft: const Radius.circular(2),
              ),
            ),
      child: child,
    );
  }
}


/// Blinking caret to indicate streaming-in-progress.
class _CaretBlink extends StatefulWidget {
  const _CaretBlink();

  @override
  State<_CaretBlink> createState() => _CaretBlinkState();
}

class _CaretBlinkState extends State<_CaretBlink>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 800),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _ctrl.drive(Tween(begin: 0.2, end: 1.0)),
      child: Container(
        width: 8,
        height: 14,
        color: AmiColors.textLow,
      ),
    );
  }
}
