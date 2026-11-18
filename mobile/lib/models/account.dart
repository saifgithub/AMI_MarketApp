/// Account closure models (CR276, CR267 WP-30) — mirror `app/api/account.py`.
///
/// `AccountPolicy` is what the server will do after the restore window, so the
/// confirm dialog can say it truthfully. `wording` is `delete` in Beta and only
/// becomes `close` if the server runs the `archive` mode with counsel's approval.
library;

class AccountPolicy {
  const AccountPolicy({
    required this.mode,
    required this.wording,
    required this.graceDays,
  });

  /// What ships in Beta, used when the policy call fails: the dialog still has
  /// to say something, and it must be the stricter, true-today answer.
  static const fallback =
      AccountPolicy(mode: 'delete', wording: 'delete', graceDays: 30);

  final String mode;
  final String wording;
  final int graceDays;

  bool get isClose => wording == 'close';

  factory AccountPolicy.fromJson(Map<String, dynamic> j) => AccountPolicy(
        mode: j['mode'] as String? ?? 'delete',
        wording: j['wording'] as String? ?? 'delete',
        graceDays: (j['grace_days'] as num?)?.toInt() ?? 30,
      );
}

class AccountClosure {
  const AccountClosure({required this.restorableUntil, required this.graceDays});

  final DateTime restorableUntil;
  final int graceDays;

  factory AccountClosure.fromJson(Map<String, dynamic> j) => AccountClosure(
        restorableUntil: DateTime.parse(j['restorable_until'] as String),
        graceDays: (j['grace_days'] as num?)?.toInt() ?? 30,
      );
}

/// A sign-in matched an account that is scheduled for deletion and still
/// inside its restore window (the server answered 409 `account_pending_deletion`).
class AccountPendingDeletion implements Exception {
  const AccountPendingDeletion(this.restorableUntil);
  final DateTime restorableUntil;

  /// The restore date from a DioException body, or null if this is not that error.
  static AccountPendingDeletion? fromResponse(int? status, Object? data) {
    if (status != 409 || data is! Map) return null;
    final detail = data['detail'];
    if (detail is! Map || detail['code'] != 'account_pending_deletion') {
      return null;
    }
    final raw = detail['restorable_until'];
    final until = raw is String ? DateTime.tryParse(raw) : null;
    return until == null ? null : AccountPendingDeletion(until);
  }
}
