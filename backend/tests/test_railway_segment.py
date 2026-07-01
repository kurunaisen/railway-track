"""segment_railway_text — местонахождение и сегменты по пути/стрелке."""

from app.services.asr_fixes import normalize_asr_text
from app.services.railway_segment import segment_railway_text

MURMANSK = (
    "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
    "острие остряка пусть 15 ширина коли 1544 мм путь 12 3 подряд куста из 3 шпал "
    "путь 11 куст из 5 негодных шпал"
)


def test_normalizes_before_split():
    blocks = segment_railway_text(MURMANSK)
    assert blocks
    joined = " ".join(b.segment for b in blocks).lower()
    assert "путь 15" in joined
    assert "ширина колеи" in joined
    assert "пусть" not in joined


def test_extracts_station_location():
    blocks = segment_railway_text(MURMANSK)
    assert all(b.location == "Мурманск" for b in blocks)


def test_murmansk_four_segments():
    blocks = segment_railway_text(MURMANSK)
    assert len(blocks) == 4
    assert "стрелочный перевод" in blocks[0].segment.lower()
    assert blocks[1].segment.lower().startswith("путь 15")
    assert "путь 12" in blocks[2].segment.lower()
    assert blocks[3].segment.lower().startswith("путь 11")


def test_no_markers_single_segment():
    blocks = segment_railway_text("перегон а-б километр 10 просадка")
    assert len(blocks) == 1
    assert blocks[0].location is None
    assert "просадка" in blocks[0].segment


def test_strp_expanded_to_switch_marker():
    text = "станция мурманск стр.п. 10 износ 7 мм"
    blocks = segment_railway_text(text)
    assert len(blocks) == 1
    assert blocks[0].location == "Мурманск"
    assert "стрелочный перевод" in blocks[0].segment.lower()
