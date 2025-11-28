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
# DB init fix
_default_db = mongo.get_default_database()
db = _default_db if _default_db is not None else mongo["ghosttlead"]
ranking_db = db["ranking"] # docs: { _id: user_id, total_messages, weekly_messages, monthly_messages }

# -------------------------------------------------------------------
# TODAY COUNTS (RAM) - memory-safe structure + lock for concurrency
# -------------------------------------------------------------------
_today_counts: Dict[int, Dict[int, int]] = {}
_today_lock = asyncio.Lock()
_last_reset_date: Optional[datetime.date] = None

# Keep a small TTL cache for resolved usernames to avoid repeated API calls
_USERNAME_CACHE: Dict[int, Tuple[str, float]] = {}
_USERNAME_CACHE_TTL = 60 * 60  # 1 hour

# -------------------------------------------------------------------
# DB HELPERS
# -------------------------------------------------------------------
async def db_inc_user_messages(user_id: int) -> None:
    """Increment total/weekly/monthly for a user."""
    try:
        # Use $inc with upsert for atomic increment
        await ranking_db.update_one(
            {"_id": user_id},
            {"$inc": {"total_messages": 1, "weekly_messages": 1, "monthly_messages": 1}},
            upsert=True,
        )
    except Exception as e:
        # Log but do not raise — watchers must never crash the main flow
        print(f"[ranking] db_inc_user_messages error for {user_id}: {e}")


async def db_get_top(field: str = "total_messages", limit: int = 10) -> List[dict]:
    """Return top documents sorted by provided field. Use projection to reduce bandwidth."""
    try:
        cursor = ranking_db.find({}, {field: 1}).sort(field, -1).limit(limit)
        return await cursor.to_list(length=limit)
    except Exception as e:
        print(f"[ranking] db_get_top error for {field}: {e}")
        return []


async def db_reset_field(field: str) -> None:
    """Reset a numeric field to 0 for all users."""
    try:
        await ranking_db.update_many({}, {"$set": {field: 0}})
    except Exception as e:
        print(f"[ranking] db_reset_field error for {field}: {e}")


async def db_get_user_counts(user_id: int) -> Tuple[int, int, int]:
    """Return (total, weekly, monthly) counts for a user (0 if not present)."""
    try:
        doc = await ranking_db.find_one({"_id": user_id}, {"total_messages": 1, "weekly_messages": 1, "monthly_messages": 1})
        if not doc:
            return 0, 0, 0
        return (
            int(doc.get("total_messages", 0)),
            int(doc.get("weekly_messages", 0)),
            int(doc.get("monthly_messages", 0)),
        )
    except Exception as e:
        print(f"[ranking] db_get_user_counts error for {user_id}: {e}")
        return 0, 0, 0


async def db_get_rank_for_field(user_id: int, field: str) -> int:
    """Return 1-based rank of user for given field."""
    try:
        doc = await ranking_db.find_one({"_id": user_id}, {field: 1})
        user_val = int(doc.get(field, 0)) if doc else 0
        greater = await ranking_db.count_documents({field: {"$gt": user_val}})
        return greater + 1
    except Exception as e:
        print(f"[ranking] db_get_rank_for_field error for {user_id} {field}: {e}")
        return 0

# -------------------------------------------------------------------
# TIME HELPERS
# -------------------------------------------------------------------
def ist_now() -> datetime.datetime:
    return datetime.datetime.now(TZ)


def reset_today_if_needed():
    """Reset _today_counts once per IST day (midnight IST)."""
    global _today_counts, _last_reset_date
    now_date = ist_now().date()
    if _last_reset_date != now_date:
        _today_counts = {}
        _last_reset_date = now_date

# -------------------------------------------------------------------
# USERNAME RESOLUTION WITH CACHE
# -------------------------------------------------------------------
async def resolve_name(user_id: int) -> str:
    """Resolve a user id to a display name, with a short in-memory TTL cache."""
    # check cache first
    try:
        entry = _USERNAME_CACHE.get(user_id)
        now_ts = time.time()
        if entry:
            name, expires = entry
            if now_ts < expires:
                return name
            # expired: fallthrough to refresh

        # fetch from Telegram
        try:
            u = await app.get_users(user_id)
        except Exception:
            # get_users can fail for deleted users, bots or privacy
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

        # store in cache
        _USERNAME_CACHE[user_id] = (name, now_ts + _USERNAME_CACHE_TTL)
        return name
    except Exception as e:
        print(f"[ranking] resolve_name unexpected error for {user_id}: {e}")
        return str(user_id)

