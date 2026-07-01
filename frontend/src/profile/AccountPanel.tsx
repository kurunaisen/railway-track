import { useCallback, useEffect, useMemo, useState } from "react";
import type { AuthUser } from "../auth";
import {
  canEdit,
  deleteSessionsBatch,
  downloadSessionAudio,
  downloadSessionExcel,
  listSessionSummaries,
  type SessionSummary,
} from "../api";
import { ProfileAvatarPicker } from "./ProfileAvatarPicker";
import { ProfileAvatar } from "./ProfileAvatar";

type AccountPanelProps = {
  open: boolean;
  user: AuthUser;
  onClose: () => void;
  onLogout: () => void;
  onOpenSession: (sessionId: number) => void;
  onAvatarSaved: (avatarId: string) => void;
  onSessionsDeleted?: (sessionIds: number[]) => void;
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

function TrashIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M3 6h18M8 6V4h8v2m-1 4v7H9v-7m2 0v7m4-7v7"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function AccountPanel({
  open,
  user,
  onClose,
  onLogout,
  onOpenSession,
  onAvatarSaved,
  onSessionsDeleted,
}: AccountPanelProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadingExcelId, setDownloadingExcelId] = useState<number | null>(null);
  const [downloadingAudioId, setDownloadingAudioId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const editable = canEdit(user.role);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listSessionSummaries();
      setSessions(list);
      setSelected((prev) => {
        const ids = new Set(list.map((s) => s.id));
        const next = new Set<number>();
        prev.forEach((id) => {
          if (ids.has(id)) next.add(id);
        });
        return next;
      });
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

  const allSelected = useMemo(
    () => sessions.length > 0 && sessions.every((s) => selected.has(s.id)),
    [sessions, selected],
  );

  const selectedCount = selected.size;

  if (!open) return null;

  function toggleSelected(sessionId: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(sessionId)) next.delete(sessionId);
      else next.add(sessionId);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(sessions.map((s) => s.id)));
  }

  async function handleDownloadExcel(sessionId: number) {
    setDownloadingExcelId(sessionId);
    try {
      await downloadSessionExcel(sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка выгрузки Excel");
    } finally {
      setDownloadingExcelId(null);
    }
  }

  async function handleDownloadAudio(item: SessionSummary) {
    setDownloadingAudioId(item.id);
    try {
      await downloadSessionAudio(item.id, item.original_name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка скачивания аудио");
    } finally {
      setDownloadingAudioId(null);
    }
  }

  async function handleDelete(ids: number[]) {
    if (ids.length === 0) return;
    const label =
      ids.length === 1
        ? "Удалить эту запись? Аудио и таблица будут удалены без восстановления."
        : `Удалить ${ids.length} записей? Аудио и таблицы будут удалены без восстановления.`;
    if (!window.confirm(label)) return;

    setDeleting(true);
    setError(null);
    try {
      await deleteSessionsBatch(ids);
      setSessions((prev) => prev.filter((s) => !ids.includes(s.id)));
      setSelected((prev) => {
        const next = new Set(prev);
        ids.forEach((id) => next.delete(id));
        return next;
      });
      onSessionsDeleted?.(ids);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить");
    } finally {
      setDeleting(false);
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
            Все ваши аудиозаписи и сгенерированные таблицы. Можно открыть, скачать аудио или Excel, удалить ненужные.
          </p>

          {editable && sessions.length > 0 && (
            <div className="session-history-toolbar">
              <label className="session-history-select-all">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  disabled={loading || deleting}
                />
                <span>Выбрать все</span>
              </label>
              {selectedCount > 0 && (
                <button
                  type="button"
                  className="btn btn-danger btn-sm session-history-delete-selected"
                  disabled={deleting}
                  onClick={() => void handleDelete([...selected])}
                >
                  {deleting ? "…" : `Удалить выбранные (${selectedCount})`}
                </button>
              )}
            </div>
          )}

          {error && <div className="error">{error}</div>}
          {loading && <p className="hint">Загрузка…</p>}

          {!loading && sessions.length === 0 && (
            <p className="hint account-empty">Пока нет загруженных записей.</p>
          )}

          {!loading && sessions.length > 0 && (
            <ul className="session-history-list">
              {sessions.map((item) => (
                <li key={item.id} className={`session-history-item${selected.has(item.id) ? " selected" : ""}`}>
                  {editable && (
                    <label className="session-history-check" aria-label={`Выбрать ${item.original_name}`}>
                      <input
                        type="checkbox"
                        checked={selected.has(item.id)}
                        onChange={() => toggleSelected(item.id)}
                        disabled={deleting}
                      />
                    </label>
                  )}
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
                      className="btn btn-secondary btn-sm"
                      disabled={downloadingAudioId === item.id || deleting}
                      onClick={() => void handleDownloadAudio(item)}
                    >
                      {downloadingAudioId === item.id ? "…" : "Аудио"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={!item.has_table || downloadingExcelId === item.id || deleting}
                      onClick={() => void handleDownloadExcel(item.id)}
                    >
                      {downloadingExcelId === item.id ? "…" : "Excel"}
                    </button>
                    {editable && (
                      <button
                        type="button"
                        className="btn btn-danger-ghost btn-sm"
                        title="Удалить"
                        aria-label={`Удалить ${item.original_name}`}
                        disabled={deleting}
                        onClick={() => void handleDelete([item.id])}
                      >
                        <TrashIcon />
                      </button>
                    )}
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
