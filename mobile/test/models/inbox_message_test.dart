/// CR102 — InboxMessage mirrors InboxMessageOut, defensively.
///
/// The DEF210 case is the load-bearing one: the backend ships by rsync days
/// ahead of the store build, so a wire literal this client has never heard
/// of (`direction`, `priority`) must parse into a renderable row, never
/// throw.
library;

import 'package:ami_trade/models/inbox_message.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _broadcastJson({
  String direction = 'out',
  String? priority = 'normal',
  String? readAt,
  String? toastedAt,
}) =>
    {
      'id': 'msg-1',
      'broadcast_id': 'bc-1',
      'direction': direction,
      'title': 'Welcome to the alpha',
      'body': 'First line.\nSecond line.',
      'priority': priority,
      'reply_to_id': null,
      'created_at': '2026-08-18T10:00:00Z',
      'read_at': readAt,
      'toasted_at': toastedAt,
    };

void main() {
  test('a broadcast row parses with every field', () {
    final m = InboxMessage.fromJson(_broadcastJson(priority: 'high'));
    expect(m.id, 'msg-1');
    expect(m.broadcastId, 'bc-1');
    expect(m.direction, 'out');
    expect(m.title, 'Welcome to the alpha');
    expect(m.priority, 'high');
    expect(m.isHighPriority, isTrue);
    expect(m.isUnread, isTrue);
    expect(m.createdAt.isUtc, isTrue);
    expect(m.readAt, isNull);
    expect(m.toastedAt, isNull);
  });

  test('a read broadcast is not unread', () {
    final m = InboxMessage.fromJson(
        _broadcastJson(readAt: '2026-08-18T11:00:00Z'));
    expect(m.isUnread, isFalse);
    expect(m.readAt, isNotNull);
  });

  test('a reply row (direction=in, null title/priority) is never unread', () {
    final m = InboxMessage.fromJson({
      'id': 'msg-2',
      'broadcast_id': 'bc-1',
      'direction': 'in',
      'title': null,
      'body': 'my reply',
      'priority': null,
      'reply_to_id': 'msg-1',
      'created_at': '2026-08-18T12:00:00Z',
      'read_at': null,
      'toasted_at': null,
    });
    expect(m.direction, 'in');
    expect(m.replyToId, 'msg-1');
    expect(m.isUnread, isFalse, reason: 'replies are never "unread"');
    expect(m.isHighPriority, isFalse);
  });

  test('unknown direction and priority parse without throwing (DEF210)', () {
    final m = InboxMessage.fromJson(
        _broadcastJson(direction: 'sideways', priority: 'shouting'));
    expect(m.direction, 'sideways');
    expect(m.isUnread, isFalse, reason: 'unknown direction is not a claim');
    expect(m.isHighPriority, isFalse,
        reason: 'unknown priority gets the normal accent');
  });

  test('an unparseable timestamp degrades to epoch, not a throw', () {
    final j = _broadcastJson()..['created_at'] = 'not-a-date';
    final m = InboxMessage.fromJson(j);
    expect(m.createdAt, DateTime.fromMillisecondsSinceEpoch(0, isUtc: true));
  });

  test('InboxReply parses the ReplyOut shape', () {
    final r = InboxReply.fromJson({
      'id': 'r-1',
      'user_id': 'u-1',
      'broadcast_id': 'bc-1',
      'reply_to_id': 'msg-1',
      'body': 'thanks',
      'created_at': '2026-08-18T12:00:00Z',
    });
    expect(r.id, 'r-1');
    expect(r.userId, 'u-1');
    expect(r.replyToId, 'msg-1');
    expect(r.body, 'thanks');
  });
}
