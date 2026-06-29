import pytest

from app.services.normalizer import normalize_piket, normalize_put, normalize_record, normalize_unit
from app.services.parser import ParsedRecord
from app.services.validator import validate_record


def test_normalize_put_ordinal():
    assert normalize_put("второй") == "2"
    assert normalize_put("3") == "3"


def test_normalize_piket_plus():
    assert normalize_piket("5 плюс 20") == "5+20"


def test_normalize_unit():
    assert normalize_unit("миллиметров") == "мм"
    assert normalize_unit("километров в час") == "км/ч"


def test_normalize_record_full():
    r = ParsedRecord(put="второй", piket="5 плюс 20", unit="миллиметров", km="245,5")
    normalize_record(r)
    assert r.put == "2"
    assert r.piket == "5+20"
    assert r.unit == "мм"
    assert r.km == "245.5"


def test_validate_km_format():
    issues = validate_record(ParsedRecord(km="abc", peregon="test"), 0)
    assert any(i.field == "km" for i in issues)


def test_validate_valid_record():
    issues = validate_record(
        ParsedRecord(km="245", piket="5+20", defect="износ", value="12", unit="мм"),
        0,
    )
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0
