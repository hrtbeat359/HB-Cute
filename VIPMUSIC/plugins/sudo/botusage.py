import asyncio
from datetime import datetime
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from VIPMUSIC import app
from VIPMUSIC.misc import SUDOERS
from VIPMUSIC.utils.database import mongodb


# ====== Mongo Collections ======
users_col = mongodb.users
chats_col = mongodb.chats
channels_col = mongodb.channels
monthly_col = mongodb.monthly_users


# =============== AUTO RESET EVERY 1ST OF MONTH ===================
async def auto_reset_monthly():
    while True:
        now = datetime.utcnow()

        # Reset only on 1st day at 00:00 UTC
        if now.day == 1 and now.hour == 0:
            await monthly_col.drop()
            print("[AUTO-RESET] Monthly Users count reset.")

            # Wait 1 hour before checking again to avoid multiple resets
            await asyncio.sleep(3600)

        await asyncio.sleep(300)  # check every 5 minutes


# Run background task
asyncio.create_task(auto_reset_monthly())


# =============== FUNCTIONS =====================
async def get_stats():
    total_users = await users_col.count_documents({})
    total_chats = await chats_col.count_documents({})
    total_channels = await channels_col.count_documents({})
    monthly_users = await monthly_col.count_documents({})

    return total_users, total_chats, total_channels, monthly_users


# =============== HANDLER: /totalusers =====================
@app.on_message(filters.command("totalusers") & filters.user(SUDOERS))
async def total_users_handler(client, message):
    total_users, total_chats, total_channels, monthly_users = await get_stats()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Total Chats", callback_data="show_chats"),
                InlineKeyboardButton("Total Channels", callback_data="show_channels"),
            ],
            [InlineKeyboardButton("Monthly Users", callback_data="show_monthly")],
        ]
    )

    text = (
        f"👥 **Total Users:** `{total_users}`\n"
        f"💬 **Total Chats:** `{total_chats}`\n"
        f"📢 **Total Channels:** `{total_channels}`\n"
        f"📅 **Monthly Users:** `{monthly_users}`"
    )

    await message.reply_text(text, reply_markup=keyboard)


# =============== HANDLER: /totalchats =====================
@app.on_message(filters.command("totalchats") & filters.user(SUDOERS))
async def total_chats_handler(client, message):
    _, total_chats, total_channels, monthly_users = await get_stats()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Total Users", callback_data="show_users"),
                InlineKeyboardButton("Total Channels", callback_data="show_channels"),
            ],
            [InlineKeyboardButton("Monthly Users", callback_data="show_monthly")],
        ]
    )

    text = (
        f"💬 **Total Chats:** `{total_chats}`\n"
        f"📢 **Total Channels:** `{total_channels}`\n"
        f"👥 **Total Users:** `{_}`\n"
        f"📅 **Monthly Users:** `{monthly_users}`"
    )

    await message.reply_text(text, reply_markup=keyboard)


# =============== HANDLER: /totalchannels =====================
@app.on_message(filters.command("totalchannels") & filters.user(SUDOERS))
async def total_channels_handler(client, message):
    total_users, total_chats, total_channels, monthly_users = await get_stats()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Total Users", callback_data="show_users"),
                InlineKeyboardButton("Total Chats", callback_data="show_chats"),
            ],
            [InlineKeyboardButton("Monthly Users", callback_data="show_monthly")],
        ]
    )

    text = (
        f"📢 **Total Channels:** `{total_channels}`\n"
        f"👥 **Total Users:** `{total_users}`\n"
        f"💬 **Total Chats:** `{total_chats}`\n"
        f"📅 **Monthly Users:** `{monthly_users}`"
    )

    await message.reply_text(text, reply_markup=keyboard)


# =============== HANDLER: /monthlyusers =====================
@app.on_message(filters.command("monthlyusers") & filters.user(SUDOERS))
async def monthly_handler(client, message):
    monthly_users = await monthly_col.count_documents({})

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Total Users", callback_data="show_users"),
                InlineKeyboardButton("Total Chats", callback_data="show_chats"),
            ],
            [InlineKeyboardButton("Total Channels", callback_data="show_channels")],
        ]
    )

    text = f"📅 **Monthly Users:** `{monthly_users}`"

    await message.reply_text(text, reply_markup=keyboard)


# =============== INLINE BUTTON CALLBACKS =====================
@app.on_callback_query()
async def callback_handler(client, callback):

    if callback.data == "show_users":
        total_users, total_chats, total_channels, monthly_users = await get_stats()
        await callback.message.edit_text(
            f"👥 Total Users: `{total_users}`",
        )

    elif callback.data == "show_chats":
        total_users, total_chats, total_channels, monthly_users = await get_stats()
        await callback.message.edit_text(
            f"💬 Total Chats: `{total_chats}`",
        )

    elif callback.data == "show_channels":
        total_users, total_chats, total_channels, monthly_users = await get_stats()
        await callback.message.edit_text(
            f"📢 Total Channels: `{total_channels}`",
        )

    elif callback.data == "show_monthly":
        monthly_users = await monthly_col.count_documents({})
        await callback.message.edit_text(
            f"📅 Monthly Users: `{monthly_users}`",
        )

    await callback.answer()
