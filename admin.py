from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_keyboard() -> InlineKeyboardMarkup:
    """Main administrator dashboard keyboard."""

    keyboard = [
        [
            InlineKeyboardButton(
                "📁 File Management",
                callback_data="admin:files",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 User Management",
                callback_data="admin:users",
            ),
        ],
        [
            InlineKeyboardButton(
                "👑 Admin Management",
                callback_data="admin:admins",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def file_management_keyboard() -> InlineKeyboardMarkup:
    """Main file-management menu."""

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Upload File",
                callback_data="admin:files:upload",
            ),
            InlineKeyboardButton(
                "📦 Bulk Upload",
                callback_data="admin:files:bulk",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔎 Search Files",
                callback_data="admin:files:search",
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 All Files",
                callback_data="admin:files:list:all",
            ),
        ],
        [
            InlineKeyboardButton(
                "🟢 Active Files",
                callback_data="admin:files:list:active",
            ),
            InlineKeyboardButton(
                "🔴 Inactive Files",
                callback_data="admin:files:list:inactive",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="admin:back",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def file_upload_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown while waiting for an uploaded file."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "❌ Cancel Upload",
                    callback_data="admin:upload:cancel",
                ),
            ],
        ]
    )

def bulk_upload_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Finish Upload",
                    callback_data="admin:bulk:finish",
                )
            ],
        ]
    )

def file_search_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown while waiting for a file-search query."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "❌ Cancel Search",
                    callback_data="admin:files:search:cancel",
                ),
            ],
        ]
    )


