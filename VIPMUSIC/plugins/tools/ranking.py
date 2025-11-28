# VIPMUSIC/plugins/tools/ranking.py
import asyncio
import datetime
import time
from typing import Dict, List, Tuple, Optional
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
except Exception:
    POST_HOUR = 21
    POST_MINUTE = 0

TZ = ZoneInfo("Asia/Kolkata")

# -------------------------------------------------------------------
# DB SETUP (motor async)
# -------------------------------------------------------------------
mongo = AsyncIOMotorClient(MONGO_DB_URI)
_default_db = mongo.get_default_database()
db = _default_db if _default_db is not None else mongo["ghosttlead"]
ranking_db = db["ranking"]

# -------------------------------------------------------------------
# TODAY COUNTS (RAM)
# -------------------------------------------------------------------
_today_counts: Dict[int, Dict[int, int]] = {}
_today_lock = asyncio.Lock()
_last_reset_date: Optional[datetime.date] = None

_USERNAME_CACHE: Dict[int, Tuple[str, float]] = {}
_USERNAME_CACHE_TTL = 3600  # 1 hour


# -------------------------------------------------------------------
# DB HELPERS
# -------------------------------------------------------------------
async def db_inc_user_messages(user_id: int) -> None:
    try:
        await ranking_db.update_one(
            {"_id": user_id},
            {"$inc": {"total_messages": 1, "weekly_messages": 1, "monthly_messages": 1}},
            upsert=True,
        )
    except Exception as e:
        print(f"[ranking] db_inc_user_messages error: {e}")


async def db_get_top(field: str = "total_messages", limit: int = 10) -> List[dict]:
    try:
        cursor = ranking_db.find({}, {field: 1}).sort(field, -1).limit(limit)
        return await cursor.to_list(length=limit)
    except Exception as e:
        print(f"[ranking] db_get_top error: {e}")
        return []


async def db_reset_field(field: str) -> None:
    try:
        await ranking_db.update_many({}, {"$set": {field: 0}})
    except Exception as e:
        print(f"[ranking] db_reset_field error: {e}")


async def db_get_user_counts(user_id: int) -> Tuple[int, int, int]:
    try:
        doc = await ranking_db.find_one(
            {"_id": user_id},
            {"total_messages": 1, "weekly_messages": 1, "monthly_messages": 1},
        )
        if not doc:
            return 0, 0, 0
        return (
            int(doc.get("total_messages", 0)),
            int(doc.get("weekly_messages", 0)),
            int(doc.get("monthly_messages", 0)),
        )
    except Exception as e:
        print(f"[ranking] db_get_user_counts error: {e}")
        return 0, 0, 0


async def db_get_rank_for_field(user_id: int, field: str) -> int:
    try:
        doc = await ranking_db.find_one({"_id": user_id}, {field: 1})
        user_val = int(doc.get(field, 0)) if doc else 0
        greater = await ranking_db.count_documents({field: {"$gt": user_val}})
        return greater + 1
    except Exception as e:
        print(f"[ranking] db_get_rank_for_field error: {e}")
        return 0


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------
def ist_now() -> datetime.datetime:
    return datetime.datetime.now(TZ)


def reset_today_if_needed():
    global _today_counts, _last_reset_date
    now_date = ist_now().date()
    if _last_reset_date != now_date:
        _today_counts = {}
        _last_reset_date = now_date


async def resolve_name(user_id: int) -> str:
    try:
        entry = _USERNAME_CACHE.get(user_id)
        now_ts = time.time()

        if entry:
            name, exp = entry
            if now_ts < exp:
                return name

        try:
            u = await app.get_users(user_id)
        except Exception:
            _USERNAME_CACHE[user_id] = (str(user_id), now_ts + _USERNAME_CACHE_TTL)
            return str(user_id)

        name = None
        if getattr(u, "first_name", None):
            name = u.first_name
            if getattr(u, "last_name", None):
                name = f"{name} {u.last_name}"
        elif getattr(u, "username", None):
            name = u.username

        if not name:
            name = str(user_id)

        _USERNAME_CACHE[user_id] = (name, now_ts + _USERNAME_CACHE_TTL)
        return name

    except Exception as e:
        print(f"[ranking] resolve_name error: {e}")
        return str(user_id)


