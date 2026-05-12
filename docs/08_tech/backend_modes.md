# Backend modes — Alpha / Beta / Prod

The AMI Trade backend lives at three different addresses over the
product's lifetime, one per phase. The Flutter app needs to:

1. **Pre-MVP** (Dev, Alpha, Beta builds): be able to point at any of
   the three backends at runtime, so the same TestFlight build can be
   used to test the on-prem stack, validate the GCP cutover, and
   sanity-check the future production stack.
2. **At MVP / Production** (App Store builds): connect only to the
   production backend. No alpha/beta hostnames exist in the binary;
   no toggle is reachable from the UI.

This is enforced at **compile time**, not at runtime, so a curious
user can't reverse-engineer the dev hostnames out of a shipped
binary.

---

## The three modes

| Mode | Backend lives on | Hostname | Phase it's intended for |
|---|---|---|---|
| `alpha` | melehost (on-prem), via Cloudflare Tunnel | `https://api-alpha.<domain>` | Alpha (today). |
| `beta` | GCP Cloud Run + Supabase | `https://api-beta.<domain>` | Beta (cloud migration). Same feature set as Alpha; infra swap only. |
| `prod` | GCP Cloud Run (production project) | `https://api.<domain>` | MVP. Public App Store launch. |

The three hostnames are independent — `beta` doesn't replace `alpha`
on cutover, both can be live at once during the migration. Same for
`prod` starting up while `beta` is still serving testers.

---

## Two build flavors

The Flutter app ships in two flavors, distinguished by one Dart-define
flag — `ALLOW_BACKEND_SWITCH`.

### Dev / Alpha / Beta flavor — `ALLOW_BACKEND_SWITCH=true`

```bash
flutter build ipa --release \
    --dart-define=AMI_ENV=alpha \
    --dart-define=ALLOW_BACKEND_SWITCH=true \
    --dart-define=AMI_API_URL_ALPHA=https://api-alpha.<your-domain> \
    --dart-define=AMI_API_URL_BETA=https://api-beta.<your-domain>  \
    --dart-define=AMI_API_URL_PROD=https://api.<your-domain>       \
    --dart-define=SENTRY_DSN=https://...@sentry.io/...
```

- All three hostnames are baked into the binary as Dart constants.
- The app starts in whatever mode the user last picked
  (`SharedPreferences` → `ami_backend_mode`); first launch defaults to
  `alpha`.
- Settings → **DEVELOPER** → "Active backend" shows three radio rows
  (alpha / beta / prod). Tap one to switch live — Riverpod rebuilds
  the `ApiClient` provider, every subsequent request goes to the new
  URL. The choice persists across launches.
- The active hostname is also surfaced in Settings → Developer so
  bug reports can quote it.

### MVP / Prod flavor — `ALLOW_BACKEND_SWITCH=false` (or omitted)

```bash
flutter build ipa --release \
    --dart-define=AMI_ENV=prod \
    --dart-define=AMI_API_URL_PROD=https://api.<your-domain> \
    --dart-define=SENTRY_DSN=https://...@sentry.io/...
# AMI_API_URL_ALPHA and AMI_API_URL_BETA are deliberately omitted.
# They default to empty strings and stay out of the binary entirely.
```

- Only `AMI_API_URL_PROD` is baked in; the alpha/beta constants
  resolve to empty strings at compile time, so they never appear in
  the IPA's data segment.
- The mode is **forced to `prod`** at app startup, regardless of what
  the user previously stored in `SharedPreferences`. If a tester
  upgraded from a TestFlight build to App Store and had `alpha`
  stored, the prod build's hydration step clears that key and writes
  `prod` instead. No way back.
- The Settings → DEVELOPER section is **not built** — the section
  widget is wrapped in a `kAllowBackendSwitch` check so the entire
  subtree compiles out under tree-shaking.

### Why this design

- **Defence in depth comes from the binary, not from runtime checks.**
  A toggle that exists at runtime but is "hidden" by a feature flag
  is easy to flip via deeplink, debug menu, or jailbreak. Stripping
  the hostname strings from the binary at compile time is a sharper
  boundary: there's nothing to attack.
- **The backend side does not enforce.** Saiful's call (and the right
  one for Alpha): the alpha backend doesn't refuse requests from a
  prod-flavor build, and prod doesn't refuse requests from
  alpha-flavor either. The combination of CF Access during Alpha and
  Supabase + RLS at Beta+ already gates who can reach what; adding a
  build-flavor header check would double the surface without adding
  real protection. Keep it simple.
- **The compose service name matches the public hostname.** In
  `docker-compose.yml`, the backend service is named `api-alpha`
  (matching `api-alpha.<domain>`), so the Cloudflare Tunnel ingress
  rule reads `http://api-alpha:8000` end-to-end. At Beta this name
  goes away with the on-prem stack — Cloud Run services have their
  own naming.

---

## How it's wired in code

### `lib/services/api/backend_modes.dart`

