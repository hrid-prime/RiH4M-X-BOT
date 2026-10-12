import html
import re
from difflib import SequenceMatcher

from telegram import Update
from telegram.ext import ContextTypes

from auth import is_authorized_admin
from admin.user_manager import handle_user_search_text
from admin.admin_manager import handle_admin_text

from database import (
    get_all_files,
    get_file_by_id,
    deactivate_file,
    reactivate_file,
    delete_file,
    log_admin_action,
)

from keyboards.admin import (
    file_management_keyboard,
    file_list_keyboard,
    file_details_keyboard,
    file_confirmation_keyboard,
    file_bulk_confirmation_keyboard,
    file_upload_keyboard,
    file_search_keyboard,
    file_search_results_keyboard,
    bulk_upload_keyboard,
)


PAGE_SIZE = 10

def _normalize_search_text(value):
    """
    Normalize text for tolerant file searching.

    Converts values to lowercase and removes punctuation
    differences so searches are less sensitive to formatting.
    """

    if value is None:
        return ""

    value = str(value).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(value.split())


def _search_similarity(query, text):
    """
    Return a similarity score between 0.0 and 1.0.
    """

    query = _normalize_search_text(query)
    text = _normalize_search_text(text)

    if not query or not text:
        return 0.0

    if query == text:
        return 1.0

    if query in text:
        return 0.90

    query_words = query.split()
    text_words = text.split()

    word_score = 0.0

    for query_word in query_words:
        best_word_score = 0.0

        for text_word in text_words:
            score = SequenceMatcher(
                None,
                query_word,
                text_word,
            ).ratio()

            if score > best_word_score:
                best_word_score = score

        word_score += best_word_score

    if query_words:
        word_score /= len(query_words)

    full_score = SequenceMatcher(
        None,
        query,
        text,
    ).ratio()

    return max(
        word_score,
        full_score,
    )


def _search_files(query):
    """
    Search all files and return them ordered by relevance.

    Search fields:
        - file name
        - file key
        - caption
        - database ID

    Small spelling mistakes are tolerated through fuzzy matching.
    """

    query = _normalize_search_text(query)

    if not query:
        return []

    all_files = get_all_files(
        include_inactive=True,
    )

    results = []

    for file_record in all_files:
        file_name = file_record["file_name"] or ""
        file_key = file_record["file_key"] or ""
        caption = file_record["caption"] or ""
        database_id = str(file_record["id"])

        candidates = [
            (file_name, 1.00),
            (file_key, 0.95),
            (caption, 0.75),
            (database_id, 0.90),
        ]

        best_score = 0.0

        for value, weight in candidates:
            score = _search_similarity(
                query,
                value,
            )

            weighted_score = score * weight

            if weighted_score > best_score:
                best_score = weighted_score

        # Ignore extremely weak fuzzy matches.
        if best_score >= 0.45:
            results.append(
                (
                    best_score,
                    file_record,
                )
            )

    results.sort(
        key=lambda item: (
            -item[0],
            -int(item[1]["id"]),
        )
    )

    return [
        file_record
        for _, file_record in results
    ]


def _record_value(record, key, default=None):
    """
    Safely read a value from either a sqlite3.Row or dictionary-like object.
    """

    try:
        return record[key]
    except (KeyError, IndexError, TypeError):
        return default


def _format_file_size(size):
    if size is None:
        return "Unknown"

    try:
        size = int(size)
    except (TypeError, ValueError):
        return "Unknown"

    units = ["B", "KB", "MB", "GB", "TB"]

    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"

        value /= 1024

    return "Unknown"


def _format_file_details(file_record):
    file_id = _record_value(file_record, "id")
    file_key = _record_value(file_record, "file_key")
    file_name = _record_value(file_record, "file_name") or "Unnamed"
    file_type = _record_value(file_record, "file_type") or "Unknown"
    file_size = _record_value(file_record, "file_size")
    download_count = _record_value(file_record, "download_count", 0)
    is_active = _record_value(file_record, "is_active", 0)
    uploaded_by = _record_value(file_record, "uploaded_by")
    uploaded_at = _record_value(file_record, "uploaded_at")

    status = "🟢 Active" if is_active else "🔴 Inactive"

    return (
        "📄 File Details\n\n"
        f"ID: {file_id}\n"
        f"Key: {file_key}\n"
        f"Name: {file_name}\n"
        f"Type: {file_type}\n"
        f"Size: {_format_file_size(file_size)}\n"
        f"Downloads: {download_count}\n"
        f"Status: {status}\n"
        f"Uploaded by: {uploaded_by}\n"
        f"Uploaded: {uploaded_at}"
    )