def format_leaderboard(title: str, items: List[Tuple[str, int]]) -> str:
    lines = [f"<blockquote><b>📈 {title}</b></blockquote>"]
    if not items:
        return "\n".join(lines + ["<blockquote>No entries yet.</blockquote>"])

    for i, (name, count) in enumerate(items, 1):
        if len(name) > 30:
            name = name[:27] + "..."
        lines.append(f"<blockquote><b>{i}.</b> {name} — <code>{count}</code></blockquote>")
    return "\n".join(lines)


# -------------------------------------------------------------------
# WATCHERS (SAFE + WILL NOT BLOCK ANY COMMAND)
# -------------------------------------------------------------------

# Global counter watcher — runs last
@app.on_message(filters.group & filters.text & ~filters.regex(r"^/"), group=9999)
async def watcher_global(_, message: Message):
    try:
        if message.from_user:
            await db_inc_user_messages(message.from_user.id)
    except Exception as e:
        print(f"[ranking] watcher_global error: {e}")


# Today watcher
@app.on_message(filters.group & filters.text & ~filters.regex(r"^/"), group=10000)
async def watcher_today(_, message: Message):
    try:
        if not message.from_user:
            return

        reset_today_if_needed()
        cid = message.chat.id
        uid = message.from_user.id

        async with _today_lock:
            if cid not in _today_counts:
                _today_counts[cid] = {}
            _today_counts[cid][uid] = _today_counts[cid].get(uid, 0) + 1
    except Exception as e:
        print(f"[ranking] watcher_today error: {e}")


# -------------------------------------------------------------------
# COMMANDS
# -------------------------------------------------------------------
@app.on_message(filters.command("today") & filters.group)
async def cmd_today(_, message: Message):
    try:
        chat_id = message.chat.id
        reset_today_if_needed()

        async with _today_lock:
            chat_counts = _today_counts.get(chat_id, {})

        if not chat_counts:
            return await message.reply_text("No data available for today.")

        pairs = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        items = [(await resolve_name(uid), cnt) for uid, cnt in pairs]

        text = format_leaderboard("Leaderboard Today", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Overall", callback_data="overall")],
                [InlineKeyboardButton("Monthly", callback_data="monthly"),
                 InlineKeyboardButton("Weekly", callback_data="weekly")],
            ]
        )

        try:
            await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
        except:
            await message.reply_text(text, reply_markup=kb)

    except Exception as e:
        print(f"[ranking] cmd_today error: {e}")


@app.on_message(filters.command("ranking") & filters.group)
async def cmd_ranking(_, message: Message):
    try:
        top = await db_get_top("total_messages", 10)
        if not top:
            return await message.reply_text("No ranking data available.")

        items = [(await resolve_name(row["_id"]), row.get("total_messages", 0)) for row in top]

        text = format_leaderboard("Leaderboard (Global)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [InlineKeyboardButton("Monthly", callback_data="monthly"),
                 InlineKeyboardButton("Weekly", callback_data="weekly")],
            ]
        )

        try:
            await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
        except:
            await message.reply_text(text, reply_markup=kb)

    except Exception as e:
        print(f"[ranking] cmd_ranking error: {e}")


@app.on_message(filters.command("myrank") & filters.group)
async def cmd_myrank(_, message: Message):
    try:
        uid = message.from_user.id
        total, weekly, monthly = await db_get_user_counts(uid)
        rank_total = await db_get_rank_for_field(uid, "total_messages")
        rank_weekly = await db_get_rank_for_field(uid, "weekly_messages")
        rank_monthly = await db_get_rank_for_field(uid, "monthly_messages")

        text = (
            f"<blockquote><b>📊 Your Rank</b></blockquote>\n"
            f"<blockquote>• Global: <b>#{rank_total}</b> — <code>{total}</code> msgs</blockquote>\n"
            f"<blockquote>• Weekly: <b>#{rank_weekly}</b> — <code>{weekly}</code> msgs</blockquote>\n"
            f"<blockquote>• Monthly: <b>#{rank_monthly}</b> — <code>{monthly}</code> msgs</blockquote>"
        )
        await message.reply_text(text)

    except Exception as e:
        print(f"[ranking] cmd_myrank error: {e}")


