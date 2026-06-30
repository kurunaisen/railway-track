import { useState } from "react";
import { updateProfileAvatar } from "../auth";
import { ProfileAvatar } from "./ProfileAvatar";
import {
  PROFILE_AVATARS,
  resolveProfileAvatarId,
  type ProfileAvatarId,
} from "./profile-avatars";

type ProfileAvatarPickerProps = {
  initialAvatarId: string | null;
  displayName: string;
  onSaved?: (avatarId: string) => void;
};

export function ProfileAvatarPicker({
  initialAvatarId,
  displayName,
  onSaved,
}: ProfileAvatarPickerProps) {
  const [selected, setSelected] = useState<ProfileAvatarId>(resolveProfileAvatarId(initialAvatarId));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const dirty = selected !== resolveProfileAvatarId(initialAvatarId);

  async function handleSave() {
    if (!dirty || saving) return;
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const profile = await updateProfileAvatar(selected);
      setMessage("Иконка обновлена");
      onSaved?.(profile.avatar_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="profile-picker">
      <div className="profile-picker-head">
        <ProfileAvatar avatarId={selected} name={displayName} size="lg" />
        <div>
          <p className="profile-section-label">Иконка профиля</p>
          <p className="hint profile-picker-hint">Выберите аватар — он отображается в шапке сайта</p>
        </div>
      </div>

      <div className="profile-avatar-grid">
        {PROFILE_AVATARS.map((avatar) => {
          const active = selected === avatar.id;
          return (
            <button
              key={avatar.id}
              type="button"
              onClick={() => setSelected(avatar.id)}
              disabled={saving}
              title={avatar.label}
              aria-label={avatar.label}
              aria-pressed={active}
              className={`profile-avatar-option ${active ? "active" : ""}`.trim()}
            >
              <ProfileAvatar avatarId={avatar.id} name={avatar.label} size="md" />
              <span>{avatar.label}</span>
            </button>
          );
        })}
      </div>

      {error && <div className="error">{error}</div>}
      {message && <p className="profile-save-msg">{message}</p>}

      <button type="button" className="btn btn-primary btn-sm" onClick={() => void handleSave()} disabled={!dirty || saving}>
        {saving ? "Сохранение…" : "Сохранить иконку"}
      </button>
    </div>
  );
}
