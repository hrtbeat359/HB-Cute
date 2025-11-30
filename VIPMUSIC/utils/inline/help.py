from typing import Union

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from VIPMUSIC import app

# Main category page (first page shown for help)
def first_page(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["H_B_22"], callback_data="help_cat music"),
            InlineKeyboardButton(text=_["H_B_27"], callback_data="help_cat games"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_3"], callback_data="help_cat management"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_9"], callback_data="help_cat chat"),
            InlineKeyboardButton(text=_["H_B_10"], callback_data="help_cat reaction"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_11"], callback_data="help_cat mention"),
        ],
        #[
         #   InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settings_back_helper"),
        #],
    ]
    return InlineKeyboardMarkup(buttons)


# Private panel (used when /help is used in private or for returning to start)
def private_help_panel(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["S_B_12"], callback_data="settings_back_helper"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


# Single-category panels -----------------------------------------------------

def music_panel(_):
    # Music contains hb14 and hb22
    buttons = [
        [
            InlineKeyboardButton(text=_["H_B_14"], callback_data="help_callback hb14"),
            InlineKeyboardButton(text=_["H_B_22"], callback_data="help_callback hb22"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settings_back_helper"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def games_panel1():
    buttons = [
        [
            InlineKeyboardButton(text="Pixel Dungeon", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJQaXhlbER1bmdlb24ifX0")),
            InlineKeyboardButton(text="Karate Kido", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJLYXJhdGVLaWRvIn19")),
            InlineKeyboardButton(text="Mars Rover", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJNYXJzUm92ZXIifX0")),
        ],
        [
            InlineKeyboardButton(text="Gravity Ninja: Emerald City", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJHcmF2aXR5TmluamFFbWVyYWxkQ2l0eSJ9fQ")),
            InlineKeyboardButton(text="ATARI Asteroids", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJBdGFyaUFzdGVyb2lkcyJ9fQ")),
            InlineKeyboardButton(text="Gravity Ninja", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJHcmF2aXR5TmluamEifX0")),
        ],
        [
            InlineKeyboardButton(text="Gravity Unicorns", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJHcmF2aXR5VW5pY29ybnMifX0")),
            InlineKeyboardButton(text="Beach Racer", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJCZWFjaFJhY2VyIn19")),
        ],
        [
            InlineKeyboardButton(text="Qube 2048", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJRdWJlMjA0OCJ9fQ")),
            InlineKeyboardButton(text="Moonshot", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJNb29uc2hvdCJ9fQ")),
        ],
        [
            InlineKeyboardButton(text=_["H_B_27"], callback_data="help_callback hb27"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settings_back_helper"),
            InlineKeyboardButton(text=_["NEXT_BUTTON"], callback_data="games_p2"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def games_panel2(_):
    buttons = [
        [
            InlineKeyboardButton(text="Run", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJSdW4ifX0")),
            InlineKeyboardButton(text="Brick Stacker", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJCcmlja1N0YWNrZXIifX0")),
            InlineKeyboardButton(text="Into the Mocaverse", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJJbnRvVGhlTW9jYXZlcnNlIn19")),
        ],
        [
            InlineKeyboardButton(text="Neon Blaster 2", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJOZW9uQmxhc3QyIn19")),
            InlineKeyboardButton(text="Bratz Pop", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJCcmF0elBvcCJ9fQ")),
            InlineKeyboardButton(text="Hooked 2048", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJIb29rZWQyMDQ4In19")),
        ],
        [
            InlineKeyboardButton(text="Ride or Die", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJSaWRlT3JEaWUifX0")),
            InlineKeyboardButton(text="Basket Boy Rush", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJCYXNrZXRCb3lSdXNoIn19")),
        ],
        [
            InlineKeyboardButton(text="JumpTuber", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJKdW1wdHViZXIxIn19")),
            InlineKeyboardButton(text="Spiky Fish 3", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJTcGlreUZpc2gzIn19")),
        ],
        [
            InlineKeyboardButton(text="Atomic Drop", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJBdG9taWNEcm9wMSJ9fQ")),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="games_p1"),
            InlineKeyboardButton(text=_["NEXT_BUTTON"], callback_data="games_p3"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)



def games_panel3(_):
    buttons = [
        [
            InlineKeyboardButton(text="Penalty Shooter", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJQZW5hbHR5U2hvb3RlcjIifX0")),
            InlineKeyboardButton(text="Sunshine Solitaire", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJTdW5zaGluZVNvbGl0YWlyZSJ9fQ")),
            InlineKeyboardButton(text="Red and Blue", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJSZWRBbmRCbHVlIn19")),
        ],
        [
            InlineKeyboardButton(text="Disco Ball", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJSb2xsZXJEaXNjbyJ9fQ")),
            InlineKeyboardButton(text="1+2=3", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJvbmV0d290aHJlZSJ9fQ")),
            InlineKeyboardButton(text="Groovy Ski", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJHcm9vdnlTa2kifX0")),
        ],
        [
            InlineKeyboardButton(text="Marble Dash", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJNYXJibGVEYXNoIn19")),
            InlineKeyboardButton(text="Switch", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJTd2l0Y2gxIn19")),
        ],
        [
            InlineKeyboardButton(text="Color Hit", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJDb2xvb3JIaXQifX0")),
            InlineKeyboardButton(text="Tents and Trees", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJUZW50c0FuZFRyZWVzIn19")),
        ],
        [
            InlineKeyboardButton(text="Neon Racer", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJOZW9uUmFjZXIifX0")),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="games_p2"),
            InlineKeyboardButton(text=_["NEXT_BUTTON"], callback_data="games_p4"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def games_panel4(_):
    buttons = [
        [
            InlineKeyboardButton(text="Samurai Hold'em", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJTYW11cmFpSG9sZGVtIn19")),
            InlineKeyboardButton(text="Man City Striker", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJNYW5DaXR5U3RyaWtlcjNEIn19")),
            InlineKeyboardButton(text="SmartUp Shark", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJTbWFydFVwU2hhcmsifX0")),
        ],
        [
            InlineKeyboardButton(text="F1 Racer", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJGMVJhY2VyIn19")),
            InlineKeyboardButton(text="SUPERBUGZ", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJTdXBlcmJ1Z3oifX0")),
            InlineKeyboardButton(text="Keep it UP", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJLZWVwSXRVcCJ9fQ")),
        ],
        [
            InlineKeyboardButton(text="Kingdoms of 2048", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJLaW5nZG9tc09mMjA0OCJ9fQ")),
            InlineKeyboardButton(text="Globo Run", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJHbG9ib1J1biJ9fQ")),
        ],
        [
            InlineKeyboardButton(text="ASTRO CAT", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJBc3Ryb2NhdCJ9fQ")),
            InlineKeyboardButton(text="Space Orbit", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJTcGFjZU9yYml0In19")),
        ],
        [
            InlineKeyboardButton(text="MotoFX", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJNb3RvRngifX0")),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="games_p3"),
            InlineKeyboardButton(text=_["NEXT_BUTTON"], callback_data="games_p5"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)



def games_panel5(_):
    buttons = [
        [
            InlineKeyboardButton(text="Neon Blaster", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJOZW9uQmxhc3RlciJ9fQ")),
            InlineKeyboardButton(text="Tamachi Jump", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJUYW1hY2hpSnVtcCJ9fQ")),
            InlineKeyboardButton(text="Wizard's 21", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJXaXphcmRzMjEifX0")),
        ],
        [
            InlineKeyboardButton(text="99 Blocks", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJTdWRva3VQdXp6bGUifX0")),
            InlineKeyboardButton(text="Block Breaker", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJCbG9ja0JyZWFrZXIifX0")),
        ],
        [
            InlineKeyboardButton(text="Hoop Shot", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJIb29wU2hvdCJ9fQ")),
            InlineKeyboardButton(text="Gravity Ninja 2", web_app=WebAppInfo(url="https://t.me/gamee/game?startapp=eyJnYW1lIjp7InNsdWciOiJHcmF2aXR5TmluamEyMSJ9fQ")),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settings_back_helper"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def chat_panel(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["H_B_9"], callback_data="help_callback hb9"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settings_back_helper"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def reaction_panel(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["H_B_10"], callback_data="help_callback hb10"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settings_back_helper"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def mention_panel(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["H_B_11"], callback_data="help_callback hb11"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settings_back_helper"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


# Management multi-page panels -----------------------------------------------

def management_page1(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["H_B_1"], callback_data="help_callback hb1"),
            InlineKeyboardButton(text=_["H_B_2"], callback_data="help_callback hb2"),
            InlineKeyboardButton(text=_["H_B_3"], callback_data="help_callback hb3"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_4"], callback_data="help_callback hb4"),
            InlineKeyboardButton(text=_["H_B_5"], callback_data="help_callback hb5"),
            InlineKeyboardButton(text=_["H_B_6"], callback_data="help_callback hb6"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_7"], callback_data="help_callback hb7"),
            InlineKeyboardButton(text=_["H_B_8"], callback_data="help_callback hb8"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_12"], callback_data="help_callback hb12"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="settings_back_helper"),
            InlineKeyboardButton(text=_["NEXT_BUTTON"], callback_data="management_p2"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def management_page2(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["H_B_13"], callback_data="help_callback hb13"),
            InlineKeyboardButton(text=_["H_B_15"], callback_data="help_callback hb15"),
            InlineKeyboardButton(text=_["H_B_16"], callback_data="help_callback hb16"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_17"], callback_data="help_callback hb17"),
            InlineKeyboardButton(text=_["H_B_18"], callback_data="help_callback hb18"),
            InlineKeyboardButton(text=_["H_B_19"], callback_data="help_callback hb19"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_20"], callback_data="help_callback hb20"),
            InlineKeyboardButton(text=_["H_B_21"], callback_data="help_callback hb21"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_23"], callback_data="help_callback hb23"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="management_p1"),
            InlineKeyboardButton(text=_["NEXT_BUTTON"], callback_data="management_p3"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def management_page3(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["H_B_24"], callback_data="help_callback hb24"),
            InlineKeyboardButton(text=_["H_B_25"], callback_data="help_callback hb25"),
            InlineKeyboardButton(text=_["H_B_26"], callback_data="help_callback hb26"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_28"], callback_data="help_callback hb28"),
            InlineKeyboardButton(text=_["H_B_29"], callback_data="help_callback hb29"),
            InlineKeyboardButton(text=_["H_B_30"], callback_data="help_callback hb30"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_31"], callback_data="help_callback hb31"),
            InlineKeyboardButton(text=_["H_B_32"], callback_data="help_callback hb32"),
        ],
        [
            InlineKeyboardButton(text=_["H_B_33"], callback_data="help_callback hb33"),
        ],
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="management_p2"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


# generic back/close markup used by individual help pages
def help_back_markup(_):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data=f"settings_back_helper"),
                InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data=f"close"),
            ]
        ]
    )
    return upl
