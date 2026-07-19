/// CR043 — tells a user that a bug they reported has been fixed.
///
/// Wraps the home shell. On cold start it reads `feedbackUpdatesProvider`
/// and drains any resolved-but-unannounced reports through [HexToast], one
/// at a time, acknowledging each as it is shown.
///
/// Cold start is the only hook: the app has no `AppLifecycleState.resumed`
/// listener and no `RouteAware`, so there is no cheaper moment to check.
/// That is also the agreed behaviour — a user learns their bug was fixed
/// the next time they open the app, not while it is closed.
///
/// Acknowledgement is server-side (`acknowledged_at`), not a local flag,
/// so "you already saw this" survives a reinstall. It is stamped only on
/// display, so a message is never lost to a failed fetch — it simply waits
/// for the next launch.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/models/feedback.dart';
import 'package:ami_trade/state/feedback_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

const _kToastDuration = Duration(seconds: 5);
const _kGapBetweenToasts = Duration(milliseconds: 600);

/// Delay before the first toast, so it doesn't collide with the home
/// shell's own entrance animation.
const _kSettleDelay = Duration(milliseconds: 1200);

class BugResolutionToasts extends ConsumerStatefulWidget {
  const BugResolutionToasts({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<BugResolutionToasts> createState() =>
      _BugResolutionToastsState();
}

class _BugResolutionToastsState extends ConsumerState<BugResolutionToasts> {
  /// Ids already queued this session. Guards against a provider rebuild
  /// re-showing a message whose ack hasn't round-tripped yet.
  final _seen = <String>{};
  final _queue = <BugResolutionUpdate>[];
  bool _draining = false;

  void _enqueue(List<BugResolutionUpdate> updates) {
    final fresh = updates.where((u) => _seen.add(u.id)).toList();
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
      final update = _queue.removeAt(0);
      if (!mounted) return;
      HexToast.show(
        context,
        _messageFor(update),
        accent: AmiColors.hexGreen,
        icon: Icons.check_circle_outline,
        duration: _kToastDuration,
      );
      await ackFeedbackUpdate(ref, update.id);
      await Future<void>.delayed(_kToastDuration + _kGapBetweenToasts);
    }
    _draining = false;
  }

  String _messageFor(BugResolutionUpdate u) {
    final headline = AppLocalizations.of(context).bugReportResolved(u.title);
    final note = u.resolutionNote?.trim();
    return note == null || note.isEmpty ? headline : '$headline\n$note';
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<AsyncValue<List<BugResolutionUpdate>>>(
      feedbackUpdatesProvider,
      (_, next) => next.whenData(_enqueue),
    );
    // The fetch may already have resolved before the listener attached.
    ref.watch(feedbackUpdatesProvider).whenData(_enqueue);
    return widget.child;
  }
}
