import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import config
import admin_manager
import gemini_engine

logger = logging.getLogger(__name__)

# Global reference to exchange manager injected by main
exchange_manager = None
# Global reference to recent signals
recent_signals = []

# State dictionary for tracking Gemini Mode: {chat_id: bool}
gemini_modes = {}

def set_exchange_manager(em):
    global exchange_manager
    exchange_manager = em

def add_signal(signal_info):
    global recent_signals
    recent_signals.insert(0, signal_info)
    if len(recent_signals) > 10:
        recent_signals.pop()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the main menu."""
    chat_id = update.effective_chat.id
    if not admin_manager.is_admin(chat_id):
        await update.message.reply_text("⛔️ شما مجاز به استفاده از این ربات نیستید.")
        return

    # Bottom persistent keyboard
    reply_keyboard = [
        [KeyboardButton("تشخیص واگرایی"), KeyboardButton("⚙️ تنظیمات ربات")],
        [KeyboardButton("👥 مدیریت ادمین‌ها"), KeyboardButton("🤖 چت با Gemini")]
    ]
    reply_markup_bottom = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    await update.message.reply_text('منوی اصلی ربات فعال شد. لطفاً از دکمه‌های پایین استفاده کنید.', reply_markup=reply_markup_bottom)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not admin_manager.is_admin(chat_id):
        return

    text = update.message.text
    
    if text == "تشخیص واگرایی":
        if not recent_signals:
            msg = "هیچ سیگنال جدیدی یافت نشد."
        else:
            msg = "📊 **آخرین سیگنال‌ها:**\n\n"
            for s in recent_signals:
                msg += f"▪️ {s}\n"
        await update.message.reply_text(text=msg, parse_mode='Markdown')
        
    elif text == "⚙️ تنظیمات ربات":
        msg = f"""⚙️ **تنظیمات فعلی ربات:**
        
فیلتر روند (EMA): {'روشن' if config.USE_EMA_FILTER else 'خاموش'}

*(توجه: برای تغییر این موارد، فایل .env را ویرایش کرده و ربات را ری‌استارت کنید)*"""
        await update.message.reply_text(text=msg, parse_mode='Markdown')

    elif text == "👥 مدیریت ادمین‌ها":
        admins = admin_manager.get_all_admins()
        admins_str = "\n".join([f"👤 `{aid}`" for aid in admins])
        msg = f"""👥 **لیست ادمین‌های فعلی:**
{admins_str}

برای اضافه کردن ادمین جدید، این دستور را بفرستید:
`/addadmin CHAT_ID`

