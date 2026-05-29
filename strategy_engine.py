import pandas as pd
import numpy as np
from config import config

class StrategyEngine:
    def __init__(self):
        self.rsi_length = config.RSI_LENGTH
        self.ema_length = config.EMA_LENGTH

    def apply_indicators(self, df):
        """Calculates indicators needed for the strategy."""
        # Calculate EMA
        df['EMA'] = df['close'].ewm(span=self.ema_length, adjust=False).mean()

        # Calculate RSI (Wilder's Smoothing)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Wilder's exponential smoothing uses alpha = 1 / length
        avg_gain = gain.ewm(alpha=1/self.rsi_length, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/self.rsi_length, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df

    def is_swing_low(self, df, index, window=5):
        if index < window or index >= len(df) - window:
            return False
        current_low = df['low'].iloc[index]
        for i in range(1, window + 1):
            if df['low'].iloc[index - i] < current_low or df['low'].iloc[index + i] < current_low:
                return False
        return True

    def is_swing_high(self, df, index, window=5):
        if index < window or index >= len(df) - window:
            return False
        current_high = df['high'].iloc[index]
        for i in range(1, window + 1):
            if df['high'].iloc[index - i] > current_high or df['high'].iloc[index + i] > current_high:
                return False
        return True

    def detect_bullish_divergence(self, df, window=5):
        """Scan for bullish divergence (LONG). Returns dict or None."""
        swing_lows = []
        for i in range(window, len(df) - window):
            if self.is_swing_low(df, i, window):
                swing_lows.append(i)
                
        if len(swing_lows) < 2:
            return None

        idx2 = swing_lows[-1]
        idx1 = swing_lows[-2]

        p1, p2 = df['low'].iloc[idx1], df['low'].iloc[idx2]
        rsi1, rsi2 = df['RSI'].iloc[idx1], df['RSI'].iloc[idx2]

        # Rule 1: Price forms a lower low
        if p2 < p1:
            # Rule 2: RSI forms a higher low
            if rsi2 > rsi1:
                # Rule 3: First RSI low MUST be in oversold region (<= 30)
                if rsi1 <= 30:
                    return {
                        'type': 'long',
                        'idx1': idx1, 'idx2': idx2,
                        'p1': p1, 'p2': p2,
                        'rsi1': rsi1, 'rsi2': rsi2
                    }
        return None

    def detect_bearish_divergence(self, df, window=5):
        """Scan for bearish divergence (SHORT). Returns dict or None."""
        swing_highs = []
        for i in range(window, len(df) - window):
            if self.is_swing_high(df, i, window):
                swing_highs.append(i)
                
        if len(swing_highs) < 2:
            return None

        idx2 = swing_highs[-1]
        idx1 = swing_highs[-2]

        p1, p2 = df['high'].iloc[idx1], df['high'].iloc[idx2]
        rsi1, rsi2 = df['RSI'].iloc[idx1], df['RSI'].iloc[idx2]

        # Rule 1: Price forms a higher high
        if p2 > p1:
            # Rule 2: RSI forms a lower high
            if rsi2 < rsi1:
                # Rule 3: First RSI high MUST be in overbought region (>= 70)
                if rsi1 >= 70:
                    return {
                        'type': 'short',
                        'idx1': idx1, 'idx2': idx2,
                        'p1': p1, 'p2': p2,
                        'rsi1': rsi1, 'rsi2': rsi2
                    }
        return None

    def analyze(self, df, symbol):
        """
        Applies logic and filters. 
        Returns (signal_dict, message) where signal_dict is not None if valid.
        """
        df = self.apply_indicators(df)
        
        if len(df) < self.ema_length and config.USE_EMA_FILTER:
            return None, f"Not enough data for {self.ema_length} EMA."

        current_close = df['close'].iloc[-1]
        current_ema = df['EMA'].iloc[-1] if 'EMA' in df.columns else None
        
        # Check Long Signal
        long_signal = self.detect_bullish_divergence(df)
        if long_signal:
            detection_edge = len(df) - 1 - 5 
            if long_signal['idx2'] >= detection_edge - 2:
                # Trend filter for Long: price shouldn't be too far below EMA
                if config.USE_EMA_FILTER and current_ema:
                    buffer_threshold = 0.05
                    if current_close < current_ema * (1 - buffer_threshold):
                        return None, f"سیگنال Long نادیده گرفته شد: قیمت ({current_close}) فاصله زیادی با میانگین متحرک 200 روزه ({current_ema:.4f}) دارد."
                return long_signal, "✅ واگرایی مثبت تایید شد!"

        # Check Short Signal
        short_signal = self.detect_bearish_divergence(df)
        if short_signal:
            detection_edge = len(df) - 1 - 5 
            if short_signal['idx2'] >= detection_edge - 2:
                # Trend filter for Short: price shouldn't be too far above EMA
                if config.USE_EMA_FILTER and current_ema:
                    buffer_threshold = 0.05
                    if current_close > current_ema * (1 + buffer_threshold):
                        return None, f"سیگنال Short نادیده گرفته شد: قیمت ({current_close}) فاصله زیادی با میانگین متحرک 200 روزه ({current_ema:.4f}) دارد."
                return short_signal, "✅ واگرایی منفی تایید شد!"

        return None, "سیگنال فعالی یافت نشد."
