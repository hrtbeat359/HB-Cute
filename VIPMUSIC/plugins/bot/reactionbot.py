# VIPMUSIC/plugins/bot/reactionbot.py
import asyncio
import random
import re
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
from config import MENTION_USERNAMES, START_REACTIONS, OWNER_ID
from VIPMUSIC import utils
from VIPMUSIC.utils.database import mongodb

try:
    from VIPMUSIC.misc import SUDOERS
except Exception:
    SUDOERS = set()

print("[reactionbot] loaded — merged reaction system")

# ---------------- DATABASE ----------------
COLLECTION = mongodb["reaction_mentions"]
SETTINGS = mongodb["reaction_settings"]

# ---------------- STATE ----------------
REACTION_ENABLED = True  # global default flag

# per-chat override cache (chat_id -> bool)
CHAT_REACTION_OVERRIDES: Dict[int, bool] = {}

# ---------------- CACHE ----------------
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

chat_used_reactions: Dict[int, Set[str]] = {}


def next_emoji(chat_id: int) -> str:
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


# schedule startup tasks safely
try:
    asyncio.get_event_loop().create_task(load_custom_mentions())
except RuntimeError:
    # fallback for when there's no running loop (tests / import-time)
    asyncio.ensure_future(load_custom_mentions())


# ---------------- LOAD SWITCH STATE + CHAT OVERRIDES ----------------
async def load_reaction_state_and_chat_overrides():
    global REACTION_ENABLED, CHAT_REACTION_OVERRIDES
    try:
        doc = await SETTINGS.find_one({"_id": "switch"})
        if doc is not None:
            REACTION_ENABLED = doc.get("enabled", True)
    except Exception as e:
        print(f"[Reaction Switch] DB read error: {e}")

    # Load any chat-specific overrides (documents where _id starts with "chat:")
    try:
        cursor = SETTINGS.find({"_id": {"$regex": r"^chat:"}})
        docs = await cursor.to_list(length=None)
        for d in docs:
            _id = d.get("_id")
            try:
                chat_id = int(_id.split(":", 1)[1])
                enabled = bool(d.get("enabled", True))
                CHAT_REACTION_OVERRIDES[chat_id] = enabled
            except Exception:
                continue
    except Exception as e:
        print(f"[Reaction Chat Overrides] DB load error: {e}")

    print(f"[Reaction Switch] Loaded => global={REACTION_ENABLED}, chat_overrides={len(CHAT_REACTION_OVERRIDES)}")


try:
    asyncio.get_event_loop().create_task(load_reaction_state_and_chat_overrides())
except RuntimeError:
    asyncio.ensure_future(load_reaction_state_and_chat_overrides())


# ---------------- ADMIN CHECK ----------------
async def is_admin_or_sudo(client, message_obj) -> Tuple[bool, Optional[str]]:
    """Return (True, None) if user is OWNER or in SUDOERS or admin in group.

    message_obj may be Message or CallbackQuery.message
    """
    # extract message and user
    message = getattr(message_obj, "message", None) if hasattr(message_obj, "message") else message_obj
    user = getattr(message, "from_user", None)
    chat = getattr(message, "chat", None)

    if not message or not user or not chat:
        return False, "invalid message"

    user_id = user.id
    chat_id = chat.id

    try:
        sudoers = set(SUDOERS or [])
    except Exception:
        sudoers = set()

    # owner or sudo always allowed
    if user_id == OWNER_ID or user_id in sudoers:
        return True, None

    # For non-group chats (private), only owner/sudo allowed to be considered admin
    chat_type = getattr(chat, "type", None)
    is_group_like = False

    try:
        if isinstance(chat_type, ChatType):
            is_group_like = chat_type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL)
        elif isinstance(chat_type, str):
            is_group_like = chat_type.lower() in ("group", "supergroup", "channel")
    except Exception:
        is_group_like = False

    if not is_group_like:
        return False, f"chat_type={chat_type}"

    # check membership status in group
    try:
        member = await client.get_chat_member(chat_id, user_id)
        status = member.status

        if isinstance(status, ChatMemberStatus):
            if status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                return True, None
        elif isinstance(status, str):
            if status.lower() in ("creator", "owner", "administrator", "admin"):
                return True, None

        return False, f"user_status={status}"

    except Exception as e:
        return False, f"get_chat_member_error={e}"


