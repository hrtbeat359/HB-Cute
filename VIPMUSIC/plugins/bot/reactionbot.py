# VIPMUSIC/plugins/tools/reaction_merged.py
import asyncio
import random
from typing import Set, Dict, Tuple, Optional

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.enums import ChatMemberStatus, ChatType

from VIPMUSIC import app
from config import BANNED_USERS, MENTION_USERNAMES, START_REACTIONS, OWNER_ID
from VIPMUSIC.utils.database import mongodb, get_sudoers

print("[reaction_merged] loaded — merged reaction system")

# ---------------- DATABASE ----------------
COLLECTION = mongodb["reaction_mentions"]         # stores mention triggers (name/id:)
SETTINGS = mongodb["reaction_settings"]          # stores {"_id":"switch","enabled":bool}

# ---------------- STATE ----------------
# Controls ONLY the global auto-react that reacts to every message.
# Mention-based reactions ignore this flag and always work.
REACTION_ENABLED = True  # default ON

# ---------------- CACHE ----------------
# Preload mention username list from config + DB
custom_mentions: Set[str] = set(x.lower().lstrip("@") for x in (MENTION_USERNAMES or []))

# ---------------- VALID REACTIONS ----------------
VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "✨", "🔥", "💫",
    "💥", "🌸", "😍", "🥰", "💎", "🌙", "🌹", "😂",
    "😎", "🤩", "😘", "😉", "🤭", "💐", "😻", "🥳",
    "👍", "👎", "👏", "😁", "🤔", "😢", "🤯", "🤩", "🙏", "🎉"
}
SAFE_REACTIONS = [e for e in (START_REACTIONS or []) if e in VALID_REACTIONS]
if not SAFE_REACTIONS:
    SAFE_REACTIONS = list(VALID_REACTIONS)

# ---------------- ROTATION STORAGE ----------------
chat_used_reactions: Dict[int, Set[str]] = {}


def next_emoji(chat_id: int) -> str:
    """Return a per-chat non-repeating emoji; cycles when exhausted."""
    if chat_id not in chat_used_reactions:
        chat_used_reactions[chat_id] = set()

    used = chat_used_reactions[chat_id]
    if len(used) >= len(SAFE_REACTIONS):
        used.clear()

    remaining = [e for e in SAFE_REACTIONS if e not in used]
    emoji = random.choice(remaining)
    used.add(emoji)
    chat_used_reactions[chat_id] = used
    return emoji


# ---------------- LOAD DB CACHE ----------------
async def load_custom_mentions():
    try:
        docs = await COLLECTION.find({}).to_list(length=None)
        for doc in docs:
            name = doc.get("name")
            if name:
                custom_mentions.add(str(name).lower().lstrip("@"))
        print(f"[Reaction Manager] Loaded {len(custom_mentions)} triggers.")
    except Exception as e:
        print(f"[Reaction Manager] DB load error: {e}")


asyncio.get_event_loop().create_task(load_custom_mentions())


# ---------------- LOAD SWITCH STATE ----------------
async def load_reaction_state():
    global REACTION_ENABLED
    try:
        doc = await SETTINGS.find_one({"_id": "switch"})
        if doc:
            REACTION_ENABLED = doc.get("enabled", True)
    except Exception as e:
        print(f"[Reaction Switch] DB read error: {e}")
    print(f"[Reaction Switch] Loaded => {REACTION_ENABLED}")


asyncio.get_event_loop().create_task(load_reaction_state())


# ---------------- ADMIN CHECK ----------------
async def is_admin_or_sudo(client, message: Message) -> Tuple[bool, Optional[str]]:
    """Return (True, None) if sender is OWNER, sudoer or chat admin (for groups)."""
    user = getattr(message, "from_user", None)
    chat = getattr(message, "chat", None)
    if not chat or not user:
        return False, "invalid message"

    user_id = user.id
    chat_id = chat.id

    # Owner / Sudoers
    try:
        sudoers = await get_sudoers()
    except Exception:
        sudoers = set()

    if user_id == OWNER_ID or user_id in sudoers:
        return True, None

    # If not group/supergroup/channel, return false
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
        return False, f"chat_type={chat.type}"

    # Normal admin check
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return True, None
        return False, f"user_status={member.status}"
    except Exception as e:
        return False, f"get_chat_member_error={e}"


