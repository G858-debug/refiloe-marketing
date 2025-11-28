-- Migration: Create look_ratings table
-- Description: Store user ratings and preferences for avatar looks across different content types
-- Date: 2025-11-28

-- Create look_ratings table
CREATE TABLE IF NOT EXISTS look_ratings (
    id UUID PRIMARY KEY,
    look_id UUID NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Foreign key constraint (if avatar_looks table exists)
    CONSTRAINT fk_look_id FOREIGN KEY (look_id) REFERENCES avatar_looks(id) ON DELETE CASCADE,

    -- Unique constraint: one rating per look per content type
    CONSTRAINT unique_look_content_rating UNIQUE (look_id, content_type)
);

-- Create index on content_type for faster lookups
CREATE INDEX IF NOT EXISTS idx_look_ratings_content_type ON look_ratings(content_type);

-- Create index on look_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_look_ratings_look_id ON look_ratings(look_id);

-- Create index on rating for performance queries
CREATE INDEX IF NOT EXISTS idx_look_ratings_rating ON look_ratings(rating DESC);

-- Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_look_ratings_content_rating ON look_ratings(content_type, rating DESC);

-- Add helpful comments
COMMENT ON TABLE look_ratings IS 'Stores user ratings and preferences for avatar looks across different content types';
COMMENT ON COLUMN look_ratings.id IS 'Unique identifier for the rating record';
COMMENT ON COLUMN look_ratings.look_id IS 'Foreign key to avatar_looks table';
COMMENT ON COLUMN look_ratings.content_type IS 'Type of content (e.g., admin_tips, motivation, fitness)';
COMMENT ON COLUMN look_ratings.rating IS 'User rating from 1 to 5 stars';
COMMENT ON COLUMN look_ratings.notes IS 'Optional notes about the look performance';
COMMENT ON COLUMN look_ratings.created_at IS 'Timestamp when rating was created';
COMMENT ON COLUMN look_ratings.updated_at IS 'Timestamp when rating was last updated';

-- Sample query to get best performing looks by content type
-- SELECT l.look_type, lr.content_type, AVG(lr.rating) as avg_rating, COUNT(*) as rating_count
-- FROM look_ratings lr
-- JOIN avatar_looks l ON lr.look_id = l.id
-- GROUP BY l.look_type, lr.content_type
-- ORDER BY lr.content_type, avg_rating DESC;
