import html

from telegram import Update
from telegram.ext import ContextTypes

from auth import (
    is_authorized_admin,
    is_authorized_owner,
)

from database import (
    get_admin,
    get_all_admins,
    get_user,
    add_admin,
    remove_admin,
    log_admin_action,
)

from keyboards.admin import (
    admin_management_keyboard,
    admin_list_keyboard,
    admin_details_keyboard,
    admin_add_keyboard,
    admin_add_confirmation_keyboard,
    admin_remove_confirmation_keyboard,
)


# ============================================================
# HELPERS
# ============================================================

def _safe(value, default="Unknown"):
    if value is None or value == "":
        return default

    return str(value)


def _get_display_name(user_id):
    """
    Return a safe display name for an administrator.

    If the administrator has not registered with the bot yet,
    fall back to the Telegram user ID.
    """

    user_record = get_user(user_id)

    if user_record is None:
        return f"User ID {user_id}"

    first_name = user_record["first_name"]
    username = user_record["username"]

    if first_name:
        name = str(first_name)
    else:
        name = f"User ID {user_id}"

    if username:
        name += f" (@{username})"

    return name


def _format_admin_details(admin_record):
    """
    Format one administrator's database record.
    """

    user_id = admin_record["user_id"]
    role = admin_record["role"]
    added_at = admin_record["added_at"]
    added_by = admin_record["added_by"]

    user_record = get_user(user_id)

    if user_record is not None:
        first_name = _safe(
            user_record["first_name"]
        )

        username = user_record["username"]

        if username:
            username_text = (
                f"@{html.escape(str(username))}"
            )
        else:
            username_text = "No username"

    else:
        first_name = "Not registered"
        username_text = "No username"

    safe_first_name = html.escape(
        first_name
    )

    if role == "owner":
        role_text = "👑 Owner"
    else:
        role_text = "🛡️ Administrator"

    if added_by:
        added_by_name = _get_display_name(
            added_by
        )

        added_by_text = (
            f"{html.escape(added_by_name)} "
            f"(<code>{added_by}</code>)"
        )
    else:
        added_by_text = "Unknown"

    return (
        "👑 <b>Administrator Details</b>\n\n"
        f"<b>Name:</b> {safe_first_name}\n"
        f"<b>Username:</b> {username_text}\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n\n"
        f"<b>Role:</b> {role_text}\n"
        f"<b>Added At:</b> "
        f"<code>{html.escape(str(added_at))}</code>\n"
        f"<b>Added By:</b> {added_by_text}"
    )


# ============================================================
# MAIN ADMIN MANAGEMENT MENU
# ============================================================

