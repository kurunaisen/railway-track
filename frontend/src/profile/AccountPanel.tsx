import { useCallback, useEffect, useState } from "react";
import type { AuthUser } from "../auth";
import { downloadSessionExcel, listSessionSummaries, type SessionSummary } from "../api";
import { ProfileAvatarPicker } from "./ProfileAvatarPicker";
import { ProfileAvatar } from "./ProfileAvatar";

type AccountPanelProps = {
  open: boolean;
  user: AuthUser;
  onClose: () => void;
  onLogout: () => void;
  onOpenSession: (sessionId: number) => void;
  onAvatarSaved: (avatarId: string) => void;
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    uploaded: "Загружено",
    queued: "В очереди",
    processing: "Обработка",
    processed: "Готово",
    saved: "Сохранено",
    confirmed: "Подтверждено",
  };
  return map[status] ?? status;
}

export function AccountPanel({
  open,
  user,
  onClose,
  onLogout,
  onOpenSession,
  onAvatarSaved,
}: AccountPanelProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSessions(await listSessionSummaries());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить историю");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void loadHistory();
  }, [open, loadHistory]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  async function handleDownload(sessionId: number) {
    setDownloadingId(sessionId);
    try {
      await downloadSessionExcel(sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка выгрузки Excel");
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <div className="account-overlay" role="presentation" onClick={onClose}>
      <div
        className="account-panel carbon-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-panel-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="account-panel-header">
          <div className="account-panel-user">
            <ProfileAvatar avatarId={user.avatar_id} name={user.username} size="md" />
            <div>
              <h2 id="account-panel-title">Аккаунт</h2>
              <p className="hint">
                {user.username} · {user.role}
              </p>
            </div>
          </div>
          <button type="button" className="account-close btn btn-secondary btn-sm" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>

        <section className="account-section">
          <ProfileAvatarPicker
            initialAvatarId={user.avatar_id ?? null}
            displayName={user.username}
            onSaved={onAvatarSaved}
          />
        </section>

        <section className="account-section">
          <div className="account-section-head">
            <p className="profile-section-label">Загруженные записи</p>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => void loadHistory()} disabled={loading}>
              Обновить
            </button>
          </div>
          <p className="hint account-section-hint">
            Все ваши аудиозаписи и сгенерированные таблицы. Можно открыть снова или выгрузить Excel.
          </p>

          {error && <div className="error">{error}</div>}
          {loading && <p className="hint">Загрузка…</p>}

          {!loading && sessions.length === 0 && (
            <p className="hint account-empty">Пока нет загруженных записей.</p>
          )}

          {!loading && sessions.length > 0 && (
            <ul className="session-history-list">
              {sessions.map((item) => (
                <li key={item.id} className="session-history-item">
                  <div className="session-history-main">
                    <strong className="session-history-name">{item.original_name}</strong>
                    <span className="session-history-meta">
                      {formatDate(item.created_at)} · {statusLabel(item.status)}
                      {item.has_table ? ` · ${item.positions_count} поз.` : ""}
                      {item.confirmed ? " · подтверждено" : ""}
                    </span>
                    {item.export_count > 0 && (
                      <span className="session-history-export hint">
                        Excel: {item.export_count}×
                        {item.last_export_at ? `, последний ${formatDate(item.last_export_at)}` : ""}
                      </span>
                    )}
                  </div>
                  <div className="session-history-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        onOpenSession(item.id);
                        onClose();
                      }}
                    >
                      Открыть
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={!item.has_table || downloadingId === item.id}
                      onClick={() => void handleDownload(item.id)}
                    >
                      {downloadingId === item.id ? "…" : "Excel"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="account-panel-footer">
          <button type="button" className="btn btn-secondary" onClick={onLogout}>
            Выход
          </button>
        </div>
      </div>
    </div>
  );
}
