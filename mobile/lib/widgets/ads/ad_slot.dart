/// The single render path for native ad placements (CR122-MOBILE-A).
///
/// Screens drop `AdSlot(placement: ...)` at an approved surface and nothing
/// else — every check (allowlist, plan gate, persisted caps, fill) runs in
/// [AdGate.request], so a screen cannot serve itself an ad the gate refuses.
/// A refusal collapses to zero height; there is deliberately no "blank slot"
/// state. The slot re-requests whenever the mandate's plan changes, which is
/// how a CR084 upgrade removes ads without an app restart (`ads.md:113`).
///
/// The structural twin of this rule lives in `test/ads_structural_test.dart`:
/// the exact set of files allowed to instantiate AdSlot is asserted there, so
/// a future screen quietly gaining an ad slot fails the suite.
library;

import 'dart:async';

import 'package:ami_trade/services/ads/admob_sdk.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/state/ads_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/admob_native_card.dart';
import 'package:ami_trade/widgets/ads/house_ad_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AdSlot extends ConsumerStatefulWidget {
  const AdSlot({super.key, required this.placement, this.topSpacing = true});

  final AdPlacement placement;

  /// Inset a spacing row above the card when it fills (so an empty slot
  /// contributes no stray gap).
  final bool topSpacing;

  @override
  ConsumerState<AdSlot> createState() => _AdSlotState();
}

class _AdSlotState extends ConsumerState<AdSlot> {
  AdDecision? _decision;
  bool _dismissed = false;
  bool _recorded = false;
  bool _requestedOnce = false;
  String? _planAtRequest;

  @override
  void didUpdateWidget(covariant AdSlot oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.placement.id != widget.placement.id) {
      // A reparented slot is a new placement decision — never carry a fill
      // (or a dismissal) across placements.
      _decision = null;
      _dismissed = false;
      _recorded = false;
      _requestedOnce = false;
    }
  }

  Future<void> _request(String? plan) async {
    _requestedOnce = true;
    _planAtRequest = plan;
    final gate = ref.read(adGateProvider);
    final decision = await gate.request(widget.placement);
    if (!mounted) return;
    setState(() => _decision = decision);
    if (decision.isFilled && !_recorded) {
      _recorded = true;
      unawaited(gate.recordShown(widget.placement));
    }
  }

  @override
  Widget build(BuildContext context) {
    final plan = ref
        .watch(mandateNotifierProvider.select((s) => s.mandate?.plan));
    if (!_requestedOnce || plan != _planAtRequest) {
      scheduleMicrotask(() {
        if (mounted) _request(plan);
      });
      _requestedOnce = true;
      _planAtRequest = plan;
    }
    final decision = _decision;
    if (_dismissed || decision == null || !decision.isFilled) {
      return const SizedBox.shrink();
    }
    final fill = decision.fill;
    final Widget card;
    if (fill is HouseAdFill) {
      card = HouseAdCard(
        creative: fill.creative,
        onDismiss: () => setState(() => _dismissed = true),
      );
    } else if (fill is AdMobNativeFill) {
      // CR122-MOBILE-C — the SDK template inside our own labelled, one-tap
      // dismissable chrome; the card owns disposal of the platform ad.
      card = AdMobNativeCard(
        fill: fill,
        onDismiss: () => setState(() => _dismissed = true),
      );
    } else {
      // An unknown fill type renders nothing rather than guessing.
      return const SizedBox.shrink();
    }
    if (!widget.topSpacing) return card;
    return Padding(
      padding: const EdgeInsets.only(top: AmiSpacing.m),
      child: card,
    );
  }
}
