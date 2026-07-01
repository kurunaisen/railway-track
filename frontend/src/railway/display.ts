import type { RailwayDisplayRow, RailwayRow } from "./types";
import { FORM_COLUMNS } from "./types";

const DASH = "—";

export function formatAssetForCell(row: RailwayRow): string {
  if (row.assetKind === "switch" && row.assetNumber) return `стр. п. ${row.assetNumber}`;
  if (row.assetKind === "track" && row.assetNumber) return row.assetNumber;
  return DASH;
}

export function formatSpeedForCell(speed: number | null): string {
  if (speed == null) return DASH;
  return `${speed} км/ч`;
}

export function toDisplayRows(
  rows: RailwayRow[],
  options?: { includeSourceText?: boolean }
): RailwayDisplayRow[] {
  return rows.map((row, index) => {
    const display: RailwayDisplayRow = {
      "Nп/п": index + 1,
      "Местонахождение (перегон, станция)": row.location ?? DASH,
      "№ пути, стрелочного перевода": formatAssetForCell(row),
      "Привязка (км,пк,м)": row.reference ?? DASH,
      "Выявленная неисправность": row.defect ?? DASH,
      "Ограничение скорости": formatSpeedForCell(row.speedLimit),
      "Примечание": row.note ?? DASH,
    };
    if (options?.includeSourceText) {
      display["Исходный текст"] = row.sourceText || DASH;
    }
    return display;
  });
}

export { FORM_COLUMNS, DASH };
