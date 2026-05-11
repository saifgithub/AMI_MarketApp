/// Placeholder for the Floor home (the honeycomb screen).
/// Real version lands in W4–W5; this is the post-onboarding landing for now.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_avatar.dart';
import 'package:flutter/material.dart';

class FloorPlaceholderScreen extends StatelessWidget {
  const FloorPlaceholderScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AmiSpacing.l),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const HexAvatar(
                label: 'CNC',
                color: AmiColors.hexPink,
                size: 140,
                status: HexAvatarStatus.recentCall,
              ),
              const SizedBox(height: AmiSpacing.xl),
              const Text('WELCOME TO THE FLOOR', style: AmiTypography.labelMono),
              const SizedBox(height: AmiSpacing.s),
              const Text(
                'Your 12 analysts are calibrating themselves to your mandate.\n\n'
                "The Floor honeycomb home is coming in Week 4. For now, your "
                'onboarding worked — that\'s the milestone.',
                textAlign: TextAlign.center,
                style: AmiTypography.body,
              ),
              const SizedBox(height: AmiSpacing.xl),
              TextButton(
                onPressed: () =>
                    Navigator.of(context).pushReplacementNamed('/onboarding'),
                child: Text(
                  'restart onboarding',
                  style: AmiTypography.caption.copyWith(color: AmiColors.hexBlue),
                ),
              ),
              const Spacer(),
              const Text(
                '⬢  AMI TRADE • EDUCATIONAL SIMULATION • NOT ADVICE',
                style: AmiTypography.caption,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
