# requestchat.py
# Join Request module for VIPMUSIC (HB-Cute)
# Requirements: pyrogram (v2.x), motor (asyncio MongoDB client)
# Place this module in plugins (or wherever VIPMUSIC loads handlers).
# Ensure VIPMUSIC exports `app` (pyrogram Client) and MONGO_URL env var is set.

import os
import asyncio
import datetime
from typing import Optional, Dict, Any, List

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ChatJoinRequest,
    Message,
    User,
)
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError

# VIPMUSIC app (should be your pyrogram.Client instance)
from VIPMUSIC import app

# MongoDB
import motor.motor_asyncio
from pymongo import ReturnDocument

MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority")
if not MONGO_URL:
    raise RuntimeError("MONGO_URL environment variable is required by requestchat.py")

mongo = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo.get_database("vipmusic")
settings_coll = db.get_collection("join_request_settings")

# Temporary in-memory states (admin decline reason prompts)
# Structure: {admin_id: {"chat_id": int, "user_id": int, "action": "decline", "payload": {...}, "expires_at": datetime}}
PENDING_REASON_PROMPTS: Dict[int, Dict[str, Any]] = {}

# Helper: get timestamp string
def ts() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

# -------------------------
# DB helpers
# -------------------------
async def get_settings(chat_id: int) -> dict:
    doc = await settings_coll.find_one({"chat_id": chat_id})
    if not doc:
        doc = {
            "chat_id": chat_id,
            "enabled": False,
            "auto_approve": False,
            "log_chat_id": None,
        }
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

# -------------------------
# Permission checks
# -------------------------
async def is_group_owner(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status == ChatMemberStatus.OWNER
    except RPCError:
        return False

async def is_group_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except RPCError:
        return False

# send log to configured log chat (best-effort)
async def send_log(client, log_chat_id: Optional[int], text: str, **kwargs):
    if not log_chat_id:
        return
    try:
        await client.send_message(log_chat_id, text, **kwargs)
    except RPCError:
        # ignore logging failures
        pass

# -------------------------
# UI helpers
# -------------------------
def make_request_buttons(chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"jr:approve:{chat_id}:{user_id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"jr:decline_prompt:{chat_id}:{user_id}"),
            ],
            [
                InlineKeyboardButton("📝 Decline w/ reason", callback_data=f"jr:decline_reason:{chat_id}:{user_id}"),
                InlineKeyboardButton("ℹ️ View user", callback_data=f"jr:view:{chat_id}:{user_id}"),
            ],
        ]
    )
    return kb

def make_owner_settings_kb(chat_id: int, enabled: bool, auto: bool, log_id: Optional[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Enabled ✅" if enabled else "Enabled ❌", callback_data=f"jr:toggle_enabled:{chat_id}"),
                InlineKeyboardButton("Auto ✅" if auto else "Auto ❌", callback_data=f"jr:toggle_auto:{chat_id}"),
            ],
            [
                InlineKeyboardButton("Set Log Chat", callback_data=f"jr:set_log:{chat_id}"),
                InlineKeyboardButton("Clear Log", callback_data=f"jr:clear_log:{chat_id}"),
            ],
            [
                InlineKeyboardButton("Approve All Pending", callback_data=f"jr:approve_all:{chat_id}"),
                InlineKeyboardButton("View Pending", callback_data=f"jr:view_pending:{chat_id}"),
            ],
        ]
    )
    return kb

def nice_user_details(user: User) -> str:
    uname = f"@{user.username}" if user.username else "—"
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if not name:
        name = "No name"
    return f"<b>{name}</b> ({uname})\nID: <code>{user.id}</code>"

