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
