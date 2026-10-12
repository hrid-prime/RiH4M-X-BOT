import sqlite3
import secrets
from datetime import datetime, timezone

from config import DATABASE_PATH, OWNER_ID


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    # ========================================================
    # USERS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT NOT NULL,
            is_verified INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0
        )
    """)

    # ========================================================
    # ADMINS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL CHECK(role IN ('owner', 'admin')),
            added_at TEXT NOT NULL,
            added_by INTEGER
        )
    """)

    # ========================================================
    # ADMIN LOGS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            description TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_key TEXT NOT NULL UNIQUE,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_name TEXT,
            caption TEXT,
            file_size INTEGER,
            uploaded_by INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL,
            download_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)

    # ========================================================
    # SETTINGS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # ========================================================
    # SYNCHRONIZE OWNER WITH .ENV
    # ========================================================
    #
    # OWNER_ID from .env is the single source of truth.
    #
    # If OWNER_ID changes:
    #   - the new OWNER_ID becomes the owner
    #   - every previous owner is demoted to regular admin
    #   - there is always exactly one owner
    #
    # This makes ownership transfer automatic on startup.
    # ========================================================

    # Ensure the configured owner exists first.
    cursor.execute("""
        INSERT OR IGNORE INTO admins
        (user_id, role, added_at, added_by)
        VALUES (?, 'owner', ?, ?)
    """, (
        OWNER_ID,
        datetime.now(timezone.utc).isoformat(),
        OWNER_ID,
    ))

    # Demote every previous owner.
    # The current OWNER_ID is intentionally excluded.
    cursor.execute("""
        UPDATE admins
        SET role = 'admin'
        WHERE role = 'owner'
        AND user_id != ?
    """, (
        OWNER_ID,
    ))

    # Promote the configured OWNER_ID to owner.
    cursor.execute("""
        UPDATE admins
        SET role = 'owner'
        WHERE user_id = ?
    """, (
        OWNER_ID,
    ))

    # ========================================================
    # USER BAN SYSTEM MIGRATION
    # ========================================================

    cursor.execute("PRAGMA table_info(users)")
    existing_columns = {
        row["name"]
        for row in cursor.fetchall()
    }

    if "blocked_reason" not in existing_columns:
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN blocked_reason TEXT
        """)

    if "blocked_at" not in existing_columns:
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN blocked_at TEXT
        """)

    connection.commit()
    connection.close()


# ============================================================
# USER FUNCTIONS
# ============================================================

def register_user(user_id, username=None, first_name=None):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        username,
        first_name,
        datetime.now(timezone.utc).isoformat(),
    ))

    cursor.execute("""
        UPDATE users
        SET username = ?, first_name = ?
        WHERE user_id = ?
    """, (
        username,
        first_name,
        user_id,
    ))

    connection.commit()
    connection.close()


def ensure_user(
    user_id,
    username=None,
    first_name=None,
):
    """
    Ensure that a Telegram user exists in the database.

    If the user does not exist, create them.

    If the user already exists, update their
    current Telegram profile information.

    This function does NOT change:
        - verification status
        - block status
        - block reason
        - block time
        - download count
        - joined_at
    """

    register_user(
        user_id=user_id,
        username=username,
        first_name=first_name,
    )


def set_user_verified(user_id, verified):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET is_verified = ?
        WHERE user_id = ?
    """, (1 if verified else 0, user_id))

    connection.commit()
    connection.close()


def is_user_verified(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT is_verified
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    result = cursor.fetchone()
    connection.close()

    if result is None:
        return False

    return bool(result["is_verified"])


def get_user(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    user = cursor.fetchone()

    connection.close()

    return user


def get_user_stats():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE is_verified = 1
    """)
    verified_users = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE is_blocked = 1
    """)
    blocked_users = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(download_count), 0)
        FROM users
    """)
    total_downloads = cursor.fetchone()[0]

    connection.close()

    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "blocked_users": blocked_users,
        "total_downloads": total_downloads,
    }


