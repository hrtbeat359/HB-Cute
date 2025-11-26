import asyncio
from pyrogram import filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from VIPMUSIC import app
from VIPMUSIC.misc import SUDOERS
from config import MONGO_DB_URI
from motor.motor_asyncio import AsyncIOMotorClient

mongo = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo["VIPMUSIC"]["CHAT_LOCKS"]

LOCK_TYPES = [
    "all", "text", "photo", "video", "audio", "voice", "videonote",
    "gif", "sticker", "stickeranim", "stickerprem",
    "file", "bot", "inline", "poll", "url", "forward",
    "forwardbot", "forwardchat", "forwardstor", "forwarduse",
    "emoji", "emojionly", "emojicustom", "emojigame",
    "contact", "command", "spoiler", "location",
    "button", "cashtag", "cyrillic", "cjk",
    "externalrep", "document", "invitelink", "anonymous",
    "rtl", "zalgo", "game"
]

def sudoadmin(_, __, message: Message):
    return message.from_user and message.from_user.id in SUDOERS

sudo_only = filters.create(sudoadmin)


async def get_locks(chat_id):
    data = await db.find_one({"chat_id": chat_id})
    if not data:
        await db.insert_one({"chat_id": chat_id, "locks": []})
        return []
    return data.get("locks", [])


async def update_locks(chat_id, locks):
    await db.update_one({"chat_id": chat_id}, {"$set": {"locks": locks}}, upsert=True)


def locks_keyboard(active):
    keyboard = []
    row = []
    for l in LOCK_TYPES:
        symbol = "🟢" if l not in active else "🔴"
        row.append(InlineKeyboardButton(f"{symbol} {l}", callback_data=f"lock_{l}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="close_lockmenu")])
    return InlineKeyboardMarkup(keyboard)


@app.on_message(filters.command("locktypes") & sudo_only)
async def locktypes(_, message: Message):
    locks = await get_locks(message.chat.id)
    await message.reply("**🔐 Lock Menu**\nToggle any item below:", reply_markup=locks_keyboard(locks))


@app.on_message(filters.command("locks") & sudo_only)
async def locks_cmd(_, message: Message):
    locks = await get_locks(message.chat.id)
    if not locks:
        await message.reply("**There are no active locks here.**")
    else:
        await message.reply("**Active Locks:**\n" + "\n".join(f"🔒 `{i}`" for i in locks))


@app.on_callback_query(filters.regex(r"lock_"))
async def lock_switch(_, query: CallbackQuery):
    lock_type = query.data.split("_", 1)[1]
    locks = await get_locks(query.message.chat.id)

    if lock_type in locks:
        locks.remove(lock_type)
        await query.answer(f"Unlocked {lock_type}", show_alert=False)
    else:
        locks.append(lock_type)
        await query.answer(f"Locked {lock_type}", show_alert=False)

    await update_locks(query.message.chat.id, locks)
    await query.message.edit("**🔐 Lock Menu**\nToggle any item below:", reply_markup=locks_keyboard(locks))


@app.on_callback_query(filters.regex("close_lockmenu"))
async def close_menu(_, query: CallbackQuery):
    await query.message.delete()


# AUTO DELETE MESSAGES WITH LOCK ACTIVE
@app.on_message(filters.group, group=99)
async def filter_locked(_, message: Message):
    locks = await get_locks(message.chat.id)
    if not locks:
        return

    msg = None
    if message.text and not message.entities:
        msg = "text"
    elif message.photo:
        msg = "photo"
    elif message.video:
        msg = "video"
    elif message.sticker:
        msg = "sticker"
    elif message.animation:
        msg = "gif"
    elif message.voice:
        msg = "voice"
    elif message.audio:
        msg = "audio"
    elif message.via_bot:
        msg = "bot"
    elif message.forward_from or message.forward_from_chat:
        msg = "forward"
    elif message.caption and "http" in message.caption.lower():
        msg = "url"

    if msg in locks or "all" in locks:
        try:
            await message.delete()
        except:
            pass
