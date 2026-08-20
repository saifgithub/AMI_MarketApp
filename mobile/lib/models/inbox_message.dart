/// CR102 — a row in the tester inbox.
///
/// Mirrors `app/schemas/messages.py::InboxMessageOut`. `direction` is the
/// server's point of view: `'out'` is a broadcast from AMI HQ to this user,
/// `'in'` is this user's own reply. Both arrive from `GET /v1/messages` in
/// one newest-first list.
///
/// [direction] and [priority] stay plain strings rather than enums on
/// purpose (DEF210 class): a wire literal this client has never heard of
/// must render as a plain row, not throw — the backend ships by rsync days
/// ahead of the store build.
library;

class InboxMessage {
  const InboxMessage({
    required this.id,
    required this.direction,
    required this.body,
    required this.createdAt,
    this.broadcastId,
    this.title,
    this.priority,
    this.replyToId,
    this.readAt,
    this.toastedAt,
  });

  final String id;
  final String? broadcastId;

  /// `'out'` (AMI HQ → user) or `'in'` (user reply). Unknown values render
  /// as a plain row.
  final String direction;

  /// Null on replies; broadcasts carry the admin-authored title.
  final String? title;
  final String body;

  /// `'normal'` | `'high'` on `'out'` rows, null on replies. Unknown values
  /// get the normal accent.
  final String? priority;
  final String? replyToId;
  final DateTime createdAt;
  final DateTime? readAt;
  final DateTime? toastedAt;

  /// A broadcast this user hasn't opened. Replies are never "unread".
  bool get isUnread => direction == 'out' && readAt == null;

  bool get isHighPriority => priority == 'high';

  factory InboxMessage.fromJson(Map<String, dynamic> j) {
    return InboxMessage(
      id: j['id'] as String,
      broadcastId: j['broadcast_id'] as String?,
      direction: j['direction'] as String,
      title: j['title'] as String?,
      body: j['body'] as String,
      priority: j['priority'] as String?,
      replyToId: j['reply_to_id'] as String?,
      createdAt: _parse(j['created_at'] as String?) ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
      readAt: _parse(j['read_at'] as String?),
      toastedAt: _parse(j['toasted_at'] as String?),
    );
  }

  static DateTime? _parse(String? s) =>
      s == null ? null : DateTime.tryParse(s);
}

/// Mirrors `app/schemas/messages.py::ReplyOut` — the row the server wrote
/// for `POST /v1/messages/{id}/reply`.
class InboxReply {
  const InboxReply({
    required this.id,
    required this.userId,
    required this.body,
    required this.createdAt,
    this.broadcastId,
    this.replyToId,
  });

  final String id;
  final String userId;
  final String? broadcastId;
  final String? replyToId;
  final String body;
  final DateTime createdAt;

  factory InboxReply.fromJson(Map<String, dynamic> j) {
    return InboxReply(
      id: j['id'] as String,
      userId: j['user_id'] as String,
      broadcastId: j['broadcast_id'] as String?,
      replyToId: j['reply_to_id'] as String?,
      body: j['body'] as String,
      createdAt: InboxMessage._parse(j['created_at'] as String?) ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
    );
  }
}
