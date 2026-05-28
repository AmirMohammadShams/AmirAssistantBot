import os
import io
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types
from PIL import Image

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

client = genai.Client(api_key=GEMINI_API_KEY)

# Dictionary to store conversation history per user
user_conversations = {}

def create_grounded_chat(user_id: int):
    """Helper to create a Gemini chat session with Google Search grounding."""
    return client.chats.create(
        model="gemini-3.5-flash",
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id
    
    # Initialize or reset the chat history for this user
    user_conversations[user_id] = create_grounded_chat(user_id)
    
    welcome_message = (
        f"سلام {user.first_name}! من دستیار پیشرفته شما هستم. 🚀\n\n"
        "من به هوش مصنوعی Gemini 3.5 متصل شده‌ام و قابلیت‌های زیر را دارم:\n"
        "🔍 **جستجوی زنده گوگل:** به صورت خودکار اطلاعات بازار طلا، برنامه‌نویسی و اخبار روز را جستجو می‌کنم.\n"
        "🎨 **تولید تصویر:** با دستور /paint و نوشتن توصیف انگلیسی عکس تولید می‌کنم.\n"
        "🖼️ **تحلیل تصویر:** کافیست هر عکسی (اسکرین‌شات کد یا چارت قیمت) را بفرستید تا تحلیل کنم.\n"
        "🎙️ **وویس صوتی:** می‌توانید برای من پیام صوتی بفرستید تا متوجه شوم و پاسخ دهم."
    )
    await update.message.reply_text(welcome_message)

import urllib.parse

async def paint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate an image using Gemini Imagen 4.0 based on user prompt."""
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("لطفا بعد از دستور /paint توصیف عکسی که می‌خواهید را به انگلیسی بنویسید.\n\nمثال:\n`/paint a futuristic city in Iran`", parse_mode="Markdown")
        return

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_photo')
        
        # Call Gemini Imagen 4.0 model
        result = client.models.generate_images(
            model='imagen-4.0-generate-001',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="1:1"
            )
        )
        
        if not result.generated_images:
            await update.message.reply_text("متاسفانه تصویری تولید نشد. لطفا دوباره تلاش کنید.")
            return

        # Send image back
        img_bytes = result.generated_images[0].image.image_bytes
        await update.message.reply_photo(photo=io.BytesIO(img_bytes), caption=f"تصویر تولید شده توسط Gemini برای: {prompt}")

    except Exception as e:
        logger.error(f"Error generating image: {e}")
        error_msg = str(e)
        if "paid plans" in error_msg or "upgrade your account" in error_msg:
            await update.message.reply_text(
                "❌ **خطای عدم دسترسی:**\n"
                "گوگل قابلیت تولید تصویر (Imagen) را فقط برای اکانت‌های دارای پرداخت فعال (Paid Plan/Billing) در پنل Google AI Studio باز گذاشته است.\n\n"
                "برای استفاده از این قابلیت باید کارت اعتباری به پنل گوگل خود اضافه کنید.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"خطا در تولید تصویر با Gemini:\n\n{error_msg}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download user photo, pass it to Gemini, and reply."""
    user_id = update.effective_user.id
    if user_id not in user_conversations:
        user_conversations[user_id] = create_grounded_chat(user_id)
    chat_session = user_conversations[user_id]

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        # Get the largest photo size
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        
        # Download locally
        temp_filename = f"photo_{user_id}_{update.message.message_id}.jpg"
        await photo_file.download_to_drive(temp_filename)
        
        # Load using PIL
        img = Image.open(temp_filename)
        
        # Get caption if provided, otherwise default prompt
        user_caption = update.message.caption or "این تصویر را تحلیل کنید."
        
        # Send both image and caption
        response = chat_session.send_message([img, user_caption])
        
        # Clean up
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
        await update.message.reply_text(response.text)

    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await update.message.reply_text(f"متاسفانه در پردازش تصویر خطایی رخ داد:\n\n{str(e)}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download voice note, upload to Gemini Files API, and reply."""
    user_id = update.effective_user.id
    if user_id not in user_conversations:
        user_conversations[user_id] = create_grounded_chat(user_id)
    chat_session = user_conversations[user_id]

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='record_voice')
        voice = update.message.voice
        voice_file = await voice.get_file()
        
        # Download locally (.ogg format)
        temp_filename = f"voice_{user_id}_{update.message.message_id}.ogg"
        await voice_file.download_to_drive(temp_filename)
        
        # Upload using Files API
        uploaded_file = client.files.upload(file=temp_filename)
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        # Pass voice file to chat
        response = chat_session.send_message([
            uploaded_file,
            "محتوای این وویس را متوجه شو و به زبان فارسی پاسخ بده."
        ])
        
        # Clean up from Gemini cloud
        client.files.delete(name=uploaded_file.name)
        # Clean up local file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
        await update.message.reply_text(response.text)

    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await update.message.reply_text(f"متاسفانه در پردازش وویس خطایی رخ داد:\n\n{str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages and pass them to Gemini with Google Search."""
    user_id = update.effective_user.id
    user_text = update.message.text

    if not user_text:
        return

    # Check if the user has an active chat session, if not create one
    if user_id not in user_conversations:
        user_conversations[user_id] = create_grounded_chat(user_id)
    
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

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("paint", paint))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Check if we are running on Render
    if os.environ.get("RENDER"):
        port = int(os.environ.get("PORT", "10000"))
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
