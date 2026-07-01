# Legacy pipeline (v1)

These modules are **not used** by the v2 runtime path:

`audio → Yandex SpeechKit → editable transcript → LLM extract → RailwayRow[] → Excel`

## Removed from runtime

- `POST /api/parse/preview` — legacy parsing pipeline endpoint
- `session_adapter` no longer builds `records_wide` / `records_form` via postprocess
- `session_adapter` no longer calls `segment_railway_text` / `propagate_switch_context`
- `excel_export.py` no longer uses `build_form_rows`, `build_wide_rows`, `evidence_only`, `postprocess_railway_rows`
- Frontend legacy parsers/postprocess deleted (`mergeSessions.ts`, `postprocessRailwayRows.ts`, etc.)

## Legacy modules (tests / reference only)

- `services/parsing_pipeline.py` — regex + narrative + segment LLM
- `services/parser.py`, `canonical_model.py`, `record_expander.py`, `segmentation.py`
- `services/parse_railway_narrative.py`, `row_segment_extract.py`, `railway_segment.py`
- `services/postprocess_railway_rows.py`, `sanitize_row_for_export.py`, `evidence_only.py`
- `services/asr_pipeline.py`, `normalizer.py`, `validator.py`, `segment_reconcile.py`
- `services/speed_limit.py`, `track_norms.py`, `switch_context.py`
- `services/llm/segment_llm_parser.py`, `openai_parser.py`
- `services/inspection_form.py`, `wide_table.py`

## v2 active modules

- `services/speech/transcribe_with_yandex.py`
- `services/llm/provider.py`, `services/llm/extract_railway_rows.py`
- `services/railway/*`
- `services/processing.py` (transcribe-only)
- `services/excel_export.py` (RailwayRow[] only)
- `routers/railway.py`

## Frontend v2

- `frontend/src/railway/*`
- `frontend/src/App.tsx`

Tests under `backend/tests/` may still import legacy modules.
