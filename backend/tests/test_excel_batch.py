from app.services.excel_export import export_sessions_batch_to_excel


def test_export_sessions_batch_to_excel_empty():
    import pytest
    from sqlalchemy.orm import Session

    class FakeDb(Session):
        pass

    with pytest.raises(ValueError, match="Не указаны"):
        export_sessions_batch_to_excel(FakeDb(), [])
