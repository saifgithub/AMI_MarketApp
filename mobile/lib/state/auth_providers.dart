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
import 'package:ami_trade/services/device_user.dart';
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
  });

  final AuthUser? user;
  final String? token;
  final bool loading;
  final String? error;

  /// Set by the dev backend when starting a magic-link flow so the alpha
  /// tester can paste the 6-digit code without checking email. Null in
  /// production.
  final String? lastDebugCode;

  AuthState copyWith({
    AuthUser? user,
    String? token,
    bool? loading,
    String? error,
    String? lastDebugCode,
    bool clearError = false,
    bool clearDebugCode = false,
  }) {
    return AuthState(
      user: user ?? this.user,
      token: token ?? this.token,
      loading: loading ?? this.loading,
      error: clearError ? null : (error ?? this.error),
      lastDebugCode: clearDebugCode ? null : (lastDebugCode ?? this.lastDebugCode),
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._ref) : super(const AuthState());

  final Ref _ref;

  Future<void> bootstrap() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final deviceUserId = await DeviceUser.getOrCreate();
      final r = await api.bootstrapAnon(deviceUserId: deviceUserId);
      state = state.copyWith(user: r.user, token: r.token, loading: false);
    } catch (e) {
      state = state.copyWith(loading: false, error: '$e');
    }
  }

  Future<bool> startMagicLink(String email) async {
    state = state.copyWith(loading: true, clearError: true, clearDebugCode: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = state.user?.id ?? await DeviceUser.getOrCreate();
      final r = await api.startMagicLink(email: email, userId: userId);
      state = state.copyWith(
        loading: false,
        lastDebugCode: r.debugCode,
      );
      return r.sent;
    } catch (e) {
      state = state.copyWith(loading: false, error: '$e');
      return false;
    }
  }

  Future<bool> verifyMagicLink({required String email, required String code}) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = state.user?.id ?? await DeviceUser.getOrCreate();
      final r = await api.verifyMagicLink(email: email, code: code, userId: userId);
      state = state.copyWith(
        user: r.user,
        token: r.token,
        loading: false,
        clearDebugCode: true,
      );
      return true;
    } catch (e) {
      state = state.copyWith(loading: false, error: '$e');
      return false;
    }
  }

  Future<bool> signInWithApple(String identityToken, {String? fullName}) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final userId = state.user?.id ?? await DeviceUser.getOrCreate();
      final r = await api.signInWithApple(
        identityToken: identityToken,
        userId: userId,
        fullName: fullName,
      );
      state = state.copyWith(user: r.user, token: r.token, loading: false);
      return true;
    } catch (e) {
      state = state.copyWith(loading: false, error: '$e');
      return false;
    }
  }
}

final authNotifierProvider =
    StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final n = AuthNotifier(ref);
  Future.microtask(n.bootstrap);
  return n;
});
