"""Сохранение и загрузка inspection_records / inspection_items (FR 11.6–11.8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models import (
    InspectionItem,
    InspectionRecord,
    ProcessingJob,
    Transcript,
    TranscriptSegment,
    UnknownTerm,
    ValidationError,
)
from app.services.parser import ParsedRecord, TranscriptSegment as AsrSegment


@dataclass
class FlatInspectionRow:
    """Плоская long-строка для API / Excel (контекст записи + позиция)."""

    id: int
    session_id: int
    record_id: int
    row_order: int
    record_date: str | None = None
    uchastok: str | None = None
    peregon: str | None = None
    put: str | None = None
    km: str | None = None
    piket: str | None = None
    obekt: str | None = None
    parameter: str | None = None
    value: str | None = None
    unit: str | None = None
    defect: str | None = None
    comment: str | None = None
    speed_limit: str | None = None
    raw_text: str | None = None
    segment_start: float | None = None
    segment_end: float | None = None
    logical_record_index: int | None = None
    logical_block_index: int | None = None
    position_index: int | None = None
    position_type: str | None = None
    disputed_fields: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)


def _value_parts(value: str | None) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    try:
        return float(value.replace(",", ".")), value
    except ValueError:
        return None, value


def _parsed_to_item(record: InspectionRecord, parsed: ParsedRecord, order: int) -> InspectionItem:
    num, txt = _value_parts(parsed.value)
    needs_review = bool(parsed.disputed_fields)
    if parsed.position_type == "speed_limit":
        num, txt = _value_parts(parsed.speed_limit or parsed.value)
        return InspectionItem(
            record_id=record.id,
            order_in_record=order,
            speed_limit=parsed.speed_limit or parsed.value,
            position_type="speed_limit",
            parameter_name="Ограничение скорости",
            canonical_parameter="ограничение скорости",
            value_numeric=num,
            value_text=txt,
            unit="км/ч",
            needs_review=needs_review,
            raw_text=parsed.raw_text,
        )
    if parsed.defect:
        display = parsed.defect[0].upper() + parsed.defect[1:]
        return InspectionItem(
            record_id=record.id,
            order_in_record=order,
            parameter_name=display,
            defect_text=parsed.defect,
            value_numeric=num,
            value_text=txt,
            unit=parsed.unit,
            position_type="defect",
            speed_limit=parsed.speed_limit,
            needs_review=needs_review,
            raw_text=parsed.raw_text,
        )
    return InspectionItem(
        record_id=record.id,
        order_in_record=order,
        parameter_name=(parsed.parameter[0].upper() + parsed.parameter[1:]) if parsed.parameter else None,
        canonical_parameter=parsed.parameter,
        value_numeric=num,
        value_text=txt,
        unit=parsed.unit,
        position_type=parsed.position_type or "parameter",
        speed_limit=parsed.speed_limit,
        needs_review=needs_review,
        raw_text=parsed.raw_text,
    )


def clear_job_results(db: Session, job_id: int) -> None:
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        return
    if job.transcript:
        db.delete(job.transcript)
    for rec in list(job.inspection_records):
        db.delete(rec)
    for term in list(job.unknown_terms):
        db.delete(term)
    db.flush()


def save_job_results(
    db: Session,
    job: ProcessingJob,
    full_text: str,
    asr_segments: list[AsrSegment],
    parsed_rows: list[ParsedRecord],
    avg_confidence: float | None,
    unknown_terms: list[dict],
    all_errors: list[dict],
    validation_record_errors: dict[int, list[str]],
    logical_blocks: list[dict],
    file_metadata: dict,
) -> int:
    clear_job_results(db, job.id)

    transcript = Transcript(
        job_id=job.id,
        full_text=full_text,
        language="ru",
        confidence_avg=avg_confidence,
    )
    db.add(transcript)
    db.flush()

    for idx, seg in enumerate(asr_segments):
        db.add(
            TranscriptSegment(
                transcript_id=transcript.id,
                segment_index=idx,
                start_sec=seg.start,
                end_sec=seg.end,
                text=seg.text,
                confidence=seg.confidence,
            )
        )

    grouped: dict[int, list[ParsedRecord]] = {}
    for row in parsed_rows:
        key = row.logical_record_index if row.logical_record_index is not None else 0
        grouped.setdefault(key, []).append(row)

    item_global_order = 0
    for seq_idx, seq in enumerate(sorted(grouped.keys())):
        rows = grouped[seq]
        first = rows[0]
        sequence_number = seq + 1  # FR 14.1: порядок с 1
        insp_rec = InspectionRecord(
            job_id=job.id,
            sequence_number=sequence_number,
            start_sec=first.segment_start,
            end_sec=first.segment_end,
            date_value=first.record_date,
            section_name=first.uchastok,
            haul_name=first.peregon,
            track_number=first.put,
            km_value=first.km,
            picket_value=first.piket,
            object_name=first.obekt,
            comment=first.comment,
            status="review" if any(r.disputed_fields for r in rows) else "draft",
            source_text="; ".join(r.raw_text for r in rows if r.raw_text),
        )
        db.add(insp_rec)
        db.flush()

        for pos_idx, parsed in enumerate(rows):
            order = (
                (parsed.position_index + 1)
                if parsed.position_index is not None
                else pos_idx + 1
            )
            item = _parsed_to_item(insp_rec, parsed, order)
            db.add(item)
            db.flush()

            if item_global_order in validation_record_errors:
                for msg in validation_record_errors[item_global_order]:
                    field_name = msg.split(":", 1)[0] if ":" in msg else "general"
                    db.add(
                        ValidationError(
                            record_id=insp_rec.id,
                            item_id=item.id,
                            field_name=field_name,
                            error_code="validation",
                            error_message=msg,
                            severity="error" if field_name in parsed.disputed_fields else "warning",
                        )
                    )
            item_global_order += 1

    for err in all_errors:
        if err.get("row", -1) >= 0:
            continue
        db.add(
            ValidationError(
                error_code="pipeline",
                field_name="general",
                error_message=err.get("error", ""),
                severity=err.get("severity", "warning"),
            )
        )

    for term in unknown_terms:
        db.add(
            UnknownTerm(
                job_id=job.id,
                term_text=term.get("term", ""),
                context_text=f"count={term.get('count', 1)}",
            )
        )

    job.set_pipeline_metadata({
        "logical_blocks": logical_blocks,
        "file_metadata": file_metadata,
        "parse_errors": all_errors,
        "disputed_by_row": [
            {"row": idx, "fields": list(row.disputed_fields)}
            for idx, row in enumerate(parsed_rows)
            if row.disputed_fields
        ],
    })
    return len(parsed_rows)


def load_latest_done_job(db: Session, audio_file_id: int) -> ProcessingJob | None:
    return (
        db.query(ProcessingJob)
        .options(
            joinedload(ProcessingJob.transcript).joinedload(Transcript.segments),
            joinedload(ProcessingJob.inspection_records)
            .joinedload(InspectionRecord.items)
            .joinedload(InspectionItem.validation_errors),
            joinedload(ProcessingJob.unknown_terms),
        )
        .filter(ProcessingJob.audio_file_id == audio_file_id, ProcessingJob.status == "done")
        .order_by(ProcessingJob.finished_at.desc())
        .first()
    )


def load_active_job(db: Session, audio_file_id: int) -> ProcessingJob | None:
    return (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.audio_file_id == audio_file_id,
            ProcessingJob.status.in_(("queued", "processing")),
        )
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )


def load_flat_rows(job: ProcessingJob, audio_file_id: int) -> list[FlatInspectionRow]:
    rows: list[FlatInspectionRow] = []
    meta = job.get_pipeline_metadata() or {}
    disputed_map = {
        int(entry["row"]): list(entry.get("fields") or [])
        for entry in meta.get("disputed_by_row", [])
    }
    global_order = 0
    for insp_rec in sorted(job.inspection_records, key=lambda r: r.sequence_number):
        for item in sorted(insp_rec.items, key=lambda i: i.order_in_record):
            val = item.value_text
            if val is None and item.value_numeric is not None:
                val = str(item.value_numeric)
            disputed: list[str] = list(dict.fromkeys(disputed_map.get(global_order, [])))
            if not disputed:
                disputed = list(dict.fromkeys(
                    e.field_name for e in item.validation_errors if e.severity == "error"
                ))
            if not disputed and item.needs_review:
                disputed = ["value"]
            val_errs = [
                f"{e.field_name}: {e.error_message}"
                for e in item.validation_errors
            ]
            rows.append(
                FlatInspectionRow(
                    id=item.id,
                    session_id=audio_file_id,
                    record_id=insp_rec.id,
                    row_order=global_order,
                    record_date=insp_rec.date_value,
                    uchastok=insp_rec.section_name,
                    peregon=insp_rec.haul_name,
                    put=insp_rec.track_number,
                    km=insp_rec.km_value,
                    piket=insp_rec.picket_value,
                    obekt=insp_rec.object_name,
                    parameter=item.canonical_parameter or (
                        item.parameter_name if item.position_type == "parameter" else None
                    ),
                    value=val,
                    unit=item.unit,
                    defect=item.defect_text,
                    comment=insp_rec.comment,
                    speed_limit=item.speed_limit,
                    raw_text=item.raw_text,
                    segment_start=insp_rec.start_sec,
                    segment_end=insp_rec.end_sec,
                    logical_record_index=insp_rec.sequence_number - 1,
                    logical_block_index=insp_rec.sequence_number - 1,
                    position_index=item.order_in_record - 1,
                    position_type=item.position_type,
                    disputed_fields=disputed,
                    validation_errors=val_errs,
                )
            )
            global_order += 1
    return rows


def get_item_with_record(db: Session, item_id: int) -> tuple[InspectionItem, InspectionRecord] | None:
    item = (
        db.query(InspectionItem)
        .options(joinedload(InspectionItem.record).joinedload(InspectionRecord.job))
        .filter(InspectionItem.id == item_id)
        .first()
    )
    if not item or not item.record:
        return None
    return item, item.record


def flat_row_from_item(item: InspectionItem, record: InspectionRecord, audio_file_id: int, row_order: int) -> FlatInspectionRow:
    val = item.value_text
    if val is None and item.value_numeric is not None:
        val = str(item.value_numeric)
    return FlatInspectionRow(
        id=item.id,
        session_id=audio_file_id,
        record_id=record.id,
        row_order=row_order,
        record_date=record.date_value,
        uchastok=record.section_name,
        peregon=record.haul_name,
        put=record.track_number,
        km=record.km_value,
        piket=record.picket_value,
        obekt=record.object_name,
        parameter=item.canonical_parameter or (
            item.parameter_name if item.position_type == "parameter" else None
        ),
        value=val,
        unit=item.unit,
        defect=item.defect_text,
        comment=record.comment,
        speed_limit=item.speed_limit,
        raw_text=item.raw_text,
        segment_start=record.start_sec,
        segment_end=record.end_sec,
        logical_record_index=record.sequence_number - 1,
        logical_block_index=record.sequence_number - 1,
        position_index=item.order_in_record - 1,
        position_type=item.position_type,
        disputed_fields=["value"] if item.needs_review else [],
        validation_errors=[f"{e.field_name}: {e.error_message}" for e in item.validation_errors],
    )


def apply_flat_update(item: InspectionItem, record: InspectionRecord, data: dict) -> None:
    mapping = {
        "record_date": ("record", "date_value"),
        "uchastok": ("record", "section_name"),
        "peregon": ("record", "haul_name"),
        "put": ("record", "track_number"),
        "km": ("record", "km_value"),
        "piket": ("record", "picket_value"),
        "obekt": ("record", "object_name"),
        "comment": ("record", "comment"),
        "raw_text": ("item", "raw_text"),
        "parameter": ("item", "canonical_parameter"),
        "defect": ("item", "defect_text"),
        "unit": ("item", "unit"),
        "speed_limit": ("item", "speed_limit"),
    }
    for key, val in data.items():
        if key == "value":
            num, txt = _value_parts(val)
            item.value_numeric = num
            item.value_text = txt
        elif key == "disputed_fields":
            item.needs_review = bool(val)
        elif key in mapping:
            target, attr = mapping[key]
            obj = record if target == "record" else item
            setattr(obj, attr, val)
            if key == "parameter" and val:
                item.parameter_name = val
                item.position_type = "parameter"
            if key == "defect" and val:
                item.parameter_name = val
                item.position_type = "defect"
    record.status = "review" if item.needs_review else record.status


def _display_parameter_name(item: InspectionItem) -> str | None:
    name = item.parameter_name or item.defect_text or item.canonical_parameter
    if not name:
        return None
    if name.lower() == "ограничение скорости":
        return "Ограничение скорости"
    return name[0].upper() + name[1:]


def item_to_structured_dict(item: InspectionItem) -> dict:
    val = item.value_numeric
    if val is None and item.value_text:
        try:
            val = float(item.value_text.replace(",", "."))
        except ValueError:
            val = None
    return {
        "order_in_record": item.order_in_record,
        "parameter_name": _display_parameter_name(item),
        "canonical_parameter": item.canonical_parameter,
        "value_numeric": val,
        "value_text": item.value_text,
        "unit": item.unit,
        "defect_text": item.defect_text,
        "speed_limit": item.speed_limit,
        "needs_review": item.needs_review,
    }


def record_to_structured_dict(rec: InspectionRecord) -> dict:
    return {
        "sequence_number": rec.sequence_number,
        "start_sec": rec.start_sec,
        "end_sec": rec.end_sec,
        "date_value": rec.date_value,
        "section_name": rec.section_name,
        "haul_name": rec.haul_name,
        "track_number": rec.track_number,
        "km_value": rec.km_value,
        "picket_value": rec.picket_value,
        "object_name": rec.object_name,
        "comment": rec.comment,
        "status": rec.status,
        "source_text": rec.source_text,
        "items": [
            item_to_structured_dict(item)
            for item in sorted(rec.items, key=lambda i: i.order_in_record)
        ],
    }


def load_structured_records(job: ProcessingJob) -> dict:
    """FR 14.2 — вложенный JSON records[] с items[]."""
    records = [
        record_to_structured_dict(rec)
        for rec in sorted(job.inspection_records, key=lambda r: r.sequence_number)
    ]
    return {"records": records}


def build_structured_from_parsed(rows: list[ParsedRecord]) -> dict:
    """Структурированный ответ из ParsedRecord (до/без БД)."""
    grouped: dict[int, list[ParsedRecord]] = {}
    for row in rows:
        key = row.logical_record_index if row.logical_record_index is not None else 0
        grouped.setdefault(key, []).append(row)

    records: list[dict] = []
    for seq in sorted(grouped.keys()):
        group = sorted(
            grouped[seq],
            key=lambda r: r.position_index if r.position_index is not None else 0,
        )
        first = group[0]
        items: list[dict] = []
        for i, r in enumerate(group):
            order = (r.position_index if r.position_index is not None else i) + 1
            name = r.parameter or r.defect
            if r.position_type == "speed_limit" or r.speed_limit:
                name = "Ограничение скорости"
            val = r.value or r.speed_limit
            num, txt = _value_parts(val)
            unit = r.unit or ("км/ч" if r.position_type == "speed_limit" else None)
            display = name[0].upper() + name[1:] if name else None
            items.append({
                "order_in_record": order,
                "parameter_name": display,
                "value_numeric": num,
                "value_text": txt,
                "unit": unit,
            })
        records.append({
            "sequence_number": seq + 1,
            "start_sec": first.segment_start,
            "end_sec": first.segment_end,
            "haul_name": first.peregon,
            "track_number": first.put,
            "km_value": first.km,
            "picket_value": first.piket,
            "items": items,
        })
    return {"records": records}
