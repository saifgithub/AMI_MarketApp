/// Sign-in screen — opens from Settings → Account.
///
/// Anonymous users see two claim paths. Federated one-tap sign-in is the
/// hero (CR050); the email code is demoted behind a "Use email instead"
/// disclosure so the primary surface stays one-tap:
///   1. Federated sign-in (primary):
///      - iOS → Sign in with Apple (`sign_in_with_apple` package; backend
///        verifies identity_token against Apple's JWKS — Phase 3, AT:R29)
///      - Android → Sign in with Google (`google_sign_in` package; backend
///        verifies ID token against Google's JWKS — D-057, AT:R36)
///   2. Continue with email (demoted, behind a disclosure) — sends a 6-digit
///      code; in dev the code is returned from the backend so the alpha
///      tester can paste it without a real email being sent. Retained as the
///      only portable cross-ecosystem recovery path + future Huawei fallback.
///
/// Already-claimed users see a "Signed in as you@example.com" line + the
/// option to stay.
library;

import 'dart:io' show Platform;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/screens/auth/merge_sheet.dart';
import 'package:ami_trade/services/api/friendly_error.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

// OAuth 2.0 **Web client ID** from GCP Console. Stamped into the Google
// ID token as `aud`; the backend verifies against `GOOGLE_AUDIENCES`.
// Empty in dev → the Google button is disabled (Google Sign-In needs
// this to return an idToken). Passed via:
//   --dart-define GOOGLE_OAUTH_WEB_CLIENT_ID=<value>
// See scripts/build_playstore.sh.
const _googleOAuthWebClientId =
    String.fromEnvironment('GOOGLE_OAUTH_WEB_CLIENT_ID', defaultValue: '');

class SignInScreen extends ConsumerStatefulWidget {
  const SignInScreen({super.key, this.showSignedOutBanner = false});

  final bool showSignedOutBanner;

  @override
  ConsumerState<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends ConsumerState<SignInScreen> {
  final _emailCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  bool _codeRequested = false;
  // CR050 — email claim is demoted behind a "Use email instead" disclosure;
  // federated one-tap sign-in is the primary surface. Hidden until tapped.
  bool _showEmail = false;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _codeCtrl.dispose();
    super.dispose();
  }

