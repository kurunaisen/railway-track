/**
 * Локальная проверка sourceText по строкам (сценарий Мурманск).
 * Запуск: npx tsx scripts/logRowSources.ts
 */
import { parsedRowsFromTrackRecords } from "../src/parsedRowsFromRecords";
import { sanitizeRowsForExport } from "../src/postprocessRailwayRows";
import type { TrackRecord } from "../src/api";

function base(overrides: Partial<TrackRecord>): TrackRecord {
  return {
    id: 0,
    session_id: 1,
    row_order: 0,
    segment_start: null,
    segment_end: null,
    raw_text: null,
    record_date: null,
    uchastok: "Мурманск",
    peregon: null,
    put: null,
    switch: null,
    km: null,
    piket: null,
    obekt: null,
    parameter: null,
    value: null,
    unit: null,
    defect: null,
    comment: null,
    speed_limit: null,
    disputed_fields: [],
    validation_errors: [],
    logical_block_index: 0,
    logical_record_index: 0,
    position_index: 0,
    position_type: "defect",
    ...overrides,
  };
}

/** Как в проде: switch в поле, raw_text — только дефект без маркера объекта */
const murmanskLike: TrackRecord[] = [
  base({
    id: 1,
    row_order: 0,
    switch: "10",
    raw_text: "износ рамного рельса 7 мм",
    defect: "износ рамного рельса 7 мм",
    value: "7",
    unit: "мм",
    comment: "в острие остряка",
  }),
  base({
    id: 2,
    row_order: 1,
    put: "15",
    raw_text: "путь 15 ширина колеи 1544 мм",
    defect: "ширина колеи 1544 мм",
    value: "1544",
    unit: "мм",
  }),
  base({
    id: 3,
    row_order: 2,
    put: "12",
    raw_text: "путь 12 3 подряд куста из 3 шпал",
    defect: "3 подряд куста из 3 шпал",
  }),
  base({
    id: 4,
    row_order: 3,
    put: "11",
    raw_text: "путь 11 куст из 5 негодных шпал",
    defect: "куст из 5 негодных шпал",
  }),
];

const rows = sanitizeRowsForExport(parsedRowsFromTrackRecords(murmanskLike));

console.log("--- Мурманск (switch=10 в поле, raw_text без «стрелочный перевод») ---\n");
rows.forEach((row, i) => {
  console.log(`ROW ${i + 1} sourceText =`, row.sourceText);
  console.log(`       asset =`, row.assetKind, row.assetNumber);
  console.log(`       defect =`, row.defect);
  console.log("");
});
