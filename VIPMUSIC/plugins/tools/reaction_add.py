import asyncio
import random
import time
from typing import Set, Tuple, Optional

from pyrogram import filters
from pyrogram.types import Message, MessageEntity
from pyrogram.enums import ChatMemberStatus
from VIPMUSIC import app
from config import BANNED_USERS, MENTION_USERNAMES, START_REACTIONS, OWNER_ID
from VIPMUSIC.utils.database import mongodb, get_sudoers

# ---------------- DB ----------------
COLLECTION = mongodb["reaction_mentions"]

# ---------------- CACHES ----------------
# triggers stored as plain tokens (username without @, words) and "id:<num>" for user-id triggers
custom_mentions: Set[str] = set(x.lower().lstrip("@") for x in MENTION_USERNAMES)

# ---------------- util load ----------------
async def load_custom_mentions():
    try:
        docs = await COLLECTION.find().to_list(None)
        for doc in docs:
            name = doc.get("name")
            if name:
                custom_mentions.add(str(name).lower().lstrip("@"))
        print(f"[Reaction Manager] Loaded {len(custom_mentions)} mention triggers.")
    except Exception as e:
        print(f"[Reaction Manager] DB load error: {e}")

asyncio.get_event_loop().create_task(load_custom_mentions())


# ---------------- admin helpers ----------------
async def fetch_admins(client, chat_id: int) -> Set[int]:
    ids = set()
    try:
        async for memb in client.get_chat_members(chat_id, filter="administrators"):
            if getattr(memb, "user", None):
                ids.add(memb.user.id)
    except Exception as e:
        print(f"[fetch_admins] error fetching admins for {chat_id}: {e}")
    return ids


async def get_chat_and_linked(client, chat_id: int):
    """Return (chat_obj, linked_chat_id or None) safely."""
    try:
        chat = await client.get_chat(chat_id)
        linked = None
        # Pyrogram Chat object may have linked_chat or linked_chat_id depending on version
        if getattr(chat, "linked_chat", None):
            linked = getattr(chat.linked_chat, "id", None)
        elif getattr(chat, "linked_chat_id", None):
            linked = getattr(chat, "linked_chat_id", None)
        return chat, linked
    except Exception as e:
        print(f"[get_chat_and_linked] error for {chat_id}: {e}")
        return None, None


# ---------------- admin check (robust + debug) ----------------
async def is_admin_or_sudo(client, message: Message) -> Tuple[bool, Optional[str]]:
    """
    Returns (is_admin_bool, debug_string_or_None)
    debug string is None on success; on failure contains details to help diagnose.
    """
    if not message.from_user:
        return False, "no from_user on message"

    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_type = message.chat.type

    # check sudoers/owner
    try:
        sudoers = await get_sudoers()
    except Exception as e:
        sudoers = set()
        print(f"[is_admin_or_sudo] get_sudoers error: {e}")

    if user_id == OWNER_ID or user_id in sudoers:
        return True, None

    if chat_type not in ("group", "supergroup"):
        return False, "not a group or supergroup"

    # 1) direct get_chat_member
    member_info = None
    try:
        member = await client.get_chat_member(chat_id, user_id)
        member_info = member
        status = getattr(member, "status", None)
        if status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return True, None
    except Exception as e:
        # record the exception for debug
        dm_get_error = f"get_chat_member error: {e}"
        print(f"[is_admin_or_sudo] get_chat_member exception: {e}")
    else:
        dm_get_error = None

    # 2) fetch admin list
    admin_ids = set()
    try:
        async for adm in client.get_chat_members(chat_id, filter="administrators"):
            if getattr(adm, "user", None):
                admin_ids.add(adm.user.id)
    except Exception as e:
        admin_list_error = f"admin list fetch error: {e}"
        print(f"[is_admin_or_sudo] admin list fetch exception: {e}")
    else:
        admin_list_error = None

    if user_id in admin_ids:
        return True, None

    # 3) linked chat channel check
    linked_chat_id = None
    linked_status = None
    try:
        chat, linked_chat_id = await get_chat_and_linked(client, chat_id)
        if linked_chat_id:
            try:
                linked_member = await client.get_chat_member(linked_chat_id, user_id)
                linked_status = getattr(linked_member, "status", None)
                if linked_status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                    return True, None
            except Exception as e:
                print(f"[is_admin_or_sudo] linked chat get_chat_member error: {e}")
    except Exception as e:
        print(f"[is_admin_or_sudo] linked chat fetch error: {e}")

    # 4) final fallback: check whether bot itself is admin (if bot is not admin, many checks won't work)
    bot_id = None
    bot_status = None
    try:
        me = await client.get_me()
        bot_id = me.id
        try:
            bot_member = await client.get_chat_member(chat_id, bot_id)
            bot_status = getattr(bot_member, "status", None)
        except Exception as e:
            bot_status = f"get_chat_member failed: {e}"
    except Exception as e:
        print(f"[is_admin_or_sudo] get_me failed: {e}")

    # Build debug string
    debug_lines = []
    debug_lines.append(f"user_id={user_id}")
    debug_lines.append(f"user_status_direct={getattr(member_info, 'status', None)}")
    debug_lines.append(f"dm_get_error={dm_get_error}")
    debug_lines.append(f"admin_ids_count={len(admin_ids)}")
    # include a few admin ids sample
    sample_admins = ",".join(str(x) for x in list(admin_ids)[:10])
    debug_lines.append(f"admin_ids_sample={sample_admins or 'none'}")
    debug_lines.append(f"linked_chat_id={linked_chat_id}")
    debug_lines.append(f"linked_status={linked_status}")
    debug_lines.append(f"bot_id={bot_id}")
    debug_lines.append(f"bot_status={bot_status}")
    debug_lines.append(f"OWNER_ID={OWNER_ID}")
    if sudoers:
        debug_lines.append(f"sudoers_sample={','.join(str(x) for x in list(sudoers)[:5])}")

    debug_text = "\n".join(debug_lines)
    # return False with debug text so caller can report it
    return False, debug_text


