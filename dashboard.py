from telegram import Update
from telegram.ext import ContextTypes

from admin.file_manager import handle_file_callback
from admin.user_manager import handle_user_callback
from admin.admin_manager import handle_admin_callback

from auth import is_authorized_admin
from keyboards.admin import (
    admin_main_keyboard,
)


async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Open the administrator dashboard.

    Only authorized administrators can access this command.
    """

    user = update.effective_user

    if user is None:
        return

    if not is_authorized_admin(user.id):
        if update.effective_message:
            await update.effective_message.reply_text(
                "You are not authorized to access the admin panel."
            )
        return

    await update.effective_message.reply_text(
        "🛠 Admin Panel\n\nChoose an option:",
        reply_markup=admin_main_keyboard(),
    )


async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Handle all admin-dashboard callbacks.

    Authorization is checked again here rather than relying
    on the /admin command. This is important because callback
    data must never be treated as a security boundary.
    """

    query = update.callback_query

    if query is None:
        return

    await query.answer()

    user = query.from_user

    if not is_authorized_admin(user.id):
        await query.edit_message_text(
            "You are not authorized to access the admin panel."
        )
        return

    callback_data = query.data or ""

    if (
        callback_data == "admin:files"
        or callback_data.startswith("admin:files:")
        or callback_data.startswith("admin:file:")
        or callback_data.startswith("admin:upload:")
        or callback_data.startswith("admin:bulk:")
    ):
        await handle_file_callback(update, context)
        return

    if (
        callback_data == "admin:users"
        or callback_data.startswith("admin:users:")
        or callback_data.startswith("admin:user:")
        ):
        await handle_user_callback(update, context)
        return

    if (
        callback_data == "admin:admins"
        or callback_data.startswith("admin:admins:")
        or callback_data.startswith("admin:admin:")
    ):
        await handle_admin_callback(
            update,
            context,
        )
        return

    if callback_data == "admin:back":
        await query.edit_message_text(
            "🛠 Admin Panel\n\nChoose an option:",
            reply_markup=admin_main_keyboard(),
        )
        return