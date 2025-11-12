import asyncio
import random
from typing import Dict
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus, ChatType
from VIPMUSIC import app
from config import BANNED_USERS, START_REACTIONS, OWNER_ID
from VIPMUSIC.misc import SUDOERS

# ---------------- DATABASE ----------------
from VIPMUSIC.core.mongo import mongodb
REACTION_STATUS_COLLECTION = mongodb["reaction_status"]

# ---------------- VALID REACTION EMOJIS ----------------
VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "✨", "🔥", "💫",
    "💥", "🌸", "😍", "🥰", "💎", "🌙", "🌹", "😂",
    "😎", "🤩", "😘", "😉", "🤭", "💐", "😻", "🥳"
}

# Filter config list safely
SAFE_REACTIONS = [e for e in START_REACTIONS if e in VALID_REACTIONS]
if not SAFE_REACTIONS:
    SAFE_REACTIONS = list(VALID_REACTIONS)

# ---------------- PER-CHAT EMOJI ROTATION ----------------
chat_used_reactions: Dict[int, set] = {}

def next_emoji(chat_id: int) -> str:
    """Return a random, non-repeating emoji per chat."""
    if chat_id not in chat_used_reactions:
        chat_used_reactions[chat_id] = set()

    used = chat_used_reactions[chat_id]

    # Reset once all are used
    if len(used) >= len(SAFE_REACTIONS):
        used.clear()

    remaining = [e for e in SAFE_REACTIONS if e not in used]
    emoji = random.choice(remaining)
    used.add(emoji)
    return emoji

# ---------------- ADMIN CHECK ----------------
async def is_admin_or_sudo(client, message: Message) -> bool:
    user_id = getattr(message.from_user, "id", None)
    chat_id = message.chat.id
    chat_type = message.chat.type

    # Sudo or owner
    if user_id and (user_id == OWNER_ID or user_id in SUDOERS):
        return True

    # Linked channel owner
    sender_chat_id = getattr(message.sender_chat, "id", None)
    if sender_chat_id:
        try:
            chat = await client.get_chat(chat_id)
            if getattr(chat, "linked_chat_id", None) == sender_chat_id:
                return True
        except Exception:
            pass

    if chat_type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return False

    if not user_id:
        return False

    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False

# ---------------- REACTION STATUS MANAGEMENT ----------------
async def get_reaction_status(chat_id: int) -> bool:
    """Get reaction status for a chat from database"""
    try:
        doc = await REACTION_STATUS_COLLECTION.find_one({"chat_id": chat_id})
        if doc:
            return doc.get("status", True)
        return True  # Default to enabled
    except Exception:
        return True

async def set_reaction_status(chat_id: int, status: bool):
    """Set reaction status for a chat in database"""
    try:
        await REACTION_STATUS_COLLECTION.update_one(
            {"chat_id": chat_id},
            {"$set": {"status": status}},
            upsert=True
        )
    except Exception as e:
        print(f"[Reaction Bot] Error setting reaction status: {e}")

# ---------------- /reactionon ----------------
@app.on_message(filters.command("reactionon") & ~BANNED_USERS)
async def reaction_on_command(client, message: Message):
    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("⚠️ Only admins or sudo users can enable reactions.")

    chat_id = message.chat.id
    await set_reaction_status(chat_id, True)
    await message.reply_text("✅ **Reaction mode enabled!**\n\nNow I will react to all messages in this chat.")

# ---------------- /reactionoff ----------------
@app.on_message(filters.command("reactionoff") & ~BANNED_USERS)
async def reaction_off_command(client, message: Message):
    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("⚠️ Only admins or sudo users can disable reactions.")

    chat_id = message.chat.id
    await set_reaction_status(chat_id, False)
    await message.reply_text("❌ **Reaction mode disabled!**\n\nI will stop reacting to messages in this chat.")

# ---------------- /reaction ----------------
@app.on_message(filters.command("reaction") & ~BANNED_USERS)
async def reaction_command(client, message: Message):
    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("⚠️ Only admins or sudo users can manage reactions.")

    chat_id = message.chat.id
    current_status = await get_reaction_status(chat_id)
    
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Enable", callback_data=f"reaction_enable_{chat_id}"),
                InlineKeyboardButton("❌ Disable", callback_data=f"reaction_disable_{chat_id}"),
            ]
        ]
    )
    
    status_text = "enabled" if current_status else "disabled"
    await message.reply_text(
        f"**🤖 Reaction Settings**\n\n"
        f"**Current Status:** `{status_text}`\n\n"
        f"Use the buttons below to enable or disable reactions:",
        reply_markup=keyboard
    )

# ---------------- CALLBACK QUERY HANDLER ----------------
@app.on_callback_query(filters.regex(r"^reaction_(enable|disable)_(\-?\d+)$"))
async def reaction_callback_handler(client, callback_query):
    chat_id = int(callback_query.matches[0].group(2))
    action = callback_query.matches[0].group(1)
    
    # Check if user has permission
    user_id = callback_query.from_user.id
    try:
        member = await client.get_chat_member(chat_id, user_id)
        is_admin = member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
        
        # Check sudo
        is_sudo = user_id == OWNER_ID or user_id in SUDOERS
        
        if not (is_admin or is_sudo):
            await callback_query.answer("❌ You need to be an admin to use this!", show_alert=True)
            return
    except Exception:
        await callback_query.answer("❌ Error verifying permissions!", show_alert=True)
        return

    if action == "enable":
        await set_reaction_status(chat_id, True)
        await callback_query.message.edit_text(
            "✅ **Reaction mode enabled!**\n\nNow I will react to all messages in this chat."
        )
    else:
        await set_reaction_status(chat_id, False)
        await callback_query.message.edit_text(
            "❌ **Reaction mode disabled!**\n\nI will stop reacting to messages in this chat."
        )
    
    await callback_query.answer()

# ---------------- REACT ON ALL MESSAGES ----------------
@app.on_message((filters.text | filters.caption) & ~BANNED_USERS)
async def react_on_all_messages(client, message: Message):
    try:
        # Skip bot commands
        if message.text and message.text.startswith("/"):
            return

        chat_id = message.chat.id
        
        # Check if reactions are enabled for this chat
        reaction_status = await get_reaction_status(chat_id)
        if not reaction_status:
            return

        # Check if it's a group or supergroup
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return

        # React to ALL messages
        emoji = next_emoji(chat_id)
        try:
            await message.react(emoji)
            print(f"[Reaction Bot] Chat {chat_id} → {emoji} for all message")
        except Exception as e:
            print(f"[Reaction Bot] Error reacting to message: {e}")

    except Exception as e:
        print(f"[react_on_all_messages] error: {e}")

# ---------------- LOAD REACTION STATUS ON STARTUP ----------------
async def load_reaction_status():
    """Load all chat reaction statuses on startup"""
    try:
        docs = await REACTION_STATUS_COLLECTION.find().to_list(None)
        print(f"[Reaction Bot] Loaded reaction status for {len(docs)} chats.")
    except Exception as e:
        print(f"[Reaction Bot] Error loading reaction status: {e}")

asyncio.get_event_loop().create_task(load_reaction_status())

print("[Reaction Bot] ✅ Reaction bot module loaded successfully!")
