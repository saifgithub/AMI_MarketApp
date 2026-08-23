/// CR172 — the answer to *"what does this cost right now?"*, and what moved.
///
/// Mirrors `RepriceResponse` in `backend/app/api/options.py`.
///
/// **Two objects, kept apart on purpose.** [OptionRepriceResult.structure] is
/// what a tap will cost; [OptionRepriceResult.drift] is a story about the past.
/// The server sends them as separate fields for the same reason this file keeps
/// them as separate types: a screen that merges them ends up putting a stale
/// figure on the button, which is the exact failure the re-price exists to
/// prevent (DEF305 — never act off a price nobody checked).
///
/// **Every number here is the server's.** Nothing in this file subtracts,
/// multiplies or divides. The drift arithmetic is done server-side and arrives
/// computed, because whoever does the arithmetic owns the mistake, and a client
/// that computes a max loss is a client that can be confidently wrong about the
/// worst case (DEF059).
library;

import 'package:ami_trade/models/option_proposal.dart';

/// One leg's premium then versus now.
class OptionLegDrift {
  const OptionLegDrift({
    required this.right,
    required this.strike,
    required this.quantity,
    required this.premiumNow,
    this.premiumThen,
    this.change,
  });

  final String right;
  final double strike;
  final double quantity;
  final double premiumNow;

  /// What the client was showing. `null` when it had nothing to show — a leg
  /// whose baseline is unknown has an unknown change, never a zero one.
  final double? premiumThen;
  final double? change;

  factory OptionLegDrift.fromJson(Map<String, dynamic> j) => OptionLegDrift(
        right: j['right'] as String? ?? '',
        strike: (j['strike'] as num?)?.toDouble() ?? 0.0,
        quantity: (j['quantity'] as num?)?.toDouble() ?? 0.0,
        premiumNow: (j['premium_now'] as num?)?.toDouble() ?? 0.0,
        premiumThen: (j['premium_then'] as num?)?.toDouble(),
        change: (j['change'] as num?)?.toDouble(),
      );
}

/// What moved between the price the user was shown and the price now.
///
/// Every "then" field is nullable and every derived field is null whenever its
/// baseline is. A drift against an unknown baseline is not zero drift, and
/// rendering it as zero tells the user nothing moved when the truth is that
/// nobody knows.
class OptionPriceDrift {
  const OptionPriceDrift({
    required this.netCostNow,
    this.spotThen,
    this.spotNow,
    this.spotChange,
    this.spotChangePct,
    this.netCostThen,
    this.netCostChange,
    this.netCostChangePct,
    this.maxLossThen,
    this.maxLossNow,
    this.agedSeconds,
    this.legs = const [],
  });

  final double netCostNow;
  final double? spotThen;
  final double? spotNow;
  final double? spotChange;
  final double? spotChangePct;
  final double? netCostThen;
  final double? netCostChange;
  final double? netCostChangePct;
  final double? maxLossThen;
  final double? maxLossNow;

  /// How old the price the user was looking at had become. `null` when the
  /// structure carried no `priced_at` — an age off an unknown clock is not
  /// "fresh".
  final double? agedSeconds;

  final List<OptionLegDrift> legs;

  /// Whether anything actually moved.
  ///
  /// `false` covers BOTH "nothing changed" and "we cannot tell", which is
  /// correct for the one thing it decides — whether to draw the drift panel —
  /// and wrong for anything else. A caller wanting to distinguish them reads
  /// [netCostChange] for null. The panel is suppressed when unknown because a
  /// panel headed "what moved" with every row reading *not known* is noise,
  /// while the structure's own figures beside it are freshly computed and true.
  bool get hasMoved =>
      (netCostChange != null && netCostChange!.abs() >= 0.005) ||
      (spotChange != null && spotChange!.abs() >= 0.005);

  factory OptionPriceDrift.fromJson(Map<String, dynamic> j) => OptionPriceDrift(
        netCostNow: (j['net_cost_now'] as num?)?.toDouble() ?? 0.0,
        spotThen: (j['spot_then'] as num?)?.toDouble(),
        spotNow: (j['spot_now'] as num?)?.toDouble(),
        spotChange: (j['spot_change'] as num?)?.toDouble(),
        spotChangePct: (j['spot_change_pct'] as num?)?.toDouble(),
        netCostThen: (j['net_cost_then'] as num?)?.toDouble(),
        netCostChange: (j['net_cost_change'] as num?)?.toDouble(),
        netCostChangePct: (j['net_cost_change_pct'] as num?)?.toDouble(),
        maxLossThen: (j['max_loss_then'] as num?)?.toDouble(),
        maxLossNow: (j['max_loss_now'] as num?)?.toDouble(),
        agedSeconds: (j['aged_seconds'] as num?)?.toDouble(),
        legs: ((j['legs'] as List?) ?? const [])
            .whereType<Map>()
            .map((m) => OptionLegDrift.fromJson(m.cast<String, dynamic>()))
            .toList(growable: false),
      );
}

class OptionRepriceResult {
  const OptionRepriceResult({
    required this.repriced,
    required this.compliance,
    this.structure,
    this.drift,
  });

  /// `false` means the chain could not be read, or a leg could not be
  /// transacted. It is NOT a refusal by the floor — that arrives as a
  /// [compliance] with violations and `repriced: true`. The two are kept apart
  /// because "we cannot price this" and "you may not open this" are different
  /// sentences and only one of them is about the user's mandate.
  final bool repriced;
  final OptionProposalCompliance compliance;
  final OptionProposal? structure;
  final OptionPriceDrift? drift;

  factory OptionRepriceResult.fromJson(Map<String, dynamic> j) {
    final structure = j['structure'];
    final compliance = j['compliance'];
    final drift = j['drift'];
    return OptionRepriceResult(
      repriced: (j['repriced'] as bool?) ?? false,
      structure: structure is Map
          ? OptionProposal.fromJson(structure.cast<String, dynamic>())
          : null,
      compliance: compliance is Map
          ? OptionProposalCompliance.fromJson(
              compliance.cast<String, dynamic>())
          : const OptionProposalCompliance(passed: false),
      drift: drift is Map
          ? OptionPriceDrift.fromJson(drift.cast<String, dynamic>())
          : null,
    );
  }
}

/// The result of `POST /v1/sim/options/open`.
class OptionOpenResult {
  const OptionOpenResult({
    required this.accepted,
    required this.compliance,
    this.strategyId,
    this.strategyName,
    this.netCost,
    this.collateralPosted,
  });

  final bool accepted;
  final OptionProposalCompliance compliance;
  final String? strategyId;
  final String? strategyName;
  final double? netCost;
  final double? collateralPosted;

  factory OptionOpenResult.fromJson(Map<String, dynamic> j) {
    final compliance = j['compliance'];
    return OptionOpenResult(
      accepted: (j['accepted'] as bool?) ?? false,
      compliance: compliance is Map
          ? OptionProposalCompliance.fromJson(
              compliance.cast<String, dynamic>())
          : const OptionProposalCompliance(passed: false),
      strategyId: j['strategy_id'] as String?,
      strategyName: j['strategy_name'] as String?,
      netCost: (j['net_cost'] as num?)?.toDouble(),
      collateralPosted: (j['collateral_posted'] as num?)?.toDouble(),
    );
  }
}
