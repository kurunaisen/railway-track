"""Мурманск: стр.п. 10; «пусть 15» → путь 15; острие остряка → примечание."""

from app.services.asr_fixes import fix_asr_transcript
from app.services.canonical_model import _split_by_location
from app.services.inspection_form import record_to_form_row
from app.services.normalizer import normalize_all
from app.services.parsing_pipeline import run_parsing_pipeline

MURMANSK = (
    "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
    "острие остряка пусть 15 ширина колеи 1544 мм путь 12 3 подряд куста из 3 шпал "
    "путь 11 куст из 5 негодных шпал"
)
MURMANSK_KOLI = (
    "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
    "острие остряка пусть 15 ширина коли 1544 мм путь 12 3 подряд куста из 3 шпал "
    "путь 11 куст из 5 негодных шпал"
)


def _rows():
    return normalize_all(run_parsing_pipeline(MURMANSK).records, source_text=MURMANSK)


def _rows_koli():
    return normalize_all(run_parsing_pipeline(MURMANSK_KOLI).records, source_text=MURMANSK_KOLI)


def test_asr_koli_to_kolei():
    fixed = fix_asr_transcript(MURMANSK_KOLI)
    assert "ширина коли" not in fixed.lower()
    assert "ширина колеи" in fixed.lower()


def test_koli_asr_four_rows_gauge_and_paths():
    """Whisper: «ширина коли» — та же таблица, что и с «колеи»."""
    rows = _rows_koli()
    assert len(rows) == 4
    wear = next(r for r in rows if r.defect and "рамн" in r.defect.lower())
    gauge = next(r for r in rows if r.defect and "коле" in r.defect.lower())
    p12 = next(r for r in rows if r.put == "12")
    p11 = next(r for r in rows if r.put == "11")
    assert wear.switch == "10"
    assert wear.value == "7"
    assert gauge.put == "15"
    assert gauge.value == "1544"
    assert gauge.speed_limit == "60"
    assert "подряд" in (p12.defect or "").lower() or "3" in (p12.defect or "")
    assert "негодн" in (p11.defect or "").lower()
    assert p12.put == "12"
    assert p11.put == "11"


def test_asr_pust_to_path():
    fixed = fix_asr_transcript(MURMANSK)
    assert "пусть 15" not in fixed.lower()
    assert "путь 15" in fixed.lower()


def test_split_path_15_before_path_12():
    parts = _split_by_location(fix_asr_transcript(MURMANSK))
    assert len(parts) == 4
    assert "стрелочный перевод" in parts[0].lower()
    assert "путь 15" in parts[1].lower()
    assert "путь 12" in parts[2].lower()
    assert "путь 11" in parts[3].lower()


def test_wear_switch_only_tip_in_note():
    rows = _rows()
    wear = next(r for r in rows if r.defect and "рамн" in r.defect.lower())
    f = record_to_form_row(wear, 1)
    assert wear.put is None
    assert wear.switch == "10"
    assert wear.value == "7"
    assert "остри" not in (wear.defect or "").lower()
    assert f["№ пути, стрелочного перевода"] == "стр.п. 10"
    assert f["Примечание"] and "остри" in f["Примечание"].lower()


def test_gauge_on_path_15_only():
    rows = _rows()
    gauge = next(r for r in rows if r.defect and "колеи" in r.defect.lower())
    f = record_to_form_row(gauge, 2)
    assert gauge.put == "15"
    assert gauge.switch is None
    assert gauge.speed_limit == "60"
    assert f["№ пути, стрелочного перевода"] == "15"


def test_path_12_and_11_sleeper_clusters():
    rows = _rows()
    p12 = next(r for r in rows if r.put == "12")
    p11 = next(r for r in rows if r.put == "11")
    assert p12.switch is None
    assert p11.switch is None
    assert "шпал" in (p12.defect or p12.raw_text or "").lower()
    assert "шпал" in (p11.defect or p11.raw_text or "").lower()


def test_four_table_rows():
    assert len(_rows()) == 4


def test_llm_merged_gauge_into_wear_reconciled():
    """Прод: 1544 на износе, кусты на путях 15/12 — segment reconcile."""
    from app.services.parser import ParsedRecord

    llm_rows = [
        ParsedRecord(
            logical_record_index=0,
            uchastok="Мурманск",
            put="15",
            switch="10",
            defect="износ рамного рельса",
            value="1544",
            unit="мм",
            comment="и острие остряка",
            raw_text=MURMANSK_KOLI[:90],
            position_type="defect",
        ),
        ParsedRecord(
            logical_record_index=1,
            uchastok="Мурманск",
            put="15",
            defect="куста из 3 шпал",
            raw_text="путь 15",
            position_type="defect",
        ),
        ParsedRecord(
            logical_record_index=2,
            uchastok="Мурманск",
            put="12",
            defect="куст негодных шпал 5",
            raw_text="путь 12",
            position_type="defect",
        ),
    ]
    rows = normalize_all(llm_rows, source_text=MURMANSK_KOLI)
    assert len(rows) == 4
    wear = next(r for r in rows if r.defect and "рамн" in r.defect.lower())
    gauge = next(r for r in rows if r.defect and "коле" in r.defect.lower())
    assert wear.put is None
    assert wear.switch == "10"
    assert wear.value == "7"
    assert gauge.put == "15"
    assert gauge.value == "1544"
    assert next(r for r in rows if r.put == "12").defect
    assert next(r for r in rows if r.put == "11").defect


def test_llm_wrong_path_on_wear_row_reconciled():
    """LLM размазывает путь 15 и примечание — normalize_all сверяет с ASR-сегментами."""
    from app.services.parser import ParsedRecord

    llm_rows = [
        ParsedRecord(
            logical_record_index=0,
            uchastok="Мурманск",
            put="15",
            switch="10",
            defect="износ рамного рельса",
            value="7",
            unit="мм",
            speed_limit="60",
            comment="в острии остряка",
            raw_text=MURMANSK[:80],
            position_type="defect",
        ),
        ParsedRecord(
            logical_record_index=1,
            uchastok="Мурманск",
            put="15",
            switch="10",
            defect="уширение рельсовой колеи",
            value="1544",
            unit="мм",
            speed_limit="60",
            comment="в острии остряка",
            raw_text="ширина колеи 1544",
            position_type="defect",
        ),
        ParsedRecord(
            logical_record_index=2,
            uchastok="Мурманск",
            put="12",
            switch="10",
            defect="куст шпал",
            raw_text="путь 12 куст",
            position_type="defect",
        ),
        ParsedRecord(
            logical_record_index=3,
            uchastok="Мурманск",
            put="11",
            defect="куст шпал",
            raw_text="путь 11",
            position_type="defect",
        ),
    ]
    rows = normalize_all(llm_rows, source_text=MURMANSK)
    f1 = record_to_form_row(rows[0], 1)
    f2 = record_to_form_row(rows[1], 2)
    f3 = record_to_form_row(rows[2], 3)
    f4 = record_to_form_row(rows[3], 4)
    assert rows[0].put is None
    assert f1["№ пути, стрелочного перевода"] == "стр.п. 10"
    assert f1["Примечание"] and "остри" in f1["Примечание"].lower()
    assert rows[0].speed_limit is None
    assert rows[1].put == "15"
    assert rows[1].switch is None
    assert f2["№ пути, стрелочного перевода"] == "15"
    assert not f2.get("Примечание") or "остри" not in (f2["Примечание"] or "").lower()
    assert rows[2].put == "12"
    assert rows[2].switch is None
    assert rows[3].put == "11"
    assert f4["№ пути, стрелочного перевода"] == "11"

