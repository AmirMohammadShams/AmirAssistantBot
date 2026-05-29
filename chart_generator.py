import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import os

def generate_divergence_chart(symbol, timeframe, df, signal_info):
    """
    Generates a dark-themed TradingView-style chart with Price and RSI,
    drawing lines to highlight the divergence.
    """
    try:
        # Keep only the last 150 candles for better visibility
        idx1 = signal_info['idx1']
        idx2 = signal_info['idx2']
        p1 = signal_info['p1']
        p2 = signal_info['p2']
        rsi1 = signal_info['rsi1']
        rsi2 = signal_info['rsi2']
        
        if len(df) <= idx1 or len(df) <= idx2:
            return None # Should not happen if df is the original one
            
        t1 = df.index[idx1]
        t2 = df.index[idx2]
        
        # Now we can safely slice
        limit = 150
        if len(df) > limit:
            df_plot = df.iloc[-limit:].copy()
        else:
            df_plot = df.copy()
            
        # Ensure t1 and t2 are in df_plot
        if t1 not in df_plot.index or t2 not in df_plot.index:
            # If the divergence happened too far in the past, don't plot or plot the whole thing
            df_plot = df.copy()

        # Create figure and subplots
        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]})
        fig.suptitle(f"{symbol} ({timeframe}) - {'Bullish' if signal_info['type'] == 'long' else 'Bearish'} Divergence", fontsize=16, color='white')

        # Plot Candlesticks on ax1
        up = df_plot[df_plot['close'] >= df_plot['open']]
        down = df_plot[df_plot['close'] < df_plot['open']]

        col_up = '#089981' # TradingView Green
        col_down = '#F23645' # TradingView Red

        # Plot wicks
        ax1.vlines(up.index, up['low'], up['high'], color=col_up, linewidth=1)
        ax1.vlines(down.index, down['low'], down['high'], color=col_down, linewidth=1)

        # Plot bodies
        width = 0.6
        ax1.bar(up.index, up['close'] - up['open'], width, bottom=up['open'], color=col_up)
        ax1.bar(down.index, down['open'] - down['close'], width, bottom=down['close'], color=col_down)

        # Draw Divergence Line on Price
        ax1.plot([t1, t2], [p1, p2], color='#FFeb3b', linewidth=2, marker='o')
        ax1.set_ylabel('Price (USDT)')
        ax1.grid(color='#2A2E39', linestyle='--', linewidth=0.5)

        # Plot RSI on ax2
        if 'RSI_14' in df_plot.columns:
            ax2.plot(df_plot.index, df_plot['RSI_14'], color='#00BCD4', linewidth=1.5, label='RSI (14)')
        else:
            # Try to find any RSI column
            rsi_col = next((col for col in df_plot.columns if 'RSI' in col), None)
            if rsi_col:
                ax2.plot(df_plot.index, df_plot[rsi_col], color='#00BCD4', linewidth=1.5, label=rsi_col)

        # Draw Divergence Line on RSI
        ax2.plot([t1, t2], [rsi1, rsi2], color='#FFeb3b', linewidth=3, marker='o')
        
        # Draw 30 and 70 lines for RSI
        ax2.axhline(70, color='#FF5252', linestyle='--', alpha=0.5)
        ax2.axhline(30, color='#4CAF50', linestyle='--', alpha=0.5)
        ax2.set_ylabel('RSI')
        ax2.set_ylim(0, 100)
        ax2.grid(color='#2A2E39', linestyle='--', linewidth=0.5)

        # Formatting X axis
        for ax in [ax1, ax2]:
            ax.tick_params(colors='gray')
            for spine in ax.spines.values():
                spine.set_color('#2A2E39')

        fig.tight_layout()
        
        # Save to file
        os.makedirs('charts', exist_ok=True)
        filename = f"charts/{symbol.replace('/', '_').replace(':', '_')}_{timeframe}_{int(datetime.now().timestamp())}.png"
        plt.savefig(filename, facecolor='#131722', edgecolor='none')
        plt.close()
        
        return filename

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to generate chart for {symbol}: {e}")
        return None