async def show_file_management(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Display the main file-management menu."""

    query = update.callback_query

    if query is None:
        return

    # Returning to the main File Management menu always
    # starts a clean normal-management state.
    _clear_file_search_state(context)

    context.user_data[
        "admin_file_selection_mode"
    ] = False

    _clear_selected_file_ids(
        context
    )

    await query.edit_message_text(
        "📁 File Management\n\nChoose an option:",
        reply_markup=file_management_keyboard(),
    )


def _get_files_for_filter(filter_name):
    """
    Return files according to the requested status filter.
    """

    if filter_name == "active":
        return get_all_files(include_inactive=False)

    if filter_name == "inactive":
        return [
            file_record
            for file_record in get_all_files(include_inactive=True)
            if not _record_value(file_record, "is_active", 0)
        ]

    return get_all_files(include_inactive=True)

def _get_selected_file_ids(context):
    """Return the current admin's selected file IDs."""

    selected_ids = context.user_data.get(
        "admin_selected_file_ids",
        [],
    )

    return {
        int(file_id)
        for file_id in selected_ids
    }


def _save_selected_file_ids(
    context,
    selected_ids,
):
    """Save selected file IDs in the current admin session."""

    context.user_data[
        "admin_selected_file_ids"
    ] = sorted(
        int(file_id)
        for file_id in selected_ids
    )


def _clear_selected_file_ids(context):
    """Clear the current admin's file selection."""

    context.user_data.pop(
        "admin_selected_file_ids",
        None,
    )


def _clear_file_search_state(context):
    """
    Clear all file-search state from the current admin session.
    """

    context.user_data.pop(
        "awaiting_file_search",
        None,
    )

    context.user_data.pop(
        "admin_file_search_query",
        None,
    )

    context.user_data.pop(
        "admin_file_search_results",
        None,
    )

    context.user_data.pop(
        "admin_file_search_page",
        None,
    )


def _get_current_file_ids(
    context,
):
    """
    Return file IDs belonging to the current
    file-management view.

    For search results, use the stored search-result IDs.
    Otherwise use the current status filter.
    """

    search_ids = context.user_data.get(
        "admin_file_search_results"
    )

    if search_ids is not None:
        return [
            int(file_id)
            for file_id in search_ids
            if get_file_by_id(file_id) is not None
        ]

    filter_name = context.user_data.get(
        "admin_file_filter",
        "all",
    )

    files = _get_files_for_filter(filter_name)

    return [
        int(record["id"])
        for record in files
    ]

async def show_file_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    filter_name="all",
    page=0,
):
    """Display a paginated file list."""

    query = update.callback_query

    if query is None:
        return

    # Normal file lists must never inherit search state.
    _clear_file_search_state(context)

    files = _get_files_for_filter(
        filter_name
    )

    if not files:
        await query.edit_message_text(
            "📁 No files found for this filter.",
            reply_markup=file_management_keyboard(),
        )
        return

    total_pages = (
        len(files) + PAGE_SIZE - 1
    ) // PAGE_SIZE

    page = max(
        0,
        min(page, total_pages - 1),
    )

    title_map = {
        "all": "📋 All Files",
        "active": "🟢 Active Files",
        "inactive": "🔴 Inactive Files",
    }

    title = title_map.get(
        filter_name,
        "📋 Files",
    )

    selection_mode = bool(
        context.user_data.get(
            "admin_file_selection_mode",
            False,
        )
    )

    selected_ids = _get_selected_file_ids(
        context
    )

    # Keep only files belonging to the current
    # filter. This prevents stale selections from
    # another filter from remaining active.
    current_file_ids = {
        int(record["id"])
        for record in files
    }

    selected_ids = {
        file_id
        for file_id in selected_ids
        if file_id in current_file_ids
    }

    _save_selected_file_ids(
        context,
        selected_ids,
    )

    context.user_data[
        "admin_file_filter"
    ] = filter_name

    context.user_data[
        "admin_file_page"
    ] = page

    await query.edit_message_text(
        f"{title}\n\n"
        f"Page {page + 1} of {total_pages}\n"
        f"Total files: {len(files)}\n"
        f"Selected: {len(selected_ids)}",
        reply_markup=file_list_keyboard(
            files,
            page=page,
            page_size=PAGE_SIZE,
            selected_ids=selected_ids,
            selection_mode=selection_mode,
            filter_name=filter_name,
        ),
    )

async def show_file_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_id,
):
    """Display details for one file."""

    query = update.callback_query

    if query is None:
        return

    try:
        file_id = int(file_id)
    except (TypeError, ValueError):
        await query.edit_message_text(
            "Invalid file identifier."
        )
        return

    file_record = get_file_by_id(file_id)

    if file_record is None:
        await query.edit_message_text(
            "This file no longer exists.",
            reply_markup=file_management_keyboard(),
        )
        return

    is_active = bool(_record_value(file_record, "is_active", 0))

    await query.edit_message_text(
        _format_file_details(file_record),
        reply_markup=file_details_keyboard(
            file_id,
            is_active,
        ),
    )


async def request_file_action_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action,
    file_id,
):
    """Ask for confirmation before changing file state."""

    query = update.callback_query

    if query is None:
        return

    try:
        file_id = int(file_id)
    except (TypeError, ValueError):
        await query.edit_message_text(
            "Invalid file identifier."
        )
        return

    file_record = get_file_by_id(file_id)

    if file_record is None:
        await query.edit_message_text(
            "This file no longer exists.",
            reply_markup=file_management_keyboard(),
        )
        return

    file_name = html.escape(
            str(
                _record_value(
                    file_record,
                    "file_name",
                )
                or "Unnamed file"
            ),
            quote=False,
        )

    if action == "deactivate":
        message = (
            "⚠️ <b>Deactivate File</b>\n\n"
            f"File: {file_name}\n"
            f"Key: {_record_value(file_record, 'file_key')}\n\n"
            "This will make the file unavailable through "
            "its public deep link.\n\n"
            "The database record will NOT be deleted.\n\n"
            "Are you sure?"
        )

    elif action == "reactivate":
        message = (
            "♻️ <b>Reactivate File</b>\n\n"
            f"File: {file_name}\n"
            f"Key: {_record_value(file_record, 'file_key')}\n\n"
            "The file will become available again.\n\n"
            "Are you sure?"
        )

    elif action == "delete":
        message = (
            "⚠️ <b>Permanently Delete File?</b>\n\n"
            f"File: {file_name}\n"
            f"Key: {_record_value(file_record, 'file_key')}\n\n"
            "This will permanently remove the file "
            "from the database.\n\n"
            "This action CANNOT be undone.\n\n"
            "Are you sure?"
        )

    else:
        await query.edit_message_text(
            "Invalid file action."
        )
        return

    await query.edit_message_text(
        message,
        reply_markup=file_confirmation_keyboard(
            action,
            file_id,
        ),
        parse_mode="HTML",
    )


