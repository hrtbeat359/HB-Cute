# VIPMUSIC/utils/thumbnails.py
import os
import re
from io import BytesIO
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# Constants
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

LOGO_PATH = "VIPMUSIC/assets/nodp.png"  # Local watermark logo

PANEL_W, PANEL_H = 763, 545
PANEL_X = (1280 - PANEL_W) // 2
PANEL_Y = 88
INNER_OFFSET = 36

THUMB_W, THUMB_H = 542, 273
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + INNER_OFFSET

TITLE_X = 377
META_X = 377
TITLE_Y = THUMB_Y + THUMB_H + 10
META_Y = TITLE_Y + 45

BAR_X, BAR_Y = 388, META_Y + 45
BAR_RED_LEN = 280
BAR_TOTAL_LEN = 480

ICONS_W, ICONS_H = 415, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 48

MAX_TITLE_WIDTH = 580


def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    try:
        if font.getlength(text) <= max_w:
            return text
    except Exception:
        if font.getsize(text)[0] <= max_w:
            return text
    for i in range(len(text) - 1, 0, -1):
        try:
            if font.getlength(text[:i] + ellipsis) <= max_w:
                return text[:i] + ellipsis
        except Exception:
            if font.getsize(text[:i] + ellipsis)[0] <= max_w:
                return text[:i] + ellipsis
    return ellipsis


async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_v4.png")
    if os.path.exists(cache_path):
        return cache_path

    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
    try:
        results_data = await results.next()
        items = results_data.get("result", [])
        if not items:
            raise ValueError("No results found.")

        data = items[0]
        title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).strip().title()
        thumb_url = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL).split("?")[0]
        duration = data.get("duration")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
    except Exception:
        title, thumb_url, duration, views = "Unsupported Title", YOUTUBE_IMG_URL, None, "Unknown Views"

    is_live = not duration or str(duration).lower() in {"", "live", "live now"}
    duration_text = "Live" if is_live else duration or "Unknown Mins"

    thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
                else:
                    thumb_path = None
    except Exception:
        thumb_path = None

    if not thumb_path or not os.path.exists(thumb_path):
        return YOUTUBE_IMG_URL

    # Base background
    base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")

    # Gaussian Blur Panel section
    blur = base.filter(ImageFilter.GaussianBlur(12))
    panel = blur.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, 140))
    frosted = Image.alpha_composite(panel, overlay)

    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 55, fill=255)
    base.paste(frosted, (PANEL_X, PANEL_Y), mask)

    draw = ImageDraw.Draw(base)

    try:
        title_font = ImageFont.truetype("VIPMUSIC/assets/font2.ttf", 32)
        regular_font = ImageFont.truetype("VIPMUSIC/assets/font.ttf", 18)
    except:
        title_font = regular_font = ImageFont.load_default()

    thumb = Image.open(thumb_path).resize((THUMB_W, THUMB_H)).convert("RGBA")
    tmask = Image.new("L", (THUMB_W, THUMB_H), 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 20, fill=255)
    base.paste(thumb, (THUMB_X, THUMB_Y), tmask)

    draw.text((TITLE_X, TITLE_Y), trim_to_width(title, title_font, MAX_TITLE_WIDTH), fill="black", font=title_font)
    draw.text((META_X, META_Y), f"YouTube | {views}", fill="black", font=regular_font)

    draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_RED_LEN, BAR_Y)], fill="red", width=6)
    draw.line([(BAR_X + BAR_RED_LEN, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=5)
    draw.ellipse([(BAR_X + BAR_RED_LEN - 7, BAR_Y - 7),
                  (BAR_X + BAR_RED_LEN + 7, BAR_Y + 7)], fill="red")

    draw.text((BAR_X, BAR_Y + 15), "00:00", fill="black", font=regular_font)
    draw.text((BAR_X + BAR_TOTAL_LEN - (90 if is_live else 60), BAR_Y + 15),
              duration_text, fill="red" if is_live else "black", font=regular_font)

    # Watermark + logo
    watermark_text = "Made By. @ HeartBeat_Offi"
    try:
        wm_font = ImageFont.truetype("VIPMUSIC/assets/Sprintura Demo.otf", 32)
    except:
        wm_font = ImageFont.load_default()

    tw, th = draw.textsize(watermark_text, font=wm_font)
    x, y = base.width - tw - 40, base.height - th - 30

    draw.text((x, y), watermark_text, font=wm_font, fill=(0, 0, 0, 255))

    try:
        logo = Image.open(LOGO_PATH).resize((75, 75)).convert("RGBA")
        base.paste(logo, (x - 90, y - 10), logo)
    except:
        pass

    os.remove(thumb_path)
    base.save(cache_path)
    return cache_path
