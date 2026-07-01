import type { AudioSession, TrackRecord, WideTable } from "./api";
import { buildEvidenceFormTable } from "./tableDisplay";

export type MergedTableView = {
  records: TrackRecord[];
  records_form: WideTable | null;
  records_wide: WideTable | null;
  positions_count: number;
  unknown_terms: AudioSession["unknown_terms"];
  validation_warnings: AudioSession["validation_warnings"];
  parse_errors: AudioSession["parse_errors"];
  session_ids: number[];
  source_names: string[];
};

function mergeWideTables(tables: WideTable[]): WideTable | null {
  if (tables.length === 0) return null;
  const columns: string[] = [];
  for (const table of tables) {
    for (const col of table.columns) {
      if (!columns.includes(col)) columns.push(col);
    }
  }
  const rows = tables.flatMap((table) =>
    table.rows.map((row) => {
      const normalized: Record<string, string | null> = {};
      for (const col of columns) {
        normalized[col] = row[col] ?? null;
      }
      return normalized;
    })
  );
  return { columns, rows };
}

function mergeUnknownTerms(sessions: AudioSession[]): AudioSession["unknown_terms"] {
  const counts = new Map<string, number>();
  for (const session of sessions) {
    for (const term of session.unknown_terms) {
      const key = (term.term || "").trim();
      if (!key) continue;
      counts.set(key, (counts.get(key) ?? 0) + (term.count || 1));
    }
  }
  return [...counts.entries()]
    .map(([term, count]) => ({ term, count }))
    .sort((a, b) => b.count - a.count);
}

function mergeRowIssues<T extends { row: number }>(
  sessions: AudioSession[],
  pick: (session: AudioSession) => T[]
): T[] {
  const merged: T[] = [];
  let offset = 0;
  for (const session of sessions) {
    for (const issue of pick(session)) {
      merged.push({
        ...issue,
        row: issue.row >= 0 ? issue.row + offset : issue.row,
      });
    }
    offset += session.records.length;
  }
  return merged;
}

/** Объединяет несколько обработанных сессий в одну таблицу (строки подряд). */
export function mergeBatchSessions(sessions: AudioSession[]): MergedTableView | null {
  const processed = sessions.filter((s) => s.records.length > 0);
  if (processed.length === 0) return null;

  if (processed.length === 1) {
    const only = processed[0];
    const records = only.records;
    return {
      records,
      records_form: buildEvidenceFormTable(records),
      records_wide: only.records_wide,
      positions_count: only.positions_count || only.records.length,
      unknown_terms: only.unknown_terms,
      validation_warnings: only.validation_warnings,
      parse_errors: only.parse_errors,
      session_ids: [only.id],
      source_names: [only.original_name],
    };
  }

  const wideTables = processed.map((s) => s.records_wide).filter(Boolean) as WideTable[];
  const records = processed.flatMap((s) => s.records);

  return {
    records,
    records_form: buildEvidenceFormTable(records),
    records_wide: mergeWideTables(wideTables),
    positions_count: processed.reduce((n, s) => n + (s.positions_count || s.records.length), 0),
    unknown_terms: mergeUnknownTerms(processed),
    validation_warnings: mergeRowIssues(processed, (s) => s.validation_warnings),
    parse_errors: mergeRowIssues(processed, (s) => s.parse_errors),
    session_ids: processed.map((s) => s.id),
    source_names: processed.map((s) => s.original_name),
  };
}

export function pickTableView(session: AudioSession | null, batch: AudioSession[]): MergedTableView | null {
  const candidates = batch.length > 0 ? batch : session ? [session] : [];
  return mergeBatchSessions(candidates);
}
