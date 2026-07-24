/// Billing identity — the id the RevenueCat SDK must log in with (CR084).
///
/// Mirrors `backend/app/api/billing.py::BillingIdentity`, the response of
/// `GET /v1/billing/identity`:
///
///     { "user_id": "<uuid>", "app_user_id": "<uuid>" }
///
/// `app_user_id` is the value passed to `Purchases.logIn(...)` so RC stamps it
/// on every webhook event and the server can map a purchase back to our
/// `users.id`. Today it equals `user_id`; the backend keeps it a distinct field
/// so the linkage stays explicit if the two ever diverge (e.g. a hashed alias),
/// and this client mirrors that — the SDK always logs in with [appUserId],
/// never with a locally-assumed id.
library;

class BillingIdentity {
  const BillingIdentity({required this.userId, required this.appUserId});

  /// Backend `BillingIdentity.user_id` (UUID, serialized as a string).
  final String userId;

  /// Backend `BillingIdentity.app_user_id` (string). Pass to Purchases.logIn.
  final String appUserId;

  factory BillingIdentity.fromJson(Map<String, dynamic> j) => BillingIdentity(
        userId: j['user_id'] as String,
        appUserId: j['app_user_id'] as String,
      );

  @override
  String toString() =>
      'BillingIdentity(userId: $userId, appUserId: $appUserId)';
}
