# -*- coding: utf-8 -*-
import os
import re
import sys
from io import BytesIO
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# Force terminal output to UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Constants
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

LOGO_PATH = "VIPMUSIC/assets/thumb.png"
WATERMARK_TEXT = "Made By. @HeartBeat_Offi"


async def get_thumb(videoid: str):
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_v4.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        search = VideosSearch(videoid, limit=1)
        data = (await search.next()).get("result", [])[0]
        raw_title = data.get("title", "Unsupported Title")

        # ---- Safe Title Processing ----
        draw_title = raw_title.encode("utf-8", "ignore").decode("utf-8")  # keep emojis for drawing
        safe_title = re.sub(r"[^\x00-\x7F]+", "", raw_title)  # remove non-ascii
        safe_title = re.sub(r"[^a-zA-Z0-9 _-]", "", safe_title).strip().replace(" ", "_")

        # thumbnail image url
        thumbnail_url = data["thumbnails"][0]["url"].split("?")[0]
    except Exception:
        thumbnail_url = YOUTUBE_IMG_URL
        draw_title = "Music Streaming"
        safe_title = "music"

    # ---- Download Image ----
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as response:
                content = await response.read()
        image = Image.open(BytesIO(content)).convert("RGBA")
    except Exception:
        return None

    # ---- Base Blur Effect ----
    blurred = image.filter(ImageFilter.GaussianBlur(15))
    enhancer = ImageEnhance.Brightness(blurred)
    blurred = enhancer.enhance(0.6)

    # ---- Add Title Text ----
    draw = ImageDraw.Draw(blurred)
    try:
        font = ImageFont.truetype("VIPMUSIC/assets/font2.ttf", 48)
    except Exception:
        font = ImageFont.load_default()

    text_w, text_h = draw.textsize(draw_title, font=font)
    x = (blurred.width - text_w) / 2
    y = blurred.height * 0.1
    draw.text((x, y), draw_title, font=font, fill="white")

    # ---- Watermark text ----
    try:
        watermark_font = ImageFont.truetype("VIPMUSIC/assets/font2.ttf", 34)  # bigger watermark
    except:
        watermark_font = ImageFont.load_default()

    wm_w, wm_h = draw.textsize(WATERMARK_TEXT, font=watermark_font)
    draw.text(
        ((blurred.width - wm_w) / 2, blurred.height - wm_h - 25),
        WATERMARK_TEXT,
        font=watermark_font,
        fill="white",
    )

    # ---- Watermark Logo Center ----
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo = logo.resize((160, 160))  # bigger & visible
        lx = (blurred.width - logo.width) // 2
        ly = (blurred.height - logo.height) // 2
        blurred.paste(logo, (lx, ly), logo)
    except Exception:
        pass

    # ---- Save Final Image ----
    final = blurred.convert("RGB")
    final.save(cache_path, format="PNG")

    return cache_path
