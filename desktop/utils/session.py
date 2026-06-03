class Session:
    token:     str = None
    role:      str = None
    full_name: str = None
    user_id:   str = None
    username:  str = None  # ← add this

    @classmethod
    def set(cls, token, role, full_name, user_id):
        cls.token     = token
        cls.role      = role
        cls.full_name = full_name
        cls.user_id   = user_id

    @classmethod
    def clear(cls):
        cls.token     = None
        cls.role      = None
        cls.full_name = None
        cls.user_id   = None
        cls.username  = None  # ← add this

    @classmethod
    def is_logged_in(cls) -> bool:
        return cls.token is not None

    @classmethod
    def is_admin(cls) -> bool:
        return cls.role in ["superadmin", "manager"]