from typing import Union

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
        [
            InlineKeyboardButton(text=_["BACK_BUTTON"], callback_data="start_menu"),
        ],
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


def games_panel(_):
    buttons = [
        [
            InlineKeyboardButton(text=_["H_B_27"], callback_data="help_callback hb27"),
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
    # Page 1:
    # hb1 | hb2 | hb3
    # hb4 | hb5 | hb6
    # hb7 | hb8
    # hb12
    # Home | Next
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
    # Page 2:
    # hb13 | hb15 | hb16
    # hb17 | hb18 | hb19
    # hb20 | hb21
    # hb23
    # Back | Next
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
    # Page 3:
    # hb24 | hb25 | hb26
    # hb28 | hb29 | hb30
    # hb31 | hb32
    # hb33
    # Back
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
