import * as XLSX from "xlsx";
import { toDisplayRows } from "./display";
import type { RailwayRow } from "./types";

export function downloadRailwayXlsx(
  rows: RailwayRow[],
  options?: { fileName?: string; sheetName?: string; includeSourceText?: boolean }
): void {
  if (typeof window === "undefined") {
    throw new Error("downloadRailwayXlsx доступен только в браузере");
  }

  const display = toDisplayRows(rows, { includeSourceText: options?.includeSourceText });
  const sheet = XLSX.utils.json_to_sheet(display);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, options?.sheetName ?? "Таблица");
  XLSX.writeFile(workbook, options?.fileName ?? "railway_table.xlsx");
}
