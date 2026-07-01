export type AssetKind = "track" | "switch";

export interface RailwayRow {
  location: string | null;
  assetKind: AssetKind | null;
  assetNumber: string | null;
  reference: string | null;
  defect: string | null;
  speedLimit: number | null;
  note: string | null;
  sourceText: string;
  warnings: string[];
}

export interface RailwayDisplayRow {
  "Nп/п": number;
  "Местонахождение (перегон, станция)": string;
  "№ пути, стрелочного перевода": string;
  "Привязка (км,пк,м)": string;
  "Выявленная неисправность": string;
  "Ограничение скорости": string;
  "Примечание": string;
  "Исходный текст"?: string;
}

export const FORM_COLUMNS: (keyof RailwayDisplayRow)[] = [
  "Nп/п",
  "Местонахождение (перегон, станция)",
  "№ пути, стрелочного перевода",
  "Привязка (км,пк,м)",
  "Выявленная неисправность",
  "Ограничение скорости",
  "Примечание",
];
