/// Auth data models — mirror app/schemas/auth.py shapes.
///
/// Anonymous-first: every user starts with `isAnonymous = true` and a stable
/// `id`. Claiming the account via Apple Sign-In or magic-link flips the flag
/// but keeps the same id, so the mandate + journal + portfolio survive.
library;

class AuthUser {
  AuthUser({
    required this.id,
    this.email,
    this.appleId,
    this.displayName,
    required this.isAnonymous,
    this.claimedAt,
    required this.createdAt,
  });

  final String id;
  final String? email;
  final String? appleId;
  /// User's preferred display name. Populated from Apple Sign-In's `full_name`
  /// on first claim (AT:R29), or from the mandate's `display_name` for
  /// anon-bootstrapped users.
  final String? displayName;
  final bool isAnonymous;
  final DateTime? claimedAt;
  final DateTime createdAt;

  factory AuthUser.fromJson(Map<String, dynamic> j) => AuthUser(
        id: j['id'] as String,
        email: j['email'] as String?,
        appleId: j['apple_id'] as String?,
        displayName: j['display_name'] as String?,
        isAnonymous: j['is_anonymous'] as bool? ?? true,
        claimedAt: j['claimed_at'] != null
            ? DateTime.parse(j['claimed_at'] as String)
            : null,
        createdAt: DateTime.parse(j['created_at'] as String),
      );

  bool get isClaimed => !isAnonymous;
  String get displayHandle =>
      displayName ?? email ?? (appleId != null ? 'Apple ID' : 'Guest');
}

class AnonSessionResponse {
  AnonSessionResponse({
    required this.user,
    required this.token,
    required this.isNew,
  });

  final AuthUser user;
  final String token;
  final bool isNew;

  factory AnonSessionResponse.fromJson(Map<String, dynamic> j) =>
      AnonSessionResponse(
        user: AuthUser.fromJson(j['user'] as Map<String, dynamic>),
        token: j['token'] as String,
        isNew: j['is_new'] as bool? ?? false,
      );
}

class MagicLinkStartResponse {
  MagicLinkStartResponse({required this.sent, this.debugCode});

  final bool sent;

  /// In dev / local env the backend returns the 6-digit code here so the
  /// alpha tester can copy-paste without a real email being sent. Null in
  /// production.
  final String? debugCode;

  factory MagicLinkStartResponse.fromJson(Map<String, dynamic> j) =>
      MagicLinkStartResponse(
        sent: j['sent'] as bool? ?? false,
        debugCode: j['debug_code'] as String?,
      );
}

class AuthVerifyResponse {
  AuthVerifyResponse({
    required this.user,
    required this.token,
    required this.claimed,
    this.adoptedFromUserId,
  });

  final AuthUser user;
  final String token;
  final bool claimed;

  /// BL16 (AT:R38): when account-linking Phase 1 silently adopted an
  /// existing email/sub row over the caller's pre-claim anon, this carries
  /// the orphan's user_id so the client can prompt the user to merge the
  /// stranded data via [ApiClient.previewMerge] + [ApiClient.executeMerge].
  /// Null on the common case (caller's anon promoted in place).
  final String? adoptedFromUserId;

  factory AuthVerifyResponse.fromJson(Map<String, dynamic> j) =>
      AuthVerifyResponse(
        user: AuthUser.fromJson(j['user'] as Map<String, dynamic>),
        token: j['token'] as String,
        claimed: j['claimed'] as bool? ?? false,
        adoptedFromUserId: j['adopted_from_user_id'] as String?,
      );
}
