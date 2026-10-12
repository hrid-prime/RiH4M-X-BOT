import sqlite3
from datetime import datetime, timezone

from config import OWNER_ID


connection = sqlite3.connect("bot.db")

try:
    # --------------------------------------------------------
    # DELETE DEVELOPMENT DATA
    # --------------------------------------------------------

    connection.execute("DELETE FROM users")
    connection.execute("DELETE FROM files")
    connection.execute("DELETE FROM admin_logs")
    connection.execute("DELETE FROM settings")

    # Reset auto-increment counters where applicable.
    connection.execute(
        "DELETE FROM sqlite_sequence "
        "WHERE name IN ('files', 'admin_logs')"
    )

    # --------------------------------------------------------
    # CREATE ONE FRESH USER: THE OWNER
    # --------------------------------------------------------

    connection.execute(
        """
        INSERT INTO users (
            user_id,
            username,
            first_name,
            joined_at,
            is_verified,
            download_count,
            is_blocked,
            blocked_reason,
            blocked_at
        )
        VALUES (
            ?,
            NULL,
            NULL,
            ?,
            0,
            0,
            0,
            NULL,
            NULL
        )
        """,
        (
            OWNER_ID,
            datetime.now(timezone.utc).isoformat(),
        ),
    )

    connection.commit()

    # --------------------------------------------------------
    # VERIFY RESULT
    # --------------------------------------------------------

    user_count = connection.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    file_count = connection.execute(
        "SELECT COUNT(*) FROM files"
    ).fetchone()[0]

    log_count = connection.execute(
        "SELECT COUNT(*) FROM admin_logs"
    ).fetchone()[0]

    owner_record = connection.execute(
        """
        SELECT
            user_id,
            is_verified,
            download_count,
            is_blocked
        FROM users
        WHERE user_id = ?
        """,
        (OWNER_ID,),
    ).fetchone()

    print()
    print("=" * 50)
    print("FRESH DATABASE RESET COMPLETE")
    print("=" * 50)
    print(f"Owner ID:       {OWNER_ID}")
    print(f"Users:          {user_count}")
    print(f"Files:          {file_count}")
    print(f"Admin logs:     {log_count}")
    print(f"Owner record:   {owner_record}")
    print("=" * 50)

finally:
    connection.close()