@app.on_message(filters.command("weeklyrank") & filters.group)
async def cmd_weekly(_, message: Message):
    try:
        top = await db_get_top("weekly_messages", 10)
        if not top:
            return await message.reply_text("No weekly data.")

        items = [(await resolve_name(row["_id"]), row.get("weekly_messages", 0)) for row in top]
        text = format_leaderboard("Leaderboard (Weekly)", items)

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [InlineKeyboardButton("Overall", callback_data="overall"),
                 InlineKeyboardButton("Monthly", callback_data="monthly")],
            ]
        )

        try:
            await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
        except:
            await message.reply_text(text, reply_markup=kb)

    except Exception as e:
        print(f"[ranking] cmd_weekly error: {e}")


@app.on_message(filters.command("monthlyrank") & filters.group)
async def cmd_monthly(_, message: Message):
    try:
        top = await db_get_top("monthly_messages", 10)
        if not top:
            return await message.reply_text("No monthly data.")

        items = [(await resolve_name(row["_id"]), row.get("monthly_messages", 0)) for row in top]
        text = format_leaderboard("Leaderboard (Monthly)", items)

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [InlineKeyboardButton("Overall", callback_data="overall"),
                 InlineKeyboardButton("Weekly", callback_data="weekly")],
            ]
        )

        try:
            await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
        except:
            await message.reply_text(text, reply_markup=kb)

    except Exception as e:
        print(f"[ranking] cmd_monthly error: {e}")


# -------------------------------------------------------------------
# CALLBACKS
# -------------------------------------------------------------------
async def _safe_edit(query: CallbackQuery, text: str, kb):
    try:
        return await query.message.edit_text(text, reply_markup=kb)
    except:
        try:
            await query.answer("Unable to update!", show_alert=True)
        except:
            pass


@app.on_callback_query(filters.regex("^today$"))
async def cb_today(_, q: CallbackQuery):
    try:
        cid = q.message.chat.id
        reset_today_if_needed()

        async with _today_lock:
            chat_counts = _today_counts.get(cid, {})

        if not chat_counts:
            return await q.answer("No data!", show_alert=True)

        pairs = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        items = [(await resolve_name(uid), cnt) for uid, cnt in pairs]

        text = format_leaderboard("Leaderboard Today", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Overall", callback_data="overall")],
                [InlineKeyboardButton("Monthly", callback_data="monthly"),
                 InlineKeyboardButton("Weekly", callback_data="weekly")],
            ]
        )

        await _safe_edit(q, text, kb)

    except Exception as e:
        print(f"[ranking] cb_today error: {e}")


@app.on_callback_query(filters.regex("^overall$"))
async def cb_overall(_, q: CallbackQuery):
    try:
        top = await db_get_top("total_messages", 10)
        items = [(await resolve_name(row["_id"]), row.get("total_messages", 0)) for row in top]

        text = format_leaderboard("Leaderboard (Global)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [InlineKeyboardButton("Monthly", callback_data="monthly"),
                 InlineKeyboardButton("Weekly", callback_data="weekly")],
            ]
        )

        await _safe_edit(q, text, kb)

    except Exception as e:
        print(f"[ranking] cb_overall error: {e}")


@app.on_callback_query(filters.regex("^monthly$"))
async def cb_monthly(_, q: CallbackQuery):
    try:
        top = await db_get_top("monthly_messages", 10)
        items = [(await resolve_name(row["_id"]), row.get("monthly_messages", 0)) for row in top]

        text = format_leaderboard("Leaderboard (Monthly)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [InlineKeyboardButton("Overall", callback_data="overall"),
                 InlineKeyboardButton("Weekly", callback_data="weekly")],
            ]
        )

        await _safe_edit(q, text, kb)

    except Exception as e:
        print(f"[ranking] cb_monthly error: {e}")


@app.on_callback_query(filters.regex("^weekly$"))
async def cb_weekly(_, q: CallbackQuery):
    try:
        top = await db_get_top("weekly_messages", 10)
        items = [(await resolve_name(row["_id"]), row.get("weekly_messages", 0)) for row in top]

        text = format_leaderboard("Leaderboard (Weekly)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [InlineKeyboardButton("Overall", callback_data="overall"),
                 InlineKeyboardButton("Monthly", callback_data="monthly")],
            ]
        )

        await _safe_edit(q, text, kb)

    except Exception as e:
        print(f"[ranking] cb_weekly error: {e}")
