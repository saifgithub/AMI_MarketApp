/// Backend mode plumbing — Alpha / Beta / Prod.
///
/// See `docs/08_tech/backend_modes.md` for the full rationale and the
/// build-command reference. In short:
///
///   - Pre-MVP TestFlight builds set `ALLOW_BACKEND_SWITCH=true` and bake
///     all three hostnames in — testers can switch live from Settings.
///   - App Store / prod builds leave `ALLOW_BACKEND_SWITCH` off (default
///     false) and bake ONLY `AMI_API_URL_PROD`. The alpha + beta URL
///     constants resolve to empty strings at compile time, so their
///     hostnames never appear in the IPA's data segment.
///
/// The defence-in-depth lives at the binary level: a curious user can't
/// reverse-engineer dev hostnames out of the prod build. No
/// runtime/feature-flag scheme is involved.
library;

const bool kAllowBackendSwitch = bool.fromEnvironment(
  'ALLOW_BACKEND_SWITCH',
  defaultValue: false,
);


enum BackendMode {
  /// On-prem stack reached via the Cloudflare Tunnel. Alpha-only.
  alpha,

  /// GCP Cloud Run + Supabase. Beta migration target; lives alongside
  /// alpha during the cutover, replaces it after.
  beta,

  /// Production Cloud Run. Public App Store builds talk only to this.
  prod,
}


/// Static, compile-time URL constants for each mode.
///
/// A mode with an empty URL constant is considered "not present in this
/// build" — `availableModes` filters it out, and the developer toggle
/// won't offer it as a choice. This is how the prod build hides the
/// alpha + beta hostnames at the binary level.
class BackendUrls {
  BackendUrls._();

  static const String _alpha = String.fromEnvironment(
    'AMI_API_URL_ALPHA',
    defaultValue: '',
  );
  static const String _beta = String.fromEnvironment(
    'AMI_API_URL_BETA',
    defaultValue: '',
  );
  static const String _prod = String.fromEnvironment(
    'AMI_API_URL_PROD',
    defaultValue: '',
  );

  /// Legacy single-URL fallback. `AMI_API_URL` predates the per-mode
  /// constants and still works in dev (`scripts/run_dev.sh` sets it).
  /// When present and `AMI_API_URL_ALPHA` is empty, it stands in for
  /// the alpha slot so local development on a Mac keeps working
  /// without a doc-define explosion.
  static const String _legacy = String.fromEnvironment(
    'AMI_API_URL',
    defaultValue: '',
  );

  /// Returns the URL for a mode, or null if not baked into this build.
  static String? urlFor(BackendMode m) {
    switch (m) {
      case BackendMode.alpha:
        if (_alpha.isNotEmpty) return _alpha;
        // Fall back to AMI_API_URL for local-dev convenience.
        return _legacy.isNotEmpty ? _legacy : null;
      case BackendMode.beta:
        return _beta.isEmpty ? null : _beta;
      case BackendMode.prod:
        return _prod.isEmpty ? null : _prod;
    }
  }

  /// Modes whose URLs are non-empty in this build. The Settings toggle
  /// renders one row per entry. Always returns at least one entry —
  /// every build must have at least one usable backend, otherwise it
  /// can't talk to anything.
  static Set<BackendMode> get availableModes {
    return {
      for (final m in BackendMode.values)
        if (urlFor(m) != null) m,
    };
  }

  /// The mode the app starts in when nothing is stored yet.
  /// Preference order: alpha → beta → prod. The earliest available is
  /// usually the "newest dev surface" the user is testing.
  static BackendMode get defaultMode {
    if (urlFor(BackendMode.alpha) != null) return BackendMode.alpha;
    if (urlFor(BackendMode.beta) != null) return BackendMode.beta;
    return BackendMode.prod;
  }

  /// The mode a locked (prod-flavor) build must use. Always `prod` when
  /// `kAllowBackendSwitch` is false. Exposed as a property so the
  /// hydration step in BackendModeNotifier has a single source of
  /// truth to call.
  static BackendMode get lockedMode => BackendMode.prod;
}


/// Human label for a mode. Used by the Settings developer section and
/// in bug-report metadata.
String backendModeLabel(BackendMode m) {
  switch (m) {
    case BackendMode.alpha:
      return 'ALPHA';
    case BackendMode.beta:
      return 'BETA';
    case BackendMode.prod:
      return 'PROD';
  }
}


/// Parse the persisted SharedPreferences value. Returns null for unknown
/// or empty strings so the caller can fall back to the default.
BackendMode? backendModeFromString(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  switch (raw) {
    case 'alpha':
      return BackendMode.alpha;
    case 'beta':
      return BackendMode.beta;
    case 'prod':
      return BackendMode.prod;
  }
  return null;
}


String backendModeToString(BackendMode m) => m.name;
