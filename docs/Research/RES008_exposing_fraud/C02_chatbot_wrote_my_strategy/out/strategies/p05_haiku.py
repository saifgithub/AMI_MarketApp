import pandas
import numpy

def signal(bars: pandas.DataFrame) -> pandas.Series:
    lookback = 20
    entry_z_threshold = 2.0
    stop_z_threshold = 3.0
    time_stop_bars = 20
    
    # Pre-calculate rolling SMA and std
    sma = bars['close'].rolling(window=lookback).mean()
    std = bars['close'].rolling(window=lookback).std()
    
    signals = numpy.zeros(len(bars), dtype=int)
    position = 0
    entry_bar = None
    
    for i in range(len(bars)):
        # Skip bars without enough data
        if pandas.isna(sma.iloc[i]) or pandas.isna(std.iloc[i]):
            signals[i] = 0
            continue
        
        current_price = bars['close'].iloc[i]
        current_sma = sma.iloc[i]
        current_std = std.iloc[i]
        
        # Calculate Z-score
        z_score = (current_price - current_sma) / current_std if current_std > 0 else 0
        
        # Check exit conditions first
        if position != 0:
            exit_signal = False
            
            # Time stop
            if i - entry_bar >= time_stop_bars:
                exit_signal = True
            # Profit target at mean
            elif position == 1 and current_price >= current_sma:
                exit_signal = True
            elif position == -1 and current_price <= current_sma:
                exit_signal = True
            # Stop loss
            elif position == 1 and z_score <= -stop_z_threshold:
                exit_signal = True
            elif position == -1 and z_score >= stop_z_threshold:
                exit_signal = True
            
            if exit_signal:
                position = 0
                entry_bar = None
        
        # Check entry conditions if flat
        if position == 0:
            if z_score < -entry_z_threshold:
                position = 1
                entry_bar = i
            elif z_score > entry_z_threshold:
                position = -1
                entry_bar = i
        
        signals[i] = position
    
    return pandas.Series(signals, index=bars.index)
