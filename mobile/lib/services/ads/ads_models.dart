/// Ads domain models (CR122-MOBILE-A).
///
/// Store-agnostic terms for the [AdsService] facade, mirroring how CR084's
/// `purchase_models.dart` keeps the paywall free of `purchases_flutter` types.
/// Three load-bearing shapes:
///
///  * [AdPlacement] — the placement allowlist. Exactly the six surfaces
///    `ads.md:39-44` approves exist as instances; the constructor is private,
///    so a screen cannot mint a seventh at compile time, and [AdGate] refuses
///    any instance not in [AdPlacement.approved] at runtime (belt + braces —
///    per CLAUDE.md, an instruction is not a control).
///  * [HouseAdSlot] / [HouseAdCreative] — the house upsell inventory of
///    `ads.md:85-88`, plus a generic Trader upsell so an unset-AdMob build
///    fills 100% house rather than rendering a blank slot.
///  * [AdDecision] — the gate's verdict, carrying an explicit refusal reason
///    so a blocked ad is diagnosable in logs, never a silent nothing (CR040).
///
/// `daily_challenge_results` is allowlisted but carries no screen wiring yet:
/// today's challenge reveal happens inline on the Floor home screen — the
/// honeycomb, a forbidden context per `ads.md:46` — so wiring waits for a
/// dedicated results surface rather than violating the denylist.
library;

import 'package:ami_trade/models/mandate.dart';
import 'package:flutter/foundation.dart';

enum AdFormat { interstitial, nativeCard }

class AdPlacement {
  const AdPlacement._(this.id, this.format);

  /// Test-only escape hatch so the runtime allowlist refusal is provable —
  /// production code can never construct an unapproved placement.
  @visibleForTesting
  const AdPlacement.unapproved(this.id, this.format);

  final String id;
  final AdFormat format;

  static const postLessonInterstitial =
      AdPlacement._('post_lesson_interstitial', AdFormat.interstitial);
  static const dailyChallengeResults =
      AdPlacement._('daily_challenge_results', AdFormat.nativeCard);
  static const journalEmptyState =
      AdPlacement._('journal_empty_state', AdFormat.nativeCard);
  static const simPortfolioEmptyState =
      AdPlacement._('sim_portfolio_empty_state', AdFormat.nativeCard);
  static const academyHubBottom =
      AdPlacement._('academy_hub_bottom', AdFormat.nativeCard);
  static const walletAndPlan =
      AdPlacement._('wallet_and_plan', AdFormat.nativeCard);

  /// The six approved placements (`ads.md:39-44`) — the whole allowlist.
  static const approved = <AdPlacement>[
    postLessonInterstitial,
    dailyChallengeResults,
    journalEmptyState,
    simPortfolioEmptyState,
    academyHubBottom,
    walletAndPlan,
  ];

  @override
  String toString() => 'AdPlacement($id)';
}

/// The house upsell slots of `ads.md:85-88`, plus the generic fallback.
enum HouseAdSlot {
  /// Floor Pass, out of free 1-on-1s → Trader.
  oneOnOnesToTrader,

  /// Floor Pass, used its free Room → Trader.
  freeRoomToTrader,

  /// Trader, near the monthly credit cap → Floor Manager.
  creditCapToFloorManager,

  /// Trader on a halal mandate → Floor Manager.
  halalToFloorManager,

  /// Floor Pass with no targeted precondition firing. House fill must be
  /// 100% when AdMob is unset, so the untargeted case still has inventory.
  genericTrader,
}

/// Which paid tier a house creative upsells to (lands on the CR084 paywall).
enum HouseAdTargetTier { trader, floorManager }

@immutable
class HouseAdCreative {
  const HouseAdCreative({required this.slot, required this.targetTier});

  final HouseAdSlot slot;
  final HouseAdTargetTier targetTier;
}

/// Usage signals the house targeting keys on, derived from the mandate the
/// backend stamps with the *effective* plan (`mandate.py::_with_plan_state`).
@immutable
class HouseAdSignals {
  const HouseAdSignals({
    required this.effectivePlan,
    this.outOfFreeOneOnOnes = false,
    this.usedFreeRoom = false,
    this.nearCreditCap = false,
    this.halalMandate = false,
  });

  /// The backend's `effective_plan` string (`floor_pass` / `trial_trader` /
  /// `trader` / `floor_manager`). Trial and future plans deliberately match
  /// no targeting branch — fail closed, never default a new plan to ads.
  final String effectivePlan;
  final bool outOfFreeOneOnOnes;
  final bool usedFreeRoom;
  final bool nearCreditCap;
  final bool halalMandate;

  factory HouseAdSignals.fromMandate(UserMandate m) => HouseAdSignals(
        effectivePlan: m.plan,
        // The client sees only the credit ledger, not per-feature quota rows,
        // so "out of 1-on-1s" is read as "credit balance exhausted" — the
        // conservative reading that can only under-fire, never over-fire.
        outOfFreeOneOnOnes: m.creditBalance <= 0,
        usedFreeRoom: m.roomCost > 0 && m.creditBalance < m.roomCost,
        nearCreditCap:
            m.creditAllowance > 0 && m.creditBalance * 5 <= m.creditAllowance,
        halalMandate: m.compliance.halal,
      );
}

/// One piece of filled inventory. House is the only concrete kind in this
/// slice; the AdMob lane (CR122-MOBILE-C) adds its own subtype behind the
/// same facade.
@immutable
abstract class AdFill {
  const AdFill();
}

class HouseAdFill extends AdFill {
  const HouseAdFill(this.creative);
  final HouseAdCreative creative;
}

enum AdRefusalReason {
  /// The placement is not one of the six in [AdPlacement.approved].
  unapprovedPlacement,

  /// The mandate has not loaded — plan unknown, so no ads (fail closed).
  planUnknown,

  /// The effective plan is a paying tier (or an unrecognised value): no ads.
  planHasNoAds,

  /// A frequency cap from `ads.md:59-60` is at its limit.
  capReached,

  /// The persisted cap store could not be read. An unreadable cap BLOCKS the
  /// ad — allowing here would silently turn every cap into unlimited, the
  /// exact failure CR122-MOBILE-B exists to prevent.
  capStoreUnreadable,

  /// The network had nothing for this placement/signal combination.
  noInventory,
}

@immutable
class AdDecision {
  const AdDecision.filled(AdFill this.fill) : refusal = null;
  const AdDecision.refused(AdRefusalReason this.refusal) : fill = null;

  final AdFill? fill;
  final AdRefusalReason? refusal;

  bool get isFilled => fill != null;
}
