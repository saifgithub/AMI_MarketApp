/// CR226 — the global anchored adaptive banner. Fills `ShellBannerSlot`
/// (`home_shell.dart`, chrome order nav / ad slot / ticker tape).
///
/// Three jobs, all load-bearing:
///
///  1. **Width-derived adaptive sizing.** A `LayoutBuilder`, not
///     `MediaQuery.of(context).size.width` — the latter is the whole
///     screen and ignores safe-area insets and any future split-pane
///     layout (`CR226_adaptive_banner_slot.md` §Scope 2). The measured
///     width is floored to an int (`AdSize` takes dp as an int) and handed
///     to [AdGate.request] via the CR226 `widthDp` parameter, which reaches
///     `AdSize.getLargeAnchoredAdaptiveBannerAdSize` inside
///     `admob_real_sdk.dart`. On a width change (unfold, split-pane) the
///     old fill is disposed and a new one requested — see [didUpdateWidget]
///     analogue below via `_lastWidthDp`.
///  2. **Plan gate.** Goes through the SAME [AdGate] every other placement
///     uses — floor_pass only, collapses to zero height for every paying
///     plan including trial_trader (`ads.md:113`), the CR084 upgrade path.
///  3. **AdMob policy spacing.** A visible border-top divider is drawn
///     ABOVE the banner content itself (not by the shell) — Saiful's
///     2026-09-24 ruling: "add a visible separator/gap between the nav
///     buttons and the banner (accidental-click risk; banner sits directly
///     under nav by Saiful's choice)". Drawing it as part of THIS widget's
///     own content, rather than a fixed gap `home_shell.dart` always
///     reserves, means the separator collapses to zero height in exactly
///     the same cases the banner itself does (paid plan, no fill) — a gap
///     with nothing under it would be a stray visual artifact on every paid
///     screen, and Saiful's ruling is about the banner's OWN proximity to
///     the nav, not about reserving space unconditionally.
///
/// Deliberately NOT built on [AdSlot]: that widget is structurally pinned to
/// the five native-card call sites (`test/ads_structural_test.dart`) and has
/// no `LayoutBuilder`/width-reload concept — a persistent, adaptive, chrome
/// slot is a different shape of thing to a per-screen native card.
library;

import 'dart:async' show scheduleMicrotask, unawaited;

import 'package:ami_trade/services/ads/admob_sdk.dart';
import 'package:ami_trade/services/ads/ads_models.dart';
import 'package:ami_trade/state/ads_providers.dart';
import 'package:ami_trade/state/mandate_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/ads/house_ad_banner_strip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AnchoredAdBanner extends ConsumerStatefulWidget {
  const AnchoredAdBanner({super.key});

  @override
  ConsumerState<AnchoredAdBanner> createState() => _AnchoredAdBannerState();
}

class _AnchoredAdBannerState extends ConsumerState<AnchoredAdBanner> {
  AdDecision? _decision;
  int? _requestedWidthDp;
  String? _planAtRequest;

  Future<void> _request(int widthDp, String? plan) async {
    _requestedWidthDp = widthDp;
    _planAtRequest = plan;
    final gate = ref.read(adGateProvider);
    final decision =
        await gate.request(AdPlacement.globalBanner, widthDp: widthDp);
    if (!mounted) return;
    // A stale response for a width/plan we've since moved past (a rapid
    // unfold, or a plan flip mid-request) must not clobber a newer decision
    // — re-check against the CURRENT targets, not the ones this call closed
    // over, before committing to state.
    if (_requestedWidthDp != widthDp || _planAtRequest != plan) return;
    _disposeOldFill();
    setState(() => _decision = decision);
    if (decision.isFilled) {
      unawaited(gate.recordShown(AdPlacement.globalBanner));
    }
  }

  void _disposeOldFill() {
    final fill = _decision?.fill;
    if (fill is AdMobBannerFill) {
      unawaited(fill.handle.dispose());
    }
  }

  @override
  void dispose() {
    _disposeOldFill();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final plan = ref
        .watch(mandateNotifierProvider.select((s) => s.mandate?.plan));
    return LayoutBuilder(
      builder: (context, constraints) {
        final widthDp = constraints.maxWidth.floor();
        if (widthDp > 0 &&
            (widthDp != _requestedWidthDp || plan != _planAtRequest)) {
          // CR226 §Scope 2 — dispose + reload on width change. Scheduled as
          // a microtask (mirrors AdSlot's own pattern) so this stays a pure
          // read during build; the actual request + setState happen after.
          scheduleMicrotask(() {
            if (mounted) _request(widthDp, plan);
          });
        }
        final decision = _decision;
        if (decision == null || !decision.isFilled) {
          // Not yet resolved, refused (paid plan, cap, no inventory) — zero
          // height. There is no "loading" placeholder: a banner-shaped empty
          // box that sometimes fills is worse than no box at all, and the
          // Column above/below it (nav, ticker tape) reflow around zero
          // height with no visible jump once a real height IS reported
          // (only ever grows from 0, never shrinks mid-render).
          return const SizedBox.shrink();
        }
        final fill = decision.fill;
        final Widget content;
        if (fill is AdMobBannerFill) {
          content = SizedBox(
            width: double.infinity,
            height: fill.handle.heightDp,
            child: fill.handle.build(context),
          );
        } else if (fill is HouseAdFill) {
          content = HouseAdBannerStrip(creative: fill.creative);
        } else {
          // An unknown fill type (a future AdFormat/network combination)
          // must not render nothing forever silently — but it also must not
          // crash persistent chrome that sits on every screen. Zero height,
          // same as "not yet resolved": degrade the SLOT, not the app.
          return const SizedBox.shrink();
        }
        return _BannerWithPolicySeparator(child: content);
      },
    );
  }
}

/// The visible separator Saiful's ruling requires, drawn only around actual
/// ad content — see the library doc's job 3.
class _BannerWithPolicySeparator extends StatelessWidget {
  const _BannerWithPolicySeparator({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: AmiColors.slate700)),
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: AmiSpacing.xs),
        child: child,
      ),
    );
  }
}
