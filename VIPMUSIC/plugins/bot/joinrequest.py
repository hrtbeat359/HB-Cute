# requestchat.py
# Join Request module for VIPMUSIC (HB-Cute)
# Features:
#  - Per-group enable/disable join-request handling (group owner only)
#  - Admin-only Approve / Decline buttons
#  - Auto-approval mode (group owner only)
#  - Per-group log chat id
# Requires: pyrogram v2.x, motor

import os
import asyncio
from typing import Optional

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ChatJoinRequest,
    Message,
)
from pyrogram.enums import ChatMemberStatus

from VIPMUSIC import app  # ensure VIPMUSIC package exports app = Client(...)
import motor.motor_asyncio
from pymongo import ReturnDocument

# Mongo setup
MONGO_URL = os.getenv("MONGO_URL", None)
if not MONGO_URL:
    raise RuntimeError("MONGO_URL env var is required by requestchat.py")

mongo = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo.get_database("vipmusic")
settings_coll = db.get_collection("join_request_settings")  # documents keyed by chat_id

# Schemas for collection documents:
# {
#   "chat_id": int,
#   "enabled": bool,         # whether module handles join requests for this group
#   "auto_approve": bool,    # if true, auto-approve join requests
#   "log_chat_id": int|null, # chat id where logs will be sent (optional)
# }

# -------------------------
# Helper functions
# -------------------------
async def get_settings(chat_id: int) -> dict:
    doc = await settings_coll.find_one({"chat_id": chat_id})
    if not doc:
        doc = {"chat_id": chat_id, "enabled": False, "auto_approve": False, "log_chat_id": None}
        await settings_coll.insert_one(doc)
    return doc


