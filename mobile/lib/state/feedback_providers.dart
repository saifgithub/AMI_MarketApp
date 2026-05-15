/// Riverpod state for the in-app bug reporting flow.
///
/// Submit is fire-and-forget from the UI perspective: show a spinner,
/// then either confirm success or surface an error. The sheet closes on
/// success regardless; on error it stays open so the user can retry.
library;

import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';

/// Reads the real version+build from the binary at runtime so it can
/// never drift from pubspec.yaml.
final appVersionProvider = FutureProvider<String>((ref) async {
  final info = await PackageInfo.fromPlatform();
  return '${info.version}+${info.buildNumber}';
});

String get kPlatform {
  if (Platform.isIOS) return 'ios';
  if (Platform.isAndroid) return 'android_gms';
  return 'android_gms';
}

@immutable
class FeedbackState {
  const FeedbackState({
    this.submitting = false,
    this.submitted = false,
    this.error,
  });

  final bool submitting;
  final bool submitted;
  final String? error;

  FeedbackState copyWith({
    bool? submitting,
    bool? submitted,
    String? error,
    bool clearError = false,
  }) {
    return FeedbackState(
      submitting: submitting ?? this.submitting,
      submitted: submitted ?? this.submitted,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class FeedbackNotifier extends StateNotifier<FeedbackState> {
  FeedbackNotifier(this._ref) : super(const FeedbackState());

  final Ref _ref;

  Future<bool> submitBug({
    required String category,
    required String title,
    String? steps,
    String? route,
  }) async {
    state = state.copyWith(submitting: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final token = _ref.read(authNotifierProvider).token;
      final appVersion = await _ref.read(appVersionProvider.future);
      await api.submitBugReport(
        category: category,
        title: title,
        steps: steps?.trim().isEmpty ?? true ? null : steps?.trim(),
        route: route,
        appVersion: appVersion,
        platform: kPlatform,
        token: token,
      );
      state = state.copyWith(submitting: false, submitted: true);
      return true;
    } catch (e) {
      state = state.copyWith(submitting: false, error: '$e');
      return false;
    }
  }

  void reset() {
    state = const FeedbackState();
  }
}

final feedbackNotifierProvider =
    StateNotifierProvider.autoDispose<FeedbackNotifier, FeedbackState>((ref) {
  return FeedbackNotifier(ref);
});
