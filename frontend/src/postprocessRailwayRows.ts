// postprocessRailwayRows.ts — жёсткая evidence-only постобработка

export type AssetKind = "track" | "switch";

export interface ParsedRow {
  location: string | null;
  assetKind: AssetKind | null;
  assetNumber: string | null;
  reference: string | null;
  defect: string | null;
  speedLimit: number | string | null;
  note: string | null;
  sourceText: string;
  rawDefect?: string | null;
  canonicalDefect?: string | null;
  normativeDecision?: string | null;
  warnings?: string[];
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

const DASH = "—";

const SYNTHETIC_NOTE_PATTERNS: RegExp[] = [
  /2288\s*р/i,
  /движение\s+закрыва(?:ется|ть|ют)/i,
  /закрытие\s+движения/i,
  /запрещается\s+движение/i,
  /ограничение\s+скорости/i,
];

const QUALIFIER_RULES: Array<{ pattern: RegExp; canonical: string }> = [
  {
    pattern: /\b(?:в|на)?\s*остри[ея]\s+остряка\b/gi,
    canonical: "в острие остряка",
  },
  {
    pattern: /\bпо\s+прямому\s+направлению\b/gi,
    canonical: "по прямому направлению",
  },
  {
    pattern: /\bпо\s+боковому\s+направлению\b/gi,
    canonical: "по боковому направлению",
  },
  {
    pattern: /\bна\s+крестовине\b/gi,
    canonical: "на крестовине",
  },
  {
    pattern: /\bна\s+усовике\b/gi,
    canonical: "на усовике",
  },
];

export function normalizeSpaces(input: string): string {
  return input
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;:])/g, "$1")
    .trim();
}

export function normalizeAsrText(input: string): string {
  return normalizeSpaces(
    input
      .replace(/\bпусть\b/gi, "путь")
      .replace(/\bколи\b/gi, "колеи")
      .replace(/\bстр[.\s]*п[.\s]?\b/gi, "стрелочный перевод ")
      .replace(/\bострии\s+остряка\b/gi, "острие остряка")
  );
}

export function dashIfEmpty(value: string | null | undefined): string {
  if (!value) return DASH;
  const normalized = normalizeSpaces(value);
  return normalized.length > 0 ? normalized : DASH;
}

function toTitleCaseRu(value: string): string {
  return value
    .split(/\s+/)
    .map((word) =>
      word
        .split("-")
        .map((part) =>
          part ? part.charAt(0).toUpperCase() + part.slice(1).toLowerCase() : part
        )
        .join("-")
    )
    .join(" ");
}

export function countAssetMarkers(sourceText: string): number {
  const text = normalizeAsrText(sourceText);
  const matches = text.match(
    /\b(?:путь\s+\d+|стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+)\b/gi
  );
  return matches?.length ?? 0;
}

export function detectLocationFromSource(sourceText: string): string | null {
  const text = normalizeAsrText(sourceText);

  const match = text.match(
    /\bстанц(?:ия|ии)\s+(.+?)(?=\s+(?:путь\s+\d+|стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+)|$)/i
  );

  if (!match?.[1]) return null;

  const location = normalizeSpaces(match[1])
    .replace(/[.,;:]+$/g, "")
    .trim();

  return location ? toTitleCaseRu(location) : null;
}

export function detectAssetFromSource(
  sourceText: string
): { kind: AssetKind; number: string } | null {
  const text = normalizeAsrText(sourceText);

  const switchMatch = text.match(
    /\bстрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*(\d+)\b/i
  );
  if (switchMatch?.[1]) {
    return { kind: "switch", number: switchMatch[1] };
  }

  const trackMatch = text.match(/\bпуть\s+(\d+)\b/i);
  if (trackMatch?.[1]) {
    return { kind: "track", number: trackMatch[1] };
  }

  return null;
}

export function formatAssetForCell(
  assetKind: AssetKind | null,
  assetNumber: string | null
): string {
  if (!assetKind || !assetNumber) return DASH;
  return assetKind === "switch" ? `стр. п. ${assetNumber}` : assetNumber;
}

export function parseExplicitSpeed(sourceText: string): number | null {
  const text = normalizeAsrText(sourceText);

  let match = text.match(/\b(\d+)\s*км\/?\s*ч\b/i);
  if (match?.[1]) return Number(match[1]);

  match = text.match(
    /\b(?:ограничени[ея]\s+скорост[ьи]|скорост[ьи])\s*(?:до|не\s+более)?\s*(\d+)\b/i
  );
  if (match?.[1]) return Number(match[1]);

  return null;
}

export function containsExplicitSpeed(sourceText: string): boolean {
  return parseExplicitSpeed(sourceText) !== null;
}

