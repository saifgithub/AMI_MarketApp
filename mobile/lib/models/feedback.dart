/// CR043 — the reporter-facing half of a bug report's lifecycle.
///
/// Mirrors `app/schemas/feedback.py::BugResolutionUpdate`. One of these
/// means: a bug this user took the trouble to report has been fixed, and
/// nobody has told them yet.
///
/// [resolutionNote] is written by Saiful when he flips the status and is
/// shown to the reporter verbatim — it is user-facing copy, not an
/// engineering note.
library;

class BugResolutionUpdate {
  const BugResolutionUpdate({
    required this.id,
    required this.title,
    this.resolvedAt,
    this.resolutionNote,
  });

  final String id;
  final String title;
  final DateTime? resolvedAt;
  final String? resolutionNote;

  factory BugResolutionUpdate.fromJson(Map<String, dynamic> j) {
    final resolved = j['resolved_at'] as String?;
    return BugResolutionUpdate(
      id: j['id'] as String,
      title: j['title'] as String,
      resolvedAt: resolved == null ? null : DateTime.tryParse(resolved),
      resolutionNote: j['resolution_note'] as String?,
    );
  }
}
