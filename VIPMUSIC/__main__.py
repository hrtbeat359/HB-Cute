import asyncio
import importlib
from pyrogram import idle

import config
from VIPMUSIC import LOGGER, app, userbot, telethn
from VIPMUSIC.core.call import VIP
from VIPMUSIC.misc import sudo
from VIPMUSIC.plugins import ALL_MODULES
from VIPMUSIC.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init_bot():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error(
            "𝐒𝐭𝐫𝐢𝐧𝐠 𝐒𝐞𝐬𝐬𝐢𝐨𝐧 𝐍𝐨𝐭 𝐅𝐢𝐥𝐥𝐞𝐝, 𝐏𝐥𝐞𝐚𝐬𝐞 𝐅𝐢𝐥𝐥 𝐀 𝐏𝐲𝐫𝐨𝐠𝐫𝐚𝐦 V2 𝐒𝐞𝐬𝐬𝐢𝐨𝐧🤬"
        )

    await sudo()

    try:
        gb = await get_gbanned()
        for u in gb:
            BANNED_USERS.add(u)

        ban = await get_banned_users()
        for u in ban:
            BANNED_USERS.add(u)

    except:
        pass

    await app.start()

    # Load all modules safely
    for all_module in ALL_MODULES:
        importlib.import_module("VIPMUSIC.plugins" + all_module)

    LOGGER("VIPMUSIC.plugins").info("𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝🥳...")

    await userbot.start()
    await VIP.start()
    await VIP.decorators()

    LOGGER("VIPMUSIC").info(
        "\n╔═════ஜ۩۞۩ஜ════╗\n  ♨️𝗠𝗔𝗗𝗘 𝗕𝗬 𝗩𝗜𝗣 𝗕𝗢𝗬♨️\n╚═════ஜ۩۞۩ஜ════╝"
    )


async def main():
    # ----------------------------------------------------
    # CRASH FIX 1: Start Telethon FIRST and ONLY ONCE
    # ----------------------------------------------------
    await telethn.start(bot_token=config.BOT_TOKEN)

    # ----------------------------------------------------
    # CRASH FIX 2: Then init the rest
    # ----------------------------------------------------
    await init_bot()

    # ----------------------------------------------------
    # CRASH FIX 3: Idle keeps loop active
    # ----------------------------------------------------
    await idle()

    # ----------------------------------------------------
    # CRASH FIX 4: Clean shutdown order
    # ----------------------------------------------------
    await telethn.disconnect()
    await userbot.stop()
    await app.stop()

    LOGGER("VIPMUSIC").info(
        "╔═════ஜ۩۞۩ஜ════╗\n  ♨️𝗠𝗔𝗗𝗘 𝗕𝗬 𝗩𝗜𝗣 𝗕𝗢𝗬♨️\n╚═════ஜ۩۞۩ஜ════╝"
    )


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
