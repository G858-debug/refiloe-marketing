"""Launch Content Generator for Refiloe's Facebook Campaign.

This module generates pre-defined launch content for the first 3 days of
Refiloe's Facebook marketing campaign with specific posts, themes, and schedules.

Author: Refiloe AI Assistant
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
    """Generates 9 pre-defined posts for the first 3 days of Facebook launch.

    This class creates a carefully orchestrated launch sequence with:
    - Day 1: Introduction posts
    - Day 2: Value proposition posts
    - Day 3: Engagement posts

    Each post is designed with specific timing, content, and CTAs.
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

        # DAY 1 - INTRODUCTION
        posts.append(self._create_day1_post1(start_date))
        posts.append(self._create_day1_post2(start_date))
        posts.append(self._create_day1_post3(start_date))

        # DAY 2 - VALUE
        posts.append(self._create_day2_post1(start_date))
        posts.append(self._create_day2_post2(start_date))
        posts.append(self._create_day2_post3(start_date))

        # DAY 3 - ENGAGEMENT
        posts.append(self._create_day3_post1(start_date))
        posts.append(self._create_day3_post2(start_date))
        posts.append(self._create_day3_post3(start_date))

        log_info(f"Generated {len(posts)} launch posts starting from {start_date.date()}")
        return posts

    # ========================================================================
    # DAY 1 - INTRODUCTION
    # ========================================================================

    def _create_day1_post1(self, start_date: datetime) -> Dict[str, Any]:
        """Day 1, Post 1 (08:00): Video 60s - 'Meet Refiloe'"""
        scheduled_time = start_date.replace(hour=8, minute=0)

        content_text = """What if you never had to chase clients for payments again? 🤔

Meet Refiloe - your AI assistant that handles all the boring admin work trainers hate.

While you're changing lives in the gym, Refiloe is:
✅ Managing your schedule
✅ Chasing payments
✅ Sending client reminders
✅ Handling bookings

Because you became a trainer to transform bodies, not to become an accountant.

Follow for more trainer life hacks! 💪

#PersonalTrainer #FitnessCoach #TrainerLife #RefiloeAI #AdminHacks #FitnessBusiness #TrainerTools"""

        video_script = """Hi, I'm Refiloe - and I'm here to ask you a question.

What if you never had to chase clients for payments again? What if you never had to stress about double bookings, or spend hours writing the same programs over and over?

I'm an AI assistant built specifically for personal trainers like you. I handle all the jobs trainers don't want to do.

While you're in the gym changing lives, I'm managing your schedule, chasing payments, sending client reminders, and handling all your bookings.

Because here's the truth - you became a trainer to transform bodies and change lives, not to become an accountant or an admin assistant.

So if you're tired of spending 15 hours a week on admin that doesn't make you money... follow me. I've got some life hacks that are going to change your business.

Let's do this together."""

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
            "avatar_id_env": "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#RefiloeAI", "#AdminHacks", "#FitnessBusiness", "#TrainerTools"],
            "call_to_action": "Follow for more trainer life hacks!",
            "status": "pending_approval"
        }

    def _create_day1_post2(self, start_date: datetime) -> Dict[str, Any]:
        """Day 1, Post 2 (13:00): Carousel 5 images - '5 Admin Tasks Killing Your Time'"""
        scheduled_time = start_date.replace(hour=13, minute=0)

        content_text = """5 admin tasks silently killing your training time ⏰

Swipe to see if you're guilty →

Every hour spent on admin is an hour you're NOT:
→ Training clients
→ Building relationships
→ Growing your income

Which one do you hate most? Drop a number in the comments! 👇

#PersonalTrainer #FitnessCoach #TrainerLife #AdminHacks #FitnessBusiness #TimeManagement #TrainerTips"""

        carousel_slides = [
            {
                "slide_number": 1,
                "title": "5 Admin Tasks Killing Your Time",
                "content": "Are you spending more time managing your business than actually training?",
                "design_notes": "Bold text, attention-grabbing colors"
            },
            {
                "slide_number": 2,
                "title": "1. Scheduling Chaos",
                "content": "Juggling WhatsApp messages, phone calls, and double bookings. 3 hours per week down the drain.",
                "design_notes": "Calendar icon, frustrated trainer imagery"
            },
            {
                "slide_number": 3,
                "title": "2. Payment Chasing",
                "content": "Awkward conversations, late payments, tracking who owes what. Another 2 hours gone.",
                "design_notes": "Money/invoice icon, uncomfortable vibe"
            },
            {
                "slide_number": 4,
                "title": "3. Program Writing",
                "content": "Typing the same exercises over and over. 4 hours of repetitive work every week.",
                "design_notes": "Clipboard/document icon, repetitive feel"
            },
            {
                "slide_number": 5,
                "title": "4. Client Reminders",
                "content": "Manual messages for sessions, payments, check-ins. 3 more hours wasted.",
                "design_notes": "Phone/notification icon, overwhelmed trainer"
            }
        ]

        return {
            "day": 1,
            "post_number": 2,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "carousel",
            "platform": "facebook",
            "content_theme": "admin_hacks",
            "content_text": content_text,
            "video_script": None,
            "video_duration": None,
            "avatar_id_env": None,
            "carousel_slides": carousel_slides,
            "image_prompt": "Modern, clean carousel design for fitness professionals showing admin pain points",
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#AdminHacks", "#FitnessBusiness", "#TimeManagement", "#TrainerTips"],
            "call_to_action": "Which one do you hate most? Comment below!",
            "status": "pending_approval"
        }

    def _create_day1_post3(self, start_date: datetime) -> Dict[str, Any]:
        """Day 1, Post 3 (18:00): Video 30s - Pain Point Meme"""
        scheduled_time = start_date.replace(hour=18, minute=0)

        content_text = """POV: Your 6am client cancels at 5:55am 😤

Tag a trainer who knows this pain TOO well 👇

But here's the thing... there's a better way.

Stay tuned 👀

#PersonalTrainer #TrainerLife #FitnessCoach #TrainerProblems #RefiloeAI #GymLife #FitnessBusiness"""

        video_script = """POV: It's 5:55 in the morning. You're already dressed, coffee in hand, mentally prepping for your 6am client.

Your phone buzzes.

"Hey sorry, can't make it today."

FIVE. MINUTES. BEFORE.

If you're a trainer, you know this pain. You've lived this pain.

The early wake-up. The lost income. The scramble to fill the slot.

But what if I told you... there's a better way?

What if your clients got automatic reminders 24 hours before? What if late cancellations triggered automatic fees? What if your entire schedule managed itself?

Stick around. You're going to want to see this."""

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
            "hashtags": ["#PersonalTrainer", "#TrainerLife", "#FitnessCoach", "#TrainerProblems", "#RefiloeAI", "#GymLife", "#FitnessBusiness"],
            "call_to_action": "Tag a trainer who needs to hear this!",
            "status": "pending_approval"
        }

    # ========================================================================
    # DAY 2 - VALUE
    # ========================================================================

    def _create_day2_post1(self, start_date: datetime) -> Dict[str, Any]:
        """Day 2, Post 1 (08:00): Video 60s - 'The Hidden 15 Hours'"""
        scheduled_time = (start_date + timedelta(days=1)).replace(hour=8, minute=0)

        content_text = """Trainers lose 15 hours EVERY WEEK to admin. Here's where it goes... ⏰

📅 Scheduling: 3 hours
💰 Chasing payments: 2 hours
📝 Program writing: 4 hours
💬 Client communications: 3 hours
📞 Managing bookings: 3 hours

That's 15 hours you could be:
→ Training MORE clients
→ Earning MORE money
→ Actually having a LIFE

Save this for later. You're going to need it. 🔖

#PersonalTrainer #FitnessCoach #TrainerLife #AdminHacks #FitnessBusiness #TimeManagement #ProductivityTips"""

        video_script = """Let me show you something that's going to blow your mind.

The average personal trainer loses 15 hours every single week to administrative tasks. FIFTEEN HOURS.

Let me break down where it's going:

3 hours on scheduling - back and forth messages, finding times, avoiding double bookings.

2 hours chasing payments - awkward conversations, tracking who paid, who didn't, who's late.

4 hours writing programs - typing the same exercises over and over for different clients.

3 hours on client communications - session reminders, check-ins, motivation messages.

And 3 hours managing bookings - cancellations, rescheduling, filling empty slots.

Now here's the crazy part. That's 15 hours you could be training MORE clients. Earning MORE money. Or actually having a life outside the gym.

15 hours. Every. Single. Week.

What would you do with that time back?

Drop a comment and let me know. Because I'm about to show you how to get it back."""

        return {
            "day": 2,
            "post_number": 4,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "admin_hacks",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 60,
            "avatar_id_env": "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#AdminHacks", "#FitnessBusiness", "#TimeManagement", "#ProductivityTips"],
            "call_to_action": "Save this for later",
            "status": "pending_approval"
        }

    def _create_day2_post2(self, start_date: datetime) -> Dict[str, Any]:
        """Day 2, Post 2 (13:00): Single Image - Motivational Quote"""
        scheduled_time = (start_date + timedelta(days=1)).replace(hour=13, minute=0)

        content_text = """"You became a trainer to change lives, not to become an accountant." 💯

Read that again.

Your gift is transforming bodies and minds. Not spreadsheets and invoices.

So why are you spending more time on admin than what you actually love?

Tag a trainer who needs this reminder 👇

#PersonalTrainer #FitnessCoach #TrainerLife #Motivation #FitnessBusiness #TrainerMotivation #FitnessMotivation"""

        image_prompt = "Motivational quote image with bold typography: 'You became a trainer to change lives, not to become an accountant.' Modern gradient background (orange to coral), clean sans-serif font, professional fitness aesthetic"

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
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#Motivation", "#FitnessBusiness", "#TrainerMotivation", "#FitnessMotivation"],
            "call_to_action": "Tag a trainer who needs to hear this",
            "status": "pending_approval"
        }

    def _create_day2_post3(self, start_date: datetime) -> Dict[str, Any]:
        """Day 2, Post 3 (18:00): Video 30s - Quick Tip"""
        scheduled_time = (start_date + timedelta(days=1)).replace(hour=18, minute=0)

        content_text = """Stop doing this with your clients... 🛑

Manual reminders are costing you time AND money.

Here's what smart trainers do instead 👇

Automate everything:
✅ Session reminders (24hrs before)
✅ Payment notifications
✅ Program delivery
✅ Check-in prompts

Your time = Your money. Protect both. 💰

#PersonalTrainer #FitnessCoach #ClientManagement #TrainerTips #FitnessBusiness #Automation #TrainerLife"""

        video_script = """Quick question - are you still sending manual reminders to your clients?

Stop. Just stop.

Every minute you spend typing "Hey, see you tomorrow at 6am!" is a minute you're not making money.

Here's what smart trainers do instead:

They automate their client reminders. 24 hours before every session - automatic message. No thinking required.

They automate payment notifications. Your client gets a reminder. You get paid on time. Nobody feels awkward.

They automate program delivery and check-in prompts.

Why? Because your time equals your money. And you need to protect both.

The trainers winning in 2024 aren't working harder. They're working smarter.

Which one are you going to be?"""

        return {
            "day": 2,
            "post_number": 6,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "client_management_tips",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 30,
            "avatar_id_env": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#ClientManagement", "#TrainerTips", "#FitnessBusiness", "#Automation", "#TrainerLife"],
            "call_to_action": "Follow for more trainer tips!",
            "status": "pending_approval"
        }

    # ========================================================================
    # DAY 3 - ENGAGEMENT
    # ========================================================================

    def _create_day3_post1(self, start_date: datetime) -> Dict[str, Any]:
        """Day 3, Post 1 (08:00): Video 45s - Transformation Teaser"""
        scheduled_time = (start_date + timedelta(days=2)).replace(hour=8, minute=0)

        content_text = """What would you do with 15 extra hours every week? ⏰

Imagine:
🎯 Taking on 5 more clients = R7,500+ extra/month
🌴 Actually taking a day off without stress
🎓 Learning new training techniques
💪 Training YOURSELF for once
👨‍👩‍👧 Spending time with family

That's what happens when your admin runs itself.

Drop a 🙋 if you want this life!

#PersonalTrainer #FitnessCoach #TrainerLife #WorkLifeBalance #FitnessBusiness #TrainerSuccess #RefiloeAI"""

        video_script = """Close your eyes for a second. Actually, don't - you need to watch this.

But imagine... what would you do with 15 extra hours every single week?

Maybe you'd take on 5 more clients. That's an extra R7,500 or more per month. Maybe you'd actually take a day off without stressing about your business falling apart.

Maybe you'd learn new training techniques. Invest in that certification you've been putting off.

Or here's a crazy idea - maybe you'd actually train YOURSELF for once. Or spend time with your family.

This isn't fantasy. This is what happens when your admin runs itself.

When scheduling is automatic. When payments chase themselves. When your programs write themselves. When client communication happens without you lifting a finger.

The trainers living this life right now? They're not superhuman. They just stopped doing everything manually.

So I'll ask again - what would YOU do with 15 extra hours every week?

Drop a 🙋 in the comments if you want this."""

        return {
            "day": 3,
            "post_number": 7,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "success_stories",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 45,
            "avatar_id_env": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#WorkLifeBalance", "#FitnessBusiness", "#TrainerSuccess", "#RefiloeAI"],
            "call_to_action": "Drop a 🙋 if you want this",
            "status": "pending_approval"
        }

    def _create_day3_post2(self, start_date: datetime) -> Dict[str, Any]:
        """Day 3, Post 2 (13:00): Carousel 4 images - 'What If Your Admin Did Itself?'"""
        scheduled_time = (start_date + timedelta(days=2)).replace(hour=13, minute=0)

        content_text = """What if your admin... just did itself? 🤯

Swipe to see what's possible →

The future of personal training isn't working harder.

It's working smarter.

Which feature would help you most? Drop 1, 2, 3, or 4 below! 👇

#PersonalTrainer #FitnessCoach #TrainerLife #FitnessBusiness #Automation #BusinessGrowth #TrainerTips"""

        carousel_slides = [
            {
                "slide_number": 1,
                "title": "What If Your Admin Did Itself?",
                "content": "The future of training is automated. Swipe to see what's possible.",
                "design_notes": "Futuristic, tech-forward design"
            },
            {
                "slide_number": 2,
                "title": "Automated Scheduling",
                "content": "Clients book themselves. Calendar syncs automatically. No more double bookings. Ever.",
                "design_notes": "Calendar interface, clean and organized"
            },
            {
                "slide_number": 3,
                "title": "Payment Reminders",
                "content": "Invoices send themselves. Reminders go out automatically. You get paid on time, every time.",
                "design_notes": "Payment/money graphics, professional"
            },
            {
                "slide_number": 4,
                "title": "More Time for Clients",
                "content": "15 hours back in your week. More training. More income. More life.",
                "design_notes": "Trainer with client, happy and engaged"
            }
        ]

        return {
            "day": 3,
            "post_number": 8,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "carousel",
            "platform": "facebook",
            "content_theme": "business_growth",
            "content_text": content_text,
            "video_script": None,
            "video_duration": None,
            "avatar_id_env": None,
            "carousel_slides": carousel_slides,
            "image_prompt": "Modern tech-forward carousel for fitness business automation",
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#FitnessBusiness", "#Automation", "#BusinessGrowth", "#TrainerTips"],
            "call_to_action": "Which feature would help you most?",
            "status": "pending_approval"
        }

    def _create_day3_post3(self, start_date: datetime) -> Dict[str, Any]:
        """Day 3, Post 3 (18:00): Video 30s - Community Question"""
        scheduled_time = (start_date + timedelta(days=2)).replace(hour=18, minute=0)

        content_text = """Be honest with me... 🤔

What's your BIGGEST admin struggle as a trainer?

Is it:
A) Scheduling chaos
B) Chasing payments
C) Writing programs
D) Client communication
E) Something else?

Drop your answer below - I'm reading every comment and creating content to help YOU specifically 👇

#PersonalTrainer #FitnessCoach #TrainerLife #TrainerCommunity #FitnessBusiness #TrainerProblems #Engagement"""

        video_script = """Alright, be honest with me.

What's your BIGGEST admin struggle as a personal trainer?

Is it scheduling? The constant back and forth, the double bookings, the cancellations?

Is it chasing payments? Those awkward conversations, the late payers, tracking who owes what?

Is it writing programs? Typing the same exercises over and over until your fingers hurt?

Is it client communication? The constant messages, the reminders, the check-ins?

Or is it something else entirely that I haven't even mentioned?

Here's why I'm asking: I'm here to help you. Really help you. And the only way I can do that is if you tell me what you're actually struggling with.

So drop your answer in the comments. A, B, C, D, or E for something else.

I'm reading every single comment, and I'm going to create content specifically to solve YOUR problems.

This is your community. Let's build it together."""

        return {
            "day": 3,
            "post_number": 9,
            "scheduled_time": scheduled_time.isoformat(),
            "post_type": "video",
            "platform": "facebook",
            "content_theme": "engagement_questions",
            "content_text": content_text,
            "video_script": video_script,
            "video_duration": 30,
            "avatar_id_env": "HEYGEN_AVATAR_CASUAL_CLOSEUP",
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#TrainerCommunity", "#FitnessBusiness", "#TrainerProblems", "#Engagement"],
            "call_to_action": "Comment your answer below!",
            "status": "pending_approval"
        }


