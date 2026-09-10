#!/usr/bin/env python3
"""AMI Trade — Alpha daily usage analytics (CR051).

Read-only. Queries the `ami_trade` Postgres on melehost (same SSH + `docker exec
psql` transport as scripts/users.sh, but SQL is piped over stdin so nothing needs
shell-quoting) and renders a self-contained, theme-aware HTML dashboard plus a
compact text summary.

All figures EXCLUDE the synthetic/seed/probe rows via the CR051 real-users
rule — DEF403: fetched at runtime from the one canonical definition
(`app.services.admin_analytics._real_users_clause()`, asked over the same
docker-exec transport below, never hand-copied here):
  - 13 CR035 `last_app_version='room-benchmark'` load-test users
  - 10 seed fixtures created in the 2026-05-24 05:10 minute (no device/app)
  - 12 CR125/DEF227-229 probe users, excluded by id (shape-indistinguishable
    from real bare sessions)

Usage:
  python3 scripts/analytics/daily_report.py [--out report.html] [--local]
      --out    HTML output path (default: <scratchpad>/ami_daily_report.html)
      --local  run `docker exec` directly instead of over SSH (for an on-host cron)
      --ssh-host HOST  override AMI_SSH_HOST (default: melehost)

Timezone for "today"/day-bucketing: Asia/Kuala_Lumpur (Saiful's TZ), matching users.sh.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone

TZ = "Asia/Kuala_Lumpur"
CONTAINER = "ami_postgres"
API_CONTAINER = "ami_api_alpha"
DB = "ami_trade"
DB_USER = "postgres"

# "Today" as a SQL expression in Saiful's timezone. Reused across queries.
D0 = f"(now() AT TIME ZONE '{TZ}')::date"

# The synthetic-exclusion predicate (applied to the users table). DEF403 —
# fetched at runtime from the ONE canonical definition
# (`app.services.admin_analytics._real_users_clause()`) via `fetch_real_pred()`
# below, rather than hand-copied here: this script has no `app` import path
# (it runs on the melehost host, not inside `ami_api_alpha`), so it asks the
# container that does for the compiled SQL. Never paste a literal copy of
# this predicate again — that is exactly the drift DEF403 found. `REAL_PRED`
# is a placeholder token, substituted into `CTES` once `fetch_real_pred()`
# has run (see `collect()`).
REAL_PRED_PLACEHOLDER = "__REAL_PRED__"

# Common CTEs: real users, a unioned per-user activity stream, and its day buckets.
# `{REAL_PRED_PLACEHOLDER}` is replaced with the fetched predicate at query time.
CTES = f"""
real_users AS (SELECT * FROM users WHERE {REAL_PRED_PLACEHOLDER}),
activity AS (
  SELECT user_id, triggered_at AS ts FROM room_runs
  UNION ALL SELECT user_id, opened_at FROM sim_trades
  UNION ALL SELECT user_id, created_at FROM journal_entries WHERE deleted_at IS NULL
  UNION ALL SELECT user_id, created_at FROM one_on_one_messages
  UNION ALL SELECT user_id, coalesce(completed_at, started_at)
             FROM lessons_progress WHERE started_at IS NOT NULL
),
ra AS (
  SELECT a.user_id, (a.ts AT TIME ZONE '{TZ}')::date AS d
  FROM activity a JOIN real_users ru ON ru.id = a.user_id
  WHERE a.ts IS NOT NULL
)"""


# ── DB transport ──────────────────────────────────────────────────────────────

def _psql_argv(local: bool, ssh_host: str) -> list[str]:
    if local:
        # No shell in between: pass a clean argv so the field separator is a
        # bare '|' (splitting a shell string would keep the quotes literally).
        return ["docker", "exec", "-i", CONTAINER, "psql", "-U", DB_USER,
                "-d", DB, "-At", "-F", "|", "-q", "-v", "ON_ERROR_STOP=1"]
    # SSH runs a remote shell, which strips the quotes around the separator.
    exec_cmd = (
        f"docker exec -i {CONTAINER} "
        f"psql -U {DB_USER} -d {DB} -At -F '|' -q -v ON_ERROR_STOP=1"
    )
    return ["ssh", ssh_host, exec_cmd]


def _api_argv(local: bool, ssh_host: str) -> list[str]:
    """Same transport shape as `_psql_argv`, targeting `ami_api_alpha` — the
    one container with `app` on PYTHONPATH, so the canonical exclusion rule
    can be asked for rather than hand-copied (DEF403)."""
    cmd = ["python3", "-m", "app.services.admin_analytics"]
    if local:
        return ["docker", "exec", API_CONTAINER, *cmd]
    exec_cmd = f"docker exec {API_CONTAINER} " + " ".join(cmd)
    return ["ssh", ssh_host, exec_cmd]


def fetch_real_pred(*, local: bool, ssh_host: str) -> str:
    """The CR051 real-users WHERE fragment, from the one canonical source.

    Asks `ami_api_alpha` to compile `admin_analytics._real_users_clause()`
    to literal SQL (see that module's `real_users_where_sql()`/`_cli()`) —
    never a pasted copy. Fails loudly (CR040): a transport error here must
    not silently fall back to a stale local literal, or every report from
    that point on would be counting probe/synthetic users as real without
    anyone knowing.
    """
    proc = subprocess.run(
        _api_argv(local, ssh_host), text=True, capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(
            "fetch_real_pred failed — could not reach ami_api_alpha for the "
            f"canonical exclusion rule:\n{proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def query(sql: str, *, local: bool, ssh_host: str) -> list[list[str]]:
    """Run one SQL statement, return rows as lists of string fields."""
    proc = subprocess.run(
        _psql_argv(local, ssh_host),
        input=sql,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"psql failed:\n{proc.stderr.strip()}\n--- SQL ---\n{sql}")
    return [line.split("|") for line in proc.stdout.splitlines() if line != ""]


def scalars(sql: str, **kw) -> dict[str, str]:
    """For key|value UNION-ALL queries → {key: value}."""
    return {r[0]: r[1] for r in query(sql, **kw)}


# ── queries ───────────────────────────────────────────────────────────────────

Q_SNAPSHOT = f"""
WITH {CTES}
SELECT 'real_total', count(*)::text FROM real_users
UNION ALL SELECT 'claimed_total', count(*)::text FROM real_users WHERE NOT is_anonymous
UNION ALL SELECT 'anon_total', count(*)::text FROM real_users WHERE is_anonymous
UNION ALL SELECT 'in_trial', count(*)::text FROM real_users WHERE trial_expires_at > now()
UNION ALL SELECT 'suspended', count(*)::text FROM real_users WHERE suspended_at IS NOT NULL
UNION ALL SELECT 'claimed_today', count(*)::text FROM real_users
    WHERE claimed_at IS NOT NULL AND (claimed_at AT TIME ZONE '{TZ}')::date = {D0}
UNION ALL SELECT 'new_7d', count(*)::text FROM real_users
    WHERE created_at > now() - interval '7 days'
UNION ALL SELECT 'plan_floor_pass', count(*)::text FROM real_users WHERE plan = 'floor_pass'
UNION ALL SELECT 'plan_trader', count(*)::text FROM real_users WHERE plan = 'trader'
UNION ALL SELECT 'plan_floor_manager', count(*)::text FROM real_users WHERE plan = 'floor_manager'
UNION ALL SELECT 'plat_ios', count(*)::text FROM real_users
    WHERE device_model LIKE 'iPhone%' OR device_model LIKE 'iPad%'
UNION ALL SELECT 'plat_android', count(*)::text FROM real_users
    WHERE (device_model IS NOT NULL AND device_model NOT LIKE 'iPhone%'
           AND device_model NOT LIKE 'iPad%') OR os_version LIKE 'Android%'
UNION ALL SELECT 'plat_unknown', count(*)::text FROM real_users
    WHERE device_model IS NULL AND coalesce(os_version,'') NOT LIKE 'Android%'
UNION ALL SELECT 'dau', count(distinct user_id)::text FROM ra WHERE d = {D0}
UNION ALL SELECT 'wau', count(distinct user_id)::text FROM ra WHERE d > {D0} - 7
UNION ALL SELECT 'mau', count(distinct user_id)::text FROM ra WHERE d > {D0} - 30
UNION ALL SELECT 'returning_today', count(distinct user_id)::text FROM ra
    WHERE d = {D0} AND user_id IN (SELECT user_id FROM ra WHERE d < {D0})
;
"""

Q_ENGAGE = f"""
WITH {CTES}
SELECT 'convene_total', count(*)::text FROM room_runs r JOIN real_users u ON u.id = r.user_id
UNION ALL SELECT 'convene_completed', count(*)::text FROM room_runs r JOIN real_users u ON u.id = r.user_id WHERE r.status = 'completed'
UNION ALL SELECT 'convene_7d', count(*)::text FROM room_runs r JOIN real_users u ON u.id = r.user_id WHERE r.triggered_at > now() - interval '7 days'
UNION ALL SELECT 'convene_completed_7d', count(*)::text FROM room_runs r JOIN real_users u ON u.id = r.user_id WHERE r.triggered_at > now() - interval '7 days' AND r.status = 'completed'
UNION ALL SELECT 'aborted_7d', count(*)::text FROM room_runs r JOIN real_users u ON u.id = r.user_id WHERE r.triggered_at > now() - interval '7 days' AND r.status = 'aborted'
UNION ALL SELECT 'failed_7d', count(*)::text FROM room_runs r JOIN real_users u ON u.id = r.user_id WHERE r.triggered_at > now() - interval '7 days' AND r.status = 'failed'
UNION ALL SELECT 'cancelled_7d', count(*)::text FROM room_runs r JOIN real_users u ON u.id = r.user_id WHERE r.triggered_at > now() - interval '7 days' AND r.status = 'cancelled'
UNION ALL SELECT 'stuck_runs', count(*)::text FROM room_runs r JOIN real_users u ON u.id = r.user_id WHERE r.status NOT IN ('completed','aborted','failed','cancelled')
UNION ALL SELECT 'median_dur_ms', coalesce(round(percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms))::text, '-') FROM room_runs r JOIN real_users u ON u.id = r.user_id WHERE r.status = 'completed' AND r.duration_ms IS NOT NULL
UNION ALL SELECT 'cohort7_size', count(*)::text FROM real_users WHERE created_at > now() - interval '7 days'
UNION ALL SELECT 'cohort7_activated', count(*)::text FROM real_users u WHERE u.created_at > now() - interval '7 days' AND EXISTS (SELECT 1 FROM room_runs r WHERE r.user_id = u.id)
UNION ALL SELECT 'trades_today', count(*)::text FROM sim_trades t JOIN real_users u ON u.id = t.user_id WHERE (t.opened_at AT TIME ZONE '{TZ}')::date = {D0}
UNION ALL SELECT 'journal_today', count(*)::text FROM journal_entries j JOIN real_users u ON u.id = j.user_id WHERE j.deleted_at IS NULL AND (j.created_at AT TIME ZONE '{TZ}')::date = {D0}
UNION ALL SELECT 'oo_today', count(*)::text FROM one_on_one_messages m JOIN real_users u ON u.id = m.user_id WHERE m.role = 'user' AND (m.created_at AT TIME ZONE '{TZ}')::date = {D0}
UNION ALL SELECT 'lessons_done_today', count(*)::text FROM lessons_progress l JOIN real_users u ON u.id = l.user_id WHERE l.completed_at IS NOT NULL AND (l.completed_at AT TIME ZONE '{TZ}')::date = {D0}
UNION ALL SELECT 'watch_today', count(*)::text FROM sim_watchlists w JOIN real_users u ON u.id = w.user_id WHERE (w.added_at AT TIME ZONE '{TZ}')::date = {D0}
UNION ALL SELECT 'credits_left', coalesce(sum(credit_balance),0)::text FROM real_users
;
"""

Q_RELIABILITY = f"""
SELECT 'llm_calls_7d', count(*)::text FROM llm_audit WHERE created_at > now() - interval '7 days'
UNION ALL SELECT 'llm_errors_7d', count(*)::text FROM llm_audit WHERE created_at > now() - interval '7 days' AND error IS NOT NULL
UNION ALL SELECT 'llm_p50_ms', coalesce(round(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms))::text, '-') FROM llm_audit WHERE created_at > now() - interval '7 days' AND latency_ms IS NOT NULL
UNION ALL SELECT 'bugs_open', count(*)::text FROM bug_reports WHERE status IN ('open','in_progress')
UNION ALL SELECT 'bugs_new_today', count(*)::text FROM bug_reports WHERE (created_at AT TIME ZONE '{TZ}')::date = {D0}
UNION ALL SELECT 'bugs_ios_open', count(*)::text FROM bug_reports WHERE status IN ('open','in_progress') AND platform = 'ios'
UNION ALL SELECT 'bugs_android_open', count(*)::text FROM bug_reports WHERE status IN ('open','in_progress') AND platform LIKE 'android%'
;
"""

# 14-day spine → new users / DAU / rooms / completed rooms per day (real users only).
Q_SERIES = f"""
WITH {CTES},
rr AS (
  SELECT r.status, (r.triggered_at AT TIME ZONE '{TZ}')::date AS d
  FROM room_runs r JOIN real_users u ON u.id = r.user_id
),
spine AS (
  SELECT generate_series({D0} - 13, {D0}, interval '1 day')::date AS d
)
SELECT to_char(s.d, 'YYYY-MM-DD'),
  (SELECT count(*) FROM real_users u WHERE (u.created_at AT TIME ZONE '{TZ}')::date = s.d)::text,
  (SELECT count(distinct user_id) FROM ra WHERE ra.d = s.d)::text,
  (SELECT count(*) FROM rr WHERE rr.d = s.d)::text,
  (SELECT count(*) FROM rr WHERE rr.d = s.d AND status = 'completed')::text
