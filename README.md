# refiloe-marketing
Social media automation and marketing for Refiloe

# Refiloe Marketing 📱

Social media automation and marketing system for Refiloe - the WhatsApp AI assistant for personal trainers.

## Features

- 🤖 **Automated Social Media**: AI-powered content generation and posting
- 📊 **Analytics Dashboard**: Track engagement and performance
- 📧 **Email Campaigns** (Coming soon)
- 📲 **WhatsApp Campaigns** (Coming soon)
- 🌐 **Landing Pages** (Coming soon)

## Architecture

This repository handles all marketing automation for Refiloe, including:

- Social media content generation (using Claude AI)
- Automated posting to Facebook, Instagram, etc.
- Analytics collection and reporting
- Future: Email campaigns, WhatsApp broadcasts, landing pages

**Important**: This app shares the same Supabase database as the main Refiloe app but runs as a separate service.

## Tech Stack

- **Backend**: Python Flask
- **Database**: Supabase (shared with main Refiloe app)
- **AI**: Anthropic Claude API for content generation
- **Image Generation**: Replicate API
- **Deployment**: Railway
- **Scheduling**: APScheduler

## Setup

### 1. Environment Variables

Set these in Railway (same Supabase credentials as main app):

```bash
# Supabase (SAME as main Refiloe app)
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key

# AI Services
ANTHROPIC_API_KEY=your_anthropic_key
REPLICATE_API_TOKEN=your_replicate_token

# Social Media
FACEBOOK_PAGE_ACCESS_TOKEN=your_facebook_token
FACEBOOK_PAGE_ID=your_page_id

# Settings
ENABLE_SOCIAL_MEDIA=true
PORT=5000
```

#### HeyGen Avatars

HeyGen avatar IDs are required for video generation. Use the helper script to provision them locally and copy the values into Railway:

1. Generate or update the local `.env` file:
   ```bash
   python scripts/setup_avatar_env.py
   ```
   The script writes all required `HEYGEN_AVATAR_*` variables to `.env`, creates `scripts/test_avatar_availability.py`, and prints Railway bulk-import instructions.
2. In Railway, open **Variables → Bulk Edit** and paste the following JSON payload:
   ```json
   {
     "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP": "110f75a397604454ba6f822c68f29949",
     "HEYGEN_AVATAR_CASUAL_CLOSEUP": "e39d22ad46c34b5599dc939c63ba1d89",
     "HEYGEN_AVATAR_FITNESS_FULLBODY": "3fa139effeb348a99b959065a2425363",
     "HEYGEN_AVATAR_CONFIDENT_SWIMWEAR_FULLBODY": "5d511d22069d4a7d9d75ffd78d1a0bda",
     "HEYGEN_AVATAR_SERIOUS_CLOSEUP": "efe8efb12f0a4bc8b961e22220fc974d",
     "HEYGEN_AVATAR_WARMSMILE_CLOSEUP": "9648b4e9da9c444c877214312c5ad27c",
     "HEYGEN_AVATAR_LAUGHING_CLOSEUP": "89c3da65880249e78e26070732b52f53",
     "HEYGEN_AVATAR_THREEQUARTERS_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
     "HEYGEN_AVATAR_SUMMERCASUAL_THREEQUARTERBODY": "12e5e8c825e547a0a67ad0057288a4da",
     "HEYGEN_AVATAR_GROUP": "89c3da65880249e78e26070732b52f53",
     "HEYGEN_AVATAR_DEFAULT": "5637676d31d54946b7585b012a3ce182"
   }
   ```
3. Add your HeyGen API key:
   ```bash
   HEYGEN_API_KEY=your_heygen_token
   ```
4. (Optional) Validate access locally before deploying:
   ```bash
   python scripts/test_avatar_availability.py
   ```

On application startup the Flask app now checks for the required HeyGen environment variables and verifies avatar availability. Status details are exposed on `/health` and `/api/status` under the `heygen` component.

### 2. Deploy to Railway

1. Create new Railway project
2. Connect this GitHub repository
3. Add environment variables
4. Deploy!

### 3. Verify Deployment

Visit your Railway app URL - you should see:

```json
{
  "status": "healthy",
  "service": "refiloe-marketing"
}
```

## Project Structure

```
refiloe-marketing/
├── social_media/          # Social media automation
│   ├── scheduler.py       # Main scheduler
│   ├── content_generator.py
│   ├── image_generator.py
│   ├── facebook_poster.py
│   ├── database.py
│   └── config.yaml
├── utils/                 # Shared utilities
│   └── logger.py
├── app.py                 # Main Flask application
├── config.py              # Configuration
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## How It Works

1. **Content Generation**: Runs daily at 6:00 AM SAST
   - AI generates engaging posts for trainers
   - Creates images using Replicate
   - Saves to Supabase database

2. **Content Posting**: Runs every 30 minutes
   - Checks for scheduled posts
   - Posts to social media platforms
   - Updates post status

3. **Analytics**: Runs daily at 11:00 PM SAST
   - Collects engagement metrics
   - Saves to database for reporting

## Relationship to Main Refiloe App

| Feature | Main Refiloe App | Marketing App |
|---------|------------------|---------------|
| WhatsApp Bot | ✅ | ❌ |
| Trainer/Client Management | ✅ | ❌ |
| Payment Processing | ✅ | ❌ |
| Social Media Automation | ❌ | ✅ |
| Analytics Dashboard | ❌ | ✅ |
| Email/WhatsApp Campaigns | ❌ | ✅ (future) |
| **Database** | **Supabase** | **Same Supabase** |

## Future Features

- 📧 Email campaign automation
- 📲 WhatsApp broadcast campaigns  
- 🌐 Landing page builder
- 📊 Advanced analytics dashboard
- 🎥 Video content automation

## Support

For issues or questions:
- Email: refiloe@refiloeradebe.co.za
- Website: refiloe.africa

---

Built with ❤️ for personal trainers globally
