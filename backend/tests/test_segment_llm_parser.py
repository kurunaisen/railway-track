"""LLM: отдельный вызов на каждый ASR-сегмент."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.llm.extraction_schema import RAILWAY_ROW_EXTRACTION_SCHEMA, openai_row_response_format
from app.services.llm.json_schema import merge_segment_row, parse_llm_row_json, structured_to_parsed_rows
from app.services.llm.segment_llm_parser import parse_structured_by_segments
from app.services.railway_segment import SegmentedBlock, segment_railway_text

MURMANSK = (
    "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
    "острие остряка пусть 15 ширина коли 1544 мм путь 12 3 подряд куста из 3 шпал "
    "путь 11 куст из 5 негодных шпал"
)

SAMPLE_ROW = {
    "location": "Мурманск",
    "assetKind": "switch",
    "assetNumber": "10",
    "reference": None,
    "defect": "износ рамного рельса 7 мм",
    "speedLimit": None,
    "note": "в острии остряка",
    "sourceText": "стрелочный перевод номер 10 износ рамного рельса 7 мм",
}


def test_row_schema_is_single_object():
    fmt = openai_row_response_format()
    assert fmt["json_schema"]["name"] == "railway_row"
    assert fmt["json_schema"]["schema"] is RAILWAY_ROW_EXTRACTION_SCHEMA["schema"]


def test_parse_llm_row_json():
    row = parse_llm_row_json(json.dumps(SAMPLE_ROW, ensure_ascii=False))
    assert row["assetNumber"] == "10"


def test_merge_segment_row_fills_location_and_source():
    block = SegmentedBlock(location="Мурманск", segment="путь 15 ширина колеи 1544")
    merged = merge_segment_row(
        {**SAMPLE_ROW, "location": None, "sourceText": ""},
        block,
    )
    assert merged["location"] == "Мурманск"
    assert merged["sourceText"] == block.segment


def test_merge_segment_row_overwrites_full_asr_source():
    block = SegmentedBlock(location="Мурманск", segment="путь 15 ширина колеи 1544")
    full = "станция мурманск стрелочный перевод 10 путь 15 ширина колеи 1544 путь 12"
    merged = merge_segment_row({**SAMPLE_ROW, "sourceText": full}, block)
    assert merged["sourceText"] == block.segment


def test_structured_by_segments_calls_llm_per_block(monkeypatch):
    blocks = segment_railway_text(MURMANSK)
    calls: list[str] = []

    def fake_parse(block: SegmentedBlock, index: int) -> dict:
        calls.append(block.segment[:20])
        row = {
            **SAMPLE_ROW,
            "assetKind": "track" if block.segment.lower().startswith("путь") else "switch",
            "assetNumber": "15" if "15" in block.segment else "10",
            "speedLimit": 60,
            "sourceText": block.segment,
        }
        if "остри" in block.segment.lower():
            row["defect"] = "износ рамного рельса 7 мм в острие остряка"
        return row

    monkeypatch.setattr(
        "app.services.llm.segment_llm_parser._parse_segment_openai",
        fake_parse,
    )
    monkeypatch.setattr("app.services.llm.segment_llm_parser.settings.llm_primary_parser", "openai")

    structured = parse_structured_by_segments(MURMANSK)
    assert len(structured["rows"]) == len(blocks) == 4
    assert len(calls) == 4

    rows = structured_to_parsed_rows(structured)
    assert len(rows) == 4
    assert rows[0].switch == "10"
    assert rows[1].put == "15"
