/// CR043 + CR102 — cold-start toasts: bug resolutions and high-priority
/// inbox broadcasts, one queue.
///
/// Wraps the home shell. On cold start it reads `feedbackUpdatesProvider`
/// (CR043: a bug this user reported was fixed) and `inboxProvider` (CR102:
/// a priority=high broadcast not yet toasted or read) and drains both
/// through [HexToast] on one cadence, acknowledging each as it is shown —
/// one queue so the two channels cannot fire over each other.
///
/// Cold start is the only hook: the app has no `AppLifecycleState.resumed`
/// listener and no `RouteAware`, so there is no cheaper moment to check.
/// That is also the agreed behaviour — a user learns of either message the
/// next time they open the app, not while it is closed.
///
/// Acknowledgement is server-side (`acknowledged_at` / `toasted_at`), not a
/// local flag, so "you already saw this" survives a reinstall. It is
/// stamped only on display, so a message is never lost to a failed fetch —
/// it simply waits for the next launch.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/feedback.dart';
import 'package:ami_trade/models/inbox_message.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/state/inbox_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

const _kToastDuration = Duration(seconds: 5);
const _kGapBetweenToasts = Duration(milliseconds: 600);

/// Delay before the first toast, so it doesn't collide with the home
/// shell's own entrance animation.
const _kSettleDelay = Duration(milliseconds: 1200);

/// One queued toast, whatever its channel. [message] is resolved at display
/// time (it needs the l10n of the then-current context); [ack] is the
/// channel's own delivered-stamp, fired as the toast shows.
class _QueuedToast {
  const _QueuedToast({
    required this.key,
    required this.message,
    required this.accent,
    required this.icon,
    required this.ack,
  });

  /// Channel-prefixed id (`bug:`/`inbox:`) for the _seen guard — two UUID
  /// namespaces must not be able to shadow each other.
  final String key;
  final String Function(BuildContext) message;
  final Color accent;
  final IconData icon;
  final Future<void> Function() ack;
}

class BugResolutionToasts extends ConsumerStatefulWidget {
  const BugResolutionToasts({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<BugResolutionToasts> createState() =>
      _BugResolutionToastsState();
}

class _BugResolutionToastsState extends ConsumerState<BugResolutionToasts> {
  /// Keys already queued this session. Guards against a provider rebuild
  /// re-showing a message whose ack hasn't round-tripped yet.
  final _seen = <String>{};
  final _queue = <_QueuedToast>[];
  bool _draining = false;

  void _enqueueBugs(List<BugResolutionUpdate> updates) {
    _enqueue([
      for (final u in updates)
        _QueuedToast(
          key: 'bug:${u.id}',
          message: (ctx) => _bugMessage(ctx, u),
          accent: AmiColors.hexGreen,
          icon: Icons.check_circle_outline,
          ack: () => ackFeedbackUpdate(ref, u.id),
        ),
    ]);
  }

  /// CR102 acceptance #5 — priority=high broadcasts toast on the next cold
  /// start and only that one; `toasted_at` is the server-side once-only
  /// stamp. An already-read message needs no herald.
  void _enqueueInbox(List<InboxMessage> messages) {
    _enqueue([
      for (final m in messages)
        if (m.direction == 'out' &&
            m.isHighPriority &&
            m.toastedAt == null &&
            m.readAt == null)
          _QueuedToast(
            key: 'inbox:${m.id}',
            message: (_) => _inboxMessage(m),
            accent: AmiColors.hexAmber,
            icon: Icons.notifications_outlined,
            ack: () => _markToasted(m.id),
          ),
    ]);
  }

  void _enqueue(List<_QueuedToast> items) {
    final fresh = items.where((t) => _seen.add(t.key)).toList();
    if (fresh.isEmpty) return;
    _queue.addAll(fresh);
    if (!_draining) {
      _draining = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => _drain());
    }
  }

  Future<void> _drain() async {
    await Future<void>.delayed(_kSettleDelay);
    while (_queue.isNotEmpty) {
      final toast = _queue.removeAt(0);
      if (!mounted) return;
      HexToast.show(
        context,
        toast.message(context),
        accent: toast.accent,
        icon: toast.icon,
        duration: _kToastDuration,
      );
      await toast.ack();
      await Future<void>.delayed(_kToastDuration + _kGapBetweenToasts);
    }
    _draining = false;
  }

  String _bugMessage(BuildContext ctx, BugResolutionUpdate u) {
    final headline = AppLocalizations.of(ctx).bugReportResolved(u.title);
    final note = u.resolutionNote?.trim();
    return note == null || note.isEmpty ? headline : '$headline\n$note';
  }

  /// Authored content, verbatim — the title when there is one, else the
  /// body's first line. The inbox screen carries the rest.
  String _inboxMessage(InboxMessage m) {
    final title = m.title?.trim();
    return title == null || title.isEmpty ? m.body.split('\n').first : title;
  }

  Future<void> _markToasted(String messageId) async {
    try {
      await ref.read(apiClientProvider).markMessageToasted(messageId);
    } catch (_) {
      // Same courtesy-write rationale as ackFeedbackUpdate: the worst case
      // is a repeat toast next launch, which beats never showing it.
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AsyncValue<List<BugResolutionUpdate>>>(
      feedbackUpdatesProvider,
      (_, next) => next.whenData(_enqueueBugs),
    );
    ref.listen<AsyncValue<List<InboxMessage>>>(
      inboxProvider,
      (_, next) => next.whenData(_enqueueInbox),
    );
    // Either fetch may already have resolved before the listener attached.
    ref.watch(feedbackUpdatesProvider).whenData(_enqueueBugs);
    ref.watch(inboxProvider).whenData(_enqueueInbox);
    return widget.child;
  }
}
