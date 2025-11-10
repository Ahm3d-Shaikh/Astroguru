def is_user_admin(user):
    role = user["role"]
    if role != "admin":
        return False
    return True