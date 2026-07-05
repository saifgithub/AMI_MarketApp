/// AlpacaConnectScreen — link an Alpaca paper trading account.
///
/// Two modes:
///   1. API Key — paste key ID + secret directly. Available immediately,
///      no OAuth app registration needed. Used for testing.
///   2. OAuth — embedded WebView. Requires ALPACA_CLIENT_ID build define
///      (greyed-out until the client is registered). Kept for production use.
///
/// Returns `true` to the caller if linking succeeded, `false` otherwise.
library;

import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:webview_flutter/webview_flutter.dart';

const _clientId = String.fromEnvironment('ALPACA_CLIENT_ID', defaultValue: '');
const _redirectUri = 'amitrade://alpaca/callback';

String _buildAuthUrl() => Uri(
      scheme: 'https',
      host: 'app.alpaca.markets',
      path: '/oauth/authorize',
      queryParameters: {
        'response_type': 'code',
        'client_id': _clientId,
        'redirect_uri': _redirectUri,
        'scope': 'account:write trading',
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
    try {
      final api = ref.read(apiClientProvider);
      await api.alpacaLinkApiKey(_keyCtrl.text.trim(), _secretCtrl.text.trim());
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
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
        ..loadRequest(Uri.parse(_buildAuthUrl()));
    }
  }

  NavigationDecision _handleNavigation(NavigationRequest req) {
    final uri = Uri.tryParse(req.url);
    if (uri == null) return NavigationDecision.navigate;

    if (uri.scheme == 'amitrade' && uri.host == 'alpaca' && uri.path == '/callback') {
      final code = uri.queryParameters['code'];
      final error = uri.queryParameters['error'];
      if (code != null) {
        _exchangeCode(code);
      } else {
        setState(() => _error = error ?? 'Access denied');
      }
      return NavigationDecision.prevent;
    }
    return NavigationDecision.navigate;
  }

  Future<void> _exchangeCode(String code) async {
    setState(() => _linking = true);
    try {
      final api = ref.read(apiClientProvider);
      await api.alpacaLink(code);
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
