/// DEF148 — the one place an exception is turned into something a user reads.
///
/// A lesson that failed to load printed the raw `DioException` to the screen:
/// stack text, `RequestOptions.validateStatus`, an MDN link and the advice to
/// "fix your request code or fix the server code". That is developer
/// diagnostics presented as app copy, and it was the **second** occurrence —
/// DEF073 was filed for a raw 502 reaching the user and produced friendly 5xx
/// handling that this call site, and 38 others, never adopted.
///
/// The reason it recurred is the shape `failure_patterns.md` keeps naming: the
/// rule lived in one call site instead of in one function. Every provider
/// wrote its own `catch (e) { error: '...: $e' }`, so "don't show the user an
/// exception" had 39 independent implementations and only one of them was
/// right. This file is the single implementation; the guard in
/// `test/friendly_error_test.dart` asserts nothing bypasses it.
///
/// **What the user is owed**, and what this returns instead of a stack:
/// what failed, in their words; why, at the granularity that changes what they
/// should do next; and whether trying again is worth anything. A timeout and a
/// 404 are the same object to Dio and completely different instructions to a
/// person — one means check your connection, the other means stop tapping
/// retry. Collapsing both into "Something went wrong" would technically pass
/// the guard below and would still be the bug.
///
/// The raw error is not discarded, it is moved: `debugPrint` in debug builds,
/// where the developer is, and nowhere near the screen.
///
/// **Not yet localized.** These strings are hardcoded English, exactly as the
/// 39 sites they replace were. That is not an improvement, it is a deferral —
/// but it is now a deferral with a single address. Localizing means giving
/// this function an `AppLocalizations`, which means the providers need a
/// context or a locale-aware error type, which is its own change.
/// `retranslate:[ar,ms]` when that happens.
library;

import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show debugPrint, kDebugMode;

/// Turns [error] into a sentence a user can act on.
///
/// [action] names what failed as a verb phrase in the user's terms — lower
/// case, no trailing punctuation: `'load your lessons'`, `'save your note'`.
/// It is the caller's contribution because only the caller knows it.
///
/// Never interpolates [error]. If you find yourself wanting to, the thing you
/// want is [debugPrint], which this already does.
String friendlyError(Object error, {required String action}) {
  if (kDebugMode) debugPrint('friendlyError($action): $error');

  final lead = "Couldn't $action";

  if (error is ServerUnavailableException) {
    return '$lead — AMI is temporarily unavailable. Try again in a moment.';
  }
  if (error is InsufficientCreditsException) {
    // Has its own surface (the credit wall). Reaching here means a caller let
    // it fall into a generic catch; say something true rather than a stack.
    return '$lead — you are out of Room credits for now.';
  }

  if (error is DioException) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return '$lead — AMI took too long to answer. Try again.';
      case DioExceptionType.connectionError:
      case DioExceptionType.unknown:
        return '$lead — AMI is unreachable. Check your connection and '
            'try again.';
      case DioExceptionType.cancel:
        return '$lead — the request was cancelled.';
      case DioExceptionType.badCertificate:
        return '$lead — the secure connection to AMI could not be verified.';
      case DioExceptionType.badResponse:
        return _forStatus(error.response?.statusCode, lead);
    }
  }

  return '$lead. Try again.';
}

/// The distinctions worth drawing for a person. A 404 and a 503 both mean "no
/// data", and only one of them is worth retrying — telling them apart is the
/// difference between a useful message and DEF151's "Tap to retry" on a
/// permanently-rejected request.
String _forStatus(int? status, String lead) {
  if (status == null) return '$lead. Try again.';
  if (status == 401 || status == 403) {
    return '$lead — please sign in again.';
  }
  if (status == 404) {
    return "$lead — that isn't available any more.";
  }
  if (status == 429) {
    return '$lead — too many requests. Wait a moment and try again.';
  }
  if (status >= 500) {
    return '$lead — AMI is temporarily unavailable. Try again in a moment.';
  }
  return '$lead. Try again.';
}