FROM spine s ORDER BY s.d;
"""

Q_FLAG_LOWCOMPLETE = f"""
WITH {CTES}
SELECT left(r.user_id::text, 8),
       coalesce(nullif(u.email, ''), u.device_model, 'anon'),
       count(*)::text,
       count(*) FILTER (WHERE r.status = 'completed')::text
FROM room_runs r JOIN real_users u ON u.id = r.user_id
GROUP BY r.user_id, u.email, u.device_model
HAVING count(*) >= 5
   AND count(*) FILTER (WHERE r.status = 'completed')::float / count(*) < 0.6
ORDER BY count(*) DESC;
"""

Q_FLAG_CLAIMED_IDLE = f"""
WITH {CTES}
SELECT left(u.id::text, 8), coalesce(nullif(u.email, ''), '-'), u.credit_balance::text
FROM real_users u
WHERE NOT u.is_anonymous
  AND NOT EXISTS (SELECT 1 FROM room_runs r WHERE r.user_id = u.id)
ORDER BY u.claimed_at DESC NULLS LAST;
"""

Q_FLAG_ORPHANS = """
SELECT left(r.user_id::text, 8), count(*)::text
FROM room_runs r LEFT JOIN users u ON u.id = r.user_id
WHERE u.id IS NULL
GROUP BY r.user_id ORDER BY count(*) DESC;
"""

Q_RECENT_CLAIMED = f"""
WITH {CTES}
SELECT left(u.id::text, 8),
       coalesce(nullif(u.email, ''), '-'),
       CASE WHEN u.apple_id IS NOT NULL THEN 'apple'
            WHEN u.google_id IS NOT NULL THEN 'google'
            WHEN u.email IS NOT NULL THEN 'email' ELSE '?' END,
       to_char(u.claimed_at AT TIME ZONE '{TZ}', 'Mon DD')
