#!/bin/bash
# M01 r2 audit — mutation battery. His MUT-1..5 re-performed + AUD-M1..M3.
set -u
ROOT="/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/audit-m01r2"
W="$ROOT/backend"
PY="/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python"
SUITE="tests/unit/test_cr136_price_history.py tests/unit/test_p15_check_then_insert_guard.py"
cd "$W" || exit 1

restore() { git -C "$ROOT" checkout -- backend/app/services/price_history.py backend/app/services/ticker_reference.py; }

run() {
  out=$(PYTHONPATH=. "$PY" -m pytest $SUITE -q 2>&1)
  printf '%-56s %s\n' "$1" "$(echo "$out" | tail -1)"
  echo "$out" | grep -E "^FAILED" | sed 's/^/      /'
}

restore
run "baseline"

# MUT-1 — drop the sticky read on the throttled path (restores A1)
perl -0pi -e 's/            if _last_fetch_failed\.get\(ticker\) and len\(series\.dates\) < min_days:\n                series = _replace_fetch_failed\(series, ticker\)\n//' app/services/price_history.py
run "MUT-1  sticky read dropped on the throttled path"
restore

# MUT-2 — sticky fires on ANY short series (drop the rejected>0 discriminator)
perl -0pi -e 's/        if rejected > 0 and len\(series\.dates\) < min_days:/        if len(series.dates) < min_days:/' app/services/price_history.py
run "MUT-2  rejected>0 discriminator dropped"
restore

# MUT-3 — never clear the flag
perl -0pi -e 's/            _last_fetch_failed\.pop\(ticker, None\)/            pass/' app/services/price_history.py
run "MUT-3  flag never cleared"
restore

# MUT-4 — let IntegrityError propagate again (A2)
perl -0pi -e 's/        except IntegrityError:/        except ZeroDivisionError:/' app/services/price_history.py
run "MUT-4  IntegrityError handler disabled"
restore

# MUT-5 — rejected counted as len(candles) - len(bars)
perl -0pi -e 's/        bars, rejected = _candles_to_bars\(candles or \(\), ticker=ticker\)/        bars, rejected = _candles_to_bars(candles or (), ticker=ticker)\n        rejected = len(candles or ()) - len(bars)/' app/services/price_history.py
run "MUT-5  rejected = len(candles) - len(bars)"
restore

# AUD-M1 — drop the `len(dates) < min_days` gate on the sticky read (over-flag)
perl -0pi -e 's/            if _last_fetch_failed\.get\(ticker\) and len\(series\.dates\) < min_days:/            if _last_fetch_failed.get(ticker):/' app/services/price_history.py
run "AUD-M1 sticky read no longer gated on the series being short"
restore

# AUD-M2 — pessimistic pre-set removed (flag only set on observed failure)
perl -0pi -e 's/        _last_fetch_failed\[ticker\] = True      # pessimistic; cleared on success\n//' app/services/price_history.py
run "AUD-M2 pessimistic pre-set before the network call removed"
restore

# AUD-M3 — ticker_reference's own P15 fix reverted
perl -0pi -e 's/    except IntegrityError:/    except ValueError:/' app/services/ticker_reference.py
run "AUD-M3 ticker_reference IntegrityError handler disabled"
restore

run "restored"
echo "--- tree ---"
git -C "$ROOT" status --short | head
