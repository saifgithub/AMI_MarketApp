"""
Core LSTM machinery for C01 ("a neural network predicts tomorrow's stock price").

Everything the two recipe variants (A1, A2) and the fair arm (B-price, B-return)
share: windowing a univariate series into (lookback, target) pairs, the two
network architectures named in the pre-registration, a plain train loop, the
naive "tomorrow = today" persistence forecast used as M1's denominator, and the
recursive 30-step self-fed forecast used for M6.

No look-ahead is enforced here except where PREREGISTRATION.md explicitly calls
for it (Arm A's whole-series scaler fit) -- the caller decides which segment the
scaler sees; this module never fits a scaler itself.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.mps.manual_seed(seed) if torch.backends.mps.is_available() else None


def make_windows(series: np.ndarray, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    """Slice a 1-D scaled series into (X, y) windows.

    X[i] = series[i : i + lookback] (shape (lookback, 1)); y[i] = series[i +
    lookback], i.e. the value immediately AFTER the window -- the window
    ending at index (i + lookback - 1) predicts index (i + lookback), never a
    value already inside the window itself.
    """
    series = np.asarray(series, dtype=np.float32).reshape(-1)
    n = len(series)
    n_windows = n - lookback
    if n_windows <= 0:
        raise ValueError(f"series length {n} too short for lookback {lookback}")

    X = np.empty((n_windows, lookback, 1), dtype=np.float32)
    y = np.empty((n_windows,), dtype=np.float32)
    for i in range(n_windows):
        X[i, :, 0] = series[i : i + lookback]
        y[i] = series[i + lookback]
    return X, y


class LSTM_A1(nn.Module):
    """3 stacked LSTM layers x 50 units -> Dense(1), as specified for Arm A1."""

    def __init__(self, input_size: int = 1, hidden_size: int = 50):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=3,
            batch_first=True,
        )
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        last = out[:, -1, :]
        return self.head(last).squeeze(-1)


class LSTM_A2(nn.Module):
    """LSTM(50) -> LSTM(50) -> Dense(25) -> Dense(1), our disclosed A2 assumption."""

    def __init__(self, input_size: int = 1, hidden_size: int = 50):
        super().__init__()
        self.lstm1 = nn.LSTM(input_size=input_size, hidden_size=hidden_size, batch_first=True)
        self.lstm2 = nn.LSTM(input_size=hidden_size, hidden_size=hidden_size, batch_first=True)
        self.dense1 = nn.Linear(hidden_size, 25)
        self.act = nn.ReLU()
        self.head = nn.Linear(25, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm1(x)
        out, _ = self.lstm2(out)
        last = out[:, -1, :]
        h = self.act(self.dense1(last))
        return self.head(h).squeeze(-1)


@dataclass
class TrainResult:
    model: nn.Module
    epochs_run: int
    final_train_loss: float


def train_model(
    model: nn.Module,
    X_train: np.ndarray,
    y_train: np.ndarray,
    epochs: int,
    batch_size: int,
    device: torch.device,
    lr: float = 1e-3,
) -> TrainResult:
    """MSE loss, Adam, as specified. Plain full-pass mini-batch loop, no shuffling
    of the temporal order needed since windows are already iid samples of
    (past-window, next-value) pairs -- shuffling batch composition (not window
    content) is standard and does not leak test information."""
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    X = torch.from_numpy(X_train).to(device)
    y = torch.from_numpy(y_train).to(device)
    n = X.shape[0]

    final_loss = float("nan")
    for _epoch in range(epochs):
        perm = torch.randperm(n, device=device)
        epoch_losses = []
        for start in range(0, n, batch_size):
            idx = perm[start : start + batch_size]
            xb, yb = X[idx], y[idx]
            optimizer.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            optimizer.step()
            epoch_losses.append(loss.item())
        final_loss = float(np.mean(epoch_losses))

    return TrainResult(model=model, epochs_run=epochs, final_train_loss=final_loss)


def predict(model: nn.Module, X: np.ndarray, device: torch.device) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        Xt = torch.from_numpy(X).to(device)
        pred = model(Xt)
    return pred.cpu().numpy().reshape(-1)


def naive_persistence_forecast(y_true_scaled: np.ndarray) -> np.ndarray:
    """The 'tomorrow = today' baseline: forecast for target y[i] is the value one
    step behind it in the same scaled space, i.e. the last element of window i
    (= series value at the close the window ends on). Caller supplies the last
    element of each window (equivalent to y shifted by one)."""
    return np.asarray(y_true_scaled, dtype=np.float64)


def recursive_forecast(
    model: nn.Module,
    seed_window: np.ndarray,
    n_steps: int,
    device: torch.device,
) -> np.ndarray:
    """Self-fed recursive forecast: predict step 1, append it to the window,
    drop the oldest element, predict step 2, etc. `seed_window` is the last
    `lookback` scaled values known at the forecast origin (shape (lookback,)).
    """
    model.eval()
    window = np.asarray(seed_window, dtype=np.float32).reshape(-1).copy()
    lookback = len(window)
    preds = np.empty(n_steps, dtype=np.float64)
    with torch.no_grad():
        for step in range(n_steps):
            x = window.reshape(1, lookback, 1)
            xt = torch.from_numpy(x).to(device)
            pred = model(xt).cpu().numpy().reshape(-1)[0]
            preds[step] = pred
            window = np.roll(window, -1)
            window[-1] = pred
    return preds
