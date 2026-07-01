// railwayExcel.ts — экспорт в .xlsx

import * as XLSX from "xlsx";
import {
  ParsedRow,
  RailwayDisplayRow,
  sanitizeRowsForExport,
  toDisplayRows,
} from "./postprocessRailwayRows";

export interface RailwayExcelOptions {
  fileName?: string;
  sheetName?: string;
  includeSourceText?: boolean;
}

const DEFAULT_FILE_NAME = "railway-defects.xlsx";
const DEFAULT_SHEET_NAME = "Ведомость";

function buildHeaders(includeSourceText = false): string[] {
  const headers = [
    "Nп/п",
    "Местонахождение (перегон, станция)",
    "№ пути, стрелочного перевода",
    "Привязка (км,пк,м)",
    "Выявленная неисправность",
    "Ограничение скорости",
    "Примечание",
  ];

  if (includeSourceText) {
    headers.push("Исходный текст");
  }

  return headers;
}

function displayRowsToAoA(
  rows: RailwayDisplayRow[],
  includeSourceText = false
): Array<Array<string | number>> {
  return rows.map((row) => {
    const line: Array<string | number> = [
      row["Nп/п"],
      row["Местонахождение (перегон, станция)"],
      row["№ пути, стрелочного перевода"],
      row["Привязка (км,пк,м)"],
      row["Выявленная неисправность"],
      row["Ограничение скорости"],
      row["Примечание"],
    ];

    if (includeSourceText) {
      line.push(row["Исходный текст"] ?? "—");
    }

    return line;
  });
}

function buildColumnWidths(includeSourceText = false): XLSX.ColInfo[] {
  const cols: XLSX.ColInfo[] = [
    { wch: 8 },
    { wch: 28 },
    { wch: 22 },
    { wch: 18 },
    { wch: 38 },
    { wch: 20 },
    { wch: 28 },
  ];

  if (includeSourceText) {
    cols.push({ wch: 60 });
  }

  return cols;
}

export function buildRailwayWorkbook(
  rows: ParsedRow[],
  options: RailwayExcelOptions = {}
): XLSX.WorkBook {
  const includeSourceText = options.includeSourceText ?? false;

  const sanitized = sanitizeRowsForExport(rows);
  const displayRows = toDisplayRows(sanitized, { includeSourceText });

  const headers = buildHeaders(includeSourceText);
  const body = displayRowsToAoA(displayRows, includeSourceText);

  const worksheet = XLSX.utils.aoa_to_sheet([headers, ...body]);

  worksheet["!cols"] = buildColumnWidths(includeSourceText);
  worksheet["!autofilter"] = {
    ref: XLSX.utils.encode_range({
      s: { r: 0, c: 0 },
      e: { r: body.length, c: headers.length - 1 },
    }),
  };

  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(
    workbook,
    worksheet,
    options.sheetName ?? DEFAULT_SHEET_NAME
  );

  return workbook;
}

/** Для браузера: скачивание xlsx-файла */
export function downloadRailwayRowsXlsx(
  rows: ParsedRow[],
  options: RailwayExcelOptions = {}
): void {
  if (typeof window === "undefined") {
    throw new Error("downloadRailwayRowsXlsx можно использовать только в браузере");
  }

  const workbook = buildRailwayWorkbook(rows, options);
  XLSX.writeFileXLSX(workbook, options.fileName ?? DEFAULT_FILE_NAME);
}

/** Универсально: бинарник xlsx как Uint8Array (API route / server response / storage) */
export function railwayRowsWorkbookToUint8Array(
  rows: ParsedRow[],
  options: RailwayExcelOptions = {}
): Uint8Array {
  const workbook = buildRailwayWorkbook(rows, options);
  const arrayBuffer = XLSX.write(workbook, {
    bookType: "xlsx",
    type: "array",
  }) as ArrayBuffer;

  return new Uint8Array(arrayBuffer);
}

/** Для Node.js: сохранить xlsx в файл */
export function saveRailwayRowsXlsxNode(
  rows: ParsedRow[],
  filePath: string,
  options: RailwayExcelOptions = {}
): void {
  const workbook = buildRailwayWorkbook(rows, options);
  XLSX.writeFileXLSX(workbook, filePath);
}
