/// CR172 §10 step 4 — the structured option proposal, as the server sends it.
///
/// AMI generates the candidates, the PM picks one, the deterministic floor
/// re-validates it, and what reaches this file is **one finished structure
/// with every number already computed**. The user's entire input is yes or no.
/// That is the whole feature; a manual chain browser is explicitly out of
/// scope (CR172 "Not in scope").
///
/// **Nothing in this file does arithmetic, and that is the point.** Not a
/// premium, not a max loss, not a greek, not a break-even, not a collateral
/// figure, not days-to-expiry from an expiry date. Every field is read off the
/// payload or it is `null`, and `null` renders as "not computed" — never as a
/// zero, never as a dash that could be mistaken for one, and never as a
/// client-side recomputation from the legs. This is the CR129-MOBILE fence
/// ("server-sourced only") applied to a surface where the numbers decide
/// whether someone accepts an obligation, plus `trading_math/__init__.py`'s
/// standing rule: the sum is done once, in Python, or it is not done.
///
/// **The wire keys mirror the backend names one-for-one**, because the server
/// halves already exist and the serializer does not yet:
///
///   * legs      → `trading_math/option_strategy.py::StrategyLeg`
///   * metrics   → `trading_math/option_strategy.py::StrategyMetrics`
///   * greeks    → `trading_math/greeks.py::Greeks`
///   * compliance→ `schemas/trade.py::ComplianceResult`
///                 (as `agents/safety_floor.py::check_option_open` returns it)
///
/// Slice 3 owns the route that emits this. Naming the four source structures
/// here means that serializer has one definition to match rather than a second
/// one to invent (DEF098), and it means a key that drifts is a parse miss
/// landing in a loud "not computed", not a fabricated number.
///
/// **Three-way nulls, and they are not interchangeable.** `maxLoss == null`
/// means one of three different things and the ticket says which: unbounded
/// (`unboundedLoss`), bounded by shares the user already owns
/// (`coveredByShares`), or genuinely not computed. Collapsing them is the
/// DEF059 shape — a missing figure rendered as a reassuring one.
library;

/// One leg of the structure. Mirrors `StrategyLeg` — signed contracts,
/// premium per share, one shared expiry.
class OptionProposalLeg {
  const OptionProposalLeg({
    required this.right,
    required this.strike,
    required this.quantity,
    required this.premium,
    required this.multiplier,
    required this.expiry,
    this.occSymbol,
    this.underlying,
  });

  /// 'call' | 'put'. Any other value renders verbatim rather than being
  /// forced into one of the two — an unrecognised right is a wire problem to
  /// show, not to guess at.
  final String right;

  /// All five are nullable for the same reason: a field the server did not
  /// send must not become a number here.
  final double? strike;

  /// SIGNED contracts — positive long, negative short. The sign is the only
  /// thing this class reads out of a number, and it is a classification, not
  /// a computation.
  final double? quantity;

  /// Per share, not per contract (the backend's convention).
  final double? premium;

  /// 100 on an ordinary contract. A column server-side because adjusted
  /// contracts exist and a hard-coded 100 misprices them silently.
  final double? multiplier;

  /// ISO `YYYY-MM-DD`, rendered verbatim. Not parsed and not reformatted:
  /// a date this client failed to parse would render as today, or as blank,
  /// and both are worse than the string the server sent.
  final String expiry;

  final String? occSymbol;
  final String? underlying;

  bool get isSellToOpen => (quantity ?? 0) < 0;

  factory OptionProposalLeg.fromJson(Map<String, dynamic> j) {
    return OptionProposalLeg(
      right: j['right'] as String? ?? '',
      strike: (j['strike'] as num?)?.toDouble(),
      quantity: (j['quantity'] as num?)?.toDouble(),
      premium: (j['premium'] as num?)?.toDouble(),
      multiplier: (j['multiplier'] as num?)?.toDouble(),
      expiry: j['expiry'] as String? ?? '',
      occSymbol: j['occ_symbol'] as String?,
      underlying: j['underlying'] as String?,
    );
  }
}

