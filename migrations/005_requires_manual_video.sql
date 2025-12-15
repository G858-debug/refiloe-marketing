-- Add requires_manual_video flag to social_posts table
-- Used to mark posts that need manual video creation when Avatar IV credits are exhausted

-- Add requires_manual_video column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'social_posts'
        AND column_name = 'requires_manual_video'
    ) THEN
        ALTER TABLE social_posts
        ADD COLUMN requires_manual_video BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Create index for quick lookups of posts requiring manual video
CREATE INDEX IF NOT EXISTS idx_social_posts_requires_manual_video
ON social_posts(requires_manual_video)
WHERE requires_manual_video = TRUE;

-- Comment
COMMENT ON COLUMN social_posts.requires_manual_video IS 'Flag indicating post needs manual video creation (e.g., when Avatar IV credits exhausted)';