# ---------------- command: /addreact ----------------
@app.on_message(filters.command("addreact") & ~BANNED_USERS)
async def add_reaction_name(client, message: Message):
    """Add a username or keyword to the reaction list. Resolves usernames to ids."""
    ok, debug = await is_admin_or_sudo(client, message)
    if not ok:
        # send debug info to chat (owner/senders will see it) to diagnose why Telegram didn't mark you admin
        await message.reply_text(
            "⚠️ Only admins or sudo users can add reaction names.\n\n"
            "Debug info:\n" + (debug or "no debug"),
            quote=True,
        )
        print("[add_reaction_name] admin check failed:\n" + (debug or "no debug"))
        return

    if len(message.command) < 2:
        return await message.reply_text("Usage: `/addreact <keyword_or_username>`", quote=True)

    raw = message.text.split(None, 1)[1].strip()
    if not raw:
        return await message.reply_text("Usage: `/addreact <keyword_or_username>`", quote=True)

    name = raw.lower().lstrip("@")

    # Try to resolve username to user id (so text_mention entities match)
    resolved_id = None
    try:
        # get_users accepts usernames like "username" or "tg://user?id=123"
        user = await client.get_users(name)
        if getattr(user, "id", None):
            resolved_id = user.id
    except Exception:
        # ignore resolve errors; still store text form
        resolved_id = None

    # store username form
    try:
        await COLLECTION.insert_one({"name": name})
    except Exception as e:
        print(f"[add_reaction_name] DB insert error (username): {e}")

    custom_mentions.add(name)
    # if resolved to an id, also store id form
    if resolved_id:
        id_token = f"id:{resolved_id}"
        try:
            await COLLECTION.insert_one({"name": id_token})
        except Exception as e:
            # duplicate inserts are fine; ignore
            print(f"[add_reaction_name] DB insert error (id): {e}")
        custom_mentions.add(id_token)

    added_msg = f"✨ Added `{name}`"
    if resolved_id:
        added_msg += f" (resolved id: `{resolved_id}`)"
    added_msg += " to the mention reaction list."
    await message.reply_text(added_msg, quote=True)


