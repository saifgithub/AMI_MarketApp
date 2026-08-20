/// CR102 — Riverpod state for the tester inbox.
///
/// Deliberately NOT `autoDispose`: the bell badge must survive navigation
/// while the toast queue drains — the same rationale documented on
/// `feedbackUpdatesProvider` (state/feedback_providers.dart).
///
/// Deliberately NOT error-swallowing, unlike `feedbackUpdatesProvider`
/// (CR040 / CR102 doc "Degrade loudly"): the inbox screen must render a
/// distinct error + retry state — "couldn't load" must never look like
/// "no messages". A silently-empty inbox is the DEF038/DEF063 dark-feature
/// class. The bell badge alone may be absent on error (it has nothing to
/// claim); the screen may not lie.
library;

import 'package:ami_trade/models/inbox_message.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final inboxProvider = FutureProvider<List<InboxMessage>>((ref) async {
  final token = ref.watch(authNotifierProvider).token;
  if (token == null) return const [];
  return ref.watch(apiClientProvider).inboxMessages();
});

/// Unread broadcasts, derived client-side (no count endpoint by design).
/// Yields 0 while loading and on error, so the bell badge is simply absent
/// when there is nothing it can honestly claim.
final unreadInboxCountProvider = Provider<int>((ref) {
  final rows = ref.watch(inboxProvider).valueOrNull;
  if (rows == null) return 0;
  return rows.where((m) => m.isUnread).length;
});
