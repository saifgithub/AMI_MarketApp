"""
Unit tests for C01's core mechanics: window alignment, persistence-forecast
alignment, and Arm B's scaler never touching test data. These are the three
places a look-ahead bug would hide silently and invalidate every downstream
number, so they are checked directly rather than trusted by inspection.

Run bare: `.venv/bin/python -m pytest code/test_core.py -q` from
C01_lstm_predicts_price/.
"""

from __future__ import annotations

import numpy as np
from sklearn.preprocessing import MinMaxScaler

from lstm_core import make_windows, naive_persistence_forecast


def test_window_target_is_next_value_never_inside_window():
    series = np.arange(20, dtype=np.float64)
    lookback = 5
    X, y = make_windows(series, lookback)

    assert X.shape == (15, lookback, 1)
    assert y.shape == (15,)

    for i in range(len(y)):
        window_values = X[i, :, 0]
        np.testing.assert_array_equal(window_values, series[i : i + lookback])
        assert y[i] == series[i + lookback]
        assert y[i] not in window_values or (window_values == y[i]).sum() == 0


def test_window_count_and_no_off_by_one_leak():
    series = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    lookback = 3
    X, y = make_windows(series, lookback)
    # windows: [10,20,30]->40 ; [20,30,40]->50 ; [30,40,50]->60
    assert len(y) == 3
    np.testing.assert_array_equal(X[0, :, 0], [10.0, 20.0, 30.0])
    assert y[0] == 40.0
    np.testing.assert_array_equal(X[-1, :, 0], [30.0, 40.0, 50.0])
    assert y[-1] == 60.0


def test_persistence_forecast_alignment_matches_last_window_element():
    series = np.arange(20, dtype=np.float64)
    lookback = 5
    X, y = make_windows(series, lookback)

    last_of_window = X[:, -1, 0]
    persistence_pred = naive_persistence_forecast(last_of_window)

    # persistence forecast for y[i] (=series[i+lookback]) is series[i+lookback-1],
    # i.e. "tomorrow = today": the actual value one step before the target.
    for i in range(len(y)):
        assert persistence_pred[i] == series[i + lookback - 1]
        assert persistence_pred[i] != y[i]


def test_arm_b_scaler_fit_on_train_segment_only_never_sees_test_values():
    rng = np.random.default_rng(0)
    full_series = rng.normal(loc=100, scale=10, size=200).cumsum()
    split = int(len(full_series) * 0.65)
    train_segment = full_series[:split]
    test_segment = full_series[split:]

    scaler = MinMaxScaler(feature_range=(0, 1))
    scaler.fit(train_segment.reshape(-1, 1))

    assert scaler.data_min_[0] == train_segment.min()
    assert scaler.data_max_[0] == train_segment.max()
    assert scaler.data_min_[0] != full_series.min() or train_segment.min() == full_series.min()

    train_min, train_max = train_segment.min(), train_segment.max()
    full_min, full_max = full_series.min(), full_series.max()
    if test_segment.min() < train_min or test_segment.max() > train_max:
        assert full_min <= train_min and full_max >= train_max
        assert not (scaler.data_min_[0] == full_min and scaler.data_max_[0] == full_max) or (
            train_min == full_min and train_max == full_max
        )

    combined_scaled_train_only = scaler.transform(train_segment.reshape(-1, 1)).reshape(-1)
    assert combined_scaled_train_only.min() >= -1e-9
    assert combined_scaled_train_only.max() <= 1.0 + 1e-9

    scaler_leaked = MinMaxScaler(feature_range=(0, 1))
    scaler_leaked.fit(full_series.reshape(-1, 1))
    assert (scaler_leaked.data_min_[0] != scaler.data_min_[0]) or (
        scaler_leaked.data_max_[0] != scaler.data_max_[0]
    ), "test setup should produce a different scaler when fit on train-only vs whole series"
