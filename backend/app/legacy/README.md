# Legacy pipeline (v1)

These modules are **not used** by the v2 runtime path (`audio → Yandex SpeechKit → editable transcript → LLM extract → RailwayRow[] → Excel`).

## Disconnected from runtime

- `services/parsing_pipeline.py` — regex + narrative + segment LLM (legacy)
- `services/parser.py`, `canonical_model.py`, `record_expander.py`, `segmentation.py`
- `services/parse_railway_narrative.py`, `row_segment_extract.py`, `railway_segment.py`
- `services/postprocess_railway_rows.py`, `sanitize_row_for_export.py`, `evidence_only.py`
- `services/asr_pipeline.py`, `normalizer.py`, `validator.py`, `segment_reconcile.py`
- `services/llm/segment_llm_parser.py`, `openai_parser.py` (legacy segment LLM)
- `services/excel_export.py` (multi-sheet DB export) — AccountPanel history only
- `services/inspection_form.py`, `wide_table.py` (server-side table rebuild)

## v2 active modules

- `services/speech/transcribe_with_yandex.py`
- `services/llm/provider.py`, `services/llm/extract_railway_rows.py`
- `services/railway/*`
- `services/processing.py` (transcribe-only)
- `routers/railway.py`

## Frontend v2

- `frontend/src/railway/*`
- `frontend/src/App.tsx` (upload → transcribe → edit → extract → preview → export)

## Frontend legacy (unused in App)

- `mergeSessions.ts`, `parseRailwayNarrative.ts`, `postprocessRailwayRows.ts`, `railwayExcel.ts`, `parsedRowsFromRecords.ts`, `tableDisplay.ts`

Tests under `backend/tests/` may still import legacy modules.