# -------------------------------------------------------------------
# FORMATTING
# -------------------------------------------------------------------
def format_leaderboard(title: str, items: List[Tuple[str, int]]) -> str:
    """Produce compact, readable leaderboard text suitable for caption/message."""
    lines = [f"<blockquote><b>📈 {title}</b></blockquote>"]
    if not items:
        lines.append("<blockquote>No entries yet.</blockquote>")
    else:
        for i, (name, count) in enumerate(items, 1):
            # truncate long names sensibly
            display_name = name if len(name) <= 30 else name[:27] + "..."
            lines.append(f"<blockquote><b>{i}.</b> {display_name} — <code>{count}</code></blockquote>")
    return "\n".join(lines)

# -------------------------------------------------------------------
# WATCHERS (SAFE)
# -------------------------------------------------------------------
# -------------------------------------------------------------------
# WATCHERS (SAFE + NON-BLOCKING)
# -------------------------------------------------------------------

# Count today's messages — run AFTER all other handlers
@app.on_message(filters.group & ~filters.command(), group=99)
async def today_watcher(_, message: Message):
    try:
        if not message.from_user:
            return
        reset_today_if_needed()
        chat_id = message.chat.id
        user_id = message.from_user.id

        async with _today_lock:
            if chat_id not in _today_counts:
                _today_counts[chat_id] = {}
            _today_counts[chat_id][user_id] = _today_counts[chat_id].get(user_id, 0) + 1
    except Exception as e:
        print(f"[ranking] today_watcher error: {e}")


# Global / weekly / monthly counter — ALSO run last
@app.on_message(filters.group & ~filters.command(), group=100)
async def global_watcher(_, message: Message):
    try:
        if not message.from_user:
            return
        user_id = message.from_user.id
        await db_inc_user_messages(user_id)
    except Exception as e:
        print(f"[ranking] global_watcher error: {e}")

# -------------------------------------------------------------------
# COMMANDS: /today, /ranking, /myrank, /weeklyrank, /monthlyrank
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
        items = []
        for uid, cnt in pairs:
            name = await resolve_name(uid)
            items.append((name, cnt))

        text = format_leaderboard("Leaderboard Today", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Overall", callback_data="overall")],
                [
                    InlineKeyboardButton("Monthly", callback_data="monthly"),
                    InlineKeyboardButton("Weekly", callback_data="weekly"),
                ],
            ]
        )
        try:
            await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
        except Exception:
            await message.reply_text(text, reply_markup=kb)
    except Exception as e:
        print(f"[ranking] cmd_today error: {e}")
        try:
            await message.reply_text("An error occurred while preparing today's leaderboard.")
        except Exception:
            pass


@app.on_message(filters.command("ranking") & filters.group)
async def cmd_ranking(_, message: Message):
    try:
        top = await db_get_top("total_messages", 10)
        if not top:
            return await message.reply_text("No ranking data available.")

        items = []
        for row in top:
            uid = row.get("_id")
            name = await resolve_name(uid)
            items.append((name, int(row.get("total_messages", 0))))

        text = format_leaderboard("Leaderboard (Global)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [
                    InlineKeyboardButton("Monthly", callback_data="monthly"),
                    InlineKeyboardButton("Weekly", callback_data="weekly"),
                ],
            ]
        )
        try:
            await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
        except Exception:
            await message.reply_text(text, reply_markup=kb)
    except Exception as e:
        print(f"[ranking] cmd_ranking error: {e}")
        try:
            await message.reply_text("An error occurred while fetching rankings.")
        except Exception:
            pass


@app.on_message(filters.command("myrank") & filters.group)
async def cmd_myrank(_, message: Message):
    try:
        if not message.from_user:
            return
        user_id = message.from_user.id
        total, weekly, monthly = await db_get_user_counts(user_id)
        rank_total = await db_get_rank_for_field(user_id, "total_messages")
        rank_weekly = await db_get_rank_for_field(user_id, "weekly_messages")
        rank_monthly = await db_get_rank_for_field(user_id, "monthly_messages")

        text = (
            f"<blockquote><b>📊 Your Rank</b></blockquote>\n"
            f"<blockquote>• Global: <b>#{rank_total}</b> — <code>{total}</code> msgs</blockquote>\n"
            f"<blockquote>• Weekly: <b>#{rank_weekly}</b> — <code>{weekly}</code> msgs</blockquote>\n"
            f"<blockquote>• Monthly: <b>#{rank_monthly}</b> — <code>{monthly}</code> msgs</blockquote>"
        )
        await message.reply_text(text)
    except Exception as e:
        print(f"[ranking] cmd_myrank error: {e}")
        try:
            await message.reply_text("An error occurred while fetching your rank.")
        except Exception:
            pass


@app.on_message(filters.command("weeklyrank") & filters.group)
async def cmd_weeklyrank(_, message: Message):
    try:
        top = await db_get_top("weekly_messages", 10)
        if not top:
            return await message.reply_text("No weekly ranking data available.")

        items = []
        for row in top:
            uid = row.get("_id")
            name = await resolve_name(uid)
            items.append((name, int(row.get("weekly_messages", 0))))

        text = format_leaderboard("Leaderboard (Weekly)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [
                    InlineKeyboardButton("Overall", callback_data="overall"),
                    InlineKeyboardButton("Monthly", callback_data="monthly"),
                ],
            ]
        )
        try:
            await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
        except Exception:
            await message.reply_text(text, reply_markup=kb)
    except Exception as e:
        print(f"[ranking] cmd_weeklyrank error: {e}")
        try:
            await message.reply_text("An error occurred while fetching weekly rankings.")
        except Exception:
            pass


@app.on_message(filters.command("monthlyrank") & filters.group)
async def cmd_monthlyrank(_, message: Message):
    try:
        top = await db_get_top("monthly_messages", 10)
        if not top:
            return await message.reply_text("No monthly ranking data available.")

        items = []
        for row in top:
            uid = row.get("_id")
            name = await resolve_name(uid)
            items.append((name, int(row.get("monthly_messages", 0))))

        text = format_leaderboard("Leaderboard (Monthly)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [
                    InlineKeyboardButton("Overall", callback_data="overall"),
                    InlineKeyboardButton("Weekly", callback_data="weekly"),
                ],
            ]
        )
        try:
            await message.reply_photo(RANKING_PIC, caption=text, reply_markup=kb)
        except Exception:
            await message.reply_text(text, reply_markup=kb)
    except Exception as e:
        print(f"[ranking] cmd_monthlyrank error: {e}")
        try:
            await message.reply_text("An error occurred while fetching monthly rankings.")
        except Exception:
            pass

# -------------------------------------------------------------------
# CALLBACKS for inline buttons (safe edits)
# -------------------------------------------------------------------
async def _safe_edit_message(query: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        if query.message:
            await query.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await query.answer("Unable to update leaderboard.", show_alert=True)
        except Exception:
            pass


@app.on_callback_query(filters.regex("^today$"))
async def cb_today(_, query: CallbackQuery):
    try:
        if not query.message or not query.message.chat:
            return await query.answer("No chat info.", show_alert=True)
        chat_id = query.message.chat.id
        reset_today_if_needed()
        async with _today_lock:
            chat_counts = _today_counts.get(chat_id, {})

        if not chat_counts:
            return await query.answer("No data for today.", show_alert=True)

        pairs = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        items = []
        for uid, cnt in pairs:
            name = await resolve_name(uid)
            items.append((name, cnt))

        text = format_leaderboard("Leaderboard Today", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Overall", callback_data="overall")],
                [
                    InlineKeyboardButton("Monthly", callback_data="monthly"),
                    InlineKeyboardButton("Weekly", callback_data="weekly"),
                ],
            ]
        )
        await _safe_edit_message(query, text, kb)
    except Exception as e:
        print(f"[ranking] cb_today error: {e}")
        try:
            await query.answer("Error generating leaderboard.", show_alert=True)
        except Exception:
            pass