# ---------------- HELPERS FOR DB OVERRIDES ----------------
def chat_settings_key(chat_id: int) -> str:
    return f"chat:{chat_id}"


async def set_chat_reaction_enabled(chat_id: int, enabled: bool):
    key = chat_settings_key(chat_id)
    await SETTINGS.update_one({"_id": key}, {"$set": {"enabled": bool(enabled)}}, upsert=True)
    CHAT_REACTION_OVERRIDES[chat_id] = bool(enabled)


async def clear_chat_reaction_override(chat_id: int):
    key = chat_settings_key(chat_id)
    await SETTINGS.delete_one({"_id": key})
    if chat_id in CHAT_REACTION_OVERRIDES:
        del CHAT_REACTION_OVERRIDES[chat_id]


def is_reaction_enabled_for_chat(chat_id: int) -> bool:
    """Decide if reactions are enabled in the given chat.

    Precedence:
    - If chat override exists -> use it
    - Else use global REACTION_ENABLED
    """
    return CHAT_REACTION_OVERRIDES.get(chat_id, REACTION_ENABLED)


# ---------------- /reaction COMMAND ----------------
@app.on_message(filters.command("reaction", prefixes=["/"]))
async def react_command(client, message: Message):
    global REACTION_ENABLED

    ok, debug = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text(
            "⚠️ Only admins/sudo users may control reaction system.\n\n"
            f"Debug: {debug}"
        )

    chat_id = message.chat.id

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Enable Global", callback_data="react_on"),
                InlineKeyboardButton("🛑 Disable Global", callback_data="react_off"),
            ],
            [
                InlineKeyboardButton("✅ Enable for this chat", callback_data=f"react_chat_on:{chat_id}"),
                InlineKeyboardButton("🛑 Disable for this chat", callback_data=f"react_chat_off:{chat_id}"),
            ],
            [
                InlineKeyboardButton("🧹 Clear chat override", callback_data=f"react_chat_clear:{chat_id}"),
                InlineKeyboardButton("🔍 Status", callback_data="react_status")
            ]
        ]
    )

    await message.reply_text(
        f"**Reaction System Control**\n\n"
        f"Global state: {'🟢 ON' if REACTION_ENABLED else '🔴 OFF'}\n"
        f"This chat: {'🟢 ON' if is_reaction_enabled_for_chat(chat_id) else '🔴 OFF'}\n\n"
        "Use the buttons below to change global or per-chat behavior.",
        reply_markup=keyboard
    )


# ---------------- CALLBACK ----------------
@app.on_callback_query(filters.regex("^react_"))
async def reaction_callback(client, query: CallbackQuery):
    global REACTION_ENABLED

    # Use the message attached to callback for admin check
    ok, debug = await is_admin_or_sudo(client, query.message)
    if not ok:
        return await query.answer("Only admins/sudo users can do this.", show_alert=True)

    action = query.data

    try:
        if action == "react_on":
            REACTION_ENABLED = True
            await SETTINGS.update_one({"_id": "switch"}, {"$set": {"enabled": True}}, upsert=True)
            return await query.edit_message_text("✅ **Auto-reactions Enabled (GLOBAL)**")

        elif action == "react_off":
            REACTION_ENABLED = False
            await SETTINGS.update_one({"_id": "switch"}, {"$set": {"enabled": False}}, upsert=True)
            return await query.edit_message_text("🛑 **Auto-reactions Disabled (GLOBAL)**")

        elif action == "react_status":
            # show both global and chat state
            chat_id = query.message.chat.id if query.message and query.message.chat else None
            chat_state = "N/A"
            if chat_id is not None:
                chat_state = "🟢 ON" if is_reaction_enabled_for_chat(chat_id) else "🔴 OFF"
            return await query.answer(
                f"Global: {'ON' if REACTION_ENABLED else 'OFF'}\nChat: {chat_state}",
                show_alert=True
            )

        # per-chat actions contain a colon with chat id
        elif action.startswith("react_chat_on:"):
            _chat = int(action.split(":", 1)[1])
            await set_chat_reaction_enabled(_chat, True)
            return await query.edit_message_text(f"✅ **Reactions enabled for chat {_chat}**")

        elif action.startswith("react_chat_off:"):
            _chat = int(action.split(":", 1)[1])
            await set_chat_reaction_enabled(_chat, False)
            return await query.edit_message_text(f"🛑 **Reactions disabled for chat {_chat}**")

        elif action.startswith("react_chat_clear:"):
            _chat = int(action.split(":", 1)[1])
            await clear_chat_reaction_override(_chat)
            return await query.edit_message_text(f"🧹 **Cleared reaction override for chat {_chat} (now uses global)**")

    except Exception as e:
        print(f"[reaction_callback] error: {e}")
        return await query.answer("Operation failed.", show_alert=True)


