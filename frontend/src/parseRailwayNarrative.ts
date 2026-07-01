// parseRailwayNarrative.ts — парсер диктовки с контекстом

import type { AssetKind, ParsedRow } from "./postprocessRailwayRows";

export type { AssetKind, ParsedRow };

interface ContextState {
  location: string | null;
  assetKind: AssetKind | null;
  assetNumber: string | null;
  reference: string | null;
  note: string | null;
}

/** JS \b не работает с кириллицей — граница слова для рус/лат/цифр */

const DEFECT_RE =
  /(?:^|[^\p{L}\d])(отсутствует\s+\d+\s+(?:стыков(?:ой|ых)|закладн(?:ой|ых))\s+болт(?:а|ов)?|не\s+закручен\s+\d+\s+(?:стыков(?:ой|ых)|закладн(?:ой|ых))\s+болт(?:а|ов)?|(?:уширение|ширина)\s+колеи(?:\s+\d{3,4})*\s+\d{4}\s*мм)(?=[^\p{L}\d]|$)/giu;

function normalizeSpaces(input: string): string {
  return input
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;:])/g, "$1")
    .trim();
}

export function normalizeNarrativeText(input: string): string {
  let text = input;
  const replacers: Array<[RegExp, string]> = [
    [/(?:^|[^\p{L}\d])пусть(?=[^\p{L}\d]|$)/giu, " путь"],
    [/(?:^|[^\p{L}\d])километр(?:а|е|ов)?(?=[^\p{L}\d]|$)/giu, " км"],
    [/(?:^|[^\p{L}\d])пикет(?=[^\p{L}\d]|$)/giu, " пк"],
    [/(?:^|[^\p{L}\d])пике(?=[^\p{L}\d]|$)/giu, " пк"],
    [/(?:^|[^\p{L}\d])на\s+станции(?=[^\p{L}\d]|$)/giu, " станция"],
    [/(\d+)\s+путь(?=[^\p{L}\d]|$)/giu, "путь $1"],
    [/(?<![\p{L}]\s)(\d+)\s+звено(?=[^\p{L}\d]|$)/giu, "звено $1"],
    [/(\d{1,3})\s+метр(?:а|ов)?(?=[^\p{L}\d]|$)/giu, "$1 м"],
  ];
  for (const [re, rep] of replacers) {
    text = text.replace(re, rep);
  }
  return normalizeSpaces(text);
}

export function narrativeMatches(rawText: string): boolean {
  const text = normalizeNarrativeText(rawText);
  DEFECT_RE.lastIndex = 0;
  return DEFECT_RE.test(text);
}

function sentenceCase(value: string): string {
  const trimmed = normalizeSpaces(value);
  if (!trimmed) return trimmed;
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
}

function extractStationLocation(text: string): string | null {
  const match = text.match(
    /(?:^|[^\p{L}\d])станция\s+([\p{L}\s-]+?)(?=\s+путь\s+\d+|\s+звено\s+\d+|\s+\d{1,4}\s*км|\s+отсутствует|\s+не\s+закручен|\s+(?:уширение|ширина)\s+колеи|$)/iu
  );

  if (!match?.[1]) return null;
  return sentenceCase(match[1]);
}

function extractPerigonLocation(text: string): string | null {
  const match = text.match(
    /(?:^|[^\p{L}\d])перегон\s+(.+?)(?=\s+\d{1,4}\s*км|\s+станция|$)/iu
  );

  if (!match?.[1]) return null;
  return sentenceCase(`перегон ${match[1]}`);
}

function extractLocation(text: string): string | null {
  return extractStationLocation(text) ?? extractPerigonLocation(text);
}

function extractAsset(text: string): { kind: AssetKind; number: string } | null {
  const switchMatch = text.match(
    /(?:^|[^\p{L}\d])стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*(\d+)(?=[^\p{L}\d]|$)/iu
  );
  if (switchMatch?.[1]) {
    return { kind: "switch", number: switchMatch[1] };
  }

  const trackMatch = text.match(/(?:^|[^\p{L}\d])путь\s+(\d+)(?=[^\p{L}\d]|$)/iu);
  if (trackMatch?.[1]) {
    return { kind: "track", number: trackMatch[1] };
  }

  return null;
}

