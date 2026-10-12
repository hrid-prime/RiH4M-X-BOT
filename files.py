import html
import logging

import re

from telegram import Update
from telegram.ext import ContextTypes

from auth import is_authorized_admin

from database import (
    create_file,
    generate_file_key,
    log_admin_action,
    get_file_by_key,
    increment_file_download_count,
    increment_download_count,
)

from keyboards.admin import file_management_keyboard

logger = logging.getLogger(__name__)

def is_valid_file_key(file_key: str) -> bool:
    if not isinstance(file_key, str):
        return False

    return re.fullmatch(r"file_[1-9][0-9]*", file_key) is not None

async def upload_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    if user is None or update.message is None:
        return

    if not is_authorized_admin(user.id):
        await update.message.reply_text(
            "❌ You are not authorized to use the admin upload system."
        )

        if user is not None:
            log_admin_action(
                admin_id=user.id,
                action="UNAUTHORIZED_ADMIN_ATTEMPT",
                target_type="FILE",
                target_id=None,
                description="Unauthorized user attempted to access /upload",
            )

        return

# /upload starts a fresh single-upload workflow.

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

    context.user_data["awaiting_file_upload"] = True

    await update.message.reply_text(
        "📤 <b>File Upload</b>\n\n"
        "Send the file you want to upload.\n\n"
        "Supported files can be sent as Telegram Documents "
        "(APK, ZIP, XML, etc.).\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Send only one file.\n"
        "The next document you send will be uploaded.",
        parse_mode="HTML",
    )


async def receive_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    if user is None or update.message is None:
        return

    if context.user_data.get("awaiting_bulk_upload"):
        await receive_bulk_file(
            update,
            context,
        )
        return

    if not context.user_data.get("awaiting_file_upload"):
        return

    if not is_authorized_admin(user.id):
        context.user_data.pop("awaiting_file_upload", None)
        context.user_data.pop("admin_upload_origin", None)

        await update.message.reply_text(
            "❌ You are not authorized to upload files."
        )
        return

    document = update.message.document

    if document is None:
        return

    try:
        file_key = generate_file_key()

        file_db_id = create_file(
            file_key=file_key,
            file_id=document.file_id,
            file_type="document",
            file_name=document.file_name,
            caption=update.message.caption,
            file_size=document.file_size,
            uploaded_by=user.id,
        )

        bot_username = context.bot.username

        if not bot_username:
            bot_info = await context.bot.get_me()
            bot_username = bot_info.username

        deep_link = (
            f"https://t.me/{bot_username}?start={file_key}"
        )

        log_admin_action(
            admin_id=user.id,
            action="FILE_UPLOADED",
            target_type="FILE",
            target_id=file_db_id,
            description=(
                f"Uploaded file '{document.file_name}' "
                f"with key {file_key}"
            ),
        )

        log_admin_action(
            admin_id=user.id,
            action="FILE_LINK_GENERATED",
            target_type="FILE",
            target_id=file_db_id,
            description=(
                f"Generated deep link for {file_key}"
            ),
        )

        context.user_data.pop("awaiting_file_upload", None)

        await update.message.reply_text(
            "╔════════════════════╗\n"
            "       ✅ UPLOADED\n"
            "╚════════════════════╝\n\n"
            f"📄 <b>File:</b> {html.escape(str(document.file_name or 'Unnamed file'), quote=False)}\n"
            f"🆔 <b>Key:</b> <code>{file_key}</code>\n"
            f"💾 <b>Size:</b> {document.file_size or 0:,} bytes\n\n"
            "🔗 <b>Download Link:</b>\n"
            f"<code>{deep_link}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "The file has been saved successfully.",
                        parse_mode="HTML",
                        reply_markup=(
                file_management_keyboard()
                if context.user_data.get("admin_upload_origin")
                else None
            ),
        )

        context.user_data.pop("admin_upload_origin", None)

        logger.info(
            "File uploaded | admin_id=%s | file_id=%s | key=%s",
            user.id,
            file_db_id,
            file_key,
        )

    except Exception:
        logger.exception(
            "Failed to upload file | admin_id=%s",
            user.id,
        )

        context.user_data.pop("awaiting_file_upload", None)

        context.user_data.pop("admin_upload_origin", None)

        await update.message.reply_text(
            "❌ <b>Upload failed.</b>\n\n"
            "The file could not be saved to the database.\n"
            "Please try again.",
            parse_mode="HTML",
        )

