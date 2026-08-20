/// CR135 — per-type push preferences, server-enforced.
///
/// One toggle per notification `type` in the backend's vocabulary — the
/// list renders what the server sends, so a type this build predates
/// still shows (its raw wire name, honest rather than hidden — DEF210
/// class). A disabled type is suppressed in `notify()`'s push path
/// server-side; the durable row still lands in the centre, and the intro
/// line says so — a toggle that silently also hid history would be lying
/// about what it does.
///
/// CR040: load failure is a distinct error + retry state, and a toggle
/// that fails to save flips back and says so in a snackbar — the thumb's
/// position always reflects the server's answer.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/app_notification.dart';
import 'package:ami_trade/state/notification_centre_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The one place a wire `type` becomes a user-facing label. Exposed for
/// the widget test: every [NotificationType] member must resolve to a
/// localised string, and an unknown wire value must fall back to the raw
/// name rather than throw or impersonate a known type.
String notificationTypeLabel(AppLocalizations l, String wireType) {
  switch (NotificationTypeJson.fromWire(wireType)) {
    case NotificationType.priceAlert:
      return l.notifTypePriceAlert;
    case NotificationType.dailyReminder:
      return l.notifTypeDailyReminder;
    case NotificationType.gameEntriesClosing:
      return l.notifTypeGameEntriesClosing;
    case NotificationType.gameFinalStretch:
      return l.notifTypeGameFinalStretch;
    case NotificationType.gameSettled:
      return l.notifTypeGameSettled;
    case NotificationType.gameRankMove:
      return l.notifTypeGameRankMove;
    case NotificationType.restingOrderFilled:
      return l.notifTypeRestingOrderFilled;
    case NotificationType.restingOrderTriggered:
      return l.notifTypeRestingOrderTriggered;
    case NotificationType.restingOrderRejected:
      return l.notifTypeRestingOrderRejected;
    case null:
      return wireType;
  }
}

class NotificationPreferencesScreen extends ConsumerWidget {
  const NotificationPreferencesScreen({super.key});

  Future<void> _toggle(
    BuildContext context,
    WidgetRef ref,
    String type,
    bool enabled,
  ) async {
    final error = await ref
        .read(notificationPrefsProvider.notifier)
        .toggle(type, enabled);
    if (error != null && context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error)));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final prefs = ref.watch(notificationPrefsProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            AmiScreenHeader(
              title: l.notifPrefsTitle,
              titleColor: AmiColors.hexPurple,
              showBack: true,
            ),
            Expanded(
              child: prefs.when(
                loading: () => const Center(child: HexPulseLoader()),
                error: (e, _) => _ErrorPanel(
                  onRetry: () =>
                      ref.read(notificationPrefsProvider.notifier).load(),
                ),
                data: (items) => ListView(
                  padding: const EdgeInsets.all(AmiSpacing.m),
                  children: [
                    Text(
                      l.notifPrefsIntro,
                      style: AmiTypography.caption
                          .copyWith(color: AmiColors.textLow),
                    ),
                    const SizedBox(height: AmiSpacing.m),
                    for (final p in items)
                      _PrefRow(
                        label: notificationTypeLabel(l, p.type),
                        enabled: p.enabled,
                        onChanged: (v) => _toggle(context, ref, p.type, v),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PrefRow extends StatelessWidget {
  const _PrefRow({
    required this.label,
    required this.enabled,
    required this.onChanged,
  });

  final String label;
  final bool enabled;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: AmiSpacing.s),
      padding: const EdgeInsets.symmetric(horizontal: AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700, width: 1),
      ),
      child: Row(
        children: [
          Expanded(child: Text(label, style: AmiTypography.body)),
          Switch(
            value: enabled,
            onChanged: onChanged,
            activeThumbColor: AmiColors.hexCyan,
          ),
        ],
      ),
    );
  }
}

/// CR040 — distinct from data-with-toggles: names the failure, offers retry.
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
              l.notifPrefsError,
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
