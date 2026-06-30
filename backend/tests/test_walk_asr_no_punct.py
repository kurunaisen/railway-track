"""ASR без точек между фразами — как в реальной расшифровке."""

from app.services.canonical_model import expand_blocks_to_canonical_rows
from app.services.inspection_form import record_to_form_row
from app.services.normalizer import normalize_all
from app.services.parser import TranscriptSegment
from app.services.parsing_pipeline import run_parsing_pipeline
from app.services.rail_side import extract_rail_side_note, strip_ungrounded_rail_side_comment
from app.services.segmentation import segment_logical_blocks

ASR_TEXT = (
    "Перегон от никиты шомгу 1418 километр пике 2 87 метр отсутствует 1 стыковой болт "
    "На 1418 км пикет 4 Метр 22 отсутствует 2 закладных болта "
    "На станции магнититы 5 путь 2 звено не закручен 1 стыковой болт "
    "И уширение колеи 1400 1543 мм"
)

ASR_SEGMENTS = [
    TranscriptSegment(text="Перегон от никиты шомгу 1418 километр пике 2 87 метр", start=0.0, end=3.0),
    TranscriptSegment(text="отсутствует 1 стыковой болт", start=3.1, end=5.0),
    TranscriptSegment(text="На 1418 км пикет 4 Метр 22", start=5.1, end=8.0),
    TranscriptSegment(text="отсутствует 2 закладных болта", start=8.1, end=10.0),
    TranscriptSegment(text="На станции магнититы 5 путь 2 звено", start=10.1, end=13.0),
    TranscriptSegment(text="не закручен 1 стыковой болт", start=13.1, end=15.0),
    TranscriptSegment(text="И уширение колеи 1400 1543 мм", start=15.1, end=17.0),
]


def _rows(text: str = ASR_TEXT, segments=None):
    blocks = segment_logical_blocks(text, segments)
    return normalize_all(expand_blocks_to_canonical_rows(blocks)), blocks


def test_asr_no_punct_four_rows():
    rows, blocks = _rows()
    assert len(rows) == 4, [(r.raw_text, r.piket, r.defect) for r in rows]


def test_asr_no_punct_bindings():
    rows, _ = _rows()
    assert rows[0].piket == "2+87"
    assert rows[1].piket == "4+22"
    assert rows[2].put == "5"
    assert rows[3].value == "1543"


def test_asr_no_punct_no_hallucinated_rail_side():
    rows, _ = _rows()
    for r in rows:
        assert extract_rail_side_note(r.raw_text) is None
        assert "левой стороне" not in (r.comment or "").lower()


def test_asr_segments_four_rows():
    rows, blocks = _rows(ASR_TEXT, ASR_SEGMENTS)
    assert len(blocks) >= 1
    assert len(rows) == 4, [(r.raw_text, r.piket) for r in rows]


def test_pipeline_keeps_four_rows_when_llm_would_merge(monkeypatch):
    """Regex-разбор не должен проигрывать LLM, если тот слил строки."""
    from app.services import parsing_pipeline as pp

    monkeypatch.setattr(pp.settings, "parser_mode", "hybrid")
    monkeypatch.setattr(pp.settings, "openai_api_key", "test-key")

    def fake_llm(full_text, segments, blocks_payload):
        from app.services.parser import ParsedRecord

        merged = ParsedRecord(
            peregon="Шонгуй-Магнититы",
            km="1418",
            piket="2+87",
            defect="отсутствует стыковой болт отсутствуют закладные болты",
            comment="на левой стороне рельсовой нити",
            raw_text="отсутствует стыковой болт",
            logical_record_index=0,
        )
        gauge = ParsedRecord(
            peregon="Шонгуй-Магнититы",
            km="1418",
            piket="2+87",
            defect="уширение рельсовой колеи",
            value="1543",
            unit="мм",
            comment="на левой стороне рельсовой нити",
            raw_text="уширение колеи 1543",
            logical_record_index=1,
        )
        structured = {
            "records": [
                {"sequence_number": 1, "items": [{"order_in_record": 1}]},
                {"sequence_number": 2, "items": [{"order_in_record": 1}]},
            ]
        }
        return [merged, gauge], structured

    monkeypatch.setattr(pp, "parse_with_primary_llm", fake_llm)

    result = run_parsing_pipeline(ASR_TEXT)
    rows = normalize_all(result.records, source_text=ASR_TEXT)
    assert len(rows) == 4
    assert all("левой стороне" not in (r.comment or "") for r in rows)


def test_strip_ungrounded_rail_side_comment():
    assert strip_ungrounded_rail_side_comment(
        "на левой стороне рельсовой нити",
        "Перегон от никиты шомгу 1418 км",
    ) is None
    assert strip_ungrounded_rail_side_comment(
        "на левой стороне рельсовой нити. звено 2",
        "на левой стороне рельсовой нити отсутствует болт",
    ) == "на левой стороне рельсовой нити. звено 2"