/// Mirrors `StrategyMetrics`. Dollar figures are totals for the structure.
class OptionProposalMetrics {
  const OptionProposalMetrics({
    this.netCost,
    this.maxLoss,
    this.maxGain,
    this.unboundedLoss = false,
    this.unboundedGain = false,
    this.breakEvens = const [],
    this.collateralRequired,
    this.hasUncoveredShortCall = false,
    this.sharesLocked,
    this.coveredByShares = false,
  });

  /// `> 0` debit paid, `< 0` credit received. Rendered with its sign exactly
  /// as sent; the DEBIT/CREDIT word is chosen from the sign, which is the
  /// server's own stated convention and not a second opinion about the value.
  final double? netCost;

  /// `null` when [unboundedLoss] or [coveredByShares] — see the library note.
  final double? maxLoss;
  final double? maxGain;
  final bool unboundedLoss;
  final bool unboundedGain;
  final List<double> breakEvens;

  /// `null` exactly when [hasUncoveredShortCall]: no cash number contains an
  /// unbounded loss, so the server sends none.
  final double? collateralRequired;
  final bool hasUncoveredShortCall;
  final double? sharesLocked;
  final bool coveredByShares;

  factory OptionProposalMetrics.fromJson(Map<String, dynamic> j) {
    return OptionProposalMetrics(
      netCost: (j['net_cost'] as num?)?.toDouble(),
      maxLoss: (j['max_loss'] as num?)?.toDouble(),
      maxGain: (j['max_gain'] as num?)?.toDouble(),
      unboundedLoss: j['unbounded_loss'] as bool? ?? false,
      unboundedGain: j['unbounded_gain'] as bool? ?? false,
      breakEvens: ((j['break_evens'] as List?) ?? const [])
          .whereType<num>()
          .map((n) => n.toDouble())
          .toList(growable: false),
      collateralRequired: (j['collateral_required'] as num?)?.toDouble(),
      hasUncoveredShortCall: j['has_uncovered_short_call'] as bool? ?? false,
      sharesLocked: (j['shares_locked'] as num?)?.toDouble(),
      coveredByShares: j['covered_by_shares'] as bool? ?? false,
    );
  }
}

/// Mirrors `Greeks` — net across the structure, per share, M15 conventions.
/// Theta is per CALENDAR day and vega/rho per volatility/rate POINT, which is
/// why the field names carry the unit: the other convention differs by ~30%
/// and a bare "theta" would not say which one arrived.
class OptionProposalGreeks {
  const OptionProposalGreeks({
    this.delta,
    this.gamma,
    this.thetaPerDay,
    this.vegaPerPoint,
    this.rhoPerPoint,
  });

  final double? delta;
  final double? gamma;
  final double? thetaPerDay;
  final double? vegaPerPoint;
  final double? rhoPerPoint;

  factory OptionProposalGreeks.fromJson(Map<String, dynamic> j) {
    return OptionProposalGreeks(
      delta: (j['delta'] as num?)?.toDouble(),
      gamma: (j['gamma'] as num?)?.toDouble(),
      thetaPerDay: (j['theta_per_day'] as num?)?.toDouble(),
      vegaPerPoint: (j['vega_per_point'] as num?)?.toDouble(),
      rhoPerPoint: (j['rho_per_point'] as num?)?.toDouble(),
    );
  }
}

/// Mirrors `ComplianceResult` as `check_option_open` returns it.
///
/// Four lists, four different meanings, and the ticket keeps them apart:
/// `violations` refuses, `notEvaluated` could not check (DEF169), `advisories`
/// checked and deliberately did not block (CR171 §6, extended to options
/// sell-to-open on 2026-08-20), and `passed` is the only thing that decides
/// whether a YES button exists at all.
class OptionProposalCompliance {
  const OptionProposalCompliance({
    required this.passed,
    this.violations = const [],
    this.notEvaluated = const [],
    this.advisories = const [],
    this.blockedBy,
  });

