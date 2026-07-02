import { useEffect, useRef, useState } from "react";
import type { AudioSession } from "./api";
import {
  canEdit,
  confirmSession,
  exportRailwayRowsXlsx,
  extractRailwayRows,
  getJob,
  getSession,
  processSession,
  saveSession,
  uploadAudio,
  type RailwayRow,
} from "./api";
import { type AuthUser, checkHealth, clearAuth, fetchMe, getUser } from "./auth";
import { healthUrl } from "./config";
import Login from "./Login";
import { APP_BRAND_ACCENT, APP_BRAND_MAIN, APP_TAGLINE, DEVELOPER_NAME, DEVELOPER_URL } from "./branding";
import { FORM_COLUMNS, toDisplayRows } from "./railway/display";
import {
  applyTranscriptSafeFixes,
  analyzeTranscriptQuality,
  buildTranscriptQualitySegments,
  type TranscriptIssue,
  type TranscriptQualitySegment,
} from "./railway/transcriptQuality";
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

function upsertBatchSession(sessions: AudioSession[], updated: AudioSession): AudioSession[] {
  const idx = sessions.findIndex((s) => s.id === updated.id);
  if (idx < 0) return [...sessions, updated];
  const next = [...sessions];
  next[idx] = updated;
  return next;
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

function combineSessionTranscripts(sessions: AudioSession[]): string {
  return sessions
    .map((item) => item.full_transcript?.trim())
    .filter((text): text is string => Boolean(text))
    .join("\n\n");
}

function appendTranscriptDraft(current: string, addition: string | null | undefined): string {
  const next = addition?.trim();
  if (!next) return current;
  if (current.includes(next)) return current;
  const existing = current.trim();
  return existing ? `${existing}\n\n${next}` : next;
}

function TranscriptQualityPreview({
  issues,
  segments,
  onApplySafeFixes,
  onSelectIssue,
}: {
  issues: TranscriptIssue[];
  segments: TranscriptQualitySegment[];
  onApplySafeFixes: () => void;
  onSelectIssue: (issue: TranscriptIssue) => void;
}) {
  if (segments.length === 1 && !segments[0].issue && !segments[0].text.trim()) return null;

  const errorCount = issues.filter((issue) => issue.severity === "error").length;
  const warningCount = issues.length - errorCount;
  const safeFixCount = issues.filter((issue) => issue.safeFix).length;
  const visibleIssues = issues.slice(0, 4);
  const hiddenIssueCount = Math.max(0, issues.length - visibleIssues.length);

  return (
    <div className="transcript-quality" aria-live="polite">
      <div className="transcript-quality-head">
        <strong>Проверка текста</strong>
        {issues.length > 0 ? (
          <span className="hint">
            {errorCount > 0 ? `красных: ${errorCount}` : ""}
            {errorCount > 0 && warningCount > 0 ? ", " : ""}
            {warningCount > 0 ? `жёлтых: ${warningCount}` : ""}
          </span>
        ) : (
          <span className="hint">подозрительных фрагментов не найдено</span>
        )}
      </div>
      {safeFixCount > 0 && (
        <div className="transcript-quality-actions">
          <button type="button" className="btn btn-secondary btn-sm" onClick={onApplySafeFixes}>
            Исправить безопасные ASR-ошибки ({safeFixCount})
          </button>
          <span className="hint">Удаляются только очевидные лишние числа перед корректной шириной колеи.</span>
        </div>
      )}
      <div className="transcript-quality-text" aria-label="Текст с подсветкой подозрительных фрагментов">
        {segments.map((segment, index) =>
          segment.issue ? (
            <mark
              key={`${segment.issue.id}-${index}`}
              className={`transcript-mark transcript-mark-${segment.issue.severity}`}
              title={`${segment.issue.title}: ${segment.issue.description}`}
              role="button"
              tabIndex={0}
              onClick={() => onSelectIssue(segment.issue!)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectIssue(segment.issue!);
                }
              }}
            >
              {segment.text}
            </mark>
          ) : (
            <span key={`plain-${index}`}>{segment.text}</span>
          ),
        )}
      </div>
      {issues.length > 0 && (
        <details className="transcript-quality-details">
          <summary>
            Пояснения ({issues.length})
            {hiddenIssueCount > 0 ? ` · показаны первые ${visibleIssues.length}` : ""}
          </summary>
          <ul className="transcript-quality-list">
          {visibleIssues.map((issue) => (
            <li
              key={issue.id}
              className={`transcript-quality-item ${issue.severity}`}
              role="button"
              tabIndex={0}
              onClick={() => onSelectIssue(issue)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectIssue(issue);
                }
              }}
            >
              <strong>{issue.title}</strong>
              <span>{issue.description}</span>
              {issue.safeFix && <em>Доступно безопасное исправление: {issue.safeFix.label}</em>}
            </li>
          ))}
          {hiddenIssueCount > 0 && <li className="hint">Ещё предупреждений: {hiddenIssueCount}</li>}
          </ul>
        </details>
      )}
    </div>
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
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [railwayRows, setRailwayRows] = useState<RailwayRow[]>([]);
  const [accountOpen, setAccountOpen] = useState(false);
  const [uploadBatch, setUploadBatch] = useState<AudioSession[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const transcriptEditorRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const editable = user ? canEdit(user.role) : false;

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

  const handleFiles = async (files: File[]) => {
    if (!editable || files.length === 0) return;
    setError(null);
    setSaved(false);
    setRailwayRows([]);
    setLoading(true);
    try {
      const uploaded: AudioSession[] = [];
      for (let i = 0; i < files.length; i++) {
        if (files.length > 1) {
          setQueueStatus(`Загрузка ${i + 1}/${files.length}…`);
        }
        uploaded.push(await uploadAudio(files[i]));
      }
      setUploadBatch((prev) => {
        const uploadedIds = new Set(uploaded.map((s) => s.id));
        return [...prev.filter((s) => !uploadedIds.has(s.id)), ...uploaded];
      });
      setSession(uploaded[uploaded.length - 1]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
      setQueueStatus(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const runProcess = async (
    target: AudioSession,
    progress?: { index: number; total: number },
    syncTranscript = true,
  ) => {
    setError(null);
    setSaved(false);
    setLoading(true);
    if (progress) {
      setQueueStatus(`Обработка ${progress.index}/${progress.total}…`);
    } else {
      setQueueStatus(null);
    }
    try {
      const result = await processSession(target.id);
      let processed = target;
      if (result.queued && result.job) {
        setQueueStatus(progress ? `Обработка ${progress.index}/${progress.total}…` : "В очереди…");
        processed = { ...target, status: "queued" };
        setSession(processed);
        setUploadBatch((prev) => upsertBatchSession(prev, processed));
        processed = await pollUntilDone(result.job.id, target.id);
      } else if (result.session) {
        processed = result.session;
      }
      setSession(processed);
      setUploadBatch((prev) => upsertBatchSession(prev, processed));
      if (syncTranscript && processed.full_transcript) {
        setTranscriptDraft((current) => appendTranscriptDraft(current, processed.full_transcript));
      }
      return processed;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка обработки");
      setQueueStatus(null);
      throw e;
    } finally {
      setLoading(false);
      if (!progress) setQueueStatus(null);
    }
  };

  const handleProcess = async () => {
    if (!session || !editable) return;
    await runProcess(session);
  };

  const handleProcessAll = async () => {
    if (!editable) return;
    const pending = uploadBatch.filter((s) => s.status === "uploaded");
    if (pending.length === 0) return;
    setError(null);
    setSaved(false);
    setLoading(true);
    try {
      for (let i = 0; i < pending.length; i++) {
        const target = pending[i];
        setSession(target);
        await runProcess(target, { index: i + 1, total: pending.length }, false);
      }
      const refreshed = await Promise.all(uploadBatch.map((s) => getSession(s.id)));
      setUploadBatch(refreshed);
      setSession(refreshed[refreshed.length - 1] ?? null);
      setTranscriptDraft(combineSessionTranscripts(refreshed));
      setRailwayRows([]);
    } catch {
      // runProcess уже выставил error
    } finally {
      setLoading(false);
      setQueueStatus(null);
    }
  };

  const handleSave = async () => {
    if (!session || !editable) return;
    setLoading(true);
    try {
      await saveSession(session.id);
      setSaved(true);
      const updated = { ...session, status: "saved" };
      setSession(updated);
      setUploadBatch((prev) => upsertBatchSession(prev, updated));
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
      const updated = { ...session, confirmed: true, status: "confirmed" };
      setSession(updated);
      setUploadBatch((prev) => upsertBatchSession(prev, updated));
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
        await handleFiles([new File([blob], `recording_${Date.now()}.webm`, { type: "audio/webm" })]);
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

  const handleExtractTable = async () => {
    if (!session || !editable || !transcriptDraft.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const rows = await extractRailwayRows(transcriptDraft, session.id);
      setRailwayRows(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка формирования таблицы");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenSession = async (sessionId: number) => {
    setError(null);
    setLoading(true);
    try {
      const loaded = await getSession(sessionId);
      setSession(loaded);
      setUploadBatch((prev) => upsertBatchSession(prev, loaded));
      setTranscriptDraft(loaded.full_transcript ?? "");
      setRailwayRows(loaded.railway_rows ?? []);
      setSaved(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось открыть запись");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectBatchSession = (item: AudioSession) => {
    setSession(item);
    setTranscriptDraft(item.full_transcript ?? "");
    setRailwayRows(item.railway_rows ?? []);
  };

  const handleExcelDownload = async () => {
    if (railwayRows.length === 0) return;
    setLoading(true);
    try {
      const base = session?.original_name?.replace(/\.[^.]+$/, "") ?? "railway_table";
      await exportRailwayRowsXlsx(railwayRows, { fileName: `${base}.xlsx` });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка выгрузки Excel");
    } finally {
      setLoading(false);
    }
  };

  const handleApplyTranscriptSafeFixes = () => {
    setTranscriptDraft((current) => applyTranscriptSafeFixes(current, analyzeTranscriptQuality(current)));
  };

  const handleSelectTranscriptIssue = (issue: TranscriptIssue) => {
    const editor = transcriptEditorRef.current;
    if (!editor) return;
    editor.focus();
    editor.setSelectionRange(issue.start, issue.end);
    const textBefore = editor.value.slice(0, issue.start);
    const lineIndex = textBefore.split("\n").length - 1;
    const lineHeight = Number.parseFloat(window.getComputedStyle(editor).lineHeight) || 24;
    editor.scrollTop = Math.max(0, lineIndex * lineHeight - editor.clientHeight / 2);
  };

  const handleTranscriptChange = (value: string) => {
    setTranscriptDraft(value);
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

  const displayRows = toDisplayRows(railwayRows);
  const hasTranscript = Boolean(transcriptDraft.trim());
  const transcriptQualityIssues = analyzeTranscriptQuality(transcriptDraft);
  const transcriptQualitySegments = buildTranscriptQualitySegments(
    transcriptDraft,
    transcriptQualityIssues,
  );

  const pendingUploadCount = uploadBatch.filter((s) => s.status === "uploaded").length;

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
              Форматы: WAV, MP3, M4A, FLAC. Можно выбрать несколько файлов — результат попадёт в таблицу после
              обработки на сервере (mono 16 kHz WAV).
            </p>
            <div className="upload-actions">
              <input
                ref={fileRef}
                type="file"
                multiple
                accept=".wav,.mp3,.m4a,.flac,audio/wav,audio/mpeg,audio/mp4,audio/flac"
                hidden
                onChange={(e) => {
                  const list = e.target.files;
                  if (list?.length) void handleFiles(Array.from(list));
                }}
              />
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => fileRef.current?.click()}
                disabled={loading}
              >
                Выбрать файлы
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
                onClick={() => void handleProcess()}
                disabled={
                  !session ||
                  loading ||
                  session.status === "processing" ||
                  session.active_job?.status === "running"
                }
              >
                {loading ? queueStatus || "Расшифровка…" : "Расшифровать"}
              </button>
              {pendingUploadCount > 1 && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void handleProcessAll()}
                  disabled={loading}
                >
                  Обработать все ({pendingUploadCount})
                </button>
              )}
            </div>
            {uploadBatch.length > 0 && (
              <ul className="upload-batch-list">
                {uploadBatch.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={`upload-batch-item ${session?.id === item.id ? "active" : ""}`}
                      onClick={() => handleSelectBatchSession(item)}
                      disabled={loading}
                    >
                      <span className="upload-batch-name">{item.original_name}</span>
                      <span className={`status status-${item.status}`}>{statusLabel(item.status)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {session && <SessionMeta session={session} disputedCount={0} />}
            {error && <div className="error">{error}</div>}
          </section>
        )}

        {!editable && session && (
          <section className="panel carbon-panel upload-panel">
            <SessionMeta session={session} disputedCount={0} />
          </section>
        )}

        {editable && session && hasTranscript && (
          <section className="panel carbon-panel transcript-panel">
            <h2>Транскрипт (можно править перед таблицей)</h2>
            {session.asr_avg_confidence != null && (
              <p className="hint">Средняя уверенность ASR: {(session.asr_avg_confidence * 100).toFixed(0)}%</p>
            )}
            <textarea
              ref={transcriptEditorRef}
              className="transcript-editor"
              rows={8}
              value={transcriptDraft}
              onChange={(e) => handleTranscriptChange(e.target.value)}
              disabled={loading}
            />
            <TranscriptQualityPreview
              issues={transcriptQualityIssues}
              segments={transcriptQualitySegments}
              onApplySafeFixes={handleApplyTranscriptSafeFixes}
              onSelectIssue={handleSelectTranscriptIssue}
            />
            <div className="upload-actions" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleExtractTable()}
                disabled={loading || !transcriptDraft.trim()}
              >
                {loading ? "Формирование…" : "Сформировать таблицу"}
              </button>
            </div>
          </section>
        )}

        {railwayRows.length > 0 && (
          <section className="panel carbon-panel table-panel">
            <div className="table-header">
              <h2>Таблица ({railwayRows.length} строк)</h2>
              <div className="table-actions">
                {editable && (
                  <>
                    <button className="btn btn-secondary" onClick={handleSave} disabled={loading}>
                      {saved ? "✓ Сохранено" : "Сохранить"}
                    </button>
                    <button
                      className="btn btn-success"
                      onClick={handleConfirm}
                      disabled={loading || !session || session.confirmed}
                    >
                      {session?.confirmed ? "✓ Подтверждено" : "Подтвердить"}
                    </button>
                  </>
                )}
                <button type="button" className="btn btn-primary" onClick={() => void handleExcelDownload()} disabled={loading}>
                  Excel
                </button>
              </div>
            </div>
            {!editable && <p className="hint">Режим просмотра (viewer).</p>}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {FORM_COLUMNS.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayRows.map((row, i) => (
                    <tr key={i}>
                      {FORM_COLUMNS.map((c) => (
                        <td key={c}>{row[c] ?? "—"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {session && !session.full_transcript && !loading && editable && (
          <section className="panel carbon-panel empty-panel">
            <p>
              Файл <strong>{session.original_name}</strong> загружен. Нажмите «Расшифровать» — аудио
              будет отправлено в Yandex SpeechKit.
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
          onSessionsDeleted={(ids) => {
            setUploadBatch((prev) => prev.filter((s) => !ids.includes(s.id)));
            if (session && ids.includes(session.id)) {
              setSession(null);
            }
          }}
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
