"""Preset profile avatars (aligned with DeltaplanAI)."""

from __future__ import annotations

ProfileAvatarId = str

VALID_AVATAR_IDS: frozenset[str] = frozenset({
    "star",
    "orbit",
    "neural",
    "bolt",
    "prism",
    "comet",
    "hex",
    "wave",
    "shield",
    "core",
})

DEFAULT_AVATAR_ID = "star"


def is_profile_avatar_id(value: str | None) -> bool:
    return bool(value and value in VALID_AVATAR_IDS)


def resolve_profile_avatar_id(value: str | None) -> str:
    if is_profile_avatar_id(value):
        return value  # type: ignore[return-value]
    return DEFAULT_AVATAR_ID
