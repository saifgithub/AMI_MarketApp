/// CR278 (CR267 WP-36) - what a "Report this response" report is about.
///
/// A response report is an ordinary bug report (`POST /v1/feedback/bug`, the
/// existing path), not a second endpoint. The only thing it adds is a stable
/// `route` string that names the response, so a triager can find the Room and
/// the agent from the report row alone:
///
///     response:<surface>:<run id, or "-" when there is none>:<agent id>[:t<turn>]
///
/// e.g. `response:room:5b0c...:risk_manager`, `response:verdict:5b0c...:portfolio_manager`,
/// `response:concierge:-:concierge:t3`. The recent request trace ids ride along
/// as for every report (`TraceIdStore.recentIds()`), unchanged.
library;

import 'package:flutter/foundation.dart';

/// Where on screen the reported response was.
enum ResponseSurface { room, verdict, concierge, oneOnOne }

@immutable
class ResponseReportTarget {
  const ResponseReportTarget({
    required this.surface,
    required this.agentId,
    required this.agentLabel,
    this.runId,
    this.turn,
  });

  final ResponseSurface surface;

  /// The backend agent id (`risk_manager`, `portfolio_manager`, `concierge`...).
  final String agentId;

  /// The short name shown to the user ("RISK", "CIO"...).
  final String agentLabel;

  /// The Room run id, when the response belongs to a Room.
  final String? runId;

  /// Zero-based message index within a chat, when there is one.
  final int? turn;

  /// The `route` value of the bug report. See the library doc for the shape.
  String get route => [
        'response',
        surface.name,
        runId ?? '-',
        agentId,
        if (turn != null) 't$turn',
      ].join(':');

  @override
  bool operator ==(Object other) =>
      other is ResponseReportTarget && other.route == route;

  @override
  int get hashCode => route.hashCode;
}
