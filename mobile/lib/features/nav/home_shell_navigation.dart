/// CR232 round 2 (DEF: MAJOR-1 from the audit) — exposes the active
/// `HomeShell` tab's nested `Navigator` to code that has no `BuildContext`
/// inside a tab's pane, so it can push there instead of on the root
/// navigator and cover the persistent chrome.
///
/// The one caller today is [DeepLinkDispatcher], reached from
/// `PushNotificationListener` (a push tap has no `BuildContext` at all —
/// that's why `appNavigatorKey` existed) and from `NotificationCentreScreen`
/// (which already has a `BuildContext` inside a tab, so it doesn't strictly
/// need this, but goes through the same table for one code path — CR027's
/// "one route table, not one `if` per feature" lock).
///
/// `_HomeShellState` owns the real `Map<AmiTab, GlobalKey<NavigatorState>>`
/// privately (`home_shell.dart`'s `_navKeys` — unchanged, still private) and
/// publishes a read-only copy here in `initState`, before the first frame.
/// `null` means "the shell has not mounted yet" — the cold-start case a
/// notification tap can race, most plausibly when the app is launched BY the
/// tap itself. Degrade loudly, not silently: nothing here falls back to the
/// root navigator; a caller that finds `null` must queue instead (see
/// `PushNotificationListener._pendingLink`), never drop the link.
library;

import 'package:ami_trade/features/nav/ami_tab.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final homeShellNavKeysProvider =
    StateProvider<Map<AmiTab, GlobalKey<NavigatorState>>?>((ref) => null);