function splitNoteParts(note: string): string[] {
  return note
    .replace(/[;]+/g, ".")
    .split(/[.]+/g)
    .map((part) => normalizeSpaces(part))
    .filter(Boolean);
}

function canonicalizeNotePart(part: string): string {
  let value = normalizeAsrText(part.toLowerCase())
    .replace(/[.,;:]+$/g, "")
    .trim();

  value = value
    .replace(/\bострие\s+остряка\b/g, "в острие остряка")
    .replace(/\bв\s+в\s+/g, "в ")
    .replace(/\bна\s+острие\s+остряка\b/g, "в острие остряка")
    .replace(/\bв\s+острии\s+остряка\b/g, "в острие остряка");

  return normalizeSpaces(value);
}

function dedupeNoteParts(parts: string[]): string | null {
  const result: string[] = [];
  const seen = new Set<string>();

  for (const part of parts) {
    const canonical = canonicalizeNotePart(part);
    if (!canonical) continue;
    if (seen.has(canonical)) continue;
    seen.add(canonical);
    result.push(canonical);
  }

  return result.length > 0 ? result.join(". ") : null;
}

function removeSyntheticNoteParts(note: string | null, sourceText: string): string | null {
  if (!note) return null;

  const source = normalizeAsrText(sourceText);
  const sourceContainsSynthetic = SYNTHETIC_NOTE_PATTERNS.some((re) => re.test(source));

  const filtered = splitNoteParts(note).filter((part) => {
    const isSynthetic = SYNTHETIC_NOTE_PATTERNS.some((re) => re.test(part));
    return sourceContainsSynthetic || !isSynthetic;
  });

  return dedupeNoteParts(filtered);
}

function extractQualifiersFromText(text: string): { cleanText: string; qualifiers: string[] } {
  let clean = normalizeSpaces(text);
  const qualifiers: string[] = [];

  for (const rule of QUALIFIER_RULES) {
    if (rule.pattern.test(clean)) {
      qualifiers.push(rule.canonical);
      clean = clean.replace(rule.pattern, " ");
      clean = normalizeSpaces(clean);
    }
    rule.pattern.lastIndex = 0;
  }

  clean = clean
    .replace(/\s+[.,;:]/g, "")
    .replace(/[.,;:]+$/g, "")
    .trim();

  return {
    cleanText: normalizeSpaces(clean),
    qualifiers,
  };
}

function stripLeadingContext(defect: string): string {
  let value = defect;

  value = value.replace(
    /\bстанц(?:ия|ии)\s+.+?(?=\s+(?:путь\s+\d+|стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+)|$)/i,
    " "
  );

  value = value.replace(
    /\b(?:путь\s+\d+|стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+)\b/gi,
    " "
  );

  return normalizeSpaces(value);
}

function normalizeDefectPunctuation(value: string): string {
  return normalizeSpaces(
    value
      .replace(/[;]+/g, " ")
      .replace(/\s+[.,:]/g, "")
      .replace(/[.,:]+$/g, "")
  );
}

function normalizeSleeperDefectLeak(defect: string): string {
  if (!/шпал/i.test(defect)) return defect;
  return normalizeSpaces(defect.replace(/\s+\d+\s*мм\b/gi, ""));
}

function normalizeLocationValue(
  explicitLocation: string | null | undefined,
  sourceText: string
): string | null {
  const fromRow = explicitLocation ? normalizeSpaces(explicitLocation) : "";
  if (fromRow) return toTitleCaseRu(fromRow);
  return detectLocationFromSource(sourceText);
}

function normalizeReferenceValue(reference: string | null | undefined): string | null {
  if (!reference) return null;
  const normalized = normalizeSpaces(reference);
  return normalized || null;
}

function extractDeterministicDefect(sourceText: string): {
  defect: string | null;
  note: string | null;
} {
  const text = normalizeAsrText(sourceText);

  let match = text.match(/износ\s+рамного\s+рельса\s+(\d+)\s*мм/i);
  if (match?.[1]) {
    const note = /\bостри[ея]\s+остряка\b/i.test(text) ? "в острие остряка" : null;
    return {
      defect: `износ рамного рельса ${match[1]} мм`,
      note,
    };
  }

  match = text.match(/ширин[аы]\s+коле[иы]\s+(\d+)\s*мм/i);
  if (match?.[1]) {
    return {
      defect: `ширина колеи ${match[1]} мм`,
      note: null,
    };
  }

  match = text.match(/(\d+)\s+подряд\s+куста\s+из\s+(\d+)\s+шпал/i);
  if (match?.[1] && match?.[2]) {
    return {
      defect: `${match[1]} подряд куста из ${match[2]} шпал`,
      note: null,
    };
  }

  match = text.match(/куст(?:\s+из)?\s+(\d+)\s+негодных\s+шпал/i);
  if (match?.[1]) {
    return {
      defect: `куст из ${match[1]} негодных шпал`,
      note: null,
    };
  }

  return { defect: null, note: null };
}

