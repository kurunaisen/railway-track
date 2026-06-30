import { useEffect, useRef, useState } from "react";
import type { AudioSession } from "./api";
import {
  PIPELINE_STEPS,
  canEdit,
  confirmSession,
  downloadSessionExcel,
  fieldLabel,
  formatTime,
  getJob,
  getSession,
  isAdmin,
  issueText,
  processSession,
  saveSession,
  uploadAudio,
} from "./api";
import { type AuthUser, checkHealth, clearAuth, fetchMe, getUser } from "./auth";
import { healthUrl } from "./config";
import Login from "./Login";
import { APP_BRAND_ACCENT, APP_BRAND_MAIN, APP_TAGLINE, DEVELOPER_NAME, DEVELOPER_URL } from "./branding";
import { AccountPanel } from "./profile/AccountPanel";
import { ProfileAvatar } from "./profile/ProfileAvatar";

function MicIcon() {
  return (
    <svg className="btn-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.93V21h2v-3.07A7 7 0 0 0 19 11h-2z" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg className="btn-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <rect x="6" y="6" width="12" height="12" rx="1.5" />
    </svg>
  );
}

function BrandTitle() {
  return (
    <h1 className="brand-title">
      {APP_BRAND_MAIN}
      <span className="text-gold">{APP_BRAND_ACCENT}</span>
    </h1>
  );
}

function SessionMeta({
  session,
  disputedCount,
}: {
  session: AudioSession;
  disputedCount: number;
}) {
  return (
    <div className="session-meta">
      <span className={`status status-${session.status}`}>{statusLabel(session.status)}</span>
      {session.confirmed && <span className="status status-confirmed">Подтверждено</span>}
      {disputedCount > 0 && <span className="status status-disputed">Спорных: {disputedCount}</span>}
      <span className="filename">{session.original_name}</span>
    </div>
  );
}

function AppFooter() {
  return (
    <footer className="footer">
      <div className="container footer-inner">
        <div>
          <p className="footer-brand">
            {APP_BRAND_MAIN}
            <span className="text-gold">{APP_BRAND_ACCENT}</span>
          </p>
          <p className="footer-tagline">{APP_TAGLINE}</p>
        </div>
        <p className="footer-copy">
          от разработчика{" "}
          <a className="footer-link" href={DEVELOPER_URL} target="_blank" rel="noopener noreferrer">
            {DEVELOPER_NAME}
          </a>
        </p>
      </div>
    </footer>
  );
}

