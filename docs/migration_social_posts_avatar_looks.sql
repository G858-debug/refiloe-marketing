-- Migration: Fix social_posts table and create avatar_looks table
-- Description: Add caption_text column to social_posts and create avatar_looks table
-- Date: 2025-11-29

-- ============================================
-- Part 1: Create avatar_looks table
-- ============================================

CREATE TABLE IF NOT EXISTS avatar_looks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    look_id VARCHAR(255) UNIQUE NOT NULL,
    photo_avatar_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'completed',
    look_type VARCHAR(100) NOT NULL,
    prompt TEXT,
    group_id VARCHAR(255),
    preview_url TEXT,
    image_urls JSONB,
    image_keys JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    look_config JSONB,

    -- Motion-related fields (optional)
    has_motion BOOLEAN DEFAULT FALSE,
    motion_id VARCHAR(255),
    motion_prompt TEXT,
    motion_type VARCHAR(100)
);

-- Create indexes for avatar_looks
CREATE INDEX IF NOT EXISTS idx_avatar_looks_look_id ON avatar_looks(look_id);
CREATE INDEX IF NOT EXISTS idx_avatar_looks_look_type ON avatar_looks(look_type);
CREATE INDEX IF NOT EXISTS idx_avatar_looks_status ON avatar_looks(status);
CREATE INDEX IF NOT EXISTS idx_avatar_looks_created_at ON avatar_looks(created_at DESC);

-- Add comments
COMMENT ON TABLE avatar_looks IS 'Stores generated avatar looks from HeyGen photo generation';
COMMENT ON COLUMN avatar_looks.look_id IS 'HeyGen look ID';
COMMENT ON COLUMN avatar_looks.photo_avatar_id IS 'HeyGen photo avatar ID';
COMMENT ON COLUMN avatar_looks.look_type IS 'Type of look (e.g., podcast_host, fitness_coach)';

-- ============================================
-- Part 2: Fix social_posts table schema
-- ============================================

-- Add caption_text column if it doesn't exist
-- Note: This assumes the table uses caption_text instead of content
ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS caption_text TEXT;

-- If content column exists but should be caption_text, migrate the data
-- Uncomment the following lines if you need to migrate from 'content' to 'caption_text':
-- DO $$
-- BEGIN
--     IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'social_posts' AND column_name = 'content') THEN
--         UPDATE social_posts SET caption_text = content WHERE caption_text IS NULL;
--         ALTER TABLE social_posts DROP COLUMN content;
--     END IF;
-- END $$;

-- Add indexes for commonly queried fields
CREATE INDEX IF NOT EXISTS idx_social_posts_status ON social_posts(status);
CREATE INDEX IF NOT EXISTS idx_social_posts_platform ON social_posts(platform);
CREATE INDEX IF NOT EXISTS idx_social_posts_scheduled_time ON social_posts(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_social_posts_created_at ON social_posts(created_at DESC);
