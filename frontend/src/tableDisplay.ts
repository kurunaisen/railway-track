import type { WideTable } from "./api";
import { parsedRowsFromTrackRecords } from "./parsedRowsFromRecords";
import {
  RailwayDisplayRow,
  sanitizeRowsForExport,
  toDisplayRows,
} from "./postprocessRailwayRows";
import type { TrackRecord } from "./api";

export const EVIDENCE_FORM_COLUMNS: (keyof RailwayDisplayRow)[] = [
  "Nп/п",
  "Местонахождение (перегон, станция)",
  "№ пути, стрелочного перевода",
  "Привязка (км,пк,м)",
  "Выявленная неисправность",
  "Ограничение скорости",
  "Примечание",
];

function displayRowToRecord(row: RailwayDisplayRow): Record<string, string | null> {
  const out: Record<string, string | null> = {};
  for (const col of EVIDENCE_FORM_COLUMNS) {
    const value = row[col];
    out[col] = value === undefined || value === null ? "—" : String(value);
  }
  return out;
}

/** Evidence-only таблица для UI: sanitize → toDisplayRows → WideTable */
export function buildEvidenceFormTable(records: TrackRecord[]): WideTable | null {
  if (records.length === 0) return null;

  const parsedRows = parsedRowsFromTrackRecords(records);
  const sanitizedRows = sanitizeRowsForExport(parsedRows);
  const displayRows = toDisplayRows(sanitizedRows);

  return {
    columns: [...EVIDENCE_FORM_COLUMNS],
    rows: displayRows.map(displayRowToRecord),
  };
}
