from typing import Union

from pyrogram import filters, types
from pyrogram.types import InlineKeyboardMarkup, Message, WebAppInfo

from VIPMUSIC import app
from VIPMUSIC.utils.database import get_lang
from VIPMUSIC.utils.decorators.language import LanguageStart, languageCB
from VIPMUSIC.utils.inline.help import (
    first_page,
    private_help_panel,
    music_panel,
    games_panel1,
    games_panel2,
    games_panel3,
    games_panel4,
    games_panel5,
    chat_panel,
    reaction_panel,
    mention_panel,
    management_page1,
    management_page2,
    management_page3,
    help_back_markup,
)
from config import BANNED_USERS, START_IMG_URL, SUPPORT_CHAT
from strings import get_string, helpers
from VIPMUSIC.misc import SUDOERS
from time import time
import asyncio

# Anti-spam system
user_last_message_time = {}
user_command_count = {}
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5


# PRIVATE HELP (shows main categories)
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


# GROUP HELP (shows main categories)
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


# HELP CALLBACK (Handles hb1 – hb∞ Safely)
@app.on_callback_query(filters.regex("help_callback") & ~BANNED_USERS)
@languageCB
async def helper_cb(client, CallbackQuery, _):

    callback_data = CallbackQuery.data.strip()
    # callback_data is like: "help_callback hb12"
    try:
        cb = callback_data.split(None, 1)[1]
    except Exception:
        return await CallbackQuery.answer("Invalid callback", show_alert=True)

    keyboard = help_back_markup(_)

    # SAFELY LOAD ALL HELP_x EVEN IF NUMBERS ARE MISSING
    help_pages = {}

    for name in dir(helpers):
        if name.startswith("HELP_"):
            try:
                num = int(name.split("_")[1])
                help_pages[f"hb{num}"] = getattr(helpers, name)
            except:
                pass

    # Pages that should show alert instead of normal text
    alert_pages = ["hb26", "hb29", "hb30", "hb31", "hb32"]

    # If it's an alert page
    if cb in alert_pages:
        return await CallbackQuery.answer(
            helpers.HELP_50,
            show_alert=True
        )

    # If it's a normal help page
    if cb in help_pages:
        return await CallbackQuery.edit_message_text(
            help_pages[cb],
            reply_markup=keyboard,
        )

    # else unknown
    return await CallbackQuery.answer("Not implemented", show_alert=True)


# Category callbacks: music, games, chat, reaction, mention, management ----------------
@app.on_callback_query(filters.regex(r"help_cat") & ~BANNED_USERS)
@languageCB
async def help_category_cb(client, CallbackQuery, _):
    # data e.g. "help_cat music"
    data = CallbackQuery.data.strip()
    try:
        cat = data.split(None, 1)[1]
    except:
        return await CallbackQuery.answer("Invalid category", show_alert=True)

    # Map categories
    if cat == "music":
        keyboard = music_panel(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if cat == "games":
        keyboard = games_panel1(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if cat == "chat":
        keyboard = chat_panel(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if cat == "reaction":
        keyboard = reaction_panel(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if cat == "mention":
        keyboard = mention_panel(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if cat == "management":
        keyboard = management_page1(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    return await CallbackQuery.answer("Unknown", show_alert=True)


#game panel callbacks
@app.on_callback_query(filters.regex(r"games_p1|games_p2|games_p3|games_p4|games_p5") & ~BANNED_USERS)
@languageCB
async def games_paging_cb(client, CallbackQuery, _):
    data = CallbackQuery.data.strip()

    if data == "games_p1":
        keyboard = games_panel1(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if data == "games_p2":
        keyboard = games_panel2(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if data == "games_p3":
        keyboard = games_panel3(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if data == "games_p4":
        keyboard = games_panel4(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if data == "games_p5":
        keyboard = games_panel5(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return
        

# Management paging callbacks: management_p1, management_p2, management_p3
@app.on_callback_query(filters.regex(r"management_p1|management_p2|management_p3") & ~BANNED_USERS)
@languageCB
async def management_paging_cb(client, CallbackQuery, _):
    data = CallbackQuery.data.strip()

    if data == "management_p1":
        keyboard = management_page1(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if data == "management_p2":
        keyboard = management_page2(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    if data == "management_p3":
        keyboard = management_page3(_)
        try:
            await CallbackQuery.message.edit_text(_["help_1"], reply_markup=keyboard)
        except:
            pass
        await CallbackQuery.answer()
        return

    await CallbackQuery.answer()
