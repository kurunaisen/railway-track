import { z } from "zod";
import type { RailwayRow } from "./types";

const assetKindSchema = z.enum(["track", "switch"]);

export const railwayRowSchema = z.object({
  location: z.string().nullable(),
  assetKind: assetKindSchema.nullable(),
  assetNumber: z.string().nullable(),
  reference: z.string().nullable(),
  defect: z.string().nullable(),
  speedLimit: z.number().nullable(),
  note: z.string().nullable(),
  sourceText: z.string(),
  warnings: z.array(z.string()),
});

export const railwayRowsResponseSchema = z.object({
  rows: z.array(railwayRowSchema),
  warnings: z.array(z.string()).optional(),
});

export function parseRailwayRowsPayload(data: unknown): RailwayRow[] {
  if (Array.isArray(data)) {
    return z.array(railwayRowSchema).parse(data);
  }
  return railwayRowsResponseSchema.parse(data).rows;
}
