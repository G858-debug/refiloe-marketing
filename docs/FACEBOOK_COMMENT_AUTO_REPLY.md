# Facebook Comment Auto-Reply System

## Overview

The Facebook Comment Auto-Reply System is an AI-powered feature that automatically monitors, analyzes, and responds to comments on Refiloe's Facebook posts using Claude AI. The system categorizes comments by intent, generates contextual replies in Refiloe's voice, and flags sensitive comments for human review.

## Features

### 1. Intelligent Comment Analysis
- **AI Categorization**: Uses Claude to categorize each comment into one of five types:
  - `question` - User asking for information or advice
  - `positive` - Praise, thanks, or encouragement
  - `negative` - Complaints or criticism
  - `spam` - Promotional or irrelevant content
  - `engagement` - Simple reactions (emojis, short phrases)

- **Sentiment Analysis**: Assigns sentiment scores from -1.0 (very negative) to 1.0 (very positive)

### 2. Contextual Reply Generation
- Generates personalized replies using Claude AI
- Maintains Refiloe's personality (friendly, helpful, professional, encouraging)
- Keeps replies under 200 characters with relevant emojis
- Uses post context to generate more relevant responses

### 3. Smart Reply Rules
- **Auto-reply to**: Questions, positive comments, and engagement
- **Flag for review**: Negative comments
- **Ignore**: Spam

### 4. Human-like Behavior
- 30-second delay before posting replies (configurable)
- Daily limit of 50 replies to appear natural
- Tracks reply counts per day

### 5. Monitoring & Analytics
- Stores all comment interactions in database
- Tracks categories, sentiment scores, and reply status
- Provides statistics via API endpoints
- Flags sensitive comments for human review

## Architecture

### Components

1. **CommentManager** (`social_media/comment_manager.py`)
   - Main class for comment processing
   - Handles AI analysis and reply generation
   - Manages database storage and tracking

2. **FacebookPoster** (`facebook_poster.py`)
   - Extended with two new methods:
     - `get_post_comments()` - Fetch comments from Facebook
     - `reply_to_comment()` - Post replies to Facebook

3. **Webhook Endpoints** (`app.py`)
   - `GET /webhook/facebook` - Verification endpoint for Facebook
   - `POST /webhook/facebook` - Receives real-time comment notifications
   - `GET /api/comments/flagged` - Get comments needing review
   - `GET /api/comments/stats` - Get comment statistics

4. **Scheduled Job** (`social_media/scheduler.py`)
   - Runs every 15 minutes to check for new comments
   - Automatically processes and replies to new comments
   - Job ID: `comment_processing_interval`

5. **Database Table** (`comment_interactions`)
   - Stores all comment data and interactions
   - Tracks replies, categories, sentiment scores
   - Flags for human review

## Configuration

All settings are in `config.yaml` under the `comment_automation` section:

```yaml
comment_automation:
  enabled: true

  # Categories that trigger automatic replies
  auto_reply_categories:
    - "question"
    - "positive"
    - "engagement"

  # Categories flagged for human review
  flag_for_review:
    - "negative"

  # Categories to ignore
  ignore:
    - "spam"

  # Rate limiting
  max_daily_replies: 50
  reply_delay_seconds: 30

  # Processing frequency
  check_interval_minutes: 15

  # Reply settings
  max_reply_length: 200
  use_emojis: true
  max_emojis_per_reply: 2
```

## Setup Instructions

### 1. Database Migration

Run the SQL migration to create the `comment_interactions` table:

```bash
# Execute the migration file in your Supabase dashboard or via psql
psql $DATABASE_URL < docs/migration_comment_interactions.sql
```

### 2. Environment Variables

Ensure these environment variables are set:

```bash
# Required for comment processing
ANTHROPIC_API_KEY=your_anthropic_api_key
PAGE_ACCESS_TOKEN=your_facebook_page_token
PAGE_ID=your_facebook_page_id

# Optional - for webhook verification
FACEBOOK_VERIFY_TOKEN=refiloe_webhook_token_2025
```

### 3. Facebook Webhook Setup

1. Go to Facebook Developer Console > App > Webhooks
2. Set up a webhook subscription for your page
3. Webhook URL: `https://your-domain.com/webhook/facebook`
4. Verify Token: `refiloe_webhook_token_2025` (or your custom token)
5. Subscribe to `feed` events

### 4. Enable the Feature

The feature is enabled by default in `config.yaml`. To disable:

```yaml
comment_automation:
  enabled: false
```

## Usage

### Automatic Processing

Once set up, the system automatically:
1. Checks for new comments every 15 minutes
2. Analyzes each comment with AI
3. Generates and posts appropriate replies
4. Stores all interactions in the database
5. Flags sensitive comments for review

### Manual Monitoring

#### Get Flagged Comments

```bash
curl https://your-domain.com/api/comments/flagged?limit=50
```

