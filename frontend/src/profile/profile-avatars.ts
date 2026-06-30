export type ProfileAvatarId =
  | "star"
  | "orbit"
  | "neural"
  | "bolt"
  | "prism"
  | "comet"
  | "hex"
  | "wave"
  | "shield"
  | "core";

export const DEFAULT_PROFILE_AVATAR_ID: ProfileAvatarId = "star";

export type ProfileAvatarOption = {
  id: ProfileAvatarId;
  label: string;
  bgClass: string;
};

export const PROFILE_AVATARS: ProfileAvatarOption[] = [
  { id: "star", label: "Звезда", bgClass: "avatar-bg-star" },
  { id: "orbit", label: "Орбита", bgClass: "avatar-bg-orbit" },
  { id: "neural", label: "Нейросеть", bgClass: "avatar-bg-neural" },
  { id: "bolt", label: "Импульс", bgClass: "avatar-bg-bolt" },
  { id: "prism", label: "Призма", bgClass: "avatar-bg-prism" },
  { id: "comet", label: "Комета", bgClass: "avatar-bg-comet" },
  { id: "hex", label: "Гекс", bgClass: "avatar-bg-hex" },
  { id: "wave", label: "Волна", bgClass: "avatar-bg-wave" },
  { id: "shield", label: "Щит", bgClass: "avatar-bg-shield" },
  { id: "core", label: "Ядро", bgClass: "avatar-bg-core" },
];

const avatarIds = new Set(PROFILE_AVATARS.map((avatar) => avatar.id));

export function isProfileAvatarId(value: string): value is ProfileAvatarId {
  return avatarIds.has(value as ProfileAvatarId);
}

export function resolveProfileAvatarId(value: string | null | undefined): ProfileAvatarId {
  if (value && isProfileAvatarId(value)) return value;
  return DEFAULT_PROFILE_AVATAR_ID;
}

export function getProfileAvatarOption(id: ProfileAvatarId): ProfileAvatarOption {
  return PROFILE_AVATARS.find((avatar) => avatar.id === id) ?? PROFILE_AVATARS[0];
}
