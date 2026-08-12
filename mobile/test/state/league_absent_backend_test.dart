/// CR109 slice 7, first half — the client survives a backend with no league.
///
/// Amendment A replaces the reputation league with the P&L game. The two
/// halves of that removal **cannot ship together**: the backend goes out by
/// rsync the same day, the client through store review days later. So for a
/// window measured in days, every installed build talks to a backend that no
/// longer serves `/v1/league/*`.
///
/// The line these tests hold is the CR040 one: a **planned absence** and a
/// **broken backend** must not look the same. A 404 becomes "nothing to
/// show"; a 500 stays an error.
library;

import 'package:ami_trade/models/league.dart';
import 'package:ami_trade/services/api/api_client.dart';
import 'package:ami_trade/state/league_providers.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _LeagueApi extends ApiClient {
  _LeagueApi({required this.error}) : super(baseUrl: 'test://localhost');

  final Object? error;

  @override
  Future<LeagueMe> leagueMe() async {
    if (error != null) throw error!;
    return const LeagueMe(
      handle: 'you',
      tier: 'floor',
      reputation: 10,
      pointsThisWeek: 4,
      rank: 2,
      showDisplayName: false,
      streak: StreakInfo(current: 3, longest: 5),
    );
  }

  @override
  Future<LeagueStandings?> leagueStandings() async {
    if (error != null) throw error!;
    return null;
  }
}

DioException _status(int code) => DioException(
      requestOptions: RequestOptions(path: '/v1/league/me'),
      response: Response(
        requestOptions: RequestOptions(path: '/v1/league/me'),
        statusCode: code,
      ),
    );

ProviderContainer _container(Object? error) {
  final container = ProviderContainer(overrides: [
    apiClientProvider.overrideWithValue(_LeagueApi(error: error)),
  ]);
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('a removed league reads as nothing to show, not as an error', () async {
    final container = _container(_status(404));

    final me = await container.read(leagueMeProvider.future);
    final standings = await container.read(standingsProvider.future);

    expect(me, isNull);
    expect(standings, isNull);
  });

  test('a broken backend still surfaces as an error', () async {
    final container = _container(_status(500));

    await expectLater(
      container.read(leagueMeProvider.future),
      throwsA(isA<DioException>()),
      reason: 'a 500 is not "the league was removed" — swallowing it would '
          'hide a real outage behind the same silence',
    );
  });

  test('a dropped connection still surfaces as an error', () async {
    final container = _container(DioException(
      requestOptions: RequestOptions(path: '/v1/league/me'),
      type: DioExceptionType.connectionError,
    ));

    await expectLater(
      container.read(leagueMeProvider.future),
      throwsA(isA<DioException>()),
    );
  });

  test('a league that is still there answers normally', () async {
    final container = _container(null);

    final me = await container.read(leagueMeProvider.future);

    expect(me, isNotNull);
    expect(me!.streak.current, 3);
  });
}
