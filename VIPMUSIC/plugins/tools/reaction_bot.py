# VIPMUSIC/plugins/tools/reaction_bot.py
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from VIPMUSIC import app
from VIPMUSIC.misc import SUDOERS
from VIPMUSIC.utils.databases.reactiondb import is_reaction_on, reaction_on, reaction_off
from config import START_REACTIONS, OWNER_ID

print("[ReactionBot] Plugin loaded!")

# -----------------------------
# Custom filter for SUDO + OWNER
# -----------------------------
def sudo_filter(_, __, message: Message):
    return message.from_user and (message.from_user.id in SUDOERS or message.from_user.id == OWNER_ID)

# -----------------------------
# Enable reactions command
# -----------------------------
@app.on_message(filters.command("reactionon") & filters.group & filters.create(sudo_filter))
async def enable_reaction(client, message: Message):
    chat_id = message.chat.id
    await reaction_on(chat_id)
    await message.reply_text("✅ Reactions have been enabled for this chat.")

# -----------------------------
# Disable reactions command
# -----------------------------
@app.on_message(filters.command("reactionoff") & filters.group & filters.create(sudo_filter))
async def disable_reaction(client, message: Message):
    chat_id = message.chat.id
    await reaction_off(chat_id)
    await message.reply_text("❌ Reactions have been disabled for this chat.")

# -----------------------------
# Reaction enable/disable buttons
# -----------------------------
@app.on_message(filters.command("reaction") & filters.group & filters.create(sudo_filter))
async def reaction_buttons(client, message: Message):
    chat_id = message.chat.id
    current_status = await is_reaction_on(chat_id)
    keyboard = [
        [
            InlineKeyboardButton("✅ Enable", callback_data="reaction_enable"),
            InlineKeyboardButton("❌ Disable", callback_data="reaction_disable")
        ]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    status_text = "enabled" if current_status else "disabled"
    await message.reply_text(f"Reactions are currently **{status_text}**.\nUse buttons below to change:", reply_markup=markup)

# -----------------------------
# Callback query for buttons
# -----------------------------
@app.on_callback_query(filters.regex("reaction_enable|reaction_disable"))
async def reaction_callback(client, callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    # Check permission
    if user_id not in SUDOERS and user_id != OWNER_ID:
        return await callback.answer("❌ You are not allowed to change reactions.", show_alert=True)

    if callback.data == "reaction_enable":
        await reaction_on(chat_id)
        await callback.answer("✅ Reactions enabled!", show_alert=True)
        await callback.message.edit_text("Reactions are now **enabled**.")
    elif callback.data == "reaction_disable":
        await reaction_off(chat_id)
        await callback.answer("❌ Reactions disabled!", show_alert=True)
        await callback.message.edit_text("Reactions are now **disabled**.")

# -----------------------------
# Auto-react to messages in groups
# -----------------------------
@app.on_message(filters.group & filters.text)
async def auto_react(client, message: Message):
    chat_id = message.chat.id
    if not await is_reaction_on(chat_id):
        return

    # Pick a random reaction
    import random
    reaction = random.choice(START_REACTIONS)
    try:
        await message.reply_text(reaction)
    except:
        pass

# -----------------------------
# Test command for debugging
# -----------------------------
@app.on_message(filters.command("zzztest") & filters.group & filters.create(sudo_filter))
async def test_react_cmd(client, message: Message):
    await message.reply_text("✅ Reaction bot commands are working properly!")
