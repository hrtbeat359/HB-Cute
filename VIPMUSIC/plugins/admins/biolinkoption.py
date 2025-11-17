# VIPMUSIC/plugins/admins/biolink_option.py
import asyncio
import logging
from typing import Tuple, Optional

from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# try to reuse existing app from biolink plugin to avoid duplicate clients
try:
    from VIPMUSIC.plugins.admins.biolink import app  # re-use existing Client if available
except Exception:
    # fallback: create a lightweight client — this should only happen if biolink.py isn't loaded.
    # NOTE: If you use multiple clients with same token you may get session conflicts.
    # Prefer to load this module after biolink.py so it re-uses the same `app`.
    from config import API_ID, API_HASH, BOT_TOKEN
    app = Client("BioLinkOptions", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# database helpers
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI, DEFAULT_CONFIG, DEFAULT_PUNISHMENT, DEFAULT_WARNING_LIMIT

# reuse functions from biolinkdb
from VIPMUSIC.utils.databases.biolinkdb import (
    is_admin,
    get_config, update_config,
    increment_warning, reset_warnings,
    is_whitelisted, add_whitelist, remove_whitelist, get_whitelist
)

# Setup DB (same DB name used in biolinkdb)
mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo_client['telegram_bot_db']
settings_collection = db['biolink_settings']  # new collection for extended options

logger = logging.getLogger(__name__)


# ---------------- DEFAULTS -----------------
DEFAULT_SETTINGS = {
    "enabled": True,                     # A. Protection enabled/disabled
    "delete_message": True,              # B. Delete message if bio contains URL
    "detection_level": "strict",         # C. strict | normal | lenient
    "ignore_admins": True,               # F. don't check admins
    "use_whitelist": True,               # G. use whitelist bypass
    "log_chat_id": None                  # H. group/channel id to log violations
}
VALID_DETECTION = ("strict", "normal", "lenient")


# ---------------- DB UTILITIES -----------------
async def get_settings(chat_id: int) -> dict:
    doc = await settings_collection.find_one({"chat_id": chat_id})
    if not doc:
        # merge default with existing punishments collection (mode/limit/penalty)
        mode, limit, penalty = await get_config(chat_id)
        settings = DEFAULT_SETTINGS.copy()
        settings.update({"mode": mode, "limit": limit, "penalty": penalty})
        return settings
    # convert and ensure all keys exist
    settings = DEFAULT_SETTINGS.copy()
    settings.update({k: doc.get(k, settings[k]) for k in settings.keys()})
    # keep mode/limit/penalty in sync with punishments_collection
    mode, limit, penalty = await get_config(chat_id)
    settings.update({"mode": mode, "limit": limit, "penalty": penalty})
    return settings


async def update_settings(chat_id: int, **kwargs):
    # Keep mode/limit/penalty in punishments_collection using existing helper for those keys.
    # For other keys, update settings_collection.
    db_update = {}
    punish_update = {}
    for k, v in kwargs.items():
        if k in ("mode", "limit", "penalty"):
            punish_update[k] = v
        else:
            db_update[k] = v

    if db_update:
        await settings_collection.update_one(
            {"chat_id": chat_id},
            {"$set": db_update},
            upsert=True
        )
    if punish_update:
        # map names: get existing and update via update_config helper
        await update_config(chat_id,
                            mode=punish_update.get("mode", None),
                            limit=punish_update.get("limit", None),
                            penalty=punish_update.get("penalty", None)
                            )


# ---------------- UI / TEXT -----------------
def settings_text(chat_id: int, settings: dict) -> str:
    enabled = "✅ Enabled" if settings.get("enabled") else "❌ Disabled"
    delete_msg = "✅ Delete messages" if settings.get("delete_message") else "❌ Don't delete"
    detection = settings.get("detection_level", "strict").capitalize()
    ignore_admins = "✅ Ignore Admins" if settings.get("ignore_admins") else "❌ Check Admins"
    use_whitelist = "✅ Whitelist active" if settings.get("use_whitelist") else "❌ Whitelist disabled"
    mode = settings.get("mode", "warn")
    limit = settings.get("limit", DEFAULT_WARNING_LIMIT)
    penalty = settings.get("penalty", DEFAULT_PUNISHMENT)
    log_chat = settings.get("log_chat_id")
    log_text = f"`{log_chat}`" if log_chat else "Not set"

    text = (
        f"**🔧 BioLink Protection Settings (chat: `{chat_id}`)**\n\n"
        f"• **Status:** {enabled}\n"
        f"• **Delete message:** {delete_msg}\n"
        f"• **Detection:** {detection}\n"
        f"• **Ignore admins:** {ignore_admins}\n"
        f"• **Whitelist mode:** {use_whitelist}\n\n"
        f"• **Punishment mode:** `{mode}`\n"
        f"• **Warning limit:** `{limit}`\n"
        f"• **Penalty:** `{penalty}`\n\n"
        f"• **Log channel:** {log_text}\n\n"
        "__Use the buttons below to change settings.__"
    )
    return text


def main_keyboard(settings: dict) -> InlineKeyboardMarkup:
    # Top row: Enable/Disable
    enabled = settings.get("enabled", True)
    enable_text = "Disable" if enabled else "Enable"
    # Delete toggle
    delete_text = "❌ Delete OFF" if not settings.get("delete_message") else "✅ Delete ON"
    # detection summary
    det = settings.get("detection_level", "strict").capitalize()
    # ignore admins
    ignore_text = "✅ Ignore Admins" if settings.get("ignore_admins") else "❌ Check Admins"
    # whitelist
    wl_text = "✅ Whitelist" if settings.get("use_whitelist") else "❌ Whitelist"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(enable_text, callback_data="toggle_enabled"),
         InlineKeyboardButton(delete_text, callback_data="toggle_delete")],
        [InlineKeyboardButton(f"Detection: {det}", callback_data="change_detection"),
         InlineKeyboardButton(f"Penalty: {settings.get('penalty')}", callback_data="change_penalty")],
        [InlineKeyboardButton(f"Warn limit: {settings.get('limit')}", callback_data="change_limit"),
         InlineKeyboardButton(ignore_text, callback_data="toggle_ignore_admins")],
        [InlineKeyboardButton(wl_text, callback_data="toggle_whitelist"),
         InlineKeyboardButton("Whitelist Menu", callback_data="whitelist_menu")],
        [InlineKeyboardButton("Set Log Channel", callback_data="set_log"),
         InlineKeyboardButton("Clear Log", callback_data="clear_log")],
        [InlineKeyboardButton("Close", callback_data="close")]
    ])
    return kb


