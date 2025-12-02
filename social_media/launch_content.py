"""VALUE-FIRST Launch Content Generator for Refiloe's Facebook Campaign.

This module generates pure value content for the first 3 days of Refiloe's Facebook
marketing campaign. Refiloe is presented as a personality/influencer helping trainers,
NOT as a product or service.

CRITICAL RULES:
- NO product mentions, no "sign up", no "coming soon", no pricing hints
- Refiloe is "a friend who gets the trainer life and shares helpful tips"
- Pure value content that builds trust and following
- Focus on relatable struggles, actionable tips, and community building

Author: Refiloe Marketing Team
Created: 2024-12-01
"""

import json
import pytz
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from utils.logger import log_info, log_warning, log_error

# South African timezone
SA_TIMEZONE = pytz.timezone("Africa/Johannesburg")


class LaunchContentGenerator:
    """Generates 9 VALUE-FIRST posts for the first 3 days of Facebook launch.

    This class creates a carefully orchestrated launch sequence with:
    - Day 1: Meet Refiloe (The Personality)
    - Day 2: Pure Value (Actionable Tips)
    - Day 3: Engagement (Build Community)

    Each post focuses on building trust and providing value, with NO product mentions.
    """

    def __init__(self):
        """Initialize the launch content generator."""
        self.sa_tz = SA_TIMEZONE

    def generate_all_posts(self, start_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Generate all 9 launch posts with scheduled times.

        Args:
            start_date: Starting date for the launch (defaults to tomorrow if None)

        Returns:
            List of 9 post dictionaries with complete metadata
        """
        # Default to tomorrow if no start date provided
        if start_date is None:
            start_date = datetime.now(self.sa_tz) + timedelta(days=1)

        # Ensure start_date is timezone-aware
        if start_date.tzinfo is None:
            start_date = self.sa_tz.localize(start_date)
        else:
            start_date = start_date.astimezone(self.sa_tz)

        # Reset to start of day
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        posts = []

        # DAY 1 - MEET REFILOE (The Personality)
        posts.append(self._create_day1_post1(start_date))
        posts.append(self._create_day1_post2(start_date))
        posts.append(self._create_day1_post3(start_date))

        # DAY 2 - PURE VALUE (Actionable Tips)
        posts.append(self._create_day2_post1(start_date))
        posts.append(self._create_day2_post2(start_date))
        posts.append(self._create_day2_post3(start_date))

        # DAY 3 - ENGAGEMENT (Build Community)
        posts.append(self._create_day3_post1(start_date))
        posts.append(self._create_day3_post2(start_date))
        posts.append(self._create_day3_post3(start_date))

        log_info(f"Generated {len(posts)} VALUE-FIRST launch posts starting from {start_date.date()}")
        return posts

    # ========================================================================
    # DAY 1 - MEET REFILOE (The Personality)
    # ========================================================================

    def _create_day1_post1(self, start_date: datetime) -> Dict[str, Any]:
        """Day 1, Post 1 (08:00): Video 60s - 'Meet Refiloe'"""
        scheduled_time = start_date.replace(hour=8, minute=0)

        content_text = """If you're a personal trainer drowning in admin... this page is for you. 💪

Hey! I'm Refiloe.

I've spent years studying what makes trainers successful - and what holds them back.

Spoiler: It's rarely their training knowledge. It's usually the business side.

The scheduling nightmares. The payment chasing. The endless WhatsApp messages.

So I created this page to share everything I've learned about working smarter, not harder.

Every week I'll share:
→ Time-saving hacks that actually work
→ Real talk about the trainer struggle
→ Tips to grow your business without burning out

If that sounds useful, give me a follow.

Let's make the business side of training suck less. 💪

#PersonalTrainer #FitnessCoach #TrainerLife #PTLife #FitnessBusiness #TrainerTips"""

        video_script = """Hey! I'm Refiloe.

I've spent years studying what makes trainers successful - and what holds them back.

Spoiler: It's rarely their training knowledge. It's usually the business side.

The scheduling nightmares. The payment chasing. The endless WhatsApp messages.

So I created this page to share everything I've learned about working smarter, not harder.

Every week I'll share:
- Time-saving hacks that actually work
- Real talk about the trainer struggle
- Tips to grow your business without burning out

If that sounds useful, give me a follow.

Let's make the business side of training suck less. 💪"""

        return {
            "day": 1,
            "post_number": 1,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "introduction",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 60,
            "avatar_id_env": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#PTLife", "#FitnessBusiness", "#TrainerTips"],
            "call_to_action": "Follow for trainer tips that actually work",
            "engagement_type": "follow",
            "status": "pending_approval"
        }

    def _create_day1_post2(self, start_date: datetime) -> Dict[str, Any]:
        """Day 1, Post 2 (13:00): Carousel 5 images - '5 Time Thieves Every Trainer Knows'"""
        scheduled_time = start_date.replace(hour=13, minute=0)

        content_text = """5 Time Thieves Stealing Hours From Your Week ⏰

Swipe to see which one hits hardest →

Every trainer knows these struggles. The question is: which one steals the MOST of your time?

Is it the schedule shuffle? The payment chase? The message marathon?

Comment your number 👇 Let's see which one we all hate the most.

#PersonalTrainer #TrainerLife #FitnessCoach #TrainerProblems #FitnessBusiness #PTLife"""

        carousel_slides = [
            {
                "slide_number": 1,
                "text": "5 Time Thieves Stealing Hours From Your Week",
                "description": "Hook slide - bold, attention-grabbing design with clock/time imagery"
            },
            {
                "slide_number": 2,
                "text": "🕐 The Schedule Shuffle",
                "description": "Clients changing times last minute, you playing calendar Tetris for hours"
            },
            {
                "slide_number": 3,
                "text": "💸 The Payment Chase",
                "description": "Awkwardly reminding clients about unpaid sessions (again and again)"
            },
            {
                "slide_number": 4,
                "text": "📱 The Message Marathon",
                "description": "Replying to 50 WhatsApps before your first coffee"
            },
            {
                "slide_number": 5,
                "text": "📋 The Program Puzzle",
                "description": "Writing the same exercises differently for every single client"
            }
        ]

        return {
            "day": 1,
            "post_number": 2,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "carousel",
            "platform": "facebook",
            "content_theme": "relatable_trainer_life",
            "content_text": content_text,
            "video_script": None,
            "video_duration": None,
            "avatar_id_env": None,
            "carousel_slides": carousel_slides,
            "image_prompt": "Modern carousel design for personal trainers - vibrant colors (coral/purple), clean typography, relatable pain points, professional but approachable aesthetic",
            "hashtags": ["#PersonalTrainer", "#TrainerLife", "#FitnessCoach", "#TrainerProblems", "#FitnessBusiness", "#PTLife"],
            "call_to_action": "Comment 1-4 - which steals the most of YOUR time?",
            "engagement_type": "comment",
            "status": "pending_approval"
        }

    def _create_day1_post3(self, start_date: datetime) -> Dict[str, Any]:
        """Day 1, Post 3 (18:00): Video 30s - Relatable Moment"""
        scheduled_time = start_date.replace(hour=18, minute=0)

        content_text = """POV: Your 6am client at 5:55am... 😤

*Phone buzzes*

"Hey, so sorry, something came up, can we reschedule?"

You're already at the gym.
You've been up since 5.
You turned down a lie-in for this.

And now you've got a free hour you didn't plan for... and a gap in your income.

Sound familiar?

Drop a 😤 if you've lived this.

#PersonalTrainer #TrainerLife #FitnessCoach #TrainerProblems #GymLife #FitPro"""

        video_script = """*Phone buzzes*

'Hey, so sorry, something came up, can we reschedule?'

You're already at the gym.
You've been up since 5.
You turned down a lie-in for this.

And now you've got a free hour you didn't plan for... and a gap in your income.

Sound familiar?

Drop a 😤 if you've lived this."""

        return {
            "day": 1,
            "post_number": 3,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "relatable_trainer_life",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 30,
            "avatar_id_env": "HEYGEN_AVATAR_CASUAL_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#TrainerLife", "#FitnessCoach", "#TrainerProblems", "#GymLife", "#FitPro"],
            "call_to_action": "Drop a 😤 if this has happened to you",
            "engagement_type": "emoji_react",
            "status": "pending_approval"
        }

    # ========================================================================
    # DAY 2 - PURE VALUE (Actionable Tips)
    # ========================================================================

    def _create_day2_post1(self, start_date: datetime) -> Dict[str, Any]:
        """Day 2, Post 1 (08:00): Video 60s - 'The 15 Hour Problem'"""
        scheduled_time = (start_date + timedelta(days=1)).replace(hour=8, minute=0)

        content_text = """The average personal trainer loses 15 hours every single week. Here's where it goes. ⏰

I've talked to hundreds of trainers, and the pattern is always the same.

Here's where your 15 hours disappear:

📅 3 hours - Scheduling and rescheduling sessions
💰 2 hours - Chasing payments and sending reminders
📝 4 hours - Writing and adjusting training programs
💬 3 hours - Replying to client messages and questions
📊 3 hours - General admin, invoices, tracking

That's 15 hours. Every. Single. Week.

60 hours a month you could spend training clients.
Or with your family.
Or just... resting.

Over the next few weeks, I'm going to share specific tips for each of these.

But first - I'm curious. Which of these eats the most of YOUR time?

Comment below. I read every single one. 👇

#PersonalTrainer #FitnessCoach #TrainerLife #FitnessBusiness #TrainerTips #TimeManagement #PTLife"""

        video_script = """I've talked to hundreds of trainers, and the pattern is always the same.

Here's where your 15 hours disappear:

3 hours - Scheduling and rescheduling sessions
2 hours - Chasing payments and sending reminders
4 hours - Writing and adjusting training programs
3 hours - Replying to client messages and questions
3 hours - General admin, invoices, tracking

That's 15 hours. Every. Single. Week.

60 hours a month you could spend training clients.
Or with your family.
Or just... resting.

Over the next few weeks, I'm going to share specific tips for each of these.

But first - I'm curious. Which of these eats the most of YOUR time?

Comment below. I read every single one."""

        return {
            "day": 2,
            "post_number": 4,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "education",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 60,
            "avatar_id_env": "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#FitnessBusiness", "#TrainerTips", "#TimeManagement", "#PTLife"],
            "call_to_action": "Comment which one steals the most of your time",
            "engagement_type": "comment",
            "status": "pending_approval"
        }

    def _create_day2_post2(self, start_date: datetime) -> Dict[str, Any]:
        """Day 2, Post 2 (13:00): Single Image - Quote"""
        scheduled_time = (start_date + timedelta(days=1)).replace(hour=13, minute=0)

        content_text = """"You became a trainer to change lives. Not to become a part-time accountant." 💯

Read that again.

Your gift is transforming bodies and minds.
Not spreadsheets.
Not invoices.
Not chasing payments.

So why are you spending more time on admin than what you actually love?

Tag a trainer who needs to hear this 👇

#PersonalTrainer #FitnessCoach #TrainerLife #FitnessBusiness #TrainerCommunity #FitPro"""

        image_prompt = "Bold motivational quote image: 'You became a trainer to change lives. Not to become a part-time accountant.' White text on deep purple/dark gradient background, clean minimal design, modern sans-serif font, professional fitness aesthetic"

        return {
            "day": 2,
            "post_number": 5,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "image",
            "platform": "facebook",
            "content_theme": "motivation",
            "content_text": content_text,
            "video_script": None,
            "video_duration": None,
            "avatar_id_env": None,
            "carousel_slides": None,
            "image_prompt": image_prompt,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#FitnessBusiness", "#TrainerCommunity", "#FitPro"],
            "call_to_action": "Tag a trainer friend",
            "engagement_type": "tag",
            "status": "pending_approval"
        }

    def _create_day2_post3(self, start_date: datetime) -> Dict[str, Any]:
        """Day 2, Post 3 (18:00): Video 30s - Quick Tip #1"""
        scheduled_time = (start_date + timedelta(days=1)).replace(hour=18, minute=0)

        content_text = """Quick tip that'll save you 2 hours this week... ⚡

Here's something most trainers don't do:

Create a 'FAQ voice note library.'

Record yourself answering the 10 questions clients ask most:
→ What should I eat before training?
→ How sore is too sore?
→ Can I train if I'm sick?

Save them in a folder.

Next time someone asks?
Forward the voice note. 10 seconds instead of 10 minutes.

You're welcome. 😉

Save this for later 📌

#PersonalTrainer #FitnessCoach #TrainerTips #TrainerLife #FitnessBusiness #ProductivityTips"""

        video_script = """Here's something most trainers don't do:

Create a 'FAQ voice note library.'

Record yourself answering the 10 questions clients ask most:
- What should I eat before training?
- How sore is too sore?
- Can I train if I'm sick?

Save them in a folder.

Next time someone asks?
Forward the voice note. 10 seconds instead of 10 minutes.

You're welcome. 😉"""

        return {
            "day": 2,
            "post_number": 6,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "actionable_tip",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 30,
            "avatar_id_env": "HEYGEN_AVATAR_CASUAL_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerTips", "#TrainerLife", "#FitnessBusiness", "#ProductivityTips"],
            "call_to_action": "Save this for later 📌",
            "engagement_type": "save",
            "status": "pending_approval"
        }

    # ========================================================================
    # DAY 3 - ENGAGEMENT (Build Community)
    # ========================================================================

    def _create_day3_post1(self, start_date: datetime) -> Dict[str, Any]:
        """Day 3, Post 1 (08:00): Video 45s - The Dream"""
        scheduled_time = (start_date + timedelta(days=2)).replace(hour=8, minute=0)

        content_text = """Imagine this for a second... ✨

You wake up. No 5am alarm panic.

Your schedule for the day is already set. No back-and-forth messages.

Payments came in automatically. No awkward reminders sent.

Your clients got their programs. Without you copy-pasting anything.

You just... train people. The thing you actually love.

This isn't fantasy. There are trainers living this right now.

And over the coming weeks, I'm going to show you exactly how they do it.

If you want in, make sure you're following.

And drop a 🙋 if this sounds like the dream.

#PersonalTrainer #FitnessCoach #TrainerLife #FitnessBusiness #WorkLifeBalance #TrainerSuccess"""

        video_script = """Close your eyes. Imagine this:

You wake up. No 5am alarm panic.

Your schedule for the day is already set. No back-and-forth messages.

Payments came in automatically. No awkward reminders sent.

Your clients got their programs. Without you copy-pasting anything.

You just... train people. The thing you actually love.

This isn't fantasy. There are trainers living this right now.

And over the coming weeks, I'm going to show you exactly how they do it.

If you want in, make sure you're following.

And drop a 🙋 if this sounds like the dream."""

        return {
            "day": 3,
            "post_number": 7,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "inspiration",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 45,
            "avatar_id_env": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#FitnessBusiness", "#WorkLifeBalance", "#TrainerSuccess"],
            "call_to_action": "Drop a 🙋 if this is the dream",
            "engagement_type": "emoji_react",
            "status": "pending_approval"
        }

    def _create_day3_post2(self, start_date: datetime) -> Dict[str, Any]:
        """Day 3, Post 2 (13:00): Carousel 4 images - 'The 3 Types of Trainers'"""
        scheduled_time = (start_date + timedelta(days=2)).replace(hour=13, minute=0)

        content_text = """The 3 Types of Trainers (Which one are you?) 🤔

Swipe to find yourself →

No judgment here. We've all been at least 2 of these at some point.

But the question is: which one do you WANT to be?

Comment 🏃, 📊, or 🧠 - be honest!

(And if you're the Organizer drowning in spreadsheets... I see you 😅)

#PersonalTrainer #TrainerLife #FitnessCoach #TrainerCommunity #FitnessBusiness #PTLife"""

        carousel_slides = [
            {
                "slide_number": 1,
                "text": "The 3 Types of Trainers",
                "description": "Which one are you? (Hook slide with bold typography)"
            },
            {
                "slide_number": 2,
                "text": "THE HUSTLER 🏃",
                "description": "Works 6am-9pm, says yes to everything, burning out slowly but surely"
            },
            {
                "slide_number": 3,
                "text": "THE ORGANIZER 📊",
                "description": "Spreadsheets for everything, but still drowning in admin, just... neatly"
            },
            {
                "slide_number": 4,
                "text": "THE SMART ONE 🧠",
                "description": "Works less, earns more, has systems that run without them"
            }
        ]

        return {
            "day": 3,
            "post_number": 8,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "carousel",
            "platform": "facebook",
            "content_theme": "engagement",
            "content_text": content_text,
            "video_script": None,
            "video_duration": None,
            "avatar_id_env": None,
            "carousel_slides": carousel_slides,
            "image_prompt": "Fun, engaging carousel design showing 3 trainer personality types - vibrant colors, playful but professional, relatable illustrations or icons",
            "hashtags": ["#PersonalTrainer", "#TrainerLife", "#FitnessCoach", "#TrainerCommunity", "#FitnessBusiness", "#PTLife"],
            "call_to_action": "Comment 🏃, 📊, or 🧠 - be honest!",
            "engagement_type": "comment",
            "status": "pending_approval"
        }

    def _create_day3_post3(self, start_date: datetime) -> Dict[str, Any]:
        """Day 3, Post 3 (18:00): Video 30s - Community Question"""
        scheduled_time = (start_date + timedelta(days=2)).replace(hour=18, minute=0)

        content_text = """Be honest with me for a second... 💭

I want to make this page actually useful for you.

So tell me:

What's the ONE thing about running your training business that frustrates you most?

Is it the scheduling chaos?
The awkward money conversations?
Clients who ghost?
Something else?

Drop it in the comments.

I'll create content specifically to help with whatever you're struggling with most.

This page is for YOU. So tell me what you need. 👇

#PersonalTrainer #FitnessCoach #TrainerLife #TrainerCommunity #FitnessBusiness #FitPro"""

        video_script = """I want to make this page actually useful for you.

So tell me:

What's the ONE thing about running your training business that frustrates you most?

Is it the scheduling chaos?
The awkward money conversations?
Clients who ghost?
Something else?

Drop it in the comments.

I'll create content specifically to help with whatever you're struggling with most.

This page is for YOU. So tell me what you need."""

        return {
            "day": 3,
            "post_number": 9,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "engagement",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 30,
            "avatar_id_env": "HEYGEN_AVATAR_CASUAL_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#TrainerCommunity", "#FitnessBusiness", "#FitPro"],
            "call_to_action": "Comment your biggest frustration 👇",
            "engagement_type": "comment",
            "status": "pending_approval"
        }