Static knobs and the three baked URLs.

```dart
const bool kAllowBackendSwitch = bool.fromEnvironment(
  'ALLOW_BACKEND_SWITCH', defaultValue: false,
);

enum BackendMode { alpha, beta, prod }

class BackendUrls {
  static const _alpha = String.fromEnvironment('AMI_API_URL_ALPHA', defaultValue: '');
  static const _beta  = String.fromEnvironment('AMI_API_URL_BETA',  defaultValue: '');
  static const _prod  = String.fromEnvironment('AMI_API_URL_PROD',  defaultValue: '');

  static String? urlFor(BackendMode m) { … }
  static BackendMode get defaultMode { … }  // alpha if available; else beta; else prod
  static Set<BackendMode> get availableModes { … }
}
```

A non-empty URL is the **declaration that the mode exists in this
build**. In a prod-flavor build, only `_prod` is non-empty, so
`availableModes == {BackendMode.prod}` and the toggle's other rows
have nothing to show.

### `lib/state/backend_mode_provider.dart`

Riverpod `StateNotifier<BackendMode>` that:

- Hydrates from `SharedPreferences` on construction, **unless**
  `kAllowBackendSwitch == false` — in that case it forces `prod` and
  removes the stored key.
- Exposes `setMode(BackendMode)` which persists the new choice.
- Other providers `watch` this so a switch re-builds them.

### `apiClientProvider`

Was a constant `Provider<ApiClient>((_) => ApiClient())`. Now it
watches `backendModeProvider` and builds a fresh `ApiClient` with the
URL for that mode. Every dependent provider sees the new client on the
next read.

### Settings UI

`SettingsScreen` renders a `_DeveloperSection` only when
`kAllowBackendSwitch` is `true`. The section shows the three
`BackendMode` rows with the current selection highlighted; tapping
calls `backendModeProvider.notifier.setMode(...)`. The active
hostname is shown beneath the radios.

---

## TestFlight → App Store transition

For users who installed a TestFlight build and then upgrade to the
App Store version:

1. **First launch under the prod build**, the hydration step in
   `BackendModeNotifier` sees `kAllowBackendSwitch == false` and:
   - sets state to `BackendMode.prod`,
   - removes `ami_backend_mode` from `SharedPreferences` (no point
     keeping a stale dev mode around).
2. **No data migration needed** because the user's mandate, journal,
   sim portfolio, etc. all live on the prod backend keyed by their
   user_id. If they signed in (claimed their anonymous account) on
   alpha, they need to claim again on prod — that's a different
   backend, with a different `auth.users` row. Alpha → Prod migration
   is a separate exercise (out of scope here; covered by Beta-phase
   Supabase data-copy in the project plan, post-MVP if needed).

In practice testers are a small set and we can hand-migrate or just
ask them to re-onboard on the prod backend.

---

## Beta retirement of `alpha`

Once Beta is live (backend on Cloud Run + Supabase), Saiful decides
when to retire the on-prem `alpha` backend:

1. The Alpha-flavor TestFlight builds still let testers switch
   between alpha / beta / prod. New builds may stop including alpha
   (drop `AMI_API_URL_ALPHA` from the build command) once testers
   have migrated.
2. When no clients are pointing at alpha, the on-prem `cloudflared`
   service and the `api-alpha.<domain>` DNS can be retired (see
   `infra/cloudflared/README.md` → "Decommission at Beta").
3. The `alpha` enum value can be deleted from `backend_modes.dart`
   at that point. Or kept around as a no-op for a release if you
   prefer a soft removal.

---

## Build-command reference

### Dev (Mac simulator / debug device)

`flutter run` from `mobile/`. The `_resolveBaseUrl()` fallback still
applies when `AMI_API_URL_*` aren't supplied: localhost:8000 on
simulator, LAN-IP:8000 on a physical device (via the `AMI_API_URL`
dart-define that `scripts/run_dev.sh` sets).

### Alpha / Beta TestFlight build

```bash
flutter build ipa --release \
    --export-method app-store \
    --dart-define=AMI_ENV=alpha \
    --dart-define=ALLOW_BACKEND_SWITCH=true \
    --dart-define=AMI_API_URL_ALPHA=https://api-alpha.<your-domain> \
    --dart-define=AMI_API_URL_BETA=https://api-beta.<your-domain>  \
    --dart-define=AMI_API_URL_PROD=https://api.<your-domain>       \
    --dart-define=SENTRY_DSN=https://...@sentry.io/...
```

### MVP / Prod App Store build

```bash
flutter build ipa --release \
    --export-method app-store \
    --dart-define=AMI_ENV=prod \
    --dart-define=AMI_API_URL_PROD=https://api.<your-domain> \
    --dart-define=SENTRY_DSN=https://...@sentry.io/...
# Note: ALLOW_BACKEND_SWITCH omitted (defaults to false).
# Note: AMI_API_URL_ALPHA + AMI_API_URL_BETA omitted (stays out of binary).
```