  Future<void> _requestCode() async {
    final email = _emailCtrl.text.trim();
    if (email.isEmpty) return;
    final ok = await ref
        .read(authNotifierProvider.notifier)
        .startMagicLink(email);
    if (!mounted) return;
    if (ok) {
      setState(() => _codeRequested = true);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).signInCodeSent)),
      );
    }
  }

  Future<void> _verifyCode() async {
    final email = _emailCtrl.text.trim();
    final code = _codeCtrl.text.trim();
    if (email.isEmpty || code.isEmpty) return;
    final outcome = await ref
        .read(authNotifierProvider.notifier)
        .verifyMagicLink(email: email, code: code);
    if (!mounted) return;
    if (outcome.success) {
      await _afterClaim(outcome.adoptedFromUserId);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).signInCodeFailed)),
      );
    }
  }

  /// BL16 (AT:R38): post-claim hook. When the backend signals an
  /// account-linking-Phase-1 adoption (adoptedFromUserId != null), surface
  /// the merge sheet before popping back to whoever pushed this screen.
  Future<void> _afterClaim(String? adoptedFromUserId) async {
    if (adoptedFromUserId != null) {
      await showMergeSheet(
        context, ref, adoptedFromUserId: adoptedFromUserId,
      );
    }
    if (!mounted) return;
    Navigator.of(context).pop();
  }

  Future<void> _signInWithApple() async {
    // Native Sign in with Apple → returns a real RSA-signed identity
    // token from Apple. Backend verifies the signature against Apple's
    // JWKS and the iss/aud/exp claims (OIDCVerifier, AT:R29).
    final AuthorizationCredentialAppleID credential;
    try {
      credential = await SignInWithApple.getAppleIDCredential(
        scopes: const [
          AppleIDAuthorizationScopes.email,
          AppleIDAuthorizationScopes.fullName,
        ],
      );
    } on SignInWithAppleAuthorizationException catch (e) {
      // User cancelled or denied — silent no-op for cancellation;
      // anything else surfaces as a snackbar.
      if (!mounted) return;
      if (e.code == AuthorizationErrorCode.canceled) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Apple sign-in failed: ${e.code.name}')),
      );
      return;
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content:
                Text(friendlyError(e, action: 'sign you in with Apple'))),
      );
      return;
    }

    final identityToken = credential.identityToken;
    if (identityToken == null || identityToken.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Apple returned no identity token')),
      );
      return;
    }

    // Apple only sends `givenName`/`familyName` on the first auth per
    // app install. After that they're null — we capture once and let
    // the backend persist if it wants the display name.
    final fullName = [credential.givenName, credential.familyName]
        .whereType<String>()
        .where((s) => s.isNotEmpty)
        .join(' ')
        .trim();

    final outcome = await ref.read(authNotifierProvider.notifier).signInWithApple(
          identityToken,
          fullName: fullName.isEmpty ? null : fullName,
        );
    if (!mounted) return;
    if (outcome.success) {
      await _afterClaim(outcome.adoptedFromUserId);
    } else {
      final msg = ref
              .read(authNotifierProvider)
              .error
              ?.replaceFirst('Exception: ', '') ??
          AppLocalizations.of(context).signInAppleFailed;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  Future<void> _signInWithGoogle() async {
    if (_googleOAuthWebClientId.isEmpty) {
      // Defensive — the button is disabled in this case, but if the build
      // forgot to inject the define we surface a clear error rather than
      // silently failing inside the plugin.
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Google Sign-In not configured for this build'),
        ),
      );
      return;
    }
    final googleSignIn = GoogleSignIn(
      scopes: const ['email'],
      serverClientId: _googleOAuthWebClientId,
    );
    final GoogleSignInAccount? account;
    try {
      account = await googleSignIn.signIn();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content:
                Text(friendlyError(e, action: 'sign you in with Google'))),
      );
      return;
    }
    if (account == null) {
      // User cancelled — silent no-op.
      return;
    }
    final auth = await account.authentication;
    final idToken = auth.idToken;
    if (idToken == null || idToken.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Google returned no ID token')),
      );
      return;
    }

    final outcome =
        await ref.read(authNotifierProvider.notifier).signInWithGoogle(idToken);
    if (!mounted) return;
    if (outcome.success) {
      await _afterClaim(outcome.adoptedFromUserId);
    } else {
      final msg = ref
              .read(authNotifierProvider)
              .error
              ?.replaceFirst('Exception: ', '') ??
          AppLocalizations.of(context).signInGoogleFailed;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authNotifierProvider);
    final user = auth.user;
    final l = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(
        backgroundColor: AmiColors.glassChrome,
        title: Text(l.signInHeading,
            style: AmiTypography.labelMono.copyWith(color: AmiColors.hexBlue)),
        iconTheme: const IconThemeData(color: AmiColors.textHigh),
        elevation: 0,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(AmiSpacing.m),
          children: [
            if (widget.showSignedOutBanner) ...[
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AmiSpacing.m,
                  vertical: AmiSpacing.s,
                ),
                decoration: BoxDecoration(
                  color: AmiColors.glassChrome,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AmiColors.textMed.withAlpha(60)),
                ),
                child: Text(
                  l.settingsSignedOut,
                  style: AmiTypography.caption
                      .copyWith(color: AmiColors.textMed),
                ),
              ),
              const SizedBox(height: AmiSpacing.m),
            ],
            if (user != null && !user.isAnonymous) ...[
              _SignedInCard(user: user),
            ] else ...[
              Text(
                l.signInIntro,
                style: AmiTypography.body,
              ),
              const SizedBox(height: AmiSpacing.l),
              // One-tap federated sign-in is the hero. Apple on iOS,
              // Google on Android — per-platform, no cross-pollination
              // (D-057). This is the "just use your Apple/Android OAuth" path.
              if (Platform.isIOS)
                _AppleButton(
                  onPressed: auth.loading ? null : _signInWithApple,
                )
              else if (Platform.isAndroid)
                _GoogleButton(
                  onPressed: (auth.loading || _googleOAuthWebClientId.isEmpty)
                      ? null
                      : _signInWithGoogle,
                ),
              const SizedBox(height: AmiSpacing.m),
              // CR050 — email 6-digit code retained but demoted: it's the only
              // portable cross-ecosystem recovery path (Apple ID is iOS-only,
              // Google Android-only) and the future Huawei fallback. Hidden
              // behind a disclosure so the primary surface stays one-tap.
              if (_showEmail)
                _EmailClaimCard(
                  emailCtrl: _emailCtrl,
                  codeCtrl: _codeCtrl,
                  codeRequested: _codeRequested,
                  loading: auth.loading,
                  onRequestCode: _requestCode,
                  onVerifyCode: _verifyCode,
                  debugCode: auth.lastDebugCode,
                )
              else
                Center(
                  child: TextButton(
                    onPressed: () => setState(() => _showEmail = true),
                    child: Text(
                      l.signInUseEmailInstead,
                      style: AmiTypography.labelMono
                          .copyWith(color: AmiColors.textLow),
                    ),
                  ),
                ),
            ],
            if (auth.error != null) ...[
              const SizedBox(height: AmiSpacing.m),
              Text(
                auth.error!,
                style: AmiTypography.caption
                    .copyWith(color: AmiColors.hexRed),
              ),
            ],
            const SizedBox(height: AmiSpacing.xl),
            const _LegalFootnote(),
          ],
        ),
      ),
    );
  }
}