FROM real_users u
WHERE u.claimed_at IS NOT NULL
ORDER BY u.claimed_at DESC LIMIT 6;
"""


# ── metric assembly ─────────────────────────────────────────────────────────────

def collect(local: bool, ssh_host: str) -> dict:
    kw = {"local": local, "ssh_host": ssh_host}
    real_pred = fetch_real_pred(**kw)

    def resolved(q: str) -> str:
        return q.replace(REAL_PRED_PLACEHOLDER, real_pred)

    snap = scalars(resolved(Q_SNAPSHOT), **kw)
    eng = scalars(resolved(Q_ENGAGE), **kw)
    rel = scalars(Q_RELIABILITY, **kw)
    series = query(resolved(Q_SERIES), **kw)
    return {
        "snap": snap,
        "eng": eng,
        "rel": rel,
        "series": [
            {"date": r[0], "new": int(r[1]), "dau": int(r[2]),
             "rooms": int(r[3]), "completed": int(r[4])}
            for r in series
        ],
        "flag_lowcomplete": query(resolved(Q_FLAG_LOWCOMPLETE), **kw),
        "flag_claimed_idle": query(resolved(Q_FLAG_CLAIMED_IDLE), **kw),
        "flag_orphans": query(Q_FLAG_ORPHANS, **kw),
        "recent_claimed": query(resolved(Q_RECENT_CLAIMED), **kw),
    }


def _i(d: dict, k: str, default: int = 0) -> int:
    try:
        return int(d.get(k, default))
    except (ValueError, TypeError):
        return default


def derive(data: dict) -> dict:
    series = data["series"]
    today = series[-1] if series else {"new": 0, "dau": 0, "rooms": 0, "completed": 0}
    yday = series[-2] if len(series) > 1 else {"new": 0, "dau": 0, "rooms": 0, "completed": 0}
    last7 = series[-7:] if len(series) >= 7 else series
    prev7 = series[-14:-7] if len(series) >= 14 else []

    def avg(rows, key):
        return (sum(r[key] for r in rows) / len(rows)) if rows else 0.0

    eng = data["eng"]
    cohort_size = _i(eng, "cohort7_size")
    cohort_act = _i(eng, "cohort7_activated")
    conv7 = _i(eng, "convene_7d")
    conv7_done = _i(eng, "convene_completed_7d")
    mau = _i(data["snap"], "mau")
    wau = _i(data["snap"], "wau")
    rooms7 = sum(r["rooms"] for r in last7)

    return {
        "today": today, "yday": yday,
        "spark_new": [r["new"] for r in series],
        "spark_dau": [r["dau"] for r in series],
        "spark_rooms": [r["rooms"] for r in series],
        "avg7_new": avg(last7, "new"),
        "avg7_dau": avg(last7, "dau"),
        "avg7_rooms": avg(last7, "rooms"),
        "completion_today": (today["completed"] / today["rooms"] * 100) if today["rooms"] else None,
        "completion_7d": (conv7_done / conv7 * 100) if conv7 else None,
        "new_7d_sum": sum(r["new"] for r in last7),
        "new_prev7_sum": sum(r["new"] for r in prev7) if prev7 else None,
        "activation_7d": (cohort_act / cohort_size * 100) if cohort_size else None,
        "cohort_size": cohort_size, "cohort_act": cohort_act,
        "rooms_per_active_7d": (rooms7 / wau) if wau else None,
        "stickiness": (wau / mau * 100) if mau else None,
        "wau": wau, "mau": mau,
    }


# ── rendering helpers ───────────────────────────────────────────────────────────

def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def fmt_dur(ms) -> str:
    try:
        v = int(ms)
    except (ValueError, TypeError):
        return "—"
    return f"{v/1000:.0f}s" if v < 60000 else f"{v/60000:.1f}m"


def sparkline(values: list[int], w: int = 132, h: int = 34) -> str:
    """Inline SVG area sparkline with an emphasized endpoint."""
    if not values:
        return ""
    n = len(values)
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pad = 3
    iw, ih = w - pad * 2, h - pad * 2

    def pt(i, v):
        x = pad + (iw * i / (n - 1)) if n > 1 else pad + iw / 2
        y = pad + ih - (ih * (v - lo) / span)
        return x, y

    pts = [pt(i, v) for i, v in enumerate(values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = (f"M{pts[0][0]:.1f},{h-pad:.1f} L"
            + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            + f" L{pts[-1][0]:.1f},{h-pad:.1f} Z")
    ex, ey = pts[-1]
    return (
        f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'preserveAspectRatio="none" aria-hidden="true">'
        f'<path d="{area}" fill="url(#sparkfill)"/>'
        f'<polyline points="{line}" fill="none" stroke="var(--accent)" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="2.4" fill="var(--accent)"/>'
        f'</svg>'
    )


def delta_badge(today: float, ref: float, *, pct=False, higher_good=True) -> str:
    """A ▲/▼ chip comparing today to a reference (yesterday or 7d avg)."""
    if ref is None:
        return ""
    diff = today - ref
    if abs(diff) < 1e-9:
        return '<span class="delta flat">— flat</span>'
    up = diff > 0
    good = (up == higher_good)
    arrow = "▲" if up else "▼"
    mag = f"{abs(diff):.0f}%" if pct else f"{abs(diff):+.1f}".lstrip("+")
    cls = "up" if good else "down"
    return f'<span class="delta {cls}">{arrow} {esc(mag)}</span>'


def kpi_tile(label, today_val, spark_svg, sub) -> str:
    return f"""
    <div class="kpi">
      <div class="kpi-label">{esc(label)}</div>
      <div class="kpi-value">{esc(today_val)}</div>
      <div class="kpi-spark">{spark_svg}</div>
      <div class="kpi-sub">{sub}</div>
    </div>"""


def stat_row(label, value, extra="") -> str:
    return (f'<div class="stat"><span class="stat-k">{esc(label)}</span>'
            f'<span class="stat-v">{esc(value)}{extra}</span></div>')


def bar(label, value, total, tone="accent") -> str:
    pct = (value / total * 100) if total else 0
    return (f'<div class="barrow"><span class="bar-k">{esc(label)}</span>'
            f'<span class="bar-track"><span class="bar-fill {tone}" style="width:{pct:.0f}%"></span></span>'
            f'<span class="bar-v">{esc(value)}</span></div>')


# ── HTML document ────────────────────────────────────────────────────────────────

def render_html(data: dict, d: dict, generated_at: str) -> str:
    s, eng, rel = data["snap"], data["eng"], data["rel"]
    t, y = d["today"], d["yday"]

    real_total = _i(s, "real_total")
    comp_today = d["completion_today"]
    comp_today_str = f"{comp_today:.0f}%" if comp_today is not None else "—"
    comp_7d = d["completion_7d"]

    # Headline tiles
    kpis = "".join([
        kpi_tile("New users", t["new"], sparkline(d["spark_new"]),
                 f'{delta_badge(t["new"], d["avg7_new"])} vs 7d avg {d["avg7_new"]:.1f}'),
        kpi_tile("Active today (DAU)", t["dau"], sparkline(d["spark_dau"]),
                 f'{delta_badge(t["dau"], d["avg7_dau"])} vs 7d avg {d["avg7_dau"]:.1f}'),
        kpi_tile("Rooms convened", t["rooms"], sparkline(d["spark_rooms"]),
                 f'{delta_badge(t["rooms"], d["avg7_rooms"])} vs 7d avg {d["avg7_rooms"]:.1f}'),
        kpi_tile("Completion rate", comp_today_str, "",
                 (f'7d {comp_7d:.0f}%' if comp_7d is not None else '7d —')
                 + f' · {_i(eng, "convene_completed_7d")}/{_i(eng, "convene_7d")} runs'),
    ])

    # Acquisition
    acq = (
        stat_row("Real users (total)", real_total)
        + stat_row("New this week", d["new_7d_sum"],
                   f' <span class="muted">/ {("+" + str(d["new_7d_sum"]-d["new_prev7_sum"]) ) if d["new_prev7_sum"] is not None else ""} vs prev wk</span>' if d["new_prev7_sum"] is not None else "")
        + stat_row("Claimed accounts", _i(s, "claimed_total"),
                   f' <span class="muted">({_i(s, "claimed_today")} today)</span>')
        + '<div class="bars">'
        + bar("iOS", _i(s, "plat_ios"), real_total)
        + bar("Android", _i(s, "plat_android"), real_total)
        + bar("Unknown", _i(s, "plat_unknown"), real_total, tone="muted")
        + '</div>'
    )
    recent = data["recent_claimed"]
    if recent:
        acq += '<div class="mini-h">Recent sign-ups</div><table class="mini">'
        for r in recent:
            acq += (f'<tr><td class="mono">{esc(r[0])}</td><td>{esc(r[1])}</td>'
                    f'<td><span class="tag">{esc(r[2])}</span></td>'
                    f'<td class="r muted">{esc(r[3])}</td></tr>')
        acq += '</table>'

    # Activation & engagement
    act = d["activation_7d"]
    rpa = d["rooms_per_active_7d"]
    engage = (
        stat_row("7-day cohort activated",
                 f'{act:.0f}%' if act is not None else "—",
                 f' <span class="muted">({d["cohort_act"]}/{d["cohort_size"]} convened a Room)</span>')
        + stat_row("Rooms convened (total)", _i(eng, "convene_total"),
                   f' <span class="muted">· {_i(eng, "convene_completed")} completed</span>')
        + stat_row("Rooms / active user (7d)",
                   f'{rpa:.1f}' if rpa is not None else "—")
        + stat_row("Median room duration", fmt_dur(eng.get("median_dur_ms")))
        + '<div class="mini-h">Today\'s actions</div><div class="chips">'
        + f'<span class="chip">Trades <b>{_i(eng, "trades_today")}</b></span>'
        + f'<span class="chip">Journal <b>{_i(eng, "journal_today")}</b></span>'
        + f'<span class="chip">1-on-1 msgs <b>{_i(eng, "oo_today")}</b></span>'
        + f'<span class="chip">Lessons done <b>{_i(eng, "lessons_done_today")}</b></span>'
        + f'<span class="chip">Watchlist adds <b>{_i(eng, "watch_today")}</b></span>'
        + '</div>'
    )

    # Retention
    stick = d["stickiness"]
    retention = (
        stat_row("DAU", t["dau"])
        + stat_row("WAU (7d)", d["wau"])
        + stat_row("MAU (30d)", d["mau"])
        + stat_row("Stickiness (WAU/MAU)", f'{stick:.0f}%' if stick is not None else "—")
        + stat_row("Returning today", _i(s, "returning_today"),
                   f' <span class="muted">· {t["new"]} new</span>')
    )

    # Reliability
    llm_calls = _i(rel, "llm_calls_7d")
    llm_err = _i(rel, "llm_errors_7d")
    err_rate = (llm_err / llm_calls * 100) if llm_calls else 0
    err_tone = "good" if err_rate < 1 else ("warn" if err_rate < 5 else "crit")
    bugs_open = _i(rel, "bugs_open")
    bug_tone = "good" if bugs_open == 0 else ("warn" if bugs_open < 5 else "crit")
    aborted = _i(eng, "aborted_7d") + _i(eng, "failed_7d") + _i(eng, "cancelled_7d")
    reliability = (
        stat_row("Room completion (7d)",
                 f'{comp_7d:.0f}%' if comp_7d is not None else "—",
                 f' <span class="pill {"good" if (comp_7d or 0) >= 90 else "warn"}">{aborted} not finished</span>')
        + stat_row("Stuck runs", _i(eng, "stuck_runs"),
                   ' <span class="pill good">clear</span>' if _i(eng, "stuck_runs") == 0 else ' <span class="pill crit">check</span>')
        + stat_row("LLM error rate (7d)", f'{err_rate:.1f}%',
                   f' <span class="pill {err_tone}">{llm_err}/{llm_calls}</span>')
        + stat_row("LLM latency p50 (7d)", fmt_dur_ms(rel.get("llm_p50_ms")))
        + stat_row("Open bugs", bugs_open,
                   f' <span class="pill {bug_tone}">{_i(rel, "bugs_ios_open")} iOS · {_i(rel, "bugs_android_open")} Android</span>')
        + stat_row("New bugs today", _i(rel, "bugs_new_today"))
    )

    # Monetization
    monet = (
        '<div class="bars">'
        + bar("Floor Pass", _i(s, "plan_floor_pass"), real_total)
        + bar("Trader", _i(s, "plan_trader"), real_total, tone="good")
        + bar("Floor Manager", _i(s, "plan_floor_manager"), real_total, tone="good")
        + '</div>'
        + stat_row("In trial", _i(s, "in_trial"))
        + stat_row("Credits outstanding", _i(eng, "credits_left"))
        + '<div class="note">Charging is off at alpha — plan mix is admin/trial-driven.</div>'
    )

    # Auto-flags
    flags = []
    for r in data["flag_lowcomplete"]:
        conv, done = int(r[2]), int(r[3])
        flags.append(("warn", f'<span class="mono">{esc(r[0])}</span> ({esc(r[1])}) — '
                              f'{conv} convened / <b>{done} done</b> ({done/conv*100:.0f}%)'))
    for r in data["flag_claimed_idle"]:
        flags.append(("info", f'<span class="mono">{esc(r[0])}</span> ({esc(r[1])}) claimed, '
                             f'<b>0 rooms</b> · {esc(r[2])} credits idle'))
    for r in data["flag_orphans"]:
        flags.append(("info", f'<span class="mono">{esc(r[0])}</span> — orphan room_runs '
                             f'(no user row) · {esc(r[1])} run(s)'))
    if not flags:
        flags.append(("good", "No anomalies. Nothing needs your attention."))
    flags_html = "".join(
        f'<div class="flag {tone}"><span class="flag-dot"></span><div>{body}</div></div>'
        for tone, body in flags
    )

    return DOC.format(
        generated=esc(generated_at),
        real_total=real_total,
        anon=_i(s, "anon_total"),
        claimed=_i(s, "claimed_total"),
        suspended=_i(s, "suspended"),
        kpis=kpis, acq=acq, engage=engage, retention=retention,
        reliability=reliability, monet=monet, flags=flags_html,
        window=f'{data["series"][0]["date"]} → {data["series"][-1]["date"]}',
    )


def fmt_dur_ms(ms) -> str:
    try:
        return f"{int(ms)/1000:.1f}s"
    except (ValueError, TypeError):
        return "—"


# The page shell. Token-level theming: dark default via prefers-color-scheme,
# both directions overridable by the viewer's data-theme toggle.
DOC = """<div class="wrap">
<style>
  :root {{
    --bg: #0e1116; --panel: #161b23; --panel-2: #1b212b; --border: #262e3a;
    --ink: #e7ebf1; --ink-dim: #9aa4b2; --ink-mute: #626d7d;
    --accent: #f0a83a; --accent-dim: #8a6a2e;
    --good: #3fbf87; --warn: #e0b341; --crit: #e8604c;
    --spark-fill-0: rgba(240,168,58,.22); --spark-fill-1: rgba(240,168,58,0);
    --shadow: 0 1px 0 rgba(255,255,255,.02), 0 8px 24px rgba(0,0,0,.35);
  }}
  @media (prefers-color-scheme: light) {{
    :root {{
      --bg: #f4f2ec; --panel: #ffffff; --panel-2: #faf8f2; --border: #e4ddcf;
      --ink: #23262b; --ink-dim: #5c636e; --ink-mute: #8c94a0;
      --accent: #b9781a;
      --good: #1f9c68; --warn: #b98718; --crit: #c8432f;
      --spark-fill-0: rgba(185,120,26,.18); --spark-fill-1: rgba(185,120,26,0);
      --shadow: 0 1px 2px rgba(30,25,10,.06), 0 8px 22px rgba(60,50,20,.08);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #0e1116; --panel: #161b23; --panel-2: #1b212b; --border: #262e3a;
    --ink: #e7ebf1; --ink-dim: #9aa4b2; --ink-mute: #626d7d;
    --accent: #f0a83a; --good: #3fbf87; --warn: #e0b341; --crit: #e8604c;
    --spark-fill-0: rgba(240,168,58,.22); --spark-fill-1: rgba(240,168,58,0);
    --shadow: 0 1px 0 rgba(255,255,255,.02), 0 8px 24px rgba(0,0,0,.35);
  }}
  :root[data-theme="light"] {{
    --bg: #f4f2ec; --panel: #ffffff; --panel-2: #faf8f2; --border: #e4ddcf;
    --ink: #23262b; --ink-dim: #5c636e; --ink-mute: #8c94a0;
    --accent: #b9781a; --good: #1f9c68; --warn: #b98718; --crit: #c8432f;
    --spark-fill-0: rgba(185,120,26,.18); --spark-fill-1: rgba(185,120,26,0);
    --shadow: 0 1px 2px rgba(30,25,10,.06), 0 8px 22px rgba(60,50,20,.08);
  }}
  * {{ box-sizing: border-box; }}
  .wrap {{
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, system-ui, sans-serif;
    --mono: ui-monospace, "SF Mono", "JetBrains Mono", "Roboto Mono", Menlo, monospace;
    background: var(--bg); color: var(--ink); font-family: var(--sans);
    min-height: 100%; padding: clamp(16px, 3vw, 34px);
    font-size: 15px; line-height: 1.5; -webkit-font-smoothing: antialiased;
  }}
  .inner {{ max-width: 1120px; margin: 0 auto; }}
  .mono {{ font-family: var(--mono); font-variant-numeric: tabular-nums; }}
  .muted {{ color: var(--ink-mute); font-weight: 400; }}

  header.bar {{
    display: flex; align-items: flex-end; justify-content: space-between;
    gap: 16px; flex-wrap: wrap; padding-bottom: 16px; margin-bottom: 22px;
    border-bottom: 1px solid var(--border);
  }}
  .brand {{ display: flex; align-items: center; gap: 12px; }}
  .hexmark {{ width: 30px; height: 34px; flex: none; color: var(--accent); }}
  .title {{ font-size: 20px; font-weight: 650; letter-spacing: -.01em; }}
  .title small {{ display:block; font-size: 11px; font-weight: 600; letter-spacing:.14em;
    text-transform: uppercase; color: var(--ink-mute); margin-bottom: 3px; }}
  .meta {{ text-align: right; font-size: 12.5px; color: var(--ink-dim); }}
  .meta .mono {{ color: var(--ink); }}
  .context {{ margin-top: 4px; font-size: 11.5px; color: var(--ink-mute); }}

  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 22px; }}
  @media (max-width: 720px) {{ .kpis {{ grid-template-columns: repeat(2, 1fr); }} }}
  .kpi {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    padding: 15px 16px 13px; box-shadow: var(--shadow); position: relative; overflow: hidden;
  }}
  .kpi::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--accent); opacity:.85; }}
  .kpi-label {{ font-size: 11.5px; letter-spacing: .05em; text-transform: uppercase; color: var(--ink-dim); }}
  .kpi-value {{ font-family: var(--mono); font-variant-numeric: tabular-nums;
    font-size: 34px; font-weight: 600; line-height: 1.1; margin: 4px 0 2px; letter-spacing: -.02em; }}
  .kpi-spark {{ height: 34px; margin: 2px 0 6px; }}
  .spark {{ display: block; width: 100%; height: 34px; }}
  .kpi-sub {{ font-size: 12px; color: var(--ink-dim); display: flex; align-items: center; gap: 7px; }}

  .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }}
  @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .card {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px 18px; box-shadow: var(--shadow);
  }}
  .card.span2 {{ grid-column: 1 / -1; }}
  .card h2 {{ font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
    color: var(--ink-dim); margin: 0 0 12px; font-weight: 650;
    display: flex; align-items: center; gap: 8px; }}
  .card h2::before {{ content:""; width: 7px; height: 8px; background: var(--accent);
    clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%); flex: none; }}

  .stat {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
    padding: 6px 0; border-bottom: 1px dashed var(--border); }}
  .stat:last-child {{ border-bottom: none; }}
  .stat-k {{ color: var(--ink-dim); font-size: 13.5px; }}
  .stat-v {{ font-family: var(--mono); font-variant-numeric: tabular-nums;
    font-weight: 600; font-size: 15px; text-align: right; }}

  .delta {{ font-family: var(--mono); font-size: 11.5px; font-weight: 600;
    padding: 1px 6px; border-radius: 5px; white-space: nowrap; }}
  .delta.up {{ color: var(--good); background: color-mix(in srgb, var(--good) 15%, transparent); }}
  .delta.down {{ color: var(--crit); background: color-mix(in srgb, var(--crit) 15%, transparent); }}
  .delta.flat {{ color: var(--ink-mute); background: color-mix(in srgb, var(--ink-mute) 14%, transparent); }}

  .pill {{ font-family: var(--mono); font-size: 11px; font-weight: 600;
    padding: 1px 7px; border-radius: 20px; white-space: nowrap; }}
  .pill.good {{ color: var(--good); background: color-mix(in srgb, var(--good) 14%, transparent); }}
  .pill.warn {{ color: var(--warn); background: color-mix(in srgb, var(--warn) 16%, transparent); }}
  .pill.crit {{ color: var(--crit); background: color-mix(in srgb, var(--crit) 15%, transparent); }}

  .bars {{ margin: 10px 0 4px; display: flex; flex-direction: column; gap: 7px; }}
  .barrow {{ display: grid; grid-template-columns: 96px 1fr 34px; align-items: center; gap: 10px; }}
  .bar-k {{ font-size: 12.5px; color: var(--ink-dim); }}
  .bar-track {{ height: 8px; background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 20px; overflow: hidden; }}
  .bar-fill {{ display: block; height: 100%; border-radius: 20px; background: var(--accent); }}
  .bar-fill.good {{ background: var(--good); }}
  .bar-fill.muted {{ background: var(--ink-mute); }}
  .bar-v {{ font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 13px;
    text-align: right; font-weight: 600; }}

  .mini-h {{ font-size: 10.5px; letter-spacing: .1em; text-transform: uppercase;
    color: var(--ink-mute); margin: 14px 0 7px; }}
  table.mini {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  table.mini td {{ padding: 4px 6px 4px 0; border-bottom: 1px dashed var(--border); }}
  table.mini tr:last-child td {{ border-bottom: none; }}
  table.mini td.r {{ text-align: right; }}
  .tag {{ font-size: 10.5px; font-family: var(--mono); color: var(--ink-dim);
    border: 1px solid var(--border); border-radius: 4px; padding: 0 5px; }}

  .chips {{ display: flex; flex-wrap: wrap; gap: 7px; }}
  .chip {{ font-size: 12.5px; color: var(--ink-dim); background: var(--panel-2);
    border: 1px solid var(--border); border-radius: 7px; padding: 4px 9px; }}
  .chip b {{ font-family: var(--mono); color: var(--ink); margin-left: 3px; }}

  .flags {{ display: flex; flex-direction: column; gap: 8px; }}
  .flag {{ display: flex; align-items: flex-start; gap: 10px; font-size: 13.5px;
    padding: 9px 12px; border-radius: 9px; background: var(--panel-2);
    border: 1px solid var(--border); border-left-width: 3px; }}
  .flag .flag-dot {{ width: 7px; height: 8px; margin-top: 5px; flex: none;
    clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%); }}
  .flag.warn {{ border-left-color: var(--warn); }} .flag.warn .flag-dot {{ background: var(--warn); }}
  .flag.crit {{ border-left-color: var(--crit); }} .flag.crit .flag-dot {{ background: var(--crit); }}
  .flag.info {{ border-left-color: var(--ink-mute); }} .flag.info .flag-dot {{ background: var(--ink-mute); }}
  .flag.good {{ border-left-color: var(--good); }} .flag.good .flag-dot {{ background: var(--good); }}

  .note {{ font-size: 11.5px; color: var(--ink-mute); margin-top: 10px; font-style: italic; }}
  footer {{ margin-top: 22px; padding-top: 14px; border-top: 1px solid var(--border);
    font-size: 11.5px; color: var(--ink-mute); display: flex; justify-content: space-between;
    flex-wrap: wrap; gap: 8px; }}
