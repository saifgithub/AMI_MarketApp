/// Riverpod state for the anonymous-first auth flow.
///
/// On app launch:
///   1. `AuthNotifier.bootstrap()` reads the device user_id from shared_prefs,
///      POSTs /v1/auth/anon, caches the returned token + user object.
///   2. The rest of the app reads `authNotifierProvider.user` and treats
///      `isAnonymous == false` as "claimed".
///
/// Claim flows:
///   - `startMagicLink(email)` + `verifyMagicLink(code)` — email path
///   - `signInWithApple(identityToken)` — Apple Sign-In path
///
/// Both flows post the current device user_id so the backend can attach
/// the new credential to the existing user row without minting a new id.
library;

import 'package:ami_trade/models/auth.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/notification_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

@immutable
class AuthState {
  const AuthState({
    this.user,
    this.token,
    this.loading = false,
    this.error,
    this.lastDebugCode,
    this.previousUserId,
  });

  final AuthUser? user;
  final String? token;
  final bool loading;
  final String? error;

  /// Set by the dev backend when starting a magic-link flow so the alpha
  /// tester can paste the 6-digit code without checking email. Null in
  /// production.
  final String? lastDebugCode;

  /// BL16 (AT:R38): set transiently when `user.id` changes (sign-in
  /// adopting a different user, sign-out, sign-back-in). Downstream
  /// providers (`sim`, `journal`, `mandate`, `watchlist`, `lessons`) hold
  /// per-user caches that go stale on this transition; `_AuthGate`
  /// listens for the change and invalidates them. Cleared on the next
  /// state mutation that does NOT change user.id.
  final String? previousUserId;

  AuthState copyWith({
    AuthUser? user,
    String? token,
    bool? loading,
    String? error,
    String? lastDebugCode,
    String? previousUserId,
    bool clearError = false,
    bool clearDebugCode = false,
    bool clearPreviousUserId = false,
  }) {
    return AuthState(
      user: user ?? this.user,
      token: token ?? this.token,
      loading: loading ?? this.loading,
      error: clearError ? null : (error ?? this.error),
      lastDebugCode: clearDebugCode ? null : (lastDebugCode ?? this.lastDebugCode),
      previousUserId: clearPreviousUserId
          ? null
          : (previousUserId ?? this.previousUserId),
    );
  }
}

/// BL16 (AT:R38) — outcome of a claim attempt (magic-link / Apple / Google).
/// Carries enough signal for [SignInScreen] to branch into the merge sheet
/// when account-linking Phase 1 adopted an existing user row over the
/// caller's anon.
@immutable
class ClaimOutcome {
  const ClaimOutcome({required this.success, this.adoptedFromUserId});
  final bool success;

