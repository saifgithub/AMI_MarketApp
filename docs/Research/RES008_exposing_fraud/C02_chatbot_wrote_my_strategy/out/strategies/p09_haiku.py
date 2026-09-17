import pandas as pd
import numpy as np

def signal(bars: pd.DataFrame) -> pd.Series:
    close = bars['close']
    
    # Calculate moving averages
    sma_50 = close.rolling(window=50).mean()
    sma_200 = close.rolling(window=200).mean()
    
    # Generate signals: 1 when 50 > 200, 0 otherwise
    signals = pd.Series(0, index=bars.index, dtype=int)
    signals[sma_50 > sma_200] = 1
    
    return signals
