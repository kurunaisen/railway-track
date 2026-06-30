"""Profile avatar and session history summary."""

from app.models import User
from app.services.profile_avatars import resolve_profile_avatar_id


def test_resolve_profile_avatar_id():
    assert resolve_profile_avatar_id("core") == "core"
    assert resolve_profile_avatar_id("invalid") == "star"
    assert resolve_profile_avatar_id(None) == "star"


def test_user_avatar_column_default():
    col = User.__table__.c.avatar_id
    assert col.default.arg == "star"