  /// Non-null when the backend silently adopted an existing email/sub row
  /// — i.e. the pre-claim anon's user_id, ready to feed into
  /// `ApiClient.previewMerge`. Null on the common case where the same
  /// row got promoted.
  final String? adoptedFromUserId;
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._ref) : super(const AuthState());

  final Ref _ref;

  Future<void> bootstrap() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      // Replay the persisted token (if any) so the backend can recognise the
      // returning user. Without this, A2 would mint a fresh user on every
      // launch, scattering data across orphaned anonymous rows.
      final persistedToken = await DeviceUser.getToken();
      if (persistedToken != null) api.setToken(persistedToken);
      final deviceUserId = await DeviceUser.getOrCreate();
      // BL1 + BL2 (AT:R33): ship device + build context + stable install_id
      // with every bootstrap. install_id keys user_devices so two phones on
      // one Apple ID show as two rows under one user post-claim.
      final ctx = await DeviceContext.read();
      final installId = await DeviceUser.getOrCreateInstallId();
      final r = await api.bootstrapAnon(
        deviceUserId: deviceUserId,
        deviceModel: ctx.deviceModel,
        osVersion: ctx.osVersion,
        appVersion: ctx.appVersion,
        deviceInstallId: installId,
      );
      api.setToken(r.token);
      // Persist the canonical (id, token) the backend returned. If the
      // backend minted fresh (A2 path), this overwrites the stale local id.
      await DeviceUser.setIdAndToken(r.user.id, r.token);
      state = _commitUserChange(state, user: r.user, token: r.token, loading: false);
      await _pushLogin(r.user.id);
    } catch (e) {
      state = state.copyWith(
          loading: false, error: friendlyError(e, action: 'reach AMI'));
    }
  }

  /// Binds this device to [userId] for push (OneSignal `external_user_id`).
  /// Non-fatal by design — a push-registration hiccup must never block
  /// auth. Fires on every login (anon bootstrap or a claimed sign-in);
  /// idempotent on OneSignal's side, so no need to diff against the
  /// previous id.
  Future<void> _pushLogin(String userId) async {
    try {
      await _ref.read(notificationServiceProvider).login(userId);
    } catch (_) {}
  }

  /// Clears the `external_user_id` binding. Non-fatal, same reasoning as
  /// [_pushLogin].
  Future<void> _pushLogout() async {
    try {
      await _ref.read(notificationServiceProvider).logout();
    } catch (_) {}
  }

  /// Centralised state-mutation for "this op might have changed user.id".
  /// Captures the previous id into [AuthState.previousUserId] so the
  /// `_AuthGate` listener can invalidate per-user caches. If the id
  /// didn't actually change, leaves [previousUserId] alone (avoids
  /// re-firing the invalidation on a no-op token refresh).
  AuthState _commitUserChange(
    AuthState current, {
    required AuthUser user,
    required String token,
    bool loading = false,
    bool clearDebugCode = false,
  }) {
    final wasId = current.user?.id;
    final isChange = wasId != null && wasId != user.id;
    return current.copyWith(
      user: user,
      token: token,
      loading: loading,
      clearDebugCode: clearDebugCode,
      previousUserId: isChange ? wasId : null,
      clearPreviousUserId: !isChange,
    );
  }

  Future<bool> startMagicLink(String email) async {
    state = state.copyWith(loading: true, clearError: true, clearDebugCode: true);
    try {
      final api = _ref.read(apiClientProvider);
      // user_id removed from body — backend binds the claim to the bearer.
      final r = await api.startMagicLink(email: email);
      state = state.copyWith(
        loading: false,
        lastDebugCode: r.debugCode,
      );
      return r.sent;
    } catch (e) {
      state = state.copyWith(
          loading: false,
          error: friendlyError(e, action: 'send your sign-in link'));
      return false;
    }
  }

  Future<ClaimOutcome> verifyMagicLink({required String email, required String code}) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      // BL13: thread pending OnboardingSession.id through so the backend can
      // stamp claimed_user_id. One-shot — cleared on success.
      final onboardingSid = await DeviceUser.getOnboardingSessionId();
      final r = await api.verifyMagicLink(
        email: email,
        code: code,
        onboardingSessionId: onboardingSid,
      );
      api.setToken(r.token);
      await DeviceUser.setIdAndToken(r.user.id, r.token);
      await DeviceUser.clearOnboardingSessionId();
      state = _commitUserChange(
        state, user: r.user, token: r.token, clearDebugCode: true,
      );
      await _pushLogin(r.user.id);
      return ClaimOutcome(success: true, adoptedFromUserId: r.adoptedFromUserId);
    } catch (e) {
      state = state.copyWith(
          loading: false, error: friendlyError(e, action: 'sign you in'));
      return const ClaimOutcome(success: false);
    }
  }

  Future<void> signOut() async {
    final api = _ref.read(apiClientProvider);
    // Clear the external_user_id BEFORE bootstrap() mints a fresh anon
    // identity — closes the gap where a shared device could receive the
    // outgoing user's push between logout and the new identity's login.
    await _pushLogout();
    await api.signOut();
    await DeviceUser.clear();
    state = const AuthState();
    await bootstrap();
  }

  Future<ClaimOutcome> signInWithApple(String identityToken, {String? fullName}) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = state.user?.id ?? await DeviceUser.getOrCreate();
      final onboardingSid = await DeviceUser.getOnboardingSessionId();
      final r = await api.signInWithApple(
        identityToken: identityToken,
        userId: userId,
        fullName: fullName,
        onboardingSessionId: onboardingSid,
      );
      api.setToken(r.token);
      await DeviceUser.setIdAndToken(r.user.id, r.token);
      await DeviceUser.clearOnboardingSessionId();
      state = _commitUserChange(state, user: r.user, token: r.token);
      await _pushLogin(r.user.id);
      return ClaimOutcome(success: true, adoptedFromUserId: r.adoptedFromUserId);
    } catch (e) {
      state = state.copyWith(
          loading: false, error: friendlyError(e, action: 'sign you in'));
      return const ClaimOutcome(success: false);
    }
  }

  Future<ClaimOutcome> signInWithGoogle(String identityToken) async {
    // D-057 (AT:R36): Android-only at alpha. No `fullName` parameter —
    // Google ships `name` in the ID token and the backend reads it
    // directly from verified claims.
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = state.user?.id ?? await DeviceUser.getOrCreate();
      final onboardingSid = await DeviceUser.getOnboardingSessionId();
      final r = await api.signInWithGoogle(
        identityToken: identityToken,
        userId: userId,
        onboardingSessionId: onboardingSid,
      );
      api.setToken(r.token);
      await DeviceUser.setIdAndToken(r.user.id, r.token);
      await DeviceUser.clearOnboardingSessionId();
      state = _commitUserChange(state, user: r.user, token: r.token);
      await _pushLogin(r.user.id);
      return ClaimOutcome(success: true, adoptedFromUserId: r.adoptedFromUserId);
    } catch (e) {
      state = state.copyWith(
          loading: false, error: friendlyError(e, action: 'sign you in'));
      return const ClaimOutcome(success: false);
    }
  }
}

final authNotifierProvider =
    StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final n = AuthNotifier(ref);
  Future.microtask(n.bootstrap);
  return n;
});
