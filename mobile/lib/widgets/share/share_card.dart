/// CR012 (C4) — share cards. A `ShareCard` is a fixed 1080×1350 logical-px
/// portrait card rendered **offscreen** (never mounted on a visible route) and
/// rasterised to a PNG by [ShareService]. Four templates share one chrome:
/// slate900 canvas, a hex-mesh watermark, the AMI wordmark, and a disclaimer
/// strip — the simulation-only framing every card must carry.
///
/// The card reads no providers and no `Localizations`: everything it draws is
/// passed in as resolved strings/colours via [ShareCardData], so the offscreen
/// render is deterministic and context-free.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_mesh_overlay.dart';
import 'package:flutter/material.dart';

/// Fixed capture size (Instagram-portrait ratio). [ShareService] rasterises at
/// this logical size, pixelRatio 1 ⇒ a 1080×1350 PNG.
const Size kShareCardSize = Size(1080, 1350);

/// Payload for a [ShareCard]. Sealed so [ShareCard.build] switches exhaustively.
sealed class ShareCardData {
  const ShareCardData({required this.kicker, required this.accent});

  /// Small mono label at the top of the card (already localized + upper-cased).
  final String kicker;

  /// The template's dominant accent colour.
  final Color accent;
}

/// The Room's verdict — ticker + stance + a short reasoning excerpt. Carries
/// **no** prices / size / P&L by design (simulation-advice safety).
class VerdictShareData extends ShareCardData {
  const VerdictShareData({
    required super.kicker,
    required super.accent,
    required this.ticker,
    required this.stanceLabel,
    required this.reason,
  });

  final String ticker;
  final String stanceLabel;
  final String reason;
}

/// A streak milestone — a big day count over a unit label.
class StreakShareData extends ShareCardData {
  const StreakShareData({
    required super.kicker,
    required super.accent,
    required this.days,
    required this.unit,
  });

  final int days;
  final String unit;
}

/// An agent unlock — the agent's hex + name.
class UnlockShareData extends ShareCardData {
  const UnlockShareData({
    required super.kicker,
    required super.accent,
    required this.agentName,
    required this.abbreviation,
  });

  final String agentName;
  final String abbreviation;
}

/// A league standing — tier + rank + week (+ optional promoted/relegated tag).
class PromotionShareData extends ShareCardData {
  const PromotionShareData({
    required super.kicker,
    required super.accent,
    required this.tierLabel,
    required this.week,
    required this.rank,
    this.outcomeLabel,
  });

  final String tierLabel;
  final String week;
  final int rank;
  final String? outcomeLabel;
}

class ShareCard extends StatelessWidget {
  const ShareCard({super.key, required this.data, required this.disclaimer});

  final ShareCardData data;
  final String disclaimer;

