/// CR102 — one broadcast, its reply thread, and the composer.
///
/// Reads the parent row and its replies from the same `inboxProvider`
/// payload the list screen rendered — no extra fetch. On first frame it
/// stamps `read_at` server-side (idempotent; the badge decays via
/// `ref.invalidate`). That write is the one place failure is swallowed:
/// the same courtesy-write rationale as `ackFeedbackUpdate` — a failed
/// stamp simply re-marks on the next open. Reply failures are NOT
/// swallowed: the draft is kept and the error is shown (CR040).
///
/// The title and body are authored content and render VERBATIM — they ship
/// from the server as written (the CR043 `resolution_note` exception),
/// never localized client-side.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/inbox_message.dart';
import 'package:ami_trade/screens/inbox/inbox_screen.dart'
    show inboxRelativeTime;
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/ami_screen_header.dart';
import 'package:ami_trade/widgets/hex/hex_button.dart';
import 'package:ami_trade/widgets/hex/hex_pulse_loader.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:ami_trade/widgets/sheet_insets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class MessageDetailScreen extends ConsumerStatefulWidget {
  const MessageDetailScreen({super.key, required this.messageId});

  final String messageId;

  @override
  ConsumerState<MessageDetailScreen> createState() =>
      _MessageDetailScreenState();
}

class _MessageDetailScreenState extends ConsumerState<MessageDetailScreen> {
  final _draft = TextEditingController();
  bool _sending = false;

  /// One mark-read attempt per open, fired when the payload is first seen —
  /// which is usually the already-resolved list the user tapped through,
  /// but may be a frame later if the provider was mid-refresh.
  bool _markAttempted = false;

  @override
  void dispose() {
    _draft.dispose();
    super.dispose();
  }

  InboxMessage? _find(List<InboxMessage> rows) {
    for (final m in rows) {
      if (m.id == widget.messageId) return m;
    }
    return null;
  }

  void _maybeMarkRead(List<InboxMessage> rows) {
    if (_markAttempted) return;
    final parent = _find(rows);
    if (parent == null) return;
    _markAttempted = true;
    if (parent.readAt != null) return;
    WidgetsBinding.instance.addPostFrameCallback((_) => _markRead());
  }

  Future<void> _markRead() async {
    if (!mounted) return;
    try {
      await ref.read(apiClientProvider).markMessageRead(widget.messageId);
      if (mounted) ref.invalidate(inboxProvider);
    } catch (_) {
      // Courtesy write — the read_at stamp is idempotent and re-fires on
      // the next open; an error banner here would outrank the message.
    }
  }

  Future<void> _send() async {
    final l = AppLocalizations.of(context);
    final body = _draft.text.trim();
    if (body.isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      await ref.read(apiClientProvider).replyToMessage(
            messageId: widget.messageId,
            body: body,
          );
      if (!mounted) return;
      _draft.clear();
      ref.invalidate(inboxProvider);
      HexToast.show(context, l.inboxReplySent, accent: AmiColors.hexGreen);
    } catch (e) {
      if (!mounted) return;
      // Draft stays in the field — the user's words are not discarded.
      HexToast.show(
        context,
        friendlyError(e, action: 'send your reply'),
        accent: AmiColors.hexRed,
      );
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final inbox = ref.watch(inboxProvider);
    final rows = inbox.valueOrNull;
    if (rows != null) _maybeMarkRead(rows);
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
                error: (e, _) => _errorPanel(l),
                data: (rows) {
                  final parent = _find(rows);
                  // A vanished id is a failure, not an empty thread (CR040).
                  if (parent == null) return _errorPanel(l);
                  final replies = rows
                      .where((m) =>
                          m.direction == 'in' &&
                          m.replyToId == widget.messageId)
                      .toList()
                    ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
                  return _thread(l, parent, replies);
                },
              ),
            ),
            _composer(l),
          ],
        ),
      ),
    );
  }

  Widget _errorPanel(AppLocalizations l) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AmiSpacing.l),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_outlined,
                size: 32, color: AmiColors.hexAmber),
            const SizedBox(height: AmiSpacing.m),
            Text(l.inboxError,
                style: AmiTypography.body, textAlign: TextAlign.center),
            const SizedBox(height: AmiSpacing.l),
            HexButton(
              label: l.inboxRetry,
              onPressed: () => ref.invalidate(inboxProvider),
            ),
          ],
        ),
      ),
    );
  }

  Widget _thread(
    AppLocalizations l,
    InboxMessage parent,
    List<InboxMessage> replies,
  ) {
    return ListView(
      padding: const EdgeInsets.all(AmiSpacing.m),
      children: [
        if (parent.title != null && parent.title!.trim().isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: AmiSpacing.s),
            child: Text(parent.title!, style: AmiTypography.h3),
          ),
        Text(
          inboxRelativeTime(l, parent.createdAt),
          style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
        ),
        const SizedBox(height: AmiSpacing.m),
        Text(parent.body, style: AmiTypography.body),
        for (final reply in replies) ...[
          const SizedBox(height: AmiSpacing.l),
          Text(
            l.inboxYou,
            style: AmiTypography.labelMono
                .copyWith(color: AmiColors.hexCyan, fontSize: 11),
          ),
          const SizedBox(height: AmiSpacing.xs),
          Text(reply.body, style: AmiTypography.body),
        ],
      ],
    );
  }

  Widget _composer(AppLocalizations l) {
    return Padding(
      // DEF075 class — clears both the keyboard and the Android 3-button
      // nav bar; the larger of the two is correct in every state.
      padding: EdgeInsets.only(
        left: AmiSpacing.m,
        right: AmiSpacing.m,
        top: AmiSpacing.s,
        bottom: sheetBottomInset(MediaQuery.of(context)) + AmiSpacing.s,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: _draft,
              maxLength: 2000,
              maxLines: 4,
              minLines: 1,
              style: AmiTypography.body,
              decoration: InputDecoration(
                hintText: l.inboxReplyHint,
                counterText: '',
              ),
            ),
          ),
          const SizedBox(width: AmiSpacing.s),
          HexButton(
            label: l.inboxReplySend,
            onPressed: _sending ? null : _send,
          ),
        ],
      ),
    );
  }
}
