import html

from telegram import Update
from telegram.ext import ContextTypes

from auth import is_authorized_admin
from database import (
    get_all_users,
    search_users,
    get_user,
    block_user,
    unblock_user,
    get_block_info,
    is_admin,
    log_admin_action,
)

from keyboards.admin import (
    user_management_keyboard,
    user_status_keyboard,
    user_search_keyboard,
    user_list_keyboard,
    user_details_keyboard,
    user_action_confirmation_keyboard,
    user_bulk_confirmation_keyboard,
)


PAGE_SIZE = 10


# ============================================================
# HELPERS
# ============================================================

def _safe(value, default="Unknown"):
    if value is None or value == "":
        return default

    return str(value)


def _format_user_details(user_record):
    """
    Format one user's database record for the admin.
    """

    user_id = user_record["user_id"]
    username = user_record["username"]
    first_name = user_record["first_name"]
    joined_at = user_record["joined_at"]
    is_verified = bool(user_record["is_verified"])
    download_count = user_record["download_count"]
    is_blocked = bool(user_record["is_blocked"])
    blocked_reason = user_record["blocked_reason"]
    blocked_at = user_record["blocked_at"]

    safe_first_name = html.escape(
        _safe(first_name)
    )

    if username:
        safe_username = html.escape(
            str(username)
        )
        username_text = f"@{safe_username}"
    else:
        username_text = "No username"

    verification_status = (
        "🟢 Verified"
        if is_verified
        else "🟡 Not verified"
    )

    block_status = (
        "🔴 Blocked"
        if is_blocked
        else "🟢 Active"
    )

    text = (
        "👤 <b>User Details</b>\n\n"
        f"<b>Name:</b> {safe_first_name}\n"
        f"<b>Username:</b> {username_text}\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n\n"
        f"<b>Status:</b> {block_status}\n"
        f"<b>Verification:</b> {verification_status}\n"
        f"<b>Downloads:</b> {download_count}\n"
        f"<b>Joined:</b> {html.escape(str(joined_at))}\n"
    )

    if is_blocked:
        text += (
            "\n"
            f"<b>Block reason:</b> "
            f"{html.escape(_safe(blocked_reason))}\n"
            f"<b>Blocked at:</b> "
            f"{html.escape(_safe(blocked_at))}\n"
        )

    return text


# ============================================================
# MAIN USER MANAGEMENT MENU
# ============================================================

