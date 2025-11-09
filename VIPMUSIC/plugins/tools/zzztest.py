from VIPMUSIC import app
from pyrogram import filters

print("[ReactionBot] Plugin loaded!")

@app.on_message(filters.command("zzztest") & filters.group)
async def zzztest_cmd(_, message):
    print("[ReactionBot] /zzztest command triggered!")
    await message.reply_text("✅ ZZZ Test command works!")
