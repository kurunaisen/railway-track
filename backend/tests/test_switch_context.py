"""Номер стр.п. из полного текста при LLM-пути и после загрузки из БД."""

from app.services.inspection_form import record_to_form_row
from app.services.normalizer import normalize_all
from app.services.parser import ParsedRecord
from app.services.switch_context import propagate_switch_context

KOLA = (
    "Станция кола 5 путь стрелочный перевод 15 износ сердечника крестовины 8 мм "
    "6 путь стрелочный перевод 18 ширина колеи в хвосте крестовины 1524"
)


def _llm_like_rows() -> list[ParsedRecord]:
    """Как structured_to_parsed_rows: только track_number, без switch."""
    return [
        ParsedRecord(
            logical_record_index=0,
            uchastok="Кола",
            put="5",
            defect="износ сердечника крестовины",
            value="8",
            unit="мм",
            raw_text="износ сердечника крестовины 8 мм",
            position_type="defect",
        ),
        ParsedRecord(
            logical_record_index=1,
            uchastok="Кола",
            put="6",
            defect="ширина колеи в хвосте крестовины",
            value="1524",
            unit="мм",
            raw_text="ширина колеи в хвосте крестовины 1524",
            position_type="defect",
        ),
    ]


def test_propagate_switch_from_full_text():
    rows = propagate_switch_context(_llm_like_rows(), KOLA)
    assert rows[0].switch == "15"
    assert rows[1].switch == "18"


def test_normalize_all_fills_switch_for_llm_rows():
    rows = normalize_all(_llm_like_rows(), source_text=KOLA)
    f1 = record_to_form_row(rows[0], 1)
    f2 = record_to_form_row(rows[1], 2)
    assert "стр.п. 15" in (f1["№ пути, стрелочного перевода"] or "")
    assert "стр.п. 18" in (f2["№ пути, стрелочного перевода"] or "")
