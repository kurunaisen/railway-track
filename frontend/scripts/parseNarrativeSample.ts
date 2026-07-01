/**
 * Пример parseRailwayNarrative — запуск: npx tsx scripts/parseNarrativeSample.ts
 */
import { parseRailwayNarrative } from "../src/parseRailwayNarrative";
import { sanitizeRowsForExport, toDisplayRows } from "../src/postprocessRailwayRows";

const SAMPLE =
  "перегон апатиты оленья 1381 километр 385 пк 5 85 метр отсутствует 1 стыковой болт " +
  "станция апатиты 2 путь 1 звено уширение колеи 1544 мм";

const rows = sanitizeRowsForExport(parseRailwayNarrative(SAMPLE));

console.log("--- parseRailwayNarrative → sanitize → display ---\n");
rows.forEach((row, i) => {
  console.log(`ROW ${i + 1}:`);
  console.log("  location:", row.location);
  console.log("  asset:", row.assetKind, row.assetNumber);
  console.log("  reference:", row.reference);
  console.log("  defect:", row.defect);
  console.log("  note:", row.note);
  console.log("  sourceText:", row.sourceText);
  console.log("");
});

const display = toDisplayRows(rows);
console.log("Display row 1:", display[0]);