  @override
  Widget build(BuildContext context) {
    return SizedBox.fromSize(
      size: kShareCardSize,
      child: DecoratedBox(
        decoration: const BoxDecoration(color: AmiColors.slate900),
        child: Stack(
          fit: StackFit.expand,
          children: [
            const Positioned.fill(child: HexMeshOverlay(opacity: 0.06)),
            // A soft accent bloom behind the content, top-anchored.
            Positioned(
              top: -220,
              left: -120,
              right: -120,
              child: Container(
                height: 620,
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    colors: [
                      data.accent.withValues(alpha: 0.22),
                      AmiColors.slate900.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(88, 96, 88, 80),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _WordmarkRow(kicker: data.kicker, accent: data.accent),
                  Expanded(child: Center(child: _body())),
                  _DisclaimerStrip(text: disclaimer),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _body() => switch (data) {
        VerdictShareData d => _VerdictBody(d),
        StreakShareData d => _StreakBody(d),
        UnlockShareData d => _UnlockBody(d),
        PromotionShareData d => _PromotionBody(d),
      };
}

class _WordmarkRow extends StatelessWidget {
  const _WordmarkRow({required this.kicker, required this.accent});
  final String kicker;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(Icons.hexagon_rounded, color: accent, size: 44),
        const SizedBox(width: 16),
        Text(
          'AMI TRADE',
          style: AmiTypography.labelMono.copyWith(
            color: AmiColors.textHigh,
            fontSize: 34,
            letterSpacing: 4,
          ),
        ),
        const Spacer(),
        Text(
          kicker,
          style: AmiTypography.labelMono.copyWith(
            color: accent,
            fontSize: 26,
            letterSpacing: 3,
          ),
        ),
      ],
    );
  }
}

class _DisclaimerStrip extends StatelessWidget {
  const _DisclaimerStrip({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 22),
      decoration: BoxDecoration(
        color: AmiColors.slate800.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: AmiTypography.labelMono.copyWith(
          color: AmiColors.textMed,
          fontSize: 24,
          letterSpacing: 1.5,
        ),
      ),
    );
  }
}

class _VerdictBody extends StatelessWidget {
  const _VerdictBody(this.d);
  final VerdictShareData d;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          d.ticker,
          style: AmiTypography.statBig.copyWith(
            color: AmiColors.textHigh,
            fontSize: 132,
          ),
        ),
        const SizedBox(height: 24),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
          decoration: BoxDecoration(
            color: d.accent.withValues(alpha: 0.16),
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(color: d.accent, width: 2),
          ),
          child: Text(
            d.stanceLabel,
            style: AmiTypography.labelMono.copyWith(
              color: d.accent,
              fontSize: 40,
              letterSpacing: 3,
            ),
          ),
        ),
        const SizedBox(height: 56),
        Text(
          d.reason,
          maxLines: 3,
          overflow: TextOverflow.ellipsis,
          style: AmiTypography.body.copyWith(
            color: AmiColors.textMed,
            fontSize: 46,
            height: 1.4,
          ),
        ),
      ],
    );
  }
}

class _StreakBody extends StatelessWidget {
  const _StreakBody(this.d);
  final StreakShareData d;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        SizedBox(
          width: 520,
          height: 520,
          child: Stack(
            alignment: Alignment.center,
            children: [
              Icon(Icons.hexagon_outlined, color: d.accent, size: 520),
              Text(
                '${d.days}',
                style: AmiTypography.statBig.copyWith(
                  color: AmiColors.textHigh,
                  fontSize: 260,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 32),
        Text(
          d.unit,
          style: AmiTypography.labelMono.copyWith(
            color: d.accent,
            fontSize: 52,
            letterSpacing: 6,
          ),
        ),
      ],
    );
  }
}

class _UnlockBody extends StatelessWidget {
  const _UnlockBody(this.d);
  final UnlockShareData d;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: d.accent.withValues(alpha: 0.5),
                blurRadius: 120,
                spreadRadius: 12,
              ),
            ],
          ),
          child: SizedBox(
            width: 480,
            height: 480,
            child: Stack(
              alignment: Alignment.center,
              children: [
                Icon(Icons.hexagon, color: d.accent, size: 480),
                Text(
                  d.abbreviation,
                  style: AmiTypography.statBig.copyWith(
                    color: AmiColors.slate900,
                    fontSize: 150,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 72),
        Text(
          d.agentName,
          textAlign: TextAlign.center,
          style: AmiTypography.h1.copyWith(fontSize: 88),
        ),
      ],
    );
  }
}

class _PromotionBody extends StatelessWidget {
  const _PromotionBody(this.d);
  final PromotionShareData d;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 44, vertical: 22),
          decoration: BoxDecoration(
            color: d.accent.withValues(alpha: 0.16),
            borderRadius: BorderRadius.circular(AmiRadii.sheet),
            border: Border.all(color: d.accent, width: 3),
          ),
          child: Text(
            d.tierLabel,
            style: AmiTypography.labelMono.copyWith(
              color: d.accent,
              fontSize: 64,
              letterSpacing: 4,
            ),
          ),
        ),
        const SizedBox(height: 72),
        Text(
          '#${d.rank}',
          style: AmiTypography.statBig.copyWith(
            color: AmiColors.textHigh,
            fontSize: 220,
          ),
        ),
        const SizedBox(height: 24),
        Text(
          d.outcomeLabel ?? d.week,
          style: AmiTypography.labelMono.copyWith(
            color: AmiColors.textMed,
            fontSize: 44,
            letterSpacing: 3,
          ),
        ),
      ],
    );
  }
}
