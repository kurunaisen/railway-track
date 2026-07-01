import type { WideTable, TrackRecord } from "./api";
import { parsedRowsFromTrackRecords } from "./parsedRowsFromRecords";
import {
  type ParsedRow,
  type RailwayDisplayRow,
  sanitizeRowsForExport,
  toDisplayRows,
} from "./postprocessRailwayRows";

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

/** ParsedRow[] → WideTable (narrative / preview) */
export function buildFormTableFromParsedRows(rows: ParsedRow[]): WideTable | null {
  if (rows.length === 0) return null;
  const sanitized = sanitizeRowsForExport(rows);
  const displayRows = toDisplayRows(sanitized);
  return {
    columns: [...EVIDENCE_FORM_COLUMNS],
    rows: displayRows.map(displayRowToRecord),
  };
}

/** Evidence-only таблица для UI: sanitize → toDisplayRows → WideTable */
export function buildEvidenceFormTable(records: TrackRecord[]): WideTable | null {
  if (records.length === 0) return null;
  return buildFormTableFromParsedRows(parsedRowsFromTrackRecords(records));
}