def increment_download_count(user_id):
    """
    Increase a user's download count by 1.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET download_count = download_count + 1
        WHERE user_id = ?
    """, (user_id,))

    connection.commit()
    connection.close()


def get_download_count(user_id):
    """
    Return the number of downloads for a user.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT download_count
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    result = cursor.fetchone()
    connection.close()

    if result is None:
        return 0

    return result["download_count"]

def user_exists(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT 1
        FROM users
        WHERE user_id = ?
        LIMIT 1
    """, (user_id,))

    result = cursor.fetchone()
    connection.close()

    return result is not None

def get_all_users():
    """
    Return all registered users.

    Newest users are shown first.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        ORDER BY joined_at DESC
    """)

    users = cursor.fetchall()

    connection.close()

    return users


def search_users(query):
    """
    Search users by:
        - Telegram user ID
        - username
        - first name

    Partial matches are supported.
    """

    query = str(query).strip()

    if not query:
        return []

    connection = get_connection()
    cursor = connection.cursor()

    like_query = f"%{query}%"

    cursor.execute("""
        SELECT *
        FROM users
        WHERE
            CAST(user_id AS TEXT) LIKE ?
            OR LOWER(COALESCE(username, '')) LIKE LOWER(?)
            OR LOWER(COALESCE(first_name, '')) LIKE LOWER(?)
        ORDER BY joined_at DESC
    """, (
        like_query,
        like_query,
        like_query,
    ))

    users = cursor.fetchall()

    connection.close()

    return users

def reset_user_verification(user_id):
    """
    Reset a user's verification status.

    This does not block the user.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET is_verified = 0
        WHERE user_id = ?
    """, (user_id,))

    connection.commit()
    connection.close()

# ============================================================
# ADMIN FUNCTIONS
# ============================================================

def get_admin(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT user_id, role, added_at, added_by
        FROM admins
        WHERE user_id = ?
    """, (user_id,))

    admin = cursor.fetchone()

    connection.close()

    return admin


def is_admin(user_id):
    return get_admin(user_id) is not None


def is_owner(user_id):
    admin = get_admin(user_id)

    return (
        admin is not None
        and admin["role"] == "owner"
    )


def add_admin(user_id, added_by):
    if user_id == OWNER_ID:
        return False

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO admins
        (user_id, role, added_at, added_by)
        VALUES (?, 'admin', ?, ?)
    """, (
        user_id,
        datetime.now(timezone.utc).isoformat(),
        added_by,
    ))

    connection.commit()
    connection.close()

    return True


def remove_admin(user_id):
    if user_id == OWNER_ID:
        return False

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM admins
        WHERE user_id = ?
        AND role = 'admin'
    """, (user_id,))

    removed = cursor.rowcount > 0

    connection.commit()
    connection.close()

    return removed


def get_all_admins():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT user_id, role, added_at, added_by
        FROM admins
        ORDER BY
            CASE role
                WHEN 'owner' THEN 0
                ELSE 1
            END,
            added_at
    """)

    admins = cursor.fetchall()

    connection.close()

    return admins

def create_file(
    file_key,
    file_id,
    file_type,
    file_name=None,
    caption=None,
    file_size=None,
    uploaded_by=None,
):
    """
    Create a new file record.

    Returns:
        The newly created SQLite file ID.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO files (
            file_key,
            file_id,
            file_type,
            file_name,
            caption,
            file_size,
            uploaded_by,
            uploaded_at,
            download_count,
            is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
    """, (
        file_key,
        file_id,
        file_type,
        file_name,
        caption,
        file_size,
        uploaded_by,
        datetime.now(timezone.utc).isoformat(),
    ))

    file_db_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return file_db_id

