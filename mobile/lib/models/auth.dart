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
    required this.isAnonymous,
    this.claimedAt,
    required this.createdAt,
  });

  final String id;
  final String? email;
  final String? appleId;
  final bool isAnonymous;
  final DateTime? claimedAt;
  final DateTime createdAt;

  factory AuthUser.fromJson(Map<String, dynamic> j) => AuthUser(
        id: j['id'] as String,
        email: j['email'] as String?,
        appleId: j['apple_id'] as String?,
        isAnonymous: j['is_anonymous'] as bool? ?? true,
        claimedAt: j['claimed_at'] != null
            ? DateTime.parse(j['claimed_at'] as String)
            : null,
        createdAt: DateTime.parse(j['created_at'] as String),
      );

  bool get isClaimed => !isAnonymous;
  String get displayHandle =>
      email ?? (appleId != null ? 'Apple ID' : 'Guest');
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
  });

  final AuthUser user;
  final String token;
  final bool claimed;

  factory AuthVerifyResponse.fromJson(Map<String, dynamic> j) =>
      AuthVerifyResponse(
        user: AuthUser.fromJson(j['user'] as Map<String, dynamic>),
        token: j['token'] as String,
        claimed: j['claimed'] as bool? ?? false,
      );
}
