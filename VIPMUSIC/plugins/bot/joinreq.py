import os
import asyncio
import datetime
import html as _html
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

MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority",
)
if not MONGO_URL:
    raise RuntimeError("MONGO_URL environment variable is required by requestchat.py")

mongo = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = mongo.get_database("ghosttreq")
settings_coll = db.get_collection("join_request_settings")

# Temporary in-memory states (admin decline reason prompts)
# Structure: {admin_id: {"chat_id": int, "user_id": int, "action": "decline", "payload": {...}, "expires_at": datetime}}
PENDING_REASON_PROMPTS: Dict[int, Dict[str, Any]] = {}

# Helper: get timestamp string
def ts() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


# small helper to build HTML mention for a user (works for edit_message_text etc)
def mention_html(user: User) -> str:
    name = _html.escape(user.first_name or "User")
    return f"<a href='tg://user?id={user.id}'>{name}</a>"


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
                InlineKeyboardButton(
                    "🍏 𝐀ᴘᴘʀᴏᴠᴇ", callback_data=f"jr:approve:{chat_id}:{user_id}"
                ),
                InlineKeyboardButton(
                    "🍎 𝐃ɪ𝗌ᴍɪ𝗌𝗌", callback_data=f"jr:decline_prompt:{chat_id}:{user_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔻 𝐃ɪ𝗌ᴍɪ𝗌𝗌 𝐖ɪᴛʜ 𝐑ᴇᴀsᴏɴ 🔻",
                    callback_data=f"jr:decline_reason:{chat_id}:{user_id}",
                ),
                #InlineKeyboardButton(
                #    "ℹ️ View user", callback_data=f"jr:view:{chat_id}:{user_id}"
                #),
            ],
        ]
    )
    return kb


def make_owner_settings_kb(chat_id: int, enabled: bool, auto: bool, log_id: Optional[int]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🍎 𝐃ɪsᴀʙʟᴇ" if enabled else "🍏 𝐄ɴᴀʙʟᴇ",
                    callback_data=f"jr:toggle_enabled:{chat_id}",
                ),
                InlineKeyboardButton(
                    "🍎 𝐀ᴜᴛᴏ" if auto else "🍏 𝐌ᴀɴᴜᴀʟ",
                    callback_data=f"jr:toggle_auto:{chat_id}",
                ),
            ],
            [
                InlinInlineKeyboardButton("𝐒ᴇᴛ 𝐋ᴏɢ-𝐆ʀᴏᴜᴘ", callback_data=f"jr:set_log:{chat_id}"),
                InlineKeyboardButton("𝐂ʟᴇᴀʀ 𝐋ᴏɢ", callback_data=f"jr:clear_log:{chat_id}"),
            ],
            [
                InlineKeyboardButton("🔻 𝐀ᴘᴘʀᴏᴠᴇ 𝐀ʟʟ 𝐏ᴇɴᴅɪɴɢ𝗌 🔻", callback_data=f"jr:approve_all:{chat_id}"),
                #InlineKeyboardButton("View Pending", callback_data=f"jr:view_pending:{chat_id}"),
            ],
        ]
    )
    return kb


def nice_user_details(user: User) -> str:
    uname = f"@{user.username}" if user.username else "—"
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    if not name:
        name = "No name"
    return f"<b>{_html.escape(name)}</b> ({_html.escape(uname)})\nID: <code>{user.id}</code>"