async def execute_file_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action,
    file_id,
):
    """Execute a confirmed file action."""

    query = update.callback_query
    user = update.effective_user

    if query is None:
        return

    try:
        file_id = int(file_id)
    except (TypeError, ValueError):
        await query.edit_message_text(
            "Invalid file identifier."
        )
        return

    file_record = get_file_by_id(file_id)

    if file_record is None:
        await query.edit_message_text(
            "This file no longer exists.",
            reply_markup=file_management_keyboard(),
        )
        return

    try:
        if action == "deactivate":
                    changed = deactivate_file(file_id)
                    success_message = (
                        "🔴 File deactivated successfully."
                    )

                    if changed:
                        log_admin_action(
                            admin_id=user.id,
                            action="FILE_DEACTIVATED",
                            target_type="file",
                            target_id=file_id,
                            description=(
                                f"Deactivated file {file_id}"
                            ),
                        )

        elif action == "reactivate":
            changed = reactivate_file(file_id)
            success_message = (
                "🟢 File reactivated successfully."
            )

            if changed:
                log_admin_action(
                    admin_id=user.id,
                    action="FILE_REACTIVATED",
                    target_type="file",
                    target_id=file_id,
                    description=(
                        f"Reactivated file {file_id}"
                    ),
                )

        elif action == "delete":
            changed = delete_file(file_id)

            if changed:
                log_admin_action(
                    admin_id=user.id,
                    action="FILE_DELETED",
                    target_type="file",
                    target_id=file_id,
                    description=(
                        f"Permanently deleted file "
                        f"{file_id}"
                    ),
                )

            if changed:
                await query.edit_message_text(
                    "🗑 <b>File Permanently Deleted</b>\n\n"
                    "The file has been permanently removed "
                    "from the database.",
                    reply_markup=file_management_keyboard(),
                    parse_mode="HTML",
                )
            else:
                await query.edit_message_text(
                    "The file could not be deleted because "
                    "it no longer exists.",
                    reply_markup=file_management_keyboard(),
                )

            return

        else:
            await query.edit_message_text(
                "Invalid file action."
            )
            return

    except Exception:
        await query.edit_message_text(
            "The file operation failed. Please try again."
        )
        raise

    if not changed:
        await query.edit_message_text(
            "No change was made to the file.",
            reply_markup=file_management_keyboard(),
        )
        return

    updated_record = get_file_by_id(file_id)

    if updated_record is None:
        await query.edit_message_text(
            success_message,
            reply_markup=file_management_keyboard(),
        )
        return

    await query.edit_message_text(
        success_message
        + "\n\n"
        + _format_file_details(updated_record),
        reply_markup=file_details_keyboard(
            file_id,
            bool(
                _record_value(
                    updated_record,
                    "is_active",
                    0,
                )
            ),
        ),
    )


async def cancel_file_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_id,
):
    """Cancel a pending file action."""

    query = update.callback_query

    if query is None:
        return

    try:
        file_id = int(file_id)
    except (TypeError, ValueError):
        await query.edit_message_text(
            "Invalid file identifier.",
            reply_markup=file_management_keyboard(),
        )
        return

    file_record = get_file_by_id(file_id)

    if file_record is None:
        await query.edit_message_text(
            "This file no longer exists.",
            reply_markup=file_management_keyboard(),
        )
        return

    await query.edit_message_text(
        "Action cancelled.\n\n" + _format_file_details(file_record),
        reply_markup=file_details_keyboard(
            file_id,
            bool(_record_value(file_record, "is_active", 0)),
        ),
    )


async def get_file_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_id,
):
    """
    Display the deep link for a file.

    We intentionally build the link from the stored file_key.
    """

    query = update.callback_query

    if query is None:
        return

    try:
        file_id = int(file_id)
    except (TypeError, ValueError):
        await query.edit_message_text(
            "Invalid file identifier."
        )
        return

    file_record = get_file_by_id(file_id)

    if file_record is None:
        await query.edit_message_text(
            "This file no longer exists.",
            reply_markup=file_management_keyboard(),
        )
        return

    file_key = _record_value(file_record, "file_key")

    # The bot username is obtained from Telegram rather than hard-coded.
    bot_user = await context.bot.get_me()

    username = bot_user.username

    if not username or not file_key:
        await query.edit_message_text(
            "The file link could not be generated.",
            reply_markup=file_management_keyboard(),
        )
        return

    link = f"https://t.me/{username}?start={file_key}"

    await query.edit_message_text(
        f"🔗 File Link\n\n{link}",
        reply_markup=file_details_keyboard(
            file_id,
            bool(_record_value(file_record, "is_active", 0)),
        ),
    )

async def start_file_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Start the file-search workflow.
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
            "You are not authorized to access the admin panel."
        )
        return

