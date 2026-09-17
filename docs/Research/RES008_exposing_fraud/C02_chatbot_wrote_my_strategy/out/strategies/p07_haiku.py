import pandas as pd
import numpy as np

def signal(bars: pd.DataFrame) -> pd.Series:
    n = len(bars)
    signals = np.zeros(n)
    
    close = bars['close'].values
    high = bars['high'].values
    low = bars['low'].values
    volume = bars['volume'].values
    
    # RSI (14)
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = np.zeros(n)
    avg_loss = np.zeros(n)
    if n >= 14:
        avg_gain[13] = np.mean(gain[1:14])
        avg_loss[13] = np.mean(loss[1:14])
    for i in range(14, n):
        avg_gain[i] = (avg_gain[i-1] * 13 + gain[i]) / 14
        avg_loss[i] = (avg_loss[i-1] * 13 + loss[i]) / 14
    rs = np.divide(avg_gain, avg_loss, where=avg_loss!=0, out=np.full_like(avg_loss, 100.0))
    rsi = 100 - (100 / (1 + rs))
    
    # MACD (12, 26, 9)
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd_line = ema12 - ema26
    macd_signal = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    macd_hist = macd_line - macd_signal
    
    # Volume MA (20)
    volume_ma = pd.Series(volume).rolling(window=20, min_periods=1).mean().values
    
    in_position = False
    position_side = 0
    entry_price = 0.0
    entry_bar = 0
    
    for i in range(n):
        if in_position:
            exit_signal = False
            
            if position_side == 1:
                # LONG exit conditions
                sl = max(entry_price * 0.98, low[entry_bar])
                if low[i] <= sl:
                    exit_signal = True
                if high[i] >= entry_price * 1.04:
                    exit_signal = True
                if rsi[i] > 70:
                    exit_signal = True
                if i > 0 and macd_line[i-1] > macd_signal[i-1] and macd_line[i] <= macd_signal[i]:
                    exit_signal = True
                if low[i] < low[entry_bar]:
                    exit_signal = True
                if i - entry_bar >= 5:
                    exit_signal = True
            
            elif position_side == -1:
                # SHORT exit conditions
                sl = min(entry_price * 1.02, high[entry_bar])
                if high[i] >= sl:
                    exit_signal = True
                if low[i] <= entry_price * 0.96:
                    exit_signal = True
                if rsi[i] < 30:
                    exit_signal = True
                if i > 0 and macd_line[i-1] < macd_signal[i-1] and macd_line[i] >= macd_signal[i]:
                    exit_signal = True
                if high[i] > high[entry_bar]:
                    exit_signal = True
                if i - entry_bar >= 5:
                    exit_signal = True
            
            if exit_signal:
                in_position = False
                signals[i] = 0
            else:
                signals[i] = position_side
        
        else:
            if i < 26:
                signals[i] = 0
                continue
            
            prev_low = np.min(low[max(0, i-10):i])
            prev_high = np.max(high[max(0, i-10):i])
            
            # LONG entry
            if (rsi[i] < 30 and 
                volume[i] > volume_ma[i] and
                i > 0 and macd_hist[i] > macd_hist[i-1] and
                close[i] > prev_low):
                in_position = True
                position_side = 1
                entry_price = close[i]
                entry_bar = i
                signals[i] = 1
            
            # SHORT entry
            elif (rsi[i] > 70 and 
                  volume[i] > volume_ma[i] and
                  i > 0 and macd_hist[i] < macd_hist[i-1] and
                  close[i] < prev_high):
                in_position = True
                position_side = -1
                entry_price = close[i]
                entry_bar = i
                signals[i] = -1
            
            else:
                signals[i] = 0
    
    return pd.Series(signals, index=bars.index)
