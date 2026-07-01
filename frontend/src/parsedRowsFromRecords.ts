import type { TrackRecord } from "./api";
import type { AssetKind, ParsedRow } from "./postprocessRailwayRows";
import { buildRowSourceText } from "./flattenBlocksToRows";

function detectSwitchNumber(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const match = raw.match(
    /\bстрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*(\d+)\b/i
  );
  return match?.[1] ?? null;
}

function detectPathNumber(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const match = raw.match(/\bпуть\s+(\d+)\b/i);
  return match?.[1] ?? null;
}

function resolveAsset(rec: TrackRecord): { assetKind: AssetKind | null; assetNumber: string | null } {
  const put = rec.put?.trim() || null;
  const switchField = rec.switch?.trim() || null;
  const raw = rec.raw_text ?? "";

  if (put) {
    return { assetKind: "track", assetNumber: put };
  }
  if (switchField) {
    return { assetKind: "switch", assetNumber: switchField };
  }

  const switchFromText = detectSwitchNumber(raw);
  if (switchFromText) {
    return { assetKind: "switch", assetNumber: switchFromText };
  }

  const pathFromText = detectPathNumber(raw);
  if (pathFromText) {
    return { assetKind: "track", assetNumber: pathFromText };
  }

  return { assetKind: null, assetNumber: null };
}

/** TrackRecord (API) → ParsedRow для postprocessRailwayRows */
export function parsedRowFromTrackRecord(rec: TrackRecord): ParsedRow {
  const { assetKind, assetNumber } = resolveAsset(rec);

  const referenceParts: string[] = [];
  if (rec.km?.trim()) referenceParts.push(`${rec.km.trim()} км`);
  if (rec.piket?.trim()) referenceParts.push(`пк ${rec.piket.trim()}`);

  let speedLimit: number | string | null = null;
  if (rec.speed_limit?.trim()) {
    const parsed = Number(rec.speed_limit.trim());
    speedLimit = Number.isFinite(parsed) ? parsed : rec.speed_limit.trim();
  }

  const location = rec.uchastok ?? rec.peregon ?? null;
  const rawText = rec.raw_text?.trim() ?? "";
  const hasAssetInSource =
    assetKind === "switch"
      ? Boolean(detectSwitchNumber(rawText))
      : assetKind === "track"
        ? Boolean(detectPathNumber(rawText))
        : false;

  const sourceText =
    assetKind && assetNumber && (!rawText || !hasAssetInSource)
      ? buildRowSourceText({
          location,
          assetKind,
          assetNumber,
          defect: rec.defect ?? null,
          note: rec.comment ?? null,
        })
      : rawText;

  return {
    location,
    assetKind,
    assetNumber,
    reference: referenceParts.length > 0 ? referenceParts.join(", ") : null,
    defect: rec.defect ?? null,
    speedLimit,
    note: rec.comment ?? null,
    sourceText,
    warnings: [],
  };
}

export function parsedRowsFromTrackRecords(records: TrackRecord[]): ParsedRow[] {
  return records.map(parsedRowFromTrackRecord);
}
