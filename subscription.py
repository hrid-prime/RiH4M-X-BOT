import asyncio
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from config import CHANNELS
from database import (
    register_user,
    set_user_verified,
)

from handlers.verification_cache import _cache_verification

from keyboards.user import user_main_keyboard

from auth import is_authorized_admin

logger = logging.getLogger(__name__)


# ============================================================
# CHANNEL MEMBERSHIP CHECK
# ============================================================

class MembershipCheckError(Exception):
    """Raised when Telegram membership status cannot be determined."""
    pass


async def is_user_member(bot, channel_id, user_id):
    try:
        member = await bot.get_chat_member(
            chat_id=channel_id,
            user_id=user_id,
        )

        if member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ):
            return True

        if (
            member.status == ChatMemberStatus.RESTRICTED
            and getattr(member, "is_member", False)
        ):
            return True

        return False

    except Exception as error:
        logger.exception(
            "Could not check membership | "
            "channel=%s | user=%s",
            channel_id,
            user_id,
        )

        raise MembershipCheckError(
            f"Could not verify membership for channel {channel_id}"
        ) from error


# ============================================================
# FIND MISSING CHANNELS
# ============================================================

async def get_missing_channels(bot, user_id):
    """
    Check every required channel concurrently.

    Returns:
        A list containing every channel the user has not joined.

    Raises:
        MembershipCheckError:
            If Telegram fails to determine membership for any
            required channel.
    """

    tasks = [
        is_user_member(
            bot,
            channel["id"],
            user_id,
        )
        for channel in CHANNELS
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    for result in results:
        if isinstance(
            result,
            MembershipCheckError,
        ):
            raise result

        if isinstance(
            result,
            Exception,
        ):
            raise MembershipCheckError(
                "One or more membership checks failed."
            ) from result

    missing_channels = []

    for channel, is_member in zip(
        CHANNELS,
        results,
    ):
        if not is_member:
            missing_channels.append(channel)

    return missing_channels


# ============================================================
# CHECK ALL CHANNELS
# ============================================================

async def check_all_channels(bot, user_id):
    """
    Returns True only when the user has joined
    every required channel.
    """

    missing_channels = await get_missing_channels(
        bot,
        user_id,
    )

    return len(missing_channels) == 0


# ============================================================
# VERIFICATION KEYBOARD
# ============================================================

def verification_keyboard(missing_channels=None):
    """
    Create the verification keyboard.

    Channels are displayed in three fixed pairs:

        Channel 1 | Channel 2
        Channel 3 | Channel 4
        Channel 5 | Channel 6

    If both channels in a pair are missing:
        They appear side-by-side.

    If only one channel in a pair is missing:
        That channel gets its own full-width row.

    If neither channel is missing:
        That row disappears.

    This keeps the original channel order and prevents
    the remaining buttons from being unnecessarily
    re-packed into different pairs.
    """

    channels_to_show = (
        missing_channels
        if missing_channels is not None
        else CHANNELS
    )

    # --------------------------------------------------------
    # FAST LOOKUP OF THE CURRENTLY MISSING CHANNELS
    # --------------------------------------------------------

    missing_ids = {
        channel["id"]
        for channel in channels_to_show
    }

    buttons = []

    # --------------------------------------------------------
    # BUILD THE THREE FIXED CHANNEL PAIRS
    # --------------------------------------------------------

    for index in range(
        0,
        len(CHANNELS),
        2,
    ):
        left_channel = CHANNELS[index]

        right_channel = (
            CHANNELS[index + 1]
            if index + 1 < len(CHANNELS)
            else None
        )

        left_missing = (
            left_channel["id"]
            in missing_ids
        )

        right_missing = (
            right_channel is not None
            and right_channel["id"]
            in missing_ids
        )

        # ----------------------------------------------------
        # BOTH CHANNELS ARE MISSING
        # ----------------------------------------------------

        if left_missing and right_missing:
            buttons.append([
                InlineKeyboardButton(
                    f"📢 {left_channel['name']}",
                    url=left_channel["url"],
                ),
                InlineKeyboardButton(
                    f"📢 {right_channel['name']}",
                    url=right_channel["url"],
                ),
            ])

        # ----------------------------------------------------
        # ONLY LEFT CHANNEL IS MISSING
        # ----------------------------------------------------

        elif left_missing:
            buttons.append([
                InlineKeyboardButton(
                    f"📢 {left_channel['name']}",
                    url=left_channel["url"],
                )
            ])

        # ----------------------------------------------------
        # ONLY RIGHT CHANNEL IS MISSING
        # ----------------------------------------------------

        elif right_missing:
            buttons.append([
                InlineKeyboardButton(
                    f"📢 {right_channel['name']}",
                    url=right_channel["url"],
                )
            ])

        # ----------------------------------------------------
        # NEITHER CHANNEL IS MISSING
        # ----------------------------------------------------

        # No button is added for this pair.

    # --------------------------------------------------------
    # VERIFY BUTTON
    # --------------------------------------------------------

    buttons.append([
        InlineKeyboardButton(
            "✅ Verify",
            callback_data="verify_subscription",
        )
    ])

    return InlineKeyboardMarkup(buttons)


# ============================================================
# VERIFICATION MESSAGE
# ============================================================

async def send_verification_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    missing_channels=None,
):
    """
    Send or update the verification screen.

    For normal messages:
        Sends a new message.

    For callback queries:
        Edits the existing verification message.
    """

    # --------------------------------------------------------
    # NO SPECIFIC MISSING CHANNELS
    # --------------------------------------------------------

    if missing_channels is None:
        text = (
            "╔═════════════════════════╗\n"
            "                     🔐 𝗩𝗘𝗥𝗜𝗙𝗜𝗖𝗔𝗧𝗜𝗢𝗡\n"
            "╚═════════════════════════╝\n\n"
            "🔒 𝗔𝗰𝗰𝗲𝘀𝘀 𝗿𝗲𝗾𝘂𝗶𝗿𝗲𝘀 𝗮 𝗾𝘂𝗶𝗰𝗸 𝘀𝘁𝗲𝗽\n\n"
            "Join all 6 required channels below\n"
            "to unlock the bot.\n\n"
            "① Join all 6 channels\n\n"
            "② Tap <b>✅ Verify</b>\n\n"
            "③ Get instant access\n\n"
            "✨ That's it! You're ready to go.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "           📌 All 6 channels are required\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    # --------------------------------------------------------
    # SPECIFIC MISSING CHANNELS
    # --------------------------------------------------------

    elif len(missing_channels) > 0:

        if len(missing_channels) == 1:
            text = (
                "╔═════════════════════════╗\n"
                "                   ⚠️ 𝗔𝗟𝗠𝗢𝗦𝗧 𝗧𝗛𝗘𝗥𝗘\n"
                "╚═════════════════════════╝\n\n"
                "You're missing just 1 required channel:\n\n"
                f"📢 {missing_channels[0]['name']}\n\n"
                "① Join the channel above\n\n"
                "② Tap <b>✅ Verify</b> again\n\n"
                "③ Your access will be unlocked\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "   📌 All required channels must be joined\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

        else:
            text = (
                "╔═════════════════════════╗\n"
                "               ⚠️ 𝗠𝗜𝗦𝗦𝗜𝗡𝗚 𝗖𝗛𝗔𝗡𝗡𝗘𝗟𝗦\n"
                "╚═════════════════════════╝\n\n"
                f"{len(missing_channels)} required channels are still missing:\n\n"
            )

            for channel in missing_channels:
                text += f"📢 {channel['name']}\n\n"

            text += (
                "\n① Join the channels above\n\n"
                "② Tap <b>✅ Verify</b> again\n\n"
                "③ Get access once everything is complete\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "   📌 All required channels must be joined\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )

    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------

    else:
        return

    keyboard = verification_keyboard(
        missing_channels
    )

    # --------------------------------------------------------
    # CALLBACK QUERY
    # --------------------------------------------------------

    if update.callback_query:
        message = update.callback_query.message

        if message:
            await message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )

        return

    # --------------------------------------------------------
    # NORMAL MESSAGE
    # --------------------------------------------------------

    if update.message:
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
    
            return


# ============================================================
# VERIFY BUTTON CALLBACK
# ============================================================

async def verify_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    user = query.from_user

    register_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
    )

    # --------------------------------------------------------
    # CHECK EVERY CHANNEL
    # --------------------------------------------------------

    try:
        missing_channels = await get_missing_channels(
            context.bot,
            user.id,
        )

    except MembershipCheckError:
        await query.answer(
            "⚠️ Telegram membership verification failed. "
            "Please try again in a moment.",
            show_alert=True,
        )

        logger.warning(
            "Verification could not be completed | user_id=%s",
            user.id,
        )

        return

    # --------------------------------------------------------
    # ALL CHANNELS JOINED
    # --------------------------------------------------------

    if not missing_channels:

        set_user_verified(
            user.id,
            True,
        )

        _cache_verification(
            user.id
        )

        await query.answer(
            "✅ Verification successful!"
        )

        # ----------------------------------------------------
        # REMOVE THE OLD VERIFICATION MESSAGE
        # ----------------------------------------------------
        #
        # Reply keyboards cannot be attached to an already
        # existing message through edit_text().
        #
        # Therefore, remove the old verification message and
        # send the successful verification message as a new
        # message with the persistent user/admin keyboard.
        # ----------------------------------------------------

        if query.message:
            chat_id = query.message.chat_id

            await query.message.delete()

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "╔═════════════════════════╗\n"
                    "                   🎉 𝗬𝗢𝗨'𝗥𝗘 𝗔𝗟𝗟 𝗦𝗘𝗧\n"
                    "╚═════════════════════════╝\n\n"
                    "✅ All required channels verified.\n\n"
                    "🚀 Your access is now unlocked.\n"
                    "You can start using the bot right away.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "  ✨ Welcome to ᯓ 𝐑𝐎𝐗𝐘 𝐄𝐃𝐈𝐓𝐙 𝐁𝐎𝐓 𓃵\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                parse_mode="HTML",
                reply_markup=user_main_keyboard(
                    is_admin=is_authorized_admin(
                        user.id
                    )
                ),
            )

        logger.info(
            "User verified | user_id=%s",
            user.id,
        )

        return

    # --------------------------------------------------------
    # CHANNELS STILL MISSING
    # --------------------------------------------------------

    set_user_verified(
        user.id,
        False,
    )

    # Build readable alert
    if len(missing_channels) == 1:
        alert_text = (
            "⚠️ One channel is still missing:\n"
            f"📢 {missing_channels[0]['name']}"
        )

    else:
        alert_text = (
            f"⚠️ {len(missing_channels)} channels are still missing."
        )

    # Answer callback ONCE
    await query.answer(
        alert_text,
        show_alert=True,
    )

    # Show exactly what is missing
    await send_verification_message(
        update,
        context,
        missing_channels=missing_channels,
    )

    logger.info(
        "Verification failed | user_id=%s | missing=%s",
        user.id,
        len(missing_channels),
    )