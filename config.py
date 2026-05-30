import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    EXCHANGE_ID = os.getenv('EXCHANGE_ID', 'binance').lower()
    API_KEY = os.getenv('API_KEY', '')
    API_SECRET = os.getenv('API_SECRET', '')
    TESTNET = os.getenv('TESTNET', 'true').lower() == 'true'
    
    SCAN_ALL_FUTURES = os.getenv('SCAN_ALL_FUTURES', 'true').lower() == 'true'
    
    # Generate list from ENV or fallback (used only if SCAN_ALL_FUTURES is false)
    fallback_pairs = "BTC/USDT,ETH/USDT,SOL/USDT"
    TRADING_PAIRS = [p.strip() for p in os.getenv('TRADING_PAIRS', fallback_pairs).split(',')]
    
    # Forex & local symbols
    fallback_forex = "EURUSD=X,GBPUSD=X,JPY=X,GC=F" # GC=F is Gold Futures on Yahoo, or XAUUSD=X if available. We'll use popular Yahoo tickers.
    FOREX_PAIRS = [p.strip() for p in os.getenv('FOREX_PAIRS', fallback_forex).split(',') if p.strip()]
    
    fallback_nobitex = "USDTIRT"
    NOBITEX_PAIRS = [p.strip() for p in os.getenv('NOBITEX_PAIRS', fallback_nobitex).split(',') if p.strip()]
    
    RISK_PERCENTAGE = float(os.getenv('RISK_PERCENTAGE', '1.0')) / 100.0
    LEVERAGE = int(os.getenv('LEVERAGE', '5'))
    MARGIN_TYPE = os.getenv('MARGIN_TYPE', 'isolated').lower()
    
    USE_EMA_FILTER = os.getenv('USE_EMA_FILTER', 'true').lower() == 'true'
    
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
    LOG_BOT_TOKEN = os.getenv('LOG_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    
    HTTP_PROXY = os.getenv('HTTP_PROXY', '')

    # Strategy Parameters
    CANDLE_LIMIT = 250
    RSI_LENGTH = 14
    EMA_LENGTH = 200

config = Config()
