from datetime import datetime
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from VIPMUSIC import app
from VIPMUSIC.misc import SUDOERS
from VIPMUSIC.utils.database import (
    get_served_users,
    get_served_chats,
    mongodb,
)

# Mongo collection for monthly users
monthly_db = mongodb.monthly_users
config_db = mongodb.monthly_config   # store last reset date


# =====================================================
# AUTO RESET MONTHLY USERS ON 1st OF EVERY MONTH
# =====================================================

async def auto_reset_monthly():
    """Run once when bot starts, resets if needed."""
    today = datetime.now()
    today_month_key = today.strftime("%Y-%m")

    config = await config_db.find_one({"config": "monthly_reset"})
    last_reset = None if not config else config.get("last")

    # If never reset OR month changed → reset
    if last_reset != today_month_key:
        await monthly_db.delete_many({})
        await config_db.update_one(
            {"config": "monthly_reset"},
            {"$set": {"last": today_month_key}},
            upsert=True
        )
        print(f"[Monthly Reset] Reset monthly users for {today_month_key}")


# Call once on startup
app.startup_tasks.append(auto_reset_monthly)


# =====================================================
# Helper: Add monthly user
# =====================================================

async def add_monthly_user(user_id: int):
    month_key = datetime.now().strftime("%Y-%m")
    await monthly_db.update_one(
        {"month": month_key},
        {"$addToSet": {"users": user_id}},
        upsert=True
    )


async def get_monthly_users():
    month_key = datetime.now().strftime("%Y-%m")
    data = await monthly_db.find_one({"month": month_key})
    if not data:
        return 0
    return len(data.get("users", []))


# =====================================================
# /totalusers
# =====================================================

@app.on_message(filters.command("totalusers") & filters.user(SUDOERS))
async def total_users(_, message):
    users = len(await get_served_users())
    chats = len(await get_served_chats())
    monthly = await get_monthly_users()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Total Chats", callback_data="stats_chats"),
                InlineKeyboardButton("Total Channels", callback_data="stats_channels"),
            ],
            [
                InlineKeyboardButton("Monthly Users", callback_data="stats_monthly")
            ]
        ]
    )

    text = (
        f"👤 **Total Users:** `{users}`\n"
        f"💬 **Total Chats:** `{chats}`\n"
        f"📡 **Total Channels:** `{chats}`\n"
        f"📅 **Monthly Users:** `{monthly}`"
    )

    await message.reply_text(text, reply_markup=keyboard)


# =====================================================
# /totalchats
# =====================================================

@app.on_message(filters.command("totalchats") & filters.user(SUDOERS))
async def total_chats(_, message):
    chats = len(await get_served_chats())
    users = len(await get_served_users())
    monthly = await get_monthly_users()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Total Users", callback_data="stats_users"),
                InlineKeyboardButton("Total Channels", callback_data="stats_channels"),
            ],
            [
                InlineKeyboardButton("Monthly Users", callback_data="stats_monthly")
            ]
        ]
    )

    text = (
        f"💬 **Total Chats:** `{chats}`\n"
        f"👤 **Total Users:** `{users}`\n"
        f"📅 **Monthly Users:** `{monthly}`"
    )

    await message.reply_text(text, reply_markup=keyboard)


# =====================================================
# /totalchannels
# =====================================================

@app.on_message(filters.command("totalchannels") & filters.user(SUDOERS))
async def total_channels(_, message):
    chats = len(await get_served_chats())
    users = len(await get_served_users())
    monthly = await get_monthly_users()

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Total Users", callback_data="stats_users"),
                InlineKeyboardButton("Total Chats", callback_data="stats_chats"),
            ],
            [
                InlineKeyboardButton("Monthly Users", callback_data="stats_monthly")
            ]
        ]
    )

    text = (
        f"📡 **Total Channels:** `{chats}`\n"
        f"👤 **Total Users:** `{users}`\n"
        f"📅 **Monthly Users:** `{monthly}`"
    )

    await message.reply_text(text, reply_markup=keyboard)


# =====================================================
# /monthlyusers
# =====================================================

@app.on_message(filters.command("monthlyusers") & filters.user(SUDOERS))
async def monthly_users_cmd(_, message):
    monthly = await get_monthly_users()
    users = len(await get_served_users())
    chats = len(await get_served_chats())

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Total Users", callback_data="stats_users"),
                InlineKeyboardButton("Total Chats", callback_data="stats_chats"),
            ],
            [
                InlineKeyboardButton("Total Channels", callback_data="stats_channels"),
            ]
        ]
    )

    text = (
        f"📅 **Monthly Active Users:** `{monthly}`\n"
        f"👤 **Total Users:** `{users}`\n"
        f"💬 **Total Chats:** `{chats}`"
    )

    await message.reply_text(text, reply_markup=keyboard)


# =====================================================
# Callback Query Handler
# =====================================================

@app.on_callback_query()
async def stats_callback(_, cb):
    data = cb.data

    if not data.startswith("stats_"):
        return

    users = len(await get_served_users())
    chats = len(await get_served_chats())
    monthly = await get_monthly_users()

    if data == "stats_users":
        txt = f"👤 **Total Users:** `{users}`"
    elif data == "stats_chats":
        txt = f"💬 **Total Chats:** `{chats}`"
    elif data == "stats_channels":
        txt = f"📡 **Total Channels:** `{chats}`"
    elif data == "stats_monthly":
        txt = f"📅 **Monthly Active Users:** `{monthly}`"
    else:
        return

    await cb.message.edit_text(
        txt, reply_markup=cb.message.reply_markup
    )
    await cb.answer()
