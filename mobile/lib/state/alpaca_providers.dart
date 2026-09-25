/// Riverpod state for the Alpaca paper trading link (AT:R45; reworked CR202).
///
/// CR202: every one of these now reads the device's own credential and calls
/// Alpaca directly. Nothing here touches the AMI backend — link state is
/// whether this handset holds a key, not something the server can be asked.
///
/// alpacaLinkedProvider — does this device hold a credential that resolves to
///   a confirmed **paper** host? (DEF439 — see its docstring below; this is
///   NOT "does the device hold *a* credential" any more.)
/// alpacaStoredNonPaperProvider — DEF439: a credential IS stored, but it does
///   NOT resolve to a paper host. Only reachable from before this fix — see
///   its own docstring.
/// alpacaPortfolioProvider / alpacaPositionsProvider — live paper account data.
/// alpacaSnapshotCacheProvider — the short-lived cache the Room convene and
///   1-on-1 message calls read before uploading positions to the backend.
/// alpacaOpenOrdersProvider / alpacaClosedOrdersProvider — CR234, the Alpaca
///   halves of Portfolio's Orders/History sections.
library;

import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final alpacaClientProvider = Provider<AlpacaClient>((ref) => AlpacaClient());

/// DEF439 (Saiful, 2026-09-25: "add key validation. Check out alpaca key
/// format") — "linked" now means linked to a confirmed **paper** account, not
/// merely "some credential is stored."
///
/// Before this fix, a live-account credential could reach the device (the
/// connect screen's free-text endpoint field accepted any `https://` host)
/// and every "linked" gate downstream — the Portfolio Alpaca section, the
/// trade ticket's destination picker, this Settings row — treated it exactly
/// like a paper one: `kAlpacaPaperLabel` ("ALPACA PAPER") on a live account's
/// card, the destination picker offering ALPACA PAPER/BOTH for an order that
/// would then structurally refuse at `submitOrder`. The connect screen now
/// refuses a live link before it can ever be stored (see
/// `alpaca_connect_screen.dart`), so in practice a stored credential IS a
/// paper credential going forward — but this provider still RE-CHECKS the
/// host via `isLinkedToPaperAccount()` rather than trusting the mere presence
/// of a stored pair, both because a credential saved before this fix could
/// still be sitting in Keychain/Keystore (see
/// [alpacaStoredNonPaperProvider]) and because "never trust a label, check
/// the endpoint" is the rule D-071 itself established.
final alpacaLinkedProvider = FutureProvider.autoDispose<bool>((ref) async {
  return ref.watch(alpacaClientProvider).isLinkedToPaperAccount();
});

/// DEF439 — true when a credential is stored on this device but does NOT
/// resolve to a paper host, i.e. exactly the "linked before this fix, to a
/// live or otherwise non-paper endpoint" case. Only reachable pre-fix: the
/// connect screen no longer lets a live link be saved, so this can only ever
/// be true for a credential that predates DEF439 (or, per CR224, a paper
/// account Alpaca resolved to a host whose name no longer matches the
/// `paper-api`/`paper` pattern — same "not linked" treatment either way,
/// since this provider cannot distinguish the two and both cases need a
/// relink through the fixed screen).
///
/// Drives the Settings row / Portfolio section's "AMI now links Alpaca paper
/// accounts only — relink" prompt instead of silently rendering a live
/// account as though it were paper (DEF439's own root complaint).
final alpacaStoredNonPaperProvider = FutureProvider.autoDispose<bool>((ref) async {
  final isLinked = await AlpacaCredentialStore.isLinked();
  if (!isLinked) return false;
  return !await ref.watch(alpacaClientProvider).isLinkedToPaperAccount();
});

final alpacaPortfolioProvider = FutureProvider.autoDispose<AlpacaPortfolio>((ref) async {
  return ref.watch(alpacaClientProvider).account();
});

final alpacaPositionsProvider = FutureProvider.autoDispose<List<AlpacaPosition>>((ref) async {
  return ref.watch(alpacaClientProvider).positions();
});

/// CR234 — Alpaca's own OPEN orders (resting, not yet filled/cancelled/
/// expired), nested so a bracket's stop/target legs come back with their
/// parent. Feeds the Orders tab's Alpaca section.
final alpacaOpenOrdersProvider = FutureProvider.autoDispose<List<AlpacaOrder>>((ref) async {
  return ref.watch(alpacaClientProvider).orders(status: 'open');
});

