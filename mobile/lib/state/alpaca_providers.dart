/// Riverpod state for the Alpaca paper trading link (AT:R45; reworked CR202).
///
/// CR202: every one of these now reads the device's own credential and calls
/// Alpaca directly. Nothing here touches the AMI backend — link state is
/// whether this handset holds a key, not something the server can be asked.
///
/// alpacaLinkedProvider — does this device hold a credential?
/// alpacaPortfolioProvider / alpacaPositionsProvider — live paper account data.
/// alpacaSnapshotCacheProvider — the short-lived cache the Room convene and
///   1-on-1 message calls read before uploading positions to the backend.
library;

import 'package:ami_trade/models/alpaca.dart';
import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final alpacaClientProvider = Provider<AlpacaClient>((ref) => AlpacaClient());

final alpacaLinkedProvider = FutureProvider.autoDispose<bool>((ref) async {
  return AlpacaCredentialStore.isLinked();
});

final alpacaPortfolioProvider = FutureProvider.autoDispose<AlpacaPortfolio>((ref) async {
  return ref.watch(alpacaClientProvider).account();
});

final alpacaPositionsProvider = FutureProvider.autoDispose<List<AlpacaPosition>>((ref) async {
  return ref.watch(alpacaClientProvider).positions();
});

/// Supplies the snapshot uploaded with a Room convene or a 1-on-1 turn.
///
/// Two behaviours worth stating, because both are deliberate:
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
class AlpacaSnapshotCache {
  AlpacaSnapshotCache(this._client);

  final AlpacaClient _client;

  static const Duration ttl = Duration(seconds: 60);

  AlpacaSnapshot? _cached;
  DateTime? _fetchedAt;

  /// Best-effort current snapshot; null when unavailable for any reason.
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
