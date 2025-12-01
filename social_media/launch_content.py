"""Launch content seeder for Refiloe's Facebook launch.

This module contains the initial 3 days of launch content designed to introduce
Refiloe to personal trainers, demonstrate value, and drive engagement.

Content strategy:
- Day 1: Introduction - Who is Refiloe and what problems does she solve
- Day 2: Value - Deep dive into time savings and benefits
- Day 3: Engagement - Success stories and community building

All posts are targeted at personal trainers worldwide with a friendly,
relatable, and encouraging tone.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List
import pytz

# Add parent directory to path to import from root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SocialMediaDatabase
from utils.logger import log_info, log_error, log_warning
from supabase import create_client


# SAST timezone for scheduling
SAST = pytz.timezone('Africa/Johannesburg')


# ============================================================================
# DAY 1: INTRODUCTION
# ============================================================================

DAY_1_POSTS = [
    {
        # 08:00 SAST - Meet Refiloe Introduction
        "title": "Meet Refiloe - Your AI Admin Assistant",
        "content": """Meet Refiloe 👋

I'm not here to replace you. I'm here to free you.

While you're transforming lives in the gym, I'm handling the jobs that drain your energy:
✅ Client check-ins and follow-ups
✅ Schedule management
✅ Payment reminders
✅ Progress tracking
✅ All the admin that steals your evenings

You became a trainer to change lives, not to chase invoices.

I'm Refiloe - and I do all the jobs a trainer doesn't want to do.

What's the one admin task you wish would just... disappear? 💬""",
        "post_type": "video",
        "video_duration": 60,
        "video_type": "avatar_intro",
        "content_theme": "introduction",
        "hashtags": [
            "#PersonalTrainer",
            "#FitnessCoach",
            "#RefiloeAI",
            "#TrainerLife",
            "#AdminHacks",
            "#FitnessBusiness",
            "#TrainerTools"
        ],
        "call_to_action": "What's the one admin task you wish would just... disappear? 💬",
        "avatar_env": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
        "scheduled_time": "08:00",
        "day_offset": 0
    },
    {
        # 13:00 SAST - Carousel about admin pain points
        "title": "5 Admin Tasks Killing Your Time",
        "content": """5 admin tasks that are stealing hours from your training business 📋

Swipe to see if you're losing time to these silent productivity killers.

Every hour you spend on admin is an hour you're not:
→ Training clients who need you
→ Building your business
→ Living your life

It doesn't have to be this way.

#PersonalTrainer #TrainerLife #AdminHacks #FitnessCoach #TrainerTips #TimeManagement #FitnessBusiness #RefiloeAI

Which one hits hardest for you? Drop a number below! 👇""",
        "post_type": "carousel",
        "content_theme": "pain_point",
        "hashtags": [
            "#PersonalTrainer",
            "#TrainerLife",
            "#AdminHacks",
            "#FitnessCoach",
            "#TrainerTips",
            "#TimeManagement",
            "#FitnessBusiness",
            "#RefiloeAI"
        ],
        "call_to_action": "Which one hits hardest for you? Drop a number below! 👇",
        "avatar_env": None,  # Carousel doesn't need avatar
        "scheduled_time": "13:00",
        "day_offset": 0,
        "generation_prompt": """Create a 5-image carousel about admin tasks that waste trainers' time:

Slide 1 (Cover): Bold text: "5 ADMIN TASKS KILLING YOUR TIME" with a stressed trainer surrounded by paperwork
Slide 2: "1. Chasing Late Payments" - Show frustrated trainer looking at unpaid invoices
Slide 3: "2. Manual Schedule Management" - Calendar chaos, double bookings, missed appointments
Slide 4: "3. Client Check-ins & Follow-ups" - Endless message threads, unanswered questions
Slide 5: "4. Progress Tracking Spreadsheets" - Complex spreadsheets, manual data entry
Slide 6: "5. Social Media Content Creation" - Blank screen, no time for posting

Style: Clean, modern, professional but relatable. Use warm colors. Each slide should have a clear number and title."""
    },
    {
        # 18:00 SAST - Pain point video
        "title": "That Moment When Your Admin Takes Over",
        "content": """That moment when you realize you've spent more time on admin today than actually training...

The message notifications pile up.
The schedule needs updating.
Someone needs a payment reminder.
Another client wants to reschedule.

And it's already 8 PM.

You didn't build a training business to become a full-time administrator.

Tomorrow can be different. 🔥

#TrainerLife #PersonalTrainerProblems #FitnessCoach #AdminOverwhelm #TrainerStruggles #RefiloeAI #FitnessBusiness

Tag a trainer who needs to see this 👥""",
        "post_type": "video",
        "video_duration": 30,
        "video_type": "pain_point",
        "content_theme": "pain_point",
        "hashtags": [
            "#TrainerLife",
            "#PersonalTrainerProblems",
            "#FitnessCoach",
            "#AdminOverwhelm",
            "#TrainerStruggles",
            "#RefiloeAI",
            "#FitnessBusiness"
        ],
        "call_to_action": "Tag a trainer who needs to see this 👥",
        "avatar_env": "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP",
        "scheduled_time": "18:00",
        "day_offset": 0
    }
]


