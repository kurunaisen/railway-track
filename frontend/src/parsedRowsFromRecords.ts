import type { TrackRecord } from "./api";
import type { AssetKind, ParsedRow } from "./postprocessRailwayRows";

function detectSwitchNumber(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const match = raw.match(
    /\bстрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*(\d+)\b/i
  );
  return match?.[1] ?? null;
}

/** TrackRecord (API) → ParsedRow для postprocessRailwayRows */
export function parsedRowFromTrackRecord(rec: TrackRecord): ParsedRow {
  let assetKind: AssetKind | null = null;
  let assetNumber: string | null = null;

  const put = rec.put?.trim();
  const switchNum = detectSwitchNumber(rec.raw_text);

  if (put) {
    assetKind = "track";
    assetNumber = put;
  } else if (switchNum) {
    assetKind = "switch";
    assetNumber = switchNum;
  }

  const referenceParts: string[] = [];
  if (rec.km?.trim()) referenceParts.push(`${rec.km.trim()} км`);
  if (rec.piket?.trim()) referenceParts.push(`пк ${rec.piket.trim()}`);

  let speedLimit: number | string | null = null;
  if (rec.speed_limit?.trim()) {
    const parsed = Number(rec.speed_limit.trim());
    speedLimit = Number.isFinite(parsed) ? parsed : rec.speed_limit.trim();
  }

  return {
    location: rec.uchastok ?? rec.peregon ?? null,
    assetKind,
    assetNumber,
    reference: referenceParts.length > 0 ? referenceParts.join(", ") : null,
    defect: rec.defect ?? null,
    speedLimit,
    note: rec.comment ?? null,
    sourceText: rec.raw_text ?? "",
    warnings: [],
  };
}

export function parsedRowsFromTrackRecords(records: TrackRecord[]): ParsedRow[] {
  return records.map(parsedRowFromTrackRecord);
}
