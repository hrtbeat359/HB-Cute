"""
VIPMUSIC/plugins/tools/reaction_bot.py

Features:
1. /reactionon  - enable reactions for the chat (owner/sudo/admin)
2. /reactionoff - disable reactions for the chat (owner/sudo/admin)
3. /reaction    - show inline Enable / Disable buttons (only owner/sudo/admin can press)
4. Works in groups & supergroups (uses filters.group — Pyrogram v1.x compatible)
5. Persists per-chat on/off state in VIPMUSIC.utils.databases.reactiondb so restarts keep state
6. Per-chat non-repeating emoji rotation (uses START_REACTIONS)
7. Logging to console and to VIPMUSIC logger (if available)
8. Includes /reactiontest (quick test)
"""

import random
import traceback
import logging
from typing import Set, Dict, Optional

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.enums import ChatMemberStatus

from VIPMUSIC import app, LOGGER  # LOGGER exists in your project; fallback to logging if not
from VIPMUSIC.utils.database import get_sudoers
from VIPMUSIC.utils.databases import reactiondb  # expects functions: reaction_on, reaction_off, is_reaction_on

# ---------- Logging fallback ----------
if "LOGGER" not in globals() or LOGGER is None:
    LOGGER = logging.getLogger("reaction_bot")
    if not LOGGER.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
        LOGGER.addHandler(h)
    LOGGER.setLevel(logging.INFO)

print("[ReactionBot] plugin import -> starting")

# ---------- Reaction emoji list (use config-style START_REACTIONS) ----------
# If you prefer, move this list to config.py and import START_REACTIONS from there.
START_REACTIONS = [
    "❤️", "💖", "💘", "💞", "💓", "🎧", "✨", "🔥", "💫",
    "💥", "🎶", "🌸", "💎", "😎", "💗", "🌹", "💕",
    "💝", "🫶", "💌", "💟", "🎵", "⚡", "🌈", "⭐"
]

# validate and deduplicate safety set
SAFE_REACTIONS = list(dict.fromkeys(START_REACTIONS))  # preserve order, remove duplicates
if not SAFE_REACTIONS:
    SAFE_REACTIONS = ["❤️"]

# per-chat rotation cache: chat_id -> set(used_emojis)
_chat_used: Dict[int, Set[str]] = {}


def next_emoji(chat_id: int) -> str:
    """Return a non-repeating emoji per chat (resets when exhausted)."""
    used = _chat_used.get(chat_id, set())
    if len(used) >= len(SAFE_REACTIONS):
        used.clear()
    remaining = [e for e in SAFE_REACTIONS if e not in used]
    emoji = random.choice(remaining)
    used.add(emoji)
    _chat_used[chat_id] = used
    return emoji


# ---------- Admin / Owner / Sudo check ----------
async def is_admin_or_sudo(client, user_id: Optional[int], chat_id: int) -> bool:
    """Return True if the user_id is Owner, in sudoers, or an admin in chat."""
    try:
        if user_id is None:
            return False

        # check sudoers from DB
        try:
            sudoers = await get_sudoers()
        except Exception:
            sudoers = []

        # Owner check: your project may define OWNER_ID in config; try to read if present
        try:
            from config import OWNER_ID
        except Exception:
            OWNER_ID = None

        if OWNER_ID and user_id == OWNER_ID:
            return True

        if user_id in sudoers:
            return True

        # chat admin check
        try:
            member = await app.get_chat_member(chat_id, user_id)
            if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                return True
        except Exception as e:
            # Could be user not in chat or other RPC error
            LOGGER.debug(f"[is_admin_or_sudo] get_chat_member error: {e}")
            return False

    except Exception as e:
        LOGGER.error(f"[is_admin_or_sudo] unexpected error: {e}\n{traceback.format_exc()}")

    return False


# ---------- Test handler ----------
@app.on_message(filters.command("reactiontest") & filters.group)
async def _reaction_test(_, message: Message):
    print("[ReactionBot] /reactiontest command triggered!")
    await message.reply_text("✅ Reaction test command works!")