async def set_settings(chat_id: int, patch: dict) -> dict:
    doc = await settings_coll.find_one_and_update(
        {"chat_id": chat_id},
        {"$set": patch},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc


async def is_group_owner(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status == ChatMemberStatus.OWNER
    except Exception:
        return False


async def is_group_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def send_log(client, log_chat_id: Optional[int], text: str, **kwargs):
    if not log_chat_id:
        return
    try:
        await client.send_message(log_chat_id, text, **kwargs)
    except Exception:
        # best effort - ignore failures
        pass


# -------------------------
# Commands (group owner only for settings)
# -------------------------

# Enable join request handling for this group
@app.on_message(filters.command("jr_on") & filters.group)
async def cmd_jr_on(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_group_owner(client, chat_id, user_id):
        await message.reply_text("⚠️ Only the group owner can change join-request settings.")
        return

    await set_settings(chat_id, {"enabled": True})
    await message.reply_text("✅ Join-request approval enabled for this group.\nAdmins will receive Approve/Decline buttons.")


@app.on_message(filters.command("jr_off") & filters.group)
async def cmd_jr_off(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_group_owner(client, chat_id, user_id):
        await message.reply_text("⚠️ Only the group owner can change join-request settings.")
        return

    await set_settings(chat_id, {"enabled": False})
    await message.reply_text("✅ Join-request approval disabled for this group.")


@app.on_message(filters.command("jr_auto_on") & filters.group)
async def cmd_jr_auto_on(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_group_owner(client, chat_id, user_id):
        await message.reply_text("⚠️ Only the group owner can change auto-approve mode.")
        return

    await set_settings(chat_id, {"auto_approve": True})
    await message.reply_text("✅ Auto-approval enabled. Join requests will be approved automatically.")


@app.on_message(filters.command("jr_auto_off") & filters.group)
async def cmd_jr_auto_off(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_group_owner(client, chat_id, user_id):
        await message.reply_text("⚠️ Only the group owner can change auto-approve mode.")
        return

    await set_settings(chat_id, {"auto_approve": False})
    await message.reply_text("✅ Auto-approval disabled. Join requests will require admin approval.")


@app.on_message(filters.command("jr_setlog") & filters.group)
async def cmd_jr_setlog(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_group_owner(client, chat_id, user_id):
        await message.reply_text("⚠️ Only the group owner can set the log chat.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("Usage: /jr_setlog <chat_id or @username>\nExample: /jr_setlog -1001234567890")
        return

    target = args[1].strip()
    try:
        # resolve username/chat id
        if target.startswith("@"):
            target_chat = await client.get_chat(target)
            target_id = target_chat.id
        else:
            # try int
            target_id = int(target)
            # validate existence by fetching
            _ = await client.get_chat(target_id)
    except Exception as e:
        await message.reply_text(f"❌ Could not resolve that chat: {e}")
        return

    await set_settings(chat_id, {"log_chat_id": target_id})
    await message.reply_text(f"✅ Log chat set to `{target_id}`", parse_mode="markdown")


@app.on_message(filters.command("jr_status") & filters.group)
async def cmd_jr_status(client, message: Message):
    chat_id = message.chat.id
    s = await get_settings(chat_id)
    enabled = s.get("enabled", False)
    auto = s.get("auto_approve", False)
    log = s.get("log_chat_id", None)
    text = (
        f"🔎 Join-request settings for **{message.chat.title or chat_id}** (`{chat_id}`):\n\n"
        f"• Enabled: `{enabled}`\n"
        f"• Auto-approve: `{auto}`\n"
        f"• Log chat id: `{log}`"
    )
    await message.reply_text(text, parse_mode="markdown")


# -------------------------
# Chat join request handler
# -------------------------
@app.on_chat_join_request()
async def handle_chat_join_request(client, chat_join_request: ChatJoinRequest):
    """
    ChatJoinRequest object fields: .chat, .from_user, .user_chat_id, .bio, etc.
    """
    chat = chat_join_request.chat
    requester = chat_join_request.from_user
    chat_id = chat.id
    user_id = requester.id

    s = await get_settings(chat_id)
    if not s.get("enabled", False):
        # module disabled for this group -> ignore (no intervention)
        return

    # If auto approve enabled -> approve immediately
    if s.get("auto_approve", False):
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            # log
            log_text = (
                f"✅ Auto-approved join request:\n"
                f"Group: {chat.title or chat_id} (`{chat_id}`)\n"
                f"User: {requester.mention} (`{user_id}`)"
            )
            await send_log(client, s.get("log_chat_id"), log_text, disable_web_page_preview=True)
        except Exception as e:
            # log failure
            await send_log(
                client,
                s.get("log_chat_id"),
                f"❌ Failed to auto-approve request for {requester.mention} (`{user_id}`) in `{chat_id}`.\nError: {e}",
            )
        return

    # Manual approval flow: notify group (or a pinned admin chat) with Approve/Decline buttons.
    # We will post the approval message into the group itself (admins will see and press).
    # Message text:
    text = (
        f"🔔 New join request in **{chat.title or chat_id}**\n\n"
        f"User: {requester.mention} (`{user_id}`)\n"
        f"Bio: `{chat_join_request.bio}`\n\n"
        f"Admins — tap to Approve or Decline."
    )
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"jr:approve:{chat_id}:{user_id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"jr:decline:{chat_id}:{user_id}"),
            ],
        ]
    )

    try:
        sent = await client.send_message(chat_id, text, reply_markup=buttons, parse_mode="markdown")
    except Exception as e:
        # can't send message to group (maybe bot not allowed) -> attempt to log and exit
        await send_log(
            client,
            s.get("log_chat_id"),
            f"❌ Could not post join-request for `{chat_id}`. Error: {e}\nRequest by {requester.mention} (`{user_id}`).",
        )
        return

    # optionally log that a request was posted
    await send_log(
        client,
        s.get("log_chat_id"),
        f"ℹ️ Join request posted in `{chat_id}` for {requester.mention} (`{user_id}`)."
    )


# -------------------------
# Callback Query Handler (Approve / Decline)
# -------------------------
@app.on_callback_query(filters.regex(r"^jr:(approve|decline):-?\d+:\d+$"))
async def jr_callback(client, callback: CallbackQuery):
    data = callback.data  # e.g. "jr:approve:CHATID:USERID"
    parts = data.split(":")
    action = parts[1]
    chat_id = int(parts[2])
    user_id = int(parts[3])
    caller = callback.from_user

    # Ensure caller is admin in target chat
    if not await is_group_admin(client, chat_id, caller.id):
        await callback.answer("❌ Only group admins can approve or decline join requests.", show_alert=True)
        return

    # Basic check: bot itself must be admin to perform approve/decline
    try:
        me_member = await client.get_chat_member(chat_id, (await client.get_me()).id)
        if me_member.status != ChatMemberStatus.ADMINISTRATOR:
            await callback.answer("❌ I must be an admin in this group to approve/decline requests.", show_alert=True)
            return
    except Exception:
        await callback.answer("❌ Unable to verify my admin status in the group.", show_alert=True)
        return

    s = await get_settings(chat_id)

    if action == "approve":
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            # edit original message
            try:
                await callback.edit_message_text(
                    f"✅ Request approved by {caller.mention}.\nUser: `{user_id}`",
                    parse_mode="markdown"
                )
            except Exception:
                # ignore edit errors
                pass

            # log
            log_text = (
                f"✅ Join request approved.\n"
                f"Group: {chat_id}\n"
                f"User id: `{user_id}`\n"
                f"Approved by: {caller.mention} (`{caller.id}`)"
            )
            await send_log(client, s.get("log_chat_id"), log_text, disable_web_page_preview=True)
            await callback.answer("✅ Approved.", show_alert=False)
        except Exception as e:
            await callback.answer(f"❌ Failed to approve: {e}", show_alert=True)

    elif action == "decline":
        try:
            await client.decline_chat_join_request(chat_id, user_id)
            try:
                await callback.edit_message_text(
                    f"❌ Request declined by {caller.mention}.\nUser: `{user_id}`",
                    parse_mode="markdown"
                )
            except Exception:
                pass

            # log
            log_text = (
                f"❌ Join request declined.\n"
                f"Group: {chat_id}\n"
                f"User id: `{user_id}`\n"
                f"Declined by: {caller.mention} (`{caller.id}`)"
            )
            await send_log(client, s.get("log_chat_id"), log_text, disable_web_page_preview=True)
            await callback.answer("❌ Declined.", show_alert=False)
        except Exception as e:
            await callback.answer(f"❌ Failed to decline: {e}", show_alert=True)


# -------------------------
# Clean-up: optional function to remove settings when group removed or admin wants it
# -------------------------
@app.on_message(filters.command("jr_clear") & filters.group)
async def cmd_jr_clear(client, message: Message):
    # optional: owner only
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_group_owner(client, chat_id, user_id):
        await message.reply_text("⚠️ Only the group owner can clear join-request settings.")
        return
    await settings_coll.delete_one({"chat_id": chat_id})
    await message.reply_text("✅ Join-request settings cleared for this group.")


# End of requestchat.py