def get_file_by_key(file_key):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM files
        WHERE file_key = ?
        AND is_active = 1
        LIMIT 1
        """,
        (file_key,),
    )

    file_record = cursor.fetchone()

    connection.close()

    return file_record

def get_file_by_id(file_id):
    """
    Retrieve a file using its internal database ID.

    Unlike get_file_by_key(), this also returns inactive files.
    This is useful for administration.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM files
        WHERE id = ?
    """, (file_id,))

    file_record = cursor.fetchone()

    connection.close()

    return file_record

def get_all_files(include_inactive=True):
    """
    Retrieve file records.

    If include_inactive is True:
        Return all files.

    If False:
        Return only active files.
    """

    connection = get_connection()
    cursor = connection.cursor()

    if include_inactive:
        cursor.execute("""
            SELECT *
            FROM files
            ORDER BY id DESC
        """)
    else:
        cursor.execute("""
            SELECT *
            FROM files
            WHERE is_active = 1
            ORDER BY id DESC
        """)

    files = cursor.fetchall()

    connection.close()

    return files

def increment_file_download_count(file_id):
    """
    Increase a file's successful delivery count by 1.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE files
        SET download_count = download_count + 1
        WHERE id = ?
        AND is_active = 1
    """, (file_id,))

    connection.commit()
    connection.close()

def deactivate_file(file_id):
    """
    Soft-delete a file.

    The database record is preserved,
    but the file can no longer be requested
    through a deep link.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE files
        SET is_active = 0
        WHERE id = ?
    """, (file_id,))

    deactivated = cursor.rowcount > 0

    connection.commit()
    connection.close()

    return deactivated

def reactivate_file(file_id):
    """
    Restore a previously deactivated file.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE files
        SET is_active = 1
        WHERE id = ?
    """, (file_id,))

    reactivated = cursor.rowcount > 0

    connection.commit()
    connection.close()

    return reactivated

def delete_file(file_id):
    connection = get_connection()

    try:
        cursor = connection.execute(
            "DELETE FROM files WHERE id = ?",
            (file_id,),
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()

def get_file_stats():
    """
    Return overall file-system statistics.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM files
        WHERE is_active = 1
    """)
    active_files = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM files
        WHERE is_active = 0
    """)
    inactive_files = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(download_count), 0)
        FROM files
        WHERE is_active = 1
    """)
    total_file_downloads = cursor.fetchone()[0]

    connection.close()

    return {
        "active_files": active_files,
        "inactive_files": inactive_files,
        "total_file_downloads": total_file_downloads,
    }

def generate_file_key():
    """
    Generate a collision-resistant public file key.

    The numeric format is intentionally preserved so existing
    file-key validation and deep-link handling continue to work.
    """

    connection = get_connection()

    try:
        while True:
            random_number = secrets.randbelow(
                900000000000
            ) + 100000000000

            file_key = f"file_{random_number}"

            cursor = connection.execute(
                """
                SELECT 1
                FROM files
                WHERE file_key = ?
                LIMIT 1
                """,
                (file_key,),
            )

            if cursor.fetchone() is None:
                return file_key

    finally:
        connection.close()


# ============================================================
# ADMIN LOGGING
# ============================================================

def log_admin_action(
    admin_id,
    action,
    target_type=None,
    target_id=None,
    description=None,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO admin_logs
        (
            timestamp,
            admin_id,
            action,
            target_type,
            target_id,
            description
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        admin_id,
        action,
        target_type,
        str(target_id) if target_id is not None else None,
        description,
    ))

    connection.commit()
    connection.close()

# ============================================================
# USER BAN SYSTEM
# ============================================================

def is_user_blocked(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT is_blocked
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    result = cursor.fetchone()

    connection.close()

    if result is None:
        return False

    return bool(result["is_blocked"])


def block_user(
    user_id,
    reason="LEFT_REQUIRED_CHANNEL",
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET is_blocked = 1,
            is_verified = 0,
            blocked_reason = ?,
            blocked_at = ?
        WHERE user_id = ?
    """, (
        reason,
        datetime.now(timezone.utc).isoformat(),
        user_id,
    ))

    connection.commit()
    connection.close()


def unblock_user(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET is_blocked = 0,
            is_verified = 0,
            blocked_reason = NULL,
            blocked_at = NULL
        WHERE user_id = ?
    """, (user_id,))

    connection.commit()
    connection.close()


def get_block_info(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            is_blocked,
            blocked_reason,
            blocked_at
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    result = cursor.fetchone()

    connection.close()

    return result