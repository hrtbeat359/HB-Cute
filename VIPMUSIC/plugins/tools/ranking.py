import asyncio
import datetime
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from motor.motor_asyncio import AsyncIOMotorClient

from VIPMUSIC import app
from config import (
    MONGO_DB_URI,
    RANKING_PIC,
    AUTOPOST_TIME_HOUR,
    AUTOPOST_TIME_MINUTE,
)

# -------------------------------------------------------------------
# DEFAULT POST TIME (Fallback 21:00 IST)
# -------------------------------------------------------------------
try:
    POST_HOUR = int(AUTOPOST_TIME_HOUR)
    POST_MINUTE = int(AUTOPOST_TIME_MINUTE)
except:
    POST_HOUR = 21
    POST_MINUTE = 0

TZ = ZoneInfo("Asia/Kolkata")

# -------------------------------------------------------------------
# DB SETUP
# -------------------------------------------------------------------
mongo = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo["ghosttlead"]
ranking_db = db["ranking"]

# -------------------------------------------------------------------
# TODAY COUNTS (RAM)
# -------------------------------------------------------------------
today_counts: Dict[int, Dict[int, int]] = {}
last_reset_date = None


# -------------------------------------------------------------------
# DB HELPERS
# -------------------------------------------------------------------
async def db_inc_user_messages(user_id: int):
    await ranking_db.update_one(
        {"_id": user_id},
        {"$inc": {"total_messages": 1, "weekly_messages": 1, "monthly_messages": 1}},
        upsert=True,
    )


async def db_get_top(field: str, limit: int = 10):
    cursor = ranking_db.find().sort(field, -1).limit(limit)
    return await cursor.to_list(length=limit)


async def db_reset_field(field: str):
    await ranking_db.update_many({}, {"$set": {field: 0}})


async def db_get_user_counts(user_id: int):
    doc = await ranking_db.find_one({"_id": user_id})
    if not doc:
        return 0, 0, 0
    return (
        int(doc.get("total_messages", 0)),
        int(doc.get("weekly_messages", 0)),
        int(doc.get("monthly_messages", 0)),
    )


async def db_get_rank_for_field(user_id: int, field: str) -> int:
    doc = await ranking_db.find_one({"_id": user_id})
    val = int(doc.get(field, 0)) if doc else 0
    greater = await ranking_db.count_documents({field: {"$gt": val}})
    return greater + 1


# -------------------------------------------------------------------
# TIME HELPERS
# -------------------------------------------------------------------
def ist_now():
    return datetime.datetime.now(TZ)


def reset_today_if_needed():
    global today_counts, last_reset_date
    now = ist_now().date()
    if last_reset_date != now:
        today_counts = {}
        last_reset_date = now


# -------------------------------------------------------------------
# WATCHERS
# -------------------------------------------------------------------
@app.on_message(filters.group, group=6)
async def today_watcher(_, message: Message):
    if not message.from_user:
        return

    reset_today_if_needed()
    chat_id = message.chat.id
    uid = message.from_user.id

    today_counts.setdefault(chat_id, {})
    today_counts[chat_id][uid] = today_counts[chat_id].get(uid, 0) + 1


@app.on_message(filters.group, group=7)
async def global_watcher(_, message: Message):
    if not message.from_user:
        return
    try:
        await db_inc_user_messages(message.from_user.id)
    except Exception as e:
        print(f"[ranking] DB increment error: {e}")


# -------------------------------------------------------------------
# RESOLVE USERNAMES
# -------------------------------------------------------------------
async def resolve_name(user_id: int) -> str:
    try:
        u = await app.get_users(user_id)
        if u.first_name:
            return u.first_name
        if u.username:
            return u.username
        return "Unknown"
    except:
        return "Unknown"


def format_leaderboard(title: str, items: List[Tuple[str, int]]) -> str:
    text = f"<blockquote><b>📈 {title}</b></blockquote>\n"
    for i, (name, count) in enumerate(items, 1):
        text += f"<blockquote><b>{i}</b>. {name} • {count}</blockquote>\n"
    return text


# -------------------------------------------------------------------
# COMMANDS
# -------------------------------------------------------------------
@app.on_message(filters.command("today") & filters.group)
async def cmd_today(_, message: Message):
    chat_id = message.chat.id
    reset_today_if_needed()

    if chat_id not in today_counts or not today_counts[chat_id]:
        return await message.reply_text("No data available for today.")

    pairs = sorted(today_counts[chat_id].items(), key=lambda x: x[1], reverse=True)[:10]
    items = [(await resolve_name(uid), cnt) for uid, cnt in pairs]

    text = format_leaderboard("Leaderboard Today", items)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Overall", callback_data="overall")]])

    try:
        await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
    except:
        await message.reply_text(text, reply_markup=kb)


@app.on_message(filters.command("ranking") & filters.group)
async def cmd_ranking(_, message: Message):
    top = await db_get_top("total_messages")
    if not top:
        return await message.reply_text("No ranking data available.")

    items = [(await resolve_name(x["_id"]), x.get("total_messages", 0)) for x in top]
    text = format_leaderboard("Leaderboard (Global)", items)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Today", callback_data="today")]])

    try:
        await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
    except:
        await message.reply_text(text, reply_markup=kb)


@app.on_message(filters.command("myrank") & filters.group)
async def cmd_myrank(_, message: Message):
    uid = message.from_user.id
    total, weekly, monthly = await db_get_user_counts(uid)
    r1 = await db_get_rank_for_field(uid, "total_messages")
    r2 = await db_get_rank_for_field(uid, "weekly_messages")
    r3 = await db_get_rank_for_field(uid, "monthly_messages")

    text = (
        "<blockquote><b>📊 Your Rank</b></blockquote>\n"
        f"<blockquote>• Global: #{r1} • {total} msgs</blockquote>\n"
        f"<blockquote>• Weekly: #{r2} • {weekly} msgs</blockquote>\n"
        f"<blockquote>• Monthly: #{r3} • {monthly} msgs</blockquote>"
    )
    await message.reply_text(text)


