import asyncio
import random
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from VIPMUSIC import app
from config import BANNED_USERS, OWNER_ID, START_REACTIONS, REACTION_BOT
from VIPMUSIC.utils.database import get_sudoers
from VIPMUSIC.utils.database.reactiondb import get_reaction_status, set_reaction_status


# --- Emoji tracking per chat to avoid repeats ---
last_emoji = {}

# --- Helper Functions ---
async def is_admin(client, chat_id: int, user_id: int) -> bool:
    """Check if a user is an admin or sudo/owner."""
    sudoers = await get_sudoers()
    if user_id in sudoers or user_id == OWNER_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


# --- Reaction Handler ---
@app.on_message(filters.incoming & ~filters.service & ~BANNED_USERS)
async def auto_react(client, message):
    """Automatically reacts to messages when reaction bot is enabled."""
    if not REACTION_BOT:
        return

    chat_id = message.chat.id
    if message.chat.type not in ["group", "supergroup"]:
        return

    # Check chat status (enabled or disabled)
    if not get_reaction_status(chat_id):
        return

    # Random emoji (non-repeating)
    emojis = START_REACTIONS.copy()
    prev = last_emoji.get(chat_id)
    if prev in emojis:
        emojis.remove(prev)
    emoji = random.choice(emojis)
    last_emoji[chat_id] = emoji

    try:
        await message.react(emoji)
    except Exception as e:
        print(f"[ReactionBot] Failed to react in {chat_id}: {e}")


# --- Reaction Command Handler ---
@app.on_message(filters.command(["reaction"]) & ~BANNED_USERS & filters.group)
async def reaction_command(client, message):
    """Enable or disable reaction bot in a chat."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Only admins, owner, or sudo users can manage reactions.")

    args = message.text.split(maxsplit=1)
    current_status = get_reaction_status(chat_id)

    if len(args) == 2:
        cmd = args[1].lower()
        if cmd == "on":
            set_reaction_status(chat_id, True)
            return await message.reply_text(
                "✅ **Reaction Bot Enabled** for this chat.\nBot will now react to every message."
            )
        elif cmd == "off":
            set_reaction_status(chat_id, False)
            return await message.reply_text("🚫 **Reaction Bot Disabled** for this chat.")
        else:
            return await message.reply_text("Usage: `/reaction on` or `/reaction off`")

    # Show current status with buttons
    text = (
        f"🤖 **Reaction Bot Status:** {'✅ Enabled' if current_status else '🚫 Disabled'}\n\n"
        "Use the buttons below to toggle."
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Enable", callback_data=f"reaction_enable_{chat_id}"),
                InlineKeyboardButton("🚫 Disable", callback_data=f"reaction_disable_{chat_id}")
            ]
        ]
    )
    await message.reply_text(text, reply_markup=keyboard)


# --- Callback Query Handler for Buttons ---
@app.on_callback_query(filters.regex(r"^reaction_(enable|disable)_(\-\d+)$"))
async def reaction_callback(client, callback_query):
    """Handle enable/disable button presses."""
    action, chat_id = callback_query.data.split("_")[1:]
    chat_id = int(chat_id)
    user_id = callback_query.from_user.id

    if not await is_admin(client, chat_id, user_id):
        return await callback_query.answer("❌ Only admins can change reaction settings.", show_alert=True)

    if action == "enable":
        set_reaction_status(chat_id, True)
        await callback_query.answer("✅ Reactions enabled for this chat.", show_alert=True)
        text = "✅ **Reaction Bot Enabled** — bot will now react to messages."
    else:
        set_reaction_status(chat_id, False)
        await callback_query.answer("🚫 Reactions disabled for this chat.", show_alert=True)
        text = "🚫 **Reaction Bot Disabled** — bot will no longer react."

    await callback_query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Enable", callback_data=f"reaction_enable_{chat_id}"),
                    InlineKeyboardButton("🚫 Disable", callback_data=f"reaction_disable_{chat_id}")
                ]
            ]
        ),
    )


print("[ReactionBot] Reaction manager loaded successfully.")