# ---------- /reactionon ----------
@app.on_message(filters.command(["reactionon", "reactionenable"], prefixes=["/", "!", "."]) & filters.group)
async def cmd_reaction_on(client, message: Message):
    try:
        caller_id = getattr(message.from_user, "id", None)
        chat_id = message.chat.id
        print(f"[ReactionBot] /reactionon triggered by {caller_id} in chat {chat_id}")

        if not await is_admin_or_sudo(client, caller_id, chat_id):
            await message.reply_text("❌ Only the Owner, sudo users or group admins can enable reactions.")
            LOGGER.info(f"/reactionon denied for {caller_id} in {chat_id}")
            return

        await reactiondb.reaction_on(chat_id)
        await message.reply_text("✅ Reactions enabled for this chat.")
        LOGGER.info(f"Reactions enabled in chat {chat_id} by {caller_id}")

    except Exception as e:
        LOGGER.error(f"Error in /reactionon: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text(f"❌ Error enabling reactions:\n`{e}`")
        except Exception:
            pass


# ---------- /reactionoff ----------
@app.on_message(filters.command(["reactionoff", "reactiondisable"], prefixes=["/", "!", "."]) & filters.group)
async def cmd_reaction_off(client, message: Message):
    try:
        caller_id = getattr(message.from_user, "id", None)
        chat_id = message.chat.id
        print(f"[ReactionBot] /reactionoff triggered by {caller_id} in chat {chat_id}")

        if not await is_admin_or_sudo(client, caller_id, chat_id):
            await message.reply_text("❌ Only the Owner, sudo users or group admins can disable reactions.")
            LOGGER.info(f"/reactionoff denied for {caller_id} in {chat_id}")
            return

        await reactiondb.reaction_off(chat_id)
        await message.reply_text("🚫 Reactions disabled for this chat.")
        LOGGER.info(f"Reactions disabled in chat {chat_id} by {caller_id}")

    except Exception as e:
        LOGGER.error(f"Error in /reactionoff: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text(f"❌ Error disabling reactions:\n`{e}`")
        except Exception:
            pass


# ---------- /reaction (status + enable/disable buttons) ----------
@app.on_message(filters.command(["reaction", "reactionstatus"], prefixes=["/", "!", "."]) & filters.group)
async def cmd_reaction_status(client, message: Message):
    try:
        caller_id = getattr(message.from_user, "id", None)
        chat_id = message.chat.id
        print(f"[ReactionBot] /reaction triggered by {caller_id} in chat {chat_id}")

        # show menu only to admins/sudo/owner — but we will still show status to anyone (optionally)
        is_admin = await is_admin_or_sudo(client, caller_id, chat_id)

        status = await reactiondb.is_reaction_on(chat_id)
        if status:
            status_text = "Enabled ✅"
            # if caller is admin show disable button, else show status only
            if is_admin:
                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🚫 Disable Reactions", callback_data=f"reaction_disable_{chat_id}")]]
                )
            else:
                markup = None
        else:
            status_text = "Disabled ⛔"
            if is_admin:
                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("✅ Enable Reactions", callback_data=f"reaction_enable_{chat_id}")]]
                )
            else:
                markup = None

        text = f"🎭 Reaction Manager\n\nChat: `{chat_id}`\nStatus: **{status_text}**\n\n(Only Owner, Sudo users or Chat Admins can toggle.)"
        await message.reply_text(text, reply_markup=markup)
        LOGGER.info(f"/reaction status shown in {chat_id} (status={status}) by {caller_id}")

    except Exception as e:
        LOGGER.error(f"Error in /reaction status: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text(f"❌ Error showing reaction status:\n`{e}`")
        except Exception:
            pass


# ---------- Callback Query: buttons ----------
@app.on_callback_query(filters.regex(r"^reaction_(enable|disable)_(\-?\d+)$"))
async def reaction_button_handler(client, callback: CallbackQuery):
    try:
        data = callback.data or ""
        parts = data.split("_")
        if len(parts) < 3:
            await callback.answer("Invalid action.", show_alert=True)
            return

        action = parts[1]
        target_chat_id = int(parts[2])
        caller = callback.from_user
        caller_id = getattr(caller, "id", None)

        # permission check: only owner/sudo/admin allowed
        allowed = await is_admin_or_sudo(client, caller_id, target_chat_id)
        if not allowed:
            await callback.answer("❌ Only Owner, Sudo users or Group Admins can use this.", show_alert=True)
            LOGGER.info(f"Unauthorized button press by {caller_id} for chat {target_chat_id}")
            return

        if action == "enable":
            await reactiondb.reaction_on(target_chat_id)
            await callback.answer("✅ Reactions enabled for this chat.")
            # edit message to show new status and show disable button
            try:
                await callback.message.edit_text(
                    f"🎭 Reaction Manager\n\nChat: `{target_chat_id}`\nStatus: **Enabled ✅**\n\n(Only Owner, Sudo users or Chat Admins can toggle.)",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🚫 Disable Reactions", callback_data=f"reaction_disable_{target_chat_id}")]]
                    ),
                )
            except Exception:
                pass
            LOGGER.info(f"Reactions enabled via button in chat {target_chat_id} by {caller_id}")

        elif action == "disable":
            await reactiondb.reaction_off(target_chat_id)
            await callback.answer("🚫 Reactions disabled for this chat.")
            try:
                await callback.message.edit_text(
                    f"🎭 Reaction Manager\n\nChat: `{target_chat_id}`\nStatus: **Disabled ⛔**\n\n(Only Owner, Sudo users or Chat Admins can toggle.)",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("✅ Enable Reactions", callback_data=f"reaction_enable_{target_chat_id}")]]
                    ),
                )
            except Exception:
                pass
            LOGGER.info(f"Reactions disabled via button in chat {target_chat_id} by {caller_id}")
        else:
            await callback.answer("Unknown action.", show_alert=True)

    except Exception as e:
        LOGGER.error(f"Error in reaction_button_handler: {e}\n{traceback.format_exc()}")
        try:
            await callback.answer(f"Error: {e}", show_alert=True)
        except Exception:
            pass


# ---------- Auto-react on messages (core behaviour) ----------
@app.on_message((filters.text | filters.caption) & filters.group & ~filters.edited)
async def auto_react_messages(client, message: Message):
    try:
        # skip commands
        text = (message.text or message.caption or "")
        if isinstance(text, str) and text.startswith("/"):
            return

        chat_id = message.chat.id
        # DB check
        try:
            enabled = await reactiondb.is_reaction_on(chat_id)
        except Exception as e:
            LOGGER.error(f"is_reaction_on DB error for chat {chat_id}: {e}")
            # fail-safe default: enabled
            enabled = True

        if not enabled:
            return

        # if message has entities that mention usernames, you can keep original mention-trigger logic elsewhere
        emoji = next_emoji(chat_id)
        try:
            await message.react(emoji)
            LOGGER.info(f"Auto-reacted in chat {chat_id} with {emoji}")
        except Exception as e:
            LOGGER.warning(f"Primary react failed ({emoji}) in chat {chat_id}: {e}")
            try:
                await message.react("❤️")
            except Exception:
                pass

    except Exception as e:
        LOGGER.error(f"Error in auto_react_messages: {e}\n{traceback.format_exc()}")

print("[ReactionBot] plugin loaded successfully")
