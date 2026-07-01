"""sanitizeRowForExport — порт TS-патча evidence-only."""

from app.services.asr_pipeline import asr_text_to_parsed_rows
from app.services.sanitize_row_for_export import (
    extract_deterministic_defect,
    remove_duplicate_note_phrases,
    sanitize_row_for_export,
)

MURMANSK_SEGMENTS = [
    "стрелочный перевод номер 10 износ рамного рельса 7 мм острие остряка",
    "путь 15 ширина колеи 1544 мм",
    "путь 12 3 подряд куста из 3 шпал",
    "путь 11 куст из 5 негодных шпал",
]


def _row(source: str, **kwargs) -> dict:
    return {
        "location": "Мурманск",
        "assetKind": "track",
        "assetNumber": "15",
        "reference": None,
        "defect": "уширение рельсовой колеи",
        "speedLimit": 60,
        "note": "движение закрывается (2288р)",
        "sourceText": source,
        **kwargs,
    }


def test_wear_deterministic_defect_and_tip():
    source = MURMANSK_SEGMENTS[0]
    defect, note = extract_deterministic_defect(source)
    assert defect == "износ рамного рельса 7 мм"
    assert note == "в острие остряка"


def test_gauge_keeps_width_not_norm_title():
    row = sanitize_row_for_export(_row(MURMANSK_SEGMENTS[1]))
    assert row["defect"] == "ширина колеи 1544 мм"
    assert row["speedLimit"] is None


def test_synthetic_note_removed():
    row = sanitize_row_for_export(_row(MURMANSK_SEGMENTS[1]))
    assert row["note"] is None


def test_sleeper_cluster_no_mm_leak():
    row = sanitize_row_for_export(
        _row(MURMANSK_SEGMENTS[2], defect="3 подряд куста из 3 шпал 7 мм")
    )
    assert row["defect"] == "3 подряд куста из 3 шпал"
    assert "мм" not in (row["defect"] or "")


def test_bad_sleepers_deterministic():
    row = sanitize_row_for_export(_row(MURMANSK_SEGMENTS[3]))
    assert row["defect"] == "куст из 5 негодных шпал"


def test_explicit_speed_kept():
    source = "путь 2 уширение колеи 1543 мм ограничение скорости 60"
    row = sanitize_row_for_export(_row(source, speedLimit=60))
    assert row["speedLimit"] == 60


def test_note_dedupe():
    assert remove_duplicate_note_phrases("в острие остряка; в острии остряка") == "в острие остряка"


def test_pipeline_applies_sanitize():
    rows = asr_text_to_parsed_rows(
        "Станция мурманск "
        + " ".join(MURMANSK_SEGMENTS),
        use_llm=False,
    )
    assert len(rows) == 4
    assert rows[0]["defect"] == "износ рамного рельса 7 мм"
    assert rows[0]["note"] == "в острие остряка"
    assert rows[1]["defect"] == "ширина колеи 1544 мм"
    assert all(r["speedLimit"] is None for r in rows)
