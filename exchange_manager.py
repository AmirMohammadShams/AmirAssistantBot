import ccxt
import pandas as pd
import logging
import requests
import yfinance as yf
from datetime import datetime, timedelta
import logging
from config import config

logger = logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self):
        self.exchange = self._init_exchange()

    def _init_exchange(self):
        exchange_config = {
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            }
        }
        if config.HTTP_PROXY:
            exchange_config['proxies'] = {
                'http': config.HTTP_PROXY,
                'https': config.HTTP_PROXY
            }

        exchange_class = getattr(ccxt, config.EXCHANGE_ID)
        exchange = exchange_class(exchange_config)
        
        if config.TESTNET:
            exchange.set_sandbox_mode(True)
            logger.info(f"Initialized {config.EXCHANGE_ID.capitalize()} in TESTNET mode.")
        else:
            logger.info(f"Initialized {config.EXCHANGE_ID.capitalize()} in LIVE mode.")
            
        return exchange

    def set_leverage_and_margin(self, symbol):
        """Sets leverage and margin mode for a symbol."""
        if not config.API_KEY: return
        try:
            self.exchange.load_markets()
            market = self.exchange.market(symbol)
            
            # Set Margin Mode
            try:
                self.exchange.set_margin_mode(config.MARGIN_TYPE, symbol)
            except Exception as e:
                # Some exchanges/symbols don't support changing margin type if already set
                pass
                
            # Set Leverage
            try:
                self.exchange.set_leverage(config.LEVERAGE, symbol)
            except Exception as e:
                pass
        except Exception as e:
            logger.error(f"Error setting leverage for {symbol}: {e}")

    def fetch_ohlcv(self, symbol, timeframe, provider='crypto'):
        """Fetches OHLCV data from the specified provider and returns a DataFrame."""
        try:
            if provider == 'crypto':
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=config.CANDLE_LIMIT)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
                
            elif provider == 'forex':
                # Map timeframe to yfinance
                interval_map = {'1h': '1h', '4h': '1h', '1d': '1d', '1w': '1wk'}
                yf_interval = interval_map.get(timeframe, '1h')
                
                df = yf.download(tickers=symbol, interval=yf_interval, period="1mo", progress=False)
                if df.empty:
                    return None
                    
                # yfinance returns MultiIndex columns if single ticker sometimes, or just capitalized columns
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                
                df = df.reset_index()
                # Rename columns
                df = df.rename(columns={'Datetime': 'timestamp', 'Date': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
                
                # Manual 4H resampling since yf doesn't support 4h directly
                if timeframe == '4h':
                    df.set_index('timestamp', inplace=True)
                    df = df.resample('4h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index()
                
                # Keep last CANDLE_LIMIT rows
                return df.tail(config.CANDLE_LIMIT)
                
            elif provider == 'nobitex':
                # Nobitex API UDF History
                res_map = {'1h': '60', '4h': '240', '1d': '1D', '1w': '1W'}
                res = res_map.get(timeframe, '60')
                
                to_time = int(datetime.now().timestamp())
                # estimate from_time to get CANDLE_LIMIT candles
                mins = 60 if timeframe == '1h' else 240 if timeframe == '4h' else 1440 if timeframe == '1d' else 10080
                from_time = to_time - (mins * 60 * (config.CANDLE_LIMIT + 10))
                
                url = f"https://api.nobitex.ir/market/udf/history?symbol={symbol}&resolution={res}&from={from_time}&to={to_time}"
                resp = requests.get(url, timeout=10)
                data = resp.json()
                if data.get('s') != 'ok':
                    return None
                
                df = pd.DataFrame({
                    'timestamp': pd.to_datetime(data['t'], unit='s'),
                    'open': data['o'],
                    'high': data['h'],
                    'low': data['l'],
                    'close': data['c'],
                    'volume': data['v']
                })
                return df.tail(config.CANDLE_LIMIT)
                
        except Exception as e:
            logger.error(f"Error fetching data for {symbol} ({provider}): {e}")
            return None

    def get_all_futures_symbols(self):
        """Fetches all active USDT-margined perpetual futures."""
        try:
            self.exchange.load_markets()
            markets = self.exchange.markets
            
            symbols = []
            for symbol, market in markets.items():
                if market.get('active') and market.get('swap') and market.get('quote') == 'USDT':
                    symbols.append(symbol)
            return symbols
        except Exception as e:
            logger.error(f"Error fetching futures symbols: {e}")
            return []

    def get_active_positions(self):
        """Returns a list of active positions."""
        if not config.API_KEY: return []
        try:
            positions = self.exchange.fetch_positions()
            active = [p for p in positions if float(p.get('contracts', 0)) > 0]
            return active
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def has_open_position(self, symbol):
        """Checks if a specific symbol has an open position."""
        if not config.API_KEY: return False
        positions = self.get_active_positions()
        for p in positions:
            if p['symbol'] == symbol:
                return True
        return False

    def execute_trade(self, symbol, signal_dict):
        """Calculates size and executes Long or Short."""
        trade_type = signal_dict.get('type', 'unknown')
        if self.has_open_position(symbol):
            logger.info(f"{symbol}: Already have an open position. Skipping.")
            return

        try:
            self.set_leverage_and_margin(symbol)
            
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # Simulated balance if no API key
            total_equity = 1000.0
            if config.API_KEY and config.API_SECRET:
                balance = self.exchange.fetch_balance()
                quote_currency = symbol.split('/')[1].split(':')[0] if ':' in symbol else symbol.split('/')[1]
                if quote_currency in balance['total']:
                    total_equity = float(balance['total'][quote_currency])
                
            p2 = signal_dict['p2']
            sl_buffer = 0.002 # 0.2%
            
            if trade_type == 'long':
                sl_price = p2 * (1 - sl_buffer)
                if sl_price >= current_price: return
                risk_per_coin = current_price - sl_price
                tp_price = current_price + (risk_per_coin * 1.5)
                side = 'buy'
                sl_side = 'sell'
            else: # short
                sl_price = p2 * (1 + sl_buffer)
                if sl_price <= current_price: return
                risk_per_coin = sl_price - current_price
                tp_price = current_price - (risk_per_coin * 1.5)
                side = 'sell'
                sl_side = 'buy'

            amount_to_risk = total_equity * config.RISK_PERCENTAGE
            position_size = amount_to_risk / risk_per_coin
            
            # Apply precision
            self.exchange.load_markets()
            position_size = self.exchange.amount_to_precision(symbol, position_size)
            sl_price = self.exchange.price_to_precision(symbol, sl_price)
            tp_price = self.exchange.price_to_precision(symbol, tp_price)

            logger.info(f"{symbol} [{trade_type.upper()}]: Entry ~{current_price}, SL: {sl_price}, TP: {tp_price}, Size: {position_size}")

            logger.info(f"{symbol}: Signal Only Mode. Simulated {trade_type.upper()} logged.")
            return

        except Exception as e:
            logger.error(f"Error executing {trade_type} for {symbol}: {e}")

    def emergency_close_all(self):
        """Closes all open positions immediately."""
        if not config.API_KEY: return "No API Key configured. Cannot close positions."
        try:
            positions = self.get_active_positions()
            if not positions:
                return "No active positions to close."
            
            count = 0
            for p in positions:
                symbol = p['symbol']
                size = float(p['contracts'])
                side = 'sell' if p['side'] == 'long' else 'buy'
                
                # Close position
                self.exchange.create_order(symbol, 'market', side, size, params={'reduceOnly': True})
                
                # Cancel open orders (SL/TP)
                self.exchange.cancel_all_orders(symbol)
                count += 1
            return f"Successfully closed {count} positions and cancelled their orders."
        except Exception as e:
            logger.error(f"Emergency close failed: {e}")
            return f"Error during emergency close: {e}"