# ---------------- command: /delreact ----------------
@app.on_message(filters.command("delreact") & ~BANNED_USERS)
async def delete_reaction_name(client, message: Message):
    ok, debug = await is_admin_or_sudo(client, message)
    if not ok:
        await message.reply_text(
            "⚠️ Only admins or sudo users can delete reaction names.\n\nDebug info:\n" + (debug or "no debug"),
            quote=True,
        )
        print("[delete_reaction_name] admin check failed:\n" + (debug or "no debug"))
        return

    if len(message.command) < 2:
        return await message.reply_text("Usage: `/delreact <keyword_or_username>`", quote=True)

    raw = message.text.split(None, 1)[1].strip()
    if not raw:
        return await message.reply_text("Usage: `/delreact <keyword_or_username>`", quote=True)

    name = raw.lower().lstrip("@")
    removed_any = False

    # remove username form
    if name in custom_mentions:
        custom_mentions.discard(name)
        try:
            await COLLECTION.delete_one({"name": name})
        except Exception as e:
            print(f"[delete_reaction_name] DB delete error (name): {e}")
        removed_any = True

    # if it's a username, also try to resolve id and remove id: token
    try:
        user = await client.get_users(name)
        if getattr(user, "id", None):
            id_token = f"id:{user.id}"
            if id_token in custom_mentions:
                custom_mentions.discard(id_token)
                try:
                    await COLLECTION.delete_one({"name": id_token})
                except Exception as e:
                    print(f"[delete_reaction_name] DB delete error (id): {e}")
                removed_any = True
    except Exception:
        pass

    if removed_any:
        await message.reply_text(f"🗑 Removed `{name}` from mention list.", quote=True)
    else:
        await message.reply_text(f"❌ `{name}` not found in mention list.", quote=True)


# ---------------- command: /reactlist ----------------
@app.on_message(filters.command("reactlist") & ~BANNED_USERS)
async def list_reactions(client, message: Message):
    if not custom_mentions:
        return await message.reply_text("ℹ️ No mention triggers found.", quote=True)
    items = sorted(custom_mentions)
    # don't show raw id tokens directly to users; present friendly view
    display = []
    for it in items:
        if it.startswith("id:"):
            display.append(f"(user id) `{it}`")
        else:
            display.append(f"`{it}`")
    msg = "**🧠 Reaction Trigger List:**\n" + "\n".join(f"• {x}" for x in display)
    await message.reply_text(msg, quote=True)


# ---------------- helpers: extract entities ----------------
def extract_usernames_and_ids_from_entities(message: Message) -> Tuple[Set[str], Set[int]]:
    """Return (usernames_set, user_ids_set) found in message entities (mention + text_mention)."""
    usernames = set()
    user_ids = set()
    text_source = message.text or message.caption or ""
    entities = (message.entities or []) + (message.caption_entities or [])
    for ent in entities:
        try:
            if ent.type == "mention":
                start = ent.offset
                end = ent.offset + ent.length
                uname = text_source[start:end].lstrip("@").lower()
                if uname:
                    usernames.add(uname)
            elif ent.type == "text_mention":
                # text_mention contains .user
                if getattr(ent, "user", None):
                    if getattr(ent.user, "username", None):
                        usernames.add(ent.user.username.lower())
                    user_ids.add(ent.user.id)
        except Exception:
            continue
    return usernames, user_ids


# ---------------- actual reacting logic ----------------
@app.on_message((filters.text | filters.caption) & ~BANNED_USERS)
async def react_on_mentions(client, message: Message):
    try:
        text = (message.text or message.caption or "").lower()
        usernames, user_ids = extract_usernames_and_ids_from_entities(message)

        # 1) check entity-based username mentions first
        for uname in usernames:
            if uname in custom_mentions:
                await message.react(random.choice(START_REACTIONS))
                return
            # also check id token if someone stored the username resolved to id earlier
            # attempt to resolve to id is not done here (too heavy)

        # 2) check entity-based user ids (text_mention)
        for uid in user_ids:
            if f"id:{uid}" in custom_mentions:
                await message.react(random.choice(START_REACTIONS))
                return

        # 3) check plain keyword anywhere in combined text
        for trigger in custom_mentions:
            # skip id: tokens for text matching
            if trigger.startswith("id:"):
                continue
            if trigger and trigger in text:
                await message.react(random.choice(START_REACTIONS))
                return
    except Exception as e:
        print(f"[react_on_mentions] error: {e}")
        return