# Start every new search with a completely clean workflow state.

    context.user_data.pop(
        "awaiting_file_upload",
        None,
    )
    context.user_data.pop(
        "admin_upload_origin",
        None,
    )
    context.user_data.pop(
        "awaiting_bulk_upload",
        None,
    )
    context.user_data.pop(
        "admin_bulk_upload_origin",
        None,
    )
    context.user_data.pop(
        "bulk_uploaded_count",
        None,
    )
    context.user_data.pop(
        "bulk_failed_count",
        None,
    )
    context.user_data.pop(
        "bulk_failed_files",
        None,
    )

    _clear_file_search_state(context)

    context.user_data[
        "admin_file_selection_mode"
    ] = False

    _clear_selected_file_ids(
        context
    )

    context.user_data[
        "admin_file_search_page"
    ] = 0

    context.user_data[
        "awaiting_file_search"
    ] = True

    await query.edit_message_text(
        "🔎 <b>Search Files</b>\n\n"
        "Enter a file name, file key, caption, or database ID.\n\n"
        "The search is tolerant of small spelling mistakes.\n\n"
        "Examples:\n"
        "• <code>logo</code>\n"
        "• <code>black shadow</code>\n"
        "• <code>shaddow</code>\n"
        "• <code>file_12</code>",
        reply_markup=file_search_keyboard(),
        parse_mode="HTML",
    )


async def cancel_file_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Cancel an active file search.
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
            "You are not authorized to access the admin panel."
        )
        return

    context.user_data.pop(
        "awaiting_file_search",
        None,
    )

    context.user_data.pop(
        "admin_file_search_query",
        None,
    )

    context.user_data.pop(
        "admin_file_search_results",
        None,
    )

    # Return to a clean Details Mode state.
    context.user_data[
        "admin_file_selection_mode"
    ] = False

    _clear_selected_file_ids(
        context
    )

    context.user_data.pop(
        "admin_file_search_page",
        None,
    )

    await query.answer("Search cancelled.")

    await query.edit_message_text(
        "📁 File Management\n\nChoose an option:",
        reply_markup=file_management_keyboard(),
    )


async def show_file_search_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    search_query=None,
    page=0,
):
    """
    Display paginated file-search results.
    """

    query = update.callback_query

    if query is None:
        return

    if search_query is not None:
        results = _search_files(
            search_query
        )

        context.user_data[
            "admin_file_search_query"
        ] = search_query

        context.user_data[
            "admin_file_search_results"
        ] = [
            record["id"]
            for record in results
        ]

    else:
        search_query = context.user_data.get(
            "admin_file_search_query"
        )

        stored_ids = context.user_data.get(
            "admin_file_search_results",
            [],
        )

        results = []

        for file_id in stored_ids:
            file_record = get_file_by_id(
                file_id
            )

            if file_record is not None:
                results.append(file_record)

    if not search_query:
        await query.edit_message_text(
            "No search query was provided.",
            reply_markup=file_management_keyboard(),
        )
        return

    safe_search_query = html.escape(
        str(search_query)
    )

    if not results:
            await query.edit_message_text(
                f"🔎 <b>Search Results</b>\n\n"
                f"Query: <code>{safe_search_query}</code>\n\n"
                "❌ No matching files were found.\n\n"
                "Try a shorter word, part of the filename, "
                "or a different spelling.",
                reply_markup=file_search_keyboard(),
                parse_mode="HTML",
            )

            context.user_data[
                "awaiting_file_search"
            ] = True

            return

    total_pages = (
        len(results) + PAGE_SIZE - 1
    ) // PAGE_SIZE

    page = max(
        0,
        min(page, total_pages - 1),
    )

    selection_mode = bool(
        context.user_data.get(
            "admin_file_selection_mode",
            False,
        )
    )

    search_file_ids = {
        int(record["id"])
        for record in results
    }

    selected_ids = _get_selected_file_ids(
        context
    )

    selected_ids = {
        file_id
        for file_id in selected_ids
        if file_id in search_file_ids
    }

    _save_selected_file_ids(
        context,
        selected_ids,
    )

    context.user_data[
        "admin_file_search_page"
    ] = page

    keyboard = file_search_results_keyboard(
        results,
        page=page,
        page_size=PAGE_SIZE,
        selected_ids=selected_ids,
        selection_mode=selection_mode,
    )

    await query.edit_message_text(
        f"🔎 <b>Search Results</b>\n\n"
        f"Query: <code>{safe_search_query}</code>\n"
        f"Matches: {len(results)}\n"
        f"Page {page + 1} of {total_pages}\n"
        f"Selected: {len(selected_ids)}",
        reply_markup=keyboard,
        parse_mode="HTML",
    )

