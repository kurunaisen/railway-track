"""
Схема БД FR 11.1–11.10.

users → audio_files → processing_jobs → transcripts / inspection_records / unknown_terms / exports
inspection_records → inspection_items
validation_errors → record_id и/или item_id
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

ROLES = ("admin", "operator", "viewer")
JOB_STATUSES = ("queued", "processing", "done", "failed")
RECORD_STATUSES = ("draft", "review", "approved")


# ── 11.1 users ──────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(32), default="operator")
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    audio_files: Mapped[list["AudioFile"]] = relationship(back_populates="uploader")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")

    @property
    def username(self) -> str:
        """Обратная совместимость API (логин по name)."""
        return self.name


# ── audit (NFR, не в FR 11) ─────────────────────────────────────────────────


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User | None"] = relationship(back_populates="audit_logs")


# ── 11.2 audio_files ────────────────────────────────────────────────────────


class AudioFile(Base):
    __tablename__ = "audio_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(512))
    stored_path: Mapped[str] = mapped_column(String(1024))
    converted_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    uploader: Mapped["User | None"] = relationship(back_populates="audio_files")
    jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="audio_file", cascade="all, delete-orphan", order_by="ProcessingJob.created_at"
    )


# ── 11.3 processing_jobs ────────────────────────────────────────────────────


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    audio_file_id: Mapped[int] = mapped_column(ForeignKey("audio_files.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    asr_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Операционные поля (очередь, конвейер)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    steps_log_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    audio_file: Mapped["AudioFile"] = relationship(back_populates="jobs")
    transcript: Mapped["Transcript | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    inspection_records: Mapped[list["InspectionRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="InspectionRecord.sequence_number"
    )
    unknown_terms: Mapped[list["UnknownTerm"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    exports: Mapped[list["Export"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    def get_steps_log(self) -> list[dict]:
        if not self.steps_log_json:
            return []
        return json.loads(self.steps_log_json)

    def set_steps_log(self, log: list[dict]) -> None:
        self.steps_log_json = json.dumps(log, ensure_ascii=False)

    def get_pipeline_metadata(self) -> dict:
        if not self.pipeline_metadata_json:
            return {}
        try:
            return json.loads(self.pipeline_metadata_json)
        except json.JSONDecodeError:
            return {}

    def set_pipeline_metadata(self, data: dict) -> None:
        self.pipeline_metadata_json = json.dumps(data, ensure_ascii=False)

    @property
    def completed_at(self) -> datetime | None:
        return self.finished_at


# ── 11.4 transcripts ────────────────────────────────────────────────────────


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"), unique=True, index=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True, default="ru")
    confidence_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["ProcessingJob"] = relationship(back_populates="transcript")
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="transcript", cascade="all, delete-orphan", order_by="TranscriptSegment.segment_index"
    )


# ── 11.5 transcript_segments ────────────────────────────────────────────────


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transcript_id: Mapped[int] = mapped_column(ForeignKey("transcripts.id"), index=True)
    segment_index: Mapped[int] = mapped_column(Integer, default=0)
    start_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    transcript: Mapped["Transcript"] = relationship(back_populates="segments")


# ── 11.6 inspection_records ─────────────────────────────────────────────────


class InspectionRecord(Base):
    __tablename__ = "inspection_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    start_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_value: Mapped[str | None] = mapped_column(String(32), nullable=True)
    section_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    haul_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    track_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    km_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    picket_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["ProcessingJob"] = relationship(back_populates="inspection_records")
    items: Mapped[list["InspectionItem"]] = relationship(
        back_populates="record", cascade="all, delete-orphan", order_by="InspectionItem.order_in_record"
    )
    validation_errors: Mapped[list["ValidationError"]] = relationship(
        back_populates="record", cascade="all, delete-orphan", foreign_keys="ValidationError.record_id"
    )


# ── 11.7 inspection_items ───────────────────────────────────────────────────


class InspectionItem(Base):
    __tablename__ = "inspection_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("inspection_records.id"), index=True)
    order_in_record: Mapped[int] = mapped_column(Integer, default=0)
    parameter_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    canonical_parameter: Mapped[str | None] = mapped_column(String(256), nullable=True)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    defect_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    speed_limit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    position_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    record: Mapped["InspectionRecord"] = relationship(back_populates="items")
    validation_errors: Mapped[list["ValidationError"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", foreign_keys="ValidationError.item_id"
    )


# ── 11.8 validation_errors ──────────────────────────────────────────────────


class ValidationError(Base):
    __tablename__ = "validation_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    record_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_records.id"), nullable=True, index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("inspection_items.id"), nullable=True, index=True)
    field_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="warning")

    record: Mapped["InspectionRecord | None"] = relationship(
        back_populates="validation_errors", foreign_keys=[record_id]
    )
    item: Mapped["InspectionItem | None"] = relationship(
        back_populates="validation_errors", foreign_keys=[item_id]
    )


# ── 11.9 unknown_terms ──────────────────────────────────────────────────────


class UnknownTerm(Base):
    __tablename__ = "unknown_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
    term_text: Mapped[str] = mapped_column(String(256), index=True)
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["ProcessingJob"] = relationship(back_populates="unknown_terms")


# ── 11.10 exports ───────────────────────────────────────────────────────────


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    format: Mapped[str] = mapped_column(String(32), default="xlsx")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["ProcessingJob"] = relationship(back_populates="exports")
