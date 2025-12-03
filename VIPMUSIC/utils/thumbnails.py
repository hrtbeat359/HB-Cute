# VIPMUSIC/utils/thumbnails.py

import os
import re
from io import BytesIO

import aiofiles
import aiohttp
from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont
)
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# ============ CONSTANTS ============
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

LOGO_PATH = "VIPMUSIC/assets/nodp.png"

PANEL_W, PANEL_H = 780, 560
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 80

INNER_OFFSET = 38
THUMB_W, THUMB_H = 540, 300
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + INNER_OFFSET

TITLE_X = PANEL_X + 40
TITLE_Y = THUMB_Y + THUMB_H + 20

META_X = TITLE_X
META_Y = TITLE_Y + 50

MAX_TITLE_WIDTH = 600


async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_HB.png")
    if os.path.exists(cache_path):
        return cache_path

    # ---------- GET YOUTUBE INFO ----------
    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
    try:
        data = await results.next()
        item = data["result"][0]
        title = re.sub(r"\W+", " ", item["title"]).title()
        thumb_url = item["thumbnails"][0]["url"].split("?")[0]
        duration = item.get("duration")
        views = item.get("viewCount", {}).get("short", "Views?")
    except:
        title, thumb_url, duration, views = "Unknown Track", YOUTUBE_IMG_URL, None, "Unknown"

    is_live = not duration or str(duration).lower() in ["", "live", "live now"]
    duration_text = "LIVE" if is_live else duration

    # ---------- DOWNLOAD THUMBNAIL ----------
    temp = os.path.join(CACHE_DIR, f"temp_{videoid}.png")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(thumb_url) as r:
                if r.status == 200:
                    async with aiofiles.open(temp, "wb") as f:
                        await f.write(await r.read())
    except:
        return YOUTUBE_IMG_URL

    # ---------- BASE IMAGE + BLUR PANEL ----------
    base = Image.open(temp).resize((1280, 720)).convert("RGBA")
    blur = base.filter(ImageFilter.GaussianBlur(12))

    panel = blur.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, 140))
    frosted = Image.alpha_composite(panel, overlay)

    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 55, fill=255)
    base.paste(frosted, (PANEL_X, PANEL_Y), mask)

    draw = ImageDraw.Draw(base)

    # ---------- ROUND THUMBNAIL ----------
    tmask = Image.new("L", (THUMB_W, THUMB_H), 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 28, fill=255)
    thumb = Image.open(temp).resize((THUMB_W, THUMB_H)).convert("RGBA")
    base.paste(thumb, (THUMB_X, THUMB_Y), tmask)

    # ---------- AUTO FONT SIZE ----------
    font_size = max(32, int(base.width * 0.032))
    meta_size = max(22, int(base.width * 0.018))

    try:
        title_font = ImageFont.truetype("VIPMUSIC/assets/font2.ttf", font_size)
        meta_font = ImageFont.truetype("VIPMUSIC/assets/font.ttf", meta_size)
    except:
        title_font = meta_font = ImageFont.load_default()

    # Trim title to fit width
    while title_font.getlength(title) > MAX_TITLE_WIDTH:
        title = title[:-1]

    draw.text((TITLE_X, TITLE_Y), title, font=title_font, fill="black")
    draw.text((META_X, META_Y), f"YouTube | {views} | {duration_text}", font=meta_font, fill="black")

    # ---------- EMBOSS WATERMARK ----------
    watermark_text = "Made By. @ HeartBeat_Offi"
    wm_size = max(30, int(base.width * 0.04))

    try:
        wm_font = ImageFont.truetype("VIPMUSIC/assets/Sprintura Demo.otf", wm_size)
    except:
        wm_font = ImageFont.load_default()

    tw, th = draw.textsize(watermark_text, font=wm_font)
    wx = base.width - tw - 60
    wy = base.height - th - 55

    blur_box = (wx - 20, wy - 20, wx + tw + 20, wy + th + 20)
    b = base.crop(blur_box).filter(ImageFilter.GaussianBlur(8))
    base.paste(b, blur_box)

    draw.text((wx + 2, wy + 2), watermark_text, font=wm_font, fill=(255, 255, 255, 95))
    draw.text((wx, wy), watermark_text, font=wm_font, fill=(0, 0, 0, 170))

    # ---------- EMBOSSED LOGO ----------
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        ls = max(110, int(base.width * 0.075))
        logo = logo.resize((ls, ls))
        shadow = logo.filter(ImageFilter.GaussianBlur(8))
        base.paste(shadow, (40, base.height - ls - 90), shadow)
        base.paste(logo, (40, base.height - ls - 90), logo)
    except:
        pass

    os.remove(temp)
    base.save(cache_path)
    return cache_path
