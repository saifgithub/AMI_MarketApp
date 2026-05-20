# Flutter Implementation Patterns

State management, project structure, key widget patterns.

## State management — Riverpod

| Why Riverpod | |
|---|---|
| Type-safe | Compile-time errors for typos |
| Test-friendly | Easy provider override in tests |
| No boilerplate | Compared to Bloc / Redux |
| Async-first | Natural fit for API calls |
| Granular rebuilds | Only widgets watching a provider rebuild |

Alternative considered: Bloc. Rejected — more boilerplate, less fluid for our use case.

## Provider categories

### Data providers

```dart
// API client (singleton)
final apiClientProvider = Provider<ApiClient>((ref) {
  final supabase = ref.watch(supabaseClientProvider);
  return ApiClient(baseUrl: kApiBaseUrl, supabase: supabase);
});

// User
final currentUserProvider = StreamProvider<User?>((ref) {
  return ref.watch(supabaseClientProvider).auth.onAuthStateChange
    .map((event) => event.session?.user)
    .asyncMap((u) async => u == null ? null : await ref.read(apiClientProvider).getCurrentUser());
});

// Mandate
final mandateProvider = FutureProvider<Mandate?>((ref) async {
  final user = ref.watch(currentUserProvider).valueOrNull;
  if (user == null) return null;
  return await ref.read(apiClientProvider).getMandate();
});
```

### Agents

```dart
final twelveAgentsProvider = FutureProvider<List<Agent>>((ref) async {
  return await ref.read(apiClientProvider).listAgents();
});

final agentDetailProvider = FutureProvider.family<AgentDetail, String>((ref, agentId) async {
  return await ref.read(apiClientProvider).getAgentDetail(agentId);
});

// 1-on-1 chat state
final oneOnOneStateProvider = StateNotifierProvider.family
  .autoDispose<OneOnOneNotifier, OneOnOneState, String>((ref, agentId) {
  return OneOnOneNotifier(ref, agentId);
});
```

### Convene the Room — streaming

```dart
// Convene live updates flow through Supabase Realtime
final roomRunStreamProvider = StreamProvider.family<RoomRunEvent, String>((ref, roomRunId) {
  final supabase = ref.watch(supabaseClientProvider);
  final channel = supabase.channel('room_run:$roomRunId');
  
  return channel
    .onBroadcast(event: 'agent_token', callback: (payload) => /* ... */)
    .stream();
});
```

## Project structure (Flutter side)

```
mobile/lib/
├── main.dart                    ← app entry; sets up Riverpod, Supabase, theming
├── app.dart                     ← MaterialApp + router
├── theme/
│   ├── ami_theme.dart           ← AMI design tokens (colors, type, motion)
│   ├── hex_clipper.dart         ← Hex clip-path implementations
│   └── theme_extensions.dart    ← Helper extensions on Theme
├── i18n/
│   ├── generated/               ← Generated from content/i18n/
│   ├── localizations.dart
│   └── locale_provider.dart
├── routes/
│   ├── app_router.dart          ← go_router config
│   └── routes.dart              ← Route constants
├── screens/
│   ├── splash/
│   ├── onboarding/
│   │   ├── concierge_chat_screen.dart
│   │   ├── account_claim_screen.dart
│   │   └── widgets/
│   ├── floor/
│   │   ├── floor_screen.dart
│   │   └── widgets/
│   │       ├── honeycomb.dart            ← The signature widget
│   │       ├── mandate_health_strip.dart
│   │       └── briefing_card.dart
│   ├── sim/
│   ├── convene/
│   │   ├── convene_screen.dart
│   │   ├── matrix_console.dart           ← streaming agent logs
│   │   └── verdict_card.dart
│   ├── academy/
│   ├── journal/
│   ├── agent_profile/
│   ├── brief/
│   ├── concierge/
│   └── settings/
├── widgets/
│   ├── hex/
│   │   ├── hex_button.dart
│   │   ├── hex_avatar.dart               ← Used for every agent representation
│   │   ├── hex_chip.dart
│   │   └── glass_panel.dart
│   ├── chat/
│   │   ├── chat_bubble.dart              ← Role-colour coded
│   │   └── streaming_text.dart           ← Typewriter effect
│   └── common/
├── services/                              ← Facade interfaces + implementations
│   ├── platform/
│   │   ├── push_service.dart
│   │   ├── auth_service.dart
│   │   ├── billing_service.dart
│   │   └── ads_service.dart
│   ├── api/
│   │   └── api_client.dart
│   ├── audio/
│   │   └── tts_player.dart
│   └── analytics/
│       └── posthog_service.dart
├── state/                                 ← Riverpod providers
│   ├── auth_providers.dart
│   ├── mandate_providers.dart
│   ├── agent_providers.dart
│   ├── credit_providers.dart
│   ├── concierge_providers.dart
│   └── ...
└── models/                                ← Data models (mirror backend Pydantic)
    ├── user.dart
    ├── mandate.dart
    ├── agent.dart
    ├── room_run.dart
    └── ...
```

