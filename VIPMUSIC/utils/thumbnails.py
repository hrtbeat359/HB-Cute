import os
import random
import string
import aiohttp
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from VIPMUSIC.utils.logger import LOGS
from config import SUPPORT_CHAT

def random_hash():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

async def get_thumb(track_id: str):
    try:
        path = f"downloads/{track_id}.png"
        if os.path.exists(path):
            return path
    except:
        pass

    thumb_url = f"https://i.ytimg.com/vi/{track_id}/maxresdefault.jpg"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as response:
                if response.status == 200:
                    with open(f"downloads/{track_id}.png", "wb") as f:
                        f.write(await response.read())
                else:
                    await generate_fallback_thumb(track_id)
    except:
        await generate_fallback_thumb(track_id)

    try:
        await create_watermark(track_id)
    except Exception as e:
        LOGS.error(e)
    return f"downloads/{track_id}.png"


async def generate_fallback_thumb(track_id: str):
    img = Image.new("RGB", (1280, 720))
    img.save(f"downloads/{track_id}.png")


async def create_watermark(track_id: str):
    img_path = f"downloads/{track_id}.png"
    base_img = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(base_img)

    # Watermark Config
    watermark_text = "Made By. @HeartBeat_Fam"
    font_path = "VIPMUSIC/assets/font2.ttf"
    logo_path = "VIPMUSIC/assets/nodp.png"

    try:
        watermark_font = ImageFont.truetype(font_path, 70)
    except:
        watermark_font = ImageFont.load_default()

    text_w, text_h = draw.textsize(watermark_text, font=watermark_font)
    x = base_img.width - text_w - 50
    y = base_img.height - text_h - 50

    # Emboss effect (Light + Dark Layer)
    draw.text((x + 3, y + 3), watermark_text, font=watermark_font, fill=(255, 255, 255, 60))
    draw.text((x - 2, y - 2), watermark_text, font=watermark_font, fill=(0, 0, 0, 40))

    # Emboss logo
    try:
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((150, 150))
        shadow = logo.filter(ImageFilter.GaussianBlur(4))
        shadow_layer = ImageEnhance.Brightness(shadow).enhance(0.2)
        base_img.paste(shadow_layer, (40, base_img.height - 200), shadow_layer)
        base_img.paste(logo, (40, base_img.height - 200), logo)
    except Exception as e:
        LOGS.error(f"Logo Load Error: {e}")

    base_img.save(img_path, "PNG")