def file_list_keyboard(
    files,
    page=0,
    page_size=10,
    selected_ids=None,
    selection_mode=False,
    filter_name="all",
) -> InlineKeyboardMarkup:
    """
    Build the keyboard for the normal file-management list.

    Details mode:
        Clicking a file opens its details.

    Selection mode:
        Clicking a file selects/deselects it.
    """

    if selected_ids is None:
        selected_ids = set()

    keyboard = []

    start = page * page_size
    page_files = files[start:start + page_size]

    for file_record in page_files:
        file_id = file_record["id"]
        file_name = (
            file_record["file_name"]
            or "Unnamed file"
        )

        if selection_mode:
            if file_id in selected_ids:
                prefix = "☑️"
            else:
                prefix = "☐"

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{prefix} {file_name}",
                        callback_data=(
                            f"admin:file:select:{file_id}"
                        ),
                    )
                ]
            )

        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📄 {file_name}",
                        callback_data=(
                            f"admin:file:{file_id}"
                        ),
                    )
                ]
            )

    if selection_mode:
        selected_count = len(selected_ids)

        keyboard.append(
            [
                InlineKeyboardButton(
                    "☑️ Select All",
                    callback_data=(
                        "admin:files:select_all"
                    ),
                ),
                InlineKeyboardButton(
                    "⬜ Clear Selection",
                    callback_data=(
                        "admin:files:clear_selection"
                    ),
                ),
            ]
        )

        if selected_count:
            if filter_name in ("all", "active"):
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"🔴 Deactivate ({selected_count})",
                            callback_data=(
                                "admin:files:bulk:deactivate"
                            ),
                        )
                    ]
                )

            if filter_name in ("all", "inactive"):
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"🟢 Reactivate ({selected_count})",
                            callback_data=(
                                "admin:files:bulk:reactivate"
                            ),
                        )
                    ]
                )

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🗑 Delete ({selected_count})",
                        callback_data=(
                            "admin:files:bulk:delete"
                        ),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "↩️ Details Mode",
                    callback_data=(
                        "admin:files:details_mode"
                    ),
                )
            ]
        )

    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "☑️ Selection Mode",
                    callback_data=(
                        "admin:files:selection_mode"
                    ),
                )
            ]
        )

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=(
                    f"admin:files:page:{page - 1}"
                ),
            )
        )

    if start + page_size < len(files):
        navigation.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=(
                    f"admin:files:page:{page + 1}"
                ),
            )
        )

    if navigation:
        keyboard.append(navigation)

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="admin:files",
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def file_search_results_keyboard(
    files,
    page=0,
    page_size=10,
    selected_ids=None,
    selection_mode=False,
) -> InlineKeyboardMarkup:
    """
    Build the keyboard for file-search results.

    Details mode:
        Clicking a file opens its details.

    Selection mode:
        Clicking a file selects/deselects it.
    """

    if selected_ids is None:
        selected_ids = set()

    keyboard = []

    start = page * page_size
    page_files = files[start:start + page_size]

    for file_record in page_files:
        file_id = file_record["id"]
        file_name = (
            file_record["file_name"]
            or "Unnamed file"
        )

        is_active = bool(
            file_record["is_active"]
        )

        status = "🟢" if is_active else "🔴"

        if selection_mode:
            if file_id in selected_ids:
                prefix = "☑️"
            else:
                prefix = "☐"

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{prefix} {status} {file_name}",
                        callback_data=(
                            f"admin:file:select:{file_id}"
                        ),
                    )
                ]
            )

        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{status} 📄 {file_name}",
                        callback_data=(
                            f"admin:file:{file_id}"
                        ),
                    )
                ]
            )

    if selection_mode:
        selected_count = len(selected_ids)

        keyboard.append(
            [
                InlineKeyboardButton(
                    "☑️ Select All",
                    callback_data=(
                        "admin:files:select_all"
                    ),
                ),
                InlineKeyboardButton(
                    "⬜ Clear Selection",
                    callback_data=(
                        "admin:files:clear_selection"
                    ),
                ),
            ]
        )

        if selected_count:
            # Search results can contain both active
            # and inactive files, so both actions are
            # potentially relevant.
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🔴 Deactivate ({selected_count})",
                        callback_data=(
                            "admin:files:bulk:deactivate"
                        ),
                    ),
                    InlineKeyboardButton(
                        f"🟢 Reactivate ({selected_count})",
                        callback_data=(
                            "admin:files:bulk:reactivate"
                        ),
                    ),
                ]
            )

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🗑 Delete ({selected_count})",
                        callback_data=(
                            "admin:files:bulk:delete"
                        ),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "↩️ Details Mode",
                    callback_data=(
                        "admin:files:details_mode"
                    ),
                )
            ]
        )

    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "☑️ Selection Mode",
                    callback_data=(
                        "admin:files:selection_mode"
                    ),
                )
            ]
        )

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=(
                    f"admin:files:search:page:{page - 1}"
                ),
            )
        )

    if start + page_size < len(files):
        navigation.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=(
                    f"admin:files:search:page:{page + 1}"
                ),
            )
        )

    if navigation:
        keyboard.append(navigation)

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔎 New Search",
                callback_data="admin:files:search",
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ File Management",
                callback_data="admin:files",
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def file_details_keyboard(
    file_id,
    is_active,
) -> InlineKeyboardMarkup:
    """Keyboard for an individual file."""

    keyboard = []

    if is_active:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔴 Deactivate",
                    callback_data=f"admin:file:deactivate:{file_id}",
                )
            ]
        )
    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🟢 Reactivate",
                    callback_data=f"admin:file:reactivate:{file_id}",
                )
            ]
        )

    # Permanent delete button
    keyboard.append(
        [
            InlineKeyboardButton(
                "🗑 Delete Permanently",
                callback_data=f"admin:file:delete:{file_id}",
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔗 Get Link",
                callback_data=f"admin:file:link:{file_id}",
            )
        ]
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Back to Files",
                callback_data="admin:files:list:all",
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def file_confirmation_keyboard(
    action,
    file_id,
) -> InlineKeyboardMarkup:
    """Confirmation keyboard for file actions."""

    if action == "delete":
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🗑 Yes, Delete Permanently",
                        callback_data=(
                            f"admin:file:confirm_delete:{file_id}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data=(
                            f"admin:file:cancel:{file_id}"
                        ),
                    )
                ],
            ]
        )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Confirm",
                    callback_data=(
                        f"admin:file:confirm:{action}:{file_id}"
                    ),
                ),
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=(
                        f"admin:file:cancel:{file_id}"
                    ),
                ),
            ],
        ]
    )

def file_bulk_confirmation_keyboard(
    action,
) -> InlineKeyboardMarkup:
    """Confirmation keyboard for bulk file actions."""

    if action == "delete":
        confirm_text = "🗑 Yes, Delete All Permanently"
    elif action == "deactivate":
        confirm_text = "🔴 Yes, Deactivate All"
    elif action == "reactivate":
        confirm_text = "🟢 Yes, Reactivate All"
    else:
        confirm_text = "✅ Confirm"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    confirm_text,
                    callback_data=f"admin:files:bulk:confirm:{action}",
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="admin:files:bulk:cancel",
                )
            ],
        ]
    )

# ============================================================
# USER MANAGEMENT
# ============================================================

