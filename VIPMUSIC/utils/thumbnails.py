# VIPMUSIC/utils/thumbnails.py

import os
import re
from io import BytesIO
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# Constants
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

LOGO_PATH = "VIPMUSIC/assets/thumb.png"
WATERMARK_FONT_PATH = "VIPMUSIC/assets/font2.ttf"

async def fetch_image(url: str) -> BytesIO:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return BytesIO(await resp.read())

async def get_thumb(videoid: str):
    try:
        image_cache_path = f"{CACHE_DIR}/{videoid}.jpg"
        if os.path.exists(image_cache_path):
            return image_cache_path

        # Search video
        results = VideosSearch(videoid, limit=1)
        data = await results.next()
        thumbnail_url = data["result"][0]["thumbnails"][0]["url"].split("?")[0]

        # Download image
        img_data = await fetch_image(thumbnail_url)
        image = Image.open(img_data).convert("RGB")

        # Blur background
        blurred = image.resize((1280, 720))
        blurred = blurred.filter(Image.BLUR)
        blurred.paste(image.resize((750, 450)), (265, 135))

        draw = ImageDraw.Draw(blurred)

        # Watermark Logo
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo = logo.resize((130, 130))
            lw, lh = logo.size
            blurred.paste(logo, ((1280 - lw) // 2, 720 - lh - 40), logo)
        except Exception as e:
            print(f"Logo error: {e}")

        # Watermark text
        watermark_text = "Made By. @HeartBeat_Fam"
        try:
            watermark_font = ImageFont.truetype(WATERMARK_FONT_PATH, 36)
        except Exception:
            watermark_font = ImageFont.load_default()

        text_w, text_h = draw.textsize(watermark_text, font=watermark_font)
        draw.text(
            ((1280 - text_w) // 2, 720 - text_h - 5),
            watermark_text,
            font=watermark_font,
            fill=(255, 255, 255, 255),
        )

        # Save final
        blurred.save(image_cache_path, "JPEG", quality=95)
        return image_cache_path

    except Exception as e:
        print(e)
        return None
