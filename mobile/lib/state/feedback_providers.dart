/// Riverpod state for the in-app bug reporting flow.
///
/// Submit is fire-and-forget from the UI perspective: show a spinner,
/// then either confirm success or surface an error. The sheet closes on
/// success regardless; on error it stays open so the user can retry.
library;

import 'dart:io' show Platform;

import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'package:ami_trade/models/feedback.dart';
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
    this.reportId,
    this.error,
  });

  final bool submitting;
  final bool submitted;

  /// Server-assigned report UUID, set on a successful submit. The sheet
  /// shows its first 8 characters back to the user as a reference — the
  /// same short-id `/fix-bugs` uses in commit messages.
  final String? reportId;
  final String? error;

  /// Reference the user sees. Matches `LEFT(id::text, 8)` on the server.
  String? get shortId => reportId?.replaceAll('-', '').substring(0, 8);

  FeedbackState copyWith({
    bool? submitting,
    bool? submitted,
    String? reportId,
    String? error,
    bool clearError = false,
  }) {
    return FeedbackState(
      submitting: submitting ?? this.submitting,
      submitted: submitted ?? this.submitted,
      reportId: reportId ?? this.reportId,
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
    String? attachmentPath,
    String? attachmentMime,
  }) async {
    state = state.copyWith(submitting: true, clearError: true);
    try {
      final api = _ref.read(apiClientProvider);
      final token = _ref.read(authNotifierProvider).token;
      final appVersion = await _ref.read(appVersionProvider.future);
      final res = await api.submitBugReport(
        category: category,
        title: title,
        steps: steps?.trim().isEmpty ?? true ? null : steps?.trim(),
        route: route,
        appVersion: appVersion,
        platform: kPlatform,
        attachmentPath: attachmentPath,
        attachmentMime: attachmentMime,
        token: token,
      );
      state = state.copyWith(
        submitting: false,
        submitted: true,
        reportId: res['id'] as String?,
      );
      return true;
    } catch (e) {
      state = state.copyWith(
          submitting: false,
          error: friendlyError(e, action: 'send your report'));
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

/// CR043 — resolved reports the user hasn't been told about.
///
/// Deliberately NOT `autoDispose`, unlike [feedbackNotifierProvider]: that
/// one is scoped to the report sheet's lifetime, this one is fetched once
/// per cold start and must survive navigation while the toasts drain.
///
/// A failure here is silent by design. This is a courtesy message; if the
/// backend is unreachable the user has real problems, and an error banner
/// about the bug-notification system on top of them would be noise. The
/// message is not lost — `acknowledged_at` is only stamped on delivery, so
/// it surfaces on the next launch that succeeds.
final feedbackUpdatesProvider =
    FutureProvider<List<BugResolutionUpdate>>((ref) async {
  final token = ref.watch(authNotifierProvider).token;
  if (token == null) return const [];
  try {
    return await ref.read(apiClientProvider).feedbackUpdates();
  } catch (_) {
    return const [];
  }
});

/// Stamp a resolution message delivered so it fires exactly once. Failure
/// is swallowed for the same reason as above — the worst case is the user
/// sees the message twice, which beats never seeing it at all.
Future<void> ackFeedbackUpdate(WidgetRef ref, String reportId) async {
  try {
    await ref.read(apiClientProvider).ackFeedback(reportId);
  } catch (_) {
    // Retried implicitly on the next cold start.
  }
}