</style>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <linearGradient id="sparkfill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="var(--spark-fill-0)"/>
    <stop offset="100%" stop-color="var(--spark-fill-1)"/>
  </linearGradient>
</defs></svg>

<div class="inner">
  <header class="bar">
    <div class="brand">
      <svg class="hexmark" viewBox="0 0 30 34" fill="none" aria-hidden="true">
        <path d="M15 1 L28.9 9 V25 L15 33 L1.1 25 V9 Z" stroke="currentColor" stroke-width="1.6"/>
        <path d="M15 8 L22.8 12.5 V21.5 L15 26 L7.2 21.5 V12.5 Z" fill="currentColor" opacity=".22"/>
      </svg>
      <div class="title"><small>AMI Trade · Alpha</small>Daily Usage Report</div>
    </div>
    <div class="meta">
      <div>Generated <span class="mono">{generated}</span></div>
      <div class="context">{real_total} real users · {claimed} claimed · {anon} anonymous · {suspended} suspended</div>
      <div class="context">Synthetics excluded (13 benchmark + 10 seed + 12 probe) · window {window}</div>
    </div>
  </header>

  <section class="kpis">{kpis}</section>

  <section class="grid">
    <div class="card"><h2>Acquisition</h2>{acq}</div>
    <div class="card"><h2>Activation &amp; Engagement</h2>{engage}</div>
    <div class="card"><h2>Retention</h2>{retention}</div>
    <div class="card"><h2>Reliability</h2>{reliability}</div>
    <div class="card"><h2>Monetization</h2>{monet}</div>
    <div class="card"><h2>Auto-flags · needs attention</h2><div class="flags">{flags}</div></div>
  </section>

  <footer>
    <span>AMI Trade — simulation-only trading education · stealth alpha</span>
    <span>Read-only · alpha DB (melehost) · CR051</span>
  </footer>
