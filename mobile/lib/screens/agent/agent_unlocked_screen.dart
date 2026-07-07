/// Full-screen agent-unlock takeover (CR004 B1 — the "major" celebration).
///
/// Slate-900 canvas; the agent's hex scales 0.6 → 1.0 with a glow bloom
/// over 900ms, then name + role line + tagline. Primary action meets the
/// agent in 1-on-1 (route replace); "Later" pops back to the earning
/// surface.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/agent.dart';
import 'package:ami_trade/screens/agent/one_on_one_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:flutter/material.dart';

class AgentUnlockedScreen extends StatefulWidget {
  const AgentUnlockedScreen({super.key, required this.agent});

  final Agent agent;

  @override
  State<AgentUnlockedScreen> createState() => _AgentUnlockedScreenState();
}

class _AgentUnlockedScreenState extends State<AgentUnlockedScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..forward();

  late final Animation<double> _scale = Tween<double>(begin: 0.6, end: 1.0)
      .animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutBack));
  late final Animation<double> _glow = CurvedAnimation(
    parent: _controller,
    curve: const Interval(0.3, 1.0, curve: Curves.easeInOut),
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final agent = widget.agent;
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AmiSpacing.l),
          child: Column(
            children: [
              const Spacer(flex: 2),
              Text(
                l.agentUnlockedHeadline,
                style: AmiTypography.labelMono
                    .copyWith(color: AmiColors.hexAmber),
              ),
              const Spacer(),
              AnimatedBuilder(
                animation: _controller,
                builder: (_, child) => Container(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: agent.color
                            .withValues(alpha: 0.45 * _glow.value),
                        blurRadius: 60 * _glow.value,
                        spreadRadius: 8 * _glow.value,
                      ),
                    ],
                  ),
                  child: Transform.scale(scale: _scale.value, child: child),
                ),
                child: HexAvatar(
                  label: agent.abbreviation,
                  color: agent.color,
                  size: 160,
                ),
              ),
              const SizedBox(height: AmiSpacing.xl),
              Text(agent.displayName, style: AmiTypography.h1),
              const SizedBox(height: AmiSpacing.s),
              Text(
                agent.tagline,
                textAlign: TextAlign.center,
                style: AmiTypography.bodyLg,
              ),
              const Spacer(flex: 2),
              SizedBox(
                width: double.infinity,
                child: HexButton(
                  label: l.agentUnlockedMeet(agent.displayName.toUpperCase()),
                  color: agent.color,
                  onPressed: () => Navigator.of(context).pushReplacement(
                    MaterialPageRoute(
                      builder: (_) => OneOnOneScreen(agent: agent),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: AmiSpacing.s),
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text(
                  l.agentUnlockedLater,
                  style: AmiTypography.body,
                ),
              ),
              const SizedBox(height: AmiSpacing.m),
            ],
          ),
        ),
      ),
    );
  }
}
