# VIPMUSIC/utils/thumbnails.py
import os
import re
import random
from io import BytesIO
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch
from pydub import AudioSegment
from pydub.utils import make_chunks
from config import YOUTUBE_IMG_URL
import tempfile

# Constants
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

THUMP_LOGO = "https://files.catbox.moe/fowgxf.jpg"

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
BAR_TOTAL_LEN = 480

ICONS_W, ICONS_H = 415, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 48

MAX_TITLE_WIDTH = 580

# Utility functions
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

def duration_to_seconds(d):
    try:
        parts = list(map(int, d.split(":")))
        if len(parts) == 3:
            return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2:
            return parts[0]*60 + parts[1]
        return 0
    except:
        return 0

async def download_audio(url: str) -> str:
    """Download audio to temp file for waveform"""
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(tmp_file.name, "wb") as f:
                        await f.write(await resp.read())
                    return tmp_file.name
    except Exception:
        return None

async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_vwave_final.png")
    if os.path.exists(cache_path):
        return cache_path

    # Fetch YouTube info
    results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
    try:
        results_data = await results.next()
        result_items = results_data.get("result", [])
        if not result_items:
            raise ValueError("No results found.")
        data = result_items[0]
        title = re.sub(r"\W+", " ", data.get("title", "Unsupported Title")).strip().title()
        thumb_url = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        thumbnail = thumb_url.split("?")[0] if thumb_url else YOUTUBE_IMG_URL
        duration = data.get("duration")
        views = data.get("viewCount", {}).get("short", "Unknown Views")
        audio_url = data.get("link")
    except Exception:
        title, thumbnail, duration, views, audio_url = (
            "Unsupported Title",
            YOUTUBE_IMG_URL,
            None,
            "Unknown Views",
            None,
        )

    is_live = not duration or str(duration).strip().lower() in {"", "live", "live now"}
    duration_text = "Live" if is_live else duration or "Unknown Mins"

    # Download thumbnail image
    thumb_path = os.path.join(CACHE_DIR, f"thumb{videoid}.png")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
                else:
                    thumb_path = None
    except Exception:
        thumb_path = None

    if not thumb_path or not os.path.exists(thumb_path):
        return YOUTUBE_IMG_URL

    base = Image.open(thumb_path).resize((1280, 720)).convert("RGBA")
    bg = ImageEnhance.Brightness(base.filter(ImageFilter.BoxBlur(10))).enhance(0.6)

    # Frosted panel
    panel_area = bg.crop((PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H))
    overlay = Image.new("RGBA", (PANEL_W, PANEL_H), (255, 255, 255, TRANSPARENCY))
    frosted = Image.alpha_composite(panel_area, overlay)
    mask = Image.new("L", (PANEL_W, PANEL_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, PANEL_W, PANEL_H), 50, fill=255)
    bg.paste(frosted, (PANEL_X, PANEL_Y), mask)

    draw = ImageDraw.Draw(bg)

    # Fonts
    try:
        title_font = ImageFont.truetype("VIPMUSIC/assets/font2.ttf", 32)
        regular_font = ImageFont.truetype("VIPMUSIC/assets/font.ttf", 18)
    except OSError:
        try:
            title_font = ImageFont.truetype("VIPMUSIC/assets/DejaVuSans-Bold.ttf", 26)
            regular_font = ImageFont.truetype("VIPMUSIC/assets/DejaVuSans.ttf", 16)
        except Exception:
            title_font = regular_font = ImageFont.load_default()

    # Thumbnail shadow
    shadow = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    bg.paste(shadow, (THUMB_X - 8, THUMB_Y - 8), shadow)

    # Paste thumbnail
    thumb = base.resize((THUMB_W, THUMB_H)).convert("RGBA")
    tmask = Image.new("L", (THUMB_W, THUMB_H), 0)
    ImageDraw.Draw(tmask).rounded_rectangle((0, 0, THUMB_W, THUMB_H), 20, fill=255)
    bg.paste(thumb, (THUMB_X, THUMB_Y), tmask)

    # Random style: anime or waveform
    style_type = random.choice(["anime", "waveform"])

    if style_type == "anime":
        gradient = Image.new("L", (1, 720))
        for y in range(720):
            gradient.putpixel((0, y), int(255 * (y / 720)))
        alpha = gradient.resize((1280, 720))
        bg.putalpha(alpha)
    else:
        # Waveform bars from audio
        if audio_url:
            audio_file = await download_audio(audio_url)
            if audio_file:
                try:
                    audio = AudioSegment.from_file(audio_file)
                    total_chunks = 50
                    chunk_length_ms = max(1, len(audio) // total_chunks)
                    chunks = make_chunks(audio, chunk_length_ms)
                    for i, chunk in enumerate(chunks):
                        x1 = THUMB_X + int(i * THUMB_W / total_chunks)
                        x2 = x1 + max(3, int(THUMB_W / total_chunks * 0.9))
                        magnitude = max(chunk.max, 5)
                        y1 = THUMB_Y + THUMB_H - int(magnitude / 32768 * 150)  # scaled
                        y2 = THUMB_Y + THUMB_H
                        draw.rectangle([x1, y1, x2, y2], fill=(255, 0, 0, 220))
                except Exception:
                    # fallback random bars
                    for i in range(50):
                        x1 = THUMB_X + int(i * THUMB_W / 50)
                        x2 = x1 + 5
                        y1 = THUMB_Y + THUMB_H - random.randint(5, 60)
                        y2 = THUMB_Y + THUMB_H
                        draw.rectangle([x1, y1, x2, y2], fill=(255, 0, 0, 200))
                finally:
                    os.remove(audio_file)

    # Title stroke
    title_txt = trim_to_width(title, title_font, MAX_TITLE_WIDTH)
    for offset in [(1,1),(-1,-1),(1,-1),(-1,1)]:
        draw.text((TITLE_X+offset[0], TITLE_Y+offset[1]), title_txt, font=title_font, fill="black")
    draw.text((TITLE_X, TITLE_Y), title_txt, font=title_font, fill="white")

    # Metadata
    draw.text((META_X, META_Y), f"YouTube | {views}", fill="white", font=regular_font)

    # Progress bar
    percent = 0.15
    if not is_live and duration:
        total = duration_to_seconds(duration)
        percent = min(0.97, max(0.03, 120 / total))
    filled = int(BAR_TOTAL_LEN * percent)
    draw.line([(BAR_X, BAR_Y), (BAR_X + BAR_TOTAL_LEN, BAR_Y)], fill="gray", width=7)
    draw.line([(BAR_X, BAR_Y), (BAR_X + filled, BAR_Y)], fill=(255, 0, 0), width=7)
    draw.ellipse([(BAR_X + filled - 8, BAR_Y - 8), (BAR_X + filled + 8, BAR_Y + 8)], fill="red")
    draw.text((BAR_X, BAR_Y + 15), "00:00", fill="white", font=regular_font)
    draw.text((BAR_X + BAR_TOTAL_LEN - 60, BAR_Y + 15), "Live" if is_live else duration_text,
              fill="red" if is_live else "white", font=regular_font)

    # Icons
    icons_path = "VIPMUSIC/assets/play_icons.png"
    if os.path.isfile(icons_path):
        try:
            ic = Image.open(icons_path).resize((ICONS_W, ICONS_H)).convert("RGBA")
            r, g, b, a = ic.split()
            black_ic = Image.merge("RGBA", (r.point(lambda *_:0), g.point(lambda *_:0), b.point(lambda *_:0), a))
            bg.paste(black_ic, (ICONS_X, ICONS_Y), black_ic)
        except Exception:
            pass

    # Watermark
    try:
        watermark_font = ImageFont.truetype("VIPMUSIC/assets/font2.ttf", 36)
    except Exception:
        watermark_font = ImageFont.load_default()

    watermark_text = "Made By. @HeartBeat_Fam"
    try:
        text_w, text_h = draw.textsize(watermark_text, font=watermark_font)
    except Exception:
        text_w, text_h = watermark_font.getsize(watermark_text)

    x = bg.width - text_w - 100
    y = bg.height - text_h - 100
    glow_positions = [(x + dx, y + dy) for dx in (-1, 1) for dy in (-1, 1)]
    for pos in glow_positions:
        draw.text(pos, watermark_text, font=watermark_font, fill=(0,0,0,200))
    draw.text((x, y), watermark_text, font=watermark_font, fill=(255,255,255,255))

    # Watermark logo bigger
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(THUMP_LOGO) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    logo_img = Image.open(BytesIO(data)).convert("RGBA").resize((100,100))
                    bg.paste(logo_img, (x - 110, y - 10), logo_img)
    except Exception:
        pass

    # Cleanup temp
    try:
        os.remove(thumb_path)
    except Exception:
        pass

    bg.save(cache_path)
    return cache_path
