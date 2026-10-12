import os
from dotenv import load_dotenv

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing from .env")

if not OWNER_ID:
    raise RuntimeError("OWNER_ID is missing from .env")

try:
    OWNER_ID = int(OWNER_ID)
except ValueError:
    raise RuntimeError("OWNER_ID must be a number")


# ============================================================
# REQUIRED CHANNELS
# ============================================================
#
# Replace the placeholder URLs with the actual Telegram
# channel links.
#
# "id" = Telegram channel ID
# "name" = button name
# "url" = link users press to join
#
# ============================================================

CHANNELS = [
    {
        "id": -1004378753583,
        "name": "Channel 1",
        "url": "https://t.me/+NyN1WDtNIWljOGRl",
    },
    {
        "id": -1003804079861,
        "name": "Channel 2",
        "url": "https://t.me/+_2v_D6fkBnM4OWY1",
    },
    {
        "id": -1004360656335,
        "name": "Channel 3",
        "url": "https://t.me/+onXOkbGXk31jYzA1",
    },
    {
        "id": -1003947690532,
        "name": "Channel 4",
        "url": "https://t.me/rifoxmods",
    },
    {
        "id": -1004311283104,
        "name": "Channel 5",
        "url": "https://t.me/+JpEYZY-hDEM5ZDhl",
    },
    {
        "id": -1003972611912,
        "name": "Channel 6",
        "url": "https://t.me/+-Oj1UuFHaXk4YzY1",
    },
]

# ============================================================
# REPORT CONTACT
# ============================================================

REPORT_CONTACT = "https://t.me/rox4xs"