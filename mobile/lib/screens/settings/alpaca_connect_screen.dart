/// AlpacaConnectScreen — embedded WebView for Alpaca OAuth paper trading link.
///
/// Loads Alpaca's OAuth authorization page in a WebView. When Alpaca redirects
/// to `amitrade://alpaca/callback?code=<code>`, the NavigationDelegate
/// intercepts it before the OS tries to resolve the URI scheme, extracts the
/// code, and POSTs it to our backend to exchange for tokens.
///
/// Returns `true` to the caller if linking succeeded, `false` otherwise.
library;

import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:webview_flutter/webview_flutter.dart';

// Public `client_id` — stamped at build time via --dart-define.
// Saiful registers the OAuth app at https://app.alpaca.markets/oauth-clients
// and passes the client_id in scripts/install_iphone.sh + build_playstore.sh.
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

class _AlpacaConnectScreenState extends ConsumerState<AlpacaConnectScreen> {
  late final WebViewController _controller;
  bool _loading = true;
  bool _linking = false;
  String? _error;

  @override
  void initState() {
    super.initState();
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

  NavigationDecision _handleNavigation(NavigationRequest req) {
    final uri = Uri.tryParse(req.url);
    if (uri == null) return NavigationDecision.navigate;

    // Intercept our custom scheme before the OS tries to resolve it.
    if (uri.scheme == 'amitrade' && uri.host == 'alpaca') {
      final path = uri.path; // '/callback'
      if (path == '/callback') {
        final code = uri.queryParameters['code'];
        final error = uri.queryParameters['error'];
        if (code != null) {
          _exchangeCode(code);
        } else {
          setState(() => _error = error ?? 'Access denied');
        }
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
    return Scaffold(
      backgroundColor: AmiColors.slate900,
      appBar: AppBar(
        backgroundColor: AmiColors.slate900,
        foregroundColor: AmiColors.textHigh,
        title: const Text(
          'Connect Alpaca Paper',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AmiColors.textHigh,
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(false),
        ),
      ),
      body: Stack(
        children: [
          if (_clientId.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(AmiSpacing.l),
                child: Text(
                  'Alpaca client ID not configured.\n'
                  'Build with --dart-define=ALPACA_CLIENT_ID=<your_id>',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AmiColors.slate500),
                ),
              ),
            )
          else
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
      ),
    );
  }
}
