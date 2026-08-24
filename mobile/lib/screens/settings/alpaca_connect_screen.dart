/// AlpacaConnectScreen — link an Alpaca paper trading account.
///
/// CR202: linking is now entirely local. The key ID and secret are validated
/// against Alpaca directly from this device and stored in the Keychain /
/// Keystore; they are never sent to the AMI backend, which no longer has
/// anywhere to put them. Only the resulting positions are ever uploaded.
///
/// Two modes:
///   1. API Key — paste key ID + secret. Validated against
///      `GET /v2/account` before being stored, so a bad pair fails here rather
///      than silently at the next Room convene.
///   2. OAuth — embedded WebView. Still requires the ALPACA_CLIENT_ID build
///      define and Alpaca app approval, so it stays greyed-out. Alpaca's token
///      endpoint requires client_secret and documents no PKCE, so that one
///      exchange cannot run on-device; the backend performs it and hands the
///      token straight back without storing it.
///
/// Returns `true` to the caller if linking succeeded, `false` otherwise.
library;

import 'dart:async';

import 'package:ami_trade/services/alpaca/alpaca_client.dart';
import 'package:ami_trade/services/alpaca/alpaca_credential_store.dart';
import 'package:ami_trade/state/alpaca_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:convert';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:webview_flutter/webview_flutter.dart';

const _clientId = String.fromEnvironment('ALPACA_CLIENT_ID', defaultValue: '');
const _redirectUri = 'amitrade://alpaca/callback';

/// DEF373 (security review M12) — hosts this WebView may navigate to.
///
/// The delegate used to return `NavigationDecision.navigate` for ANY url, and
/// JavaScript is unrestricted in here. A redirect off Alpaca therefore
/// rendered attacker-controlled content inside a WebView the user has been
/// told is their broker's login — a credential-phishing surface we built and
/// pointed at ourselves.
///
/// Allowlisted by registrable domain rather than exact host, because Alpaca
/// moves between `app.` and `api.` during the flow. Anything else is blocked
/// and NAMED: if Alpaca ever routes through a third-party identity provider,
/// this fails visibly with the host printed rather than mysteriously, which is
/// the tradeable difference between a strict allowlist and a broken login.
const allowedAuthHosts = {'alpaca.markets'};

bool isAllowedAuthHost(Uri uri) {
  if (uri.scheme != 'https') return false;
  final host = uri.host.toLowerCase();
  return allowedAuthHosts.any((d) => host == d || host.endsWith('.$d'));
}

/// DEF373 — a per-attempt CSRF nonce for the OAuth `state` parameter.
///
/// Without it, `_handleNavigation` exchanged ANY `code` that arrived on the
/// callback url. An attacker who can get the victim's app to open a crafted
/// callback links the victim's AMI install to the ATTACKER's Alpaca account —
/// the victim then trades, and the attacker sees it. `state` is the standard
/// answer: mint a nonce, send it, and refuse a callback that does not echo it.
///
/// `Random.secure()` explicitly — the default `Random()` is seeded
/// predictably and a guessable nonce is not a nonce.
String newOauthState() {
  final r = Random.secure();
  final bytes = List<int>.generate(32, (_) => r.nextInt(256));
  return base64Url.encode(bytes).replaceAll('=', '');
}

String buildAuthUrl(String state) => Uri(
      scheme: 'https',
      host: 'app.alpaca.markets',
      path: '/oauth/authorize',
      queryParameters: {
        'response_type': 'code',
        'client_id': _clientId,
        'redirect_uri': _redirectUri,
        'scope': 'account:write trading',
        'state': state,
      },
    ).toString();

class AlpacaConnectScreen extends ConsumerStatefulWidget {
  const AlpacaConnectScreen({super.key});

  @override
  ConsumerState<AlpacaConnectScreen> createState() => _AlpacaConnectScreenState();
}

class _AlpacaConnectScreenState extends ConsumerState<AlpacaConnectScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(
        backgroundColor: AmiColors.slate900,
        foregroundColor: AmiColors.textHigh,
        title: const Text(
          'Connect Alpaca Paper',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: AmiColors.textHigh),
        ),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(false),
        ),
        bottom: TabBar(
          controller: _tabController,
          labelColor: AmiColors.hexCyan,
          unselectedLabelColor: AmiColors.slate500,
          indicatorColor: AmiColors.hexCyan,
          tabs: const [
            Tab(text: 'API KEY'),
            Tab(text: 'OAUTH'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _ApiKeyTab(),
          _OAuthTab(),
        ],
      ),
    );
  }
}

// ── API Key tab ───────────────────────────────────────────────────────────

class _ApiKeyTab extends ConsumerStatefulWidget {
  const _ApiKeyTab();

