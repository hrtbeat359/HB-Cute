from pyrogram import filters
from pyrogram.types import Message
from time import time
import asyncio

from VIPMUSIC import app
from VIPMUSIC.utils.extraction import extract_user
from VIPMUSIC.utils.api import api  # make sure your api file exports "api"

print("[ccbin] Loaded ccbin.py")

# Anti-Spam Memory
user_last_message_time = {}
user_command_count = {}

SPAM_THRESHOLD = 2        # max 2 commands
SPAM_WINDOW_SECONDS = 5   # within 5 seconds


@app.on_message(filters.command(["bin", "ccbin", "bininfo"], [".", "!", "/"]))
async def check_ccbin(client, message: Message):
    user_id = message.from_user.id
    current_time = time()

    last_time = user_last_message_time.get(user_id, 0)

    # -------------------------
    # ANTI-SPAM PROTECTION
    # -------------------------
    if current_time - last_time < SPAM_WINDOW_SECONDS:
        user_last_message_time[user_id] = current_time
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1

        if user_command_count[user_id] > SPAM_THRESHOLD:
            warn = await message.reply_text(
                f"**{message.from_user.mention} Don't spam. Try again after 5 seconds.**"
            )
            await asyncio.sleep(3)
            await warn.delete()
            return
    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = current_time

    # -------------------------
    # BIN INPUT CHECK
    # -------------------------
    if len(message.command) < 2:
        return await message.reply_text(
            "<b>Please enter a BIN number to check details.</b>"
        )

    try:
        await message.delete()
    except:
        pass

    aux = await message.reply_text("<b>Checking BIN...</b>")

    bin_code = message.text.split(None, 1)[1].strip()

    if not bin_code.isdigit() or len(bin_code) < 6:
        return await aux.edit("<b>❌ Invalid BIN. Must be 6+ digits.</b>")

    # -------------------------
    # API CALL
    # -------------------------
    try:
        resp = await api.bininfo(bin_code)

        # If API returns None or error
        if not resp:
            return await aux.edit("🚫 BIN not recognized.")

        return await aux.edit(f"""
<b>💠 BIN Details:</b>

<b>🏦 Bank:</b> <tt>{resp.bank}</tt>
<b>💳 BIN:</b> <tt>{resp.bin}</tt>
<b>🏡 Country:</b> <tt>{resp.country}</tt>
<b>🇮🇳 Flag:</b> <tt>{resp.flag}</tt>
<b>🧿 ISO:</b> <tt>{resp.iso}</tt>
<b>⏳ Level:</b> <tt>{resp.level}</tt>
<b>🔴 Prepaid:</b> <tt>{resp.prepaid}</tt>
<b>🆔 Type:</b> <tt>{resp.type}</tt>
<b>ℹ️ Vendor:</b> <tt>{resp.vendor}</tt>
""")

    except Exception as e:
        return await aux.edit("🚫 BIN not recognized. Please enter a valid BIN.")
