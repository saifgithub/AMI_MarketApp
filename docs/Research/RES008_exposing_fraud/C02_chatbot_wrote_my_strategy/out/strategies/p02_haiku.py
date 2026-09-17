import numpy as np
import pandas as pd

def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars['close'].values
    sma50 = pd.Series(close).rolling(window=50).mean().values
    
    position = np.zeros(len(bars))
    entry_price = None
    
    for i in range(len(bars)):
        if np.isnan(sma50[i]):
            position[i] = 0
            continue
        
        prev_position = position[i-1] if i > 0 else 0
        
        if prev_position == 0:
            # Entry signal
            if close[i] > sma50[i]:
                position[i] = 1
                entry_price = close[i]
            else:
                position[i] = 0
        else:
            # Exit signal: close < SMA or hit 2% stop loss
            if close[i] < sma50[i] or close[i] < entry_price * 0.98:
                position[i] = 0
                entry_price = None
            else:
                position[i] = 1
    
    return pd.Series(position, index=bars.index)