  @override
  ConsumerState<_ApiKeyTab> createState() => _ApiKeyTabState();
}

class _ApiKeyTabState extends ConsumerState<_ApiKeyTab> {
  final _formKey = GlobalKey<FormState>();
  final _keyCtrl = TextEditingController();
  final _secretCtrl = TextEditingController();
  bool _secretVisible = false;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _keyCtrl.dispose();
    _secretCtrl.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    final keyId = _keyCtrl.text.trim();
    final secret = _secretCtrl.text.trim();
    try {
      // Prove the pair works BEFORE storing it. Storing an unverified
      // credential just defers the failure to the next Room convene, where
      // it is far less obvious what went wrong.
      await ref.read(alpacaClientProvider).validate(keyId, secret);
      await AlpacaCredentialStore.save(keyId, secret);
      ref.read(alpacaSnapshotCacheProvider).invalidate();
      // CR203: report the fact of the link, not the key. Deliberately not
      // awaited into the failure path — the credential is already stored and
      // working; a reporting hiccup must not tell the user linking failed.
      unawaited(_reportLinked(ref));
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on AlpacaException catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.isAuthFailure
            ? 'Alpaca rejected that key — check the ID and secret, and that '
                'they are Paper Trading keys.'
            : 'Could not reach Alpaca. Check your connection and try again.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Connection failed — check your key and secret.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AmiSpacing.l),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: AmiSpacing.m),
            const Text(
              'Get your Paper Trading API key from app.alpaca.markets → Paper Trading → API Keys.',
              style: TextStyle(color: AmiColors.textMed, fontSize: 13, height: 1.5),
            ),
            const SizedBox(height: AmiSpacing.m),
            // CR202: say both of these plainly. The first is the reason the
            // second is true, and the second otherwise reads as a bug the
            // first time they change phones.
            const Text(
              'Your key is stored only on this device and is never sent to AMI. '
              'That also means it will not follow you to a new phone or survive '
              'reinstalling the app — you will paste it again.',
              style: TextStyle(color: AmiColors.slate500, fontSize: 12, height: 1.5),
            ),
            const SizedBox(height: AmiSpacing.xl),
            _label('API KEY ID'),
            const SizedBox(height: AmiSpacing.xs),
            TextFormField(
              controller: _keyCtrl,
              style: const TextStyle(color: AmiColors.textHigh, fontFamily: 'monospace'),
              decoration: _inputDecoration('PKXXXXXXXXXXXXXXXXXXXXXXXX'),
              autocorrect: false,
              enableSuggestions: false,
              inputFormatters: [FilteringTextInputFormatter.deny(RegExp(r'\s'))],
              validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
            ),
            const SizedBox(height: AmiSpacing.l),
            _label('SECRET KEY'),
            const SizedBox(height: AmiSpacing.xs),
            TextFormField(
              controller: _secretCtrl,
              style: const TextStyle(color: AmiColors.textHigh, fontFamily: 'monospace'),
              decoration: _inputDecoration('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx').copyWith(
                suffixIcon: IconButton(
                  icon: Icon(
                    _secretVisible ? Icons.visibility_off : Icons.visibility,
                    color: AmiColors.slate500,
                    size: 20,
                  ),
                  onPressed: () => setState(() => _secretVisible = !_secretVisible),
                ),
              ),
              obscureText: !_secretVisible,
              autocorrect: false,
              enableSuggestions: false,
              inputFormatters: [FilteringTextInputFormatter.deny(RegExp(r'\s'))],
              validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
            ),
            const SizedBox(height: AmiSpacing.xl),
            SizedBox(
              height: 48,
              child: ElevatedButton(
                onPressed: _loading ? null : _connect,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AmiColors.hexCyan,
                  foregroundColor: AmiColors.slate900,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  disabledBackgroundColor: AmiColors.slate700,
                ),
                child: _loading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AmiColors.slate900,
                        ),
                      )
                    : const Text(
                        'CONNECT',
                        style: TextStyle(fontWeight: FontWeight.w700, letterSpacing: 1.2),
                      ),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: AmiSpacing.m),
              Container(
                padding: const EdgeInsets.all(AmiSpacing.m),
                decoration: BoxDecoration(
                  color: AmiColors.slate800,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AmiColors.hexAmber.withValues(alpha: 0.4)),
                ),
                child: Text(
                  _error!,
                  style: const TextStyle(color: AmiColors.hexAmber, fontSize: 13),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _label(String text) => Text(
        text,
        style: const TextStyle(
          color: AmiColors.textMed,
          fontSize: 11,
          fontWeight: FontWeight.w600,
          letterSpacing: 1.1,
        ),
      );

  InputDecoration _inputDecoration(String hint) => InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: AmiColors.slate600, fontFamily: 'monospace'),
        filled: true,
        fillColor: AmiColors.slate800,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AmiColors.hexCyan, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AmiColors.hexAmber),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AmiColors.hexAmber, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      );
}