</div>
</div>"""


# ── text summary (for the notification) ─────────────────────────────────────────

def render_text(data: dict, d: dict, generated_at: str) -> str:
    s, eng, rel = data["snap"], data["eng"], data["rel"]
    t = d["today"]
    comp7 = d["completion_7d"]
    lines = [
        f"AMI Trade · Alpha Daily — {generated_at}",
        f"  {_i(s,'real_total')} real users ({_i(s,'claimed_total')} claimed, {_i(s,'new_7d')} new/7d)",
        f"  Today: {t['new']} new · {t['dau']} active · {t['rooms']} rooms convened",
        f"  DAU {t['dau']} / WAU {d['wau']} / MAU {d['mau']}"
        + (f" · stickiness {d['stickiness']:.0f}%" if d['stickiness'] is not None else ""),
        f"  Completion 7d: {comp7:.0f}%" if comp7 is not None else "  Completion 7d: —",
        f"  iOS {_i(s,'plat_ios')} · Android {_i(s,'plat_android')} · unknown {_i(s,'plat_unknown')}",
        f"  Open bugs: {_i(rel,'bugs_open')} ({_i(rel,'bugs_new_today')} new today)",
    ]
    nflags = (len(data["flag_lowcomplete"]) + len(data["flag_claimed_idle"])
              + len(data["flag_orphans"]))
    lines.append(f"  Auto-flags: {nflags}" if nflags else "  Auto-flags: none")
    return "\n".join(lines)


# ── main ────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="AMI Trade alpha daily analytics")
    default_out = "/private/tmp/ami_daily_report.html"
    ap.add_argument("--out", default=default_out, help="HTML output path")
    ap.add_argument("--local", action="store_true",
                    help="run docker exec locally (on melehost) instead of over SSH")
    ap.add_argument("--ssh-host", default=None, help="override AMI_SSH_HOST / melehost")
    args = ap.parse_args()

    import os
    ssh_host = args.ssh_host or os.environ.get("AMI_SSH_HOST", "melehost")

    try:
        data = collect(args.local, ssh_host)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    d = derive(data)
    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    html = render_html(data, d, generated_at)

    with open(args.out, "w") as f:
        f.write(html)

    print(render_text(data, d, generated_at))
    print(f"\nHTML → {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
