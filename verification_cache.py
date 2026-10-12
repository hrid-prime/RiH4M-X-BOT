import time


# ============================================================
# VERIFICATION CACHE
# ============================================================

# How long a successful membership verification remains valid.
#
# 60 seconds = 1 minute.
#
# This cache is intentionally kept in memory.
VERIFICATION_CACHE_SECONDS = 60


# user_id -> expiry timestamp from time.monotonic()
_verification_cache = {}


def _get_cached_verification(user_id):
    """
    Return True when the user's verification cache is still valid.

    Returns:
        True  -> valid cached verification exists
        False -> no cache or cache expired
    """

    expires_at = _verification_cache.get(user_id)

    if expires_at is None:
        return False

    if time.monotonic() >= expires_at:
        _verification_cache.pop(
            user_id,
            None,
        )
        return False

    return True


def _cache_verification(user_id):
    """
    Cache a successful membership verification.
    """

    _verification_cache[user_id] = (
        time.monotonic()
        + VERIFICATION_CACHE_SECONDS
    )


def clear_verification_cache(user_id):
    """
    Immediately remove a user's cached verification.
    """

    _verification_cache.pop(
        user_id,
        None,
    )