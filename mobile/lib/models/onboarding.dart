/// Onboarding-flow models — mirror the backend Pydantic schemas at
/// backend/app/schemas/onboarding.py.
library;

enum ChatAuthorRemote { concierge, user }

class OnboardingMessage {
  const OnboardingMessage({
    required this.author,
    required this.content,
    required this.step,
    this.chips = const [],
  });

  final ChatAuthorRemote author;
  final String content;
  final String step;
  final List<String> chips;

  factory OnboardingMessage.fromJson(Map<String, dynamic> j) {
    return OnboardingMessage(
      author: (j['author'] as String) == 'user'
          ? ChatAuthorRemote.user
          : ChatAuthorRemote.concierge,
      content: j['content'] as String,
      step: j['step'] as String,
      chips: (j['chips'] as List?)?.cast<String>() ?? const [],
    );
  }
}

class StartOnboardingResponse {
  const StartOnboardingResponse({
    required this.sessionId,
    required this.welcomeMessage,
    required this.firstQuestion,
  });

  final String sessionId;
  final OnboardingMessage welcomeMessage;
  final OnboardingMessage firstQuestion;

  factory StartOnboardingResponse.fromJson(Map<String, dynamic> j) {
    return StartOnboardingResponse(
      sessionId: j['session_id'] as String,
      welcomeMessage:
          OnboardingMessage.fromJson(j['welcome_message'] as Map<String, dynamic>),
      firstQuestion:
          OnboardingMessage.fromJson(j['first_question'] as Map<String, dynamic>),
    );
  }
}

class AnswerResponse {
  const AnswerResponse({
    required this.nextStep,
    required this.conciergeReply,
    this.readbackSummary,
  });

  final String nextStep;
  final OnboardingMessage conciergeReply;
  final Map<String, dynamic>? readbackSummary;

  factory AnswerResponse.fromJson(Map<String, dynamic> j) {
    return AnswerResponse(
      nextStep: j['next_step'] as String,
      conciergeReply:
          OnboardingMessage.fromJson(j['concierge_reply'] as Map<String, dynamic>),
      readbackSummary: j['readback_summary'] as Map<String, dynamic>?,
    );
  }
}

class ReadbackConfirmResponse {
  const ReadbackConfirmResponse({
    required this.completed,
    required this.finalStep,
    required this.mandatePreview,
    required this.followUpMessage,
  });

  final bool completed;
  final String finalStep;
  final Map<String, dynamic> mandatePreview;
  final OnboardingMessage followUpMessage;

  factory ReadbackConfirmResponse.fromJson(Map<String, dynamic> j) {
    return ReadbackConfirmResponse(
      completed: j['completed'] as bool,
      finalStep: j['final_step'] as String,
      mandatePreview: j['mandate_preview'] as Map<String, dynamic>? ?? const {},
      followUpMessage:
          OnboardingMessage.fromJson(j['follow_up_message'] as Map<String, dynamic>),
    );
  }
}
