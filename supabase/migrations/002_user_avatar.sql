-- Profile avatar for Deltaplanspeech account UI
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_id VARCHAR(32) NOT NULL DEFAULT 'star';
