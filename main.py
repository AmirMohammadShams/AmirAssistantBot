import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import config
from exchange_manager import ExchangeManager
from strategy_engine import StrategyEngine
import telegram_interface

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize components
exchange_mgr = ExchangeManager()
strategy_engine = StrategyEngine()

# Wire Telegram
telegram_interface.set_exchange_manager(exchange_mgr)
tg_app = telegram_interface.get_telegram_app()

import admin_manager

async def notify_telegram(message, photo_path=None):
    if not tg_app:
        return
        
    admins = admin_manager.get_all_admins()
    for chat_id in admins:
        if not chat_id:
            continue
        try:
            if photo_path:
                with open(photo_path, 'rb') as photo:
                    await tg_app.bot.send_photo(chat_id=chat_id, photo=photo, caption=message, parse_mode="Markdown")
            else:
                await tg_app.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send telegram notification to {chat_id}: {e}")

async def analyze_timeframe(timeframe):
    logger.info(f"Starting {timeframe} market analysis...")
    
    # 1. Crypto Futures
    if config.SCAN_ALL_FUTURES:
        crypto_pairs = exchange_mgr.get_all_futures_symbols()
        if not crypto_pairs: # Fallback
            crypto_pairs = config.TRADING_PAIRS
    else:
        crypto_pairs = config.TRADING_PAIRS
        
    # 2. Forex Pairs
    forex_pairs = config.FOREX_PAIRS
    
    # 3. Nobitex Pairs
    nobitex_pairs = config.NOBITEX_PAIRS
    
    all_tasks = []
    for p in crypto_pairs: all_tasks.append((p, 'crypto'))
    for p in forex_pairs: all_tasks.append((p, 'forex'))
    for p in nobitex_pairs: all_tasks.append((p, 'nobitex'))
    
    logger.info(f"Total symbols to scan for {timeframe}: {len(all_tasks)}")
    
    batch_size = 10
    delay_between_batches = 1.0 # 1 second delay between batches to avoid rate limit
    
    for i in range(0, len(all_tasks), batch_size):
        batch = all_tasks[i:i+batch_size]
        
        for symbol, provider in batch:
            try:
                df = exchange_mgr.fetch_ohlcv(symbol, timeframe, provider=provider)
                if df is None or df.empty:
                    continue
                    
                signal_dict, message = strategy_engine.analyze(df, symbol)
                
                if signal_dict:
                    log_msg = f"[{timeframe}] {symbol} ({provider}): {message}\nDetails: {signal_dict}"
                    logger.info(log_msg)
                    telegram_interface.add_signal(log_msg)
                    
                    # Generate Chart
                    chart_path = None
                    try:
                        import chart_generator
                        chart_path = chart_generator.generate_divergence_chart(symbol, timeframe, df, signal_dict)
                    except Exception as e:
                        logger.error(f"Error generating chart for {symbol}: {e}")
                    
                    # Execute trade (only for crypto futures currently configured)
                    if provider == 'crypto':
                        exchange_mgr.execute_trade(symbol, signal_dict)
                    
                    # Notify user
                    trade_type = "خرید (Long)" if signal_dict['type'] == 'long' else "فروش (Short)"
                    await notify_telegram(
                        f"🚨 **سیگنال جدید یافت شد** 🚨\n\n📌 نماد: {symbol}\n⏱ تایم‌فریم: {timeframe}\n📈 نوع: {trade_type}\n💬 پیام: {message}\n🌐 بازار: {provider.upper()}",
                        photo_path=chart_path
                    )
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                
        # Anti-Rate Limit sleep
        await asyncio.sleep(delay_between_batches)

async def setup_scheduler(app):
    logger.info("Setting up scheduler...")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(analyze_timeframe, 'cron', minute=0, second=5, args=['1h'])
    scheduler.add_job(analyze_timeframe, 'cron', hour='0,4,8,12,16,20', minute=0, second=10, args=['4h'])
    scheduler.add_job(analyze_timeframe, 'cron', hour=0, minute=0, second=15, args=['1d'])
    scheduler.add_job(analyze_timeframe, 'cron', day_of_week='mon', hour=0, minute=0, second=20, args=['1w'])
    scheduler.start()
    
    # Run a quick startup analysis for 1h just to verify it works
    asyncio.create_task(analyze_timeframe('1h'))

def main():
    logger.info("Starting Advanced Crypto Divergence Bot...")
    
    if tg_app:
        # Attach the setup_scheduler to run when the telegram event loop starts
        tg_app.post_init = setup_scheduler
        
        logger.info("Starting Telegram interface...")
        tg_app.run_polling()
    else:
        logger.info("Running without Telegram interface. Press Ctrl+C to stop.")
        # Setup scheduler and run loop manually
        scheduler = AsyncIOScheduler()
        scheduler.add_job(analyze_timeframe, 'cron', minute=0, second=5, args=['1h'])
        scheduler.start()
        
        loop = asyncio.get_event_loop()
        loop.create_task(analyze_timeframe('1h'))
        loop.run_forever()

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
