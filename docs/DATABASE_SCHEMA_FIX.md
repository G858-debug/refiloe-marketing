# Database Schema Fix

## Issue Summary

The video generation API was failing with the following errors:

1. **avatar_looks table**: 404 error - table doesn't exist
2. **social_posts table**: 400 error - `content` column doesn't exist

Error messages:
```
2025-11-29 23:20:44,488 - ERROR - Supabase request failed: POST .../avatar_looks
2025-11-29 23:20:44,488 - ERROR - Status: 404

2025-11-29 23:20:46,074 - ERROR - Status: 400
2025-11-29 23:20:46,074 - ERROR - Response: {"code":"PGRST204","details":null,"hint":null,
"message":"Could not find the 'content' column of 'social_posts' in the schema cache"}
```

## Root Cause

1. The `avatar_looks` table was never created in the Supabase database
2. The `social_posts` table uses `caption_text` as the column name, but the code was trying to insert into a `content` column

## Solution

### 1. Database Migration

Run the SQL migration script to create the missing table and fix the schema:

```bash
# Connect to your Supabase database and run:
psql -h <your-supabase-host> -U postgres -d postgres -f docs/migration_social_posts_avatar_looks.sql
```

Or execute the SQL directly in the Supabase SQL editor.

### 2. Code Changes

Updated `database.py` to use the correct column name:

**Before:**
```python
'content': post_data.get('content') or post_data.get('content_text'),
```

**After:**
```python
'caption_text': post_data.get('content') or post_data.get('content_text') or post_data.get('caption_text'),
```

This ensures backward compatibility by checking for `content`, `content_text`, and `caption_text` in that order.

## Migration Script Details

The migration script (`docs/migration_social_posts_avatar_looks.sql`) creates:

### avatar_looks Table

Stores generated avatar looks from HeyGen photo generation:

- `id` (UUID, primary key)
- `look_id` (VARCHAR, unique, HeyGen look ID)
- `photo_avatar_id` (VARCHAR, HeyGen photo avatar ID)
- `status` (VARCHAR, default 'completed')
- `look_type` (VARCHAR, e.g., 'podcast_host', 'fitness_coach')
- `prompt` (TEXT)
- `group_id` (VARCHAR)
- `preview_url` (TEXT)
- `image_urls` (JSONB, array of image URLs)
- `image_keys` (JSONB, array of image keys)
- `look_config` (JSONB, configuration used for generation)
- `has_motion` (BOOLEAN, default FALSE)
- `motion_id`, `motion_prompt`, `motion_type` (optional motion fields)
- `created_at`, `updated_at` (TIMESTAMPTZ)

Indexes:
- `idx_avatar_looks_look_id`
- `idx_avatar_looks_look_type`
- `idx_avatar_looks_status`
- `idx_avatar_looks_created_at`

### social_posts Table Updates

- Adds `caption_text` column if it doesn't exist
- Creates indexes for commonly queried fields:
  - `idx_social_posts_status`
  - `idx_social_posts_platform`
  - `idx_social_posts_scheduled_time`
  - `idx_social_posts_created_at`

## Testing

After running the migration, test the fixes:

1. Test avatar look generation:
   ```bash
   curl -X POST http://localhost:5000/api/test/generate-video \
     -H "Content-Type: application/json" \
     -d '{"look_type": "podcast_host", "script": "Test script"}'
   ```

2. Check that the `avatar_looks` table is populated:
   ```sql
   SELECT count(*) FROM avatar_looks;
   SELECT * FROM avatar_looks ORDER BY created_at DESC LIMIT 5;
   ```

3. Check that posts are saved correctly:
   ```sql
   SELECT id, caption_text, status FROM social_posts ORDER BY created_at DESC LIMIT 5;
   ```

## Verification

To verify the schema is correct:

```sql
-- Check avatar_looks table exists
SELECT table_name FROM information_schema.tables
WHERE table_name = 'avatar_looks';

-- Check caption_text column exists in social_posts
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'social_posts' AND column_name = 'caption_text';
```

## Rollback (if needed)

If you need to rollback the changes:

```sql
-- Remove avatar_looks table
DROP TABLE IF EXISTS avatar_looks CASCADE;

-- Remove caption_text column (only if you want to completely revert)
ALTER TABLE social_posts DROP COLUMN IF EXISTS caption_text;
```

Note: Be careful with rollback as it will delete data.

## Related Files

- `database.py` - Updated to use `caption_text` instead of `content`
- `social_media/looks_generator.py` - Uses the `avatar_looks` table
- `docs/migration_social_posts_avatar_looks.sql` - Migration script

## Future Improvements

Consider standardizing on a single column name across the codebase:
- Option 1: Migrate all references to use `caption_text`
- Option 2: Add a view or computed column for backward compatibility

Current implementation maintains backward compatibility by accepting multiple field names.
