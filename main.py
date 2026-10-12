import logging

from telegram import Update

from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from config import BOT_TOKEN
from database import initialize_database
from logger import setup_logging

from handlers.user import (
    start,
    help_command,
    about_command,
    stats_command,
    report_command,
    creator_command,
)

from handlers.subscription import verify_callback

from handlers.access import check_user_access

from handlers.files import upload_command, receive_file

from admin.dashboard import admin_command, admin_callback

from admin.file_manager import handle_file_search_text

from handlers.menu import handle_menu_button

logger = logging.getLogger(__name__)


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Unhandled exception",
        exc_info=context.error,
    )

# ============================================================
# GLOBAL ACCESS GUARD
# ============================================================

async def global_access_guard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Runs before all other handlers.

    If the user is banned, or a previously verified user
    has left a required channel, stop the update completely.

    If the user is allowed, processing continues normally.
    """

    allowed = await check_user_access(
        update,
        context,
    )

    if not allowed:
        raise ApplicationHandlerStop

# ============================================================
# MAIN
# ============================================================

def main():
    setup_logging()

    logger.info("Initializing database...")
    initialize_database()

    logger.info("Starting bot...")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ========================================================
    # GLOBAL ACCESS GUARD
    # ========================================================

    application.add_handler(
        TypeHandler(
            Update,
            global_access_guard,
        ),
        group=-1,
    )

    # ========================================================
    # USER COMMANDS
    # ========================================================

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("about", about_command)
    )

    application.add_handler(
        CommandHandler("stats", stats_command)
    )

    application.add_handler(
        CommandHandler("report", report_command)
    )

    application.add_handler(
        CommandHandler("upload", upload_command)
    )

    application.add_handler(
        CommandHandler("creator", creator_command)
    )

    application.add_handler(
        MessageHandler(filters.Document.ALL, receive_file)
    )

    application.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(Start|Help|About|Statistics|Report|Admin)$"
            ),
            handle_menu_button,
        )
    )

    application.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_file_search_text,
    )
    )

    # ========================================================
    # ADMIN DASHBOARD
    # ========================================================

    application.add_handler(
        CommandHandler(
            "admin",
            admin_command,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern=r"^admin:",
        )
    )

    # ========================================================
    # VERIFICATION BUTTON
    # ========================================================

    application.add_handler(
        CallbackQueryHandler(
            verify_callback,
            pattern="^verify_subscription$",
        )
    )

    # ========================================================
    # ERROR HANDLER
    # ========================================================

    application.add_error_handler(
        error_handler
    )

    logger.info("Bot is running.")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()