# ============================================================================
# DAY 2: VALUE PROPOSITION
# ============================================================================

DAY_2_POSTS = [
    {
        # 08:00 SAST - Value deep dive
        "title": "How Trainers Lose 15 Hours Per Week",
        "content": """Let me show you where your week actually goes 📊

Monday through Friday:
→ 3 hours: Chasing payments and invoicing
→ 4 hours: Schedule management and rebooking
→ 3 hours: Client check-ins and progress updates
→ 2 hours: Social media and marketing
→ 3 hours: Answering the same questions repeatedly

That's 15 hours. Every. Single. Week.

15 hours you could spend:
✅ Training 15 more clients
✅ Building new programs
✅ Actually having a weekend
✅ Remember what rest feels like?

Here's what changes when admin runs itself:
Your mornings start with training, not emails.
Your evenings end with life, not spreadsheets.
Your weekends are yours again.

What would you do with 15 extra hours? 💡

#PersonalTrainer #FitnessCoach #TrainerLife #TimeManagement #TrainerTips #FitnessBusiness #RefiloeAI #AdminAutomation

Comment below with ONE thing you'd do with your time back! 💬""",
        "post_type": "video",
        "video_duration": 60,
        "video_type": "educational",
        "content_theme": "educational",
        "hashtags": [
            "#PersonalTrainer",
            "#FitnessCoach",
            "#TrainerLife",
            "#TimeManagement",
            "#TrainerTips",
            "#FitnessBusiness",
            "#RefiloeAI",
            "#AdminAutomation"
        ],
        "call_to_action": "Comment below with ONE thing you'd do with your time back! 💬",
        "avatar_env": "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP",
        "scheduled_time": "08:00",
        "day_offset": 1
    },
    {
        # 13:00 SAST - Quote image
        "title": "Your Value Isn't in Admin",
        "content": """"You didn't become a trainer to be good at admin.

You became a trainer to be great at transforming lives.

Let the admin handle itself." ⭐

Every minute you spend on admin is a minute you're not doing what you do best - changing lives.

Your expertise is in the gym, not in spreadsheets.
Your impact is with clients, not with invoices.
Your value is in transformation, not in task management.

What if the only thing on your to-do list... was training?

#PersonalTrainer #FitnessCoach #TrainerMotivation #TrainerLife #FitnessMotivation #TrainerInspiration #RefiloeAI #FitnessBusiness

Save this if you need the reminder 💾""",
        "post_type": "single_image",
        "content_theme": "motivational",
        "hashtags": [
            "#PersonalTrainer",
            "#FitnessCoach",
            "#TrainerMotivation",
            "#TrainerLife",
            "#FitnessMotivation",
            "#TrainerInspiration",
            "#RefiloeAI",
            "#FitnessBusiness"
        ],
        "call_to_action": "Save this if you need the reminder 💾",
        "avatar_env": None,  # Single image doesn't need avatar
        "scheduled_time": "13:00",
        "day_offset": 1,
        "generation_prompt": """Create an inspirational quote image for trainers:

Main text (large, bold): "You didn't become a trainer to be good at admin."
Secondary text: "You became a trainer to be great at transforming lives."
Bottom text: "Let the admin handle itself."

Background: Professional fitness studio setting, soft focus with warm lighting
Visual elements: Subtle fitness equipment in background, maybe a kettlebell or dumbbells
Color scheme: Warm, motivational (golds, deep blues, warm whites)
Style: Clean, modern, Instagram-worthy

Add small "- Refiloe" signature at bottom right
Image should feel empowering and validating, not salesy."""
    },
    {
        # 18:00 SAST - Quick tip video
        "title": "The 30-Second Admin Check",
        "content": """Quick trainer tip: The 30-second admin check 💡

What if checking in with all your clients took 30 seconds instead of 30 minutes?

What if payment reminders sent themselves?

What if your schedule just... worked?

That's not a dream. That's automation.

And it's how the best trainers are getting their time back.

#TrainerTips #FitnessCoach #PersonalTrainer #AdminHacks #TrainerHacks #FitnessTech #RefiloeAI #SmartTraining

Drop a 🔥 if you're ready for this!""",
        "post_type": "video",
        "video_duration": 30,
        "video_type": "quick_tip",
        "content_theme": "educational",
        "hashtags": [
            "#TrainerTips",
            "#FitnessCoach",
            "#PersonalTrainer",
            "#AdminHacks",
            "#TrainerHacks",
            "#FitnessTech",
            "#RefiloeAI",
            "#SmartTraining"
        ],
        "call_to_action": "Drop a 🔥 if you're ready for this!",
        "avatar_env": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
        "scheduled_time": "18:00",
        "day_offset": 1
    }
]