async def show_user_management(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Display the main User Management menu."""

    query = update.callback_query

    if query is None:
        return

    context.user_data.pop(
        "awaiting_user_search",
        None,
    )

    context.user_data.pop(
        "admin_user_search_query",
        None,
    )

    context.user_data.pop(
        "admin_user_search_results",
        None,
    )

    context.user_data.pop(
        "admin_user_page",
        None,
    )

    await query.edit_message_text(
        "👥 <b>User Management</b>\n\n"
        "Manage registered users, inspect user details, "
        "or search for a specific user.",
        reply_markup=user_management_keyboard(),
        parse_mode="HTML",
    )

async def show_user_status_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Display the Active / Blocked user filter menu.
    """

    query = update.callback_query

    if query is None:
        return

    context.user_data.pop(
        "admin_user_selection_mode",
        None,
    )

    context.user_data.pop(
        "admin_user_selected_ids",
        None,
    )

    context.user_data.pop(
        "admin_user_filter",
        None,
    )

    await query.edit_message_text(
        "👥 <b>All Users</b>\n\n"
        "Choose which users you want to view:",
        reply_markup=user_status_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# USER LIST
# ============================================================

async def show_user_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page=0,
    filter_name="active",
):
    """
    Display users filtered by Active or Blocked status.
    """

    query = update.callback_query

    if query is None:
        return

    all_users = get_all_users()

    if filter_name == "blocked":
        users = [
            user
            for user in all_users
            if bool(user["is_blocked"])
        ]

        title = "🔴 Blocked Users"

    else:
        users = [
            user
            for user in all_users
            if not bool(user["is_blocked"])
        ]

        filter_name = "active"
        title = "🟢 Active Users"

    context.user_data[
        "admin_user_filter"
    ] = filter_name

    context.user_data[
        "admin_user_selection_mode"
    ] = False

    context.user_data.pop(
        "admin_user_selected_ids",
        None,
    )

    context.user_data.pop(
        "admin_user_search_query",
        None,
    )

    context.user_data.pop(
        "admin_user_search_results",
        None,
    )

    if not users:
        await query.edit_message_text(
            f"{title}\n\n"
            "No users were found in this category.",
            reply_markup=user_status_keyboard(),
            parse_mode="HTML",
        )
        return

    total_users = len(users)

    total_pages = (
        total_users + PAGE_SIZE - 1
    ) // PAGE_SIZE

    page = max(
        0,
        min(
            page,
            total_pages - 1,
        ),
    )

    context.user_data[
        "admin_user_page"
    ] = page

    await query.edit_message_text(
        f"{title}\n\n"
        f"Total users: <b>{total_users}</b>\n"
        f"Page <b>{page + 1}</b> of "
        f"<b>{total_pages}</b>\n\n"
        "Choose a user to view their details.",
        reply_markup=user_list_keyboard(
            users,
            page=page,
            page_size=PAGE_SIZE,
            total_users=total_users,
            search_mode=False,
            filter_name=filter_name,
            selected_ids=set(),
            selection_mode=False,
        ),
        parse_mode="HTML",
    )

# ============================================================
# USER SELECTION MODE
# ============================================================

def _clear_user_selection(
    context: ContextTypes.DEFAULT_TYPE,
):
    """Clear user selection state."""

    context.user_data.pop(
        "admin_user_selected_ids",
        None,
    )


def _get_filtered_users(
    context: ContextTypes.DEFAULT_TYPE,
):
    """Return users for the currently selected status filter."""

    filter_name = context.user_data.get(
        "admin_user_filter",
        "active",
    )

    all_users = get_all_users()

    if filter_name == "blocked":
        return [
            user
            for user in all_users
            if bool(user["is_blocked"])
        ]

    return [
        user
        for user in all_users
        if not bool(user["is_blocked"])
    ]


async def enter_user_selection_mode(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Enter bulk-selection mode."""

    query = update.callback_query

    if query is None:
        return

    filter_name = context.user_data.get(
        "admin_user_filter",
        "active",
    )

    context.user_data[
        "admin_user_selection_mode"
    ] = True

    _clear_user_selection(context)

    context.user_data[
        "admin_user_selected_ids"
    ] = set()

    await render_user_list(
        update,
        context,
        page=context.user_data.get(
            "admin_user_page",
            0,
        ),
        filter_name=filter_name,
        selection_mode=True,
    )


async def exit_user_selection_mode(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Return from selection mode to details mode."""

    context.user_data[
        "admin_user_selection_mode"
    ] = False

    _clear_user_selection(context)

    filter_name = context.user_data.get(
        "admin_user_filter",
        "active",
    )

    await render_user_list(
        update,
        context,
        page=context.user_data.get(
            "admin_user_page",
            0,
        ),
        filter_name=filter_name,
        selection_mode=False,
    )


async def toggle_user_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id,
):
    """Select or deselect one user."""

    query = update.callback_query

    if query is None:
        return

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        await query.answer(
            "Invalid user ID.",
            show_alert=True,
        )
        return

    user_record = get_user(user_id)

    if user_record is None:
        await query.answer(
            "User no longer exists.",
            show_alert=True,
        )
        return

    # Never allow administrators to be selected.
    if is_admin(user_id):
        await query.answer(
            "Administrators cannot be selected here.",
            show_alert=True,
        )
        return

    selected_ids = context.user_data.get(
        "admin_user_selected_ids",
        set(),
    )

    if not isinstance(selected_ids, set):
        selected_ids = set(
            selected_ids
        )

    if user_id in selected_ids:
        selected_ids.remove(user_id)

        await query.answer(
            "User deselected."
        )
    else:
        selected_ids.add(user_id)

        await query.answer(
            "User selected."
        )

    context.user_data[
        "admin_user_selected_ids"
    ] = selected_ids

    filter_name = context.user_data.get(
        "admin_user_filter",
        "active",
    )

    await render_user_list(
        update,
        context,
        page=context.user_data.get(
            "admin_user_page",
            0,
        ),
        filter_name=filter_name,
        selection_mode=True,
    )


async def select_all_users(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Select every manageable user in the current filter."""

    query = update.callback_query

    if query is None:
        return

    users = _get_filtered_users(
        context
    )

    selected_ids = set()

    for user in users:
        user_id = user["user_id"]

        if not is_admin(user_id):
            selected_ids.add(
                user_id
            )

    context.user_data[
        "admin_user_selected_ids"
    ] = selected_ids

    await query.answer(
        f"Selected {len(selected_ids)} users."
    )

    filter_name = context.user_data.get(
        "admin_user_filter",
        "active",
    )

    await render_user_list(
        update,
        context,
        page=context.user_data.get(
            "admin_user_page",
            0,
        ),
        filter_name=filter_name,
        selection_mode=True,
    )


async def clear_user_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Clear all selected users."""

    query = update.callback_query

    if query is None:
        return

    _clear_user_selection(
        context
    )

    await query.answer(
        "Selection cleared."
    )

    filter_name = context.user_data.get(
        "admin_user_filter",
        "active",
    )

    await render_user_list(
        update,
        context,
        page=context.user_data.get(
            "admin_user_page",
            0,
        ),
        filter_name=filter_name,
        selection_mode=True,
    )

async def render_user_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page=0,
    filter_name="active",
    selection_mode=False,
):
    """
    Re-render the current Active/Blocked user list.

    Used by pagination and selection mode.
    """

    query = update.callback_query

    if query is None:
        return

    all_users = get_all_users()

    if filter_name == "blocked":
        users = [
            user
            for user in all_users
            if bool(user["is_blocked"])
        ]

        title = "🔴 Blocked Users"

    else:
        users = [
            user
            for user in all_users
            if not bool(user["is_blocked"])
        ]

        filter_name = "active"
        title = "🟢 Active Users"

    total_users = len(users)

    if total_users == 0:
        await query.edit_message_text(
            f"{title}\n\n"
            "No users were found.",
            reply_markup=user_status_keyboard(),
            parse_mode="HTML",
        )
        return

    total_pages = (
        total_users + PAGE_SIZE - 1
    ) // PAGE_SIZE

    page = max(
        0,
        min(
            page,
            total_pages - 1,
        ),
    )

    context.user_data[
        "admin_user_filter"
    ] = filter_name

    context.user_data[
        "admin_user_page"
    ] = page

    context.user_data[
        "admin_user_selection_mode"
    ] = selection_mode

    selected_ids = context.user_data.get(
        "admin_user_selected_ids",
        set(),
    )

    if not isinstance(selected_ids, set):
        selected_ids = set(
            selected_ids
        )

    await query.edit_message_text(
        f"{title}\n\n"
        f"Total users: <b>{total_users}</b>\n"
        f"Page <b>{page + 1}</b> of "
        f"<b>{total_pages}</b>\n\n"
        + (
            f"Selected: <b>{len(selected_ids)}</b>"
            if selection_mode
            else "Choose a user to view their details."
        ),
        reply_markup=user_list_keyboard(
            users,
            page=page,
            page_size=PAGE_SIZE,
            total_users=total_users,
            search_mode=False,
            filter_name=filter_name,
            selected_ids=selected_ids,
            selection_mode=selection_mode,
        ),
        parse_mode="HTML",
    )


# ============================================================
# BULK USER ACTIONS
# ============================================================

async def request_bulk_user_action_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action,
):
    """Ask for confirmation before a bulk block/unblock."""

    query = update.callback_query

    if query is None:
        return

    selected_ids = context.user_data.get(
        "admin_user_selected_ids",
        set(),
    )

    if not selected_ids:
        await query.answer(
            "No users are selected.",
            show_alert=True,
        )
        return

    if action not in (
        "block",
        "unblock",
    ):
        await query.answer(
            "Invalid bulk action.",
            show_alert=True,
        )
        return

    # Re-check every selected account.
    valid_ids = []

    for user_id in selected_ids:
        user_record = get_user(
            user_id
        )

        if user_record is None:
            continue

        # Never bulk-manage administrators.
        if is_admin(user_id):
            continue

        if action == "block":
            if not bool(
                user_record["is_blocked"]
            ):
                valid_ids.append(
                    user_id
                )

        elif action == "unblock":
            if bool(
                user_record["is_blocked"]
            ):
                valid_ids.append(
                    user_id
                )

    if not valid_ids:
        await query.answer(
            "No eligible users are selected.",
            show_alert=True,
        )
        return

    context.user_data[
        "admin_user_selected_ids"
    ] = set(valid_ids)

    count = len(valid_ids)

    if action == "block":
        message = (
            "⚠️ <b>Block Selected Users?</b>\n\n"
            f"You selected <b>{count}</b> users.\n\n"
            "All selected users will immediately "
            "lose access to the bot.\n\n"
            "Their verification status will also "
            "be reset.\n\n"
            "<b>This action affects every selected user.</b>"
        )

    else:
        message = (
            "♻️ <b>Unblock Selected Users?</b>\n\n"
            f"You selected <b>{count}</b> users.\n\n"
            "All selected users will become eligible "
            "to access the bot again.\n\n"
            "They will still need to verify their "
            "required-channel membership.\n\n"
            "<b>This action affects every selected user.</b>"
        )

    await query.edit_message_text(
        message,
        reply_markup=user_bulk_confirmation_keyboard(
            action
        ),
        parse_mode="HTML",
    )