def user_management_keyboard() -> InlineKeyboardMarkup:
    """Main user-management menu."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👥 All Users",
                    callback_data="admin:users:list",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔎 Search Users",
                    callback_data="admin:users:search",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="admin:back",
                ),
            ],
        ]
    )


def user_status_keyboard() -> InlineKeyboardMarkup:
    """
    User-status filter menu.

    All Users opens this menu before displaying
    Active or Blocked users.
    """

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🟢 Active Users",
                    callback_data="admin:users:list:active",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔴 Blocked Users",
                    callback_data="admin:users:list:blocked",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ User Management",
                    callback_data="admin:users",
                ),
            ],
        ]
    )


def user_search_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown while waiting for a user-search query."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "❌ Cancel Search",
                    callback_data="admin:users:search:cancel",
                ),
            ],
        ]
    )


def user_list_keyboard(
    users,
    page=0,
    page_size=10,
    total_users=None,
    search_mode=False,
    filter_name="active",
    selected_ids=None,
    selection_mode=False,
) -> InlineKeyboardMarkup:
    """
    Build the paginated user list keyboard.

    Details mode:
        Clicking a user opens the user's details.

    Selection mode:
        Clicking a user selects/deselects that user.

    Search results intentionally remain in Details Mode only.
    """

    if selected_ids is None:
        selected_ids = set()

    keyboard = []

    start = page * page_size
    page_users = users[start:start + page_size]

    for user in page_users:
        user_id = user["user_id"]

        first_name = (
            user["first_name"]
            or "Unknown"
        )

        username = user["username"]

        is_blocked = bool(
            user["is_blocked"]
        )

        status_icon = (
            "🔴"
            if is_blocked
            else "🟢"
        )

        if username:
            label = (
                f"{status_icon} "
                f"{first_name} "
                f"(@{username})"
            )
        else:
            label = (
                f"{status_icon} "
                f"{first_name}"
            )

        if selection_mode and not search_mode:
            if user_id in selected_ids:
                prefix = "☑️"
            else:
                prefix = "☐"

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{prefix} {label}",
                        callback_data=(
                            f"admin:user:select:{user_id}"
                        ),
                    )
                ]
            )

        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"👤 {label}",
                        callback_data=(
                            f"admin:user:{user_id}"
                        ),
                    )
                ]
            )

    total_pages = max(
        1,
        (
            total_users + page_size - 1
        ) // page_size,
    )

    # --------------------------------------------------------
    # Selection controls
    # --------------------------------------------------------

    if selection_mode and not search_mode:

        selected_count = len(
            selected_ids
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "☑️ Select All",
                    callback_data=(
                        "admin:users:select_all"
                    ),
                ),
                InlineKeyboardButton(
                    "⬜ Clear Selection",
                    callback_data=(
                        "admin:users:clear_selection"
                    ),
                ),
            ]
        )

        if selected_count:
            if filter_name == "active":
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"🔴 Block ({selected_count})",
                            callback_data=(
                                "admin:users:bulk:block"
                            ),
                        )
                    ]
                )

            elif filter_name == "blocked":
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"🟢 Unblock ({selected_count})",
                            callback_data=(
                                "admin:users:bulk:unblock"
                            ),
                        )
                    ]
                )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "↩️ Details Mode",
                    callback_data=(
                        "admin:users:details_mode"
                    ),
                )
            ]
        )

    else:
        if not search_mode:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "☑️ Selection Mode",
                        callback_data=(
                            "admin:users:selection_mode"
                        ),
                    )
                ]
            )

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=(
                    f"admin:users:page:{page - 1}"
                ),
            )
        )

    if start + page_size < total_users:
        navigation.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=(
                    f"admin:users:page:{page + 1}"
                ),
            )
        )

    if navigation:
        keyboard.append(navigation)

    # --------------------------------------------------------
    # Bottom navigation
    # --------------------------------------------------------

    if search_mode:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔎 New Search",
                    callback_data=(
                        "admin:users:search"
                    ),
                )
            ]
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "⬅️ User Management",
                    callback_data=(
                        "admin:users"
                    ),
                )
            ]
        )

    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔄 Change User Status",
                    callback_data=(
                        "admin:users:list"
                    ),
                )
            ]
        )

    return InlineKeyboardMarkup(
        keyboard
    )


def user_details_keyboard(
    user_id,
    is_blocked,
) -> InlineKeyboardMarkup:
    """Keyboard for an individual user."""

    keyboard = []

    if is_blocked:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🟢 Unblock User",
                    callback_data=(
                        f"admin:user:unblock:{user_id}"
                    ),
                )
            ]
        )
    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔴 Block User",
                    callback_data=(
                        f"admin:user:block:{user_id}"
                    ),
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Back to Users",
                callback_data=(
                    "admin:users:list"
                ),
            )
        ]
    )

    return InlineKeyboardMarkup(
        keyboard
    )


def user_action_confirmation_keyboard(
    action,
    user_id,
) -> InlineKeyboardMarkup:
    """Confirmation keyboard for individual user actions."""

    if action == "block":
        confirm_text = (
            "🔴 Yes, Block User"
        )
    elif action == "unblock":
        confirm_text = (
            "🟢 Yes, Unblock User"
        )
    else:
        confirm_text = "✅ Confirm"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    confirm_text,
                    callback_data=(
                        f"admin:user:confirm:"
                        f"{action}:{user_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=(
                        f"admin:user:cancel:"
                        f"{user_id}"
                    ),
                )
            ],
        ]
    )


def user_bulk_confirmation_keyboard(
    action,
) -> InlineKeyboardMarkup:
    """Confirmation keyboard for bulk user actions."""

    if action == "block":
        confirm_text = (
            "🔴 Yes, Block Selected Users"
        )
    elif action == "unblock":
        confirm_text = (
            "🟢 Yes, Unblock Selected Users"
        )
    else:
        confirm_text = "✅ Confirm"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    confirm_text,
                    callback_data=(
                        f"admin:users:bulk:"
                        f"confirm:{action}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=(
                        "admin:users:bulk:cancel"
                    ),
                )
            ],
        ]
    )

# ============================================================
# ADMIN MANAGEMENT
# ============================================================

def admin_management_keyboard(
    is_owner=False,
) -> InlineKeyboardMarkup:
    """
    Main Admin Management menu.

    All administrators can view the administrator list.

    Only the owner receives Add Administrator controls.
    """

    keyboard = [
        [
            InlineKeyboardButton(
                "👑 All Administrators",
                callback_data="admin:admins:list",
            ),
        ],
    ]

    if is_owner:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "➕ Add Administrator",
                    callback_data="admin:admins:add",
                ),
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="admin:back",
            ),
        ]
    )

    return InlineKeyboardMarkup(
        keyboard
    )


def admin_list_keyboard(
    admins,
    is_owner=False,
) -> InlineKeyboardMarkup:
    """
    Build the administrator list.

    Owner:
        Can see removal controls through details.

    Regular administrators:
        Can only inspect administrator details.
    """

    keyboard = []

    for admin_record in admins:
        user_id = admin_record["user_id"]
        role = admin_record["role"]

        display_name = (
            f"User ID {user_id}"
        )

        try:
            from database import get_user

            user_record = get_user(
                user_id
            )

            if user_record is not None:
                first_name = (
                    user_record["first_name"]
                    or ""
                )

                username = (
                    user_record["username"]
                )

                if first_name:
                    display_name = first_name

                if username:
                    display_name += (
                        f" (@{username})"
                    )

        except Exception:
            pass

        if role == "owner":
            prefix = "👑"
        else:
            prefix = "🛡️"

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{prefix} {display_name}",
                    callback_data=(
                        f"admin:admin:{user_id}"
                    ),
                )
            ]
        )

    if is_owner:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "➕ Add Administrator",
                    callback_data=(
                        "admin:admins:add"
                    ),
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Admin Management",
                callback_data=(
                    "admin:admins"
                ),
            )
        ]
    )

    return InlineKeyboardMarkup(
        keyboard
    )


def admin_details_keyboard(
    user_id,
    can_remove=False,
) -> InlineKeyboardMarkup:
    """
    Keyboard for administrator details.
    """

    keyboard = []

    if can_remove:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔴 Remove Administrator",
                    callback_data=(
                        f"admin:admin:"
                        f"remove:{user_id}"
                    ),
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Back to Administrators",
                callback_data=(
                    "admin:admins:list"
                ),
            )
        ]
    )

    return InlineKeyboardMarkup(
        keyboard
    )


def admin_add_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard shown while waiting for an admin ID.
    """

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=(
                        "admin:admins:add:cancel"
                    ),
                ),
            ],
        ]
    )


def admin_add_confirmation_keyboard(
    user_id,
) -> InlineKeyboardMarkup:
    """
    Confirmation keyboard for adding an administrator.
    """

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Yes, Add Administrator",
                    callback_data=(
                        f"admin:admins:add:"
                        f"confirm:{user_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=(
                        "admin:admins:add:cancel"
                    ),
                ),
            ],
        ]
    )


def admin_remove_confirmation_keyboard(
    user_id,
) -> InlineKeyboardMarkup:
    """
    Confirmation keyboard for removing an administrator.
    """

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔴 Yes, Remove Administrator",
                    callback_data=(
                        f"admin:admin:remove:"
                        f"confirm:{user_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=(
                        f"admin:admin:remove:"
                        f"cancel:{user_id}"
                    ),
                ),
            ],
        ]
    )