async def receive_bulk_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Receive and store one file during bulk-upload mode.

    Telegram sends multi-selected files as individual document
    messages, so this function is called once per file.
    """

    user = update.effective_user

    if user is None or update.message is None:
        return

    if not context.user_data.get(
        "awaiting_bulk_upload"
    ):
        return

    if not is_authorized_admin(user.id):
        context.user_data.pop(
            "awaiting_bulk_upload",
            None,
        )

        context.user_data.pop(
            "admin_bulk_upload_origin",
            None,
        )

        await update.message.reply_text(
            "❌ You are not authorized to upload files."
        )

        return

    document = update.message.document

    if document is None:
        # Ignore ordinary text/photos/etc. while bulk mode is active.
        return

    try:
        file_key = generate_file_key()

        file_db_id = create_file(
            file_key=file_key,
            file_id=document.file_id,
            file_type="document",
            file_name=document.file_name,
            caption=update.message.caption,
            file_size=document.file_size,
            uploaded_by=user.id,
        )

        log_admin_action(
            admin_id=user.id,
            action="FILE_UPLOADED",
            target_type="FILE",
            target_id=file_db_id,
            description=(
                f"Bulk uploaded file "
                f"'{document.file_name}' "
                f"with key {file_key}"
            ),
        )

        uploaded_count = context.user_data.get(
            "bulk_uploaded_count",
            0,
        )

        context.user_data[
            "bulk_uploaded_count"
        ] = uploaded_count + 1

        logger.info(
            "Bulk file uploaded | "
            "admin_id=%s | database_id=%s | key=%s | "
            "file_name=%s | bulk_count=%s",
            user.id,
            file_db_id,
            file_key,
            document.file_name,
            uploaded_count + 1,
        )

    except Exception as error:
        logger.exception(
            "Bulk file upload failed | admin_id=%s | file_name=%s",
            user.id,
            document.file_name,
        )

        failed_count = context.user_data.get(
            "bulk_failed_count",
            0,
        )

        context.user_data[
            "bulk_failed_count"
        ] = failed_count + 1

        failed_files = context.user_data.get(
            "bulk_failed_files",
            [],
        )

        failed_files.append(
            {
                "file_name": document.file_name or "Unnamed file",
                "error": str(error),
            }
        )

        context.user_data[
            "bulk_failed_files"
        ] = failed_files

        # Do not stop the entire batch because one file failed.
        # The remaining files can continue uploading.

async def deliver_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_key: str,
):
    user = update.effective_user

    if user is None or update.message is None:
        return

    # --------------------------------------------------------
    # Validate file key
    # --------------------------------------------------------

    if not is_valid_file_key(file_key):
        await update.message.reply_text(
            "❌ Invalid file link."
        )
        return

    # --------------------------------------------------------
    # Look up active file
    # --------------------------------------------------------

    file_record = get_file_by_key(file_key)

    if file_record is None:
        await update.message.reply_text(
            "╔════════════════════╗\n"
            "       ❌ FILE NOT FOUND\n"
            "╚════════════════════╝\n\n"
            "This file does not exist or is no longer available."
        )
        return

    database_file_id = file_record["id"]
    telegram_file_id = file_record["file_id"]
    file_name = file_record["file_name"]
    caption = file_record["caption"]

    # --------------------------------------------------------
    # Validate database record
    # --------------------------------------------------------

    if not telegram_file_id:
        logger.error(
            "File record has no Telegram file_id | "
            "file_key=%s | database_id=%s",
            file_key,
            database_file_id,
        )

        await update.message.reply_text(
            "❌ <b>File unavailable.</b>\n\n"
            "This file record is incomplete.",
            parse_mode="HTML",
        )
        return

    # --------------------------------------------------------
    # Deliver file
    # --------------------------------------------------------

    try:
        await update.message.reply_document(
            document=telegram_file_id,
            caption=caption,
        )

    except Exception as error:
        logger.exception(
            "File delivery failed | "
            "user_id=%s | file_key=%s | database_id=%s | "
            "file_name=%s | error=%s",
            user.id,
            file_key,
            database_file_id,
            file_name,
            error,
        )

        await update.message.reply_text(
            "❌ <b>File delivery failed.</b>\n\n"
            "The file could not be sent right now.\n"
            "Please try again later.",
            parse_mode="HTML",
        )
        return

    # --------------------------------------------------------
    # Count successful download
    # --------------------------------------------------------

    try:
        increment_download_count(user.id)
        increment_file_download_count(database_file_id)

    except Exception:
        logger.exception(
            "File was delivered but download counter update failed | "
            "user_id=%s | file_key=%s | database_id=%s",
            user.id,
            file_key,
            database_file_id,
        )

    logger.info(
        "File delivered successfully | "
        "user_id=%s | file_key=%s | database_id=%s | "
        "file_name=%s",
        user.id,
        file_key,
        database_file_id,
        file_name,
    )