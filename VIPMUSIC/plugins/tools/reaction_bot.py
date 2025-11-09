# VIPMUSIC/plugins/tools/reaction_bot.py
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from VIPMUSIC import app
from VIPMUSIC.utils.databases import reactiondb
import config

print("[ReactionBot] Plugin loaded!")

# --- Helper to check if user can manage reactions ---
async def can_manage(user_id: int, chat_id: int):
    if user_id == config.OWNER_ID or user_id in map(int, config.SUDOERS):
        return True
    member = await app.get_chat_member(chat_id, user_id)
    if member.status in ["administrator", "creator"]:
        return True
    return False

# --- /reactionon Command ---
@app.on_message(filters.command("reactionon", prefixes="/") & (filters.group | filters.supergroup))
async def reaction_on_cmd(_, message):
    if not await can_manage(message.from_user.id, message.chat.id):
        await message.reply_text("❌ You are not allowed to use this command!")
        return

    await reactiondb.reaction_on(message.chat.id)
    await message.reply_text("✅ Reactions enabled for this group!")

# --- /reactionoff Command ---
@app.on_message(filters.command("reactionoff", prefixes="/") & (filters.group | filters.supergroup))
async def reaction_off_cmd(_, message):
    if not await can_manage(message.from_user.id, message.chat.id):
        await message.reply_text("❌ You are not allowed to use this command!")
        return

    await reactiondb.reaction_off(message.chat.id)
    await message.reply_text("❌ Reactions disabled for this group!")

# --- /reaction Command (buttons) ---
@app.on_message(filters.command("reaction", prefixes="/") & (filters.group | filters.supergroup))
async def reaction_button_cmd(_, message):
    if not await can_manage(message.from_user.id, message.chat.id):
        await message.reply_text("❌ You are not allowed to use this command!")
        return

    # Check current status
    status = await reactiondb.is_reaction_on(message.chat.id)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Enable", callback_data="reaction_enable"),
                InlineKeyboardButton("❌ Disable", callback_data="reaction_disable")
            ]
        ]
    )
    text = f"Reactions are currently **{'Enabled' if status else 'Disabled'}**"
    await message.reply_text(text, reply_markup=kb)

# --- Callback for Buttons ---
@app.on_callback_query(filters.regex(r"^reaction_(enable|disable)$"))
async def reaction_callback(_, query):
    user_id = query.from_user.id
    chat_id = query.message.chat.id

    if not await can_manage(user_id, chat_id):
        await query.answer("❌ You are not allowed to do this!", show_alert=True)
        return

    action = query.data.split("_")[1]
    if action == "enable":
        await reactiondb.reaction_on(chat_id)
        await query.message.edit_text("✅ Reactions enabled!", reply_markup=None)
    else:
        await reactiondb.reaction_off(chat_id)
        await query.message.edit_text("❌ Reactions disabled!", reply_markup=None)

# --- Test command ---
@app.on_message(filters.command("reactiontest", prefixes="/") & (filters.group | filters.supergroup))
async def test_react_cmd(_, message):
    print("[ReactionBot] /reactiontest command triggered!")
    await message.reply_text("✅ Reaction test command works!")