# -------------------------
# Commands (owner-only settings) & menu
# -------------------------
# Owner inline menu trigger: /jr_menu (must be used inside the target group by owner)
@app.on_message(filters.command("/joinreq") & filters.group)
async def cmd_jr_menu(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_group_owner(client, chat_id, user_id):
        await message.reply_text("⚠️ Only the group *owner* can open join-request settings.")
        return

    s = await get_settings(chat_id)
    kb = make_owner_settings_kb(
        chat_id, s.get("enabled", False), s.get("auto_approve", False), s.get("log_chat_id")
    )
    text = (
        f"<blockquote>🚀 𝐉ᴏɪɴ 𝐑ᴇǫᴜᴇ𝗌ᴛ 𝐌ᴇɴᴜ\n <b>{_html.escape(message.chat.title or str(chat_id))}</b></blockquote>\n"
        f"<blockquote>▪️ 𝐑ᴇǫ 𝐓ᴏ 𝐉ᴏɪɴ: <code>{s.get('enabled', False)}</code>\n"
        f"▪️ 𝐀ᴘᴘʀᴏᴠᴇ 𝐌ᴏᴅᴇ: <code>{s.get('auto_approve', False)}</code>\n"
        f"▪️ 𝐋ᴏɢ 𝐆ʀᴏᴜᴘ: <code>{s.get('log_chat_id')}</code></blockquote>\n"
        f"ᴏᴡɴᴇʀ𝗌 ᴜsᴇ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴄʜᴀɴɢᴇ ᴏᴘᴛɪᴏɴ𝗌"
    )
    await message.reply_text(text, reply_markup=kb)


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
            f"✅ Enabled set to <code>{new}</code> for chat <b>{chat_id}</b>.\nUse /jr_menu to reopen.",
        )
    elif action == "toggle_auto":
        new = not s.get("auto_approve", False)
        await set_settings(chat_id, {"auto_approve": new})
        await cq.answer("Toggled auto-approve.", show_alert=False)
        await cq.edit_message_text(
            f"✅ Auto-approve set to <code>{new}</code> for chat <b>{chat_id}</b>.\nUse /jr_menu to reopen.",
        )
    elif action == "set_log":
        # ask owner to reply with chat id or @username in SAME CHAT privately -> we instruct them to DM the bot
        await cq.answer("Send me the log chat id / @username in private to finish.", show_alert=True)
        try:
            await client.send_message(
                caller.id,
                f"Please reply to this message with the target log chat id (e.g. -1001234567890) or @username to set as log for chat <b>{chat_id}</b>.",
            )
        except RPCError:
            await cq.answer("Could not send private message — please start a chat with the bot first.", show_alert=True)
    elif action == "clear_log":
        await set_settings(chat_id, {"log_chat_id": None})
        await cq.answer("Log cleared.", show_alert=False)
        await cq.edit_message_text(f"✅ Cleared log chat for <b>{chat_id}</b>.")
    elif action == "approve_all":
        # approve all pending join requests for that chat
        try:
            ok = await client.approve_all_chat_join_requests(chat_id)
            if ok:
                await cq.answer("All pending requests approved.", show_alert=True)
                s = await get_settings(chat_id)
                await send_log(
                    client,
                    s.get("log_chat_id"),
                    f"{ts()} — ✅ Approve ALL executed by owner {mention_html(caller)} for chat <code>{chat_id}</code>.",
                )
                await cq.edit_message_text("✅ Approved all pending join requests.")
            else:
                await cq.answer("Failed to approve all (no permission?).", show_alert=True)
        except RPCError as e:
            await cq.answer(f"Error: {e}", show_alert=True)
    elif action == "view_pending":
        # fetch pending join requests and display small list
        try:
            # get_chat_join_requests returns an async generator — consume it
            reqs = []
            async for r in client.get_chat_join_requests(chat_id):
                reqs.append(r)
            if not reqs:
                await cq.answer("No pending requests.", show_alert=True)
                await cq.edit_message_text("No pending join requests.")
                return
            lines = []
            for r in reqs[:20]:  # limit preview
                user = r.from_user
                uname = f"@{user.username}" if user.username else "—"
                lines.append(f"{_html.escape(user.first_name or 'NoName')} {_html.escape(user.last_name or '')} {uname} — <code>{user.id}</code>")
            text = "Pending (preview up to 20):\n\n" + "\n".join(lines)
            await cq.answer("Fetched pending requests.", show_alert=False)
            await cq.edit_message_text(text)
        except RPCError as e:
            await cq.answer(f"Error: {e}", show_alert=True)