# -------------------------
# Commands (owner-only settings) & menu
# -------------------------
# Owner inline menu trigger: /jr_menu (must be used inside the target group by owner)
@app.on_message(filters.command("jr_menu") & filters.group)
async def cmd_jr_menu(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_group_owner(client, chat_id, user_id):
        await message.reply_text("⚠️ Only the group *owner* can open join-request settings.", parse_mode="html")
        return

    s = await get_settings(chat_id)
    kb = make_owner_settings_kb(chat_id, s.get("enabled", False), s.get("auto_approve", False), s.get("log_chat_id"))
    text = (
        f"⚙️ Join Request Settings for <b>{message.chat.title or chat_id}</b>\n\n"
        f"• Enabled: <code>{s.get('enabled', False)}</code>\n"
        f"• Auto-approve: <code>{s.get('auto_approve', False)}</code>\n"
        f"• Log chat: <code>{s.get('log_chat_id')}</code>\n\n"
        f"Use the buttons below to change options. Owner only."
    )
    await message.reply_text(text, reply_markup=kb, parse_mode="html")

# -------------------------
# Settings callbacks (owner-only)
# -------------------------
@app.on_callback_query(filters.regex(r"^jr:(toggle_enabled|toggle_auto|set_log|clear_log|approve_all|view_pending):-?\d+$"))
async def jr_owner_cb(client, cq: CallbackQuery):
    data = cq.data  # jr:toggle_enabled:CHATID etc
    parts = data.split(":")
    action = parts[1]
    chat_id = int(parts[2])
    caller = cq.from_user

    # verify caller is owner of that chat
    if not await is_group_owner(client, chat_id, caller.id):
        await cq.answer("Only the group owner can use this menu.", show_alert=True)
        return

    s = await get_settings(chat_id)

    if action == "toggle_enabled":
        new = not s.get("enabled", False)
        await set_settings(chat_id, {"enabled": new})
        await cq.answer("Toggled enabled.", show_alert=False)
        await cq.edit_message_text(
            f"✅ Enabled set to <code>{new}</code> for chat <b>{chat_id}</b>.\nUse /jr_menu to reopen.", parse_mode="html"
        )
    elif action == "toggle_auto":
        new = not s.get("auto_approve", False)
        await set_settings(chat_id, {"auto_approve": new})
        await cq.answer("Toggled auto-approve.", show_alert=False)
        await cq.edit_message_text(
            f"✅ Auto-approve set to <code>{new}</code> for chat <b>{chat_id}</b>.\nUse /jr_menu to reopen.", parse_mode="html"
        )
    elif action == "set_log":
        # ask owner to reply with chat id or @username in SAME CHAT privately -> we instruct them to DM the bot
        await cq.answer("Send me the log chat id / @username in private to finish.", show_alert=True)
        try:
            await client.send_message(
                caller.id,
                f"Please reply to this message with the target log chat id (e.g. -1001234567890) or @username to set as log for chat <b>{chat_id}</b>.",
                parse_mode="html",
            )
        except RPCError:
            await cq.answer("Could not send private message — please start a chat with the bot first.", show_alert=True)
    elif action == "clear_log":
        await set_settings(chat_id, {"log_chat_id": None})
        await cq.answer("Log cleared.", show_alert=False)
        await cq.edit_message_text(f"✅ Cleared log chat for <b>{chat_id}</b>.", parse_mode="html")
    elif action == "approve_all":
        # approve all pending join requests for that chat
        try:
            ok = await client.approve_all_chat_join_requests(chat_id)
            if ok:
                await cq.answer("All pending requests approved.", show_alert=True)
                s = await get_settings(chat_id)
                await send_log(client, s.get("log_chat_id"), f"{ts()} — ✅ Approve ALL executed by owner {caller.mention} for chat <code>{chat_id}</code>.", parse_mode="html")
                await cq.edit_message_text("✅ Approved all pending join requests.")
            else:
                await cq.answer("Failed to approve all (no permission?).", show_alert=True)
        except RPCError as e:
            await cq.answer(f"Error: {e}", show_alert=True)
    elif action == "view_pending":
        # fetch pending join requests and display small list
        try:
            reqs = await client.get_chat_join_requests(chat_id)
            if not reqs:
                await cq.answer("No pending requests.", show_alert=True)
                await cq.edit_message_text("No pending join requests.")
                return
            lines = []
            for r in reqs[:20]:  # limit preview
                user = r.from_user
                uname = f"@{user.username}" if user.username else "—"
                lines.append(f"{user.first_name or 'NoName'} {user.last_name or ''} {uname} — <code>{user.id}</code>")
            text = "Pending (preview up to 20):\n\n" + "\n".join(lines)
            await cq.answer("Fetched pending requests.", show_alert=False)
            await cq.edit_message_text(text, parse_mode="html")
        except RPCError as e:
            await cq.answer(f"Error: {e}", show_alert=True)

# Owner DM handler for setting log chat id
@app.on_message(filters.private & ~filters.bot)
async def owner_private_handler(client, message: Message):
    # If the message is in reply to the bot's instruction to set_log, parse it
    text = (message.text or "").strip()
    if not text:
        return

    # The bot will receive "set log" requests only from an owner that was instructed
    # We will try to find a chat for which owner (this user) is owner and hasn't yet got log set,
    # but best approach — parse numbers or @username from input, and set them for any chats where owner==this user
    # Simpler flow: require the user to provide "<chat_id> <target>" as "chat_id target" when sending DM.
    # We'll support formats:
    #  - "<target>" — if user has exactly one group where they are owner and have a pending "set_log" flow (not tracked),
    #  - "<chat_id> <target>" — explicit.
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        # ambiguous: can't know which chat the owner meant. Tell them the expected format.
        await message.reply_text(
            "To set a log chat for a group, reply with:\n\n"
            "<code>&lt;group_chat_id&gt; &lt;log_chat_id_or_@username&gt;</code>\n\nExample:\n<code>-1001234567890 -1009876543210</code>",
            parse_mode="html",
        )
        return

    try:
        target_chat = int(parts[0])
    except ValueError:
        await message.reply_text("First argument must be the group chat id (e.g. -1001234567890).", parse_mode="html")
        return

    log_target_raw = parts[1].strip()
    try:
        # resolve
        if log_target_raw.startswith("@"):
            resolved = await client.get_chat(log_target_raw)
            log_target_id = resolved.id
        else:
            log_target_id = int(log_target_raw)
            _ = await client.get_chat(log_target_id)
    except RPCError as e:
        await message.reply_text(f"Could not resolve log chat: {e}", parse_mode="html")
        return

    # verify caller is owner of target_chat
    if not await is_group_owner(client, target_chat, message.from_user.id):
        await message.reply_text("You are not the owner of that target group.", parse_mode="html")
        return

    await set_settings(target_chat, {"log_chat_id": log_target_id})
    await message.reply_text(f"✅ Log chat set for <code>{target_chat}</code> -> <code>{log_target_id}</code>", parse_mode="html")
    # notify the log chat
    await send_log(client, log_target_id, f"{ts()} — Log channel configured for group <code>{target_chat}</code> by {message.from_user.mention}", parse_mode="html")

# -------------------------
# Chat join request handler (main)
# -------------------------
@app.on_chat_join_request()
async def handle_chat_join_request(client, req: ChatJoinRequest):
    chat = req.chat
    requester = req.from_user
    chat_id = chat.id
    user_id = requester.id

    s = await get_settings(chat_id)
    if not s.get("enabled", False):
        # nothing to do
        return

    # Auto-approve path
    if s.get("auto_approve", False):
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            # log
            await send_log(
                client,
                s.get("log_chat_id"),
                f"{ts()} — ✅ Auto-approved join request in <b>{chat.title or chat_id}</b>\nUser: {nice_user_details(requester)}",
                parse_mode="html",
                disable_web_page_preview=True,
            )
        except RPCError as e:
            await send_log(
                client,
                s.get("log_chat_id"),
                f"{ts()} — ❌ Failed to auto-approve for <b>{chat.title or chat_id}</b>. Error: {e}",
                parse_mode="html",
            )
        return

    # Manual approval: post a rich message into the group (admins will see the inline buttons)
    bio = req.bio or "—"
    date_sent = req.date.strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        f"🔔 <b>New Join Request</b>\n"
        f"<b>Group:</b> {chat.title or chat_id} (<code>{chat_id}</code>)\n"
        f"<b>User:</b>\n{nice_user_details(requester)}\n\n"
        f"<b>Bio:</b> <code>{bio}</code>\n"
        f"<b>Requested at:</b> <code>{date_sent}</code>\n\n"
        f"Admins: use the buttons below to approve or decline."
    )
    kb = make_request_buttons(chat_id, user_id)

    # try to attach user avatar (best-effort): get_user_profile_photos exists but we won't fetch full size here (avoid extra requests)
    try:
        sent = await client.send_message(chat_id, text, reply_markup=kb, parse_mode="html", disable_web_page_preview=True)
    except RPCError:
        # fallback: log to log chat instead
        await send_log(
            client,
            s.get("log_chat_id"),
            f"{ts()} — ⚠️ Could not post join request into group <code>{chat_id}</code>. Request by {nice_user_details(requester)}",
            parse_mode="html",
        )
        return

    # notify log that a request was posted
    await send_log(
        client,
        s.get("log_chat_id"),
        f"{ts()} — ℹ️ Join request posted in <b>{chat.title or chat_id}</b> for {nice_user_details(requester)}",
        parse_mode="html",
    )

