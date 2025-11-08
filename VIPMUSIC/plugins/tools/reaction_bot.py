import asyncio
import random
from typing import Set, Dict, Optional, Tuple

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus

from VIPMUSIC import app
from config import BANNED_USERS, START_REACTIONS, REACTION_BOT, OWNER_ID
from VIPMUSIC.utils.database import mongodb, get_sudoers

# -------------------- DATABASE --------------------
COLLECTION = mongodb["reaction_bot_chats"]

# -------------------- CACHE --------------------
reaction_enabled_chats: Set[int] = set()       # Chats where reactions are ON
chat_used_reactions: Dict[int, Set[str]] = {}  # Emoji rotation per chat

# -------------------- VALID REACTIONS --------------------
VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "💫", "🔥",
    "💥", "🎶", "🌸", "😍", "🥰", "💎", "🌙",
    "🌹", "😂", "😎", "🤩", "😘", "😉", "💐", "😻", "🥳"
}
SAFE_REACTIONS = [e for e in START_REACTIONS if e in VALID_REACTIONS] or list(VALID_REACTIONS)

# -------------------- LOAD PERSISTENT CHAT SETTINGS --------------------
async def load_reaction_chats():
    try:
        docs = await COLLECTION.find().to_list(None)
        for doc in docs:
            chat_id = doc.get("chat_id")
            if chat_id:
                reaction_enabled_chats.add(chat_id)
        print(f"[ReactionBot] Loaded {len(reaction_enabled_chats)} chat statuses from DB.")
    except Exception as e:
        print(f"[ReactionBot] Error loading chat states: {e}")

asyncio.get_event_loop().create_task(load_reaction_chats())

# -------------------- HELPER FUNCTIONS --------------------
def next_emoji(chat_id: int) -> str:
    """Return a random, non-repeating emoji per chat."""
    if chat_id not in chat_used_reactions:
        chat_used_reactions[chat_id] = set()

    used = chat_used_reactions[chat_id]
    if len(used) >= len(SAFE_REACTIONS):
        used.clear()

    remaining = [e for e in SAFE_REACTIONS if e not in used]
    emoji = random.choice(remaining)
    used.add(emoji)
    return emoji

async def is_admin_or_sudo(client, message: Message) -> Tuple[bool, Optional[str]]:
    """Check if the user is admin, owner or sudoer in the chat."""
    user_id = getattr(message.from_user, "id", None)
    chat_id = message.chat.id
    chat_type = getattr(message.chat, "type", "").lower()

    if not user_id:
        return False, "no from_user"

    try:
        sudoers = await get_sudoers()
    except Exception:
        sudoers = set()

    if user_id == OWNER_ID or user_id in sudoers:
        return True, None

    if chat_type not in ("group", "supergroup"):
        return False, f"chat_type={chat_type}"

    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return True, None
        return False, f"user_status={member.status}"
    except Exception as e:
        return False, str(e)

# -------------------- COMMAND: /reaction on|off --------------------
@app.on_message(filters.command("reaction") & ~BANNED_USERS & (filters.group | filters.channel))
async def toggle_reaction(client, message: Message):
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)

    # If no argument, show current status
    if len(args) < 2:
        status = "✅ ON" if chat_id in reaction_enabled_chats else "❌ OFF"
        return await message.reply_text(
            f"🤖 Reaction Bot Status: `{status}`\nUse `/reaction on` or `/reaction off`",
            quote=True,
        )

    action = args[1].strip().lower()
    ok, debug = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text(
            f"⚠️ Only admins, owner, or sudo users can toggle reactions.\nDebug: {debug or 'unknown'}",
            quote=True,
        )

    if action == "on":
        try:
            await COLLECTION.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
            reaction_enabled_chats.add(chat_id)
            return await message.reply_text("❤️ Reaction Bot **enabled**!", quote=True)
        except Exception as e:
            return await message.reply_text(f"❌ DB Error: {e}", quote=True)
    elif action == "off":
        try:
            await COLLECTION.delete_one({"chat_id": chat_id})
            reaction_enabled_chats.discard(chat_id)
            return await message.reply_text("💤 Reaction Bot **disabled**!", quote=True)
        except Exception as e:
            return await message.reply_text(f"❌ DB Error: {e}", quote=True)
    else:
        return await message.reply_text("Usage: `/reaction on` or `/reaction off`", quote=True)

# -------------------- AUTO REACT --------------------
@app.on_message((filters.text | filters.sticker | filters.photo | filters.video | filters.document) & ~BANNED_USERS & (filters.group | filters.channel))
async def auto_react(client, message: Message):
    if not REACTION_BOT:
        return

    chat_id = message.chat.id
    if chat_id not in reaction_enabled_chats:
        return
    if message.text and message.text.startswith("/"):
        return

    try:
        emoji = next_emoji(chat_id)
        await message.react(emoji)
        print(f"[ReactionBot] Reacted in {chat_id} with {emoji}")
    except Exception as e:
        print(f"[ReactionBot] Error reacting: {e}")