برای حذف ادمین، این دستور را بفرستید:
`/removeadmin CHAT_ID`"""
        await update.message.reply_text(text=msg, parse_mode='Markdown')
        return

    elif text == "🤖 چت با Gemini":
        gemini_modes[chat_id] = True
        keyboard = [[KeyboardButton("🔙 خروج از چت")]]
        await update.message.reply_text(
            "ورود به حالت هوش مصنوعی! 🤖\n\nحالا من مستقیماً به عنوان دستیار Gemini پاسخ می‌دهم. می‌توانید برای من متن، عکس یا وویس صوتی ارسال کنید.\nبرای ساخت عکس از دستور زیر استفاده کنید:\n`/paint توصیف عکس`",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode='Markdown'
        )
        return

    elif text == "🔙 خروج از چت":
        gemini_modes[chat_id] = False
        reply_keyboard = [
            [KeyboardButton("تشخیص واگرایی"), KeyboardButton("⚙️ تنظیمات ربات")],
            [KeyboardButton("👥 مدیریت ادمین‌ها"), KeyboardButton("🤖 چت با Gemini")]
        ]
        await update.message.reply_text("خروج از حالت هوش مصنوعی. به منوی ربات واگرایی برگشتید.", reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True))
        return

    # If in Gemini Mode, forward text to Gemini
    if gemini_modes.get(chat_id):
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        response_text = await gemini_engine.chat_with_gemini(chat_id, text)
        if len(response_text) > 4000:
            for i in range(0, len(response_text), 4000):
                await update.message.reply_text(response_text[i:i+4000])
        else:
            await update.message.reply_text(response_text)
        return

async def cmd_paint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not admin_manager.is_admin(chat_id): return
    if not gemini_modes.get(chat_id):
        await update.message.reply_text("لطفاً ابتدا از طریق دکمه «🤖 چت با Gemini» وارد حالت چت شوید.")
        return
        
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("توصیف تصویر را بنویسید:\n`/paint a futuristic city`", parse_mode="Markdown")
        return
        
    await context.bot.send_chat_action(chat_id=chat_id, action='upload_photo')
    img_io, err = await gemini_engine.generate_image(prompt)
    if err:
        await update.message.reply_text(err, parse_mode="Markdown")
    else:
        await update.message.reply_photo(photo=img_io, caption=f"تولید شده برای: {prompt}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not admin_manager.is_admin(chat_id) or not gemini_modes.get(chat_id): return
    
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    temp_filename = f"photo_{chat_id}_{update.message.message_id}.jpg"
    await photo_file.download_to_drive(temp_filename)
    
    caption = update.message.caption or ""
    response = await gemini_engine.analyze_photo_with_gemini(chat_id, temp_filename, caption)
    
    if os.path.exists(temp_filename):
        os.remove(temp_filename)
        
    await update.message.reply_text(response)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not admin_manager.is_admin(chat_id) or not gemini_modes.get(chat_id): return
    
    await context.bot.send_chat_action(chat_id=chat_id, action='record_voice')
    voice = update.message.voice
    voice_file = await voice.get_file()
    temp_filename = f"voice_{chat_id}_{update.message.message_id}.ogg"
    await voice_file.download_to_drive(temp_filename)
    
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    response = await gemini_engine.analyze_voice_with_gemini(chat_id, temp_filename)
    
    if os.path.exists(temp_filename):
        os.remove(temp_filename)
        
    await update.message.reply_text(response)

async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not admin_manager.is_admin(chat_id):
        return
        
    if not context.args:
        await update.message.reply_text("لطفاً آیدی عددی ادمین جدید را وارد کنید. مثال:\n`/addadmin 123456789`", parse_mode='Markdown')
        return
        
    new_admin = context.args[0]
    if admin_manager.add_admin(new_admin):
        await update.message.reply_text(f"✅ کاربر `{new_admin}` با موفقیت به لیست ادمین‌ها اضافه شد.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ کاربر `{new_admin}` از قبل ادمین بود.", parse_mode='Markdown')

async def cmd_removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not admin_manager.is_admin(chat_id):
        return
        
    if not context.args:
        await update.message.reply_text("لطفاً آیدی عددی ادمین را برای حذف وارد کنید. مثال:\n`/removeadmin 123456789`", parse_mode='Markdown')
        return
        
    target_admin = context.args[0]
    if str(target_admin) == str(config.TELEGRAM_CHAT_ID):
        await update.message.reply_text("⛔️ شما نمی‌توانید ادمین اصلی سیستم (Super Admin) را حذف کنید.")
        return
        
    if admin_manager.remove_admin(target_admin):
        await update.message.reply_text(f"✅ کاربر `{target_admin}` از لیست ادمین‌ها حذف شد.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ کاربر `{target_admin}` در لیست ادمین‌ها یافت نشد.", parse_mode='Markdown')


def get_telegram_app():
    if not config.TELEGRAM_TOKEN:
        logger.warning("No TELEGRAM_TOKEN provided. Telegram UI will not start.")
        return None
        
    builder = ApplicationBuilder().token(config.TELEGRAM_TOKEN)
    builder = builder.read_timeout(30).write_timeout(30).connect_timeout(30)
    if config.HTTP_PROXY:
        builder = builder.proxy(config.HTTP_PROXY).get_updates_proxy(config.HTTP_PROXY)
    
    app = builder.build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('addadmin', cmd_addadmin))
    app.add_handler(CommandHandler('removeadmin', cmd_removeadmin))
    app.add_handler(CommandHandler('paint', cmd_paint))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
