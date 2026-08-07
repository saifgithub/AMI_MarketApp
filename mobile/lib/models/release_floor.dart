/// CR121 — client version-gate model.
///
/// Mirrors `backend/app/schemas/client_release_floor.py::ReleaseFloorResponse`,
/// the shape of both `GET /v1/client/release-floor` and the `detail` object
/// inside a 426's JSON body:
///
///     { "min_build", "recommended_build", "action", "headline", "body",
///       "store_url" }
///
/// `action` is decided server-side ("block" | "nag" | "ok") so a floor raise
/// or retraction changes client behaviour with no app release.
library;

class ReleaseFloorResponse {
  const ReleaseFloorResponse({
    this.minBuild,
    this.recommendedBuild,
    required this.action,
    this.headline,
    this.body,
    this.storeUrl,
  });

  final int? minBuild;
  final int? recommendedBuild;

  /// "block" | "nag" | "ok" — an unrecognised value from a future server
  /// falls back to "ok" via [fromJson] rather than defaulting to a state
  /// this build doesn't know how to render as a block.
  final String action;
  final String? headline;
  final String? body;
  final String? storeUrl;

  bool get isBlock => action == 'block';
  bool get isNag => action == 'nag';

  factory ReleaseFloorResponse.fromJson(Map<String, dynamic> json) {
    return ReleaseFloorResponse(
      minBuild: (json['min_build'] as num?)?.toInt(),
      recommendedBuild: (json['recommended_build'] as num?)?.toInt(),
      action: json['action'] as String? ?? 'ok',
      headline: json['headline'] as String?,
      body: json['body'] as String?,
      storeUrl: json['store_url'] as String?,
    );
  }

  @override
  String toString() =>
      'ReleaseFloorResponse(action: $action, minBuild: $minBuild)';
}
