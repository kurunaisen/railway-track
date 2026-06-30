"""Smoke-тест сборки ответа с records_form."""

from app.schemas import AudioSessionOut, WideTableOut
from app.services.inspection_form import build_form_rows
from app.services.inspection_repository import FlatInspectionRow


def test_audio_session_out_accepts_records_form():
    row = FlatInspectionRow(
        id=1,
        session_id=1,
        record_id=1,
        row_order=0,
        peregon="Кица — Блокпост 1381 км",
        put="2",
        km="1384",
        piket="4+33",
        defect="Отсутствие одного стыкового болта",
        raw_text="перегон Кица-Блокпост 1381, путь 2",
    )
    cols, rows = build_form_rows([row])
    payload = AudioSessionOut(
        id=1,
        filename="x.wav",
        original_name="x.wav",
        status="processed",
        full_transcript="test",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
        records_form=WideTableOut(columns=cols, rows=rows),
    )
    assert payload.records_form is not None
    assert payload.records_form.rows[0]["Nп/п"] == 1