# -------------------------
# Admin callbacks: approve / decline / view / decline_reason flow
# -------------------------
@app.on_callback_query(filters.regex(r"^jr:(approve|decline_prompt|decline_reason|view):-?\d+:\d+$"))
async def jr_admin_cb(client, cq: CallbackQuery):
    data = cq.data
    parts = data.split(":")
    action = parts[1]
    chat_id = int(parts[2])
    user_id = int(parts[3])
    caller = cq.from_user

    # ensure caller is admin of the target chat
    if not await is_group_admin(client, chat_id, caller.id):
        await cq.answer("Only group admins can perform this action.", show_alert=True)
        return

    # ensure bot is admin too (required to approve/decline)
    me = await client.get_me()
    try:
        me_member = await client.get_chat_member(chat_id, me.id)
        if me_member.status != ChatMemberStatus.ADMINISTRATOR:
            await cq.answer("I must be admin in the group to perform approvals.", show_alert=True)
            return
    except RPCError:
        await cq.answer("Unable to verify my admin status in the group.", show_alert=True)
        return

    s = await get_settings(chat_id)

    if action == "approve":
        # Approve the single request
        try:
            await client.approve_chat_join_request(chat_id, user_id)
            await cq.edit_message_text(f"✅ Approved by {caller.mention_html()}\nUser: <code>{user_id}</code>", parse_mode="html")
            await send_log(
                client,
                s.get("log_chat_id"),
                f"{ts()} — ✅ Request approved in <b>{chat_id}</b>\nUser: <code>{user_id}</code>\nBy: {caller.mention_html()}",
                parse_mode="html",
            )
            await cq.answer("User approved.", show_alert=False)
        except RPCError as e:
            # handle Hide_requester_missing and others
            await cq.answer(f"Failed to approve: {e}", show_alert=True)

    elif action == "decline_prompt":
        # Quick decline (no reason): decline immediately
        try:
            await client.decline_chat_join_request(chat_id, user_id)
            await cq.edit_message_text(f"❌ Declined by {caller.mention_html()}\nUser: <code>{user_id}</code>", parse_mode="html")
            await send_log(
                client,
                s.get("log_chat_id"),
                f"{ts()} — ❌ Request declined in <b>{chat_id}</b>\nUser: <code>{user_id}</code>\nBy: {caller.mention_html()}",
                parse_mode="html",
            )
            await cq.answer("User declined.", show_alert=False)
        except RPCError as e:
            await cq.answer(f"Failed to decline: {e}", show_alert=True)

    elif action == "decline_reason":
        # Start a reason flow: ask admin to DM the bot with their reason (or reply to bot message)
        await cq.answer("Please send me (in private) the reason for decline. Reply to the bot's DM with the reason.", show_alert=True)
        # record in memory; expires after 5 minutes
        PENDING_REASON_PROMPTS[caller.id] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "action": "decline",
            "initiated_by": caller.id,
            "initiated_at": datetime.datetime.utcnow(),
            "expires_at": datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
        }
        try:
            await client.send_message(caller.id,
                f"You chose to decline user <code>{user_id}</code> from group <code>{chat_id}</code>.\n\n"
                "Please reply to this message with the reason for decline (within 5 minutes).",
                parse_mode="html")
        except RPCError:
            await cq.answer("Could not open private chat with you. Please start a chat with the bot first.", show_alert=True)

    elif action == "view":
        # show a short user preview (attempt to fetch the user object)
        try:
            user = await client.get_users(user_id)
            txt = (
                f"<b>User preview</b>\n{nice_user_details(user)}\n\n"
                f"<a href='tg://user?id={user.id}'>Open profile</a>"
            )
            await cq.answer("Showing user details.", show_alert=False)
            await cq.edit_message_text(txt, parse_mode="html")
        except RPCError as e:
            await cq.answer(f"Could not fetch user: {e}", show_alert=True)