def get_launch_content_preview() -> List[Dict[str, Any]]:
    """Get a preview of all 9 launch posts without saving to database.

    Returns:
        List of 9 post dictionaries with complete metadata
    """
    log_info("Generating VALUE-FIRST launch content preview...")

    generator = LaunchContentGenerator()
    posts = generator.generate_all_posts()

    log_info(f"Preview generated: {len(posts)} posts")
    return posts


def seed_launch_content(supabase_client, start_date: Optional[datetime] = None) -> List[str]:
    """Generate and save all 9 VALUE-FIRST launch posts to the database.

    Args:
        supabase_client: Supabase client instance for database operations
        start_date: Starting date for the launch (defaults to tomorrow if None)

    Returns:
        List of created post IDs

    Raises:
        Exception: If database operations fail
    """
    from database import SocialMediaDatabase

    log_info("Starting VALUE-FIRST launch content generation and seeding...")

    # Initialize generator
    generator = LaunchContentGenerator()

    # Generate all posts
    posts = generator.generate_all_posts(start_date)
    log_info(f"Generated {len(posts)} VALUE-FIRST launch posts")

    # Initialize database
    db = SocialMediaDatabase(supabase_client)

    # Save each post
    created_ids = []
    for idx, post in enumerate(posts, 1):
        try:
            # Prepare post data for database
            # Store extended metadata in generation_prompt as JSON
            metadata = {
                "day": post["day"],
                "post_number": post["post_number"],
                "video_script": post.get("video_script"),
                "avatar_id_env": post.get("avatar_id_env"),
                "carousel_slides": post.get("carousel_slides"),
                "image_prompt": post.get("image_prompt"),
                "hashtags": post.get("hashtags", []),
                "call_to_action": post.get("call_to_action"),
                "engagement_type": post.get("engagement_type"),
                "launch_content": True,
                "value_first": True  # Flag to identify VALUE-FIRST content
            }

            post_data = {
                "post_type": post["post_type"],
                "platform": post["platform"],
                "content": post["content_text"],  # Maps to caption_text in DB
                "title": f"Day {post['day']} - Post {post['post_number']} ({post['content_theme']})",
                "content_theme": post["content_theme"],
                "scheduled_time": post["scheduled_time"],
                "status": post["status"],
                "video_duration": post.get("video_duration", 0) or 0,
                "generation_prompt": json.dumps(metadata)  # Store metadata as JSON
            }

            post_id = db.save_post(post_data)

            if post_id:
                created_ids.append(post_id)
                log_info(f"✓ Saved post {idx}/9: Day {post['day']}, Post {post['post_number']} - {post['content_theme']} (ID: {post_id})")
            else:
                log_error(f"✗ Failed to save post {idx}/9: Day {post['day']}, Post {post['post_number']}")

        except Exception as e:
            log_error(f"Error saving post {idx}/9: {str(e)}")
            continue

    log_info(f"VALUE-FIRST launch content seeding complete. Created {len(created_ids)}/{len(posts)} posts")
    return created_ids