  /// Defaults to `false` when the key is missing. A proposal whose compliance
  /// answer did not arrive is not a proposal a user may accept — the default
  /// that fails closed is the only defensible one on a control whose whole
  /// job is refusing (DEF059).
  final bool passed;

  /// Server sentences, rendered VERBATIM. Never paraphrased, never
  /// re-authored in ARB copy: `NAKED_CALL_REFUSAL` explains a containment
  /// ruling and the halal advisory reports a Sharia position, and a
  /// client-side translation of either is a second, unverified copy of a
  /// claim (DEF158).
  final List<String> violations;
  final List<String> notEvaluated;
  final List<String> advisories;

  /// Which rule refused — 'compliance', 'long_only', … Rendered as the raw
  /// slug, uppercased, the same way the journal's compliance-block card does:
  /// the enum grows server-side and a client switch would silently mislabel
  /// the value it did not know about.
  final String? blockedBy;

  factory OptionProposalCompliance.fromJson(Map<String, dynamic> j) {
    List<String> strings(String key) => ((j[key] as List?) ?? const [])
        .whereType<String>()
        .where((s) => s.trim().isNotEmpty)
        .toList(growable: false);
    return OptionProposalCompliance(
      passed: j['passed'] as bool? ?? false,
      violations: strings('violations'),
      notEvaluated: strings('not_evaluated'),
      advisories: strings('advisories'),
      blockedBy: j['blocked_by'] as String?,
    );
  }
}

/// One costed structure, ready for a yes or a no.
class OptionProposal {
  const OptionProposal({
    required this.strategyName,
    required this.underlying,
    required this.legs,
    required this.compliance,
    this.structureId,
    this.expiry,
    this.daysToExpiry,
    this.narration,
    this.metrics,
    this.greeks,
    this.greeksReason,
    this.contracts,
    this.spot,
    this.pricedAt,
  });

  /// The PM's pick as an INDEX into the candidate set AMI built — never a
  /// structure the model described in prose. Sent back on accept so the
  /// server resolves the legs from its own list rather than from ours.
  final int? structureId;

  /// A backend slug: 'bull_call_spread', 'covered_call'. Rendered by
  /// [strategyLabel] rather than mapped through a localized lookup, so a
  /// structure a newer backend ships still names itself instead of falling
  /// into whichever bucket this build happened to know (the `RoomVerdict
  /// .action` rule).
  final String strategyName;
  final String underlying;

  /// ISO `YYYY-MM-DD`, verbatim.
  final String? expiry;

  /// Server-computed. NOT derived from [expiry] — the client has no clock the
  /// settlement calendar agrees with.
  final int? daysToExpiry;

  /// The PM's prose. Why this structure, in AMI's voice.
  final String? narration;

  final List<OptionProposalLeg> legs;

  /// `null` when the server could not cost the structure. The ticket refuses
  /// to offer YES in that state regardless of what `compliance.passed` says.
  final OptionProposalMetrics? metrics;

  final OptionProposalGreeks? greeks;

  /// Set exactly when [greeks] is null — the per-leg sentences the server put
  /// in `greeks_not_evaluated`, joined. Rendered, because a greeks block that
  /// simply is not there teaches nothing about why (CR040).
  ///
  /// **DEF363:** this used to parse `greeks_reason`, a key no server has ever
  /// sent at this level. `greeks_reason` exists on `EnrichedOptionQuote`, one
  /// leg down, and never reaches a client; the structure carries
  /// `greeks_not_evaluated`. Both tests that covered this supplied the wrong
  /// key themselves, so the parser was proven against a fixture rather than
  /// against the wire, and the reason line was unreachable on every real
  /// payload.
  final String? greeksReason;

  /// How many contracts of the structure. Server-sized against the loss
  /// budget; the ticket never multiplies by it.
  final int? contracts;

