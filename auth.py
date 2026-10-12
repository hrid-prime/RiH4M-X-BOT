from database import is_admin, is_owner


def is_authorized_admin(user_id):
    return is_admin(user_id)


def is_authorized_owner(user_id):
    return is_owner(user_id)


def get_role(user_id):
    if is_owner(user_id):
        return "owner"

    if is_admin(user_id):
        return "admin"

    return "user"