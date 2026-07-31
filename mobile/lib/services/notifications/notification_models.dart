/// Deep-link model for a received push (CR027).
///
/// The backend's `notifications.deep_link` column shape is ambiguous
/// between a flat object (`{"route": "open_holding_detail", "ticker":
/// "AAPL"}`) and a nested one (`{"route": "...", "params": {...}}`) — this
/// parses either defensively so a backend-side choice never silently
/// breaks dispatch on the one path that reads it.
library;

class DeepLink {
  const DeepLink({required this.route, this.params = const {}});

  final String route;
  final Map<String, dynamic> params;

  factory DeepLink.fromJson(Map<String, dynamic> json) {
    final route = json['route'] as String? ?? '';
    final nested = json['params'];
    if (nested is Map) {
      return DeepLink(route: route, params: Map<String, dynamic>.from(nested));
    }
    final flat = Map<String, dynamic>.from(json)
      ..remove('route')
      ..remove('params');
    return DeepLink(route: route, params: flat);
  }
}