// ── OAuth tab ─────────────────────────────────────────────────────────────

class _OAuthTab extends ConsumerStatefulWidget {
  const _OAuthTab();

  @override
  ConsumerState<_OAuthTab> createState() => _OAuthTabState();
}

class _OAuthTabState extends ConsumerState<_OAuthTab> {
  late final WebViewController _controller;

  /// DEF373 — the nonce for the in-flight attempt; null when none is open.
  String? _oauthState;
  bool _loading = true;
  bool _linking = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (_clientId.isNotEmpty) {
      _controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setBackgroundColor(AmiColors.slate900)
        ..setNavigationDelegate(
          NavigationDelegate(
            onPageStarted: (_) => setState(() => _loading = true),
            onPageFinished: (_) => setState(() => _loading = false),
            onWebResourceError: (err) => setState(() {
              _loading = false;
              _error = 'Page failed to load (${err.errorCode})';
            }),
            onNavigationRequest: (req) => _handleNavigation(req),
          ),
        )
        ..loadRequest(Uri.parse(buildAuthUrl(_oauthState = newOauthState())));
    }
  }

  NavigationDecision _handleNavigation(NavigationRequest req) {
    final uri = Uri.tryParse(req.url);
    // DEF373 — an unparseable url used to be ALLOWED. Default to refusing
    // what we cannot inspect; a navigation we cannot reason about is exactly
    // the one to stop.
    if (uri == null) return NavigationDecision.prevent;

    if (uri.scheme == 'amitrade' && uri.host == 'alpaca' && uri.path == '/callback') {
      final code = uri.queryParameters['code'];
      final error = uri.queryParameters['error'];
      final returned = uri.queryParameters['state'];

      // DEF373 — the CSRF check. A callback that does not echo the nonce we
      // minted for THIS attempt is not the result of this attempt, whatever
      // else it carries. Compared before the code is read, so a forged code
      // is never handled at all.
      if (returned == null || returned != _oauthState || _oauthState == null) {
        setState(() => _error =
            'That sign-in response did not match this attempt, so it was '
            'ignored. Start the connection again.');
        return NavigationDecision.prevent;
      }
      // One nonce, one use — a replayed callback must not work twice.
      _oauthState = null;

      if (code != null) {
        _exchangeCode(code);
      } else {
        setState(() => _error = error ?? 'Access denied');
      }
      return NavigationDecision.prevent;
    }

    if (isAllowedAuthHost(uri)) return NavigationDecision.navigate;

    // Named, not silent — see `allowedAuthHosts`.
    setState(() => _error =
        'Sign-in tried to leave Alpaca (${uri.host}), so it was stopped.');
    return NavigationDecision.prevent;
  }

  Future<void> _exchangeCode(String code) async {
    setState(() => _linking = true);
    try {
      // CR202: the backend performs the exchange (Alpaca requires
      // client_secret) and returns the tokens without storing them; the
      // credential is persisted here, on the device, like the API key pair.
      final api = ref.read(apiClientProvider);
      final tokens = await api.alpacaExchangeOAuthCode(code);
      await AlpacaCredentialStore.save(
        tokens.accessToken,
        tokens.refreshToken,
        mode: AlpacaAuthMode.oauth,
      );
      ref.read(alpacaSnapshotCacheProvider).invalidate();
      unawaited(_reportLinked(ref));
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _linking = false;
        _error = 'Link failed — try again';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_clientId.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(AmiSpacing.l),
          child: Text(
            'OAuth not available yet.\n\nUse the API Key tab to connect for now.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AmiColors.slate500, height: 1.6),
          ),
        ),
      );
    }

    return Stack(
      children: [
        WebViewWidget(controller: _controller),
        if (_loading || _linking)
          const Center(child: CircularProgressIndicator(color: AmiColors.hexCyan)),
        if (_error != null)
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: Container(
              color: AmiColors.slate800,
              padding: const EdgeInsets.all(AmiSpacing.m),
              child: Text(
                _error!,
                style: const TextStyle(color: AmiColors.textHigh),
                textAlign: TextAlign.center,
              ),
            ),
          ),
      ],
    );
  }
}


/// CR203 — best-effort link-state report. Swallows failure by design: the
/// credential lives on this device and the link is already complete, so a
/// failed report costs an analytics row, not the feature. The next successful
/// report (or unlink) corrects it.
Future<void> _reportLinked(WidgetRef ref) async {
  try {
    await ref.read(apiClientProvider).alpacaReportLinkState(true);
  } catch (_) {}
}