@app.on_callback_query(filters.regex("^overall$"))
async def cb_overall(_, query: CallbackQuery):
    try:
        top = await db_get_top("total_messages", 10)
        if not top:
            return await query.answer("No ranking data.", show_alert=True)

        items = []
        for row in top:
            uid = row.get("_id")
            name = await resolve_name(uid)
            items.append((name, int(row.get("total_messages", 0))))

        text = format_leaderboard("Leaderboard (Global)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [
                    InlineKeyboardButton("Monthly", callback_data="monthly"),
                    InlineKeyboardButton("Weekly", callback_data="weekly"),
                ],
            ]
        )
        await _safe_edit_message(query, text, kb)
    except Exception as e:
        print(f"[ranking] cb_overall error: {e}")
        try:
            await query.answer("Unable to edit message.", show_alert=True)
        except Exception:
            pass


@app.on_callback_query(filters.regex("^monthly$"))
async def cb_monthly(_, q: CallbackQuery):
    try:
        top = await db_get_top("monthly_messages", 10)
        if not top:
            return await q.answer("No monthly data.", show_alert=True)

        items = []
        for row in top:
            uid = row.get("_id")
            name = await resolve_name(uid)
            items.append((name, int(row.get("monthly_messages", 0))))

        text = format_leaderboard("Leaderboard (Monthly)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [
                    InlineKeyboardButton("Overall", callback_data="overall"),
                    InlineKeyboardButton("Weekly", callback_data="weekly"),
                ],
            ]
        )
        await _safe_edit_message(q, text, kb)
    except Exception as e:
        print(f"[ranking] cb_monthly error: {e}")
        try:
            await q.answer("Error editing", show_alert=True)
        except Exception:
            pass


@app.on_callback_query(filters.regex("^weekly$"))
async def cb_weekly(_, q: CallbackQuery):
    try:
        top = await db_get_top("weekly_messages", 10)
        if not top:
            return await q.answer("No weekly data.", show_alert=True)

        items = []
        for row in top:
            uid = row.get("_id")
            name = await resolve_name(uid)
            items.append((name, int(row.get("weekly_messages", 0))))

        text = format_leaderboard("Leaderboard (Weekly)", items)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Today", callback_data="today")],
                [
                    InlineKeyboardButton("Overall", callback_data="overall"),
                    InlineKeyboardButton("Monthly", callback_data="monthly"),
                ],
            ]
        )
        await _safe_edit_message(q, text, kb)
    except Exception as e:
        print(f"[ranking] cb_weekly error: {e}")
        try:
            await q.answer("Error editing", show_alert=True)
        except Exception:
            pass

# -------------------------------------------------------------------
# AUTO-POST SYSTEM (improved)
# -------------------------------------------------------------------
async def collect_group_chats() -> List[int]:
    """
    Collect group & supergroup chat ids where the bot is a member.
    Uses iter_dialogs to find group/supergroup dialogs.
    """
    chats = []
    try:
        async for dialog in app.iter_dialogs():
            c = dialog.chat
            if getattr(c, "type", None) in ("group", "supergroup"):
                chats.append(c.id)
    except Exception as e:
        print(f"[ranking] Failed to iterate dialogs: {e}")
    return list(set(chats))


async def build_post_texts() -> Tuple[str, str, str]:
    """Return (global_text, weekly_text, monthly_text) pre-built strings."""
    # GLOBAL (used for global postings)
    top_global = await db_get_top("total_messages", 10)
    items_global = []
    for row in top_global:
        name = await resolve_name(row.get("_id"))
        items_global.append((name, int(row.get("total_messages", 0))))
    text_global = format_leaderboard("Leaderboard (Global)", items_global)

    # WEEKLY
    top_weekly = await db_get_top("weekly_messages", 10)
    items_weekly = []
    for row in top_weekly:
        name = await resolve_name(row.get("_id"))
        items_weekly.append((name, int(row.get("weekly_messages", 0))))
    text_weekly = format_leaderboard("Leaderboard (Weekly)", items_weekly)

    # MONTHLY
    top_monthly = await db_get_top("monthly_messages", 10)
    items_monthly = []
    for row in top_monthly:
        name = await resolve_name(row.get("_id"))
        items_monthly.append((name, int(row.get("monthly_messages", 0))))
    text_monthly = format_leaderboard("Leaderboard (Monthly)", items_monthly)

    return text_global, text_weekly, text_monthly


