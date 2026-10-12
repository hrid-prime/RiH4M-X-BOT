from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ============================================================
# USER / ADMIN REPLY KEYBOARD
# ============================================================

def user_main_keyboard(
    is_admin=False,
) -> ReplyKeyboardMarkup:
    """
    Persistent Telegram reply keyboard.

    Normal users:
        Start
        Help | About
        Statistics | Report

    Administrators:
        Start | Help
        About | Statistics
        Report | Admin
    """

    if is_admin:
        keyboard = [
            [
                KeyboardButton("Start"),
                KeyboardButton("Help"),
            ],
            [
                KeyboardButton("About"),
                KeyboardButton("Statistics"),
            ],
            [
                KeyboardButton("Report"),
                KeyboardButton("Admin"),
            ],
        ]

    else:
        keyboard = [
            [
                KeyboardButton("Start"),
            ],
            [
                KeyboardButton("Help"),
                KeyboardButton("About"),
            ],
            [
                KeyboardButton("Statistics"),
                KeyboardButton("Report"),
            ],
        ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )