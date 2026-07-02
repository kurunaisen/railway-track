import { authHeaders } from "./auth";
import { apiBase } from "./config";
import type { RailwayRow } from "./railway/types";
import { parseRailwayRowsPayload } from "./railway/schema";
import { normalizeRailwayRows } from "./railway/normalizeRailwayRows";
import type { TranscriptIssue } from "./railway/transcriptQuality";

export type { RailwayRow };

export interface TrackRecord {
  id: number;
  session_id: number;
  row_order: number;
  segment_start: number | null;
  segment_end: number | null;
  raw_text: string | null;
  record_date: string | null;
  uchastok: string | null;
  peregon: string | null;
  put: string | null;
  switch: string | null;
  km: string | null;
  piket: string | null;
  obekt: string | null;
  parameter: string | null;
  value: string | null;
  unit: string | null;
  defect: string | null;
  comment: string | null;
  speed_limit: string | null;
  disputed_fields: string[];
  validation_errors: string[];
  logical_block_index: number | null;
  logical_record_index: number | null;
  position_index: number | null;
  position_type: string | null;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
  confidence?: number | null;
}

export interface LogicalRecord {
  index: number;
  peregon: string | null;
  put: string | null;
  km: string | null;
  piket: string | null;
  comment: string | null;
  segment_start: number | null;
  segment_end: number | null;
  positions_count: number;
}

export interface LogicalBlock {
  index: number;
  text: string;
  start: number | null;
  end: number | null;
  trigger: string | null;
}

export interface WideTable {
  columns: string[];
  rows: Record<string, string | null>[];
}

export interface ProcessingJob {
  id: number;
  session_id: number;
  status: string;
  current_step: number;
  error_message: string | null;
}

export interface AudioSession {
  id: number;
  filename: string;
  original_name: string;
  status: string;
  full_transcript: string | null;
  confirmed: boolean;
  asr_avg_confidence: number | null;
  created_at: string;
  updated_at: string;
  records: TrackRecord[];
  transcript_segments: TranscriptSegment[];
  logical_blocks: LogicalBlock[];
  logical_records: LogicalRecord[];
  unknown_terms: { term: string; count: number; context?: string }[];
  parse_errors: { row: number; error: string; field?: string; message?: string; text?: string; severity?: string }[];
  validation_warnings: { row: number; field: string; message: string; severity?: string }[];
  file_metadata: Record<string, unknown>;
  records_wide: WideTable | null;
  records_form: WideTable | null;
  active_job: ProcessingJob | null;
  logical_blocks_count: number;
  records_count: number;
  logical_records_count: number;
  positions_count: number;
  railway_rows: RailwayRow[];
}

export interface TranscriptCheckResponse {
  issues: TranscriptIssue[];
  unknown_terms: { term: string; count: number; context?: string }[];
  normalized_text: string;
}

export interface AsrCorrection {
  target: string;
  sources: string[];
  field: string | null;
  enabled: boolean;
  count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserDomainTerm {
  term: string;
  enabled: boolean;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

const API = apiBase();

/** Бэкенд может вернуть урезанный объект — заполняем обязательные поля, чтобы UI не падал. */
export function normalizeSession(raw: Partial<AudioSession> & Pick<AudioSession, "id">): AudioSession {
  return {
    id: raw.id,
    filename: raw.filename ?? "",
    original_name: raw.original_name ?? "",
    status: raw.status ?? "uploaded",
    full_transcript: raw.full_transcript ?? null,
    confirmed: raw.confirmed ?? false,
    asr_avg_confidence: raw.asr_avg_confidence ?? null,
    created_at: raw.created_at ?? new Date().toISOString(),
    updated_at: raw.updated_at ?? new Date().toISOString(),
    records: raw.records ?? [],
    transcript_segments: raw.transcript_segments ?? [],
    logical_blocks: raw.logical_blocks ?? [],
    logical_records: raw.logical_records ?? [],
    unknown_terms: raw.unknown_terms ?? [],
    parse_errors: raw.parse_errors ?? [],
    validation_warnings: raw.validation_warnings ?? [],
    file_metadata: raw.file_metadata ?? {},
    records_wide: raw.records_wide ?? null,
    records_form: raw.records_form ?? null,
    active_job: raw.active_job ?? null,
    logical_blocks_count: raw.logical_blocks_count ?? raw.logical_blocks?.length ?? 0,
    records_count: raw.records_count ?? raw.records?.length ?? 0,
    logical_records_count: raw.logical_records_count ?? raw.logical_records?.length ?? 0,
    positions_count: raw.positions_count ?? raw.records?.length ?? 0,
    railway_rows: raw.railway_rows ?? [],
  };
}

function formatApiError(body: string, status: number): string {
  if (!body.trim()) return `HTTP ${status}`;
  try {
    const j = JSON.parse(body) as { detail?: unknown };
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) {
      return j.detail
        .map((item) => (typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)))
        .join("; ");
    }
    return JSON.stringify(j);
  } catch {
    return body;
  }
}

async function apiFetch(url: string, init?: RequestInit) {
  const res = await fetch(url, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  });
  if (res.status === 401) throw new Error("Требуется авторизация");
  if (!res.ok) {
    const body = await res.text();
    throw new Error(formatApiError(body, res.status));
  }
  return res;
}

export async function uploadAudio(file: File): Promise<AudioSession> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch(`${API}/upload`, { method: "POST", body: form });
  return normalizeSession(await res.json());
}

export async function uploadAudioFiles(files: File[]): Promise<AudioSession[]> {
  const sessions: AudioSession[] = [];
  for (const file of files) {
    sessions.push(await uploadAudio(file));
  }
  return sessions;
}

export async function extractRailwayRows(
  transcript: string,
  sessionId?: number
): Promise<RailwayRow[]> {
  const url = sessionId
    ? `${API}/railway/sessions/${sessionId}/extract`
    : `${API}/railway/extract`;
  const res = await apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript }),
  });
  const data = await res.json();
  const rows = parseRailwayRowsPayload(data);
  return normalizeRailwayRows(rows);
}

export async function checkTranscript(transcript: string): Promise<TranscriptCheckResponse> {
  const res = await apiFetch(`${API}/transcript/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript }),
  });
  return res.json();
}

export async function listAsrCorrections(): Promise<AsrCorrection[]> {
  const res = await apiFetch(`${API}/asr-corrections`);
  return res.json();
}

export async function setAsrCorrectionEnabled(
  target: string,
  enabled: boolean,
  source?: string,
): Promise<AsrCorrection[]> {
  const res = await apiFetch(`${API}/asr-corrections`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target, enabled, source }),
  });
  return res.json();
}

export async function deleteAsrCorrection(target: string, source?: string): Promise<AsrCorrection[]> {
  const query = new URLSearchParams({ target });
  if (source) query.set("source", source);
  const res = await apiFetch(`${API}/asr-corrections?${query.toString()}`, { method: "DELETE" });
  return res.json();
}

export async function listDomainTerms(): Promise<UserDomainTerm[]> {
  const res = await apiFetch(`${API}/domain-terms`);
  return res.json();
}

export async function addDomainTerm(term: string): Promise<UserDomainTerm[]> {
  const res = await apiFetch(`${API}/domain-terms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ term }),
  });
  return res.json();
}

export async function deleteDomainTerm(term: string): Promise<UserDomainTerm[]> {
  const res = await apiFetch(`${API}/domain-terms/${encodeURIComponent(term)}`, { method: "DELETE" });
  return res.json();
}

export async function exportRailwayRowsXlsx(
  rows: RailwayRow[],
  options?: { includeSourceText?: boolean; fileName?: string }
): Promise<void> {
  const res = await apiFetch(`${API}/railway/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rows,
      include_source_text: options?.includeSourceText ?? false,
    }),
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = options?.fileName ?? "railway_table.xlsx";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function processSession(
  sessionId: number
): Promise<{ session?: AudioSession; job?: ProcessingJob; queued: boolean; message: string }> {
  const res = await apiFetch(`${API}/sessions/${sessionId}/process`, { method: "POST" });
  const data = await res.json();
  if (data.job) return { job: data.job, queued: true, message: data.message };
  return {
    session: data.session ? normalizeSession(data.session) : undefined,
    queued: false,
    message: data.message,
  };
}

export async function getJob(jobId: number): Promise<ProcessingJob> {
  const res = await apiFetch(`${API}/jobs/${jobId}`);
  return res.json();
}

export async function getSession(sessionId: number): Promise<AudioSession> {
  const res = await apiFetch(`${API}/sessions/${sessionId}`);
  return normalizeSession(await res.json());
}

export async function updateRecord(recordId: number, patch: Partial<TrackRecord>): Promise<TrackRecord> {
  const res = await apiFetch(`${API}/records/${recordId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return res.json();
}

export async function saveSession(sessionId: number): Promise<void> {
  await apiFetch(`${API}/sessions/${sessionId}/save`, { method: "POST" });
}

export async function confirmSession(sessionId: number): Promise<void> {
  await apiFetch(`${API}/sessions/${sessionId}/confirm`, { method: "POST" });
}

export function exportExcelUrl(sessionId: number): string {
  return `${API}/sessions/${sessionId}/export`;
}

export interface SessionSummary {
  id: number;
  original_name: string;
  status: string;
  created_at: string;
  updated_at: string;
  positions_count: number;
  confirmed: boolean;
  has_table: boolean;
  export_count: number;
  last_export_at: string | null;
}

export async function listSessionSummaries(): Promise<SessionSummary[]> {
  const res = await apiFetch(`${API}/sessions/summary`);
  return res.json();
}

export async function downloadSessionExcel(sessionId: number): Promise<void> {
  const res = await apiFetch(`${API}/sessions/${sessionId}/export`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `railway_session_${sessionId}.xlsx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function downloadSessionAudio(sessionId: number, suggestedName?: string): Promise<void> {
  const res = await apiFetch(`${API}/sessions/${sessionId}/audio`);
  const blob = await res.blob();
  let filename = suggestedName || `session_${sessionId}.webm`;
  const disposition = res.headers.get("Content-Disposition");
  if (disposition) {
    const starMatch = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
    const plainMatch = /filename="([^"]+)"/i.exec(disposition);
    if (starMatch) filename = decodeURIComponent(starMatch[1]);
    else if (plainMatch) filename = plainMatch[1];
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function deleteSession(sessionId: number): Promise<void> {
  await apiFetch(`${API}/sessions/${sessionId}`, { method: "DELETE" });
}

export async function deleteSessionsBatch(sessionIds: number[]): Promise<void> {
  if (sessionIds.length === 0) return;
  // Delete one-by-one to avoid server/proxy timeouts when storage cleanup is slow.
  for (const sessionId of sessionIds) {
    await deleteSession(sessionId);
  }
}

export async function downloadBatchExcel(sessionIds: number[]): Promise<void> {
  if (sessionIds.length === 0) return;
  if (sessionIds.length === 1) {
    await downloadSessionExcel(sessionIds[0]);
    return;
  }
  const query = encodeURIComponent(sessionIds.join(","));
  const res = await apiFetch(`${API}/sessions/export-batch?session_ids=${query}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `railway_batch_${sessionIds.length}_sessions.xlsx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function formatTime(seconds: number | null): string {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export const EDITABLE_FIELDS = [
  "record_date", "uchastok", "peregon", "put", "km", "piket", "obekt",
  "parameter", "value", "unit", "defect", "comment", "speed_limit",
] as const;

export type EditableField = (typeof EDITABLE_FIELDS)[number];

export const FIELD_LABELS: Record<EditableField, string> = {
  record_date: "Дата", uchastok: "Участок", peregon: "Перегон", put: "Путь",
  km: "Км", piket: "Пикет", obekt: "Объект", parameter: "Параметр",
  value: "Значение", unit: "Ед.", defect: "Дефект", comment: "Комментарий",
  speed_limit: "V огр.",
};

export const PIPELINE_STEPS = [
  "Загрузка",
  "Предобработка",
  "Yandex SpeechKit",
  "Transcript готов",
];

export function canEdit(role: string): boolean {
  return role === "admin" || role === "operator";
}

export function isAdmin(role: string): boolean {
  return role === "admin";
}

export function fieldLabel(field: string): string {
  return FIELD_LABELS[field as EditableField] || field;
}

export function issueText(issue: {
  error?: string;
  message?: string;
  field?: string;
}): string {
  const text = (issue.error || issue.message || "").trim();
  if (!text) return "—";
  const field = issue.field && issue.field !== "general" ? fieldLabel(issue.field) : null;
  return field ? `${field}: ${text}` : text;
}
