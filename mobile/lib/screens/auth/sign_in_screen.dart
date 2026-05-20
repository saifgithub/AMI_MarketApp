/// Sign-in screen — opens from Settings → Account.
///
/// Anonymous users see two claim paths:
///   1. Sign in with Apple — native Sign in with Apple via the
///      `sign_in_with_apple` package; the returned identity_token is
///      verified against Apple's JWKS by the backend (Phase 3, AT:R29).
///   2. Continue with email — sends a 6-digit code; in dev the code is
///      returned from the backend so the alpha tester can paste it without
///      a real email being sent.
///
/// Already-claimed users see a "Signed in as you@example.com" line + the
/// option to stay.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/state/auth_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

class SignInScreen extends ConsumerStatefulWidget {
  const SignInScreen({super.key});

  @override
  ConsumerState<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends ConsumerState<SignInScreen> {
  final _emailCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  bool _codeRequested = false;

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
    final ok = await ref
        .read(authNotifierProvider.notifier)
        .verifyMagicLink(email: email, code: code);
    if (!mounted) return;
    if (ok) {
      Navigator.of(context).pop();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).signInCodeFailed)),
      );
    }
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
        SnackBar(content: Text('Apple sign-in failed: $e')),
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

    final ok = await ref.read(authNotifierProvider.notifier).signInWithApple(
          identityToken,
          fullName: fullName.isEmpty ? null : fullName,
        );
    if (!mounted) return;
    if (ok) {
      Navigator.of(context).pop();
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
            if (user != null && !user.isAnonymous) ...[
              _SignedInCard(user: user),
              const SizedBox(height: AmiSpacing.l),
            ] else ...[
              Text(
                l.signInIntro,
                style: AmiTypography.body,
              ),
              const SizedBox(height: AmiSpacing.l),
            ],
            _AppleButton(
              onPressed:
                  auth.loading ? null : _signInWithApple,
            ),
            const SizedBox(height: AmiSpacing.l),
            _EmailClaimCard(
              emailCtrl: _emailCtrl,
              codeCtrl: _codeCtrl,
              codeRequested: _codeRequested,
              loading: auth.loading,
              onRequestCode: _requestCode,
              onVerifyCode: _verifyCode,
              debugCode: auth.lastDebugCode,
            ),
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
