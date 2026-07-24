/// Store-agnostic paywall domain models (CR084).
///
/// These wrap the RevenueCat SDK's `Offering` / `Package` / `StoreProduct` so
/// the paywall UI (and its widget tests) never import `purchases_flutter` and
/// never touch a platform channel. The [PurchaseService] abstraction maps RC's
/// wrappers into these; a fake service in tests builds them directly.
///
/// **Prices are always [PaywallPackage.priceString] — the value RevenueCat read
/// from the store for the user's region.** Nothing here hard-codes a price; the
/// canonical amounts in `tiers_and_pricing.md` are the *store's* truth, surfaced
/// through RC, not duplicated in the client.
library;

/// Canonical RC product ids (from the CR084 product catalog / webhooks.py). The
/// backend webhook maps subscriptions off the RC entitlement or a `trader_*` /
/// `floor_manager_*` product prefix, and credit packs off these exact ids
/// (`credits_starter|standard|power`). The mobile side classifies the offering
/// with the same keys so a purchase renders under the right plan/pack.
class PaywallProductIds {
  const PaywallProductIds._();

  static const traderMonthly = 'trader_monthly';
  static const traderAnnual = 'trader_annual';
  static const floorManagerMonthly = 'floor_manager_monthly';
  static const floorManagerAnnual = 'floor_manager_annual';

  static const creditsStarter = 'credits_starter';
  static const creditsStandard = 'credits_standard';
  static const creditsPower = 'credits_power';

  /// Credit counts per pack — DISPLAY ONLY. The actual grant is server-side in
  /// `credit_service.add_credit_pack` via the webhook; these mirror
  /// `webhooks.py::_CREDIT_PACKS` purely so the card can say "+60 credits".
  static const Map<String, int> packCredits = {
    creditsStarter: 60,
    creditsStandard: 300,
    creditsPower: 850,
  };
}

enum PaywallKind { subscription, creditPack, unknown }

enum PaywallTier { trader, floorManager }

enum PaywallInterval { monthly, annual }

/// One purchasable item in the live offering.
class PaywallPackage {
  const PaywallPackage({
    required this.productId,
    required this.priceString,
    required this.storeTitle,
    required this.kind,
    this.tier,
    this.interval,
    this.packCredits,
    this.raw,
  });

  /// The store product identifier (`StoreProduct.identifier`) — the same value
  /// RC sends the backend webhook as `product_id`.
  final String productId;

  /// Localized, region-correct price string from RC (e.g. "$14.99", "€14,99").
  /// The single source of truth for price — never hard-coded.
  final String priceString;

  /// RC's `StoreProduct.title` — a display fallback for an unrecognized product.
  final String storeTitle;

  final PaywallKind kind;
  final PaywallTier? tier; // subscriptions only
  final PaywallInterval? interval; // subscriptions only
  final int? packCredits; // credit packs only

  /// The underlying RC `Package`, opaque to the UI. The real service casts it
  /// back to purchase; the UI and tests never inspect it.
  final Object? raw;

  /// Classify a product id into our catalog. Falls back to a prefix match, then
  /// [PaywallKind.unknown] (still shown, so a mis-keyed product surfaces
  /// visibly rather than silently vanishing — degrade loudly).
  static ({PaywallKind kind, PaywallTier? tier, PaywallInterval? interval, int? credits})
      classify(String productId) {
    switch (productId) {
      case PaywallProductIds.traderMonthly:
        return (kind: PaywallKind.subscription, tier: PaywallTier.trader, interval: PaywallInterval.monthly, credits: null);
      case PaywallProductIds.traderAnnual:
        return (kind: PaywallKind.subscription, tier: PaywallTier.trader, interval: PaywallInterval.annual, credits: null);
      case PaywallProductIds.floorManagerMonthly:
        return (kind: PaywallKind.subscription, tier: PaywallTier.floorManager, interval: PaywallInterval.monthly, credits: null);
      case PaywallProductIds.floorManagerAnnual:
        return (kind: PaywallKind.subscription, tier: PaywallTier.floorManager, interval: PaywallInterval.annual, credits: null);
    }
    final credits = PaywallProductIds.packCredits[productId];
    if (credits != null) {
      return (kind: PaywallKind.creditPack, tier: null, interval: null, credits: credits);
    }
    if (productId.startsWith('floor_manager')) {
      return (kind: PaywallKind.subscription, tier: PaywallTier.floorManager, interval: productId.contains('annual') ? PaywallInterval.annual : PaywallInterval.monthly, credits: null);
    }
    if (productId.startsWith('trader')) {
      return (kind: PaywallKind.subscription, tier: PaywallTier.trader, interval: productId.contains('annual') ? PaywallInterval.annual : PaywallInterval.monthly, credits: null);
    }
    return (kind: PaywallKind.unknown, tier: null, interval: null, credits: null);
  }
}

/// The current RC offering, mapped to our domain. Null (not this object) means
/// "no offering configured yet" — the degrade path.
class PaywallOffering {
  const PaywallOffering({required this.identifier, required this.packages});

  final String identifier;
  final List<PaywallPackage> packages;

  bool get isEmpty => packages.isEmpty;

  List<PaywallPackage> get subscriptions =>
      packages.where((p) => p.kind == PaywallKind.subscription).toList();

  List<PaywallPackage> get creditPacks =>
      packages.where((p) => p.kind == PaywallKind.creditPack).toList();

  List<PaywallPackage> get other =>
      packages.where((p) => p.kind == PaywallKind.unknown).toList();

  /// Subscriptions for a given tier (monthly + annual), interval-ordered.
  List<PaywallPackage> tier(PaywallTier t) {
    final list = subscriptions.where((p) => p.tier == t).toList();
    list.sort((a, b) => (a.interval == PaywallInterval.monthly ? 0 : 1)
        .compareTo(b.interval == PaywallInterval.monthly ? 0 : 1));
    return list;
  }
}

enum PurchaseStatus {
  /// Store transaction completed. The caller MUST now re-read entitlement from
  /// the backend (the webhook is the grant authority) before unlocking.
  success,

  /// User dismissed the store sheet — not an error, show nothing.
  cancelled,

  /// Deferred/pending approval (e.g. Ask-to-Buy, prepaid). Entitlement is not
  /// granted yet; tell the user it's processing.
  pending,

  /// A store/network/config failure.
  error,

  /// RC is not configured (no public SDK key — DEF100). The paywall must show
  /// the info state, not a buy button, so this should not normally be reached.
  notConfigured,
}

class PurchaseOutcome {
  const PurchaseOutcome(this.status, {this.message});

  final PurchaseStatus status;
  final String? message;

  bool get isSuccess => status == PurchaseStatus.success;

  static const cancelled = PurchaseOutcome(PurchaseStatus.cancelled);
  static const pending = PurchaseOutcome(PurchaseStatus.pending);
  static const notConfigured = PurchaseOutcome(PurchaseStatus.notConfigured);
  static const success = PurchaseOutcome(PurchaseStatus.success);
}
