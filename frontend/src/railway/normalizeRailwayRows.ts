import type { RailwayRow } from "./types";

function trim(value: string | null | undefined): string | null {
  if (value == null) return null;
  const text = value.replace(/\s+/g, " ").trim();
  return text || null;
}

function sentenceCase(value: string | null | undefined): string | null {
  const text = trim(value);
  if (!text) return null;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function dedupeNote(note: string | null | undefined): string | null {
  const text = trim(note);
  if (!text) return null;
  const parts = text.split(/[.;]+/).map((p) => p.trim()).filter(Boolean);
  const seen = new Set<string>();
  const unique: string[] = [];
  for (const part of parts) {
    const key = part.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(part);
  }
  return unique.length > 0 ? unique.join(". ") : null;
}

export function normalizeRailwayRow(row: RailwayRow): RailwayRow {
  const warnings = row.warnings.map((w) => trim(w)).filter(Boolean) as string[];
  let speedLimit = row.speedLimit;
  if (speedLimit != null && speedLimit <= 0) {
    speedLimit = null;
    warnings.push("speedLimit ignored: non-positive value");
  }

  return {
    location: sentenceCase(row.location),
    assetKind: row.assetKind,
    assetNumber: trim(row.assetNumber),
    reference: trim(row.reference),
    defect: trim(row.defect),
    speedLimit,
    note: dedupeNote(row.note),
    sourceText: trim(row.sourceText) ?? "",
    warnings,
  };
}

export function normalizeRailwayRows(rows: RailwayRow[]): RailwayRow[] {
  return rows.map(normalizeRailwayRow);
}
