/// Placeholder Floor home — shows the 12 agents as tappable hexes.
/// Long-press / tap to open a 1-on-1 chat with that agent.
/// Real honeycomb layout lands in W4–W5.
library;

import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';

class FloorPlaceholderScreen extends StatelessWidget {
  const FloorPlaceholderScreen({super.key});

  void _openAgent(BuildContext context, Agent agent) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => OneOnOneScreen(agent: agent),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final concierge = kAllAgents.last;
    final tradingAgents = kAllAgents.sublist(0, 12);

    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AmiSpacing.m),
          child: Column(
            children: [
              const SizedBox(height: AmiSpacing.l),
              // ── Concierge centerpiece ──
              GestureDetector(
                onTap: () => _openAgent(context, concierge),
                child: HexAvatar(
                  label: concierge.abbreviation,
                  color: concierge.color,
                  size: 110,
                  status: HexAvatarStatus.recentCall,
                ),
              ),
              const SizedBox(height: AmiSpacing.s),
              const Text('AMI CONCIERGE', style: AmiTypography.labelMono),
              const SizedBox(height: AmiSpacing.xs),
              Text(
                'Your personal assistant — tap to chat',
                style: AmiTypography.caption.copyWith(color: AmiColors.hexPink),
              ),
              const SizedBox(height: AmiSpacing.xl),

              // ── 12 trading agents grid ──
              const Text('YOUR TEAM', style: AmiTypography.labelMono),
              const SizedBox(height: AmiSpacing.s),
              const Text(
                'Tap any agent to start a 1-on-1.',
                style: AmiTypography.caption,
              ),
              const SizedBox(height: AmiSpacing.m),
              Wrap(
                spacing: AmiSpacing.m,
                runSpacing: AmiSpacing.l,
                alignment: WrapAlignment.center,
                children: [
                  for (final agent in tradingAgents)
                    _AgentTile(agent: agent, onTap: () => _openAgent(context, agent)),
                ],
              ),

              const SizedBox(height: AmiSpacing.xl),

              // ── Footer ──
              TextButton(
                onPressed: () =>
                    Navigator.of(context).pushReplacementNamed('/onboarding'),
                child: Text(
                  'restart onboarding',
                  style: AmiTypography.caption.copyWith(color: AmiColors.hexBlue),
                ),
              ),
              const SizedBox(height: AmiSpacing.m),
              const Text(
                '⬢  AMI TRADE • EDUCATIONAL SIMULATION • NOT ADVICE',
                style: AmiTypography.caption,
              ),
              const SizedBox(height: AmiSpacing.l),
            ],
          ),
        ),
      ),
    );
  }
}


class _AgentTile extends StatelessWidget {
  const _AgentTile({required this.agent, required this.onTap});
  final Agent agent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 88,
      child: Column(
        children: [
          HexAvatar(
            label: agent.abbreviation,
            color: agent.color,
            size: 72,
            onTap: onTap,
          ),
          const SizedBox(height: 6),
          Text(
            agent.displayName,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: AmiTypography.caption.copyWith(fontSize: 10),
          ),
        ],
      ),
    );
  }
}
