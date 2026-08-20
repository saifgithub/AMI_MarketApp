/// Post-lesson house interstitial (CR122-MOBILE-A).
///
/// Full-screen, skippable after 5 seconds per `ads.md` UX rules — the back
/// gesture is held closed until the countdown ends, then SKIP and system
/// back both work. No sound, no motion; a static house creative with the AD
/// label. [maybeShowPostLessonInterstitial] is the only entry point: it runs
/// the lesson counter first (so the 1-per-5 cap advances even when nothing
/// shows), then asks [AdGate] — plan gate, session/day/10-minute caps and
/// the unreadable-store block all apply before a route is ever pushed.
/// With AdMob filling (CR122-MOBILE-C) the SDK presents its own full-screen
/// ad through [AdMobInterstitialFill.handle]; this page renders house fill.
library;

import 'dart:async';

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/ads/admob_sdk.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/state/ads_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/ad_badge.dart';
import 'package:ami_trade/widgets/ads/house_ad_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Fire-and-forget from the lesson-completion listener. Never throws into
/// the caller; a refusal is silent for the user and loud in the gate's log.
Future<void> maybeShowPostLessonInterstitial(
    BuildContext context, WidgetRef ref) async {
  final gate = ref.read(adGateProvider);
  await gate.recordLessonCompleted();
  final decision = await gate.request(AdPlacement.postLessonInterstitial);
  final fill = decision.fill;
  if (fill is AdMobInterstitialFill) {
    // CR122-MOBILE-C — the SDK presents its own full-screen ad and owns the
    // close affordance; skippability is verified on-device (test plan #2).
    await gate.recordShown(AdPlacement.postLessonInterstitial);
    await fill.handle.show();
    return;
  }
  if (fill is! HouseAdFill) return;
  if (!context.mounted) return;
  await gate.recordShown(AdPlacement.postLessonInterstitial);
  if (!context.mounted) return;
  await Navigator.of(context).push(MaterialPageRoute<void>(
    fullscreenDialog: true,
    builder: (_) => HouseAdInterstitialPage(creative: fill.creative),
  ));
}

class HouseAdInterstitialPage extends ConsumerStatefulWidget {
  const HouseAdInterstitialPage({super.key, required this.creative});

  final HouseAdCreative creative;

  static const skipAfter = Duration(seconds: 5);

  @override
  ConsumerState<HouseAdInterstitialPage> createState() =>
      _HouseAdInterstitialPageState();
}

class _HouseAdInterstitialPageState
    extends ConsumerState<HouseAdInterstitialPage> {
  late int _secondsLeft;
  Timer? _timer;

  bool get _skippable => _secondsLeft <= 0;

  @override
  void initState() {
    super.initState();
    _secondsLeft = HouseAdInterstitialPage.skipAfter.inSeconds;
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return;
      setState(() => _secondsLeft--);
      if (_secondsLeft <= 0) t.cancel();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final copy = HouseAdCard.copyFor(l, widget.creative.slot);
    final cta = widget.creative.targetTier == HouseAdTargetTier.floorManager
        ? l.houseAdCtaFloorManager
        : l.houseAdCtaTrader;
    return PopScope(
      canPop: _skippable,
      child: Scaffold(
        backgroundColor: AmiColors.slate900,
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AmiSpacing.l),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const AdBadge(),
                const Spacer(),
                Text(copy.headline, style: AmiTypography.h2),
                const SizedBox(height: AmiSpacing.s),
                Text(copy.body, style: AmiTypography.bodyLg),
                const SizedBox(height: AmiSpacing.l),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AmiColors.hexAmber,
                      side: const BorderSide(color: AmiColors.hexAmber),
                    ),
                    onPressed: () => openHouseAdPaywall(context, ref),
                    child: Text(cta),
                  ),
                ),
                const Spacer(),
                Align(
                  alignment: AlignmentDirectional.centerEnd,
                  child: TextButton(
                    onPressed: _skippable
                        ? () => Navigator.of(context).maybePop()
                        : null,
                    child: Text(
                      _skippable
                          ? l.adInterstitialSkip
                          : l.adInterstitialSkipIn(_secondsLeft),
                      style: AmiTypography.labelMono.copyWith(
                        color: _skippable
                            ? AmiColors.textHigh
                            : AmiColors.textLow,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
