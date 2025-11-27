# VIPMUSIC/plugins/setmybio.py
import os
import json
from pyrogram import Client, filters
from pyrogram.types import Message

# Path to local storage
BIO_DB_PATH = "VIPMUSIC/utils/localdb/user_bios.json"

# Ensure folder exists
os.makedirs("VIPMUSIC/utils/localdb", exist_ok=True)

# Load DB
def load_bios():
    if not os.path.exists(BIO_DB_PATH):
        return {}
    try:
        with open(BIO_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# Save DB
def save_bios(data):
    with open(BIO_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# -------------------------
# /setmybio → set user bio
# -------------------------
@Client.on_message(filters.command("setmybio"))
async def set_my_bio(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(
            "💬 **Usage:**\n`/setmybio Your bio here`\n\nExample:\n`/setmybio I love music and coding!`"
        )
        return

    user_id = str(message.from_user.id)
    bio_text = " ".join(message.command[1:])

    db = load_bios()
    db[user_id] = bio_text
    save_bios(db)

    await message.reply_text(
        f"✅ **Your bio has been updated!**\n\n**New Bio:**\n`{bio_text}`"
    )


# -------------------------
# /mybio → view own bio
# -------------------------
@Client.on_message(filters.command("mybio"))
async def get_my_bio(client: Client, message: Message):
    user_id = str(message.from_user.id)
    db = load_bios()

    if user_id not in db:
        await message.reply_text("❌ You haven't set any bio yet.\nSet one with: `/setmybio text`")
        return

    await message.reply_text(
        f"📝 **Your Bio:**\n`{db[user_id]}`"
    )


# -------------------------------------------------------
# Auto reply user's bio when someone replies to their msg
# -------------------------------------------------------
@Client.on_message(filters.text & ~filters.command([]))
async def auto_bio_reply(client: Client, message: Message):
    # Only react when someone replies to a user's message
    if not message.reply_to_message or not message.from_user:
        return

    target = message.reply_to_message.from_user
    if not target:
        return

    user_id = str(target.id)
    db = load_bios()

    if user_id in db:
        await message.reply_text(
            f"🧾 **{target.first_name}'s Bio:**\n`{db[user_id]}`"
        )