  /// The underlying's price when this was costed, and when that was. Both are
  /// null when the source could not state them — never defaulted to "now" or
  /// "today's price", which would invent the provenance the drift line at
  /// consent is measured against.
  final double? spot;
  final DateTime? pricedAt;

  final OptionProposalCompliance compliance;

  /// The slug, humanised for display: `bull_call_spread` → `BULL CALL SPREAD`.
  /// A formatting transform, deliberately not a translation table.
  String get strategyLabel =>
      strategyName.replaceAll('_', ' ').trim().toUpperCase();

  bool get isRefused => !compliance.passed;

  /// Whether any leg sells to open. Used for the ticket's own labelling only;
  /// whether the disclosure is REQUIRED is [requiresDisclosure], which reads
  /// the server's advisories and never this.
  bool get hasSellToOpen => legs.any((l) => l.isSellToOpen);

  /// The sell-to-open disclosure gate.
  ///
  /// Keyed on the server having sent an advisory, not on the client spotting
  /// a negative quantity. The halal inform-not-block ruling is the server's
  /// to make — it depends on the user's mandate, which this widget does not
  /// hold — and re-deriving the trigger here would produce a disclosure on
  /// mandates that warrant none and, far worse, none on a mandate that does
  /// the day the rule moves.
  bool get requiresDisclosure => compliance.advisories.isNotEmpty;

  /// The one gate on the YES button.
  ///
  /// Both halves are load-bearing. `compliance.passed` is the floor's answer.
  /// `metrics != null` is the structure having a price at all: a proposal the
  /// server could not cost has no max loss to consent to, and offering YES on
  /// it would be consent to an unknown.
  bool get canAccept => compliance.passed && metrics != null;

  /// The server's per-leg explanations, as one sentence.
  ///
  /// Joined rather than rendered as a list because the ARB string takes a
  /// single `{reason}`, and because a two-leg structure whose greeks both
  /// failed has one story, not two. Empty stays empty: the ticket has a
  /// distinct string for "not computed, and the server did not say why", and
  /// collapsing that into a blank reason would render them the same.
  static String? _greeksReason(Map<String, dynamic> j) {
    final raw = j['greeks_not_evaluated'];
    if (raw is! List) return null;
    final parts = raw.whereType<String>().map((s) => s.trim())
        .where((s) => s.isNotEmpty).toList();
    return parts.isEmpty ? null : parts.join('; ');
  }

  factory OptionProposal.fromJson(Map<String, dynamic> j) {
    final metrics = j['metrics'];
    final greeks = j['net_greeks'] ?? j['greeks'];
    final compliance = j['compliance'];
    return OptionProposal(
      structureId: (j['structure_id'] as num?)?.toInt(),
      strategyName: j['strategy_name'] as String? ?? '',
      underlying: j['underlying'] as String? ?? '',
      expiry: j['expiry'] as String?,
      daysToExpiry: (j['days_to_expiry'] as num?)?.toInt(),
      narration: j['narration'] as String?,
      legs: ((j['legs'] as List?) ?? const [])
          .whereType<Map>()
          .map((m) => OptionProposalLeg.fromJson(m.cast<String, dynamic>()))
          .toList(growable: false),
      metrics: metrics is Map
          ? OptionProposalMetrics.fromJson(metrics.cast<String, dynamic>())
          : null,
      greeks: greeks is Map
          ? OptionProposalGreeks.fromJson(greeks.cast<String, dynamic>())
          : null,
      greeksReason: _greeksReason(j),
      contracts: (j['contracts'] as num?)?.toInt(),
      spot: (j['spot'] as num?)?.toDouble(),
      pricedAt: DateTime.tryParse(j['priced_at'] as String? ?? ''),
      compliance: compliance is Map
          ? OptionProposalCompliance.fromJson(compliance.cast<String, dynamic>())
          : const OptionProposalCompliance(passed: false),
    );
  }
}