# ============================================================================
# DAY 3: ENGAGEMENT & COMMUNITY
# ============================================================================

DAY_3_POSTS = [
    {
        # 08:00 SAST - Success story teaser
        "title": "From Burnout to Balance",
        "content": """Three months ago, Sarah was training from 5 AM to 8 PM.

Then spending another 3 hours on admin every night.

Her partner barely saw her.
Her clients got delayed responses.
Her business was growing, but she was shrinking.

Today? She trains the same number of clients, but she's home by 6 PM.

Her secret isn't working less.
It's letting admin work for itself.

What Sarah did that changed everything:
✅ Automated client check-ins
✅ Self-managing schedule
✅ Automatic payment reminders
✅ Progress tracking that tracks itself

The best part? Her clients are happier because she's more present.

Your time is too valuable to spend on tasks that can run themselves 💪

What would change for you if admin just... happened? 🤔

#PersonalTrainer #TrainerSuccess #FitnessCoach #WorkLifeBalance #TrainerStory #RefiloeAI #FitnessBusiness #TrainerLife

Share your biggest admin challenge below 👇""",
        "post_type": "video",
        "video_duration": 45,
        "video_type": "success_story",
        "content_theme": "success_story",
        "hashtags": [
            "#PersonalTrainer",
            "#TrainerSuccess",
            "#FitnessCoach",
            "#WorkLifeBalance",
            "#TrainerStory",
            "#RefiloeAI",
            "#FitnessBusiness",
            "#TrainerLife"
        ],
        "call_to_action": "Share your biggest admin challenge below 👇",
        "avatar_env": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
        "scheduled_time": "08:00",
        "day_offset": 2
    },
    {
        # 13:00 SAST - Carousel about possibilities
        "title": "What If Your Admin Did Itself?",
        "content": """Imagine if your admin just... did itself 💭

Swipe through what's possible when tasks handle themselves.

This isn't science fiction. This is how trainers are working in 2025.

While you're training Client A at 6 AM:
→ Client B gets their automated check-in
→ Client C receives their payment reminder
→ Client D's schedule conflict resolves itself
→ Your content posts to social media

All without you touching your phone.

What would you do with 2 extra hours every day? 🎯

#PersonalTrainer #FitnessCoach #TrainerLife #FitnessTech #AdminAutomation #TrainerTools #RefiloeAI #FutureFitness

Tag a trainer who needs to see this vision! 👥""",
        "post_type": "carousel",
        "content_theme": "visionary",
        "hashtags": [
            "#PersonalTrainer",
            "#FitnessCoach",
            "#TrainerLife",
            "#FitnessTech",
            "#AdminAutomation",
            "#TrainerTools",
            "#RefiloeAI",
            "#FutureFitness"
        ],
        "call_to_action": "Tag a trainer who needs to see this vision! 👥",
        "avatar_env": None,  # Carousel doesn't need avatar
        "scheduled_time": "13:00",
        "day_offset": 2,
        "generation_prompt": """Create a 5-image carousel showing possibilities when admin automates:

Slide 1 (Cover): "WHAT IF YOUR ADMIN DID ITSELF?" - Trainer relaxing while phone shows automation working
Slide 2: "Your Mornings Start With Training" - Trainer with client, happy, energized, 6 AM on clock
Slide 3: "Your Evenings End With Life" - Trainer at home, dinner with family, phone face-down
Slide 4: "Your Weekends Are Yours Again" - Trainer hiking/relaxing, NOT checking messages
Slide 5: "Your Business Runs Smoothly" - Happy clients, organized schedule, automated systems
Slide 6 (CTA): "This Is How Trainers Work in 2025" - Modern, tech-enabled training life

Style: Aspirational but realistic, warm colors, diverse trainers, show the transformation from stressed to balanced"""
    },
    {
        # 18:00 SAST - Community question
        "title": "Trainers: What's Your Admin Reality?",
        "content": """Real talk, trainers 💬

I want to hear from YOU.

How many hours do you actually spend on admin each week?

A) 0-5 hours (living the dream)
B) 5-10 hours (manageable... barely)
C) 10-15 hours (it's taking over)
D) 15+ hours (I'm drowning)

And here's the follow-up:

What's the ONE admin task you'd eliminate if you could wave a magic wand? ✨

No judgment, just honest answers.

Your reality helps other trainers realize they're not alone.

Comment below with your letter + the task 👇

#TrainerLife #PersonalTrainer #FitnessCoach #TrainerCommunity #RealTalk #AdminReality #RefiloeAI #TrainerSupport

I'm reading every single comment 💚""",
        "post_type": "video",
        "video_duration": 30,
        "video_type": "question",
        "content_theme": "engagement",
        "hashtags": [
            "#TrainerLife",
            "#PersonalTrainer",
            "#FitnessCoach",
            "#TrainerCommunity",
            "#RealTalk",
            "#AdminReality",
            "#RefiloeAI",
            "#TrainerSupport"
        ],
        "call_to_action": "Comment below with your letter + the task 👇",
        "avatar_env": "HEYGEN_AVATAR_CASUAL_CLOSEUP",
        "scheduled_time": "18:00",
        "day_offset": 2
    }
]


