from typing import Union

from pyrogram import filters, types
from pyrogram.types import InlineKeyboardMarkup, Message

from VIPMUSIC import app
from VIPMUSIC.utils import first_page, second_page, third_page
from VIPMUSIC.utils.database import get_lang
from VIPMUSIC.utils.decorators.language import LanguageStart, languageCB
from VIPMUSIC.utils.inline.help import help_back_markup, private_help_panel
from config import BANNED_USERS, START_IMG_URL, SUPPORT_CHAT
from strings import get_string, helpers
from VIPMUSIC.misc import SUDOERS
from time import time
import asyncio
from VIPMUSIC.utils.extraction import extract_user

# Anti-spam
user_last_message_time = {}
user_command_count = {}
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5


# ───────────────────────────────────────────────────────────────
# PRIVATE HELP
# ───────────────────────────────────────────────────────────────
@app.on_message(filters.command(["help"]) & filters.private & ~BANNED_USERS)
@app.on_callback_query(filters.regex("settings_back_helper") & ~BANNED_USERS)
async def helper_private(
    client: app, update: Union[types.Message, types.CallbackQuery]
):

    is_callback = isinstance(update, types.CallbackQuery)

    if is_callback:
        try:
            await update.answer()
        except:
            pass

        chat_id = update.message.chat.id
        language = await get_lang(chat_id)
        _ = get_string(language)

        keyboard = first_page(_)
        await update.edit_message_text(
            _["help_1"].format(SUPPORT_CHAT), reply_markup=keyboard
        )

    else:
        try:
            await update.delete()
        except:
            pass

        language = await get_lang(update.chat.id)
        _ = get_string(language)

        keyboard = first_page(_)
        await update.reply_photo(
            photo=START_IMG_URL,
            caption=_["help_1"].format(SUPPORT_CHAT),
            reply_markup=keyboard,
        )


# ───────────────────────────────────────────────────────────────
# GROUP HELP
# ───────────────────────────────────────────────────────────────
@app.on_message(filters.command(["help"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client, message: Message, _):

    user_id = message.from_user.id
    current_time = time()
    last_message_time = user_last_message_time.get(user_id, 0)

    if current_time - last_message_time < SPAM_WINDOW_SECONDS:
        user_last_message_time[user_id] = current_time
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1

        if user_command_count[user_id] > SPAM_THRESHOLD:
            warn = await message.reply_text(
                f"**{message.from_user.mention} ᴘʟᴇᴀsᴇ ᴅᴏɴᴛ sᴘᴀᴍ, ᴛʀʏ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 5 sᴇᴄ**"
            )
            await asyncio.sleep(3)
            await warn.delete()
            return

    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = current_time

    keyboard = private_help_panel(_)
    await message.reply_text(_["help_2"], reply_markup=keyboard)


# ───────────────────────────────────────────────────────────────
# HELP CALLBACK
# ───────────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex("help_callback") & ~BANNED_USERS)
@languageCB
async def helper_cb(client, CallbackQuery, _):

    callback_data = CallbackQuery.data.strip()
    cb = callback_data.split(None, 1)[1]

    keyboard = help_back_markup(_)

    # AUTO-MAP HELP PAGES SAFELY (no AttributeError)
    help_pages = {}
    for i in range(1, 100):  # high limit, stops automatically
        attr = f"HELP_{i}"
        if hasattr(helpers, attr):
            help_pages[f"hb{i}"] = getattr(helpers, attr)
        else:
            break

    # ALERT-ONLY HELP PAGES
    alert_pages = ["hb26", "hb29", "hb30", "hb31", "hb32"]

    # If callback is for an alert page
    if cb in alert_pages:
        return await CallbackQuery.answer(
            helpers.HELP_50,
            show_alert=True
        )

    # Normal help page
    if cb in help_pages:
        return await CallbackQuery.edit_message_text(
            help_pages[cb],
            reply_markup=keyboard,
        )


# ───────────────────────────────────────────────────────────────
# MULTI-PAGE NAVIGATION
# ───────────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex("GhostPage1") & ~BANNED_USERS)
@languageCB
async def first_pagexx(client, CallbackQuery, _):
    menu_next = second_page(_)
    try:
        await CallbackQuery.message.edit_text(
            _["help_1"], reply_markup=menu_next
        )
    except:
        return


@app.on_callback_query(filters.regex("GhostPage2") & ~BANNED_USERS)
@languageCB
async def second_pagexx(client, CallbackQuery, _):
    menu_next = third_page(_)
    try:
        await CallbackQuery.message.edit_text(
            _["help_1"], reply_markup=menu_next
        )
    except:
        return
