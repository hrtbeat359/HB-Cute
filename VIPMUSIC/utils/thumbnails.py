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

# Watermark config (change paths/names if you want)
WM_LOGO_PATH = "VIPMUSIC/assets/thumb.png"         # watermark logo file
WATERMARK_TEXT = "Made By. @HeartBeat_Offi"       # watermark text
WATERMARK_FONT_PATH = "VIPMUSIC/assets/font2.ttf" # preferred watermark font
WATERMARK_FONT_SIZE = 34                          # font size for watermark text
WM_LOGO_SIZE = (120, 120)                         # logo width,height

def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    try:
        if font.getlength(text) <= max_w:
            return text
    except Exception:
        # fallback
        if ImageFont.ImageFont.getsize(font, text)[0] <= max_w:
            return text
    for i in range(len(text) - 1, 0, -1):
        cand = text[:i] + ellipsis
        try:
            if font.getlength(cand) <= max_w:
                return cand
        except Exception:
            if ImageFont.ImageFont.getsize(font, cand)[0] <= max_w:
                return cand
    return ellipsis

async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_v4.png")
    if os.path.exists(cache_path):
        return cache_path

    # YouTube video data fetch
    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
    try:
        results_data = await results.next()
        result_items = results_data.get("result", [])
        if not result_items:
            raise ValueError("No results found.")
        data = result_items[0]

        # --- sanitize title: remove emojis / non-ascii to avoid latin-1 encoding errors ---
        raw_title = data.get("title", "Unsupported Title")
        try:
            title = raw_title.encode("ascii", "ignore").decode()  # removes emojis/unicode
            title = re.sub(r"\s+", " ", title).strip()
            title = re.sub(r"\W+", " ", title).title()
        except Exception:
            title = re.sub(r"\W+", " ", str(raw_title)).title()

        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        duration = data.get("duration")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
    except Exception:
        title, thumbnail, duration, views = "Unsupported Title", YOUTUBE_IMG_URL, None, "Unknown Views"

    is_live = not duration or str(duration).strip().lower() in {"", "live", "live now"}
    duration_text = "Live" if is_live else duration or "Unknown Mins"

    # Download thumbnail (into temporary file)
    thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
    except Exception:
        # fallback to config url
        return YOUTUBE_IMG_URL

    # Create base image
    base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
    bg = ImageEnhance.Brightness(base.filter(ImageFilter.BoxBlur(10))).enhance(0.6)

    # Frosted glass panel
    panel_area = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, TRANSPARENCY))
    frosted = Image.alpha_composite(panel_area, overlay)
    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
    bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

    # Draw details
    draw = ImageDraw.Draw(bg)
    try:
        title_font = ImageFont.truetype("VIPMUSIC/assets/assets/font2.ttf", 32)
        regular_font = ImageFont.truetype("VIPMUSIC/assets/assets/font.ttf", 18)
    except Exception:
        title_font = regular_font = ImageFont.load_default()

    thumb = base.resize((THUMB_W, THUMB_H))
    tmask = Image.new("L", thumb.size, 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 20, fill=255)
    bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

    draw.text((TITLE_X, TITLE_Y), trim_to_width(title, title_font, MAX_TITLE_WIDTH), fill="black", font=title_font)
    draw.text((META_X, META_Y), f"YouTube | {views}", fill="black", font=regular_font)

    # Progress bar
    draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_RED_LEN, BAR_Y)], fill="red", width=6)
    draw.line([(BAR_X + BAR_RED_LEN, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=5)
    draw.ellipse([(BAR_X + BAR_RED_LEN - 7, BAR_Y - 7), (BAR_X + BAR_RED_LEN + 7, BAR_Y + 7)], fill="red")

    draw.text((BAR_X, BAR_Y + 15), "00:00", fill="black", font=regular_font)
    end_text = "Live" if is_live else duration_text
    draw.text((BAR_X + BAR_TOTAL_LEN - (90 if is_live else 60), BAR_Y + 15), end_text, fill="red" if is_live else "black", font=regular_font)

    # Icons
    icons_path = "VIPMUSIC/assets/assets/play_icons.png"
    if os.path.isfile(icons_path):
        ic = Image.open(icons_path).resize((ICONS_W, ICONS_H)).convert("RGBA")
        r, g, b, a = ic.split()
        black_ic = Image.merge("RGBA", (r.point(lambda *_: 0), g.point(lambda *_: 0), b.point(lambda *_: 0), a))
        bg.paste(black_ic, (ICONS_X, ICONS_Y), black_ic)

    # ------------------ WATERMARK SECTION ------------------
    # Sanitize watermark text (removes emojis/unicode that can cause encoding issues)
    try:
        wm_text = WATERMARK_TEXT.encode("ascii", "ignore").decode()
    except Exception:
        wm_text = re.sub(r"[^\x00-\x7F]+", "", WATERMARK_TEXT)

    # Load watermark font (fallback to default)
    try:
        wm_font = ImageFont.truetype(WATERMARK_FONT_PATH, WATERMARK_FONT_SIZE)
    except Exception:
        wm_font = ImageFont.load_default()

    # Determine logo placement (centered, slightly above bottom)
    logo_y = 720 - WM_LOGO_SIZE[1] - 80  # base Y for logo; adjust spacing here
    text_y = logo_y + WM_LOGO_SIZE[1] + 8  # text below logo

    # Paste logo (centered) if file exists and is valid
    if os.path.isfile(WM_LOGO_PATH):
        try:
            wm_logo = Image.open(WM_LOGO_PATH).convert("RGBA")
            wm_logo = wm_logo.resize(WM_LOGO_SIZE)
            logo_x = (1280 - wm_logo.width) // 2
            bg.paste(wm_logo, (logo_x, logo_y), wm_logo)
        except Exception:
            # if logo fails, continue without breaking thumbnail generation
            pass

    # Compute text width (use safe approaches)
    try:
        # prefer font.getlength when available
        text_w = wm_font.getlength(wm_text)
    except Exception:
        try:
            text_w, _ = draw.textsize(wm_text, font=wm_font)
        except Exception:
            text_w = len(wm_text) * (WATERMARK_FONT_SIZE // 2)

    text_x = int((1280 - text_w) // 2)

    # Draw shadow + white text (shadow slightly offset)
    try:
        draw.text((text_x + 2, text_y + 2), wm_text, font=wm_font, fill="black")
        draw.text((text_x, text_y), wm_text, font=wm_font, fill="white")
    except Exception:
        # fallback: use default font draw without shadow
        try:
            draw.text((text_x, text_y), wm_text, font=ImageFont.load_default(), fill="white")
        except Exception:
            pass
    # ---------------- END WATERMARK -----------------------

    # Cleanup temp thumb
    try:
        os.remove(thumb_path)
    except Exception:
        pass

    # Save final image as PNG (RGBA)
    try:
        bg.save(cache_path, format="PNG")
    except Exception:
        # as last resort, convert to RGB and save as PNG
        try:
            bg.convert("RGB").save(cache_path, format="PNG")
        except Exception as e:
            # if saving completely fails, re-raise so caller knows
            raise e

    return cache_path
