import pandas
import numpy as np

def signal(bars: pandas.DataFrame) -> pandas.Series:
    signals = pandas.Series(0, index=bars.index, dtype=int)
    
    # Calculate moving averages
    sma10 = bars['close'].rolling(window=10).mean()
    sma20 = bars['close'].rolling(window=20).mean()
    
    # Calculate volume average
    vol_avg = bars['volume'].rolling(window=20).mean()
    
    # Track position state
    position = 0
    entry_price = None
    peak_price = None
    
    for i in range(len(bars)):
        current_close = bars['close'].iloc[i]
        current_high = bars['high'].iloc[i]
        current_low = bars['low'].iloc[i]
        current_volume = bars['volume'].iloc[i]
        
        ma10 = sma10.iloc[i]
        ma20 = sma20.iloc[i]
        vol_avg_val = vol_avg.iloc[i]
        
        if pandas.isna(ma10) or pandas.isna(ma20) or pandas.isna(vol_avg_val):
            signals.iloc[i] = position
            continue
        
        # Exit logic for long positions
        if position == 1:
            exit_signal = False
            
            if current_low <= entry_price - 0.0020:  # Stop loss: 20 pips
                exit_signal = True
            elif current_high >= entry_price + 0.0040:  # Take profit: 40 pips (1:2 RR)
                exit_signal = True
            elif peak_price >= entry_price + 0.0030 and current_low <= peak_price - 0.0010:  # Trailing stop
                exit_signal = True
            elif i > 0 and sma10.iloc[i-1] > sma20.iloc[i-1] and ma10 <= ma20:  # MA crossover
                exit_signal = True
            
            if exit_signal:
                position = 0
                entry_price = None
                peak_price = None
            else:
                peak_price = max(peak_price, current_high)
        
        # Exit logic for short positions
        elif position == -1:
            exit_signal = False
            
            if current_high >= entry_price + 0.0020:  # Stop loss: 20 pips
                exit_signal = True
            elif current_low <= entry_price - 0.0040:  # Take profit: 40 pips (1:2 RR)
                exit_signal = True
            elif peak_price <= entry_price - 0.0030 and current_high >= peak_price + 0.0010:  # Trailing stop
                exit_signal = True
            elif i > 0 and sma10.iloc[i-1] < sma20.iloc[i-1] and ma10 >= ma20:  # MA crossover
                exit_signal = True
            
            if exit_signal:
                position = 0
                entry_price = None
                peak_price = None
            else:
                peak_price = min(peak_price, current_low)
        
        # Entry logic
        if position == 0 and i > 0:
            prev_ma10 = sma10.iloc[i-1]
            prev_ma20 = sma20.iloc[i-1]
            
            # Long entry: MA10 crosses above MA20
            if prev_ma10 <= prev_ma20 and ma10 > ma20:
                if current_close > ma10 and current_close > ma20:
                    if current_volume > vol_avg_val:
                        position = 1
                        entry_price = current_close
                        peak_price = current_high
            
            # Short entry: MA10 crosses below MA20
            elif prev_ma10 >= prev_ma20 and ma10 < ma20:
                if current_close < ma10 and current_close < ma20:
                    if current_volume > vol_avg_val:
                        position = -1
                        entry_price = current_close
                        peak_price = current_low
        
        signals.iloc[i] = position
    
    return signals
