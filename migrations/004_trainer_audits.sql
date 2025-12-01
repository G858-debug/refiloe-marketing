-- Migration: Create trainer_audits table
-- Description: Stores data from the Trainer Time Audit Calculator for lead generation
-- Date: 2025-12-01

CREATE TABLE IF NOT EXISTS trainer_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Lead Information
    name TEXT NOT NULL,
    country_code TEXT NOT NULL DEFAULT '+27',
    phone TEXT NOT NULL,

    -- Business Metrics
    active_clients INTEGER NOT NULL,
    hourly_rate DECIMAL(10, 2) NOT NULL,

    -- Time Breakdown (hours per week)
    scheduling_hours DECIMAL(4, 1) NOT NULL,
    payment_hours DECIMAL(4, 1) NOT NULL,
    program_hours DECIMAL(4, 1) NOT NULL,
    message_hours DECIMAL(4, 1) NOT NULL,
    admin_hours DECIMAL(4, 1) NOT NULL,

    -- Calculated Values
    total_hours DECIMAL(5, 1) NOT NULL,
    weekly_lost DECIMAL(10, 2) NOT NULL,
    monthly_lost DECIMAL(10, 2) NOT NULL,
    yearly_lost DECIMAL(10, 2) NOT NULL,
    biggest_time_sink TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes for common queries
    CONSTRAINT valid_phone CHECK (length(phone) >= 8),
    CONSTRAINT valid_clients CHECK (active_clients >= 1 AND active_clients <= 100),
    CONSTRAINT valid_rate CHECK (hourly_rate > 0)
);

-- Index for searching by creation date
CREATE INDEX IF NOT EXISTS idx_trainer_audits_created_at ON trainer_audits(created_at DESC);

-- Index for searching by phone (for deduplication)
CREATE INDEX IF NOT EXISTS idx_trainer_audits_phone ON trainer_audits(country_code, phone);

-- Index for analytics
CREATE INDEX IF NOT EXISTS idx_trainer_audits_biggest_sink ON trainer_audits(biggest_time_sink);

-- Add updated_at trigger
CREATE OR REPLACE FUNCTION update_trainer_audits_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_trainer_audits_updated_at
    BEFORE UPDATE ON trainer_audits
    FOR EACH ROW
    EXECUTE FUNCTION update_trainer_audits_updated_at();

-- Grant permissions (adjust based on your RLS policies)
ALTER TABLE trainer_audits ENABLE ROW LEVEL SECURITY;

-- Create a policy that allows inserts (for the form submission)
CREATE POLICY "Allow public inserts" ON trainer_audits
    FOR INSERT
    WITH CHECK (true);

-- Create a policy for reading (restrict to authenticated users)
CREATE POLICY "Allow authenticated reads" ON trainer_audits
    FOR SELECT
    USING (auth.role() = 'authenticated');