class _SignedInCard extends StatelessWidget {
  const _SignedInCard({required this.user});
  final dynamic user;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.hexGreen),
      ),
      child: Row(
        children: [
          const Icon(Icons.check_circle, color: AmiColors.hexGreen, size: 18),
          const SizedBox(width: AmiSpacing.s),
          Expanded(
            child: Text(
              AppLocalizations.of(context).signInSignedInAs(user.displayHandle),
              style: AmiTypography.body,
            ),
          ),
        ],
      ),
    );
  }
}

class _AppleButton extends StatelessWidget {
  const _AppleButton({required this.onPressed});
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: FilledButton.icon(
        onPressed: onPressed,
        icon: const Icon(Icons.apple, size: 22, color: Colors.black),
        label: Text(AppLocalizations.of(context).signInWithApple),
        style: FilledButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: Colors.black,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AmiRadii.card),
          ),
        ),
      ),
    );
  }
}

class _GoogleButton extends StatelessWidget {
  const _GoogleButton({required this.onPressed});
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: FilledButton.icon(
        onPressed: onPressed,
        // Material icons doesn't ship a Google G mark — using a generic
        // login icon. Swap for a brand asset (assets/icons/google.svg)
        // once design produces one. The button still meets Google's
        // brand guidelines for non-prominent placements: white background,
        // black text, no specific G required for non-marketing UI.
        icon: const Icon(Icons.login, size: 20, color: Colors.black),
        label: Text(AppLocalizations.of(context).signInWithGoogle),
        style: FilledButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: Colors.black,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AmiRadii.card),
          ),
        ),
      ),
    );
  }
}

class _EmailClaimCard extends StatelessWidget {
  const _EmailClaimCard({
    required this.emailCtrl,
    required this.codeCtrl,
    required this.codeRequested,
    required this.loading,
    required this.onRequestCode,
    required this.onVerifyCode,
    required this.debugCode,
  });

  final TextEditingController emailCtrl;
  final TextEditingController codeCtrl;
  final bool codeRequested;
  final bool loading;
  final VoidCallback onRequestCode;
  final VoidCallback onVerifyCode;
  final String? debugCode;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Container(
      padding: const EdgeInsets.all(AmiSpacing.m),
      decoration: BoxDecoration(
        color: AmiColors.slate800,
        borderRadius: BorderRadius.circular(AmiRadii.card),
        border: Border.all(color: AmiColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.signInWithEmail,
              style: AmiTypography.labelMono
                  .copyWith(color: AmiColors.hexBlue)),
          const SizedBox(height: AmiSpacing.m),
          TextField(
            controller: emailCtrl,
            keyboardType: TextInputType.emailAddress,
            autocorrect: false,
            enableSuggestions: false,
            style: AmiTypography.body,
            decoration: InputDecoration(
              hintText: l.signInEmailHint,
              hintStyle: const TextStyle(color: AmiColors.textLow),
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: AmiSpacing.s),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: loading ? null : onRequestCode,
                  child: Text(codeRequested ? l.signInResendCode : l.signInSendCode),
                ),
              ),
            ],
          ),
          if (codeRequested) ...[
            const SizedBox(height: AmiSpacing.m),
            TextField(
              controller: codeCtrl,
              keyboardType: TextInputType.number,
              style: AmiTypography.body,
              decoration: InputDecoration(
                hintText: l.signInCodeHint,
                hintStyle: const TextStyle(color: AmiColors.textLow),
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: AmiSpacing.s),
            SizedBox(
              height: 44,
              child: FilledButton(
                onPressed: loading ? null : onVerifyCode,
                child: Text(l.signInVerify),
              ),
            ),
            if (debugCode != null) ...[
              const SizedBox(height: AmiSpacing.s),
              Text(
                l.signInDevCode(debugCode!),
                style: AmiTypography.caption.copyWith(color: AmiColors.hexAmber),
              ),
            ],
          ],
        ],
      ),
    );
  }
}

class _LegalFootnote extends StatelessWidget {
  const _LegalFootnote();
  @override
  Widget build(BuildContext context) {
    return Text(
      AppLocalizations.of(context).signInLegalFootnote,
      style: AmiTypography.caption.copyWith(color: AmiColors.textLow),
    );
  }
}
