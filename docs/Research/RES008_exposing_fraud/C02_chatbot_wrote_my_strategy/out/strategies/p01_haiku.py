import numpy as np
import pandas as pd

def signal(bars: pd.DataFrame) -> pd.Series:
    # Calculate technical indicators
    ema_9 = bars['close'].ewm(span=9, adjust=False).mean()
    ema_21 = bars['close'].ewm(span=21, adjust=False).mean()
    
    # RSI calculation
    delta = bars['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=14, adjust=False).mean()
    avg_loss = loss.ewm(span=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Track positions
    positions = np.zeros(len(bars), dtype=int)
    entry_price = np.nan
    
    for i in range(len(bars)):
        current_price = bars['close'].iloc[i]
        in_position = not np.isnan(entry_price)
        
        if in_position:
            # Exit conditions
            stop_loss = entry_price * 0.98
            take_profit = entry_price * 1.02
            
            if (current_price <= stop_loss or 
                current_price >= take_profit or 
                ema_9.iloc[i] < ema_21.iloc[i] or 
                rsi.iloc[i] > 80):
                positions[i] = 0
                entry_price = np.nan
            else:
                positions[i] = 1
        else:
            # Entry conditions
            if (pd.notna(ema_9.iloc[i]) and 
                pd.notna(ema_21.iloc[i]) and 
                pd.notna(rsi.iloc[i]) and
                ema_9.iloc[i] > ema_21.iloc[i] and
                40 < rsi.iloc[i] < 70 and
                current_price > ema_9.iloc[i]):
                positions[i] = 1
                entry_price = current_price
            else:
                positions[i] = 0
    
    return pd.Series(positions, index=bars.index)