Response:
```json
{
  "success": true,
  "count": 3,
  "comments": [
    {
      "id": "uuid",
      "facebook_comment_id": "fb_comment_id",
      "comment_text": "This is terrible!",
      "category": "negative",
      "sentiment_score": -0.8,
      "flagged_for_review": true,
      "created_at": "2025-12-01T10:30:00"
    }
  ]
}
```

#### Get Comment Statistics

```bash
curl https://your-domain.com/api/comments/stats?days=7
```

Response:
```json
{
  "success": true,
  "stats": {
    "total_comments": 45,
    "by_category": {
      "question": 15,
      "positive": 20,
      "engagement": 8,
      "negative": 2
    },
    "replied_count": 38,
    "flagged_count": 2,
    "avg_sentiment": 0.65,
    "reply_rate": 84.4
  },
  "period_days": 7
}
```

## Database Schema

### comment_interactions Table

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| facebook_comment_id | VARCHAR(255) | Unique Facebook comment ID |
| post_id | UUID | Foreign key to social_posts |
| comment_text | TEXT | Original comment text |
| comment_author | VARCHAR(255) | Commenter's name |
| comment_author_id | VARCHAR(255) | Commenter's Facebook ID |
| category | VARCHAR(50) | AI-assigned category |
| reply_text | TEXT | Generated reply (if any) |
| replied_at | TIMESTAMPTZ | When reply was posted |
| flagged_for_review | BOOLEAN | Needs human review |
| sentiment_score | FLOAT | -1.0 to 1.0 |
| created_at | TIMESTAMPTZ | When comment was received |
| updated_at | TIMESTAMPTZ | Last update timestamp |

## Example Workflow

1. **User comments on Facebook post**: "How do I get started with meal planning?"

2. **Scheduler job runs** (every 15 minutes):
   - Fetches new comments from recent posts
   - Finds the new comment

3. **Comment analysis**:
   - Claude analyzes: "This is a question"
   - Category: `question`
   - Sentiment: `0.5` (neutral/positive)

4. **Reply generation**:
   - Claude generates: "Great question! Meal planning starts with setting clear goals. DM me for a free starter guide! 💪"
   - System waits 30 seconds (appears more human)
   - Posts reply to Facebook

5. **Database storage**:
   - Saves interaction with all details
   - Tracks that reply was posted successfully

6. **Result**: User receives helpful reply within 15-20 minutes, automatically

## Refiloe's Voice Guidelines

The AI is configured to reply in Refiloe's personality:

- **Friendly**: "Love your energy! 🙌"
- **Helpful**: "Let me help you with that..."
- **Professional**: Maintains expertise and credibility
- **Encouraging**: "You've got this! 💪"

## Rate Limiting

To appear natural and avoid spam detection:

- **Daily limit**: 50 replies per day
- **Reply delay**: 30 seconds before posting
- **Check frequency**: Every 15 minutes
- **Batch processing**: Processes all new comments in each cycle

## Best Practices

1. **Monitor flagged comments daily**: Review negative comments and respond personally if needed

2. **Adjust categories**: If certain comment types need different handling, update `config.yaml`

3. **Track analytics**: Use `/api/comments/stats` to monitor performance

4. **Tune sentiment threshold**: Adjust `sentiment_threshold_negative` in config if too many/few comments are flagged

5. **Scale gradually**: Start with lower `max_daily_replies`, increase as you gain confidence

## Troubleshooting

### No comments being processed

Check:
- ✅ `comment_automation.enabled: true` in config.yaml
- ✅ ANTHROPIC_API_KEY is set
- ✅ PAGE_ACCESS_TOKEN and PAGE_ID are set
- ✅ Scheduler is running (`/scheduler/status`)
- ✅ Recent posts exist with `status: published`

### Replies not posting

Check:
- ✅ Daily limit not reached (`max_daily_replies`)
- ✅ Facebook token has correct permissions
- ✅ Comment categories match `auto_reply_categories`

### Too many flagged comments

Adjust in `config.yaml`:
```yaml
sentiment_threshold_negative: -0.7  # More strict (only very negative)
```

## Future Enhancements

- [ ] Multi-language support
- [ ] A/B testing for reply styles
- [ ] Learning from human corrections
- [ ] Reply templates for common questions
- [ ] Integration with WhatsApp for escalation
- [ ] Dashboard for comment management

## Security Notes

- All AI processing uses OpenAI's API with standard safety filters
- Spam detection prevents promotional content engagement
- Negative comments are flagged, not auto-replied
- Rate limiting prevents abuse
- Facebook tokens stored securely in environment variables

## Support

For issues or questions:
1. Check logs in `/var/log/refiloe` or application logs
2. Review scheduler status at `/scheduler/status`
3. Check comment stats at `/api/comments/stats`
4. Verify database migration was applied

---

**Created**: 2025-12-01
**Author**: Refiloe AI Assistant
**Version**: 1.0
