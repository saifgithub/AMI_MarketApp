"""ISS001 — INSERT sites that predate the insert tripwire, pinned as an owned list.

Each entry is `(table, "<path under app/>::<function>")`: the innermost application frame that
FLUSHED an INSERT into a collidable table (`app/db/ami_claim.py`) with no `claim()`/`unclaimed()`
sanction. The value says who owns converting it and why it is not converted yet. Because the
tripwire sees the flush, not the constructor, an entry means "inserts of this table flushed from
this function" — coarse by design, and replaced by a `claim(...)` call at conversion.

This is not an allowlist to extend. The tripwire raises in the unit suite for any site NOT listed;
`tests/unit/test_iss001_insert_tripwire.py` fails when a listed function no longer exists (fixed —
delete the line) or when a DEF308-pinned site is missing. A site leaves this file by being
converted, in ISS001 Phase 2/3. Regenerate the candidate list with the opt-in report:
`ISS001_OUT=report.json PYTHONPATH=. python -m pytest tests/unit -p tests.iss001_observer`.
"""

from __future__ import annotations

INSERT_BASELINE: dict[tuple[str, str], str] = {
    ('agent_activations', 'services/lessons_service.py::_check_agent_unlocks'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('badges', 'services/reputation_service.py::_award_badge'):
        'DEF220 fixed (skip outcome at site); convert to claim().or_skip() in Phase 2',
    ('career_events', 'services/career_ledger.py::post_career_event'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('daily_challenge_attempts', 'api/daily_challenge.py::attempt'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('game_duels', 'services/games_duels.py::pair_field'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('game_entries', 'services/games_service.py::enter_field'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('game_fields', 'services/games_service.py::ensure_field'):
        'DEF308 frozen — founder ruling 2026-08-15 (CR191); convert in ISS001 Phase 3 after the unfreeze',
    ('journal_entries', 'api/portfolio.py::portfolio_health_finding'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('journal_entries', 'services/journal_store.py::append'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('league_members', 'services/league_service.py::_assemble_week'):
        'found by ISS001 observers: scheduler path with no handler; not in DEF308; Phase 2',
    ('league_members', 'services/league_service.py::weekly_roll'):
        'flush point of _assemble_week (attach site); Phase 2',
    ('mandates', 'services/mandate_store.py::upsert'):
        'version-sequence retry-then-raise (DEF220); expected unclaimed(why=...) in Phase 2',
    ('notification_preferences', 'services/notification_service.py::set_preferences'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('notifications', 'services/notification_service.py::notify'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('overlay_edit_counts', 'services/overlay_store.py::save_new_version'):
        'edit counter, DEF220 re-read-and-update; convert to claim().or_update() in Phase 2',
    ('portfolio_nav_daily', 'services/portfolio_nav_daily.py::run_game_nav_snapshot_tick'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('portfolio_nav_daily', 'services/portfolio_nav_daily.py::run_portfolio_nav_snapshot_tick'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('portfolio_value_snapshots', 'services/portfolio_snapshot.py::run_portfolio_snapshot_tick'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('price_history_daily', 'services/price_history.py::upsert_daily_bars'):
        'handled at the caller (P15 _HANDLED_AT_CALLER); convert to ON CONFLICT DO UPDATE in Phase 2',
    ('price_history_daily', 'services/verdict_outcomes.py::score_pending'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('ratio_baselines', 'services/ratio_baselines.py::record_observation'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('reputation_events', 'services/reputation_service.py::award'):
        'append-with-unique-key; expected unclaimed(why=...) or claim().or_skip() in Phase 2',
    ('revenuecat_events', 'api/webhooks.py::revenuecat_webhook'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('room_ratings', 'services/room_rating.py::set_rating'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('sim_holdings', 'services/sim_engine.py::_apply_option_settlement'):
        'holding insert on option settlement, uq_holding_portfolio_ticker; Phase 2',
    ('sim_holdings', 'services/sim_engine.py::_execute_fill'):
        'flush point of _apply_buy_row (attach site): in-memory check over p_row.holdings, uq_holding_portfolio_ticker; found by ISS001 observers, not in DEF308; Phase 2',
    ('sim_option_trades', 'services/sim_options.py::open_structure'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('sim_portfolios', 'services/sim_engine.py::ensure_portfolio'):
        'DEF499 — race-safe since bc4fd43d (partial unique indexes + recovery) and the training key is now claim()-compatible; convert to claim().or_skip() in Phase 2',
    ('social_sentiment_cache', 'services/social_context.py::_cache_write'):
        'DEF220 fixed (skip outcome at site); convert to claim().or_skip() in Phase 2',
    ('streak_freezes', 'services/reputation_service.py::freeze'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('ticker_reference', 'services/ticker_reference.py::upsert_reference'):
        'handled at the caller (P15 _HANDLED_AT_CALLER); convert to ON CONFLICT DO UPDATE in Phase 2',
    ('ticker_splits', 'services/ticker_splits.py::upsert_splits'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
    ('user_devices', 'services/auth_service.py::_upsert_user_device'):
        'DEF220 fixed (re-read-and-update at site); convert to claim().or_update() in Phase 2',
    ('user_overlays', 'services/overlay_store.py::save_new_version'):
        'version-sequence retry-then-raise (DEF220); expected unclaimed(why=...) in Phase 2',
    ('users', 'services/auth_service.py::ensure_anonymous'):
        'DEF308 frozen — founder ruling 2026-08-15 (CR191); convert in ISS001 Phase 3 after the unfreeze',
    ('users', 'services/auth_service.py::sign_in_with_apple'):
        'DEF416 — handled (uq_users_apple_id + begin_nested re-read); convert to claim().or_update() in Phase 3',
    ('users', 'services/auth_service.py::sign_in_with_google'):
        'DEF416 — handled (uq_users_google_id + begin_nested re-read); convert to claim().or_update() in Phase 3',
    ('users', 'services/games_service.py::ensure_field'):
        'User row minted inside the DEF308-frozen ensure_field (not itself pinned by DEF308); convert with it in Phase 3',
    ('verdict_outcomes', 'services/verdict_outcomes.py::bank_verdict_outcome'):
        'ISS001 Phase 2: unconverted pre-control site — convert to claim(...) or declare unclaimed(Model, why=...)',
}
