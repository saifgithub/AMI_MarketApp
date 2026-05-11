/// 1-on-1 chat session + message models.
library;

class OneOnOneSession {
  const OneOnOneSession({required this.id, required this.agentId, required this.locale});

  final String id;
  final String agentId;
  final String locale;

  factory OneOnOneSession.fromJson(Map<String, dynamic> j) {
    return OneOnOneSession(
      id: j['id'] as String,
      agentId: j['agent_id'] as String,
      locale: j['locale'] as String? ?? 'en',
    );
  }
}

class ChatMessage {
  const ChatMessage({required this.role, required this.content, this.isStreaming = false});

  final String role; // 'user' | 'assistant'
  final String content;
  final bool isStreaming;

  ChatMessage copyWith({String? content, bool? isStreaming}) =>
      ChatMessage(role: role, content: content ?? this.content, isStreaming: isStreaming ?? this.isStreaming);

  Map<String, dynamic> toJson() => {'role': role, 'content': content};
}
