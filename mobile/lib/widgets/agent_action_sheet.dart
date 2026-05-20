/// Bottom sheet shown when the user taps an unlocked agent hex on the Floor.
/// Offers two paths: 1-on-1 (talk *to* the agent) or Brief (modify *how* the
/// agent thinks). Added in AT:R27 alongside the Coach → Brief rename to fix
/// the discoverability gap — Brief was previously buried behind a tune icon
/// inside the 1-on-1 header.
library;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/agent/brief_screen.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';


class AgentActionSheet extends StatelessWidget {
  const AgentActionSheet({super.key, required this.agent});

  final Agent agent;

  static Future<void> show(BuildContext context, Agent agent) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: AmiColors.slate800,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => AgentActionSheet(agent: agent),
    );
  }

  // Concierge has no Brief — its base prompt is fixed and there's no
  // user_overlay surface for it.
  bool get _briefAvailable => agent.family != AgentFamily.concierge;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AmiSpacing.l,
          vertical: AmiSpacing.l,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Header(agent: agent),
            const SizedBox(height: AmiSpacing.l),
            _ActionButton(
              label: '1-ON-1',
              sublabel: 'Talk to the agent',
              icon: Icons.chat_bubble_outline,
              accent: AmiColors.hexBlue,
              onTap: () {
                Navigator.of(context).pop();
                Navigator.of(context).push(MaterialPageRoute<void>(
                  builder: (_) => OneOnOneScreen(agent: agent),
                ));
              },
            ),
            const SizedBox(height: AmiSpacing.s),
            _ActionButton(
              label: 'BRIEF',
              sublabel: _briefAvailable
                  ? 'Tell the agent how to think'
                  : 'Not available for ${agent.displayName}',
              icon: Icons.tune,
              accent: AmiColors.hexAmber,
              enabled: _briefAvailable,
              onTap: _briefAvailable
                  ? () {
                      Navigator.of(context).pop();
                      Navigator.of(context).push(MaterialPageRoute<void>(
                        builder: (_) => BriefScreen(agent: agent),
                      ));
                    }
                  : null,
            ),
            const SizedBox(height: AmiSpacing.s),
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(
                'CANCEL',
                style: TextStyle(
                  color: AmiColors.textMed,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.08,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}


class _Header extends StatelessWidget {
  const _Header({required this.agent});

  final Agent agent;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        HexAvatar(
          label: agent.abbreviation,
          color: agent.color,
          size: 48,
        ),
        const SizedBox(width: AmiSpacing.m),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                agent.displayName.toUpperCase(),
                style: const TextStyle(
                  color: AmiColors.textHigh,
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  letterSpacing: 0.06,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                agent.tagline,
                style: const TextStyle(
                  color: AmiColors.textMed,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}


class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.label,
    required this.sublabel,
    required this.icon,
    required this.accent,
    required this.onTap,
    this.enabled = true,
  });

  final String label;
  final String sublabel;
  final IconData icon;
  final Color accent;
  final VoidCallback? onTap;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final dim = !enabled;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AmiSpacing.m,
          vertical: AmiSpacing.m,
        ),
        decoration: BoxDecoration(
          color: dim
              ? AmiColors.slate900.withValues(alpha: 0.4)
              : AmiColors.slate900,
          border: Border.all(
            color: dim ? AmiColors.slate700 : accent.withValues(alpha: 0.4),
            width: 1,
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: dim
                    ? AmiColors.slate700
                    : accent.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                icon,
                color: dim ? AmiColors.textLow : accent,
                size: 20,
              ),
            ),
            const SizedBox(width: AmiSpacing.m),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      color: dim ? AmiColors.textLow : AmiColors.textHigh,
                      fontWeight: FontWeight.w700,
                      fontSize: 15,
                      letterSpacing: 0.08,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    sublabel,
                    style: TextStyle(
                      color: dim ? AmiColors.textLow : AmiColors.textMed,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.arrow_forward_ios,
              size: 14,
              color: dim ? AmiColors.textLow : AmiColors.textMed,
            ),
          ],
        ),
      ),
    );
  }
}
