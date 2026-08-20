/// CR135 — the in-app notification centre: every row `notify()` ever wrote
/// for this user, newest-first as the server orders them.
///
/// Tap marks the row read (idempotent, server-stamped) and fires its deep
/// link through the EXISTING `DeepLinkDispatcher` — the same table a
/// tapped OS push rides, no second mapping (CR027 lock). Unread rows are
/// visually distinct (cyan accent + dot); read rows mute to slate.
///
/// CR040: the error state is visually distinct from the empty state —
/// "couldn't load" shows a retry button, "no notifications yet" never
/// does. The notifications-off banner (OS permission denied) rides above
/// the list and re-checks itself on every foreground resume, so granting
/// permission in OS Settings dismisses it without an app restart.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/app_notification.dart';
import 'package:ami_trade/screens/inbox/inbox_screen.dart' show inboxRelativeTime;
import 'package:ami_trade/screens/notifications/notification_preferences_screen.dart';
import 'package:ami_trade/services/notifications/deep_link_dispatcher.dart';
import 'package:ami_trade/state/notification_centre_providers.dart';
import 'package:ami_trade/state/notification_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/empty_state.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class NotificationCentreScreen extends ConsumerWidget {
  const NotificationCentreScreen({super.key});

  Future<void> _markAllRead(BuildContext context, WidgetRef ref) async {
    final error =
        await ref.read(notificationReadActionsProvider).markAllRead();
    if (error != null && context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error)));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final page = ref.watch(notificationPageProvider);
    final hasUnread =
        (page.valueOrNull?.items.any((n) => n.isUnread) ?? false);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            AmiScreenHeader(
              title: l.notifCentreTitle,
              titleColor: AmiColors.hexPurple,
              showBack: true,
              actions: [
                if (hasUnread)
                  IconButton(
                    icon: const Icon(Icons.done_all,
                        color: AmiColors.hexCyan, size: 22),
                    tooltip: l.notifMarkAllRead,
                    onPressed: () => _markAllRead(context, ref),
                  ),
                IconButton(
                  icon: const Icon(Icons.tune,
                      color: AmiColors.textMed, size: 22),
                  tooltip: l.notifPrefsTitle,
                  onPressed: () =>
                      Navigator.of(context).push(MaterialPageRoute<void>(
                    builder: (_) => const NotificationPreferencesScreen(),
                  )),
                ),
              ],
            ),
            const NotificationsOffBanner(),
            Expanded(
              child: page.when(
                loading: () => const Center(child: HexPulseLoader()),
                error: (e, _) => _ErrorPanel(
                  onRetry: () => ref.invalidate(notificationPageProvider),
                ),
                data: (data) {
                  if (data.items.isEmpty) {
                    return AmiEmptyState(
                      icon: Icons.notifications_none,
                      title: l.notifEmptyTitle,
                      body: l.notifEmptyBody,
                    );
                  }
                  return ListView.separated(
                    padding: const EdgeInsets.all(AmiSpacing.m),
                    itemCount: data.items.length,
                    separatorBuilder: (_, __) =>
                        const SizedBox(height: AmiSpacing.s),
                    itemBuilder: (context, i) =>
                        _NotificationCard(row: data.items[i]),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// CR040 — distinct from the empty state: names the failure and offers the
/// one recourse that can change it. Same shape as the inbox's panel.
class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_outlined,
                size: 32, color: AmiColors.hexAmber),
            const SizedBox(height: AmiSpacing.m),
            Text(
              l.notifError,
              style: AmiTypography.body,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AmiSpacing.l),
            HexButton(label: l.notifRetry, onPressed: onRetry),
          ],
        ),
      ),
    );
  }
}

class _NotificationCard extends ConsumerWidget {
  const _NotificationCard({required this.row});

  final AppNotification row;

  void _open(BuildContext context, WidgetRef ref) {
    if (row.isUnread) {
      // Fire-and-forget: the stamp re-syncs list + badge from the server
      // either way; a failure leaves the row honestly unread.
      ref.read(notificationReadActionsProvider).markRead(row.id);
    }
    final navigator = Navigator.of(context);
    DeepLinkDispatcher.dispatch(navigator, row.deepLink);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final unread = row.isUnread;
    return AccentCard(
      accent: unread ? AmiColors.hexCyan : AmiColors.slate700,
      onTap: () => _open(context, ref),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (unread) ...[
                Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: AmiColors.hexCyan,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: AmiSpacing.s),
              ],
              Expanded(
                child: Text(
                  row.title,
                  style: unread
                      ? AmiTypography.h4
                      : AmiTypography.h4.copyWith(color: AmiColors.textMed),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            row.body,
            style: AmiTypography.bodySm.copyWith(color: AmiColors.textLow),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            inboxRelativeTime(l, row.createdAt),
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
          ),
        ],
      ),
    );
  }
}

/// "Pushes are blocked at the OS level" — shown only when that is true,
/// shaped like `sharia_verdict_banner.dart` (bordered panel, icon +
/// labelMono header + caption body). Tapping calls the service's
/// `requestPermission`, whose OneSignal implementation falls back to
/// opening OS Settings when the permission was already denied — no new
/// dependency needed for the Settings deep link.
///
/// Public for the widget test; observes app lifecycle so returning from OS
/// Settings with permission granted dismisses it immediately.
class NotificationsOffBanner extends ConsumerStatefulWidget {
  const NotificationsOffBanner({super.key});

  @override
  ConsumerState<NotificationsOffBanner> createState() =>
      _NotificationsOffBannerState();
}

class _NotificationsOffBannerState extends ConsumerState<NotificationsOffBanner>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Permission may have changed in OS Settings while we were backgrounded.
    if (state == AppLifecycleState.resumed) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final service = ref.watch(notificationServiceProvider);
    if (!service.isConfigured || service.permissionGranted) {
      return const SizedBox.shrink();
    }
    final l = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(
          AmiSpacing.m, AmiSpacing.m, AmiSpacing.m, 0),
      child: InkWell(
        onTap: () async {
          await service.requestPermission();
          if (mounted) setState(() {});
        },
        borderRadius: BorderRadius.circular(AmiRadii.card),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AmiSpacing.s),
          decoration: BoxDecoration(
            color: AmiColors.slate900,
            borderRadius: BorderRadius.circular(AmiRadii.card),
            border: Border.all(color: AmiColors.hexAmber),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.notifications_off_outlined,
                      color: AmiColors.hexAmber, size: 16),
                  const SizedBox(width: 4),
                  Text(
                    l.notifOffBannerTitle,
                    style: AmiTypography.labelMono
                        .copyWith(color: AmiColors.hexAmber, fontSize: 11),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(l.notifOffBannerBody, style: AmiTypography.caption),
            ],
          ),
        ),
      ),
    );
  }
}