# Combine all posts
ALL_LAUNCH_POSTS = DAY_1_POSTS + DAY_2_POSTS + DAY_3_POSTS


def get_avatar_id(avatar_env: str | None) -> str | None:
    """Get avatar ID from environment variable.

    Args:
        avatar_env: Environment variable name for the avatar

    Returns:
        Avatar ID or None if not available
    """
    if not avatar_env:
        return None

    avatar_id = os.getenv(avatar_env)
    if not avatar_id:
        log_warning(f"Avatar environment variable {avatar_env} not set")

    return avatar_id


def calculate_scheduled_time(base_date: datetime, time_str: str, day_offset: int) -> str:
    """Calculate the scheduled time for a post.

    Args:
        base_date: Base datetime to start from (should be in SAST)
        time_str: Time string in HH:MM format
        day_offset: Number of days to offset from base_date

    Returns:
        ISO format datetime string in SAST timezone
    """
    # Parse the time
    hour, minute = map(int, time_str.split(':'))

    # Create scheduled datetime
    scheduled = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    scheduled = scheduled + timedelta(days=day_offset)

    return scheduled.isoformat()


def seed_launch_content(start_date: datetime | None = None, dry_run: bool = False) -> Dict[str, any]:
    """Seed the database with initial launch content.

    Args:
        start_date: Optional start date for scheduling (defaults to today in SAST)
        dry_run: If True, don't actually save to database (for testing)

    Returns:
        Dict with results:
            - success: bool
            - posts_created: int
            - post_ids: List[str]
            - errors: List[str]
    """
    log_info("=" * 80)
    log_info("STARTING LAUNCH CONTENT SEEDING")
    log_info("=" * 80)

    # Initialize result tracking
    result = {
        'success': True,
        'posts_created': 0,
        'post_ids': [],
        'errors': []
    }

    # Set start date (default to today in SAST)
    if start_date is None:
        start_date = datetime.now(SAST)
    elif start_date.tzinfo is None:
        # If naive datetime provided, localize to SAST
        start_date = SAST.localize(start_date)
    else:
        # If timezone-aware, convert to SAST
        start_date = start_date.astimezone(SAST)

    log_info(f"Launch start date: {start_date.strftime('%Y-%m-%d %H:%M %Z')}")
    log_info(f"Total posts to create: {len(ALL_LAUNCH_POSTS)}")
    log_info(f"Dry run mode: {dry_run}")
    log_info("")

    if dry_run:
        log_info("DRY RUN MODE - No database operations will be performed")
        log_info("")

    # Initialize database connection if not dry run
    db = None
    if not dry_run:
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')

            if not supabase_url or not supabase_key:
                error_msg = "Missing SUPABASE_URL or SUPABASE_KEY environment variables"
                log_error(error_msg)
                result['success'] = False
                result['errors'].append(error_msg)
                return result

            supabase = create_client(supabase_url, supabase_key)
            db = SocialMediaDatabase(supabase)
            log_info("✓ Database connection established")
            log_info("")
        except Exception as e:
            error_msg = f"Failed to initialize database: {str(e)}"
            log_error(error_msg)
            result['success'] = False
            result['errors'].append(error_msg)
            return result

    # Process each post
    for idx, post_data in enumerate(ALL_LAUNCH_POSTS, 1):
        day = post_data['day_offset'] + 1
        log_info(f"Processing post {idx}/{len(ALL_LAUNCH_POSTS)} - Day {day} - {post_data['title']}")

        try:
            # Calculate scheduled time
            scheduled_time = calculate_scheduled_time(
                start_date,
                post_data['scheduled_time'],
                post_data['day_offset']
            )

            # Get avatar ID if applicable
            avatar_id = get_avatar_id(post_data.get('avatar_env'))

            # Prepare post for database
            db_post = {
                'title': post_data['title'],
                'content': post_data['content'],
                'post_type': post_data['post_type'],
                'platform': 'facebook',
                'content_theme': post_data['content_theme'],
                'scheduled_time': scheduled_time,
                'status': 'pending_approval',  # Requires approval before publishing
                'generation_prompt': post_data.get('generation_prompt'),
                'video_duration': post_data.get('video_duration', 0),
                'video_type': post_data.get('video_type'),
            }

            # Add avatar style for video posts
            if avatar_id and post_data['post_type'] == 'video':
                db_post['video_style'] = avatar_id

            log_info(f"  Type: {post_data['post_type']}")
            log_info(f"  Theme: {post_data['content_theme']}")
            log_info(f"  Scheduled: {scheduled_time}")
            if avatar_id:
                log_info(f"  Avatar: {post_data.get('avatar_env')} -> {avatar_id}")
            log_info(f"  Hashtags: {', '.join(post_data['hashtags'])}")
            log_info(f"  CTA: {post_data['call_to_action']}")

            # Save to database if not dry run
            if not dry_run:
                post_id = db.save_post(db_post)

                if post_id:
                    log_info(f"  ✓ Post saved with ID: {post_id}")
                    result['posts_created'] += 1
                    result['post_ids'].append(post_id)
                else:
                    error_msg = f"Failed to save post: {post_data['title']}"
                    log_error(f"  ✗ {error_msg}")
                    result['errors'].append(error_msg)
                    result['success'] = False
            else:
                log_info("  ✓ Post validated (dry run)")
                result['posts_created'] += 1

            log_info("")

        except Exception as e:
            error_msg = f"Error processing post '{post_data['title']}': {str(e)}"
            log_error(f"  ✗ {error_msg}")
            result['errors'].append(error_msg)
            result['success'] = False
            log_info("")
            continue

    # Summary
    log_info("=" * 80)
    log_info("LAUNCH CONTENT SEEDING COMPLETE")
    log_info("=" * 80)
    log_info(f"Status: {'SUCCESS' if result['success'] else 'FAILED'}")
    log_info(f"Posts created: {result['posts_created']}/{len(ALL_LAUNCH_POSTS)}")

    if result['errors']:
        log_info(f"Errors encountered: {len(result['errors'])}")
        for error in result['errors']:
            log_error(f"  - {error}")

    if not dry_run and result['post_ids']:
        log_info(f"\nPost IDs created:")
        for post_id in result['post_ids']:
            log_info(f"  - {post_id}")

    log_info("=" * 80)

    return result


