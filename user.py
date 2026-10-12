import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from keyboards.user import user_main_keyboard

from auth import is_authorized_admin

from telegram.ext import ContextTypes

from database import (
    get_user_stats,
    register_user,
)

from config import REPORT_CONTACT

logger = logging.getLogger(__name__)

from handlers.files import deliver_file

# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    if user is None or update.message is None:
        return

    # The global access guard in main.py has already:
    # - registered/updated the user
    # - checked ban status
    # - checked subscription status
    # - stopped unauthorized users
    #
    # Therefore, do NOT run check_user_access() again here.

    # ========================================================
    # DEEP-LINK FILE REQUEST
    # ========================================================

    if context.args:
        file_key = context.args[0]

        if file_key.startswith("file_"):
            await deliver_file(
                update,
                context,
                file_key,
            )
            return

    # ========================================================
    # USER IS VERIFIED
    # ========================================================

    await update.message.reply_text(
        "╔═════════════════════════╗\n"
        "               ᯓ 𝐑𝐎𝐗𝐘 𝐄𝐃𝐈𝐓𝐙 𝐁𝐎𝐓 𓃵\n"
        "╚═════════════════════════╝\n\n"
        f"👋 Welcome, {user.first_name}!\n\n"
        "✨ 𝗛𝗼𝘄 𝘁𝗼 𝗴𝗲𝘁 𝘆𝗼𝘂𝗿 𝗦𝗲𝗰𝗿𝗲𝘁 𝗙𝗶𝗹𝗲𝘀\n\n"
        "① Browse available files from the channels\n\n"
        "② Open your file link\n\n"
        "③ Get your file instantly\n\n"
        "⚠️ 𝗪𝗔𝗥𝗡𝗜𝗡𝗚\n\n"
        "Leaving even one required channel will result in an immediate ban from the bot.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📌 Use the buttons below to get started\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=user_main_keyboard(
            is_admin=is_authorized_admin(
                user.id
            )
        ),
    )


# ============================================================
# HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "╔═════════════════════════╗\n"
        "                             📖 𝗛𝗘𝗟𝗣\n"
        "╚═════════════════════════╝\n\n"
        "📌 𝗔𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀\n\n"
        "① /start — Open the bot\n\n"
        "② /help — Show this help\n\n"
        "③ /about — About the bot\n\n"
        "④ /stats — View bot stats\n\n"
        "⑤ /report — Report an issue\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ Use the buttons below for quick access\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=user_main_keyboard(
            is_admin=is_authorized_admin(
                update.effective_user.id
            )
        ),
    )


# ============================================================
# ABOUT
# ============================================================

async def about_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "╔═════════════════════════╗\n"
        "                           ℹ️ 𝗔𝗕𝗢𝗨𝗧\n"
        "╚═════════════════════════╝\n\n"
        "🚫 𝗡𝗼 𝗜𝗿𝗿𝗶𝘁𝗮𝘁𝗶𝗻𝗴 𝗔𝗱𝘀\n\n"
        "Enjoy a clean experience without unnecessary advertisements.\n\n"
        "📁 𝗙𝗶𝗹𝗲𝘀 𝗪𝗵𝗲𝗻 𝗬𝗼𝘂 𝗡𝗲𝗲𝗱 𝗧𝗵𝗲𝗺\n\n"
        "Access available files through simple, direct links without the hassle.\n\n"
        "⚡ 𝗙𝗮𝘀𝘁 & 𝗖𝗼𝗻𝘃𝗲𝗻𝗶𝗲𝗻𝘁\n\n"
        "Less waiting. Less searching. Fewer steps. Just a smooth way to get what you need.\n\n"
        "🛡️ 𝗦𝗲𝗰𝘂𝗿𝗲 𝗗𝗲𝗹𝗶𝘃𝗲𝗿𝘆\n\n"
        "Your files are delivered through Telegram with a simple and reliable experience.\n\n"
        "🎯 𝗕𝘂𝗶𝗹𝘁 𝗙𝗼𝗿 𝗦𝗶𝗺𝗽𝗹𝗶𝗰𝗶𝘁𝘆\n\n"
        "Everything is designed to keep your journey quick, clear and frustration-free.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  ❤️ 𝗬𝗼𝘂 𝗳𝗶𝗻𝗱 𝗶𝘁 > 𝗬𝗼𝘂 𝗼𝗽𝗲𝗻 𝗶𝘁 > 𝗬𝗼𝘂 𝗴𝗲𝘁 𝗶𝘁\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=user_main_keyboard(
            is_admin=is_authorized_admin(
                update.effective_user.id
            )
        ),
    )


# ============================================================
# STATS
# ============================================================

async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    stats = get_user_stats()

    await update.message.reply_text(
        "╔═════════════════════════╗\n"
        "                            📊 𝗦𝗧𝗔𝗧𝗦\n"
        "╚═════════════════════════╝\n\n"
        "📈 𝗕𝗼𝘁 𝗦𝘁𝗮𝘁𝗶𝘀𝘁𝗶𝗰𝘀\n\n"
        f"👥 Users: {stats['total_users']}\n\n"
        f"📥 Downloads: {stats['total_downloads']}\n\n"
        f"🛡️ Verified: {stats['verified_users']}\n\n"
        
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "      ✨ Growing with every file delivered\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=user_main_keyboard(
            is_admin=is_authorized_admin(
                update.effective_user.id
            )
        ),
    )


# ============================================================
# REPORT
# ============================================================

async def report_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔵 Contact Support",
                url=REPORT_CONTACT,
            )
        ]
    ])

    await update.message.reply_text(
        "╔═════════════════════════╗\n"
        "                           🚨 𝗥𝗘𝗣𝗢𝗥𝗧\n"
        "╚═════════════════════════╝\n\n"
        "⚠️ 𝗙𝗼𝘂𝗻𝗱 𝗮 𝗽𝗿𝗼𝗯𝗹𝗲𝗺?\n\n"
        "• File not working?\n\n"
        "• Something not right?\n\n"
        "• Need to report an issue?\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "       💬 Your feedback helps us improve\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=keyboard,
    )


# ============================================================
# Who made this Bot
# ============================================================

async def creator_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "╔═════════════════════════╗\n"
        "                        👑 𝗖𝗥𝗘𝗔𝗧𝗢𝗥\n"
        "╚═════════════════════════╝\n\n"
        "ᯓ 𝐑𝐎𝐗𝐘 𝐄𝐃𝐈𝐓𝐙 𝐁𝐎𝐓 𓃵 was created by\n"
        "👤 @Ariyansfx\n\n"
        "❤️ Hope you're enjoying the experience!\n"
        "Thank you for using the bot.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "                ✨ Built with care for you\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )