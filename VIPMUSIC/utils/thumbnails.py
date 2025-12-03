# VIPMUSIC/utils/thumbnails.py

import os
import re
from io import BytesIO
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

LOGO_PATH = "VIPMUSIC/assets/thumb.png"

PANEL_W, PANEL_H = 763, 545
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 88
TRANSPARENCY = 170
INNER_OFFSET = 36

THUMB_W, THUMB_H = 542, 273
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + INNER_OFFSET

TITLE_X = 377
META_X = 377
TITLE_Y = THUMB_Y + THUMB_H + 15
META_Y = TITLE_Y + 50

BAR_X, BAR_Y = 388, META_Y + 50
BAR_RED_LEN = 280
BAR_TOTAL_LEN = 480

ICONS_W, ICONS_H = 415, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 50

MAX_TITLE_WIDTH = 600


def trim_to_width(text, font, max_w):
    ellipsis = "…"
    try:
        if font.getlength(text) <= max_w:
            return text
    except:
        if font.getsize(text)[0] <= max_w:
            return text
    for i in range(len(text) - 1, 0, -1):
        chunk = text[:i] + ellipsis
        try:
            if font.getlength(chunk) <= max_w:
                return chunk
        except:
            if font.getsize(chunk)[0] <= max_w:
                return chunk
    return ellipsis


async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_v4.png")
    if os.path.exists(cache_path):
        return cache_path

    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
    try:
        results_data = await results.next()
        items = results_data.get("result", [])
        data = items[0]

        # FIX: preserve all Unicode characters safely
        title = str(data.get("title", "Unsupported Title"))
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        duration = data.get("duration")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
    except:
        title, thumbnail, duration, views = "Unsupported Title", YOUTUBE_IMG_URL, None, "Unknown Views"

    is_live = not duration or str(duration).lower() in {"", "live", "live now"}
    duration_text = "Live" if is_live else duration or "Unknown"

    thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
    except:
        return YOUTUBE_IMG_URL

    base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
    bg = ImageEnhance.Brightness(base.filter(ImageFilter.BoxBlur(10))).enhance(0.6)

    panel = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, TRANSPARENCY))
    frosted = Image.alpha_composite(panel, overlay)

    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
    bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

    draw = ImageDraw.Draw(bg)

    # Increased Sizes
    try:
        title_font = ImageFont.truetype("VIPMUSIC/assets/font2.ttf", 42)
        regular_font = ImageFont.truetype("VIPMUSIC/assets/font.ttf", 28)
    except:
        title_font = regular_font = ImageFont.load_default()

    # Thumbnail rounded
    thumb = base.resize((THUMB_W, THUMB_H)).convert("RGBA")
    tmask = Image.new("L", (THUMB_W, THUMB_H), 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 20, fill=255)
    bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

    draw.text((TITLE_X, TITLE_Y), trim_to_width(title, title_font, MAX_TITLE_WIDTH), fill="black", font=title_font)
    draw.text((META_X, META_Y), f"YouTube | {views}", fill="black", font=regular_font)

    draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_RED_LEN, BAR_Y)], fill="red", width=8)
    draw.line([(BAR_X + BAR_RED_LEN, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=6)
    draw.ellipse([(BAR_X + BAR_RED_LEN - 9, BAR_Y - 9), (BAR_X + BAR_RED_LEN + 9, BAR_Y + 9)], fill="red")

    draw.text((BAR_X, BAR_Y + 18), "00:00", fill="black", font=regular_font)
    draw.text((BAR_X + BAR_TOTAL_LEN - 80, BAR_Y + 18), duration_text, fill="black", font=regular_font)

    try:
        icons = Image.open("VIPMUSIC/assets/play_icons.png").resize((ICONS_W, ICONS_H)).convert("RGBA")
        r, g, b, a = icons.split()
        black_ic = Image.merge("RGBA", (r.point(lambda *_: 0), g.point(lambda *_: 0), b.point(lambda *_: 0), a))
        bg.paste(black_ic, (ICONS_X, ICONS_Y), black_ic)
    except:
        pass

    try:
        os.remove(thumb_path)
    except:
        pass

    bg.save(cache_path, format="PNG")
    return cache_path
