# VIPMUSIC/utils/thumbnails.py

import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

# Constants
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

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
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_v4.png")
    if os.path.exists(cache_path):
        return cache_path

    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
    try:
        results_data = await results.next()
        data = results_data.get("result", [])[0]
        title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).title()
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        duration = data.get("duration")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
    except Exception:
        title, thumbnail, duration, views = "Unsupported Title", YOUTUBE_IMG_URL, None, "Unknown Views"

    is_live = not duration or str(duration).strip().lower() in {"", "live", "live now"}
    duration_text = "Live" if is_live else duration or "Unknown Mins"

    thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
    except Exception:
        return YOUTUBE_IMG_URL

    base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
    bg = ImageEnhance.Brightness(base.filter(ImageFilter.BoxBlur(10))).enhance(0.6)

    panel_area = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, TRANSPARENCY))
    frosted = Image.alpha_composite(panel_area, overlay)
    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
    bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

    draw = ImageDraw.Draw(bg)

    try:
        title_font = ImageFont.truetype("VIPMUSIC/assets/font2.ttf", 32)
        regular_font = ImageFont.truetype("VIPMUSIC/assets/font.ttf", 18)
    except OSError:
        title_font = regular_font = ImageFont.load_default()

    thumb = base.resize((THUMB_W, THUMB_H))
    tmask = Image.new("L", thumb.size, 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 20, fill=255)
    bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

    draw.text((TITLE_X, TITLE_Y), trim_to_width(title, title_font, MAX_TITLE_WIDTH), fill="black", font=title_font)
    draw.text((META_X, META_Y), f"YouTube | {views}", fill="black", font=regular_font)

    draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_RED_LEN, BAR_Y)], fill="red", width=6)
    draw.line([(BAR_X + BAR_RED_LEN, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=5)
    draw.ellipse([(BAR_X + BAR_RED_LEN - 7, BAR_Y - 7),
                  (BAR_X + BAR_RED_LEN + 7, BAR_Y + 7)], fill="red")
    draw.text((BAR_X, BAR_Y + 15), "00:00", fill="black", font=regular_font)
    draw.text((BAR_X + BAR_TOTAL_LEN - 60, BAR_Y + 15),
              duration_text, fill="red" if is_live else "black", font=regular_font)

    icons_path = "VIPMUSIC/assets/play_icons.png"
    if os.path.isfile(icons_path):
        ic = Image.open(icons_path).resize((ICONS_W, ICONS_H)).convert("RGBA")
        r, g, b, a = ic.split()
        black_ic = Image.merge("RGBA", (r.point(lambda *_: 0), g.point(lambda *_: 0), b.point(lambda *_: 0), a))
        bg.paste(black_ic, (ICONS_X, ICONS_Y), black_ic)

    # ---------------- WATERMARK FIX -----------------
    WM_LOGO_PATH = "VIPMUSIC/assets/thumb.png"
    WATERMARK_TEXT = "Made By. @ HeartBeat_Offi"
    WATERMARK_FONT_PATH = "VIPMUSIC/assets/Sprintura_Demo.otf"
    WATERMARK_FONT_SIZE = 34
    WM_LOGO_SIZE = (60, 60)

    wm_layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    wm_draw = ImageDraw.Draw(wm_layer)

    try:
        wm_font = ImageFont.truetype(WATERMARK_FONT_PATH, WATERMARK_FONT_SIZE)
    except Exception:
        wm_font = ImageFont.load_default()

    wm_y = int(PANEL_Y + PANEL_H + 30)

    wm_logo = None
    if os.path.isfile(WM_LOGO_PATH):
        try:
            wm_logo = Image.open(WM_LOGO_PATH).convert("RGBA").resize(WM_LOGO_SIZE, Image.LANCZOS)
        except Exception:
            wm_logo = None

    text_w = int(wm_font.getlength(WATERMARK_TEXT))

    logo_w, logo_h = WM_LOGO_SIZE
    total_width = int(logo_w + 12 + text_w)
    start_x = int((1280 - total_width) // 2)

    if wm_logo:
        wm_layer.alpha_composite(wm_logo, (start_x, wm_y))

    text_x = int(start_x + logo_w + 12)
    text_y = int(wm_y + (logo_h - WATERMARK_FONT_SIZE) // 2)

    wm_draw.text((text_x + 2, text_y + 2), WATERMARK_TEXT, font=wm_font, fill="black")
    wm_draw.text((text_x, text_y), WATERMARK_TEXT, font=wm_font, fill="white")

    bg = Image.alpha_composite(bg, wm_layer)
    # ---------------- END WATERMARK -----------------

    try:
        os.remove(thumb_path)
    except OSError:
        pass

    bg.save(cache_path)
    return cache_path
