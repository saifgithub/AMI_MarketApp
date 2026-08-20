/// CR102 — the tester inbox: broadcasts from AMI HQ, one card per message.
///
/// Reached from the bell in the Floor header ('/inbox'). Renders only the
/// `direction == 'out'` rows as top-level cards (replies live inside the
/// detail thread), newest-first as the server orders them. Tap → detail,
/// which marks the message read and carries the reply composer.
///
/// CR040 acceptance #8: the error state is visually distinct from the empty
/// state — "couldn't load" shows a retry button, "no messages" never does.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/inbox_message.dart';
import 'package:ami_trade/screens/inbox/message_detail_screen.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/accent_card.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// "14m ago" / "3h ago" / "2d ago" — same shape as the CR186 order-book rows.
String inboxRelativeTime(AppLocalizations l, DateTime t) {
  final d = DateTime.now().toUtc().difference(t.toUtc());
  if (d.inMinutes < 1) return l.inboxJustNow;
  if (d.inHours < 1) return l.inboxMinutesAgo('${d.inMinutes}');
  if (d.inDays < 1) return l.inboxHoursAgo('${d.inHours}');
  return l.inboxDaysAgo('${d.inDays}');
}

class InboxScreen extends ConsumerWidget {
  const InboxScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppLocalizations.of(context);
    final inbox = ref.watch(inboxProvider);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      body: SafeArea(
        child: Column(
          children: [
            AmiScreenHeader(
              title: l.inboxTitle,
              titleColor: AmiColors.hexCyan,
              showBack: true,
            ),
            Expanded(
              child: inbox.when(
                loading: () => const Center(child: HexPulseLoader()),
                error: (e, _) => _ErrorPanel(
                  onRetry: () => ref.invalidate(inboxProvider),
                ),
                data: (rows) {
                  final broadcasts =
                      rows.where((m) => m.direction == 'out').toList();
                  if (broadcasts.isEmpty) {
                    return Center(
                      child: Padding(
                        padding: const EdgeInsets.all(AmiSpacing.l),
                        child: Text(
                          l.inboxEmpty,
                          style: AmiTypography.body
                              .copyWith(color: AmiColors.textLow),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    );
                  }
                  return ListView.separated(
                    padding: const EdgeInsets.all(AmiSpacing.m),
                    itemCount: broadcasts.length,
                    separatorBuilder: (_, __) =>
                        const SizedBox(height: AmiSpacing.s),
                    itemBuilder: (context, i) =>
                        _MessageCard(message: broadcasts[i]),
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

/// CR040 — distinct from the empty state: the message names a failure and
/// the button offers the one recourse that can change it.
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
              l.inboxError,
              style: AmiTypography.body,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AmiSpacing.l),
            HexButton(label: l.inboxRetry, onPressed: onRetry),
          ],
        ),
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({required this.message});

  final InboxMessage message;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final firstLine = message.body.split('\n').first;
    return AccentCard(
      accent: message.isHighPriority ? AmiColors.hexAmber : AmiColors.hexCyan,
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => MessageDetailScreen(messageId: message.id),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (message.isUnread) ...[
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
                  message.title ?? firstLine,
                  style: AmiTypography.h4,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (message.isHighPriority) ...[
                const SizedBox(width: AmiSpacing.s),
                Text(
                  l.inboxHighPriorityChip,
                  style: AmiTypography.labelMono
                      .copyWith(color: AmiColors.hexAmber, fontSize: 10),
                ),
              ],
            ],
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            firstLine,
            style: AmiTypography.bodySm.copyWith(color: AmiColors.textLow),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(
            inboxRelativeTime(l, message.createdAt),
            style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
          ),
        ],
      ),
    );
  }
}
