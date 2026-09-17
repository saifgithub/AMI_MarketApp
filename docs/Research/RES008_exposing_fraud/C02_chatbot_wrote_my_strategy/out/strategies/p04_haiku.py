def signal(bars: pandas.DataFrame) -> pandas.Series:
    import pandas as pd
    import numpy as np
    
    close = bars['close'].values
    high = bars['high'].values
    low = bars['low'].values
    volume = bars['volume'].values
    
    ema20 = pd.Series(close).ewm(span=20, adjust=False).mean().values
    
    delta = np.diff(close, prepend=close[0])
    delta[0] = 0
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).ewm(span=14, adjust=False).mean().values
    avg_loss = pd.Series(loss).ewm(span=14, adjust=False).mean().values
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd_line = ema12 - ema26
    signal_line = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    macd_hist = macd_line - signal_line
    
    volume_ma = pd.Series(volume).rolling(window=20).mean().values
    
    signals = pd.Series(0, index=bars.index, dtype=int)
    position = 0
    entry_price = None
    entry_bar = None
    pos_type = None
    
    for i in range(len(bars)):
        if position != 0:
            if pos_type == 'long':
                if low[i] < entry_price * 0.985:
                    position, entry_price, entry_bar, pos_type = 0, None, None, None
                    signals.iloc[i] = 0
                    continue
                if high[i] > entry_price * 1.03:
                    position, entry_price, entry_bar, pos_type = 0, None, None, None
                    signals.iloc[i] = 0
                    continue
            else:
                if high[i] > entry_price * 1.015:
                    position, entry_price, entry_bar, pos_type = 0, None, None, None
                    signals.iloc[i] = 0
                    continue
                if low[i] < entry_price * 0.97:
                    position, entry_price, entry_bar, pos_type = 0, None, None, None
                    signals.iloc[i] = 0
                    continue
            
            if i - entry_bar >= 5:
                position, entry_price, entry_bar, pos_type = 0, None, None, None
                signals.iloc[i] = 0
                continue
            
            signals.iloc[i] = position
            continue
        
        if i < 26:
            signals.iloc[i] = 0
            continue
        
        vol_ok = not np.isnan(volume_ma[i]) and volume[i] > volume_ma[i]
        
        if (close[i] > ema20[i] and
            40 < rsi[i] < 60 and
            macd_hist[i] > 0 and
            macd_hist[i-1] <= 0 and
            vol_ok):
            position = 1
            entry_price = close[i]
            entry_bar = i
            pos_type = 'long'
            signals.iloc[i] = 1
        
        elif (close[i] < ema20[i] and
              40 < rsi[i] < 60 and
              macd_hist[i] < 0 and
              macd_hist[i-1] >= 0 and
              vol_ok):
            position = -1
            entry_price = close[i]
            entry_bar = i
            pos_type = 'short'
            signals.iloc[i] = -1
        
        else:
            signals.iloc[i] = 0
    
    return signals