async def post_daily_leaderboards():
    """
    Post leaderboards:
    - per-chat today leaderboard (if that chat has today data)
    - global leaderboard (all chats)
    - if Monday also post weekly and reset weekly counters
    - if day == 1 also post monthly and reset monthly counters
    """
    try:
        now = ist_now()
        weekday = now.weekday()  # Monday == 0
        day_of_month = now.day

        text_global, text_weekly, text_monthly = await build_post_texts()

        groups = await collect_group_chats()
        if not groups:
            print("[ranking] No groups found to post to.")
            return

        for chat_id in groups:
            try:
                # build per-chat today leaderboard if any
                reset_today_if_needed()
                async with _today_lock:
                    chat_counts = _today_counts.get(chat_id, {}).copy()

                if chat_counts:
                    pairs = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                    items = []
                    for uid, cnt in pairs:
                        name = await resolve_name(uid)
                        items.append((name, cnt))
                    text_chat = format_leaderboard("Leaderboard Today", items)
                    kb = InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("Overall", callback_data="overall")],
                            [
                                InlineKeyboardButton("Monthly", callback_data="monthly"),
                                InlineKeyboardButton("Weekly", callback_data="weekly"),
                            ],
                        ]
                    )
                    try:
                        await app.send_photo(chat_id, RANKING_PIC, caption=text_chat, reply_markup=kb)
                    except Exception:
                        await app.send_message(chat_id, text_chat, reply_markup=kb)

                # Also post global leaderboard for every group
                kb2 = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("Today", callback_data="today")],
                        [
                            InlineKeyboardButton("Monthly", callback_data="monthly"),
                            InlineKeyboardButton("Weekly", callback_data="weekly"),
                        ],
                    ]
                )
                try:
                    await app.send_photo(chat_id, RANKING_PIC, caption=text_global, reply_markup=kb2)
                except Exception:
                    await app.send_message(chat_id, text_global, reply_markup=kb2)

                # If Monday, post weekly
                if weekday == 0:
                    try:
                        await app.send_photo(chat_id, RANKING_PIC, caption=text_weekly, reply_markup=kb2)
                    except Exception:
                        await app.send_message(chat_id, text_weekly, reply_markup=kb2)

                # If 1st of month, post monthly
                if day_of_month == 1:
                    try:
                        await app.send_photo(chat_id, RANKING_PIC, caption=text_monthly, reply_markup=kb2)
                    except Exception:
                        await app.send_message(chat_id, text_monthly, reply_markup=kb2)

            except Exception as inner_e:
                print(f"[ranking] failed to post to {chat_id}: {inner_e}")

        # Resets after posting:
        if weekday == 0:
            try:
                await db_reset_field("weekly_messages")
                print("[ranking] weekly_messages reset done.")
            except Exception as e:
                print(f"[ranking] weekly reset failed: {e}")

        if day_of_month == 1:
            try:
                await db_reset_field("monthly_messages")
                print("[ranking] monthly_messages reset done.")
            except Exception as e:
                print(f"[ranking] monthly reset failed: {e}")

    except Exception as e:
        print(f"[ranking] post_daily_leaderboards unexpected error: {e}")


async def schedule_daily_poster():
    """Background task: waits until next POST_HOUR:POST_MINUTE IST and posts leaderboards."""
    print(f"[ranking] Scheduler running → posts at {POST_HOUR:02d}:{POST_MINUTE:02d} IST daily")
    while True:
        try:
            now = ist_now()
            target = now.replace(hour=POST_HOUR, minute=POST_MINUTE, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            sleep_for = (target - now).total_seconds()
            # sleep in chunks to be responsive to cancellation
            while sleep_for > 0:
                await asyncio.sleep(min(300, sleep_for))
                sleep_for -= 300
            # do posting
            await post_daily_leaderboards()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[ranking] scheduler error: {e}")
            # small backoff to avoid busy-looping on persistent errors
            await asyncio.sleep(60)

# -------------------------------------------------------------------
# START SCHEDULER SAFELY USING RAW UPDATE (PYROGRAM v2 + VIP CLIENT)
# -------------------------------------------------------------------
scheduler_started = False

@app.on_raw_update()
async def start_scheduler_once(client, update, users, chats):
    """Start the scheduler once after the client is up."""
    global scheduler_started
    if scheduler_started:
        return

    scheduler_started = True
    print("[ranking] Scheduler started successfully")
    try:
        # schedule as background task (non-blocking)
        asyncio.create_task(schedule_daily_poster())
    except Exception as e:
        print(f"[ranking] Failed to start scheduler: {e}")
