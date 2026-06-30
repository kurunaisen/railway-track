from app.services.pipeline_issues import normalize_pipeline_issues


def test_validation_message_becomes_error_text():
    errors, warnings = normalize_pipeline_issues([
        {"row": 0, "field": "value", "message": "Параметр/дефект без значения", "severity": "warning"},
    ])
    assert not errors
    assert len(warnings) == 1
    assert warnings[0]["error"] == "Параметр/дефект без значения"


def test_pipeline_error_preserved():
    errors, warnings = normalize_pipeline_issues([
        {"row": -1, "error": "LLM fallback", "severity": "warning"},
    ])
    assert not errors
    assert warnings[0]["message"] == "LLM fallback"


def test_validation_error_severity():
    errors, warnings = normalize_pipeline_issues([
        {"row": 0, "field": "km", "message": "Неверный формат км: abc", "severity": "error"},
    ])
    assert len(errors) == 1
    assert errors[0]["field"] == "km"
    assert "формат" in errors[0]["message"]