/// CR234 — Alpaca's own recently-CLOSED orders (filled / cancelled /
/// expired / rejected), most-recent-first per Alpaca's own default
/// ordering. Capped at 50 — History already caps AMI's own transaction log
/// (`_closedTradeCap`) rather than fetching every trade ever made, same
/// "view default with data intact server-side" posture.
final alpacaClosedOrdersProvider = FutureProvider.autoDispose<List<AlpacaOrder>>((ref) async {
  return ref.watch(alpacaClientProvider).orders(status: 'closed', limit: 50);
});

/// Supplies the snapshot uploaded with a Room convene or a 1-on-1 turn.
///
/// Three behaviours worth stating, because all are deliberate:
///
/// **It never blocks the run.** Any failure — unlinked, offline, Alpaca down,
/// credential revoked — yields null, and null means the prompt simply carries
/// no overlay. That is exactly the path the ~100% of users without a linked
/// account already take, and it is the same degradation the server-side fetch
/// had before CR202. The failure is not swallowed silently in the product
/// sense: the Portfolio screen's own Alpaca panel surfaces the same error
/// loudly, which is where a user can actually act on it. Failing a paid Room
/// convene because a non-authoritative overlay was unavailable would be the
/// worse trade.
///
/// **It caches for a minute.** A 1-on-1 exchange sends one message per turn,
/// and each turn would otherwise re-fetch the account and positions — two
/// Alpaca calls per typed sentence, against a rate-limited API, for data that
/// does not move that fast.
///
/// **DEF430 (Saiful, 2026-09-25: "paper only") — a live/production account's
/// summary must never leave the device.** The agents only ever see a paper
/// account's cash/positions; a live account's holdings still render on the
/// Portfolio screen, they just never get uploaded. Checked with
/// [isAlpacaPaperHost] — the exact same predicate `AlpacaClient.submitOrder`/
/// `cancelOrder` use to refuse a write against a live host — rather than a
/// second copy of the host check, so the two can never drift apart on what
/// counts as "paper."
class AlpacaSnapshotCache {
  AlpacaSnapshotCache(this._client);

  final AlpacaClient _client;

  static const Duration ttl = Duration(seconds: 60);

  AlpacaSnapshot? _cached;
  DateTime? _fetchedAt;

  /// Best-effort current snapshot; null when unavailable for any reason,
  /// including a live (non-paper) linked account (DEF430).
  ///
  /// EVERYTHING is inside the try, including the credential read. That is not
  /// defensive padding: `AlpacaCredentialStore.isLinked()` reaches the
  /// Keychain / Keystore through a platform channel, and a channel that is
  /// unavailable or a keystore that cannot be opened *throws* rather than
  /// returning false. With that call outside the guard, one unreadable
  /// credential took down the whole Room convene — a paid action — for a
  /// non-authoritative overlay the user may not even have configured. Caught
  /// by `room_agent_withheld_test.dart`, which drives the real notifier with
  /// no secure-storage mock registered, i.e. exactly that condition.
  Future<AlpacaSnapshot?> current({DateTime? now}) async {
    final t = now ?? DateTime.now();
    if (_cached != null && _fetchedAt != null && t.difference(_fetchedAt!) < ttl) {
      return _cached;
    }
    try {
      if (!await AlpacaCredentialStore.isLinked()) {
        _cached = null;
        return null;
      }
      // DEF430 — a live/production account's summary must never leave the
      // device. Routed through the injected `_client` (mockable via
      // `alpacaClientProvider`, same as the `account()`/`positions()` calls
      // just below) rather than a second, ungated read of
      // `AlpacaCredentialStore` — see `AlpacaClient.isLinkedToPaperAccount`.
      if (!await _client.isLinkedToPaperAccount()) {
        _cached = null;
        return null;
      }
      final results = await Future.wait([
        _client.account(),
        _client.positions(),
      ]);
      _cached = AlpacaSnapshot(
        portfolio: results[0] as AlpacaPortfolio,
        positions: results[1] as List<AlpacaPosition>,
      );
      _fetchedAt = t;
      return _cached;
    } catch (_) {
      // Deliberately non-fatal — see the class docstring.
      return null;
    }
  }

  /// Drop the cache — called on link/unlink so a stale account cannot ride
  /// along into the next run under a credential that has since changed.
  void invalidate() {
    _cached = null;
    _fetchedAt = null;
  }
}

final alpacaSnapshotCacheProvider = Provider<AlpacaSnapshotCache>(
  (ref) => AlpacaSnapshotCache(ref.watch(alpacaClientProvider)),
);
