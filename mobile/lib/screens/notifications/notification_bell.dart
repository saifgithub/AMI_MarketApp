/// CR135 — the notification centre's bell + unread badge.
///
/// Lives in the YOU header (CR133 put settings-nature content there; the
/// CR anticipated exactly this home). A SEPARATE surface from CR102's
/// Floor-header inbox bell: that one is admin messages (`/v1/messages`),
/// this one is system/event notifications (`/v1/notifications`) — two
/// backends, two screens, deliberately not merged (lane ruling 2026-08-20).
///
/// The count is the server's `unread_count` over the `notifications`
/// table — the same table the OS icon badge reads, so the two can't drift
/// (CR135 badge-count parity). Absent (no badge) while loading or on
/// error: the badge only asserts a number it actually has; the screen
/// behind it owns the loud error state.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/notifications/notification_centre_screen.dart';
import 'package:ami_trade/state/notification_centre_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class NotificationBell extends ConsumerWidget {
  const NotificationBell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final count = ref.watch(notificationBadgeCountProvider);
    return Semantics(
      label: l.notifBellSemantics(count),
      button: true,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined,
                color: AmiColors.textLow),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
              builder: (_) => const NotificationCentreScreen(),
            )),
          ),
          if (count > 0)
            Positioned(
              top: 6,
              right: 6,
              child: IgnorePointer(
                child: Container(
                  width: 14,
                  height: 14,
                  decoration: const BoxDecoration(
                    color: AmiColors.hexCyan,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    count > 9 ? '9+' : '$count',
                    style: const TextStyle(
                      fontFamily: AmiTypography.jetBrains,
                      fontSize: 9,
                      height: 1.0,
                      fontWeight: FontWeight.w700,
                      color: AmiColors.slate900,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
