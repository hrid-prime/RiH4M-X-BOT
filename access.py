import logging

from database import (
    ensure_user,
    is_user_blocked,
    is_user_verified,
    block_user,
    unblock_user,
    reset_user_verification,
)

from auth import is_authorized_owner

from .subscription import (
    check_all_channels,
    send_verification_message,
    MembershipCheckError,
)

from .verification_cache import (
    _get_cached_verification,
    _cache_verification,
    clear_verification_cache,
)

logger = logging.getLogger(__name__)


# ============================================================
# BANNED MESSAGE
# ============================================================

async def send_banned_message(update):
    message = (
        "╔═════════════════════════╗\n"
        "                🚫 𝗔𝗖𝗖𝗘𝗦𝗦 𝗕𝗟𝗢𝗖𝗞𝗘𝗗\n"
        "╚═════════════════════════╝\n\n"
        "⚠️ 𝗬𝗼𝘂 𝗵𝗮𝘃𝗲 𝗯𝗲𝗲𝗻 𝗯𝗮𝗻𝗻𝗲𝗱 from using this bot.\n\n"
        "❌ Leaving even one or more required channel results in an immediate ban.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "       📌 Your access is currently blocked \n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    if update.callback_query:
        await update.callback_query.answer(
            "🚫 You are banned from using this bot.",
            show_alert=True,
        )

        await update.callback_query.message.reply_text(
            message
        )

    elif update.message:
        await update.message.reply_text(
            message
        )


# ============================================================
# CENTRAL ACCESS CHECK
# ============================================================

async def check_user_access(update, context):
    """
    Central access-control system.

    All users, including the owner, must be verified
    before they can use the bot.

    Owner:
        Must remain subscribed to all required channels,
        but is never banned for leaving a required channel.

    Normal verified users:
        If they leave a required channel, they are blocked.

    Returns:
        True  -> user may continue
        False -> stop processing
    """

    user = update.effective_user

    if user is None:
        return False

    user_id = user.id

    # --------------------------------------------------------
    # REGISTER / UPDATE USER
    # --------------------------------------------------------

    ensure_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
    )

    # --------------------------------------------------------
    # 1. EXISTING BAN
    # --------------------------------------------------------

    if is_user_blocked(user_id):

        # The owner can never remain blocked.
        # If an old database state marked the owner as blocked,
        # repair it immediately and require verification again.
        if is_authorized_owner(user_id):
            unblock_user(user_id)

        else:
            clear_verification_cache(user_id)

            await send_banned_message(update)

            logger.info(
                "Blocked user attempted to use bot | "
                "user_id=%s",
                user_id,
            )

            return False

    # --------------------------------------------------------
    # 2. UNVERIFIED USERS
    # --------------------------------------------------------

    if not is_user_verified(user_id):

        # The Verify button itself must always perform
        # a fresh membership check.
        if (
            update.callback_query
            and update.callback_query.data
            == "verify_subscription"
        ):
            return True

        await send_verification_message(
            update,
            context,
        )

        logger.info(
            "Unverified user attempted restricted action | "
            "user_id=%s",
            user_id,
        )

        return False

    # --------------------------------------------------------
    # 3. VALID VERIFICATION CACHE
    # --------------------------------------------------------

    if _get_cached_verification(user_id):
        return True

    # --------------------------------------------------------
    # 4. CACHE EXPIRED / NOT PRESENT
    #
    # Perform a fresh six-channel membership check.
    # --------------------------------------------------------

    try:
        still_subscribed = await check_all_channels(
            context.bot,
            user_id,
        )

    except MembershipCheckError:
        clear_verification_cache(user_id)

        logger.warning(
            "Membership check failed; user was not banned | "
            "user_id=%s",
            user_id,
        )

        await update.effective_message.reply_text(
            "⚠️ I couldn't verify your channel membership right now.\n\n"
            "Please try again in a moment."
        )

        return False

    if still_subscribed:
        _cache_verification(user_id)

        return True

    # --------------------------------------------------------
    # 5. VERIFIED USER LEFT A REQUIRED CHANNEL
    # --------------------------------------------------------

    clear_verification_cache(user_id)

    # --------------------------------------------------------
    # OWNER SPECIAL RULE
    #
    # The owner must re-verify, but is never banned.
    # --------------------------------------------------------

    if is_authorized_owner(user_id):

        reset_user_verification(user_id)

        logger.info(
            "Owner left a required channel; verification reset | "
            "user_id=%s",
            user_id,
        )

        await send_verification_message(
            update,
            context,
        )

        return False

    # --------------------------------------------------------
    # NORMAL USER
    #
    # A normal verified user who leaves a required channel
    # is blocked.
    # --------------------------------------------------------

    block_user(
        user_id,
        reason="LEFT_REQUIRED_CHANNEL",
    )

    logger.warning(
        "Verified user banned for leaving required channel | "
        "user_id=%s",
        user_id,
    )

    await send_banned_message(update)

    return False