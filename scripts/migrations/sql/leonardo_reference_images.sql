-- Leonardo Reference Images Table
-- Stores reference images for Leonardo AI character consistency
-- Images are stored in Supabase Storage with metadata in this table

CREATE TABLE IF NOT EXISTS leonardo_reference_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    supabase_storage_url TEXT NOT NULL,
    leonardo_image_id VARCHAR(100),
    leonardo_upload_status VARCHAR(20) DEFAULT 'pending',
    last_leonardo_upload TIMESTAMPTZ,
    last_used TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_leonardo_reference_images_name ON leonardo_reference_images(name);
CREATE INDEX IF NOT EXISTS idx_leonardo_reference_images_is_active ON leonardo_reference_images(is_active);
CREATE INDEX IF NOT EXISTS idx_leonardo_reference_images_upload_status ON leonardo_reference_images(leonardo_upload_status);

-- Add comment for documentation
COMMENT ON TABLE leonardo_reference_images IS 'Stores reference images for Leonardo AI character consistency. Images are backed up in Supabase Storage.';

-- Add comments on columns
COMMENT ON COLUMN leonardo_reference_images.name IS 'Human-readable name for the reference image (e.g., refiloe_main)';
COMMENT ON COLUMN leonardo_reference_images.supabase_storage_url IS 'Public URL of the image in Supabase Storage (permanent backup)';
COMMENT ON COLUMN leonardo_reference_images.leonardo_image_id IS 'Cached Leonardo AI image ID (may expire)';
COMMENT ON COLUMN leonardo_reference_images.leonardo_upload_status IS 'Status: pending, uploaded, failed, expired';
COMMENT ON COLUMN leonardo_reference_images.last_leonardo_upload IS 'When the image was last uploaded to Leonardo AI';
COMMENT ON COLUMN leonardo_reference_images.last_used IS 'When this reference was last used for image generation';
