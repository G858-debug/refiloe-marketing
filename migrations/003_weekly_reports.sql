-- Weekly Reports Table
-- Stores generated weekly performance reports

CREATE TABLE IF NOT EXISTS weekly_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Report period
    week_start TIMESTAMPTZ NOT NULL,
    week_end TIMESTAMPTZ NOT NULL,

    -- Metrics snapshot (JSON)
    metrics JSONB NOT NULL DEFAULT '{}',

    -- Formatted versions
    whatsapp_text TEXT,
    html_content TEXT,

    -- Insights generated
    insights JSONB DEFAULT '[]',

    -- Delivery status
    sent_via_whatsapp BOOLEAN DEFAULT FALSE,
    whatsapp_sent_at TIMESTAMPTZ,
    whatsapp_message_id TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_weekly_reports_week_start
ON weekly_reports(week_start DESC);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_weekly_reports_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS weekly_reports_updated_at ON weekly_reports;
CREATE TRIGGER weekly_reports_updated_at
    BEFORE UPDATE ON weekly_reports
    FOR EACH ROW
    EXECUTE FUNCTION update_weekly_reports_updated_at();

-- Comment
COMMENT ON TABLE weekly_reports IS 'Stores weekly performance reports for the marketing system';
