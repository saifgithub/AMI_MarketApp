import numpy as np
import pandas as pd

def signal(bars: pd.DataFrame) -> pd.Series:
    """
    VWAP Crossover Strategy
    - Buy when price crosses above 30-period VWAP
    - Sell when position gains 3% or loses 1%
    - Short when price crosses below VWAP
    """
    
    position = pd.Series(0, index=bars.index, dtype=int)
    
    # Calculate 30-period VWAP
    tp = (bars['high'] + bars['low'] + bars['close']) / 3
    vwap = (tp * bars['volume']).rolling(window=30).sum() / bars['volume'].rolling(window=30).sum()
    
    entry_price = 0.0
    current_position = 0
    
    for i in range(len(bars)):
        close = bars['close'].iloc[i]
        vwap_val = vwap.iloc[i]
        
        # Exit conditions for open positions
        if current_position == 1:  # Long position
            if close >= entry_price * 1.03 or close <= entry_price * 0.99:
                current_position = 0
                entry_price = 0.0
        
        elif current_position == -1:  # Short position
            if close <= entry_price * 0.97 or close >= entry_price * 1.01:
                current_position = 0
                entry_price = 0.0
        
        # Entry conditions when flat
        if current_position == 0 and i > 0 and not pd.isna(vwap_val):
            prev_close = bars['close'].iloc[i-1]
            prev_vwap = vwap.iloc[i-1]
            
            # Crossover: long entry
            if prev_close <= prev_vwap and close > vwap_val:
                current_position = 1
                entry_price = close
            
            # Crossunder: short entry
            elif prev_close >= prev_vwap and close < vwap_val:
                current_position = -1
                entry_price = close
        
        position.iloc[i] = current_position
    
    return position