# -------------------------
# Private message handler for admin decline reason replies
# -------------------------
@app.on_message(filters.private & ~filters.me & ~filters.bot)
async def private_reason_handler(client, message: Message):
    admin_id = message.from_user.id
    if admin_id not in PENDING_REASON_PROMPTS:
        return  # not expecting a reason from this user

    state = PENDING_REASON_PROMPTS[admin_id]
    if datetime.datetime.utcnow() > state.get("expires_at"):
        del PENDING_REASON_PROMPTS[admin_id]
        await message.reply_text("❌ The decline request has expired. Please try again in the group.")
        return

    reason = (message.text or "").strip()
    if not reason:
        await message.reply_text("Please send a non-empty reason for decline.")
        return

    chat_id = state["chat_id"]
    user_id = state["user_id"]
    caller = message.from_user

    # proceed to decline with reason
    try:
        await client.decline_chat_join_request(chat_id, user_id)
    except RPCError as e:
        await message.reply_text(f"Failed to decline join request: {e}")
        del PENDING_REASON_PROMPTS[admin_id]
        return

    # log the decline with reason to the group's log chat if set
    s = await get_settings(chat_id)
    log_chat = s.get("log_chat_id")
    log_text = (
        f"{ts()} — ❌ Request declined (with reason)\n"
        f"Group: <code>{chat_id}</code>\n"
        f"User: <code>{user_id}</code>\n"
        f"Declined by: {caller.mention}\n"
        f"Reason: {reason}"
    )
    await send_log(client, log_chat, log_text, parse_mode="html")
    # confirmation to admin
    await message.reply_text(f"✅ Declined user <code>{user_id}</code> from <code>{chat_id}</code> and logged reason.", parse_mode="html")
    # try to edit the message in the group that had buttons (best-effort: find last message referencing user)
    # We will not attempt extensive search to avoid rate limits.
    del PENDING_REASON_PROMPTS[admin_id]