# ---------------- /reaction COMMAND (controls ONLY auto-react) ----------------
@app.on_message(filters.command("reaction") & ~BANNED_USERS, group=1)
async def react_command(client, message: Message):
    global REACTION_ENABLED

    ok, debug = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text(
            "⚠️ Only admins/sudo users may control reaction system.\n\n"
            f"Debug: {debug}"
        )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Enable", callback_data="react_on"),
                InlineKeyboardButton("🛑 Disable", callback_data="react_off"),
            ],
            [
                InlineKeyboardButton("🔍 Status", callback_data="react_status")
            ]
        ]
    )

    await message.reply_text(
        f"**Reaction System Control**\n\n"
        f"Current state: {'🟢 ON' if REACTION_ENABLED else '🔴 OFF'}",
        reply_markup=keyboard
    )


# ---------------- CALLBACK HANDLER ----------------
@app.on_callback_query(filters.regex("^react_"))
async def reaction_callback(client, query: CallbackQuery):
    global REACTION_ENABLED

    # Only admins/sudo can change the switch
    ok, debug = await is_admin_or_sudo(client, query.message)
    if not ok:
        return await query.answer("Only admins/sudo users can do this.", show_alert=True)

    action = query.data

    if action == "react_on":
        REACTION_ENABLED = True
        await SETTINGS.update_one({"_id": "switch"}, {"$set": {"enabled": True}}, upsert=True)
        return await query.edit_message_text("✅ **Auto-reactions Enabled**")

    elif action == "react_off":
        REACTION_ENABLED = False
        await SETTINGS.update_one({"_id": "switch"}, {"$set": {"enabled": False}}, upsert=True)
        return await query.edit_message_text("🛑 **Auto-reactions Disabled**")

    elif action == "react_status":
        return await query.answer(
            f"Auto-reactions are {'ON' if REACTION_ENABLED else 'OFF'}",
            show_alert=True
        )


# ---------------- addreact / delreact / reactlist / clearreact ----------------
@app.on_message(filters.command("addreact") & ~BANNED_USERS, group=1)
async def add_reaction_name(client, message: Message):
    ok, reason = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text(f"⚠️ Admins only.\nDebug: `{reason}`")

    if len(message.command) < 2:
        return await message.reply_text("Usage: `/addreact <username_or_keyword>`")

    raw = message.text.split(None, 1)[1].strip().lower().lstrip("@")

    if raw in custom_mentions:
        return await message.reply_text(f"ℹ️ `{raw}` is already in the list.")

    resolved_id = None
    try:
        user = await client.get_users(raw)
        resolved_id = user.id
    except Exception:
        resolved_id = None

    await COLLECTION.update_one(
        {"name": raw},
        {"$setOnInsert": {"name": raw}},
        upsert=True
    )
    custom_mentions.add(raw)

    if resolved_id:
        id_key = f"id:{resolved_id}"
        if id_key not in custom_mentions:
            await COLLECTION.update_one(
                {"name": id_key},
                {"$setOnInsert": {"name": id_key}},
                upsert=True
            )
            custom_mentions.add(id_key)

    msg = f"✨ Added `{raw}`"
    if resolved_id:
        msg += f" (id: `{resolved_id}`)"
    await message.reply_text(msg)


@app.on_message(filters.command("delreact") & ~BANNED_USERS, group=1)
async def delete_reaction_name(client, message: Message):
    ok, reason = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text(f"⚠️ Admins only.\nDebug: `{reason}`")

    if len(message.command) < 2:
        return await message.reply_text("Usage: `/delreact <keyword_or_username>`")

    raw = message.text.split(None, 1)[1].strip().lower().lstrip("@")
    removed = False

    if raw in custom_mentions:
        custom_mentions.remove(raw)
        await COLLECTION.delete_one({"name": raw})
        removed = True

    # Also try resolving username → id and remove id:...
    try:
        user = await client.get_users(raw)
        id_key = f"id:{user.id}"
        if id_key in custom_mentions:
            custom_mentions.remove(id_key)
            await COLLECTION.delete_one({"name": id_key})
            removed = True
    except Exception:
        pass

    if removed:
        return await message.reply_text(f"🗑 Removed `{raw}`.")
    return await message.reply_text(f"❌ `{raw}` not found.")