# ---------------- COMMANDS -----------------
@app.on_message(filters.group & filters.command(["biolink", "biolinkmenu", "bioconfig"]))
async def open_biolink_options(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ You must be an administrator to manage BioLink settings.")

    settings = await get_settings(chat_id)
    text = settings_text(chat_id, settings)
    kb = main_keyboard(settings)
    await message.reply_text(text, reply_markup=kb)
    try:
        await message.delete()
    except Exception:
        pass


@app.on_message(filters.group & filters.command(["biolink", "biolinkon", "biolinkoff"]))
async def biolink_quick_toggle(client: Client, message: Message):
    """
    Quick toggle: /biolink on | off or /biolinkon /biolinkoff
    """
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ You must be an administrator to change BioLink status.")

    args = message.command
    if len(args) > 1:
        arg = args[1].lower()
        if arg in ("on", "enable", "1"):
            await update_settings(chat_id, enabled=True)
            return await message.reply_text("✅ BioLink protection ENABLED.")
        if arg in ("off", "disable", "0"):
            await update_settings(chat_id, enabled=False)
            return await message.reply_text("❌ BioLink protection DISABLED.")

    # if only /biolink provided, show menu (same as open_biolink_options)
    settings = await get_settings(chat_id)
    text = settings_text(chat_id, settings)
    kb = main_keyboard(settings)
    await message.reply_text(text, reply_markup=kb)
    try:
        await message.delete()
    except Exception:
        pass


# whitelist submenu handlers (simple)
def whitelist_keyboard(chat_id: int, ids: list) -> InlineKeyboardMarkup:
    rows = []
    for uid in ids:
        rows.append([InlineKeyboardButton(f"Remove {uid}", callback_data=f"wl_remove_{uid}")])
    rows.append([InlineKeyboardButton("Add by reply", callback_data="wl_add_reply"),
                 InlineKeyboardButton("Close", callback_data="close")])
    return InlineKeyboardMarkup(rows)


# ---------------- CALLBACKS -----------------
@app.on_callback_query()
async def options_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id

    # quick admin check
    if not await is_admin(client, chat_id, user_id):
        return await callback_query.answer("❌ You are not administrator", show_alert=True)

    # CLOSE
    if data == "close":
        try:
            return await callback_query.message.delete()
        except Exception:
            return await callback_query.answer()

    # TOGGLE ENABLED
    if data == "toggle_enabled":
        settings = await get_settings(chat_id)
        new = not bool(settings.get("enabled", True))
        await update_settings(chat_id, enabled=new)
        settings = await get_settings(chat_id)
        await callback_query.message.edit_text(settings_text(chat_id, settings), reply_markup=main_keyboard(settings))
        return await callback_query.answer("Toggled protection.")

    # TOGGLE DELETE MESSAGE
    if data == "toggle_delete":
        settings = await get_settings(chat_id)
        new = not bool(settings.get("delete_message", True))
        await update_settings(chat_id, delete_message=new)
        settings = await get_settings(chat_id)
        await callback_query.message.edit_text(settings_text(chat_id, settings), reply_markup=main_keyboard(settings))
        return await callback_query.answer("Toggled delete message.")

    # CHANGE DETECTION -> open choices
    if data == "change_detection":
        settings = await get_settings(chat_id)
        keys = VALID_DETECTION
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Strict", callback_data="set_det_strict"),
             InlineKeyboardButton("Normal", callback_data="set_det_normal"),
             InlineKeyboardButton("Lenient", callback_data="set_det_lenient")],
            [InlineKeyboardButton("Back", callback_data="back"), InlineKeyboardButton("Close", callback_data="close")]
        ])
        await callback_query.message.edit_text("Select detection level:", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith("set_det_"):
        val = data.split("_")[-1]
        if val in VALID_DETECTION:
            await update_settings(chat_id, detection_level=val)
            settings = await get_settings(chat_id)
            await callback_query.message.edit_text(settings_text(chat_id, settings), reply_markup=main_keyboard(settings))
            return await callback_query.answer(f"Detection set to {val}.")

    # CHANGE PENALTY (uses punishments db)
    if data == "change_penalty":
        # show penalty options available: warn, mute, ban
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Warn", callback_data="set_penalty_warn"),
             InlineKeyboardButton("Mute", callback_data="set_penalty_mute"),
             InlineKeyboardButton("Ban", callback_data="set_penalty_ban")],
            [InlineKeyboardButton("Back", callback_data="back"), InlineKeyboardButton("Close", callback_data="close")]
        ])
        await callback_query.message.edit_text("Select penalty:", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith("set_penalty_"):
        val = data.split("_")[-1]
        if val in ("warn", "mute", "ban"):
            await update_settings(chat_id, penalty=val)
            settings = await get_settings(chat_id)
            await callback_query.message.edit_text(settings_text(chat_id, settings), reply_markup=main_keyboard(settings))
            return await callback_query.answer(f"Penalty set to {val}.")

    # CHANGE LIMIT -> number buttons 0-5
    if data == "change_limit":
        _, limit, _ = await get_config(chat_id)
        kb_rows = [
            [InlineKeyboardButton(str(i) + (" ✅" if i == limit else ""), callback_data=f"set_limit_{i}") for i in range(3)],
            [InlineKeyboardButton(str(i) + (" ✅" if i == limit else ""), callback_data=f"set_limit_{i}") for i in range(3,6)],
            [InlineKeyboardButton("Back", callback_data="back"), InlineKeyboardButton("Close", callback_data="close")]
        ]
        kb = InlineKeyboardMarkup(kb_rows)
        await callback_query.message.edit_text("Select warning limit (0-5):", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith("set_limit_"):
        try:
            num = int(data.split("_")[-1])
            await update_settings(chat_id, limit=num)
            settings = await get_settings(chat_id)
            await callback_query.message.edit_text(settings_text(chat_id, settings), reply_markup=main_keyboard(settings))
            return await callback_query.answer(f"Limit set to {num}.")
        except Exception:
            return await callback_query.answer("Invalid limit.", show_alert=True)

    # BACK button - return to main view
    if data == "back":
        settings = await get_settings(chat_id)
        await callback_query.message.edit_text(settings_text(chat_id, settings), reply_markup=main_keyboard(settings))
        return await callback_query.answer()

    # TOGGLE IGNORE ADMINS
    if data == "toggle_ignore_admins":
        settings = await get_settings(chat_id)
        new = not bool(settings.get("ignore_admins", True))
        await update_settings(chat_id, ignore_admins=new)
        settings = await get_settings(chat_id)
        await callback_query.message.edit_text(settings_text(chat_id, settings), reply_markup=main_keyboard(settings))
        return await callback_query.answer("Toggled admin ignore setting.")

    # TOGGLE WHITELIST MODE
    if data == "toggle_whitelist":
        settings = await get_settings(chat_id)
        new = not bool(settings.get("use_whitelist", True))
        await update_settings(chat_id, use_whitelist=new)
        settings = await get_settings(chat_id)
        await callback_query.message.edit_text(settings_text(chat_id, settings), reply_markup=main_keyboard(settings))
        return await callback_query.answer("Toggled whitelist usage.")

    # WHITELIST MENU
    if data == "whitelist_menu":
        ids = await get_whitelist(chat_id)
        kb = whitelist_keyboard(chat_id, ids)
        await callback_query.message.edit_text("Whitelisted users (IDs). Use buttons to remove or reply to add:", reply_markup=kb)
        return await callback_query.answer()

    # remove from whitelist buttons
    if data.startswith("wl_remove_"):
        target_id = int(data.split("_")[-1])
        await remove_whitelist(chat_id, target_id)
        ids = await get_whitelist(chat_id)
        kb = whitelist_keyboard(chat_id, ids)
        await callback_query.message.edit_text(f"Removed `{target_id}` from whitelist.", reply_markup=kb)
        return await callback_query.answer("Removed from whitelist.")

    # add by reply - we instruct admin to reply to a user's message with /biolinkmenu and press this
    if data == "wl_add_reply":
        await callback_query.answer("Reply to the user's message with /biolinkmenu and press 'Add by reply'.", show_alert=True)
        return

    # SET LOG: will instruct admin how to set, or accept reply
    if data == "set_log":
        # instruct admin to reply to a message from the target channel/group with this button
        await callback_query.answer("Reply to a message from the log channel/group with the command /setbiolog or send `/setbiolog <chat_id>`", show_alert=True)
        return

    if data == "clear_log":
        await update_settings(chat_id, log_chat_id=None)
        settings = await get_settings(chat_id)
        await callback_query.message.edit_text(settings_text(chat_id, settings), reply_markup=main_keyboard(settings))
        return await callback_query.answer("Cleared log channel.")

    # fallback
    return await callback_query.answer()


# ---------------- TEXT COMMANDS FOR LOGGING / WHITELIST ADD BY REPLY -----------------
@app.on_message(filters.group & filters.command("setbiolog"))
async def set_bio_log(client: Client, message: Message):
    """
    Usage:
    - Reply to a message in a channel/group and run /setbiolog to set that chat as log target.
    - Or: /setbiolog <chat_id>
    """
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ You must be an administrator to set the log channel.")

    target_chat_id: Optional[int] = None
    if message.reply_to_message:
        target_chat_id = message.reply_to_message.chat.id
    elif len(message.command) > 1:
        try:
            target_chat_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("❌ Invalid chat id. Use numeric id or reply to a message in target chat.")

    if target_chat_id:
        await update_settings(chat_id, log_chat_id=target_chat_id)
        return await message.reply_text(f"✅ Log channel set to `{target_chat_id}`.")
    else:
        return await message.reply_text("❌ Provide a chat id or reply to a message from target channel/group.")


@app.on_message(filters.group & filters.command("clearbiolog"))
async def clear_bio_log(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ You must be an administrator to clear the log channel.")
    await update_settings(chat_id, log_chat_id=None)
    await message.reply_text("✅ Cleared BioLink log channel setting.")


@app.on_message(filters.group & filters.command("biowhitelist"))
async def biowhitelist_cmd(client: Client, message: Message):
    """
    Add/remove via reply or args:
    /biowhitelist add <user_id or @username>
    /biowhitelist remove <user_id>
    /biowhitelist list
    If used as reply: /biowhitelist add (when replying to a user's message)
    """
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ You must be an administrator to manage whitelist.")

    args = message.command
    if len(args) < 2:
        return await message.reply_text("Usage: /biowhitelist add|remove|list [user_id|@username] (or reply to user and use `add`).")

    action = args[1].lower()
    target = None
    if action == "add":
        if message.reply_to_message:
            target = message.reply_to_message.from_user
        elif len(args) > 2:
            try:
                arg = args[2]
                target = await client.get_users(int(arg) if arg.isdigit() else arg)
            except Exception:
                return await message.reply_text("❌ Could not find that user.")
        else:
            return await message.reply_text("Reply to a user's message or provide user id/username to add.")
        await add_whitelist(chat_id, target.id)
        await reset_warnings(chat_id, target.id)
        return await message.reply_text(f"✅ Added {target.mention} to whitelist.")

    if action == "remove":
        if len(args) > 2:
            try:
                arg = args[2]
                uid = int(arg) if arg.isdigit() else (await client.get_users(arg)).id
            except Exception:
                return await message.reply_text("❌ Could not parse user.")
        elif message.reply_to_message:
            uid = message.reply_to_message.from_user.id
        else:
            return await message.reply_text("Reply to a user's message or provide user id/username to remove.")
        await remove_whitelist(chat_id, uid)
        return await message.reply_text(f"✅ Removed `{uid}` from whitelist.")

    if action == "list":
        ids = await get_whitelist(chat_id)
        if not ids:
            return await message.reply_text("⚠️ No whitelisted users.")
        text = "**Whitelisted Users:**\n\n"
        for i, uid in enumerate(ids, start=1):
            try:
                user = await client.get_users(uid)
                name = f"{user.first_name}{(' ' + user.last_name) if user.last_name else ''}"
                text += f"{i}: {name} [`{uid}`]\n"
            except Exception:
                text += f"{i}: [User not found] [`{uid}`]\n"
        return await message.reply_text(text)


# ---------------- INTEGRATION: LOGGING FUNCTION -----------------
async def log_violation(chat_id: int, victim_id: int, actor_id: int, bio_text: str, reason: str, note: str = ""):
    """
    Call this to log violations to configured log channel (if any).
    Designed to be imported/used by main biolink enforcement code when it detects a violation.
    """
    settings = await get_settings(chat_id)
    log_chat = settings.get("log_chat_id")
    if not log_chat:
        return
    try:
        # Build a compact message
        msg = (
            f"**BioLink Violation**\n"
            f"• Chat: `{chat_id}`\n"
            f"• User: [`{victim_id}`]\n"
            f"• Triggered by: [`{actor_id}`]\n"
            f"• Reason: {reason}\n"
            f"• Bio: `{bio_text[:350]}`\n"
        )
        if note:
            msg += f"\n• Note: {note}"
        await app.send_message(log_chat, msg)
    except Exception as e:
        logger.exception("Failed to log violation: %s", e)


# ---------------- BOOT LOG -----------------
logger.info("biolink_option plugin loaded.")

