# FR 11 — схема для Supabase Postgres
# Выполните в Supabase Dashboard → SQL Editor

-- users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(256) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'operator',
    password_hash VARCHAR(256) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_name ON users (name);

-- audit_logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users (id),
    username VARCHAR(64),
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64),
    resource_id VARCHAR(64),
    ip_address VARCHAR(64),
    user_agent VARCHAR(512),
    details_json TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at);

-- audio_files
CREATE TABLE IF NOT EXISTS audio_files (
    id SERIAL PRIMARY KEY,
    original_filename VARCHAR(512) NOT NULL,
    stored_path VARCHAR(1024) NOT NULL,
    converted_path VARCHAR(1024),
    mime_type VARCHAR(128),
    duration_sec DOUBLE PRECISION,
    uploaded_by INTEGER REFERENCES users (id),
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_audio_files_uploaded_by ON audio_files (uploaded_by);

-- processing_jobs
CREATE TABLE IF NOT EXISTS processing_jobs (
    id SERIAL PRIMARY KEY,
    audio_file_id INTEGER NOT NULL REFERENCES audio_files (id),
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    asr_provider VARCHAR(64),
    llm_provider VARCHAR(64),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    celery_task_id VARCHAR(128),
    current_step INTEGER NOT NULL DEFAULT 1,
    steps_log_json TEXT,
    pipeline_metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_audio_file_id ON processing_jobs (audio_file_id);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_celery_task_id ON processing_jobs (celery_task_id);

-- transcripts
CREATE TABLE IF NOT EXISTS transcripts (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES processing_jobs (id),
    full_text TEXT,
    text_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    language VARCHAR(16) DEFAULT 'ru',
    confidence_avg DOUBLE PRECISION,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_transcripts_job_id ON transcripts (job_id);

-- transcript_segments
CREATE TABLE IF NOT EXISTS transcript_segments (
    id SERIAL PRIMARY KEY,
    transcript_id INTEGER NOT NULL REFERENCES transcripts (id),
    segment_index INTEGER NOT NULL DEFAULT 0,
    start_sec DOUBLE PRECISION,
    end_sec DOUBLE PRECISION,
    text TEXT NOT NULL,
    confidence DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS ix_transcript_segments_transcript_id ON transcript_segments (transcript_id);

-- inspection_records
CREATE TABLE IF NOT EXISTS inspection_records (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES processing_jobs (id),
    sequence_number INTEGER NOT NULL DEFAULT 0,
    start_sec DOUBLE PRECISION,
    end_sec DOUBLE PRECISION,
    date_value VARCHAR(32),
    section_name VARCHAR(256),
    haul_name VARCHAR(256),
    track_number VARCHAR(64),
    km_value VARCHAR(64),
    picket_value VARCHAR(64),
    object_name VARCHAR(256),
    comment TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    source_text TEXT
);
CREATE INDEX IF NOT EXISTS ix_inspection_records_job_id ON inspection_records (job_id);

-- inspection_items
CREATE TABLE IF NOT EXISTS inspection_items (
    id SERIAL PRIMARY KEY,
    record_id INTEGER NOT NULL REFERENCES inspection_records (id),
    order_in_record INTEGER NOT NULL DEFAULT 0,
    parameter_name VARCHAR(256),
    canonical_parameter VARCHAR(256),
    value_numeric DOUBLE PRECISION,
    value_text VARCHAR(128),
    unit VARCHAR(64),
    defect_text VARCHAR(256),
    speed_limit VARCHAR(64),
    confidence DOUBLE PRECISION,
    needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    position_type VARCHAR(32),
    raw_text TEXT
);
CREATE INDEX IF NOT EXISTS ix_inspection_items_record_id ON inspection_items (record_id);

-- validation_errors
CREATE TABLE IF NOT EXISTS validation_errors (
    id SERIAL PRIMARY KEY,
    record_id INTEGER REFERENCES inspection_records (id),
    item_id INTEGER REFERENCES inspection_items (id),
    field_name VARCHAR(64),
    error_code VARCHAR(64),
    error_message TEXT NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'warning'
);
CREATE INDEX IF NOT EXISTS ix_validation_errors_record_id ON validation_errors (record_id);
CREATE INDEX IF NOT EXISTS ix_validation_errors_item_id ON validation_errors (item_id);

-- unknown_terms
CREATE TABLE IF NOT EXISTS unknown_terms (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES processing_jobs (id),
    term_text VARCHAR(256) NOT NULL,
    context_text TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_unknown_terms_job_id ON unknown_terms (job_id);
CREATE INDEX IF NOT EXISTS ix_unknown_terms_term_text ON unknown_terms (term_text);

-- exports
CREATE TABLE IF NOT EXISTS exports (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES processing_jobs (id),
    file_path VARCHAR(1024),
    format VARCHAR(32) NOT NULL DEFAULT 'xlsx',
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_exports_job_id ON exports (job_id);
