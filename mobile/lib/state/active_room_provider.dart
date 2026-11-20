/// DEF506 — "is one of my Rooms still running?", asked on launch and resume.
///
/// AMI-DL-4 (real iPhone): the app was reopened while a Room was still running
/// and landed on the Floor with nothing to say so; the user did not know the
/// run was alive. DEF500 made the Room itself replay and say it had rejoined,
/// but the app had no way to *find* the run — the only route back was convening
/// the same ticker again.
///
/// Saiful's ruling (2026-11-20): open on the Floor with a rejoin banner, never
/// auto-jump into the Room. This is the lookup behind that banner. It reuses
/// `GET /v1/room/user/{id}` (newest run first); no backend change.
///
/// **What counts as in flight** mirrors the server's own attach rule
/// (`RoomRunner._find_active_run`): `status == running` and started inside the
/// `room_dedup_running_minutes` window (30). A `running` row older than that is
/// a stranded run the server will no longer attach to, so tapping REJOIN on it
/// would convene a NEW run and charge for it. That is exactly the charge this
/// banner must never cause, so a row outside the window is "not in flight".
///
/// **Failure is quiet in the UI and loud in the log.** A failed lookup shows no
/// banner (the Floor must not break or nag over a flaky network) and says so
/// with a `debugPrint`.
library;

import 'package:ami_trade/models/room.dart';
import 'package:ami_trade/services/device_user.dart';
import 'package:ami_trade/state/onboarding_providers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Server `room_dedup_running_minutes` (backend/app/core/config.py). Past this
/// the server stops attaching a re-convene to the run.
const Duration kRoomAttachWindow = Duration(minutes: 30);

/// The one Room run worth a banner.
@immutable
class ActiveRoomRun {
  const ActiveRoomRun({required this.runId, required this.ticker});

  final String runId;
  final String ticker;

  @override
  bool operator ==(Object other) =>
      other is ActiveRoomRun && other.runId == runId && other.ticker == ticker;

  @override
  int get hashCode => Object.hash(runId, ticker);
}

/// The newest run when (and only when) it is in flight, else null. Only the
/// newest matters: the server permits one Room in flight per user (CR270), so
/// an older row that still says `running` is stranded, not live.
ActiveRoomRun? activeRoomRunFrom(
  List<RoomRunSnapshot> runs, {
  DateTime? now,
}) {
  if (runs.isEmpty) return null;
  final newest = runs.first;
  if (newest.status != 'running') return null;
  final started = newest.startedAt ?? newest.triggeredAt;
  if (started == null) return null;
  final age = (now ?? DateTime.now().toUtc()).difference(started);
  if (age > kRoomAttachWindow) return null;
  return ActiveRoomRun(runId: newest.id, ticker: newest.ticker);
}

class ActiveRoomNotifier extends StateNotifier<ActiveRoomRun?> {
  ActiveRoomNotifier(this._ref) : super(null) {
    Future<void>.microtask(refresh);
  }

  final Ref _ref;
  int _token = 0;

  /// Re-ask the server. Safe to call at any time; a slower older answer never
  /// overwrites a newer one. Returns what the server said (null on none/error).
  Future<ActiveRoomRun?> refresh() async {
    final mine = ++_token;
    ActiveRoomRun? found;
    try {
      final api = _ref.read(apiClientProvider);
      final userId = await DeviceUser.getOrCreate();
      final runs = await api.listUserRooms(userId, limit: 1);
      found = activeRoomRunFrom(runs);
    } catch (e) {
      debugPrint('DEF506 active-room lookup failed, no rejoin banner: $e');
    }
    if (!mounted || mine != _token) return found;
    state = found;
    return found;
  }

  /// The banner was used or is stale.
  void clear() {
    _token++;
    if (mounted) state = null;
  }
}

final activeRoomProvider =
    StateNotifierProvider<ActiveRoomNotifier, ActiveRoomRun?>(
        (ref) => ActiveRoomNotifier(ref));