def seed_launch_content(supabase_client, start_date: Optional[datetime] = None) -> List[str]:
    """Generate and save all 9 launch posts to the database.

    Args:
        supabase_client: Supabase client instance for database operations
        start_date: Starting date for the launch (defaults to tomorrow if None)

    Returns:
        List of created post IDs

    Raises:
        Exception: If database operations fail
    """
    from database import SocialMediaDatabase

    log_info("Starting launch content generation and seeding...")

    # Initialize generator
    generator = LaunchContentGenerator()

    # Generate all posts
    posts = generator.generate_all_posts(start_date)
    log_info(f"Generated {len(posts)} launch posts")

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
                "launch_content": True
            }

            post_data = {
                "post_type": post["post_type"],
                "platform": post["platform"],
                "content": post["content_text"],  # Maps to caption_text in DB
                "title": f"Day {post['day']} - Post {post['post_number']}",
                "content_theme": post["content_theme"],
                "scheduled_time": post["scheduled_time"],
                "status": post["status"],
                "video_duration": post.get("video_duration", 0) or 0,
                "generation_prompt": json.dumps(metadata)  # Store metadata as JSON
            }

            post_id = db.save_post(post_data)

            if post_id:
                created_ids.append(post_id)
                log_info(f"✓ Saved post {idx}/9: Day {post['day']}, Post {post['post_number']} (ID: {post_id})")
            else:
                log_error(f"✗ Failed to save post {idx}/9: Day {post['day']}, Post {post['post_number']}")

        except Exception as e:
            log_error(f"Error saving post {idx}/9: {str(e)}")
            continue

    log_info(f"Launch content seeding complete. Created {len(created_ids)}/{len(posts)} posts")
    return created_ids


def get_launch_content_preview() -> List[Dict[str, Any]]:
    """Get a preview of all 9 launch posts without saving to database.

    Returns:
        List of 9 post dictionaries with complete metadata
    """
    log_info("Generating launch content preview...")

    generator = LaunchContentGenerator()
    posts = generator.generate_all_posts()

    log_info(f"Preview generated: {len(posts)} posts")
    return posts


__all__ = ["LaunchContentGenerator", "seed_launch_content", "get_launch_content_preview"]