@app.on_message(filters.command("reactlist") & ~BANNED_USERS, group=1)
async def list_reactions(client, message: Message):
    if not custom_mentions:
        return await message.reply_text("No reaction triggers found.")
    text = "\n".join(f"• `{m}`" for m in sorted(custom_mentions))
    await message.reply_text(f"**🧠 Reaction Triggers:**\n{text}")


@app.on_message(filters.command("clearreact") & ~BANNED_USERS, group=1)
async def clear_reactions(client, message: Message):
    ok, reason = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text(f"⚠️ Admins only.\nDebug: `{reason}`")

    await COLLECTION.delete_many({})
    custom_mentions.clear()
    # reload MENTION_USERNAMES from config as baseline
    for n in (MENTION_USERNAMES or []):
        custom_mentions.add(n.lower().lstrip("@"))
    await message.reply_text("🧹 Cleared all reaction triggers.")


# ---------------- MENTION / KEYWORD TRIGGERED REACTIONS (ALWAYS ACTIVE) ----------------
# This handler reacts when custom_mentions match mention entities or keywords.
# It must remain active even if REACTION_ENABLED == False.
@app.on_message(
    (filters.text | filters.caption)
    & ~filters.regex(r"^/")  # ignore messages starting with slash (commands)
    & ~BANNED_USERS,
    group=5
)
async def react_on_mentions(client, message: Message):
    try:
        raw = message.text or message.caption or ""
        if not raw:
            return

        text = raw.lower()

        # quick guard against other command-like prefixes
        if text.startswith(("!", "$", ".", "#")):
            # NOTE: We purposely DO NOT ignore "/" here because we already excluded it.
            # These extra checks avoid reacting to bot command-like content.
            return

        chat_id = message.chat.id

        # Collect entities
        entities = (message.entities or []) + (message.caption_entities or [])
        mentioned_usernames = set()
        mentioned_ids = set()

        # Extract mentions and text_mentions
        for ent in entities:
            try:
                if ent.type == "mention":
                    src = message.text or message.caption
                    username = src[ent.offset:ent.offset + ent.length]
                    mentioned_usernames.add(username.lstrip("@").lower())

                elif ent.type == "text_mention" and ent.user:
                    mentioned_ids.add(ent.user.id)
                    if ent.user.username:
                        mentioned_usernames.add(ent.user.username.lower())
            except Exception:
                continue

        # 1) Username entity triggers
        for uname in mentioned_usernames:
            if uname in custom_mentions:
                try:
                    return await message.react(next_emoji(chat_id))
                except Exception:
                    try:
                        return await message.react("❤️")
                    except Exception:
                        return

        # 2) ID entity triggers
        for uid in mentioned_ids:
            if f"id:{uid}" in custom_mentions:
                try:
                    return await message.react(next_emoji(chat_id))
                except Exception:
                    try:
                        return await message.react("❤️")
                    except Exception:
                        return

        # 3) Keyword triggers (word boundary-ish)
        # Split into words and also check @name included
        words = set(text.replace("@", " @").split())
        for trig in custom_mentions:
            if trig.startswith("id:"):
                continue
            if trig in words or f"@{trig}" in words or trig in text:
                try:
                    return await message.react(next_emoji(chat_id))
                except Exception:
                    try:
                        return await message.react("❤️")
                    except Exception:
                        return

    except Exception as e:
        print(f"[react_on_mentions] error: {e}")


# ---------------- GLOBAL AUTO-REACTION (TOGGLED BY /reaction) ----------------
# This reacts to most messages (non-command) when REACTION_ENABLED is True.
# It is intentionally lower priority (runs later) to avoid stealing messages.
@app.on_message(
    (filters.text | filters.caption)
    & ~filters.command([])  # matches everything except commands
    & ~BANNED_USERS,
    group=50
)
async def auto_react(client, message: Message):
    # This global auto-react is controlled by the REACTION_ENABLED switch.
    # Mention/keyword reactions are handled by react_on_mentions above and always work.
    if not REACTION_ENABLED:
        return

    try:
        # ignore messages that look like commands
        if message.text and message.text.startswith("/"):
            return

        chat_id = message.chat.id
        # produce emoji and react
        emoji = next_emoji(chat_id)
        try:
            await message.react(emoji)
        except Exception:
            try:
                await message.react("❤️")
            except Exception:
                pass
    except Exception as e:
        print(f"[auto_react] error: {e}")
