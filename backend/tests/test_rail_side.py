"""Тесты указателя стороны рельсовой нити."""

from dataclasses import dataclass

from app.services.inspection_form import build_form_rows, format_binding, format_defect
from app.services.normalizer import normalize_all, reconcile_rail_side_rows
from app.services.parser import ParsedRecord, parse_transcript
from app.services.rail_side import extract_rail_side, is_rail_side_only_fragment
from app.services.segmentation import LogicalBlock, segment_logical_blocks


def test_extract_left_rail_side():
    assert extract_rail_side("на левой стороне рельсовой нити") == "левая нить"
    assert extract_rail_side("сторона рельсовой нити левая") == "левая нить"


def test_rail_side_is_not_defect_fragment():
    assert is_rail_side_only_fragment("на левой стороне рельсовой нити")
    assert not is_rail_side_only_fragment("отсутствует 1 стыковой болт")


def test_reconcile_side_and_bolt_rows():
    rows = [
        ParsedRecord(
            peregon="Кица — Блокпост 1381 км",
            km="1385",
            piket="5",
            raw_text="на левой стороне рельсовой нити",
            logical_record_index=0,
            position_index=0,
        ),
        ParsedRecord(
            peregon="Кица — Блокпост 1381 км",
            km="1385",
            piket="5",
            defect="отсутствует",
            raw_text="отсутствует 1 стыковой",
            logical_record_index=0,
            position_index=1,
        ),
        ParsedRecord(
            peregon="Кица — Блокпост 1381 км",
            km="1385",
            piket="5",
            raw_text="болт",
            logical_record_index=0,
            position_index=2,
        ),
    ]
    merged = reconcile_rail_side_rows(rows)
    assert len(merged) == 1
    assert merged[0].obekt == "левая нить"
    assert "болт" in (merged[0].defect or "").lower()


def test_user_asr_example_single_row_in_table():
    text = (
        "Перегон кица блокпост 1381 километр На 1000 385 км пикет 5 метр 82 "
        "На левой стороне рельсовой нити Отсутствует 1 стыковой Болт."
    )
    blocks = segment_logical_blocks(text, None)
    from app.services.record_expander import expand_blocks_to_rows

    rows = normalize_all(expand_blocks_to_rows(blocks))
    rows = reconcile_rail_side_rows(rows)
    rows = normalize_all(rows)

    @dataclass
    class Rec:
        peregon: str | None
        uchastok: str | None
        put: str | None
        obekt: str | None
        km: str | None
        piket: str | None
        parameter: str | None
        defect: str | None
        value: str | None
        unit: str | None
        comment: str | None
        speed_limit: str | None
        raw_text: str | None

    form_rows = build_form_rows(
        [
            Rec(
                peregon=r.peregon,
                uchastok=r.uchastok,
                put=r.put,
                obekt=r.obekt,
                km=r.km,
                piket=r.piket,
                parameter=r.parameter,
                defect=r.defect,
                value=r.value,
                unit=r.unit,
                comment=r.comment,
                speed_limit=r.speed_limit,
                raw_text=r.raw_text,
            )
            for r in rows
            if r.defect or r.parameter or r.value
        ]
    )[1]

    assert len(form_rows) == 1
    binding = form_rows[0]["Привязка (км,пк,м)"]
    defect = form_rows[0]["Выявленная неисправность"]
    assert "левая нить" in binding
    assert "сторона" not in (defect or "").lower()
    assert "болт" in (defect or "").lower()


def test_format_binding_includes_side():
    @dataclass
    class Rec:
        km = "1385"
        piket = "5"
        obekt = "левая нить"
        raw_text = None
        comment = None

    assert "левая нить" in format_binding(Rec())


def test_format_defect_skips_side_only_raw():
    @dataclass
    class Rec:
        defect = None
        parameter = None
        value = None
        unit = None
        raw_text = "на левой стороне рельсовой нити"

    assert format_defect(Rec()) == ""