## Key widgets

### Honeycomb (the Floor home)

```dart
class Honeycomb extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final agents = ref.watch(twelveAgentsProvider).valueOrNull ?? [];
    
    return AspectRatio(
      aspectRatio: 1.0,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Concierge centre
          Positioned(
            top: '50%',
            left: '50%',
            child: ConciergeHex(),
          ),
          // 12 agents — positioned at calculated coordinates
          ..._positionAgents(agents).map((entry) => Positioned(
            top: entry.y,
            left: entry.x,
            child: HexAvatar(
              agentId: entry.agent.id,
              color: entry.agent.color,
              active: entry.agent.activated,
              status: entry.agent.status,
              onTap: () => context.go('/agent/${entry.agent.id}'),
              onLongPress: () => _openQuickOneOnOne(context, entry.agent.id),
            ),
          )),
        ],
      ),
    );
  }
}
```

### Matrix Console (Convene streaming)

```dart
class MatrixConsole extends ConsumerWidget {
  final String roomRunId;
  
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final stream = ref.watch(roomRunStreamProvider(roomRunId));
    
    return stream.when(
      data: (events) => ListView(
        children: events.map((e) => MatrixLine(
          prefix: e.agentLabel.toUpperCase(),
          prefixColor: e.agentColor,
          content: e.content,
        )).toList(),
      ),
      loading: () => StreamingLoader(),
      error: (e, s) => ErrorBanner(message: e.toString()),
    );
  }
}
```

### Chat bubble (1-on-1, Concierge, Coach)

```dart
class ChatBubble extends StatelessWidget {
  final String content;
  final ChatRole role;   // user | agent
  final String? agentId;
  final Color? agentColor;
  final bool streaming;
  
  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      accentColor: role == ChatRole.agent ? agentColor : AmiColors.hexBlue,
      padding: EdgeInsets.all(AmiSpacing.m),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (role == ChatRole.agent && agentId != null)
            Text(
              agentId!.toUpperCase(),
              style: AmiTypography.labelMono.copyWith(color: agentColor),
            ),
          SizedBox(height: AmiSpacing.xs),
          streaming
            ? StreamingText(content)
            : Text(content, style: AmiTypography.body),
        ],
      ),
    );
  }
}
```

## Routing — go_router

```dart
final router = GoRouter(
  initialLocation: '/splash',
  redirect: (context, state) {
    final user = currentUser();
    if (state.location.startsWith('/onboarding')) return null;
    if (user == null) return '/splash';
    return null;
  },
  routes: [
    GoRoute(path: '/splash', builder: (c, s) => SplashScreen()),
    GoRoute(path: '/onboarding', builder: (c, s) => OnboardingScreen()),
    ShellRoute(
      builder: (c, s, child) => TabScaffold(child: child),
      routes: [
        GoRoute(path: '/floor', builder: ...),
        GoRoute(path: '/sim', builder: ...),
        GoRoute(path: '/convene', builder: ...),
        GoRoute(path: '/academy', builder: ...),
        GoRoute(path: '/journal', builder: ...),
      ],
    ),
    GoRoute(path: '/agent/:id', builder: ...),
    GoRoute(path: '/agent/:id/brief', builder: ...),
    GoRoute(path: '/convene/:id', builder: ...),
    // ... etc.
  ],
);
```

## i18n integration

```dart
// Use Flutter's intl package + arb files generated from content/i18n/
final ar = AppLocalizations.of(context)!;
Text(ar.floor_greeting(user.displayName));
```

ARB files are *generated* from our `content/i18n/{locale}/strings.json` at build time via a script (`scripts/gen_i18n.dart`). Source of truth is the JSON in `content/`; ARBs are a build artifact.

## Performance principles

- **Const constructors** wherever possible
- **`AutoDispose` providers** for screen-scoped state — prevents memory leaks
- **`select`** for reading specific fields of large providers (avoids unnecessary rebuilds)
- **Image caching** via `cached_network_image`
- **List virtualisation** via `ListView.builder` for any list >20 items
- **`compute()`** for heavy parsing tasks (JSON deserialization of large payloads)

## Testing

| Test type | Tool | What we test |
|---|---|---|
| Unit | `flutter_test` | Mandate-overlay-generator logic, hex clip-path math, route helpers |
| Widget | `flutter_test` | Hex avatar rendering, chat bubble layout, honeycomb positioning |
| Integration | `integration_test` | Full onboarding flow, claim flow, Convene flow with mocked LLM |
| Golden | `flutter_test` snapshots | Per-locale snapshots of key screens (EN, AR-RTL, MS) |

CI runs all of these. Saiful manually tests on real devices.

## Cross-references

- AMI hex implementation: [`docs/05_design/ami_hex_in_flutter.md`](../05_design/ami_hex_in_flutter.md)
- Information architecture: [`docs/05_design/information_architecture.md`](../05_design/information_architecture.md)
- Platform facade: [`platform_facade.md`](platform_facade.md)
- API client this consumes: [`api_design.md`](api_design.md)
