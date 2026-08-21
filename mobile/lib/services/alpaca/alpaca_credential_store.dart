/// Alpaca paper-trading credentials, stored on THIS DEVICE only (CR202).
///
/// Before CR202 the user's Alpaca key ID and secret were POSTed to the AMI
/// backend and stored in Postgres. That custody produced four security defects
/// on its own — DEF044 (cleartext at rest), DEF181 (the key leaking into the
/// HTTP audit log), DEF182 (the encryption key reused and failing open) and
/// DEF185 (an empty key silently disabling that encryption). The credential
/// now never leaves the handset: the app calls Alpaca directly and uploads
/// only the resulting positions.
///
/// Storage is the same Keychain / Keystore configuration `device_user.dart`
/// uses for the bearer token (CR125), and for the same reason — SharedPrefs
/// is cleartext and rides device backups.
///
/// Deliberate consequence: `first_unlock_this_device` is excluded from iCloud
/// Keychain and from backups, so the link does NOT follow the user to a new
/// phone or survive a reinstall. They re-paste the key. That is stated in the
/// connect screen rather than left to surprise them.
library;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// How the stored credential authenticates to Alpaca.
///
/// Both modes are kept because the header shape genuinely differs — this is
/// the device-side mirror of what the backend's `_paper_get` used to branch on.
/// `oauth` is unreachable today (the OAuth tab needs ALPACA_CLIENT_ID and
/// Alpaca app approval); it is modelled anyway so that enabling OAuth later is
/// a config change and not a debugging session.
enum AlpacaAuthMode { apiKey, oauth }

class AlpacaCredentials {
  const AlpacaCredentials({
    required this.keyId,
    required this.secret,
    this.mode = AlpacaAuthMode.apiKey,
  });

  /// API-key mode: the key ID. OAuth mode: the bearer access token.
  final String keyId;

  /// API-key mode: the key secret. OAuth mode: the refresh token (unused
  /// today — Alpaca's trading-app token refresh is not wired).
  final String secret;

  final AlpacaAuthMode mode;
}

class AlpacaCredentialStore {
  static const String _kKeyIdKey = 'ami.alpaca_key_id';
  static const String _kSecretKey = 'ami.alpaca_secret';
  static const String _kModeKey = 'ami.alpaca_auth_mode';

  /// Identical options to device_user.dart — see CR125. `resetOnError`
  /// recovers a corrupted keystore by wiping it, which surfaces here as
  /// "not linked": the re-paste path, not a crash.
  static const FlutterSecureStorage _storage = FlutterSecureStorage(
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock_this_device,
    ),
    aOptions: AndroidOptions(
      encryptedSharedPreferences: true,
      resetOnError: true,
    ),
  );

  static AlpacaCredentials? _cached;

  /// Read the stored pair, or null when unlinked.
  ///
  /// A half-written pair (one key present, the other missing) reads as null
  /// rather than as a credential with an empty half — an empty secret would
  /// otherwise be sent to Alpaca and come back 401, which reads to the user
  /// as "Alpaca is broken" instead of "you are not linked".
  static Future<AlpacaCredentials?> read() async {
    if (_cached != null) return _cached;
    final keyId = await _storage.read(key: _kKeyIdKey);
    final secret = await _storage.read(key: _kSecretKey);
    if (keyId == null || secret == null || keyId.isEmpty || secret.isEmpty) {
      return null;
    }
    final mode = await _storage.read(key: _kModeKey) == 'oauth'
        ? AlpacaAuthMode.oauth
        : AlpacaAuthMode.apiKey;
    _cached = AlpacaCredentials(keyId: keyId, secret: secret, mode: mode);
    return _cached;
  }

  static Future<bool> isLinked() async => (await read()) != null;

  /// Persist a validated pair. Callers must have already proved the pair works
  /// against Alpaca — storing an unverified credential just defers the failure
  /// to the next Room convene, where it is far less obvious what went wrong.
  static Future<void> save(
    String keyId,
    String secret, {
    AlpacaAuthMode mode = AlpacaAuthMode.apiKey,
  }) async {
    await _storage.write(key: _kKeyIdKey, value: keyId);
    await _storage.write(key: _kSecretKey, value: secret);
    await _storage.write(
      key: _kModeKey,
      value: mode == AlpacaAuthMode.oauth ? 'oauth' : 'apikey',
    );
    _cached = AlpacaCredentials(keyId: keyId, secret: secret, mode: mode);
  }

  /// Unlink. Purely local — there is nothing on the server to tell.
  static Future<void> clear() async {
    await _storage.delete(key: _kKeyIdKey);
    await _storage.delete(key: _kSecretKey);
    await _storage.delete(key: _kModeKey);
    _cached = null;
  }

  /// Tests only: drop the in-memory cache so a fresh read hits storage.
  static void resetCacheForTest() => _cached = null;
}
