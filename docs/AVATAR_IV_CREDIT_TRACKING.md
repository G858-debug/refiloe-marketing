# Avatar IV Credit Tracking

This document describes the Avatar IV credit tracking system for managing the 90-credit monthly allocation.

## Overview

Avatar IV has a monthly limit of **90 credits**, where:
- **1 credit = 60 seconds** of video
- Total monthly allocation = **5,400 seconds** (90 minutes) of video

The system tracks usage separately from regular HeyGen photo avatar usage and automatically prevents exceeding the monthly limit.

## Database Schema

### video_generation_usage Table

New fields added:
- `avatar_type`: Type of avatar used (`'photo_avatar'`, `'avatar_iv'`, or `'standard'`)
- `duration_seconds`: Video duration in seconds (used for Avatar IV credit calculation)

### social_posts Table

New field:
- `requires_manual_video`: Boolean flag indicating post needs manual video creation (e.g., when Avatar IV credits exhausted)

## API Methods

### VideoGenerator Methods

#### `get_avatar_iv_usage_this_month() -> int`
Returns total Avatar IV usage in seconds for the current month.

```python
usage_seconds = video_generator.get_avatar_iv_usage_this_month()
print(f"Used {usage_seconds} seconds this month")
```

#### `get_avatar_iv_remaining_credits() -> Dict[str, Any]`
Returns detailed credit information:

```python
credits = video_generator.get_avatar_iv_remaining_credits()
# Returns:
# {
#     "used_seconds": 720,
#     "limit_seconds": 5400,
#     "remaining_seconds": 4680,
#     "used_credits": 12.0,
#     "limit_credits": 90,
#     "remaining_credits": 78.0
# }
```

#### `can_generate_avatar_iv(estimated_duration_seconds: int) -> Tuple[bool, Optional[str]]`
Checks if Avatar IV video can be generated within credit limits.

```python
can_generate, reason = video_generator.can_generate_avatar_iv(90)
if not can_generate:
    print(f"Cannot generate: {reason}")
```

#### `generate_avatar_iv_video(..., wait_for_completion: bool = False)`
Updated to:
- Check credits before generation (raises `UsageLimitExceeded` if insufficient)
- Record usage with `avatar_type='avatar_iv'`
- Track actual duration when `wait_for_completion=True`

## API Endpoint

### GET `/api/avatar-iv-credits`

Returns current Avatar IV credit status:

```json
{
  "used": 720,
  "limit": 5400,
  "remaining": 4680,
  "remaining_videos_estimate": 52,
  "used_credits": 12.0,
  "limit_credits": 90,
  "remaining_credits": 78.0
}
```

- `used`, `limit`, `remaining`: Values in seconds
- `remaining_videos_estimate`: Estimated videos remaining (based on 90s average)
- `*_credits`: Values in credits (seconds / 60)

## Usage Example

### Generating Avatar IV Video with Credit Tracking

```python
from social_media.video_generator import VideoGenerator, UsageLimitExceeded

try:
    # Check credits first (optional - generate_avatar_iv_video does this automatically)
    can_generate, reason = video_generator.can_generate_avatar_iv(estimated_duration=90)
    if not can_generate:
        # Flag post for manual creation
        supabase_client.table('social_posts').update({
            'requires_manual_video': True,
            'notes': reason
        }).eq('id', post_id).execute()
        return

    # Generate video
    result = video_generator.generate_avatar_iv_video(
        script="Your video script here...",
        image_url="https://example.com/avatar.jpg",
        voice_id="voice-id-here",
        wait_for_completion=True  # Will record actual duration
    )

    print(f"Video generated: {result['video_id']}")
    print(f"Duration: {result.get('duration')} seconds")

except UsageLimitExceeded as e:
    # Credits exhausted - flag post for manual creation
    print(f"Credits exhausted: {e}")
    supabase_client.table('social_posts').update({
        'requires_manual_video': True,
        'notes': str(e)
    }).eq('id', post_id).execute()

except Exception as e:
    print(f"Video generation failed: {e}")
```

### Checking Credits Before Batch Generation

```python
# Get current credit status
credits = video_generator.get_avatar_iv_remaining_credits()
print(f"Remaining credits: {credits['remaining_credits']}")

# Estimate how many videos can be generated
avg_video_duration = 90  # seconds
max_videos = int(credits['remaining_seconds'] / avg_video_duration)
print(f"Can generate approximately {max_videos} more videos this month")
```

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Avatar IV Credits (1 credit = 60 seconds of video)
# Monthly limit: 90 credits = 5400 seconds
AVATAR_IV_MONTHLY_LIMIT_CREDITS=90
```

## Database Migrations

Run the following migrations:

1. `migrations/004_avatar_iv_credits.sql` - Adds `avatar_type` and `duration_seconds` to `video_generation_usage`
2. `migrations/005_requires_manual_video.sql` - Adds `requires_manual_video` flag to `social_posts`

```bash
# Apply migrations using Supabase CLI or SQL editor
psql $DATABASE_URL -f migrations/004_avatar_iv_credits.sql
psql $DATABASE_URL -f migrations/005_requires_manual_video.sql
```

## Credit Reset

Credits automatically reset on the 1st of each month. The tracking uses the `requested_at` timestamp to filter records for the current month.

## Monitoring

### Dashboard Query

To see posts requiring manual video creation:

```sql
SELECT id, platform, content_type, created_at, notes
FROM social_posts
WHERE requires_manual_video = TRUE
ORDER BY created_at DESC;
```

### Monthly Usage Query

```sql
SELECT
    DATE_TRUNC('month', requested_at) as month,
    COUNT(*) as video_count,
    SUM(duration_seconds) as total_seconds,
    ROUND(SUM(duration_seconds)::numeric / 60, 2) as total_credits
FROM video_generation_usage
WHERE avatar_type = 'avatar_iv'
    AND success = TRUE
GROUP BY DATE_TRUNC('month', requested_at)
ORDER BY month DESC;
```

## Error Handling

The system raises `UsageLimitExceeded` exception when:
- Avatar IV credits are insufficient for the requested video duration
- This exception should be caught and handled appropriately (e.g., by flagging the post for manual creation)

```python
from social_media.video_generator import UsageLimitExceeded

try:
    video_generator.generate_avatar_iv_video(...)
except UsageLimitExceeded as e:
    # Handle credit exhaustion
    handle_manual_video_required(post_id, str(e))
```