def clear_launch_content(supabase_client) -> int:
    """Delete any existing launch content (for regeneration).

    Args:
        supabase_client: Supabase client instance for database operations

    Returns:
        int: Count of posts deleted
    """
    try:
        log_info("Clearing existing launch content...")

        # Delete posts where generation_prompt contains "launch_content": true
        result = supabase_client.table('social_posts').delete().like('generation_prompt', '%"launch_content": true%').execute()

        deleted_count = len(result.data) if result.data else 0
        log_info(f"Deleted {deleted_count} launch content posts")

        return deleted_count

    except Exception as e:
        log_error(f"Error clearing launch content: {str(e)}")
        return 0


def clear_all_test_posts(supabase_client) -> int:
    """Delete all test posts and old content to start fresh."""

    try:
        # Delete posts with post_type='test'
        result1 = supabase_client.table('social_posts').delete().eq('post_type', 'test').execute()
        count1 = len(result1.data) if result1.data else 0

        # Delete any posts from before December 2025 (old test data)
        result2 = supabase_client.table('social_posts').delete().lt('created_at', '2025-12-01').execute()
        count2 = len(result2.data) if result2.data else 0

        total_deleted = count1 + count2
        log_info(f"Deleted {total_deleted} old/test posts")
        return total_deleted

    except Exception as e:
        log_error(f"Error clearing test posts: {e}")
        return 0


__all__ = [
    "LaunchContentGenerator",
    "get_launch_content_preview",
    "seed_launch_content",
    "clear_launch_content",
    "clear_all_test_posts"
]