async def execute_bulk_user_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action,
):
    """Execute a confirmed bulk user action."""

    query = update.callback_query
    admin_user = update.effective_user

    if query is None or admin_user is None:
        return

    selected_ids = context.user_data.get(
        "admin_user_selected_ids",
        set(),
    )

    if not selected_ids:
        await query.edit_message_text(
            "No users are selected.",
            reply_markup=user_status_keyboard(),
        )
        return

    processed = 0
    skipped = 0

    for user_id in list(selected_ids):

        user_record = get_user(
            user_id
        )

        if user_record is None:
            skipped += 1
            continue

        # Never modify administrators.
        if is_admin(user_id):
            skipped += 1
            continue

        if action == "block":

            if bool(
                user_record["is_blocked"]
            ):
                skipped += 1
                continue

            block_user(
                user_id,
                reason="ADMIN_ACTION",
            )

            log_admin_action(
                admin_id=admin_user.id,
                action="USER_BLOCKED",
                target_type="user",
                target_id=user_id,
                description=(
                    f"Administrator "
                    f"{admin_user.id} "
                    f"bulk blocked user "
                    f"{user_id}"
                ),
            )

            processed += 1

        elif action == "unblock":

            if not bool(
                user_record["is_blocked"]
            ):
                skipped += 1
                continue

            unblock_user(
                user_id
            )

            log_admin_action(
                admin_id=admin_user.id,
                action="USER_UNBLOCKED",
                target_type="user",
                target_id=user_id,
                description=(
                    f"Administrator "
                    f"{admin_user.id} "
                    f"bulk unblocked user "
                    f"{user_id}"
                ),
            )

            processed += 1

        else:
            skipped += 1

    _clear_user_selection(
        context
    )

    context.user_data[
        "admin_user_selection_mode"
    ] = False

    filter_name = context.user_data.get(
        "admin_user_filter",
        "active",
    )

    if action == "block":
        title = "🔴 <b>Users Blocked</b>"

        action_text = (
            "The selected users have been blocked."
        )

    else:
        title = "🟢 <b>Users Unblocked</b>"

        action_text = (
            "The selected users have been unblocked."
        )

    await query.edit_message_text(
        f"{title}\n\n"
        f"Processed: <b>{processed}</b>\n"
        f"Skipped: <b>{skipped}</b>\n\n"
        f"{action_text}",
        reply_markup=user_list_after_bulk_keyboard(
            filter_name
        ),
        parse_mode="HTML",
    )


