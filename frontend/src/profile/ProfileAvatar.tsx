import { AvatarArt } from "./AvatarArt";
import {
  getProfileAvatarOption,
  resolveProfileAvatarId,
  type ProfileAvatarId,
} from "./profile-avatars";

type ProfileAvatarProps = {
  avatarId?: string | null;
  name?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
};

export function ProfileAvatar({
  avatarId,
  name = "?",
  size = "sm",
  className = "",
}: ProfileAvatarProps) {
  const resolvedId = resolveProfileAvatarId(avatarId);
  const option = getProfileAvatarOption(resolvedId);

  return (
    <span
      className={`profile-avatar profile-avatar-${size} ${option.bgClass} ${className}`.trim()}
      aria-hidden={!name}
      title={name}
    >
      <AvatarArt id={resolvedId as ProfileAvatarId} />
    </span>
  );
}
