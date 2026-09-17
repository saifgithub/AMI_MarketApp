"""
The one figure for the video team: A1 predicted-vs-actual on AAPL's test set
(the chart the videos show), beside a zoom of the last 60 test days with the
persistence forecast ("tomorrow = today") drawn too, so a viewer can see how
much of the "near-perfect overlay" is just one-step lag.

Trains its own AAPL A1 model (seed 0, same recipe as run_c01.py's A1 arm) so
this script can run standalone; it does not read run_c01.py's saved state.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.preprocessing import MinMaxScaler

THIS_DIR = Path(__file__).resolve().parent
C01_DIR = THIS_DIR.parent
ROOT_DIR = C01_DIR.parent
OUT_DIR = C01_DIR / "out"

sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(ROOT_DIR))

from common.data import load_daily
from lstm_core import LSTM_A1, make_windows, train_model, predict, set_all_seeds

TICKER = "AAPL"
START = "2012-01-01"
END = "2026-08-31"
LOOKBACK = 100
SPLIT_FRAC = 0.65
EPOCHS = 100
BATCH_SIZE = 64
DEVICE = torch.device("mps")
SEED = 0


def main():
    bars = load_daily([TICKER], START, END)[TICKER]
    close = bars["close"].to_numpy(dtype=np.float64)
    dates = bars.index
    n = len(close)
    split_at = int(round(n * SPLIT_FRAC))

    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled = scaler.fit_transform(close.reshape(-1, 1)).reshape(-1)

    X, y_scaled = make_windows(scaled, LOOKBACK)
    target_idx = np.arange(LOOKBACK, n)
    train_mask = target_idx < split_at
    test_mask = ~train_mask

    X_train, y_train = X[train_mask], y_scaled[train_mask]
    X_test = X[test_mask]
    target_idx_test = target_idx[test_mask]

    set_all_seeds(SEED)
    model = LSTM_A1()
    train_model(model, X_train, y_train, epochs=EPOCHS, batch_size=BATCH_SIZE, device=DEVICE)

    pred_scaled = predict(model, X_test, DEVICE)
    pred_price = scaler.inverse_transform(pred_scaled.reshape(-1, 1)).reshape(-1)
    actual_price = close[target_idx_test]
    test_dates = dates[target_idx_test]
    persistence_price = close[target_idx_test - 1]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    ax.plot(test_dates, actual_price, label="actual", color="black", linewidth=1.2)
    ax.plot(test_dates, pred_price, label="A1 predicted", color="tab:red", linewidth=1.0, alpha=0.85)
    ax.set_title(f"{TICKER} A1: predicted vs actual (full test set)")
    ax.set_xlabel("date")
    ax.set_ylabel("close ($)")
    ax.legend()

    zoom_n = 60
    zoom_dates = test_dates[-zoom_n:]
    zoom_actual = actual_price[-zoom_n:]
    zoom_pred = pred_price[-zoom_n:]
    zoom_persist = persistence_price[-zoom_n:]

    ax2 = axes[1]
    ax2.plot(zoom_dates, zoom_actual, label="actual", color="black", linewidth=1.4, marker="o", markersize=2)
    ax2.plot(zoom_dates, zoom_pred, label="A1 predicted", color="tab:red", linewidth=1.2, marker="o", markersize=2)
    ax2.plot(zoom_dates, zoom_persist, label="persistence (today)", color="tab:blue", linewidth=1.0, linestyle="--")
    ax2.set_title(f"{TICKER} A1: last {zoom_n} test days, zoomed")
    ax2.set_xlabel("date")
    ax2.set_ylabel("close ($)")
    ax2.legend()

    fig.autofmt_xdate()
    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / "overlay_AAPL.png", dpi=150)
    print(f"Wrote {OUT_DIR / 'overlay_AAPL.png'}")


if __name__ == "__main__":
    main()
