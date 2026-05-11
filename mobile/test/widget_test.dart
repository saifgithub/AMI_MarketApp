import 'package:ami_trade/app.dart';
import 'package:ami_trade/models/onboarding.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// A test-only ApiClient that returns canned responses without making real HTTP calls.
/// Extends [ApiClient] so it inherits the dio field and only overrides the methods we use.
class _FakeApiClient extends ApiClient {
  _FakeApiClient() : super(baseUrl: 'test://localhost');

  @override
  Future<StartOnboardingResponse> startOnboarding({
    required String locale,
    required String timezone,
  }) async {
    return StartOnboardingResponse(
      sessionId: 'fake-session',
      welcomeMessage: const OnboardingMessage(
        author: ChatAuthorRemote.concierge,
        content: 'Welcome (test)',
        step: 'welcome',
        chips: ['ok'],
      ),
      firstQuestion: const OnboardingMessage(
        author: ChatAuthorRemote.concierge,
        content: 'First question (test)',
        step: 'q1_goal',
        chips: ['option a', 'option b'],
      ),
    );
  }

  @override
  Future<AnswerResponse> submitAnswer({
    required String sessionId,
    required String step,
    required String answer,
  }) async {
    return const AnswerResponse(
      nextStep: 'q2_horizon',
      conciergeReply: OnboardingMessage(
        author: ChatAuthorRemote.concierge,
        content: 'Next (test)',
        step: 'q2_horizon',
      ),
    );
  }

  @override
  Future<ReadbackConfirmResponse> confirmReadback({
    required String sessionId,
    required bool confirm,
  }) async {
    return const ReadbackConfirmResponse(
      completed: true,
      finalStep: 'complete',
      mandatePreview: {},
      followUpMessage: OnboardingMessage(
        author: ChatAuthorRemote.concierge,
        content: 'Done (test)',
        step: 'complete',
      ),
    );
  }

  @override
  Future<bool> health() async => true;
}

void main() {
  testWidgets('App renders without throwing', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [apiClientProvider.overrideWithValue(_FakeApiClient())],
        child: const AmiTradeApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.byType(AmiTradeApp), findsOneWidget);
  });
}
