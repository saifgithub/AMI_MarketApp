import numpy as np
import pandas as pd

def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars['close']
    high = bars['high']
    low = bars['low']
    n = len(bars)
    
    # Calculate ATR
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(10).mean()
    
    # Calculate SuperTrend
    hl = (high + low) / 2
    basic_ub = hl + 3.0 * atr
    basic_lb = hl - 3.0 * atr
    
    final_ub = np.full(n, np.nan)
    final_lb = np.full(n, np.nan)
    st_signal = np.full(n, np.nan)
    
    for i in range(10, n):
        if i == 10:
            final_ub[i] = basic_ub.iloc[i]
            final_lb[i] = basic_lb.iloc[i]
        else:
            final_ub[i] = basic_ub.iloc[i] if basic_ub.iloc[i] < final_ub[i-1] or high.iloc[i-1] > final_ub[i-1] else final_ub[i-1]
            final_lb[i] = basic_lb.iloc[i] if basic_lb.iloc[i] > final_lb[i-1] or low.iloc[i-1] < final_lb[i-1] else final_lb[i-1]
        
        if i == 10:
            st_signal[i] = -1.0 if close.iloc[i] <= final_ub[i] else 1.0
        else:
            if st_signal[i-1] == -1.0:
                st_signal[i] = -1.0 if close.iloc[i] <= final_ub[i] else 1.0
            else:
                st_signal[i] = 1.0 if close.iloc[i] >= final_lb[i] else -1.0
    
    # Calculate RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Calculate ADX
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    
    for i in range(1, n):
        up = high.iloc[i] - high.iloc[i-1]
        down = low.iloc[i-1] - low.iloc[i]
        plus_dm[i] = max(up, 0) if up > down else 0
        minus_dm[i] = max(down, 0) if down > up else 0
    
    tr_sum = tr.rolling(14).sum()
    plus_di = 100 * pd.Series(plus_dm).rolling(14).sum() / tr_sum
    minus_di = 100 * pd.Series(minus_dm).rolling(14).sum() / tr_sum
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(14).mean()
    
    # Position tracking
    positions = np.zeros(n)
    position = 0
    entry_price = None
    entry_idx = None
    
    for i in range(28, n):
        should_exit = False
        
        if position != 0:
            # SuperTrend reversal
            if not np.isnan(st_signal[i]):
                if (position == 1 and st_signal[i] == -1.0) or (position == -1 and st_signal[i] == 1.0):
                    should_exit = True
            
            # ADX drops below 20
            if not np.isnan(adx.iloc[i]) and adx.iloc[i] < 20:
                should_exit = True
            
            # Take profit at 2.5x risk
            if entry_price is not None and not np.isnan(final_ub[entry_idx]) and not np.isnan(final_lb[entry_idx]):
                if position == 1:
                    risk = entry_price - final_lb[entry_idx]
                    if close.iloc[i] >= entry_price + 2.5 * risk:
                        should_exit = True
                elif position == -1:
                    risk = final_ub[entry_idx] - entry_price
                    if close.iloc[i] <= entry_price - 2.5 * risk:
                        should_exit = True
        
        if should_exit:
            position = 0
            entry_price = None
            entry_idx = None
        
        # Entry conditions
        if position == 0:
            if not np.isnan(st_signal[i]) and not np.isnan(rsi.iloc[i]) and not np.isnan(adx.iloc[i]):
                # Long entry
                if adx.iloc[i] > 25 and st_signal[i] == 1.0 and 30 <= rsi.iloc[i] <= 70 and rsi.iloc[i] > 50:
                    position = 1
                    entry_price = close.iloc[i]
                    entry_idx = i
                # Short entry
                elif adx.iloc[i] > 25 and st_signal[i] == -1.0 and 30 <= rsi.iloc[i] <= 70 and rsi.iloc[i] < 50:
                    position = -1
                    entry_price = close.iloc[i]
                    entry_idx = i
        
        positions[i] = position
    
    return pd.Series(positions, index=bars.index)
