"""Image generation service for SmartPostAI - Uses Gemini API exclusively"""
import os
import sys
import base64
import asyncio
import aiohttp
import time
import hashlib
from typing import Optional, List, Dict
from uagents import Context
from dotenv import load_dotenv

# Ensure safe console output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Gemini image models to attempt in priority order
GEMINI_IMAGE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
    "gemini-3.1-flash-lite-image"
]

class ImageGenerator:
    """Handles image generation using Gemini API exclusively"""

    def __init__(self, agent_context: Optional[Context] = None):
        self.gemini_api_key = GEMINI_API_KEY
        self.agent_context = agent_context
        self.image_generation_agent = None
        self._pending_image_requests = {}
        self._last_image_url = None

    async def generate(self, prompt: str, topic: Optional[str] = None, ctx: Optional[Context] = None) -> Optional[str]:
        """
        Generate image using Gemini API exclusively.
        Returns image URL or Base64 data URL if Gemini API succeeds, or None if Gemini fails/quota exceeded.
        """
        topic_text = topic or prompt or "Social Media Post"
        
        if not self.gemini_api_key:
            print("❌ GEMINI_API_KEY environment variable is not configured.")
            return None

        # Call Gemini API directly for image generation
        try:
            base64_data = await self._generate_image_with_gemini(topic_text)
            if base64_data:
                hosted_url = await self._upload_image_to_hosting_service(base64_data, topic_text)
                if hosted_url:
                    return hosted_url
                return f"data:image/png;base64,{base64_data}"
            else:
                print("❌ Gemini API did not return image data.")
                return None
        except Exception as e:
            print(f"❌ Gemini Image Generation error: {e}")
            return None

    async def _generate_image_with_gemini(self, topic: str) -> Optional[str]:
        """
        Query Gemini API image generation models to obtain image base64 data.
        """
        if not self.gemini_api_key:
            return None

        image_prompt = (
            f"Generate a professional, high-resolution digital image for a social media post about: {topic}. "
            "Clean layout, high quality, modern design."
        )

        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": image_prompt}]
            }]
        }

        # Attempt available Gemini image generation models
        for model in GEMINI_IMAGE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
            print(f"🔍 Requesting Gemini Image Generation ({model})...")

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                        if response.status == 200:
                            data = await response.json()
                            candidates = data.get('candidates', [])
                            if candidates:
                                parts = candidates[0].get('content', {}).get('parts', [])
                                for part in parts:
                                    inline = part.get('inlineData') or part.get('inline_data')
                                    if inline and inline.get('data'):
                                        print(f"✅ Gemini API ({model}) successfully generated image!")
                                        return inline['data']
                        else:
                            error_text = await response.text()
                            print(f"⚠️ Gemini API ({model}) returned HTTP {response.status}: {error_text[:200]}")
            except Exception as model_err:
                print(f"⚠️ Gemini API model {model} attempt error: {model_err}")

        return None

    async def _upload_image_to_hosting_service(self, image_data: str, topic: str) -> Optional[str]:
        """
        Upload Base64 image data to Supabase Storage if configured.
        """
        try:
            decoded_image = base64.b64decode(image_data)
            timestamp = str(int(time.time()))
            topic_hash = hashlib.md5(topic.encode('utf-8')).hexdigest()[:8]
            filename = f"gemini_image_{topic_hash}_{timestamp}.png"

            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")

            if supabase_url and supabase_key:
                storage_url = f"{supabase_url}/storage/v1/object/generated-images/{filename}"
                headers = {
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "image/png"
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(storage_url, headers=headers, data=decoded_image, timeout=15) as response:
                        if response.status == 200:
                            public_url = f"{supabase_url}/storage/v1/object/public/generated-images/{filename}"
                            print(f"✅ Image uploaded to Supabase Storage: {public_url}")
                            return public_url
                        else:
                            error_text = await response.text()
                            print(f"⚠️ Supabase upload warning: {response.status} - {error_text[:150]}")

            return f"data:image/png;base64,{image_data}"
        except Exception as e:
            print(f"⚠️ Image upload warning: {e}")
            return f"data:image/png;base64,{image_data}"

    def handle_response(self, sender: str, msg) -> bool:
        return False
