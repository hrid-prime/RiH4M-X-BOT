from telegram import Update
from telegram.ext import ContextTypes

from auth import is_authorized_admin

from handlers.user import (
    start,
    help_command,
    about_command,
    stats_command,
    report_command,
)

from admin.dashboard import admin_command


# ============================================================
# REPLY KEYBOARD BUTTON HANDLER
# ============================================================

async def handle_menu_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Handle buttons from the persistent user/admin
    reply keyboard.

    The buttons behave like convenient shortcuts to
    the existing commands.
    """

    if update.message is None:
        return

    user = update.effective_user

    if user is None:
        return

    text = (
        update.message.text
        or ""
    ).strip()

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    if text == "Start":
        await start(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # HELP
    # --------------------------------------------------------

    if text == "Help":
        await help_command(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ABOUT
    # --------------------------------------------------------

    if text == "About":
        await about_command(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    if text == "Statistics":
        await stats_command(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    if text == "Report":
        await report_command(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if text == "Admin":

        if not is_authorized_admin(
            user.id
        ):
            await update.message.reply_text(
                "❌ You are not authorized "
                "to access the admin panel."
            )
            return

        await admin_command(
            update,
            context,
        )
        return