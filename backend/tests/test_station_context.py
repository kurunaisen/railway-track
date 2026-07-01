"""Наследование станции на строки после «на станции … N путь»."""

from app.services.inspection_form import record_to_form_row
from app.services.normalizer import normalize_all
from app.services.parser import ParsedRecord
from tests.test_walk_asr_no_punct import ASR_TEXT


def test_gauge_inherits_station_after_bolt_llm_rows():
    """LLM: уширение с перегоном вместо станции → Магнетиты, 5 путь."""
    llm_rows = [
        ParsedRecord(
            peregon="Шонгуй-Магнетиты",
            km="1418",
            piket="2+87",
            defect="отсутствует стыковой болт 1",
            logical_record_index=0,
            position_type="defect",
        ),
        ParsedRecord(
            peregon="Шонгуй-Магнетиты",
            km="1418",
            piket="4+22",
            defect="отсутствует 2 закладных болта",
            logical_record_index=1,
            position_type="defect",
        ),
        ParsedRecord(
            uchastok="Магнетиты",
            put="5",
            defect="не закручен 1 стыковой болт",
            logical_record_index=2,
            position_type="defect",
            raw_text="2 звено не закручен 1 стыковой болт",
        ),
        ParsedRecord(
            peregon="Шонгуй-Магнетиты",
            defect="уширение рельсовой колеи",
            value="1543",
            unit="мм",
            logical_record_index=3,
            position_type="defect",
            raw_text="И уширение колеи 1400 1543 мм",
        ),
    ]
    rows = normalize_all(llm_rows, source_text=ASR_TEXT)
    assert len(rows) == 4
    form4 = record_to_form_row(rows[3], 4)
    assert rows[3].uchastok == "Магнетиты"
    assert rows[3].peregon is None
    assert rows[3].put == "5"
    assert form4["Местонахождение (перегон, станция)"] == "Магнетиты"
    assert form4["№ пути, стрелочного перевода"] == "5"
    assert "1543" in form4["Выявленная неисправность"]
    assert form4["Ограничение скорости"] == "60 км/ч"