function formatSpeedForCell(speedLimit: number | string | null): string {
  if (speedLimit === null || speedLimit === undefined || speedLimit === "") return DASH;

  if (typeof speedLimit === "number") {
    return `${speedLimit} км/ч`;
  }

  const normalized = normalizeSpaces(String(speedLimit));
  if (!normalized) return DASH;

  if (/^\d+$/.test(normalized)) {
    return `${normalized} км/ч`;
  }

  return normalized;
}

export function sanitizeRowForExport(row: ParsedRow): ParsedRow {
  const source = normalizeAsrText(row.sourceText || "");
  const assetMarkerCount = countAssetMarkers(source);

  const warnings = [...(row.warnings ?? [])];

  if (assetMarkerCount > 1) {
    warnings.push(
      "sourceText содержит несколько объектов; для корректной постобработки нужен сегмент одной строки"
    );
  }

  const sourceLooksLikeSingleSegment = assetMarkerCount <= 1;

  const detectedAsset = sourceLooksLikeSingleSegment ? detectAssetFromSource(source) : null;
  const normalizedAssetKind = detectedAsset?.kind ?? row.assetKind ?? null;
  const normalizedAssetNumber = detectedAsset?.number ?? row.assetNumber ?? null;

  const normalizedLocation = normalizeLocationValue(row.location, source);
  const normalizedReference = normalizeReferenceValue(row.reference);

  const explicitSpeed = sourceLooksLikeSingleSegment ? parseExplicitSpeed(source) : null;
  const normalizedSpeed = explicitSpeed !== null ? explicitSpeed : null;

  const noteParts: string[] = [];

  const initialNote = removeSyntheticNoteParts(row.note ?? null, source);
  if (initialNote) {
    noteParts.push(...splitNoteParts(initialNote));
  }

  let defectFromRow = row.defect ? normalizeDefectPunctuation(stripLeadingContext(row.defect)) : null;

  if (defectFromRow) {
    const extracted = extractQualifiersFromText(defectFromRow);
    defectFromRow = extracted.cleanText || null;
    noteParts.push(...extracted.qualifiers);
  }

  let finalDefect = defectFromRow;

  if (sourceLooksLikeSingleSegment) {
    const deterministic = extractDeterministicDefect(source);

    if (deterministic.defect) {
      finalDefect = deterministic.defect;
    }

    if (deterministic.note) {
      noteParts.push(deterministic.note);
    }

    const gaugeMatch = source.match(/ширин[аы]\s+коле[иы]\s+(\d+)\s*мм/i);
    if (gaugeMatch?.[1]) {
      finalDefect = `ширина колеи ${gaugeMatch[1]} мм`;
    }
  }

  if (finalDefect) {
    finalDefect = normalizeDefectPunctuation(finalDefect);
    finalDefect = normalizeSleeperDefectLeak(finalDefect);
  }

  const finalNote = dedupeNoteParts(noteParts);

  return {
    ...row,
    location: normalizedLocation,
    assetKind: normalizedAssetKind,
    assetNumber: normalizedAssetNumber,
    reference: normalizedReference,
    defect: finalDefect || null,
    speedLimit: normalizedSpeed,
    note: finalNote,
    sourceText: source,
    rawDefect: row.rawDefect ?? row.defect ?? null,
    canonicalDefect: finalDefect || null,
    normativeDecision: null,
    warnings,
  };
}

export function sanitizeRowsForExport(rows: ParsedRow[]): ParsedRow[] {
  return rows.map(sanitizeRowForExport);
}

export function toDisplayRows(
  rows: ParsedRow[],
  options?: { includeSourceText?: boolean }
): RailwayDisplayRow[] {
  const sanitized = sanitizeRowsForExport(rows);

  return sanitized.map((row, index) => {
    const result: RailwayDisplayRow = {
      "Nп/п": index + 1,
      "Местонахождение (перегон, станция)": dashIfEmpty(row.location),
      "№ пути, стрелочного перевода": formatAssetForCell(row.assetKind, row.assetNumber),
      "Привязка (км,пк,м)": dashIfEmpty(row.reference),
      "Выявленная неисправность": dashIfEmpty(row.defect),
      "Ограничение скорости": formatSpeedForCell(row.speedLimit),
      "Примечание": dashIfEmpty(row.note),
    };

    if (options?.includeSourceText) {
      result["Исходный текст"] = dashIfEmpty(row.sourceText);
    }

    return result;
  });
}