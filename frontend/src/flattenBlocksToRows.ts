import type { AssetKind, ParsedRow } from "./postprocessRailwayRows";

export interface LogicalBlock {
  location: string | null;
  assetKind: AssetKind | null;
  assetNumber: string | null;
  sourceText?: string | null;
  rows: Array<Partial<ParsedRow>>;
}

function buildRowSourceText(params: {
  location: string | null;
  assetKind: AssetKind | null;
  assetNumber: string | null;
  defect: string | null;
  note: string | null;
}): string {
  const parts: string[] = [];

  if (params.location) {
    parts.push(`станция ${params.location}`);
  }

  if (params.assetKind === "switch" && params.assetNumber) {
    parts.push(`стрелочный перевод номер ${params.assetNumber}`);
  }

  if (params.assetKind === "track" && params.assetNumber) {
    parts.push(`путь ${params.assetNumber}`);
  }

  if (params.defect) {
    parts.push(params.defect);
  }

  if (params.note) {
    parts.push(params.note);
  }

  return parts.join(" ").trim();
}

export function flattenBlocksToRows(blocks: LogicalBlock[]): ParsedRow[] {
  return blocks.flatMap((block) =>
    block.rows.map((row) => {
      const inheritedAssetKind = row.assetKind ?? block.assetKind ?? null;
      const inheritedAssetNumber = row.assetNumber ?? block.assetNumber ?? null;
      const inheritedLocation = row.location ?? block.location ?? null;

      const sourceText =
        row.sourceText && row.sourceText.trim().length > 0
          ? row.sourceText
          : buildRowSourceText({
              location: inheritedLocation,
              assetKind: inheritedAssetKind,
              assetNumber: inheritedAssetNumber,
              defect: row.defect ?? null,
              note: row.note ?? null,
            });

      return {
        location: inheritedLocation,
        assetKind: inheritedAssetKind,
        assetNumber: inheritedAssetNumber,
        reference: row.reference ?? null,
        defect: row.defect ?? null,
        speedLimit: row.speedLimit ?? null,
        note: row.note ?? null,
        sourceText,
        rawDefect: row.rawDefect ?? row.defect ?? null,
        canonicalDefect: row.canonicalDefect ?? row.defect ?? null,
        normativeDecision: null,
        warnings: row.warnings ?? [],
      };
    })
  );
}

export { buildRowSourceText };
