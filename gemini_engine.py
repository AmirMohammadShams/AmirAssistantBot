import os
import io
import logging
from google import genai
from google.genai import types
from PIL import Image
from config import config

logger = logging.getLogger(__name__)

# Initialize client
client = None
if config.GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Gemini Client: {e}")

# Dictionary to store conversation history per user
user_conversations = {}

def create_chat(user_id: int):
    """Helper to create a Gemini chat session."""
    if not client:
        return None
    return client.chats.create(
        model="gemini-3.5-flash"
    )

def get_chat_session(user_id: int):
    if user_id not in user_conversations:
        user_conversations[user_id] = create_chat(user_id)
    return user_conversations[user_id]

async def generate_image(prompt: str):
    """Generate an image using Gemini Imagen 4.0 based on user prompt."""
    if not client:
        return None, "کلید API برای Gemini تنظیم نشده است."
        
    try:
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
            return None, "متاسفانه تصویری تولید نشد. لطفا دوباره تلاش کنید."

        # Send image back
        img_bytes = result.generated_images[0].image.image_bytes
        return io.BytesIO(img_bytes), None

    except Exception as e:
        logger.error(f"Error generating image: {e}")
        error_msg = str(e)
        if "paid plans" in error_msg or "upgrade your account" in error_msg:
            return None, (
                "❌ **خطای عدم دسترسی:**\n"
                "گوگل قابلیت تولید تصویر (Imagen) را فقط برای اکانت‌های دارای پرداخت فعال (Paid Plan/Billing) باز گذاشته است.\n\n"
                "برای استفاده از این قابلیت باید کارت اعتباری به پنل گوگل خود اضافه کنید."
            )
        return None, f"خطا در تولید تصویر با Gemini:\n\n{error_msg}"

async def analyze_photo_with_gemini(user_id: int, image_path: str, caption: str):
    """Analyze a downloaded photo using Gemini."""
    chat_session = get_chat_session(user_id)
    if not chat_session:
        return "هوش مصنوعی فعال نیست."
        
    try:
        img = Image.open(image_path)
        prompt = caption or "این تصویر را به صورت تخصصی بررسی کن."
        response = chat_session.send_message([img, prompt])
        return response.text
    except Exception as e:
        logger.error(f"Error analyzing photo: {e}")
        return f"متاسفانه در پردازش تصویر خطایی رخ داد:\n\n{str(e)}"

async def analyze_voice_with_gemini(user_id: int, voice_path: str):
    """Analyze a voice note using Gemini."""
    chat_session = get_chat_session(user_id)
    if not chat_session:
        return "هوش مصنوعی فعال نیست."
        
    try:
        # Upload using Files API
        uploaded_file = client.files.upload(file=voice_path)
        
        # Pass voice file to chat
        response = chat_session.send_message([
            uploaded_file,
            "محتوای این وویس را متوجه شو و به صورت دقیق به زبان فارسی پاسخ بده."
        ])
        
        # Clean up from Gemini cloud
        client.files.delete(name=uploaded_file.name)
        return response.text
    except Exception as e:
        logger.error(f"Error analyzing voice: {e}")
        return f"متاسفانه در پردازش وویس خطایی رخ داد:\n\n{str(e)}"

async def chat_with_gemini(user_id: int, text: str):
    """Send text to Gemini and get response."""
    chat_session = get_chat_session(user_id)
    if not chat_session:
        return "هوش مصنوعی فعال نیست. لطفاً API Key را در تنظیمات بررسی کنید."
        
    try:
        response = chat_session.send_message(text)
        return response.text
    except Exception as e:
        logger.error(f"Error chatting with Gemini: {e}")
        return f"خطا در ارتباط با هوش مصنوعی:\n\n{str(e)}"