function extractReference(text: string): string | null {
  const kmMatch = text.match(/(\d{1,4})\s*км/iu);
  if (!kmMatch?.[1]) return null;

  const parts = [`${kmMatch[1]} км`];

  const pkChain = text.match(/(\d{1,3})\s*пк\s+(\d{1,2})(?:\s+(\d{1,3})\s*м)?/iu);
  if (pkChain?.[1]) {
    parts.push(`пк ${pkChain[1]}`);
    if (pkChain[3]) {
      parts.push(`${pkChain[3]} м`);
    } else if (pkChain[2]) {
      parts.push(`${pkChain[2]} м`);
    }
    return parts.join(", ");
  }

  const pkShort = text.match(/(?:^|[^\p{L}\d])пк\s*(\d{1,2})(?=[^\p{L}\d]|$)/iu);
  if (pkShort?.[1]) {
    parts.push(`пк ${pkShort[1]}`);
  }

  const meters = [...text.matchAll(/(\d{1,3})\s*м(?=[^\p{L}\d]|$)/giu)];
  if (meters.length > 0) {
    const last = meters[meters.length - 1][1];
    if (last && !parts.some((p) => p.includes(`${last} м`))) {
      parts.push(`${last} м`);
    }
  }

  return parts.length > 1 ? parts.join(", ") : parts[0];
}

function extractNote(text: string): string | null {
  const match = text.match(/(?:^|[^\p{L}\d])звено\s+(\d+)(?=[^\p{L}\d]|$)/iu);
  if (!match?.[1]) return null;
  return `звено ${match[1]}`;
}

function normalizeDefect(defect: string): string {
  const text = normalizeSpaces(defect.toLowerCase());

  let match = text.match(
    /^отсутствует\s+(\d+)\s+(стыков(?:ой|ых)|закладн(?:ой|ых))\s+болт(?:а|ов)?$/i
  );
  if (match?.[1] && match?.[2]) {
    return `отсутствует ${match[1]} ${match[2]} болт${match[1] === "1" ? "" : "а"}`;
  }

  match = text.match(
    /^не\s+закручен\s+(\d+)\s+(стыков(?:ой|ых)|закладн(?:ой|ых))\s+болт(?:а|ов)?$/i
  );
  if (match?.[1] && match?.[2]) {
    return `не закручен ${match[1]} ${match[2]} болт${match[1] === "1" ? "" : "а"}`;
  }

  match = text.match(/^(уширение|ширина)\s+колеи(?:\s+\d{3,4})*\s+(\d{4})\s*мм$/i);
  if (match?.[1] && match?.[2]) {
    return `${match[1].toLowerCase()} колеи ${match[2]} мм`;
  }

  return normalizeSpaces(defect);
}

function applyContext(prev: ContextState, chunk: string): ContextState {
  const text = normalizeNarrativeText(chunk);
  let next: ContextState = { ...prev };

  const location = extractLocation(text);
  if (location) {
    next = {
      location,
      assetKind: null,
      assetNumber: null,
      reference: null,
      note: null,
    };
  }

  const reference = extractReference(text);
  if (reference) {
    next.reference = reference;
    next.assetKind = null;
    next.assetNumber = null;
  }

  const asset = extractAsset(text);
  if (asset) {
    next.assetKind = asset.kind;
    next.assetNumber = asset.number;
    next.reference = null;
  }

  const note = extractNote(text);
  if (note) {
    next.note = note;
  }

  return next;
}

export function parseRailwayNarrative(rawText: string): ParsedRow[] {
  const text = normalizeNarrativeText(rawText);
  DEFECT_RE.lastIndex = 0;
  const matches = [...text.matchAll(DEFECT_RE)];

  if (matches.length === 0) {
    return [];
  }

  const rows: ParsedRow[] = [];
  let state: ContextState = {
    location: null,
    assetKind: null,
    assetNumber: null,
    reference: null,
    note: null,
  };

  let cursor = 0;

  for (const match of matches) {
    if (match.index === undefined) continue;

    const defectRaw = match[1] ?? match[0];
    const contextChunk = text.slice(cursor, match.index);

    state = applyContext(state, contextChunk);

    const sourceText = normalizeSpaces(`${contextChunk} ${defectRaw}`);
    const defect = normalizeDefect(defectRaw);

    rows.push({
      location: state.location,
      assetKind: state.assetKind,
      assetNumber: state.assetNumber,
      reference: state.reference,
      defect,
      speedLimit: null,
      note: state.note,
      sourceText,
      warnings: [],
    });

    cursor = match.index + match[0].length;
  }

  return rows;
}
