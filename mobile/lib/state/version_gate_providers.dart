/// CR121 — client version-gate state.
///
/// `VersionGateController.check()` is called on app launch and on every
/// foreground-resume (see `app.dart`'s `_VersionGateListener`) — a session
/// left open for days must not outlive a floor raise. It hits the
/// unauthenticated `GET /v1/client/release-floor` and turns the server's
/// `action` into [VersionGateStatus.block] (non-dismissible, full-screen) or
/// [VersionGateStatus.nag] (dismissible, shown at most once per app
/// session).
///
/// **Fails open, on purpose (deliberate exception to CLAUDE.md's degrade-
/// loudly rule — see the CR121 spec's "Fail-open, loudly" section).** Any
/// failure here — offline, DNS, malformed JSON, a melehost outage — is
/// caught and logged; [state] is left exactly as it was (defaults to "not
/// gated"), so the app proceeds normally. A fail-CLOSED gate would turn any
/// backend outage into a simultaneous brick of every installed client,
/// which is strictly worse than briefly serving a stale build.
library;

import 'dart:io' show Platform;

import 'package:ami_trade/i18n/locale_provider.dart';
import 'package:ami_trade/models/release_floor.dart';
import 'package:ami_trade/services/api/api_exceptions.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart' show apiClientProvider;
import 'package:flutter/foundation.dart' show debugPrint;
import 'package:flutter_riverpod/flutter_riverpod.dart';

enum VersionGateStatus { unknown, ok, nag, block }

class VersionGateState {
  const VersionGateState({
    this.status = VersionGateStatus.unknown,
    this.floor,
  });

  final VersionGateStatus status;

  /// The server response that produced [status]. Null when [status] is
  /// `unknown` or `ok` with nothing to show.
  final ReleaseFloorResponse? floor;

  bool get isBlocked => status == VersionGateStatus.block;
  bool get isNagging => status == VersionGateStatus.nag;

  VersionGateState copyWith({VersionGateStatus? status, ReleaseFloorResponse? floor}) {
    return VersionGateState(status: status ?? this.status, floor: floor ?? this.floor);
  }
}

class VersionGateController extends StateNotifier<VersionGateState> {
  VersionGateController(this._ref) : super(const VersionGateState());

  final Ref _ref;

  /// Once a nag has been dismissed this app session, it does not reappear
  /// on the next resume even if the server still returns "nag" — "shown at
  /// most once per app session" per the CR's acceptance criteria. A fresh
  /// launch (process restart) resets this, by construction: it's an
  /// in-memory field on a provider that dies with the process.
  bool _nagDismissedThisSession = false;

  Future<void> check() async {
    try {
      final api = _ref.read(apiClientProvider);
      final ctx = await DeviceContext.read();
      final locale = _ref.read(contentLocaleProvider);
      final platform = Platform.isIOS ? 'ios' : 'android';

      final floor = await api.getReleaseFloor(
        build: ctx.buildNumber,
        locale: locale,
        platform: platform,
      );

      switch (floor.action) {
        case 'block':
          state = VersionGateState(status: VersionGateStatus.block, floor: floor);
          return;
        case 'nag':
          if (_nagDismissedThisSession) {
            state = const VersionGateState(status: VersionGateStatus.ok);
            return;
          }
          state = VersionGateState(status: VersionGateStatus.nag, floor: floor);
          return;
        default:
          state = const VersionGateState(status: VersionGateStatus.ok);
      }
    } catch (e) {
      // CR121 fail-open: a lookup failure must never block the app — only
      // ever skip this one check. Still loud: logged here, and separately
      // surfaced operator-side via GET /v1/admin/config-check's
      // client_release_floor_configured field (api/admin.py).
      debugPrint('version gate check failed — failing open: $e');
    }
  }

  /// CR121 audit MAJOR — raise the gate from a 426 on ANY request, not only
  /// from [check]'s two call sites (launch and foreground-resume).
  ///
  /// Those two cover the overwhelming majority of sessions, but they leave
  /// exactly the window `VersionGateMiddleware` exists to close: a floor
  /// raised while the app is already open and foregrounded. Before this, such
  /// a user's next trade or lesson load got a 426 that `friendlyError`
  /// rendered as "that request wasn't accepted. Check the details before
  /// trying again." — no headline, no store link, and advice to re-check
  /// details that were never the problem, about a request that cannot succeed
  /// on this build.
  ///
  /// Only ever escalates to [VersionGateStatus.block]: the middleware emits
  /// 426 for the block case alone, and `action` is carried rather than assumed
  /// so a future server that reuses 426 for something softer cannot be
  /// silently mis-rendered as a hard block.
  void raiseFromServer(UpgradeRequiredException e) {
    if (e.action != 'block') return;
    if (state.isBlocked) return;
    state = VersionGateState(
      status: VersionGateStatus.block,
      floor: ReleaseFloorResponse(
        minBuild: e.minBuild,
        recommendedBuild: e.recommendedBuild,
        action: e.action,
        headline: e.headline,
        body: e.body,
        storeUrl: e.storeUrl,
      ),
    );
  }

  /// Dismiss the current nag sheet. No-ops if not currently nagging.
  void dismissNag() {
    if (state.status != VersionGateStatus.nag) return;
    _nagDismissedThisSession = true;
    state = const VersionGateState(status: VersionGateStatus.ok);
  }
}

/// Fires the launch check the moment anything first reads this provider —
/// same "construct, then `Future.microtask` the bootstrap" shape as
/// `authNotifierProvider` (auth_providers.dart). The resume check is a
/// separate call site: `app.dart`'s `_VersionGateResumeListener` calls
/// `.check()` again on every `AppLifecycleState.resumed`, because a session
/// left open for days must not outlive a floor raise.
final versionGateControllerProvider =
    StateNotifierProvider<VersionGateController, VersionGateState>((ref) {
  final controller = VersionGateController(ref);
  // CR121 audit MAJOR: subscribe to 426s from every request, not just this
  // provider's own two checks. `_VersionGateInterceptor` fires this from
  // ApiClient's error path — same wiring shape as CR125's `onUnauthorized`.
  ref.read(apiClientProvider).onUpgradeRequired = controller.raiseFromServer;
  Future.microtask(controller.check);
  return controller;
});
