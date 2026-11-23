/// CR282 - the compile-time switch for Bursa Malaysia (`.KL`) in the app.
///
/// Off by default, and off in Beta builds. Mirrors the server's
/// `MARKET_BURSA_ENABLED` but is its own gate: the client only decides whether
/// to *accept Bursa-shaped input*; the server still refuses `.KL` when its own
/// flag is off, so a stray `--dart-define` cannot make a closed market trade.
///
///     flutter build ios --release --dart-define=AMI_BURSA=true
///
/// Read as a flexible truthy STRING rather than `bool.fromEnvironment`, which
/// accepts only the literals 'true'/'false' (the `AMI_BETA` / `AMI_QA_SEMANTICS`
/// lesson).
library;

const String _bursaFlag = String.fromEnvironment('AMI_BURSA');

/// True only when the build was made with `--dart-define=AMI_BURSA=<truthy>`.
const bool kBursaEnabled = _bursaFlag == '1' ||
    _bursaFlag == 'true' ||
    _bursaFlag == 'yes' ||
    _bursaFlag == 'on';