# -------------------------------------------------------------------
# CALLBACKS
# -------------------------------------------------------------------
@app.on_callback_query(filters.regex("^today$"))
async def cb_today(_, q: CallbackQuery):
    chat_id = q.message.chat.id
    reset_today_if_needed()

    if chat_id not in today_counts or not today_counts[chat_id]:
        return await q.answer("No data today", show_alert=True)

    pairs = sorted(today_counts[chat_id].items(), key=lambda x: x[1], reverse=True)[:10]
    items = [(await resolve_name(uid), cnt) for uid, cnt in pairs]
    text = format_leaderboard("Leaderboard Today", items)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Overall", callback_data="overall")]])

    try:
        await q.message.edit_text(text, reply_markup=kb)
    except:
        await q.answer("Unable to edit message", show_alert=True)


@app.on_callback_query(filters.regex("^overall$"))
async def cb_overall(_, q: CallbackQuery):
    top = await db_get_top("total_messages")
    items = [(await resolve_name(x["_id"]), x.get("total_messages", 0)) for x in top]
    text = format_leaderboard("Leaderboard (Global)", items)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Today", callback_data="today")]])

    try:
        await q.message.edit_text(text, reply_markup=kb)
    except:
        await q.answer("Error editing", show_alert=True)


# -------------------------------------------------------------------
# AUTO-POST SYSTEM
# -------------------------------------------------------------------
async def collect_group_chats():
    chats = []
    try:
        async for dialog in app.iter_dialogs():
            c = dialog.chat
            if c.type in ("group", "supergroup"):
                chats.append(c.id)
    except Exception as e:
        print(f"[ranking] dialog error: {e}")
    return list(set(chats))


async def build_post_texts():
    # GLOBAL
    g = await db_get_top("total_messages")
    g_items = [(await resolve_name(x["_id"]), x.get("total_messages", 0)) for x in g]
    t_global = format_leaderboard("Leaderboard (Global)", g_items)

    # WEEKLY
    w = await db_get_top("weekly_messages")
    w_items = [(await resolve_name(x["_id"]), x.get("weekly_messages", 0)) for x in w]
    t_weekly = format_leaderboard("Leaderboard (Weekly)", w_items)

    # MONTHLY
    m = await db_get_top("monthly_messages")
    m_items = [(await resolve_name(x["_id"]), x.get("monthly_messages", 0)) for x in m]
    t_monthly = format_leaderboard("Leaderboard (Monthly)", m_items)

    return t_global, t_weekly, t_monthly


async def post_daily_leaderboards():
    now = ist_now()
    weekday = now.weekday()     # Monday = 0
    day = now.day               # 1 = month start

    t_global, t_weekly, t_monthly = await build_post_texts()
    groups = await collect_group_chats()

    kb_today = InlineKeyboardMarkup([[InlineKeyboardButton("Today", callback_data="today")]])
    kb_overall = InlineKeyboardMarkup([[InlineKeyboardButton("Overall", callback_data="overall")]])

    reset_today_if_needed()

    for chat_id in groups:
        # Today per-chat
        if chat_id in today_counts and today_counts[chat_id]:
            pairs = sorted(today_counts[chat_id].items(), key=lambda x: x[1], reverse=True)[:10]
            items = [(await resolve_name(uid), cnt) for uid, cnt in pairs]
            text_today = format_leaderboard("Leaderboard Today", items)

            try:
                await app.send_photo(chat_id, RANKING_PIC, caption=text_today, reply_markup=kb_overall)
            except:
                await app.send_message(chat_id, text_today, reply_markup=kb_overall)

        # Global
        try:
            await app.send_photo(chat_id, RANKING_PIC, caption=t_global, reply_markup=kb_today)
        except:
            await app.send_message(chat_id, t_global, reply_markup=kb_today)

        # Weekly (Monday)
        if weekday == 0:
            try:
                await app.send_photo(chat_id, RANKING_PIC, caption=t_weekly, reply_markup=kb_today)
            except:
                await app.send_message(chat_id, t_weekly, reply_markup=kb_today)

        # Monthly (1st)
        if day == 1:
            try:
                await app.send_photo(chat_id, RANKING_PIC, caption=t_monthly, reply_markup=kb_today)
            except:
                await app.send_message(chat_id, t_monthly, reply_markup=kb_today)

    # resets
    if weekday == 0:
        await db_reset_field("weekly_messages")
    if day == 1:
        await db_reset_field("monthly_messages")


async def schedule_daily_poster():
    print(f"[ranking] Scheduler running → posts at {POST_HOUR:02d}:{POST_MINUTE:02d} IST daily")

    while True:
        now = ist_now()
        target = now.replace(hour=POST_HOUR, minute=POST_MINUTE, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)

        sleep_for = (target - now).total_seconds()
        await asyncio.sleep(sleep_for)

        try:
            await post_daily_leaderboards()
        except Exception as e:
            print(f"[ranking] posting failed: {e}")
            await asyncio.sleep(30)


# -------------------------------------------------------------------
# START SCHEDULER SAFELY (PYROGRAM v2)
# -------------------------------------------------------------------
@app.on_ready
async def start_scheduler(_, __):
    print("[ranking] Starting daily scheduler…")
    asyncio.create_task(schedule_daily_poster())
