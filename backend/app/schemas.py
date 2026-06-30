from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str
    is_active: bool
    avatar_id: str = "star"
    created_at: datetime

    @computed_field
    @property
    def username(self) -> str:
        return self.name


class ProfileUpdateRequest(BaseModel):
    avatar_id: str | None = None


class SessionSummaryOut(BaseModel):
    id: int
    original_name: str
    status: str
    created_at: datetime
    updated_at: datetime
    positions_count: int = 0
    confirmed: bool = False
    has_table: bool = False
    export_count: int = 0
    last_export_at: datetime | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    username: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    created_at: datetime
    details_json: str | None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    celery_task_id: str | None
    status: str
    current_step: int = 1
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ProcessQueuedResponse(BaseModel):
    job: JobOut
    message: str


class TrackRecordBase(BaseModel):
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
    row_order: int = 0
    disputed_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    logical_record_index: int | None = None
    logical_block_index: int | None = None
    position_index: int | None = None
    position_type: str | None = None


class TrackRecordCreate(TrackRecordBase):
    pass


class TrackRecordUpdate(BaseModel):
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
    row_order: int | None = None
    disputed_fields: list[str] | None = None


class TrackRecordOut(TrackRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int


class TranscriptSegmentOut(BaseModel):
    start: float
    end: float
    text: str
    confidence: float | None = None


class LogicalRecordOut(BaseModel):
    """10.1 — логическая запись (контекст)."""

    index: int
    peregon: str | None = None
    put: str | None = None
    km: str | None = None
    piket: str | None = None
    comment: str | None = None
    segment_start: float | None = None
    segment_end: float | None = None
    positions_count: int = 0


class LogicalBlockOut(BaseModel):
    index: int
    text: str
    start: float | None = None
    end: float | None = None
    trigger: str | None = None


class WideTableOut(BaseModel):
    columns: list[str]
    rows: list[dict]


class InspectionItemStructured(BaseModel):
    order_in_record: int
    parameter_name: str | None = None
    canonical_parameter: str | None = None
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    defect_text: str | None = None
    speed_limit: str | None = None
    needs_review: bool = False


class InspectionRecordStructured(BaseModel):
    sequence_number: int
    start_sec: float | None = None
    end_sec: float | None = None
    date_value: str | None = None
    section_name: str | None = None
    haul_name: str | None = None
    track_number: str | None = None
    km_value: str | None = None
    picket_value: str | None = None
    object_name: str | None = None
    comment: str | None = None
    status: str | None = None
    source_text: str | None = None
    items: list[InspectionItemStructured] = Field(default_factory=list)


class StructuredRecordsOut(BaseModel):
    records: list[InspectionRecordStructured] = Field(default_factory=list)


class AudioSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_name: str
    status: str
    full_transcript: str | None
    confirmed: bool = False
    asr_avg_confidence: float | None = None
    created_at: datetime
    updated_at: datetime
    records: list[TrackRecordOut] = Field(default_factory=list)
    transcript_segments: list[TranscriptSegmentOut] = Field(default_factory=list)
    logical_blocks: list[LogicalBlockOut] = Field(default_factory=list)
    logical_records: list[LogicalRecordOut] = Field(default_factory=list)
    unknown_terms: list[dict] = Field(default_factory=list)
    parse_errors: list[dict] = Field(default_factory=list)
    validation_warnings: list[dict] = Field(default_factory=list)
    file_metadata: dict = Field(default_factory=dict)
    records_wide: WideTableOut | None = None
    records_form: WideTableOut | None = None
    active_job: JobOut | None = None
    logical_blocks_count: int = 0
    records_count: int = 0
    logical_records_count: int = 0
    positions_count: int = 0
    structured_records: StructuredRecordsOut | None = None


class ProcessResponse(BaseModel):
    session: AudioSessionOut
    message: str