# ---------------- addreact / delreact / reactlist / clearreact ----------------
@app.on_message(filters.command("addreact", prefixes=["/"]))
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


@app.on_message(filters.command("delreact", prefixes=["/"]))
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


@app.on_message(filters.command("reactlist", prefixes=["/"]))
async def list_reactions(client, message: Message):
    if not custom_mentions:
        return await message.reply_text("No reaction triggers found.")
    text = "\n".join(f"• `{m}`" for m in sorted(custom_mentions))
    await message.reply_text(f"**🧠 Reaction Triggers:**\n{text}")


@app.on_message(filters.command("clearreact", prefixes=["/"]))
async def clear_reactions(client, message: Message):
    ok, reason = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text(f"⚠️ Admins only.\nDebug: `{reason}`")

    await COLLECTION.delete_many({})
    custom_mentions.clear()
    for n in (MENTION_USERNAMES or []):
        custom_mentions.add(n.lower().lstrip("@"))
    await message.reply_text("🧹 Cleared all reaction triggers.")


# ---------------- HELPERS FOR MATCHING ----------------
WORD_RE = re.compile(r"\b([\w@:\-\.]+)\b", flags=re.UNICODE)


def message_words(text: str):
    return set(m.group(1).lower() for m in WORD_RE.finditer(text))


# ---------------- MENTION / KEYWORD TRIGGERED REACTIONS ----------------
# NOTE: Keyword and mention reactions MUST fire even if auto-reactions are OFF
@app.on_message(
    (filters.text | filters.caption)
    & ~filters.regex(r"^[\\/!.#].*")
)
async def react_on_mentions(client, message: Message):
    try:
        raw = message.text or message.caption or ""
        if not raw:
            return

        # Ignore bot commands starting with common prefixes
        if raw.strip().startswith(("/", "!", "$", ".", "#")):
            return

        text = raw.lower()
        chat_id = message.chat.id

        entities = (message.entities or []) + (message.caption_entities or [])
        mentioned_usernames = set()
        mentioned_ids = set()

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

        # React for explicit mentions if matched
        for uname in mentioned_usernames:
            if uname in custom_mentions:
                # For mention triggers we react regardless of chat/global auto-react flag
                try:
                    return await message.react(next_emoji(chat_id))
                except Exception:
                    try:
                        return await message.react("❤️")
                    except Exception:
                        return

        for uid in mentioned_ids:
            if f"id:{uid}" in custom_mentions:
                try:
                    return await message.react(next_emoji(chat_id))
                except Exception:
                    try:
                        return await message.react("❤️")
                    except Exception:
                        return

        # Keyword detection (must work in private and group chats)
        words = message_words(text)
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


# ---------------- GLOBAL AUTO-REACTION ----------------
# replaced ~filters.command() (which requires args) with a prefix-regex exclusion,
# consistent with react_on_mentions, to avoid the TypeError.
@app.on_message(
    (filters.text | filters.caption)
    & ~filters.regex(r"^[\\/!.#].*")
)
async def auto_react(client, message: Message):
    # Auto reactions follow the REACTION_ENABLED flag and per-chat overrides.
    try:
        raw = message.text or message.caption or ""
        if not raw:
            return

        # Ignore bot commands and common prefixes
        if raw.strip().startswith(("/", "!", "$", ".", "#")):
            return

        chat_id = message.chat.id

        # decide if reactions are enabled for this chat
        if not is_reaction_enabled_for_chat(chat_id):
            return

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
