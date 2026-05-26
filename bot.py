import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configure Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("No GEMINI_API_KEY found in environment variables. Please check your .env file.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Dictionary to store conversation history per user
user_conversations = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id
    
    # Initialize or reset the chat history for this user
    user_conversations[user_id] = model.start_chat(history=[])
    
    welcome_message = (
        f"سلام {user.first_name}! من دستیار هوشمند شما هستم که به هوش مصنوعی Gemini متصل شده‌ام.\n"
        "هر سوالی دارید بپرسید تا کمکتون کنم."
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages and pass them to Gemini."""
    user_id = update.effective_user.id
    user_text = update.message.text

    if not user_text:
        return

    # Check if the user has an active chat session, if not create one
    if user_id not in user_conversations:
        user_conversations[user_id] = model.start_chat(history=[])
    
    chat_session = user_conversations[user_id]

    try:
        # Show "typing..." status
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        # Send message to Gemini
        response = chat_session.send_message(user_text)
        
        # Send response back to Telegram
        response_text = response.text
        if len(response_text) > 4000:
            for i in range(0, len(response_text), 4000):
                await update.message.reply_text(response_text[i:i+4000])
        else:
            await update.message.reply_text(response_text)

    except Exception as e:
        logger.error(f"Error communicating with Gemini: {e}")
        await update.message.reply_text(f"متاسفانه در ارتباط با هوش مصنوعی خطایی رخ داد. خطا:\n\n{str(e)}")

def main() -> None:
    """Start the bot."""
    # Get Telegram token
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables. Please check your .env file.")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(telegram_token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Check if we are running on Render
    if os.environ.get("RENDER"):
        port = int(os.environ.get("PORT", "10000"))
        # Render sets RENDER_EXTERNAL_HOSTNAME automatically
        app_name = os.environ.get("RENDER_EXTERNAL_HOSTNAME") 
        logger.info(f"Starting webhook on port {port} for {app_name}")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=f"https://{app_name}/"
        )
    else:
        # Run the bot with polling locally
        logger.info("Bot is starting with polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
