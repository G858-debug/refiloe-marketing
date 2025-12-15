-- Avatar IV Credit Tracking Migration
-- Adds avatar_type and duration_seconds fields to video_generation_usage table
-- to support separate tracking of Avatar IV credits (90 credits/month, 1 credit = 60 seconds)

-- Add new columns to existing video_generation_usage table
-- If the table doesn't exist, create it with all fields
CREATE TABLE IF NOT EXISTS video_generation_usage (
    id UUID PRIMARY KEY,
    video_id TEXT NOT NULL,
    style TEXT,
    success BOOLEAN DEFAULT FALSE,
    duration_seconds INTEGER,
    credits_used INTEGER DEFAULT 1,
    requested_at TIMESTAMPTZ NOT NULL,
    avatar_type TEXT DEFAULT 'photo_avatar',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add avatar_type column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'video_generation_usage'
        AND column_name = 'avatar_type'
    ) THEN
        ALTER TABLE video_generation_usage
        ADD COLUMN avatar_type TEXT DEFAULT 'photo_avatar';
    END IF;
END $$;

-- Ensure duration_seconds exists (it should from video_generator.py but let's be safe)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'video_generation_usage'
        AND column_name = 'duration_seconds'
    ) THEN
        ALTER TABLE video_generation_usage
        ADD COLUMN duration_seconds INTEGER;
    END IF;
END $$;

-- Create index for efficient Avatar IV usage queries
CREATE INDEX IF NOT EXISTS idx_video_usage_avatar_type_requested
ON video_generation_usage(avatar_type, requested_at DESC);

-- Create index for monthly usage queries
CREATE INDEX IF NOT EXISTS idx_video_usage_requested_at
ON video_generation_usage(requested_at DESC);

-- Comment
COMMENT ON COLUMN video_generation_usage.avatar_type IS 'Type of avatar used: photo_avatar, avatar_iv, or standard';
COMMENT ON COLUMN video_generation_usage.duration_seconds IS 'Video duration in seconds (used for Avatar IV credit calculation)';