async def enter_file_selection_mode(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Switch the current file view into selection mode."""

    query = update.callback_query

    if query is None:
        return

    context.user_data[
        "admin_file_selection_mode"
    ] = True

    await query.answer(
        "Selection mode enabled."
    )

    search_query = context.user_data.get(
        "admin_file_search_query"
    )

    if search_query:
        page = context.user_data.get(
            "admin_file_search_page",
            0,
        )

        await show_file_search_results(
            update,
            context,
            search_query=None,
            page=page,
        )
        return

    filter_name = context.user_data.get(
        "admin_file_filter",
        "all",
    )

    page = context.user_data.get(
        "admin_file_page",
        0,
    )

    await show_file_list(
        update,
        context,
        filter_name,
        page,
    )


async def exit_file_selection_mode(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Return to details mode and clear selections."""

    query = update.callback_query

    if query is None:
        return

    context.user_data[
        "admin_file_selection_mode"
    ] = False

    _clear_selected_file_ids(
        context
    )

    await query.answer(
        "Details mode enabled."
    )

    search_query = context.user_data.get(
        "admin_file_search_query"
    )

    if search_query:
        page = context.user_data.get(
            "admin_file_search_page",
            0,
        )

        await show_file_search_results(
            update,
            context,
            search_query=None,
            page=page,
        )
        return

    filter_name = context.user_data.get(
        "admin_file_filter",
        "all",
    )

    page = context.user_data.get(
        "admin_file_page",
        0,
    )

    await show_file_list(
        update,
        context,
        filter_name,
        page,
    )

async def toggle_file_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_id,
):
    """Toggle one file in the current selection."""

    query = update.callback_query

    if query is None:
        return

    try:
        file_id = int(file_id)
    except (TypeError, ValueError):
        await query.answer(
            "Invalid file.",
            show_alert=True,
        )
        return

    current_file_ids = set(
        _get_current_file_ids(context)
    )

    if file_id not in current_file_ids:
        await query.answer(
            "This file is not part of the current view.",
            show_alert=True,
        )
        return

    selected_ids = _get_selected_file_ids(
        context
    )

    if file_id in selected_ids:
        selected_ids.remove(file_id)
        message = "File removed from selection."
    else:
        selected_ids.add(file_id)
        message = "File selected."

    _save_selected_file_ids(
        context,
        selected_ids,
    )

    await query.answer(message)

    search_query = context.user_data.get(
        "admin_file_search_query"
    )

    if search_query:
        page = context.user_data.get(
            "admin_file_search_page",
            0,
        )

        await show_file_search_results(
            update,
            context,
            search_query=None,
            page=page,
        )
        return

    filter_name = context.user_data.get(
        "admin_file_filter",
        "all",
    )

    page = context.user_data.get(
        "admin_file_page",
        0,
    )

    await show_file_list(
        update,
        context,
        filter_name,
        page,
    )


async def select_all_files(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Select every file in the current view."""

    query = update.callback_query

    if query is None:
        return

    current_ids = _get_current_file_ids(
        context
    )

    selected_ids = _get_selected_file_ids(
        context
    )

    selected_ids.update(current_ids)

    _save_selected_file_ids(
        context,
        selected_ids,
    )

    await query.answer(
        f"{len(current_ids)} files selected."
    )

    search_query = context.user_data.get(
        "admin_file_search_query"
    )

    if search_query:
        page = context.user_data.get(
            "admin_file_search_page",
            0,
        )

        await show_file_search_results(
            update,
            context,
            search_query=None,
            page=page,
        )
        return

    filter_name = context.user_data.get(
        "admin_file_filter",
        "all",
    )

    page = context.user_data.get(
        "admin_file_page",
        0,
    )

    await show_file_list(
        update,
        context,
        filter_name,
        page,
    )


async def clear_file_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Clear all currently selected files."""

    query = update.callback_query

    if query is None:
        return

    _clear_selected_file_ids(
        context
    )

    await query.answer(
        "Selection cleared."
    )

    search_query = context.user_data.get(
        "admin_file_search_query"
    )

    if search_query:
        page = context.user_data.get(
            "admin_file_search_page",
            0,
        )

        await show_file_search_results(
            update,
            context,
            search_query=None,
            page=page,
        )
        return

    filter_name = context.user_data.get(
        "admin_file_filter",
        "all",
    )

    page = context.user_data.get(
        "admin_file_page",
        0,
    )

    await show_file_list(
        update,
        context,
        filter_name,
        page,
    )

async def request_bulk_file_action_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action,
):
    """Ask for confirmation before a bulk file action."""

    query = update.callback_query

    if query is None:
        return

    selected_ids = _get_selected_file_ids(
        context
    )

    # A selection is valid only inside the current view.
    current_file_ids = set(
        _get_current_file_ids(context)
    )

    selected_ids = {
        file_id
        for file_id in selected_ids
        if file_id in current_file_ids
        and get_file_by_id(file_id) is not None
    }

    _save_selected_file_ids(
        context,
        selected_ids,
    )

    if not selected_ids:
        await query.answer(
            "No files are selected.",
            show_alert=True,
        )
        return

    count = len(selected_ids)

    if action == "deactivate":
        message = (
            "⚠️ <b>Bulk Deactivate</b>\n\n"
            f"You are about to deactivate <b>{count}</b> files.\n\n"
            "Their database records will be preserved, "
            "but their public links will stop working.\n\n"
            "Are you sure?"
        )

    elif action == "reactivate":
        message = (
            "♻️ <b>Bulk Reactivate</b>\n\n"
            f"You are about to reactivate <b>{count}</b> files.\n\n"
            "Their public links will become available again.\n\n"
            "Are you sure?"
        )

    elif action == "delete":
        message = (
            "⚠️ <b>PERMANENT BULK DELETE</b>\n\n"
            f"You are about to permanently delete "
            f"<b>{count}</b> files.\n\n"
            "The database records will be permanently removed.\n\n"
            "This action <b>CANNOT be undone</b>.\n\n"
            "Are you absolutely sure?"
        )

    else:
        await query.answer(
            "Invalid bulk action.",
            show_alert=True,
        )
        return

    await query.edit_message_text(
        message,
        reply_markup=file_bulk_confirmation_keyboard(
            action
        ),
        parse_mode="HTML",
    )


async def cancel_bulk_file_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Cancel a pending bulk file action."""

    query = update.callback_query

    if query is None:
        return

    selected_ids = _get_selected_file_ids(context)

    await query.answer(
        "Bulk action cancelled."
    )

    search_ids = context.user_data.get(
        "admin_file_search_results"
    )

    if search_ids is not None:
        await show_file_search_results(
            update,
            context,
            search_query=None,
            page=0,
        )
        return

    filter_name = context.user_data.get(
        "admin_file_filter",
        "all",
    )

    await show_file_list(
        update,
        context,
        filter_name,
        0,
    )

async def execute_bulk_file_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action,
):
    """Execute a confirmed bulk file action."""

    query = update.callback_query
    user = update.effective_user

    if query is None or user is None:
        return

    selected_ids = _get_selected_file_ids(
        context,
    )

    # Never execute a bulk operation against files
    # outside the current file-management view.
    current_file_ids = set(
        _get_current_file_ids(context)
    )

    selected_ids = {
        file_id
        for file_id in selected_ids
        if file_id in current_file_ids
    }

    _save_selected_file_ids(
        context,
        selected_ids,
    )

    if not selected_ids:
        await query.edit_message_text(
            "No files are selected.",
            reply_markup=file_management_keyboard(),
        )
        return

    success_count = 0
    skipped_count = 0
    failed_count = 0
    affected_ids = []

    for file_id in sorted(selected_ids):
        file_record = get_file_by_id(file_id)

        if file_record is None:
            failed_count += 1
            continue

        try:
            is_active = bool(
                _record_value(
                    file_record,
                    "is_active",
                    0,
                )
            )

            if action == "deactivate":

                if not is_active:
                    skipped_count += 1
                    continue

                changed = deactivate_file(
                    file_id
                )

                log_action = "FILE_DEACTIVATED"

                description = (
                    f"File {file_id} deactivated "
                    "through bulk action."
                )

            elif action == "reactivate":

                if is_active:
                    skipped_count += 1
                    continue

                changed = reactivate_file(
                    file_id
                )

                log_action = "FILE_REACTIVATED"

                description = (
                    f"File {file_id} reactivated "
                    "through bulk action."
                )

            elif action == "delete":

                changed = delete_file(
                    file_id
                )

                log_action = "FILE_DELETED"

                description = (
                    f"File {file_id} permanently deleted "
                    "through bulk action."
                )

            else:
                failed_count += 1
                continue

            if changed:
                success_count += 1
                affected_ids.append(
                    file_id
                )

                log_admin_action(
                    admin_id=user.id,
                    action=log_action,
                    target_type="file",
                    target_id=file_id,
                    description=description,
                )
            else:
                failed_count += 1

        except Exception:
            failed_count += 1

    _clear_selected_file_ids(
        context
    )

    if action == "deactivate":
        action_name = "deactivated"

    elif action == "reactivate":
        action_name = "reactivated"

    elif action == "delete":
        action_name = "permanently deleted"

    else:
        action_name = "processed"

    summary = (
        "📦 <b>Bulk File Operation Complete</b>\n\n"
        f"Action: {action_name}\n"
        f"✅ Successful: {success_count}\n"
        f"⏭ Skipped: {skipped_count}\n"
        f"❌ Failed: {failed_count}\n"
    )

    if affected_ids:
        summary += (
            "\nAffected file IDs:\n"
            + ", ".join(
                str(file_id)
                for file_id in affected_ids
            )
        )

    await query.edit_message_text(
        summary,
        reply_markup=file_management_keyboard(),
        parse_mode="HTML",
    )

async def handle_file_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Route file-management callbacks.

    Authorization is checked independently of the dashboard.
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
            "You are not authorized to access the admin panel."
        )
        return

    await query.answer()

    data = query.data or ""

    if data == "admin:files:search":
        await start_file_search(update, context)
        return

    if data == "admin:files:search:cancel":
        await cancel_file_search(update, context)
        return

    if data.startswith("admin:files:search:page:"):
        try:
            page = int(
                data.rsplit(":", 1)[1]
            )
        except ValueError:
            await query.edit_message_text(
                "Invalid search page.",
                reply_markup=file_management_keyboard(),
            )
            return

        await show_file_search_results(
            update,
            context,
            search_query=None,
            page=page,
        )
        return

    if data == "admin:files:upload":
        await start_admin_upload(update, context)
        return

    if data == "admin:files:bulk":
        await start_bulk_upload(update, context)
        return

    if data == "admin:upload:cancel":
        await cancel_admin_upload(update, context)
        return

    if data == "admin:bulk:finish":
        await finish_bulk_upload(update, context)
        return

    if data == "admin:files":
        await show_file_management(update, context)
        return

    if data == "admin:files:list:all":
        context.user_data[
            "admin_file_selection_mode"
        ] = False

        _clear_selected_file_ids(
            context
        )

        await show_file_list(
            update,
            context,
            "all",
            0,
        )
        return

    if data == "admin:files:list:active":
        context.user_data[
            "admin_file_selection_mode"
        ] = False

        _clear_selected_file_ids(
            context
        )

        await show_file_list(
            update,
            context,
            "active",
            0,
        )
        return

    if data == "admin:files:list:inactive":
        context.user_data[
            "admin_file_selection_mode"
        ] = False

        _clear_selected_file_ids(
            context
        )

        await show_file_list(
            update,
            context,
            "inactive",
            0,
        )
        return

    if data.startswith("admin:files:page:"):
        try:
            page = int(
                data.rsplit(":", 1)[1]
            )
        except ValueError:
            await query.edit_message_text(
                "Invalid page.",
                reply_markup=file_management_keyboard(),
            )
            return

        filter_name = context.user_data.get(
            "admin_file_filter",
            "all",
        )

        await show_file_list(
            update,
            context,
            filter_name,
            page,
        )
        return

    if data == "admin:files:selection_mode":
        await enter_file_selection_mode(
            update,
            context,
        )
        return

    if data == "admin:files:details_mode":
        await exit_file_selection_mode(
            update,
            context,
        )
        return

    if data.startswith("admin:file:select:"):
        file_id = data.rsplit(":", 1)[1]

        await toggle_file_selection(
            update,
            context,
            file_id,
        )
        return

    if data == "admin:files:select_all":
        await select_all_files(
            update,
            context,
        )
        return

    if data == "admin:files:clear_selection":
        await clear_file_selection(
            update,
            context,
        )
        return

    if data == "admin:files:bulk:deactivate":
        await request_bulk_file_action_confirmation(
            update,
            context,
            "deactivate",
        )
        return

    if data == "admin:files:bulk:reactivate":
        await request_bulk_file_action_confirmation(
            update,
            context,
            "reactivate",
        )
        return

    if data == "admin:files:bulk:delete":
        await request_bulk_file_action_confirmation(
            update,
            context,
            "delete",
        )
        return

    if data.startswith("admin:files:bulk:confirm:"):
        action = data.rsplit(":", 1)[1]

        await execute_bulk_file_action(
            update,
            context,
            action,
        )
        return

    if data == "admin:files:bulk:cancel":
        await cancel_bulk_file_action(
            update,
            context,
        )
        return

    if data.startswith("admin:file:deactivate:"):
        file_id = data.rsplit(":", 1)[1]

        await request_file_action_confirmation(
            update,
            context,
            "deactivate",
            file_id,
        )
        return

    if data.startswith("admin:file:reactivate:"):
        file_id = data.rsplit(":", 1)[1]

        await request_file_action_confirmation(
            update,
            context,
            "reactivate",
            file_id,
        )
        return

    if data.startswith("admin:file:delete:"):
        file_id = data.rsplit(":", 1)[1]

        await request_file_action_confirmation(
            update,
            context,
            "delete",
            file_id,
        )
        return

    if data.startswith("admin:file:confirm:"):
        parts = data.split(":")

        if len(parts) != 5:
            await query.edit_message_text(
                "Invalid confirmation.",
                reply_markup=file_management_keyboard(),
            )
            return

        action = parts[3]
        file_id = parts[4]

        await execute_file_action(
            update,
            context,
            action,
            file_id,
        )
        return

    if data.startswith("admin:file:confirm_delete:"):
        file_id = data.rsplit(":", 1)[1]

        await execute_file_action(
            update,
            context,
            "delete",
            file_id,
        )
        return

    if data.startswith("admin:file:cancel:"):
        file_id = data.rsplit(":", 1)[1]

        await cancel_file_action(
            update,
            context,
            file_id,
        )
        return

    if data.startswith("admin:file:link:"):
        file_id = data.rsplit(":", 1)[1]

        await get_file_link(
            update,
            context,
            file_id,
        )
        return

    if data.startswith("admin:file:"):
        file_id = data.rsplit(":", 1)[1]

        await show_file_details(
            update,
            context,
            file_id,
        )
        return

    await query.edit_message_text(
        "This file-management action is invalid.",
        reply_markup=file_management_keyboard(),
    )


async def handle_file_search_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Receive the administrator's search text.
    """

    if context.user_data.get(
        "awaiting_admin_add"
    ):
        return await handle_admin_text(
            update,
            context,
        )

    if context.user_data.get(
        "awaiting_user_search"
    ):
        return await handle_user_search_text(
            update,
            context,
        )

    user = update.effective_user
    message = update.message

    if user is None or message is None:
        return

    if not context.user_data.get(
        "awaiting_file_search"
    ):
        from handlers.user import help_command

        await help_command(
            update,
            context,
        )

        return True

    if not is_authorized_admin(user.id):
        context.user_data.pop(
            "awaiting_file_search",
            None,
        )

        await message.reply_text(
            "❌ You are not authorized to search files."
        )

        return True

    search_query = message.text.strip()

    if not search_query:
        await message.reply_text(
            "Please enter a search term."
        )
        return True

    context.user_data.pop(
        "awaiting_file_search",
        None,
    )

    results = _search_files(search_query)

    context.user_data[
        "admin_file_search_query"
    ] = search_query

    context.user_data[
        "admin_file_search_results"
    ] = [
        record["id"]
        for record in results
    ]

    if not results:
        await message.reply_text(
            f"🔎 Search Results\n\n"
            f"Query: {search_query}\n\n"
            "❌ No matching files were found.\n\n"
            "Try a shorter word or another spelling.",
            reply_markup=file_search_keyboard(),
        )

        context.user_data[
            "awaiting_file_search"
        ] = True

        return True

    total_pages = (
        len(results) + PAGE_SIZE - 1
    ) // PAGE_SIZE

    await message.reply_text(
        f"🔎 Search Results\n\n"
        f"Query: {search_query}\n"
        f"Matches: {len(results)}\n"
        f"Page 1 of {total_pages}",
        reply_markup=file_search_results_keyboard(
            results,
            page=0,
            page_size=PAGE_SIZE,
        ),
    )

    return True


async def start_admin_upload(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Start the file-upload workflow from the admin dashboard.

    The actual upload/storage logic remains in handlers.files.receive_file().
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
            "You are not authorized to access the admin panel."
        )
        return

# Cancel every other interactive workflow first.

    _clear_file_search_state(context)
    _clear_selected_file_ids(context)

    context.user_data.pop(
        "admin_file_selection_mode",
        None,
    )

    context.user_data.pop(
        "awaiting_bulk_upload",
        None,
    )
    context.user_data.pop(
        "admin_bulk_upload_origin",
        None,
    )
    context.user_data.pop(
        "bulk_uploaded_count",
        None,
    )
    context.user_data.pop(
        "bulk_failed_count",
        None,
    )
    context.user_data.pop(
        "bulk_failed_files",
        None,
    )

    context.user_data["awaiting_file_upload"] = True
    context.user_data["admin_upload_origin"] = True

    await query.edit_message_text(
        "📤 <b>File Upload</b>\n\n"
        "Send the file you want to upload.\n\n"
        "Supported files can be sent as Telegram Documents "
        "(APK, ZIP, XML, etc.).\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Send only one file.\n"
        "The next document you send will be uploaded.",
        reply_markup=file_upload_keyboard(),
        parse_mode="HTML",
    )


async def cancel_admin_upload(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Cancel an active dashboard upload."""

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
            "You are not authorized to access the admin panel."
        )
        return

    context.user_data.pop("awaiting_file_upload", None)
    context.user_data.pop("admin_upload_origin", None)

    await query.answer("Upload cancelled.")

    await query.edit_message_text(
        "📁 File Management\n\nChoose an option:",
        reply_markup=file_management_keyboard(),
    )


async def start_bulk_upload(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Start bulk-upload mode.

    Each document sent while this mode is active is uploaded
    automatically. The administrator can finish the batch
    when all files have been sent.
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
            "You are not authorized to access the admin panel."
        )
        return

# Cancel every other interactive workflow first.

    _clear_file_search_state(context)
    _clear_selected_file_ids(context)

    context.user_data.pop(
        "admin_file_selection_mode",
        None,
    )

    context.user_data.pop(
        "awaiting_file_upload",
        None,
    )
    context.user_data.pop(
        "admin_upload_origin",
        None,
    )

    context.user_data.pop(
        "bulk_uploaded_count",
        None,
    )
    context.user_data.pop(
        "bulk_failed_count",
        None,
    )
    context.user_data.pop(
        "bulk_failed_files",
        None,
    )

    # Start bulk-upload state.
    context.user_data["awaiting_bulk_upload"] = True
    context.user_data["admin_bulk_upload_origin"] = True
    context.user_data["bulk_uploaded_count"] = 0
    context.user_data["bulk_failed_count"] = 0
    context.user_data["bulk_failed_files"] = []

    await query.edit_message_text(
        "📦 <b>Bulk File Upload</b>\n\n"
        "You can now send multiple files.\n\n"
        "Select all the files you want to upload in Telegram "
        "and send them here.\n\n"
        "Each file will automatically receive its own unique "
        "file key and will be added to File Management.\n\n"
        "You do not need to wait between files.\n\n"
        "When you have finished sending all files, tap "
        "<b>Finish Upload</b>.",
        reply_markup=bulk_upload_keyboard(),
        parse_mode="HTML",
    )


async def finish_bulk_upload(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Finish the current bulk-upload session."""

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
            "You are not authorized to access the admin panel."
        )
        return

    uploaded_count = context.user_data.get(
        "bulk_uploaded_count",
        0,
    )

    failed_count = context.user_data.get(
        "bulk_failed_count",
        0,
    )

    failed_files = context.user_data.get(
        "bulk_failed_files",
        [],
    )

    failure_text = ""

    if failed_files:
        failure_lines = []

        for item in failed_files:
            file_name = str(
                item["file_name"]
                or "Unnamed file"
            )

            if len(file_name) > 80:
                file_name = file_name[:77] + "..."

            file_name = html.escape(
                file_name,
                quote=False,
            )

            failure_lines.append(
                f"• {file_name}"
            )

        failure_text = (
            "\n\n❌ <b>Failed Files</b>\n"
            + "\n".join(failure_lines)
        )

    # Stop accepting additional documents.
    context.user_data.pop(
        "awaiting_bulk_upload",
        None,
    )

    context.user_data.pop(
        "admin_bulk_upload_origin",
        None,
    )

    context.user_data.pop(
        "bulk_uploaded_count",
        None,
    )

    context.user_data.pop(
        "bulk_failed_count",
        None,
    )

    context.user_data.pop(
        "bulk_failed_files",
        None,
    )

    await query.answer("Bulk upload finished.")

    await query.edit_message_text(
        "📦 <b>Bulk Upload Complete</b>\n\n"
        f"✅ Uploaded: <b>{uploaded_count}</b>\n"
        f"❌ Failed: <b>{failed_count}</b>\n\n"
        "All successfully uploaded files are now available "
        "in File Management."
        f"{failure_text}",
        reply_markup=file_management_keyboard(),
        parse_mode="HTML",
    )