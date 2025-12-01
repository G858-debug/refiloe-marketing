-- Migration: Create comment_interactions table
-- Description: Store Facebook comments and automated AI-powered replies
-- Date: 2025-12-01

-- Create comment_interactions table
CREATE TABLE IF NOT EXISTS comment_interactions (
    id UUID PRIMARY KEY,
    facebook_comment_id VARCHAR(255) UNIQUE NOT NULL,
    post_id UUID,
    comment_text TEXT NOT NULL,
    comment_author VARCHAR(255),
    comment_author_id VARCHAR(255),
    category VARCHAR(50) NOT NULL CHECK (category IN ('question', 'positive', 'negative', 'spam', 'engagement')),
    reply_text TEXT,
    replied_at TIMESTAMPTZ,
    flagged_for_review BOOLEAN DEFAULT FALSE,
    sentiment_score FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Foreign key constraint to social_posts table
    CONSTRAINT fk_post_id FOREIGN KEY (post_id) REFERENCES social_posts(id) ON DELETE CASCADE
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_comment_interactions_post_id ON comment_interactions(post_id);
CREATE INDEX IF NOT EXISTS idx_comment_interactions_category ON comment_interactions(category);
CREATE INDEX IF NOT EXISTS idx_comment_interactions_flagged ON comment_interactions(flagged_for_review) WHERE flagged_for_review = TRUE;
CREATE INDEX IF NOT EXISTS idx_comment_interactions_facebook_comment_id ON comment_interactions(facebook_comment_id);
CREATE INDEX IF NOT EXISTS idx_comment_interactions_created_at ON comment_interactions(created_at DESC);

-- Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_comment_interactions_post_category ON comment_interactions(post_id, category);

-- Add helpful comments
COMMENT ON TABLE comment_interactions IS 'Stores Facebook comments and AI-powered automated replies';
COMMENT ON COLUMN comment_interactions.id IS 'Unique identifier for the comment interaction';
COMMENT ON COLUMN comment_interactions.facebook_comment_id IS 'Facebook comment ID from Graph API';
COMMENT ON COLUMN comment_interactions.post_id IS 'Foreign key to social_posts table';
COMMENT ON COLUMN comment_interactions.comment_text IS 'Original comment text from user';
COMMENT ON COLUMN comment_interactions.comment_author IS 'Name of the person who commented';
COMMENT ON COLUMN comment_interactions.comment_author_id IS 'Facebook user ID of the commenter';
COMMENT ON COLUMN comment_interactions.category IS 'AI-categorized comment type (question, positive, negative, spam, engagement)';
COMMENT ON COLUMN comment_interactions.reply_text IS 'Generated reply text from AI';
COMMENT ON COLUMN comment_interactions.replied_at IS 'Timestamp when reply was posted to Facebook';
COMMENT ON COLUMN comment_interactions.flagged_for_review IS 'Flag for comments requiring human review';
COMMENT ON COLUMN comment_interactions.sentiment_score IS 'Sentiment analysis score (-1 to 1)';
COMMENT ON COLUMN comment_interactions.created_at IS 'Timestamp when comment was first received';
COMMENT ON COLUMN comment_interactions.updated_at IS 'Timestamp when record was last updated';

-- Sample queries for analytics
-- Get comment category distribution
-- SELECT category, COUNT(*) as count,
--        AVG(CASE WHEN replied_at IS NOT NULL THEN 1 ELSE 0 END) * 100 as reply_rate
-- FROM comment_interactions
-- WHERE created_at >= NOW() - INTERVAL '7 days'
-- GROUP BY category;

-- Get comments requiring review
-- SELECT ci.*, sp.caption_text as post_caption
-- FROM comment_interactions ci
-- JOIN social_posts sp ON ci.post_id = sp.id
-- WHERE ci.flagged_for_review = TRUE
-- ORDER BY ci.created_at DESC;
