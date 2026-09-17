import pandas as pd
import numpy as np

def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars['close'].values
    sma_20 = bars['close'].rolling(window=20).mean().values
    sma_50 = bars['close'].rolling(window=50).mean().values
    
    position = np.zeros(len(bars), dtype=int)
    entry_price = None
    current_pos = 0
    
    stop_loss_pct = 0.025
    profit_target_pct = 0.05
    
    for i in range(len(bars)):
        # Exit on stop loss or profit target
        if current_pos != 0 and entry_price is not None:
            if current_pos == 1:
                if close[i] <= entry_price * (1 - stop_loss_pct) or \
                   close[i] >= entry_price * (1 + profit_target_pct):
                    current_pos = 0
                    entry_price = None
            else:
                if close[i] >= entry_price * (1 + stop_loss_pct) or \
                   close[i] <= entry_price * (1 - profit_target_pct):
                    current_pos = 0
                    entry_price = None
        
        # Entry signals
        if current_pos == 0 and not np.isnan(sma_20[i]) and not np.isnan(sma_50[i]):
            if sma_20[i] > sma_50[i]:
                current_pos = 1
                entry_price = close[i]
            elif sma_20[i] < sma_50[i]:
                current_pos = -1
                entry_price = close[i]
        
        position[i] = current_pos
    
    return pd.Series(position, index=bars.index)
