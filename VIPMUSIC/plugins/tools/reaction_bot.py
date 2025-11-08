import asyncio
import random
from typing import Dict, Set, Optional, Tuple

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus, ChatType

from VIPMUSIC import app
from config import BANNED_USERS, OWNER_ID, START_REACTIONS, REACTION_BOT
from VIPMUSIC.utils.database import mongodb, get_sudoers

# -------------------- DATABASE --------------------
COLLECTION = mongodb["reaction_bot_chats"]

# -------------------- CACHE --------------------
reaction_enabled_chats: Set[int] = set()
chat_used_reactions: Dict[int, Set[str]] = {}

# -------------------- VALID REACTIONS --------------------
VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "💫", "🔥",
    "💥", "🎶", "🌸", "😍", "🥰", "💎", "🌙",
    "🌹", "😂", "😎", "🤩", "😘", "😉", "💐", "😻", "🥳"
}
SAFE_REACTIONS = [e for e in START_REACTIONS if e in VALID_REACTIONS] or list(VALID_REACTIONS)

# -------------------- UTILITIES --------------------
async def load_reaction_chats():
    """Load enabled chats from DB."""
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

def next_emoji(chat_id: int) -> str:
    """Return a random non-repeating emoji per chat."""
    if chat_id not in chat_used_reactions:
        chat_used_reactions[chat_id] = set()

    used = chat_used_reactions[chat_id]
    if len(used) >= len(SAFE_REACTIONS):
        used.clear()

    remaining = [e for e in SAFE_REACTIONS if e not in used]
    emoji = random.choice(remaining)
    used.add(emoji)
    return emoji

# -------------------- ADMIN CHECK --------------------
async def is_admin_or_sudo(client, message: Message) -> Tuple[bool, Optional[str]]:
    """Check if the user is an admin, owner, or sudoer."""
    user_id = getattr(message.from_user, "id", None)
    chat_id = message.chat.id
    chat_type = getattr(message.chat, "type", None)

    if not user_id:
        return False, "no from_user"

    try:
        sudoers = await get_sudoers()
    except Exception:
        sudoers = set()

    if user_id == OWNER_ID or user_id in sudoers:
        return True, None

    if chat_type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return False, "not a group or supergroup"

    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return True, None
        return False, f"user_status={member.status}"
    except Exception as e:
        return False, str(e)

# -------------------- COMMAND: /reaction --------------------
@app.on_message(filters.command("reaction") & filters.group & ~BANNED_USERS)
async def toggle_reaction(client, message: Message):
    """Enable or disable reaction bot in this chat."""
    ok, debug = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text(
            f"⚠️ Only admins, owner, or sudo users can toggle reactions.\n\nDebug: {debug or 'unknown'}"
        )

    if len(message.command) < 2:
        return await message.reply_text("Usage: `/reaction on` or `/reaction off`")

    action = message.command[1].lower()
    chat_id = message.chat.id

    if action == "on":
        await COLLECTION.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
        reaction_enabled_chats.add(chat_id)
        await message.reply_text("✅ **Reaction Bot enabled** for this chat.")
    elif action == "off":
        await COLLECTION.delete_one({"chat_id": chat_id})
        reaction_enabled_chats.discard(chat_id)
        await message.reply_text("🚫 **Reaction Bot disabled** for this chat.")
    else:
        await message.reply_text("Usage: `/reaction on` or `/reaction off`")

# -------------------- REACT TO MESSAGES --------------------
@app.on_message(filters.text & filters.group & ~BANNED_USERS)
async def auto_react(client, message: Message):
    """React automatically if enabled and globally allowed."""
    if not REACTION_BOT:
        return
    chat_id = message.chat.id
    if chat_id not in reaction_enabled_chats:
        return
    if message.text.startswith("/"):
        return
    try:
        emoji = next_emoji(chat_id)
        await message.react(emoji)
        print(f"[ReactionBot] Reacted in {chat_id} with {emoji}")
    except Exception as e:
        print(f"[ReactionBot] Error reacting: {e}")
