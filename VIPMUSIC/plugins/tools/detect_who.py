# VIPMUSIC/plugins/tools/detect_who.py
"""
Detect & Who modules in single file.
Commands:
 - /detect [reply or @username]  -> funny analyzer report
 - /who <tag>                   -> pick someone from chat for the tag (e.g. /who love)

Requires: pyrogram, VIPMUSIC.app, config.BANNED_USERS
"""

import random
import asyncio
from typing import List, Optional
from pyrogram import filters
from pyrogram.types import Message
from VIPMUSIC import app
from config import BANNED_USERS

print("[detect_who] loaded")

# ------------------ Helpers ------------------
ATTRIBUTES = [
    ("Simp Level", 5),
    ("Attractiveness", 5),
    ("Brain Usage", 5),
    ("Luck Today", 5),
    ("Attitude", 5),
    ("Wealth Vibes", 5),
]

WHO_TAGS = {
    "love": "Most romantic",
    "beautiful": "Most beautiful",
    "smart": "Smartest",
    "active": "Most active",
    "noob": "Biggest noob",
    "funny": "Funniest",
    "hot": "Hottest",
    "shy": "Shyest",
}


def pick_percent(base: int = 50, variance: int = 30) -> int:
    """Return a percent 0-100 with a base and variance."""
    val = base + random.randint(-variance, variance)
    return max(0, min(100, val))


async def resolve_target_user(client, message: Message) -> Optional[dict]:
    """Return a (user_id, mention) dict for target in order:
    1) replied user
    2) first mentioned username in message.entities
    3) username or id argument
    4) the sender (message.from_user)
    """
    # 1) reply
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return {"id": u.id, "name": mention_user(u)}

    # 2) entities mentions
    if message.entities:
        for ent in message.entities:
            if ent.type == "mention":
                src = message.text or ""
                uname = src[ent.offset: ent.offset + ent.length]
                try:
                    user = await client.get_users(uname)
                    return {"id": user.id, "name": mention_user(user)}
                except Exception:
                    continue
            elif ent.type == "text_mention" and ent.user:
                u = ent.user
                return {"id": u.id, "name": mention_user(u)}

    # 3) argument (username or id)
    parts = message.text.split()
    if len(parts) >= 2:
        arg = parts[1].strip()
        try:
            user = await client.get_users(arg)
            return {"id": user.id, "name": mention_user(user)}
        except Exception:
            # not resolvable
            pass

    # 4) fallback to sender
    if message.from_user:
        return {"id": message.from_user.id, "name": mention_user(message.from_user)}

    return None


def mention_user(u) -> str:
    """Safe mention text for a user object or dict."""
    if not u:
        return "[user]"
    name = getattr(u, "first_name", None) or getattr(u, "username", None) or "User"
    uid = getattr(u, "id", None)
    if getattr(u, "username", None):
        return f"@{u.username}"
    if uid:
        return f"[{name}](tg://user?id={uid})"
    return name


# ------------------ /detect Command ------------------
@app.on_message(filters.command("detect") & ~BANNED_USERS)
async def detect_command(client, message: Message):
    """Funny analyzer: /detect [reply or @username or id]
    If no target provided, analyses the sender.
    """
    target = await resolve_target_user(client, message)
    if not target:
        return await message.reply_text("⚠️ Could not resolve a user to analyse.")

    # deterministic-ish for repeatability in a short window
    seed_base = f"detect:{target['id']}:{message.chat.id}"
    random.seed(seed_base + str((message.message_id // 100) ))

    parts: List[str] = [f"🔍 Analysis for {target['name']}:\n"]

    for attr, weight in ATTRIBUTES:
        # vary base and variance based on weight
        base = random.randint(30, 70)
        variance = weight * 10
        p = pick_percent(base=base, variance=variance)

        bar_len = 12
        filled = int((p / 100) * bar_len)
        bar = "█" * filled + "—" * (bar_len - filled)
        parts.append(f"**{attr}:** {p}%\n`{bar}`")

    # small horoscope style fun line
    luck = pick_percent(50, 45)
    if luck > 80:
        mood = "🍀 Lucky day! Good time for new moves."
    elif luck > 50:
        mood = "🙂 Decent vibes. Keep going."
    elif luck > 20:
        mood = "😐 Meh — be careful today."
    else:
        mood = "⚠️ Tough luck — maybe avoid big decisions."

    parts.append(f"\n{mood}")

    text = "\n\n".join(parts)

    await message.reply_text(text, disable_web_page_preview=True)


# ------------------ /who Command ------------------
@app.on_message(filters.command("who") & ~BANNED_USERS)
async def who_command(client, message: Message):
    """Pick a user from the chat by tag.

    Usage:
    /who love
    /who funny
    /who (no tag) -> random pick
    """
    # determine tag
    parts = message.text.split(maxsplit=1)
    tag_key = parts[1].strip().lower() if len(parts) > 1 else None
    tag_title = WHO_TAGS.get(tag_key, None) if tag_key else None

    # gather candidates: prefer mentioned/replied users first
    candidates = []
    if message.reply_to_message and message.reply_to_message.from_user:
        candidates.append(message.reply_to_message.from_user)

    if message.entities:
        for ent in message.entities:
            if ent.type == "mention":
                src = message.text or ""
                uname = src[ent.offset: ent.offset + ent.length]
                try:
                    user = await client.get_users(uname)
                    candidates.append(user)
                except Exception:
                    continue
            elif ent.type == "text_mention" and ent.user:
                candidates.append(ent.user)

    # if still few candidates, try to fetch some chat members (best effort)
    if len(candidates) < 3:
        try:
            # Pyrogram: get_chat_members may be paginated; using get_chat_members with limit
            members = []
            async for mem in client.get_chat_members(message.chat.id, limit=50):
                if getattr(mem, 'user', None):
                    # skip bots
                    if getattr(mem.user, 'is_bot', False):
                        continue
                    members.append(mem.user)
            # shuffle and extend
            random.shuffle(members)
            for u in members:
                if u not in candidates:
                    candidates.append(u)
                if len(candidates) >= 20:
                    break
        except Exception:
            # ignore any errors (private chats or lack of permissions)
            pass

    # final fallback
    if not candidates:
        if message.from_user:
            candidates = [message.from_user]
        else:
            return await message.reply_text("⚠️ No users available to pick.")

    # choose target
    chosen = random.choice(candidates)

    # format output
    display_tag = tag_title or (tag_key.capitalize() if tag_key else "Random Pick")
    name = mention_user(chosen)
    score = pick_percent(50, 45)

    await message.reply_text(f"**{display_tag}** ➜ {name}\n\n💯 Score: {score}%", disable_web_page_preview=True)


# ------------------ End ------------------