# Owner DM handler for setting log chat id
@app.on_message(filters.private & ~filters.bot)
async def owner_private_handler(client, message: Message):
    # If the message is in reply to the bot's instruction to set_log
    text = (message.text or "").strip()
    if not text:
        return

    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        # ambiguous: can't know which chat the owner meant. Tell them the expected format.
        await message.reply_text(
            "To set a log chat for a group, reply with:\n\n"
            "<code>&lt;group_chat_id&gt; &lt;log_chat_id_or_@username&gt;</code>\n\nExample:\n<code>-1001234567890 -1009876543210</code>",
        )
        return

    try:
        target_chat = int(parts[0])
    except ValueError:
        await message.reply_text("First argument must be the group chat id (e.g. -1001234567890).")
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
        await message.reply_text(f"Could not resolve log chat: {e}")
        return

    # verify caller is owner of target_chat
    if not await is_group_owner(client, target_chat, message.from_user.id):
        await message.reply_text("You are not the owner of that target group.")
        return

    await set_settings(target_chat, {"log_chat_id": log_target_id})
    await message.reply_text(f"✅ Log chat set for <code>{target_chat}</code> -> <code>{log_target_id}</code>")
    # notify the log chat
    await send_log(client, log_target_id, f"{ts()} — Log channel configured for group <code>{target_chat}</code> by {mention_html(message.from_user)}")


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
                f"{ts()} — ✅ Auto-approved join request in <b>{_html.escape(chat.title or str(chat_id))}</b>\nUser: {nice_user_details(requester)}",
                disable_web_page_preview=True,
            )
            # notify user
            try:
                await client.send_message(
                    user_id,
                    f"✅ Your join request to <b>{_html.escape(chat.title or str(chat_id))}</b> has been approved automatically.",
                )
            except RPCError:
                pass
        except RPCError as e:
            await send_log(
                client,
                s.get("log_chat_id"),
                f"{ts()} — ❌ Failed to auto-approve for <b>{_html.escape(chat.title or str(chat_id))}</b>. Error: {e}",
            )
        return

    # Manual approval: post a rich message into the group (admins will see the inline buttons)
    bio = req.bio or "—"
    date_sent = req.date.strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        f"🔔 <b>New Join Request</b>\n"
        f"<b>Group:</b> {_html.escape(chat.title or str(chat_id))} (<code>{chat_id}</code>)\n"
        f"<b>User:</b>\n{nice_user_details(requester)}\n\n"
        f"<b>Bio:</b> <code>{_html.escape(bio)}</code>\n"
        f"<b>Requested at:</b> <code>{date_sent}</code>\n\n"
        f"Admins: use the buttons below to approve or decline."
    )
    kb = make_request_buttons(chat_id, user_id)

    # try to attach user avatar (best-effort): get_user_profile_photos exists but we won't fetch full size here (avoid extra requests)
    try:
        sent = await client.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)
    except RPCError:
        # fallback: log to log chat instead
        await send_log(
            client,
            s.get("log_chat_id"),
            f"{ts()} — ⚠️ Could not post join request into group <code>{chat_id}</code>. Request by {nice_user_details(requester)}",
        )
        return

    # notify log that a request was posted
    await send_log(
        client,
        s.get("log_chat_id"),
        f"{ts()} — ℹ️ Join request posted in <b>{_html.escape(chat.title or str(chat_id))}</b> for {nice_user_details(requester)}",
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
            # edit the join-request message (admins see)
            await cq.edit_message_text(
                f"<blockquote>🍏 𝐀ᴘᴘʀᴏᴠᴇᴅ 𝐁ʏ \n{mention_html(caller)}</blockquote>\n<blockquote>✨ 𝐔𝗌ᴇʀ: <code>{user_id}</code></blockquote>",
            )
            await send_log(
                client,
                s.get("log_chat_id"),
                f"<blockquote>{ts()} — 🚀 𝐑ᴇǫᴜᴇ𝗌ᴛ 𝐀ᴘᴘʀᴏᴠᴇᴅ 𝐈ɴ \n <b>{chat_id}</b>\n✨ 𝐔𝗌ᴇʀ: <code>{user_id}</code></blockquote>\n<blockquote>𝐁ʏ: {mention_html(caller)}</blockquote>",
            )
            # notify the requester (best-effort)
            try:
                await client.send_message(
                    user_id,
                    f"💥 Your join request to <b>{_html.escape(str(chat_id))}</b> was approved by {mention_html(caller)}.",
                )
            except RPCError:
                pass
            await cq.answer("User approved.", show_alert=False)
        except RPCError as e:
            # handle Hide_requester_missing and others
            await cq.answer(f"Failed to approve: {e}", show_alert=True)

    elif action == "decline_prompt":
        # Quick decline (no reason): decline immediately
        try:
            await client.decline_chat_join_request(chat_id, user_id)
            await cq.edit_message_text(
                f"🍎 𝐃ᴇᴄʟɪɴᴇᴅ 𝐁ʏ \n{mention_html(caller)}\nUser: <code>{user_id}</code>",
            )
            await send_log(
                client,
                s.get("log_chat_id"),
                f"<blockquote>{ts()} — 🚀 𝐑ᴇǫᴜᴇ𝗌ᴛ 𝐃ᴇᴄʟɪɴᴇᴅ 𝐈ɴ <b>{chat_id}</b>\n✨ 𝐔𝗌ᴇʀ: <code>{user_id}</code></blockquote>\n<blockquote>𝐁ʏ: {mention_html(caller)}</blockquote>",
            )
            # notify the requester (best-effort)
            try:
                await client.send_message(
                    user_id,
                    f"💥 Your join request to <b>{_html.escape(str(chat_id))}</b> was declined by {mention_html(caller)}.",
                )
            except RPCError:
                pass
            await cq.answer("User declined.", show_alert=False)
        except RPCError as e:
            await cq.answer(f"Failed to decline: {e}", show_alert=True)

    elif action == "decline_reason":
        # Start a reason flow: ask admin to DM the bot with their reason (or reply to bot message)
        await cq.answer(
            "Please send me (in private) the reason for decline. Reply to the bot's DM with the reason.",
            show_alert=True,
        )
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
            await client.send_message(
                caller.id,
                f"You chose to decline user <code>{user_id}</code> from group <code>{chat_id}</code>.\n\n"
                "Please reply to this message with the reason for decline (within 5 minutes).",
            )
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
            await cq.edit_message_text(txt)
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
        f"Declined by: {mention_html(caller)}\n"
        f"Reason: {_html.escape(reason)}"
    )
    await send_log(client, log_chat, log_text)
    # confirmation to admin
    await message.reply_text(
        f"✅ Declined user <code>{user_id}</code> from <code>{chat_id}</code> and logged reason.",
    )

    # notify the requester with reason (best-effort)
    try:
        await client.send_message(
            user_id,
            f"❌ Your join request to <b>{_html.escape(str(chat_id))}</b> was declined by {mention_html(caller)}.\n\nReason:\n{_html.escape(reason)}",
        )
    except RPCError:
        pass

    # cleanup
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
            await send_log(
                client,
                s.get("log_chat_id"),
                f"{ts()} — ✅ Approve ALL executed by {mention_html(message.from_user)} for chat <code>{chat_id}</code>.",
            )
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


