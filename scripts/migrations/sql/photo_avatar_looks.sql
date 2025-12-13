-- Photo Avatar Looks Table
-- Stores the mapping between content types and HeyGen photo avatar IDs
-- This allows updating avatar configurations without code deployments

CREATE TABLE IF NOT EXISTS photo_avatar_looks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type VARCHAR(50) UNIQUE NOT NULL,
    photo_avatar_id VARCHAR(100) NOT NULL,
    label VARCHAR(100) NOT NULL,
    outfit_description TEXT,
    environment_description TEXT,
    makeup_description TEXT,
    lighting_description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_photo_avatar_looks_content_type ON photo_avatar_looks(content_type);
CREATE INDEX IF NOT EXISTS idx_photo_avatar_looks_is_active ON photo_avatar_looks(is_active);

-- Add comment for documentation
COMMENT ON TABLE photo_avatar_looks IS 'Stores HeyGen photo avatar configurations for different content types';

-- Ensure only one default
CREATE UNIQUE INDEX IF NOT EXISTS idx_photo_avatar_looks_single_default
ON photo_avatar_looks(is_default) WHERE is_default = TRUE;