async function pollUntilDone(jobId: number, sessionId: number): Promise<AudioSession> {
  for (let i = 0; i < 600; i++) {
    const job = await getJob(jobId);
    if (job.status === "completed") return getSession(sessionId);
    if (job.status === "failed") throw new Error(job.error_message || "Ошибка обработки");
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("Превышено время ожидания обработки");
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(() => getUser());
  const [authRequired, setAuthRequired] = useState<boolean | null>(() =>
    typeof window !== "undefined" &&
    (window.location.hostname.endsWith(".vercel.app") ||
      window.location.hostname.endsWith(".vercel.sh"))
      ? true
      : null
  );
  const [session, setSession] = useState<AudioSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [queueStatus, setQueueStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [saved, setSaved] = useState(false);
  const [tableView, setTableView] = useState<"long" | "wide">("long");
  const [accountOpen, setAccountOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const editable = user ? canEdit(user.role) : false;
  const adminView = user ? isAdmin(user.role) : false;

  useEffect(() => {
    let cancelled = false;
    const fallback = window.setTimeout(() => {
      if (!cancelled) {
        setAuthRequired(true);
        setError((prev) =>
          prev ??
          "API не ответил вовремя — показана форма входа. Если вход не работает, проверьте VITE_API_URL (Production) на Vercel и redeploy."
        );
      }
    }, 8000);

    checkHealth()
      .then((h) => {
        if (cancelled) return;
        window.clearTimeout(fallback);
        setAuthRequired(h.auth_required);
        if (!h.auth_required && !user) setUser({ username: "dev", role: "operator" });
        if (getUser() && h.auth_required) {
          fetchMe()
            .then((profile) => {
              if (!cancelled && profile) setUser(profile);
            })
            .catch(() => {});
        }
      })
      .catch(() => {
        if (cancelled) return;
        window.clearTimeout(fallback);
        setError(
          "Не удалось подключиться к API. Проверьте VITE_API_URL на Vercel (Production, https://....up.railway.app) и CORS на Railway."
        );
        setAuthRequired(true);
      });

    return () => {
      cancelled = true;
      window.clearTimeout(fallback);
    };
  }, []);

  const handleFile = async (file: File) => {
    if (!editable) return;
    setError(null);
    setSaved(false);
    setLoading(true);
    try {
      setSession(await uploadAudio(file));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleProcess = async () => {
    if (!session || !editable) return;
    setError(null);
    setSaved(false);
    setLoading(true);
    setQueueStatus(null);
    try {
      const result = await processSession(session.id);
      if (result.queued && result.job) {
        setQueueStatus("В очереди…");
        setSession({ ...session, status: "queued" });
        const processed = await pollUntilDone(result.job.id, session.id);
        setSession(processed);
        setQueueStatus(null);
      } else if (result.session) {
        setSession(result.session);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка обработки");
      setQueueStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!session || !editable) return;
    setLoading(true);
    try {
      await saveSession(session.id);
      setSaved(true);
      setSession({ ...session, status: "saved" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!session || !editable) return;
    setLoading(true);
    try {
      await confirmSession(session.id);
      setSession({ ...session, confirmed: true, status: "confirmed" });
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка подтверждения");
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    if (!editable) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        await handleFile(new File([blob], `recording_${Date.now()}.webm`, { type: "audio/webm" }));
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setError("Не удалось получить доступ к микрофону");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  const handleLogout = () => {
    clearAuth();
    setUser(null);
    setSession(null);
    setAccountOpen(false);
  };

  const handleOpenSession = async (sessionId: number) => {
    setError(null);
    setLoading(true);
    try {
      setSession(await getSession(sessionId));
      setSaved(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось открыть запись");
    } finally {
      setLoading(false);
    }
  };

  const handleExcelDownload = async () => {
    if (!session) return;
    setLoading(true);
    try {
      await downloadSessionExcel(session.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка выгрузки Excel");
    } finally {
      setLoading(false);
    }
  };

  if (authRequired === null) {
    return (
      <div className="app carbon-bg loading-screen">
        <div className="loader" aria-hidden />
        <p>Загрузка системы…</p>
        {error ? (
          <div className="error" style={{ maxWidth: 520, marginTop: 16, textAlign: "left" }}>
            {error}
          </div>
        ) : (
          <p className="hint" style={{ marginTop: 12 }}>
            Подключение к {healthUrl()}
          </p>
        )}
      </div>
    );
  }

  if (authRequired && !user) {
    return (
      <div className="app carbon-bg">
        <header className="header">
          <div className="container header-inner">
            <div className="logo">
              <BrandTitle />
              <p>Защищённый доступ</p>
            </div>
          </div>
        </header>
        <main className="main">
          <div className="container">
            <Login authRequired={authRequired} onSuccess={setUser} />
          </div>
        </main>
        <AppFooter />
      </div>
    );
  }

  const disputedCount =
    session?.records.reduce((n, r) => n + (r.disputed_fields?.length ?? 0), 0) ?? 0;

  const disputedRows =
    session?.records
      .map((r, i) => ({ row: i, record: r }))
      .filter(({ record }) => (record.disputed_fields?.length ?? 0) > 0) ?? [];

  const unknownTerms =
    session?.unknown_terms.filter((t) => (t.term || "").trim()) ?? [];

  const hasWarningsPanel =
    !!session &&
    (disputedRows.length > 0 ||
      (session.validation_warnings?.length ?? 0) > 0 ||
      (session.parse_errors?.length ?? 0) > 0 ||
      unknownTerms.length > 0);

  return (
    <div className="app carbon-bg">
      <header className="header">
        <div className="container header-inner">
          <div className="logo">
            <BrandTitle />
          </div>
          <div className="header-actions">
            {user && (
              <button
                type="button"
                className="user-menu-btn"
                onClick={() => setAccountOpen(true)}
                aria-label={`Аккаунт: ${user.username}`}
                title={user.username}
              >
                <ProfileAvatar avatarId={user.avatar_id} name={user.username} size="sm" />
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="main">
        <div className="container">
        {editable && (
          <section className="panel carbon-panel upload-panel">
            <h2>Загрузите аудио или запишите аудио</h2>
            <p className="hint">
              Форматы: WAV, MP3, M4A, FLAC. Запись с микрофона или файл — результат попадёт в таблицу после
              обработки на сервере (mono 16 kHz WAV).
            </p>
            <div className="upload-actions">
              <input
                ref={fileRef}
                type="file"
                accept=".wav,.mp3,.m4a,.flac,audio/wav,audio/mpeg,audio/mp4,audio/flac"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                }}
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => fileRef.current?.click()}
                disabled={loading}
              >
                Выбрать файл
              </button>
              {!recording ? (
                <button type="button" className="btn btn-record" onClick={startRecording} disabled={loading}>
                  <MicIcon />
                  Записать
                </button>
              ) : (
                <button type="button" className="btn btn-stop" onClick={stopRecording}>
                  <StopIcon />
                  Остановить
                </button>
              )}
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleProcess}
                disabled={
                  !session ||
                  loading ||
                  session.status === "processing" ||
                  session.active_job?.status === "running"
                }
              >
                {loading ? queueStatus || "Обработка…" : "Обработать"}
              </button>
            </div>
            {session && <SessionMeta session={session} disputedCount={disputedCount} />}
            {error && <div className="error">{error}</div>}
          </section>
        )}

        {!editable && session && (
          <section className="panel carbon-panel upload-panel">
            <SessionMeta session={session} disputedCount={disputedCount} />
          </section>
        )}

        {adminView && session?.full_transcript && (
          <section className="panel carbon-panel transcript-panel">
            <h2>Шаг 3–4: ASR и логические блоки</h2>
            {session.logical_blocks.length > 0 && session.records.length > 0 && (
              <p className="hint multi-record-summary">
                1 аудио → {session.logical_records_count || session.logical_blocks.length} лог. записей →{" "}
                {session.positions_count || session.records.length} позиций (строк)
              </p>
            )}
            {session.asr_avg_confidence != null && (
              <p className="hint">Средняя уверенность ASR: {(session.asr_avg_confidence * 100).toFixed(0)}%</p>
            )}
            {session.active_job && session.active_job.status === "running" && (
              <p className="hint pipeline-step">
                Конвейер: шаг {session.active_job.current_step} — {PIPELINE_STEPS[session.active_job.current_step - 1]}
              </p>
            )}
            <p className="transcript">{session.full_transcript}</p>
            {session.transcript_segments.length > 0 && (
              <details className="segments-details" open>
                <summary>ASR-сегменты ({session.transcript_segments.length})</summary>
                <ul className="segments-list">
                  {session.transcript_segments.map((seg, i) => (
                    <li key={i}>
                      <span className="seg-time">
                        {formatTime(seg.start)} — {formatTime(seg.end)}
                        {seg.confidence != null && (
                          <span className="conf"> {(seg.confidence * 100).toFixed(0)}%</span>
                        )}
                      </span>
                      {seg.text}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {session.logical_records.length > 0 && (
              <details className="segments-details">
                <summary>Логические записи ({session.logical_records.length})</summary>
                <ul className="segments-list">
                  {session.logical_records.map((lr) => (
                    <li key={lr.index}>
                      <span className="seg-time">#{lr.index + 1}</span>
                      {[lr.peregon, lr.put && `путь ${lr.put}`, lr.km && `км ${lr.km}`, lr.piket && `пикет ${lr.piket}`]
                        .filter(Boolean)
                        .join(", ") || "—"}
                      {lr.positions_count > 1 && (
                        <span className="conf"> · {lr.positions_count} поз.</span>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {session.logical_blocks.length > 0 && (
              <details className="segments-details">
                <summary>Логические блоки ({session.logical_blocks.length})</summary>
                <ul className="segments-list">
                  {session.logical_blocks.map((b) => (
                    <li key={b.index}>
                      <span className="seg-time">{b.trigger ?? "—"}</span>
                      {b.text}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>
        )}

        {session && session.records.length > 0 && (
          <section className="panel carbon-panel table-panel">
            <div className="table-header">
              <h2>
                {adminView
                  ? `Шаг 9: Построчная таблица (${session.positions_count || session.records.length} позиций)`
                  : `Таблица результатов (${session.positions_count || session.records.length} поз.)`}
              </h2>
              <div className="table-actions">
                <div className="view-toggle">
                  <button
                    className={`btn btn-secondary btn-sm ${tableView === "long" ? "active" : ""}`}
                    onClick={() => setTableView("long")}
                  >
                    Построчная
                  </button>
                  <button
                    className={`btn btn-secondary btn-sm ${tableView === "wide" ? "active" : ""}`}
                    onClick={() => setTableView("wide")}
                  >
                    Сводная
                  </button>
                </div>
                {editable && (
                  <>
                    <button className="btn btn-secondary" onClick={handleSave} disabled={loading}>
                      {saved ? "✓ Сохранено" : "Сохранить"}
                    </button>
                    <button
                      className="btn btn-success"
                      onClick={handleConfirm}
                      disabled={loading || session.confirmed}
                    >
                      {session.confirmed ? "✓ Подтверждено" : "Подтвердить"}
                    </button>
                  </>
                )}
                <button type="button" className="btn btn-primary" onClick={() => void handleExcelDownload()} disabled={loading}>
                  Excel
                </button>
              </div>
            </div>
            {!editable && <p className="hint">Режим просмотра (viewer).</p>}
            <div className="table-layout">
              <div className="table-main">
                {tableView === "wide" && session.records_wide ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          {session.records_wide.columns.map((c) => (
                            <th key={c}>{c}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {session.records_wide.rows.map((row, i) => (
                          <tr key={i}>
                            {session.records_wide!.columns.map((c) => (
                              <td key={c}>{row[c] ?? "—"}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : session.records_form ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          {session.records_form.columns.map((c) => (
                            <th key={c}>{c}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {session.records_form.rows.map((row, i) => (
                          <tr key={i}>
                            {session.records_form!.columns.map((c) => (
                              <td key={c}>{row[c] ?? "—"}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="hint">
                    Нет данных для таблицы. Переобработайте файл после обновления сервера.
                  </p>
                )}
              </div>
              {(session.records_wide || session.records_form) && (
                <aside className="table-aside" aria-hidden>
                  <img src="/surprise.png" alt="" className="table-aside-art" />
                </aside>
              )}
            </div>
          </section>
        )}

        {hasWarningsPanel && (
          <section className="panel carbon-panel meta-panel">
            <h2>{adminView ? "Шаг 7: Предупреждения" : "Требует проверки"}</h2>
            {disputedRows.length > 0 && (
              <div className="meta-block">
                <h3>Спорные поля ({disputedCount})</h3>
                <ul>
                  {disputedRows.map(({ row, record }) => (
                    <li key={record.id ?? row}>
                      <strong>Строка {row + 1}:</strong>{" "}
                      {record.disputed_fields.map((f) => fieldLabel(f)).join(", ")}
                      {record.km != null && record.piket != null && (
                        <span className="issue-context">
                          {" "}
                          (км {record.km}, пикет {record.piket})
                        </span>
                      )}
                      {record.raw_text && (
                        <div className="issue-fragment">«{record.raw_text.slice(0, 160)}»</div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {session!.validation_warnings.length > 0 && (
              <div className="meta-block">
                <h3>Валидация ({session!.validation_warnings.length})</h3>
                <ul>
                  {session!.validation_warnings.map((w, i) => (
                    <li key={i}>
                      {w.row != null && w.row >= 0 ? `Строка ${w.row + 1}: ` : ""}
                      {issueText(w)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {session!.parse_errors.length > 0 && (
              <div className="meta-block">
                <h3>Ошибки разбора ({session!.parse_errors.length})</h3>
                <ul>
                  {session!.parse_errors.map((e, i) => (
                    <li key={i}>
                      {e.row != null && e.row >= 0 ? `Строка ${e.row + 1}: ` : "Общее: "}
                      {issueText(e)}
                      {e.text && <div className="issue-fragment">«{e.text}»</div>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {unknownTerms.length > 0 && (
              <div className="meta-block">
                <h3>Неизвестные термины ({unknownTerms.length})</h3>
                <p className="hint meta-hint">
                  Слова вне словаря — возможная ошибка ASR; проверьте строку таблицы.
                </p>
                <div className="terms-cloud">
                  {unknownTerms.slice(0, 20).map((t) => (
                    <span key={t.term} className="term-tag" title={`встречается ${t.count}×`}>
                      {t.term}
                      {t.count > 1 ? ` ×${t.count}` : ""}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {session && !session.full_transcript && !loading && editable && (
          <section className="panel carbon-panel empty-panel">
            <p>
              Файл <strong>{session.original_name}</strong> загружен. Нажмите «Обработать» — распознавание и
              разбор выполняются на сервере.
            </p>
          </section>
        )}
        </div>
      </main>

      {user && (
        <AccountPanel
          open={accountOpen}
          user={user}
          onClose={() => setAccountOpen(false)}
          onLogout={handleLogout}
          onOpenSession={handleOpenSession}
          onAvatarSaved={(avatarId) => setUser((prev) => (prev ? { ...prev, avatar_id: avatarId } : prev))}
        />
      )}

      <AppFooter />
    </div>
  );
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    uploaded: "Загружено",
    queued: "В очереди",
    processing: "Обработка",
    processed: "Обработано",
    saved: "Сохранено",
    confirmed: "Подтверждено",
    error: "Ошибка",
  };
  return map[status] ?? status;
}
