/// Dev preview — sanity check that the AMI design system renders correctly.
/// This screen is the temporary launch target until the real router is wired (W2).
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/glass_panel.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_chip.dart';
import 'package:flutter/material.dart';

class DevPreviewScreen extends StatelessWidget {
  const DevPreviewScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AmiSpacing.m),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('AMI TRADE', style: AmiTypography.labelMono),
              const SizedBox(height: AmiSpacing.xs),
              Text('Design system preview', style: AmiTypography.h2),
              const SizedBox(height: AmiSpacing.l),

              // Tier badges
              const _SectionTitle('TIER BADGES'),
              const SizedBox(height: AmiSpacing.s),
              Wrap(
                spacing: AmiSpacing.s,
                children: const [
                  HexChip(label: 'FLOOR PASS', color: AmiColors.slate600, filled: false),
                  HexChip(label: 'TRADER', color: AmiColors.hexBlue),
                  HexChip(label: 'FLOOR MANAGER', color: AmiColors.hexPurple),
                ],
              ),
              const SizedBox(height: AmiSpacing.xl),

              // The 12 agents — by family
              const _SectionTitle('THE 12 AGENTS'),
              const SizedBox(height: AmiSpacing.s),

              const _AgentFamilyRow(
                title: 'ANALYSTS',
                color: AmiColors.hexCyan,
                items: [
                  _Item('FUND', HexAvatarStatus.idle),
                  _Item('MKT', HexAvatarStatus.recentCall),
                  _Item('NEWS', HexAvatarStatus.idle),
                  _Item('SOC', HexAvatarStatus.signal),
                ],
              ),
              const SizedBox(height: AmiSpacing.m),
              const _AgentFamilyRow(
                title: 'RESEARCHERS',
                color: AmiColors.hexPurple,
                items: [
                  _Item('BULL', HexAvatarStatus.idle),
                  _Item('BEAR', HexAvatarStatus.attention),
                  _Item('RES-M', HexAvatarStatus.locked),
                ],
              ),
              const SizedBox(height: AmiSpacing.m),
              const _AgentFamilyRow(
                title: 'RISK',
                color: AmiColors.hexAmber,
                items: [
                  _Item('AGG', HexAvatarStatus.idle),
                  _Item('CON', HexAvatarStatus.idle),
                  _Item('NEU', HexAvatarStatus.locked),
                ],
              ),
              const SizedBox(height: AmiSpacing.m),
              const _AgentFamilyRow(
                title: 'EXECUTION + MANAGER',
                color: AmiColors.hexGreen,
                items: [
                  _Item('TRADE', HexAvatarStatus.idle, color: AmiColors.hexGreen),
                  _Item('PM', HexAvatarStatus.locked, color: AmiColors.hexPurple),
                ],
              ),
              const SizedBox(height: AmiSpacing.m),
              const _AgentFamilyRow(
                title: 'CONCIERGE',
                color: AmiColors.hexPink,
                items: [
                  _Item('CNC', HexAvatarStatus.recentCall, color: AmiColors.hexPink),
                ],
              ),
              const SizedBox(height: AmiSpacing.xl),

              // Buttons
              const _SectionTitle('HEX BUTTONS'),
              const SizedBox(height: AmiSpacing.s),
              Row(
                children: [
                  HexButton(label: 'CONVENE', onPressed: () {}),
                  const SizedBox(width: AmiSpacing.s),
                  HexButton(
                    label: 'COACH',
                    onPressed: () {},
                    variant: HexButtonVariant.outlined,
                    color: AmiColors.hexPurple,
                  ),
                ],
              ),
              const SizedBox(height: AmiSpacing.xl),

              // Glass panel sample with role accent
              const _SectionTitle('GLASS PANELS'),
              const SizedBox(height: AmiSpacing.s),
              GlassPanel(
                accentColor: AmiColors.hexPurple,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('MORNING BRIEFING', style: AmiTypography.labelMono),
                    const SizedBox(height: AmiSpacing.s),
                    Text(
                      'NVDA up 3.2% overnight. Your Bear wants to talk about TSLA.',
                      style: AmiTypography.body,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AmiSpacing.m),
              GlassPanel(
                accentColor: AmiColors.hexGreen,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('PORTFOLIO VALUE', style: AmiTypography.labelMono),
                    const SizedBox(height: AmiSpacing.xs),
                    Text(r'$10,234.50', style: AmiTypography.statBig),
                    Text('+2.34% today  •  drawdown 4% / 30%', style: AmiTypography.caption),
                  ],
                ),
              ),
              const SizedBox(height: AmiSpacing.xxl),

              Center(
                child: Text(
                  '— alpha build • 0.1.0 —',
                  style: AmiTypography.caption,
                ),
              ),
              const SizedBox(height: AmiSpacing.l),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(text, style: AmiTypography.labelMono.copyWith(color: AmiColors.textLow));
  }
}

class _Item {
  const _Item(this.label, this.status, {this.color});
  final String label;
  final HexAvatarStatus status;
  final Color? color;
}

class _AgentFamilyRow extends StatelessWidget {
  const _AgentFamilyRow({required this.title, required this.color, required this.items});
  final String title;
  final Color color;
  final List<_Item> items;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: AmiTypography.caption.copyWith(letterSpacing: 1.3)),
        const SizedBox(height: AmiSpacing.xs),
        Wrap(
          spacing: AmiSpacing.s,
          runSpacing: AmiSpacing.s,
          children: items
              .map((i) => HexAvatar(label: i.label, color: i.color ?? color, status: i.status))
              .toList(),
        ),
      ],
    );
  }
}
