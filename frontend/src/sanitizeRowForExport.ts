export type ParsedRow = {
  location: string | null;
  assetKind: "track" | "switch" | null;
  assetNumber: string | null;
  reference: string | null;
  defect: string | null;
  speedLimit: number | string | null;
  note: string | null;
  sourceText: string;
};

function normalizeSpaces(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function normalizeAsrText(text: string): string {
  return normalizeSpaces(
    text
      .replace(/\bпусть\b/gi, "путь")
      .replace(/\bколи\b/gi, "колеи")
      .replace(/\bострии\s+остряка\b/gi, "острие остряка")
      .replace(/\bстр[.\s]*п[.\s]?\b/gi, "стрелочный перевод ")
  );
}

export function dashIfEmpty(value: string | null | undefined): string {
  if (!value) return "—";
  const v = normalizeSpaces(value);
  return v ? v : "—";
}

function removeDuplicateNotePhrases(note: string | null): string | null {
  if (!note) return null;
  const normalized = normalizeAsrText(note.toLowerCase())
    .replace(/[.;,]+/g, ".")
    .split(".")
    .map((s) => normalizeSpaces(s))
    .filter(Boolean);

  const seen = new Set<string>();
  const result: string[] = [];

  for (const part of normalized) {
    const key = part
      .replace(/\bв\s+острии\s+остряка\b/g, "в острие остряка")
      .replace(/\bв\s+острие\s+остряка\b/g, "в острие остряка");

    if (!seen.has(key)) {
      seen.add(key);
      result.push(key);
    }
  }

  if (result.length === 0) return null;
  return result.join(". ");
}

function containsExplicitSpeed(source: string): boolean {
  return /\b\d+\s*км\/?ч\b/i.test(source) || /\bограничени[ея]\s+скорост[ьи]\b/i.test(source);
}

function removeSyntheticNote(note: string | null, source: string): string | null {
  if (!note) return null;

  const syntheticPatterns = [
    /2288\s*р/i,
    /движение\s+закрыва(?:ется|ть)/i,
    /закрытие\s+движения/i,
    /ограничение\s+скорости/i,
  ];

  const noteHasSynthetic = syntheticPatterns.some((re) => re.test(note));
  const sourceHasSynthetic = syntheticPatterns.some((re) => re.test(source));

  if (noteHasSynthetic && !sourceHasSynthetic) {
    return null;
  }

  return note;
}

function extractDeterministicDefect(source: string): { defect: string | null; note: string | null } {
  const text = normalizeAsrText(source);
  let m: RegExpMatchArray | null = null;

  m = text.match(/износ\s+рамного\s+рельса\s+(\d+)\s*мм/i);
  if (m) {
    const note = /остри[ея]\s+остряка/i.test(text) ? "в острие остряка" : null;
    return {
      defect: `износ рамного рельса ${m[1]} мм`,
      note,
    };
  }

  m = text.match(/ширин[аы]\s+коле[иы]\s+(\d+)\s*мм/i);
  if (m) {
    return {
      defect: `ширина колеи ${m[1]} мм`,
      note: null,
    };
  }

  m = text.match(/(\d+)\s+подряд\s+куста\s+из\s+(\d+)\s+шпал/i);
  if (m) {
    return {
      defect: `${m[1]} подряд куста из ${m[2]} шпал`,
      note: null,
    };
  }

  m = text.match(/куст(?:\s+из)?\s+(\d+)\s+негодных\s+шпал/i);
  if (m) {
    return {
      defect: `куст из ${m[1]} негодных шпал`,
      note: null,
    };
  }

  return { defect: null, note: null };
}

export function sanitizeRowForExport(row: ParsedRow): ParsedRow {
  const source = normalizeAsrText(row.sourceText || "");
  const out: ParsedRow = { ...row };

  if (!containsExplicitSpeed(source)) {
    out.speedLimit = null;
  }

  out.note = removeSyntheticNote(out.note, source);

  const deterministic = extractDeterministicDefect(source);
  if (deterministic.defect) {
    out.defect = deterministic.defect;
  }

  if (deterministic.note) {
    out.note = deterministic.note;
  }

  if (out.defect && /шпал/i.test(out.defect)) {
    out.defect = out.defect.replace(/\s+\d+\s*мм\b/gi, "").trim();
  }

  if (out.defect && !/сужение|уширение|движение\s+закрыва/i.test(source)) {
    const widthMatch = source.match(/ширин[аы]\s+коле[иы]\s+(\d+)\s*мм/i);
    if (widthMatch) {
      out.defect = `ширина колеи ${widthMatch[1]} мм`;
    }
  }

  out.note = removeDuplicateNotePhrases(out.note);

  out.defect = out.defect ? normalizeSpaces(out.defect) : null;
  out.note = out.note ? normalizeSpaces(out.note) : null;

  return out;
}