def print_content_summary():
    """Print a summary of all launch content for review."""
    print("\n" + "=" * 80)
    print("REFILOE LAUNCH CONTENT SUMMARY")
    print("=" * 80)
    print(f"\nTotal posts: {len(ALL_LAUNCH_POSTS)}")
    print(f"Launch duration: 3 days")
    print(f"Posts per day: 3")
    print("\n")

    for day in range(3):
        day_posts = [p for p in ALL_LAUNCH_POSTS if p['day_offset'] == day]
        print(f"DAY {day + 1}:")
        print("-" * 80)

        for post in day_posts:
            print(f"\n{post['scheduled_time']} SAST - {post['title']}")
            print(f"Type: {post['post_type']}")
            if post.get('video_duration'):
                print(f"Duration: {post['video_duration']}s")
            print(f"Theme: {post['content_theme']}")
            print(f"Avatar: {post.get('avatar_env', 'N/A')}")
            print(f"\nContent preview:")
            print(post['content'][:200] + "..." if len(post['content']) > 200 else post['content'])
            print(f"\nHashtags ({len(post['hashtags'])}): {', '.join(post['hashtags'])}")
            print(f"CTA: {post['call_to_action']}")
            print()

        print()

    print("=" * 80)
    print()


if __name__ == "__main__":
    """Run content seeding when executed directly."""
    import sys

    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--summary':
            print_content_summary()
            sys.exit(0)
        elif sys.argv[1] == '--dry-run':
            print("\nRunning in DRY RUN mode - no database operations will be performed\n")
            result = seed_launch_content(dry_run=True)
            sys.exit(0 if result['success'] else 1)
        elif sys.argv[1] == '--help':
            print("\nRefiloe Launch Content Seeder")
            print("\nUsage:")
            print("  python social_media/launch_content.py              # Seed content to database")
            print("  python social_media/launch_content.py --summary    # Print content summary")
            print("  python social_media/launch_content.py --dry-run    # Test without saving")
            print("  python social_media/launch_content.py --help       # Show this help")
            print()
            sys.exit(0)

    # Default: Run the seeding
    print("\n🚀 Seeding Refiloe launch content to database...\n")
    result = seed_launch_content()

    if result['success']:
        print("\n✅ Launch content seeded successfully!")
        print(f"Created {result['posts_created']} posts ready for approval\n")
        sys.exit(0)
    else:
        print("\n❌ Launch content seeding failed")
        print(f"Created {result['posts_created']} posts before errors occurred")
        print(f"Errors: {len(result['errors'])}\n")
        sys.exit(1)