# -------------------------
# Optional admin command to approve all pending (shortcut)
# -------------------------
@app.on_message(filters.command("jr_approve_all") & filters.group)
async def cmd_approve_all(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_group_admin(client, chat_id, user_id):
        await message.reply_text("Only group admins can approve all pending requests.")
        return
    try:
        ok = await client.approve_all_chat_join_requests(chat_id)
        if ok:
            await message.reply_text("✅ All pending join requests approved.")
            s = await get_settings(chat_id)
            await send_log(client, s.get("log_chat_id"), f"{ts()} — ✅ Approve ALL executed by {message.from_user.mention} for chat <code>{chat_id}</code>.", parse_mode="html")
        else:
            await message.reply_text("❌ Failed to approve all (maybe no permission).")
    except RPCError as e:
        await message.reply_text(f"❌ Error: {e}")

# -------------------------
# Regular cleanup task to drop expired pending reasons (keeps memory tidy)
# -------------------------
async def reason_cleanup_task():
    while True:
        now = datetime.datetime.utcnow()
        to_del = []
        for k, v in list(PENDING_REASON_PROMPTS.items()):
            if v.get("expires_at") and now > v["expires_at"]:
                to_del.append(k)
        for k in to_del:
            try:
                del PENDING_REASON_PROMPTS[k]
            except KeyError:
                pass
        await asyncio.sleep(30)

# start cleanup background task when app starts
@app.on_start()
async def _start_background_tasks(client):
    client.create_task(reason_cleanup_task())

# End of requestchat.py