async def show_admin_management(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Display the Admin Management menu.
    """

    query = update.callback_query

    if query is None:
        return

    user = query.from_user

    if not is_authorized_admin(user.id):
        await query.answer(
            "You are not authorized.",
            show_alert=True,
        )
        return

    context.user_data.pop(
        "awaiting_admin_add",
        None,
    )

    context.user_data.pop(
        "admin_pending_add_id",
        None,
    )

    await query.edit_message_text(
        "👑 <b>Admin Management</b>\n\n"
        "View administrators and manage admin access.\n\n"
        "Only the owner can add or remove "
        "administrators.",
        reply_markup=admin_management_keyboard(
            is_owner=is_authorized_owner(user.id)
        ),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN LIST
# ============================================================

async def show_admin_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Display all administrators.
    """

    query = update.callback_query

    if query is None:
        return

    user = query.from_user

    if not is_authorized_admin(user.id):
        await query.answer(
            "You are not authorized.",
            show_alert=True,
        )
        return

    admins = get_all_admins()

    await query.edit_message_text(
        "👑 <b>Administrators</b>\n\n"
        f"Total administrators: "
        f"<b>{len(admins)}</b>\n\n"
        "Select an administrator to view details.",
        reply_markup=admin_list_keyboard(
            admins,
            is_owner=is_authorized_owner(
                user.id
            ),
        ),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN DETAILS
# ============================================================

async def show_admin_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id,
):
    """
    Display details for one administrator.
    """

    query = update.callback_query

    if query is None:
        return

    try:
        user_id = int(user_id)

    except (TypeError, ValueError):
        await query.edit_message_text(
            "❌ Invalid administrator ID.",
            reply_markup=admin_list_keyboard(
                get_all_admins(),
                is_owner=is_authorized_owner(
                    query.from_user.id
                ),
            ),
            parse_mode="HTML",
        )
        return

    admin_record = get_admin(user_id)

    if admin_record is None:
        await query.edit_message_text(
            "❌ This administrator no longer exists.",
            reply_markup=admin_list_keyboard(
                get_all_admins(),
                is_owner=is_authorized_owner(
                    query.from_user.id
                ),
            ),
            parse_mode="HTML",
        )
        return

    can_remove = (
        is_authorized_owner(
            query.from_user.id
        )
        and admin_record["role"] == "admin"
        and user_id != query.from_user.id
    )

    await query.edit_message_text(
        _format_admin_details(
            admin_record
        ),
        reply_markup=admin_details_keyboard(
            user_id=user_id,
            can_remove=can_remove,
        ),
        parse_mode="HTML",
    )


# ============================================================
# START ADD ADMIN
# ============================================================

async def start_add_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Start the owner-only Add Administrator workflow.
    """

    query = update.callback_query

    if query is None:
        return

    user = query.from_user

    if not is_authorized_owner(user.id):
        await query.answer(
            "Only the owner can add administrators.",
            show_alert=True,
        )
        return

    context.user_data[
        "awaiting_admin_add"
    ] = True

    context.user_data.pop(
        "admin_pending_add_id",
        None,
    )

    await query.edit_message_text(
        "➕ <b>Add Administrator</b>\n\n"
        "Enter the Telegram User ID of the person "
        "you want to make an administrator.\n\n"
        "Example:\n"
        "<code>123456789</code>\n\n"
        "⚠️ Only the owner can perform this action.",
        reply_markup=admin_add_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# CANCEL ADD ADMIN
# ============================================================

async def cancel_add_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Cancel the Add Administrator workflow.
    """

    query = update.callback_query

    if query is None:
        return

    context.user_data.pop(
        "awaiting_admin_add",
        None,
    )

    context.user_data.pop(
        "admin_pending_add_id",
        None,
    )

    await query.edit_message_text(
        "👑 <b>Admin Management</b>\n\n"
        "View administrators and manage admin access.",
        reply_markup=admin_management_keyboard(
            is_owner=is_authorized_owner(
                query.from_user.id
            )
        ),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN ADD CONFIRMATION
# ============================================================

async def request_admin_add_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id,
):
    """
    Show confirmation before adding an administrator.
    """

    query = update.callback_query

    if query is None:
        return

    if not is_authorized_owner(
        query.from_user.id
    ):
        await query.answer(
            "Only the owner can add administrators.",
            show_alert=True,
        )
        return

    context.user_data[
        "admin_pending_add_id"
    ] = user_id

    display_name = _get_display_name(
        user_id
    )

    await query.edit_message_text(
        "⚠️ <b>Confirm Administrator Addition</b>\n\n"
        f"<b>User:</b> "
        f"{html.escape(display_name)}\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n\n"
        "Do you want to grant this user "
        "administrator access?",
        reply_markup=admin_add_confirmation_keyboard(
            user_id
        ),
        parse_mode="HTML",
    )


# ============================================================
# EXECUTE ADD ADMIN
# ============================================================

async def execute_admin_add(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id,
):
    """
    Add an administrator after confirmation.

    All security checks are repeated here.
    """

    query = update.callback_query

    if query is None:
        return

    owner_id = query.from_user.id

    if not is_authorized_owner(
        owner_id
    ):
        await query.answer(
            "Only the owner can add administrators.",
            show_alert=True,
        )
        return

    try:
        user_id = int(user_id)

    except (TypeError, ValueError):
        await query.edit_message_text(
            "❌ Invalid administrator ID.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    if user_id == owner_id:
        await query.edit_message_text(
            "❌ The owner is already the owner.\n\n"
            "The owner cannot be added as another administrator.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    if get_admin(user_id) is not None:
        await query.edit_message_text(
            "❌ This user is already an administrator.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    added = add_admin(
        user_id=user_id,
        added_by=owner_id,
    )

    if not added:
        await query.edit_message_text(
            "❌ The administrator could not be added.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    context.user_data.pop(
        "admin_pending_add_id",
        None,
    )

    log_admin_action(
        admin_id=owner_id,
        action="ADMIN_ADDED",
        target_type="admin",
        target_id=user_id,
        description=(
            f"Owner {owner_id} added "
            f"administrator {user_id}."
        ),
    )

    await query.edit_message_text(
        "✅ <b>Administrator Added</b>\n\n"
        f"User ID <code>{user_id}</code> "
        "is now an administrator.",
        reply_markup=admin_management_keyboard(
            is_owner=True
        ),
        parse_mode="HTML",
    )


# ============================================================
# REQUEST ADMIN REMOVAL
# ============================================================

async def request_admin_removal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id,
):
    """
    Ask the owner to confirm administrator removal.
    """

    query = update.callback_query

    if query is None:
        return

    owner_id = query.from_user.id

    if not is_authorized_owner(
        owner_id
    ):
        await query.answer(
            "Only the owner can remove administrators.",
            show_alert=True,
        )
        return

    try:
        user_id = int(user_id)

    except (TypeError, ValueError):
        await query.edit_message_text(
            "❌ Invalid administrator ID.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    if user_id == owner_id:
        await query.edit_message_text(
            "❌ The owner cannot be removed.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    admin_record = get_admin(user_id)

    if admin_record is None:
        await query.edit_message_text(
            "❌ This administrator no longer exists.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    if admin_record["role"] != "admin":
        await query.edit_message_text(
            "❌ The owner cannot be removed "
            "through Admin Management.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    display_name = _get_display_name(
        user_id
    )

    await query.edit_message_text(
        "⚠️ <b>Confirm Administrator Removal</b>\n\n"
        f"<b>User:</b> "
        f"{html.escape(display_name)}\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n\n"
        "Removing this administrator will immediately "
        "remove their admin-panel access.\n\n"
        "Do you want to continue?",
        reply_markup=admin_remove_confirmation_keyboard(
            user_id
        ),
        parse_mode="HTML",
    )


# ============================================================
# EXECUTE ADMIN REMOVAL
# ============================================================

async def execute_admin_removal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id,
):
    """
    Remove an administrator after confirmation.

    All security checks are repeated here.
    """

    query = update.callback_query

    if query is None:
        return

    owner_id = query.from_user.id

    if not is_authorized_owner(
        owner_id
    ):
        await query.answer(
            "Only the owner can remove administrators.",
            show_alert=True,
        )
        return

    try:
        user_id = int(user_id)

    except (TypeError, ValueError):
        await query.edit_message_text(
            "❌ Invalid administrator ID.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    if user_id == owner_id:
        await query.edit_message_text(
            "❌ The owner cannot be removed.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    admin_record = get_admin(user_id)

    if admin_record is None:
        await query.edit_message_text(
            "❌ This administrator no longer exists.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    if admin_record["role"] != "admin":
        await query.edit_message_text(
            "❌ Only regular administrators can "
            "be removed here.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    removed = remove_admin(
        user_id
    )

    if not removed:
        await query.edit_message_text(
            "❌ The administrator could not be removed.",
            reply_markup=admin_management_keyboard(
                is_owner=True
            ),
            parse_mode="HTML",
        )
        return

    log_admin_action(
        admin_id=owner_id,
        action="ADMIN_REMOVED",
        target_type="admin",
        target_id=user_id,
        description=(
            f"Owner {owner_id} removed "
            f"administrator {user_id}."
        ),
    )

    await query.edit_message_text(
        "✅ <b>Administrator Removed</b>\n\n"
        f"User ID <code>{user_id}</code> "
        "is no longer an administrator.",
        reply_markup=admin_management_keyboard(
            is_owner=True
        ),
        parse_mode="HTML",
    )


# ============================================================
# CANCEL ADMIN REMOVAL
# ============================================================

async def cancel_admin_removal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Cancel administrator removal.
    """

    query = update.callback_query

    if query is None:
        return

    await query.edit_message_text(
        "👑 <b>Admin Management</b>\n\n"
        "View administrators and manage admin access.",
        reply_markup=admin_management_keyboard(
            is_owner=is_authorized_owner(
                query.from_user.id
            )
        ),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN TEXT INPUT
# ============================================================

async def handle_admin_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Receive the owner's Telegram User ID when adding
    an administrator.

    Returns True when the message was handled.
    """

    user = update.effective_user
    message = update.message

    if user is None or message is None:
        return False

    if not context.user_data.get(
        "awaiting_admin_add"
    ):
        return False

    if not is_authorized_owner(
        user.id
    ):
        context.user_data.pop(
            "awaiting_admin_add",
            None,
        )

        await message.reply_text(
            "❌ Only the owner can add administrators."
        )

        return True

    raw_user_id = (
        message.text.strip()
        if message.text
        else ""
    )

    if not raw_user_id.isdigit():
        await message.reply_text(
            "❌ Invalid Telegram User ID.\n\n"
            "Please enter a numeric Telegram User ID.\n\n"
            "Example:\n"
            "<code>123456789</code>",
            reply_markup=admin_add_keyboard(),
            parse_mode="HTML",
        )

        return True

    target_user_id = int(
        raw_user_id
    )

    if target_user_id <= 0:
        await message.reply_text(
            "❌ Invalid Telegram User ID.\n\n"
            "Please enter a valid positive number.",
            reply_markup=admin_add_keyboard(),
        )

        return True

    if target_user_id == user.id:
        await message.reply_text(
            "❌ You are already the owner.\n\n"
            "You do not need to add yourself.",
            reply_markup=admin_add_keyboard(),
        )

        return True

    if get_admin(
        target_user_id
    ) is not None:
        await message.reply_text(
            "❌ This user is already an administrator.",
            reply_markup=admin_add_keyboard(),
        )

        return True

    context.user_data.pop(
        "awaiting_admin_add",
        None,
    )

    context.user_data[
        "admin_pending_add_id"
    ] = target_user_id

    display_name = _get_display_name(
        target_user_id
    )

    await message.reply_text(
        "⚠️ <b>Confirm Administrator Addition</b>\n\n"
        f"<b>User:</b> "
        f"{html.escape(display_name)}\n"
        f"<b>User ID:</b> "
        f"<code>{target_user_id}</code>\n\n"
        "Do you want to grant this user "
        "administrator access?",
        reply_markup=admin_add_confirmation_keyboard(
            target_user_id
        ),
        parse_mode="HTML",
    )

    return True


# ============================================================
# ADMIN MANAGEMENT CALLBACK ROUTER
# ============================================================

async def handle_admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Route Admin Management callbacks.

    Authorization is checked independently.

    Viewing:
        All authorized admins.

    Adding/removing:
        Owner only.
    """

    query = update.callback_query

    if query is None:
        return

    user = query.from_user

    if not is_authorized_admin(
        user.id
    ):
        await query.answer(
            "You are not authorized.",
            show_alert=True,
        )

        await query.edit_message_text(
            "You are not authorized to access "
            "Admin Management."
        )

        return

    await query.answer()

    data = query.data or ""

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------

    if data == "admin:admins":
        await show_admin_management(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADMIN LIST
    # --------------------------------------------------------

    if data == "admin:admins:list":
        await show_admin_list(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ADD ADMIN
    # --------------------------------------------------------

    if data == "admin:admins:add":
        await start_add_admin(
            update,
            context,
        )
        return

    if data == "admin:admins:add:cancel":
        await cancel_add_admin(
            update,
            context,
        )
        return

    if data.startswith(
        "admin:admins:add:confirm:"
    ):
        target_id = data.rsplit(
            ":",
            1,
        )[1]

        await execute_admin_add(
            update,
            context,
            target_id,
        )
        return

    # --------------------------------------------------------
    # ADMIN DETAILS
    # --------------------------------------------------------

    if data.startswith(
        "admin:admin:"
    ):
        parts = data.split(":")

        # admin:admin:<id>
        if len(parts) == 3:
            await show_admin_details(
                update,
                context,
                parts[2],
            )
            return

        # admin:admin:remove:<id>
        if (
            len(parts) == 4
            and parts[2] == "remove"
        ):
            await request_admin_removal(
                update,
                context,
                parts[3],
            )
            return

        # admin:admin:remove:confirm:<id>
        if (
            len(parts) == 5
            and parts[2] == "remove"
            and parts[3] == "confirm"
        ):
            await execute_admin_removal(
                update,
                context,
                parts[4],
            )
            return

        # admin:admin:remove:cancel:<id>
        if (
            len(parts) == 5
            and parts[2] == "remove"
            and parts[3] == "cancel"
        ):
            await cancel_admin_removal(
                update,
                context,
            )
            return

    await query.edit_message_text(
        "This admin-management action is invalid.",
        reply_markup=admin_management_keyboard(
            is_owner=is_authorized_owner(
                user.id
            )
        ),
        parse_mode="HTML",
    )