def user_list_after_bulk_keyboard(
    filter_name,
):
    """
    Return to the relevant status list after
    a bulk operation.
    """

    return user_status_keyboard()


async def cancel_bulk_user_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Cancel a pending bulk user action."""

    query = update.callback_query

    if query is None:
        return

    _clear_user_selection(
        context
    )

    context.user_data[
        "admin_user_selection_mode"
    ] = True

    await query.answer(
        "Bulk action cancelled."
    )

    filter_name = context.user_data.get(
        "admin_user_filter",
        "active",
    )

    await render_user_list(
        update,
        context,
        page=context.user_data.get(
            "admin_user_page",
            0,
        ),
        filter_name=filter_name,
        selection_mode=True,
    )


# ============================================================
# USER DETAILS
# ============================================================

async def show_user_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id,
):
    """Display details for one user."""

    query = update.callback_query

    if query is None:
        return

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        await query.edit_message_text(
            "Invalid user ID.",
            reply_markup=user_management_keyboard(),
        )
        return

    user_record = get_user(user_id)

    if user_record is None:
        await query.edit_message_text(
            "❌ This user does not exist in the database.",
            reply_markup=user_management_keyboard(),
        )
        return

    await query.edit_message_text(
        _format_user_details(user_record),
        reply_markup=user_details_keyboard(
            user_id,
            bool(user_record["is_blocked"]),
        ),
        parse_mode="HTML",
    )


# ============================================================
# START USER SEARCH
# ============================================================

async def start_user_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Start the user-search workflow."""

    query = update.callback_query

    if query is None:
        return

    context.user_data.pop(
        "awaiting_file_search",
        None,
    )

    context.user_data[
        "awaiting_user_search"
    ] = True

    context.user_data.pop(
        "admin_user_search_query",
        None,
    )

    context.user_data.pop(
        "admin_user_search_results",
        None,
    )

    await query.edit_message_text(
        "🔎 <b>Search Users</b>\n\n"
        "Enter a Telegram user ID, username, "
        "or first name.\n\n"
        "Examples:\n"
        "• <code>123456789</code>\n"
        "• <code>john</code>\n"
        "• <code>John</code>",
        reply_markup=user_search_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# CANCEL USER SEARCH
# ============================================================

async def cancel_user_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Cancel an active user search."""

    query = update.callback_query

    if query is None:
        return

    context.user_data.pop(
        "awaiting_user_search",
        None,
    )

    context.user_data.pop(
        "admin_user_search_query",
        None,
    )

    context.user_data.pop(
        "admin_user_search_results",
        None,
    )

    await query.answer(
        "Search cancelled."
    )

    await query.edit_message_text(
        "👥 <b>User Management</b>\n\n"
        "Manage registered users, inspect user details, "
        "or search for a specific user.",
        reply_markup=user_management_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# USER SEARCH RESULTS
# ============================================================

async def show_user_search_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    search_query=None,
    page=0,
):
    """Display paginated user-search results."""

    query = update.callback_query

    if query is None:
        return

    if search_query is not None:
        results = search_users(
            search_query
        )

        context.user_data[
            "admin_user_search_query"
        ] = search_query

        context.user_data[
            "admin_user_search_results"
        ] = [
            user["user_id"]
            for user in results
        ]

    else:
        search_query = context.user_data.get(
            "admin_user_search_query"
        )

        stored_ids = context.user_data.get(
            "admin_user_search_results",
            [],
        )

        results = []

        for user_id in stored_ids:
            user_record = get_user(
                user_id
            )

            if user_record is not None:
                results.append(user_record)

    if not search_query:
        await query.edit_message_text(
            "No search query was provided.",
            reply_markup=user_management_keyboard(),
        )
        return

    if not results:
        await query.edit_message_text(
            "🔎 <b>User Search</b>\n\n"
            f"Query: <code>{html.escape(str(search_query))}</code>\n\n"
            "❌ No matching users were found.",
            reply_markup=user_search_keyboard(),
            parse_mode="HTML",
        )

        context.user_data[
            "awaiting_user_search"
        ] = True

        return

    total_users = len(results)

    total_pages = (
        total_users + PAGE_SIZE - 1
    ) // PAGE_SIZE

    page = max(
        0,
        min(page, total_pages - 1),
    )

    context.user_data[
        "admin_user_page"
    ] = page

    await query.edit_message_text(
        "🔎 <b>User Search Results</b>\n\n"
        f"Query: <code>{html.escape(str(search_query))}</code>\n"
        f"Matches: <b>{total_users}</b>\n"
        f"Page <b>{page + 1}</b> of <b>{total_pages}</b>",
        reply_markup=user_list_keyboard(
            results,
            page=page,
            page_size=PAGE_SIZE,
            total_users=total_users,
            search_mode=True,
        ),
        parse_mode="HTML",
    )


# ============================================================
# REQUEST BLOCK / UNBLOCK CONFIRMATION
# ============================================================

async def request_user_action_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action,
    user_id,
):
    """Ask for confirmation before blocking or unblocking."""

    query = update.callback_query

    if query is None:
        return

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        await query.edit_message_text(
            "Invalid user ID.",
            reply_markup=user_management_keyboard(),
        )
        return

    user_record = get_user(user_id)

    if user_record is None:
        await query.edit_message_text(
            "❌ This user does not exist.",
            reply_markup=user_management_keyboard(),
        )
        return

    # Admins are managed separately in Step 4E.
    if is_admin(user_id):
        await query.answer(
            "Administrators cannot be managed from User Management.",
            show_alert=True,
        )

        await query.edit_message_text(
            "👑 This account is an administrator.\n\n"
            "Administrator management belongs to the "
            "Admin Management section.",
            reply_markup=user_management_keyboard(),
        )
        return

    first_name = html.escape(
        _safe(user_record["first_name"])
    )

    if action == "block":
        message = (
            "⚠️ <b>Block User?</b>\n\n"
            f"Name: {first_name}\n"
            f"User ID: <code>{user_id}</code>\n\n"
            "The user will immediately lose access "
            "to the bot.\n\n"
            "Their verification status will also be reset.\n\n"
            "<b>Are you sure?</b>"
        )

    elif action == "unblock":
        message = (
            "♻️ <b>Unblock User?</b>\n\n"
            f"Name: {first_name}\n"
            f"User ID: <code>{user_id}</code>\n\n"
            "The user will become eligible to access "
            "the bot again.\n\n"
            "They will still need to verify their "
            "required-channel membership.\n\n"
            "<b>Are you sure?</b>"
        )

    else:
        await query.edit_message_text(
            "Invalid user action.",
            reply_markup=user_management_keyboard(),
        )
        return

    await query.edit_message_text(
        message,
        reply_markup=user_action_confirmation_keyboard(
            action,
            user_id,
        ),
        parse_mode="HTML",
    )


# ============================================================
# EXECUTE BLOCK / UNBLOCK
# ============================================================

async def execute_user_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action,
    user_id,
):
    """Execute a confirmed user action."""

    query = update.callback_query
    admin_user = update.effective_user

    if query is None or admin_user is None:
        return

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        await query.edit_message_text(
            "Invalid user ID.",
            reply_markup=user_management_keyboard(),
        )
        return

    user_record = get_user(user_id)

    if user_record is None:
        await query.edit_message_text(
            "❌ This user no longer exists.",
            reply_markup=user_management_keyboard(),
        )
        return

    # Never allow User Management to alter administrators.
    if is_admin(user_id):
        await query.edit_message_text(
            "👑 This account is an administrator.\n\n"
            "Administrator management belongs to "
            "Admin Management.",
            reply_markup=user_management_keyboard(),
        )
        return

    if action == "block":
        block_user(
            user_id,
            reason="ADMIN_ACTION",
        )

        log_admin_action(
            admin_id=admin_user.id,
            action="USER_BLOCKED",
            target_type="user",
            target_id=user_id,
            description=(
                f"Administrator {admin_user.id} "
                f"blocked user {user_id}"
            ),
        )

        await query.edit_message_text(
            "🔴 <b>User Blocked</b>\n\n"
            f"User <code>{user_id}</code> has been blocked.\n\n"
            "The user can no longer access the bot.",
            reply_markup=user_management_keyboard(),
            parse_mode="HTML",
        )

        return

    if action == "unblock":
        unblock_user(
            user_id
        )

        log_admin_action(
            admin_id=admin_user.id,
            action="USER_UNBLOCKED",
            target_type="user",
            target_id=user_id,
            description=(
                f"Administrator {admin_user.id} "
                f"unblocked user {user_id}"
            ),
        )

        await query.edit_message_text(
            "🟢 <b>User Unblocked</b>\n\n"
            f"User <code>{user_id}</code> has been unblocked.\n\n"
            "The user must verify their required-channel "
            "membership before accessing the bot again.",
            reply_markup=user_management_keyboard(),
            parse_mode="HTML",
        )

        return

    await query.edit_message_text(
        "Invalid user action.",
        reply_markup=user_management_keyboard(),
    )


# ============================================================
# CANCEL USER ACTION
# ============================================================

async def cancel_user_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id,
):
    """Cancel a pending user action."""

    query = update.callback_query

    if query is None:
        return

    await query.answer(
        "Action cancelled."
    )

    await show_user_details(
        update,
        context,
        user_id,
    )


# ============================================================
# USER SEARCH TEXT HANDLER
# ============================================================

async def handle_user_search_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Receive the administrator's user-search text.

    Returns True when the message was handled.
    """

    user = update.effective_user
    message = update.message

    if user is None or message is None:
        return False

    if not context.user_data.get(
        "awaiting_user_search"
    ):
        return False

    if not is_authorized_admin(user.id):
        context.user_data.pop(
            "awaiting_user_search",
            None,
        )

        await message.reply_text(
            "❌ You are not authorized to search users."
        )

        return True

    search_query = message.text.strip()

    if not search_query:
        await message.reply_text(
            "Please enter a user ID, username, or name."
        )
        return True

    context.user_data.pop(
        "awaiting_user_search",
        None,
    )

    results = search_users(
        search_query
    )

    context.user_data[
        "admin_user_search_query"
    ] = search_query

    context.user_data[
        "admin_user_search_results"
    ] = [
        user_record["user_id"]
        for user_record in results
    ]

    # Search results must be displayed through
    # the callback-driven interface.
    if not results:
        await message.reply_text(
            "🔎 <b>User Search</b>\n\n"
            f"Query: <code>{html.escape(search_query)}</code>\n\n"
            "❌ No matching users were found.\n\n"
            "Press Search Users to try again.",
            reply_markup=user_management_keyboard(),
            parse_mode="HTML",
        )

        return True

    total_users = len(results)
    total_pages = (
        total_users + PAGE_SIZE - 1
    ) // PAGE_SIZE

    await message.reply_text(
        "🔎 <b>User Search Results</b>\n\n"
        f"Query: <code>{html.escape(search_query)}</code>\n"
        f"Matches: <b>{total_users}</b>\n"
        f"Page <b>1</b> of <b>{total_pages}</b>",
        reply_markup=user_list_keyboard(
            results,
            page=0,
            page_size=PAGE_SIZE,
            total_users=total_users,
            search_mode=True,
        ),
        parse_mode="HTML",
    )

    context.user_data[
        "admin_user_page"
    ] = 0

    return True


# ============================================================
# USER MANAGEMENT CALLBACK ROUTER
# ============================================================

async def handle_user_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Route User Management callbacks.

    Authorization is checked independently.
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

        await query.edit_message_text(
            "You are not authorized to access User Management."
        )

        return

    await query.answer()

    data = query.data or ""

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------

    if data == "admin:users":
        await show_user_management(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # ALL USERS / STATUS FILTERS
    # --------------------------------------------------------

    if data == "admin:users:list":
        await show_user_status_menu(
            update,
            context,
        )
        return

    if data == "admin:users:list:active":
        context.user_data[
            "admin_user_filter"
        ] = "active"

        context.user_data[
            "admin_user_selection_mode"
        ] = False

        _clear_user_selection(
            context
        )

        await show_user_list(
            update,
            context,
            page=0,
            filter_name="active",
        )
        return

    if data == "admin:users:list:blocked":
        context.user_data[
            "admin_user_filter"
        ] = "blocked"

        context.user_data[
            "admin_user_selection_mode"
        ] = False

        _clear_user_selection(
            context
        )

        await show_user_list(
            update,
            context,
            page=0,
            filter_name="blocked",
        )
        return

    if data.startswith(
        "admin:users:page:"
    ):
        try:
            page = int(
                data.rsplit(":", 1)[1]
            )
        except ValueError:
            await query.edit_message_text(
                "Invalid user page.",
                reply_markup=user_status_keyboard(),
            )
            return

        filter_name = context.user_data.get(
            "admin_user_filter",
            "active",
        )

        selection_mode = context.user_data.get(
            "admin_user_selection_mode",
            False,
        )

        await render_user_list(
            update,
            context,
            page=page,
            filter_name=filter_name,
            selection_mode=selection_mode,
        )
        return

    # --------------------------------------------------------
    # USER SELECTION MODE
    # --------------------------------------------------------

    if data == "admin:users:selection_mode":
        await enter_user_selection_mode(
            update,
            context,
        )
        return

    if data == "admin:users:details_mode":
        await exit_user_selection_mode(
            update,
            context,
        )
        return

    if data.startswith(
        "admin:user:select:"
    ):
        user_id = data.rsplit(
            ":",
            1,
        )[1]

        await toggle_user_selection(
            update,
            context,
            user_id,
        )
        return

    if data == "admin:users:select_all":
        await select_all_users(
            update,
            context,
        )
        return

    if data == "admin:users:clear_selection":
        await clear_user_selection(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # BULK USER ACTIONS
    # --------------------------------------------------------

    if data == "admin:users:bulk:block":
        await request_bulk_user_action_confirmation(
            update,
            context,
            "block",
        )
        return

    if data == "admin:users:bulk:unblock":
        await request_bulk_user_action_confirmation(
            update,
            context,
            "unblock",
        )
        return

    if data.startswith(
        "admin:users:bulk:confirm:"
    ):
        action = data.rsplit(
            ":",
            1,
        )[1]

        await execute_bulk_user_action(
            update,
            context,
            action,
        )
        return

    if data == "admin:users:bulk:cancel":
        await cancel_bulk_user_action(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    if data == "admin:users:search":
        await start_user_search(
            update,
            context,
        )
        return

    if data == "admin:users:search:cancel":
        await cancel_user_search(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # USER DETAILS
    # --------------------------------------------------------

    if data.startswith("admin:user:"):

        parts = data.split(":")

        # admin:user:<id>
        if len(parts) == 3:
            user_id = parts[2]

            await show_user_details(
                update,
                context,
                user_id,
            )

            return

        # admin:user:block:<id>
        if len(parts) == 4 and parts[2] == "block":
            user_id = parts[3]

            await request_user_action_confirmation(
                update,
                context,
                "block",
                user_id,
            )

            return

        # admin:user:unblock:<id>
        if len(parts) == 4 and parts[2] == "unblock":
            user_id = parts[3]

            await request_user_action_confirmation(
                update,
                context,
                "unblock",
                user_id,
            )

            return

        # admin:user:confirm:<action>:<id>
        if len(parts) == 5 and parts[2] == "confirm":
            action = parts[3]
            user_id = parts[4]

            await execute_user_action(
                update,
                context,
                action,
                user_id,
            )

            return

        # admin:user:cancel:<id>
        if len(parts) == 4 and parts[2] == "cancel":
            user_id = parts[3]

            await cancel_user_action(
                update,
                context,
                user_id,
            )

            return

    await query.edit_message_text(
        "This user-management action is invalid.",
        reply_markup=user_management_keyboard(),
    )