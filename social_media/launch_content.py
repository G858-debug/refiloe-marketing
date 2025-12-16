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
import os
import pytz
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from utils.logger import log_info, log_warning, log_error
from social_media.config.avatar_ids import DEFAULT_AVATAR_ID

try:  # Allow use both as package module and standalone
    from content_generator import ContentGenerator  # type: ignore
except ImportError:  # pragma: no cover - fallback when imported from package wrapper
    from ..content_generator import ContentGenerator  # type: ignore

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

    def __init__(self, supabase_client=None, config_path: str = None):
        """Initialize the launch content generator.

        Args:
            supabase_client: Supabase client instance for ContentGenerator
            config_path: Path to config.yaml file (defaults to ../config.yaml)
        """
        self.sa_tz = SA_TIMEZONE

        # Initialize ContentGenerator if supabase_client provided
        if supabase_client:
            if config_path is None:
                # Default to config.yaml in parent directory
                current_dir = os.path.dirname(os.path.abspath(__file__))
                config_path = os.path.join(os.path.dirname(current_dir), 'config.yaml')

            self.content_generator = ContentGenerator(config_path, supabase_client)
            log_info("LaunchContentGenerator initialized with ContentGenerator")
        else:
            self.content_generator = None
            log_info("LaunchContentGenerator initialized without ContentGenerator (will use hardcoded templates)")

    def _generate_video_content(self, theme: str, duration: int, style: str, hook_type: str = 'personal_story') -> Dict[str, Any]:
        """Generate video content using ContentGenerator with proper fallback.

        Args:
            theme: Content theme for the video
            duration: Video duration in seconds
            style: Video style (introduction, relatable, educational, etc.)
            hook_type: Type of hook to use

        Returns:
            Dict with 'video_script', 'content_text' (caption), and 'hashtags'
        """
        result = {'video_script': '', 'content_text': '', 'hashtags': []}

        if not self.content_generator:
            return result

        try:
            # First, try to generate video script
            log_info(f"Generating video content - theme: {theme}, duration: {duration}s, style: {style}")
            script_data = self.content_generator.create_video_script(
                theme=theme,
                duration=duration,
                style=style
            )

            # Extract video script from generated data
            if script_data and 'script' in script_data and script_data['script']:
                video_script = "\n\n".join([
                    segment.get('text', '')
                    for segment in script_data['script']
                    if segment.get('text', '').strip()
                ])
                if video_script.strip():
                    result['video_script'] = video_script
                    result['hashtags'] = script_data.get('hashtags', [])
                    log_info(f"Successfully generated video script ({len(video_script)} chars)")

            # If no video script, try generate_single_post for video format
            if not result['video_script']:
                log_info("Video script generation failed, trying generate_single_post...")
                post_data = self.content_generator.generate_single_post(
                    theme=theme,
                    format_type='video_with_caption',
                    hook_type=hook_type
                )

                if post_data and post_data.get('content', '').strip():
                    # Use the generated content as video script
                    result['video_script'] = post_data.get('content', '')
                    result['hashtags'] = post_data.get('hashtags', [])
                    log_info(f"Generated video script via single_post ({len(result['video_script'])} chars)")

            # Generate separate caption/content_text if needed
            # The caption is different from the video script (what appears on social media)
            if result['video_script'] and not result['content_text']:
                # Caption is auto-generated by _create_social_caption later
                pass

        except Exception as e:
            log_error(f"Error generating video content: {str(e)}")
            import traceback
            log_error(f"Traceback: {traceback.format_exc()}")

        return result

    def _generate_carousel_content(self, theme: str, topic_hint: str, num_slides: int = 5, hook_type: str = 'pain_point') -> Dict[str, Any]:
        """Generate carousel content using ContentGenerator with proper fallback.

        Args:
            theme: Content theme for the carousel
            topic_hint: Hint about the specific topic for the carousel
            num_slides: Number of slides to generate
            hook_type: Type of hook to use

        Returns:
            Dict with 'content_text' (caption), 'carousel_slides', and 'hashtags'
        """
        result = {'content_text': '', 'carousel_slides': [], 'hashtags': []}

        if not self.content_generator:
            return result

        try:
            log_info(f"Generating carousel content - theme: {theme}, slides: {num_slides}")

            # Generate carousel caption/content using ContentGenerator
            post_data = self.content_generator.generate_single_post(
                theme=theme,
                format_type='carousel_style',
                hook_type=hook_type
            )

            if post_data:
                # Extract caption (content_text)
                content = post_data.get('content', '')
                if content and content.strip():
                    result['content_text'] = content
                    log_info(f"Generated carousel caption ({len(content)} chars)")

                # Extract hashtags
                result['hashtags'] = post_data.get('hashtags', [])

                # Extract carousel_slides if generated
                if post_data.get('carousel_slides'):
                    result['carousel_slides'] = post_data.get('carousel_slides')
                    log_info(f"Generated {len(result['carousel_slides'])} carousel slides")

        except Exception as e:
            log_error(f"Error generating carousel content: {str(e)}")
            import traceback
            log_error(f"Traceback: {traceback.format_exc()}")

        return result

    def _generate_image_content(self, theme: str, hook_type: str = 'inspiring_quote') -> Dict[str, Any]:
        """Generate image post content using ContentGenerator with proper fallback.

        Args:
            theme: Content theme for the image post
            hook_type: Type of hook to use

        Returns:
            Dict with 'content_text' (caption) and 'hashtags'
        """
        result = {'content_text': '', 'hashtags': []}

        if not self.content_generator:
            return result

        try:
            log_info(f"Generating image content - theme: {theme}, hook: {hook_type}")

            # Generate image caption using ContentGenerator
            post_data = self.content_generator.generate_single_post(
                theme=theme,
                format_type='single_image_with_caption',
                hook_type=hook_type
            )

            if post_data:
                # Extract caption (content_text)
                content = post_data.get('content', '')
                if content and content.strip():
                    result['content_text'] = content
                    log_info(f"Generated image caption ({len(content)} chars)")

                # Extract hashtags
                result['hashtags'] = post_data.get('hashtags', [])

        except Exception as e:
            log_error(f"Error generating image content: {str(e)}")
            import traceback
            log_error(f"Traceback: {traceback.format_exc()}")

        return result

    def _create_social_caption(self, video_script: str, hashtags: list, cta: str) -> str:
        """Create a social media caption that's different from the video script.

        Adds hook, context, and formatting that works well for static posts.
        """
        # Extract first compelling line from script as hook
        lines = [line.strip() for line in video_script.split('\n') if line.strip()]
        hook = lines[0] if lines else video_script[:100]

        # Create engaging caption with structure
        caption_parts = []

        # Add hook with emoji
        if not any(emoji in hook for emoji in ['💪', '✨', '⏰', '🤔', '💭', '😤']):
            hook = hook + " 💡"
        caption_parts.append(hook)
        caption_parts.append("")  # Blank line

        # Add preview of what's in the video
        caption_parts.append("In this video, I break down:")

        # Extract key points from script (look for bullet points or numbered items)
        key_points = []
        for line in lines[1:]:
            if line.startswith(('→', '-', '•', '✓')) or any(char.isdigit() and '. ' in line for char in line[:3]):
                key_points.append(line)

        if key_points:
            caption_parts.extend(key_points[:3])  # Max 3 points
        else:
            # Generate summary points from script
            caption_parts.append("→ The real challenge trainers face")
            caption_parts.append("→ Why this matters for your business")
            caption_parts.append("→ What you can do about it")

        caption_parts.append("")  # Blank line
        caption_parts.append(cta)
        caption_parts.append("")  # Blank line

        # Add hashtags
        caption_parts.append(" ".join(hashtags))

        return "\n".join(caption_parts)

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

        # Default hashtags and CTA
        default_hashtags = ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#PTLife", "#FitnessBusiness", "#TrainerTips"]
        call_to_action = "Follow for trainer tips that actually work"

        # Hardcoded template fallback
        fallback_video_script = """You know that moment—5:47 AM, gym bag packed, coffee in hand—when you realise you're not just tired. You're drowning.

Not in clients. In everything around the clients.

The scheduling chaos. The payment awkwardness. The endless WhatsApp pings before your eyes are even open.

I've spent years studying what separates trainers who burn out from those who build something sustainable. And here's the uncomfortable truth: it's rarely about training knowledge. It's about the business side—the part nobody taught us.

That's why this page exists. Not for motivation porn. For real talk about the trainer struggle. Time-saving hacks that actually work. Ways to grow without sacrificing your sanity.

Because you didn't become a trainer to drown in admin.

You became a trainer to change lives.

If that resonates, stick around. This is just the beginning. 💪"""

        # Try to generate content using ContentGenerator
        generated = self._generate_video_content(
            theme='introduction',
            duration=60,
            style='introduction',
            hook_type='personal_story'
        )

        # Use generated content if available and non-empty, otherwise use fallback
        video_script = generated.get('video_script', '').strip()
        if not video_script:
            log_info("Using fallback video script for Day 1 Post 1")
            video_script = fallback_video_script

        hashtags = generated.get('hashtags', [])
        if not hashtags:
            hashtags = default_hashtags

        content_text = self._create_social_caption(
            video_script=video_script,
            hashtags=hashtags,
            cta=call_to_action
        )

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
            "avatar_id_env": DEFAULT_AVATAR_ID,
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": hashtags,
            "call_to_action": call_to_action,
            "engagement_type": "follow",
            "status": "pending_approval"
        }

    def _create_day1_post2(self, start_date: datetime) -> Dict[str, Any]:
        """Day 1, Post 2 (13:00): Carousel 5 images - '5 Time Thieves Every Trainer Knows'"""
        scheduled_time = start_date.replace(hour=13, minute=0)

        # Default hashtags and CTA
        default_hashtags = ["#PersonalTrainer", "#TrainerLife", "#FitnessCoach", "#TrainerProblems", "#FitnessBusiness", "#PTLife"]
        call_to_action = "Comment 1-5 - which steals the most of YOUR time?"

        # Hardcoded template fallback
        fallback_content_text = """It was 9 PM on a Sunday. I was "just finishing up" some admin—for the third hour straight.

That's when it hit me. The clients weren't draining me. The invisible work around the clients was.

5 Time Thieves Stealing Hours From Your Week ⏰

Swipe to see which one hits hardest →

Every trainer carries these struggles. The schedule shuffle. The payment chase. The message marathon. The question isn't whether you know them—it's which one gnaws at you most.

Here's the uncomfortable truth: we train others to be efficient with their time. But who's training us?

Comment your number 👇 Let's see which one we all wrestle with the most.

#PersonalTrainer #TrainerLife #FitnessCoach #TrainerProblems #FitnessBusiness #PTLife"""

        fallback_carousel_slides = [
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

        # Try to generate content using ContentGenerator
        generated = self._generate_carousel_content(
            theme='relatable_trainer_life',
            topic_hint='time thieves stealing trainer time',
            num_slides=5,
            hook_type='pain_point'
        )

        # Use generated content if available and non-empty, otherwise use fallback
        content_text = generated.get('content_text', '').strip()
        if not content_text:
            log_info("Using fallback content for Day 1 Post 2 (carousel)")
            content_text = fallback_content_text

        carousel_slides = generated.get('carousel_slides', [])
        if not carousel_slides:
            carousel_slides = fallback_carousel_slides

        hashtags = generated.get('hashtags', [])
        if not hashtags:
            hashtags = default_hashtags

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
            "hashtags": hashtags,
            "call_to_action": call_to_action,
            "engagement_type": "comment",
            "status": "pending_approval"
        }

    def _create_day1_post3(self, start_date: datetime) -> Dict[str, Any]:
        """Day 1, Post 3 (18:00): Video 30s - Relatable Moment"""
        scheduled_time = start_date.replace(hour=18, minute=0)

        # Default hashtags and CTA
        default_hashtags = ["#PersonalTrainer", "#TrainerLife", "#FitnessCoach", "#TrainerProblems", "#GymLife", "#FitPro"]
        call_to_action = "Drop a 😤 if this has happened to you"

        # Hardcoded template fallback
        fallback_video_script = """The message landed at 6:47 AM.

"Hey, so sorry, something came up, can we reschedule?"

You're already at the gym. Coffee half-finished. Warm-up complete. Mind already locked in for the session.

And now? An empty hour you didn't plan for. A gap in your income nobody warned you about.

The worst part isn't the lost time—it's that sinking feeling of "not again."

You built this career to help people transform. Not to become an expert in last-minute cancellations.

Sound familiar?

Drop a 😤 if you've lived this moment."""

        # Try to generate content using ContentGenerator
        generated = self._generate_video_content(
            theme='relatable_trainer_life',
            duration=30,
            style='relatable',
            hook_type='pain_point'
        )

        # Use generated content if available and non-empty, otherwise use fallback
        video_script = generated.get('video_script', '').strip()
        if not video_script:
            log_info("Using fallback video script for Day 1 Post 3")
            video_script = fallback_video_script

        hashtags = generated.get('hashtags', [])
        if not hashtags:
            hashtags = default_hashtags

        content_text = self._create_social_caption(
            video_script=video_script,
            hashtags=hashtags,
            cta=call_to_action
        )

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
            "avatar_id_env": DEFAULT_AVATAR_ID,
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": hashtags,
            "call_to_action": call_to_action,
            "engagement_type": "emoji_react",
            "status": "pending_approval"
        }

    # ========================================================================
    # DAY 2 - PURE VALUE (Actionable Tips)
    # ========================================================================

    def _create_day2_post1(self, start_date: datetime) -> Dict[str, Any]:
        """Day 2, Post 1 (08:00): Video 60s - 'The 15 Hour Problem'"""
        scheduled_time = (start_date + timedelta(days=1)).replace(hour=8, minute=0)

        # Default hashtags and CTA
        default_hashtags = ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#FitnessBusiness", "#TrainerTips", "#TimeManagement", "#PTLife"]
        call_to_action = "Comment which one steals the most of your time"

        # Hardcoded template fallback
        fallback_video_script = """I've talked to hundreds of trainers over the years. And the pattern haunts me.

Here's where your 15 hours disappear every week:

3 hours - Scheduling and rescheduling sessions
2 hours - Chasing payments and sending awkward reminders
4 hours - Writing and adjusting training programs
3 hours - Replying to client messages and questions
3 hours - General admin, invoices, tracking

That's 15 hours. Every. Single. Week.

60 hours a month you could spend training clients. Or with your family. Or just... resting. Remember resting?

Here's what nobody tells you: the solution isn't working harder. It's building systems that work while you sleep.

Over the coming weeks, I'm going to share specific strategies for each of these time thieves.

But first—I'm curious. Which of these gnaws at you the most?

Comment below. I read every single one. And your answer will shape what I share next."""

        # Try to generate content using ContentGenerator
        generated = self._generate_video_content(
            theme='admin_hacks',
            duration=60,
            style='educational',
            hook_type='statistic'
        )

        # Use generated content if available and non-empty, otherwise use fallback
        video_script = generated.get('video_script', '').strip()
        if not video_script:
            log_info("Using fallback video script for Day 2 Post 1")
            video_script = fallback_video_script

        hashtags = generated.get('hashtags', [])
        if not hashtags:
            hashtags = default_hashtags

        content_text = self._create_social_caption(
            video_script=video_script,
            hashtags=hashtags,
            cta=call_to_action
        )

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
            "avatar_id_env": DEFAULT_AVATAR_ID,
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": hashtags,
            "call_to_action": call_to_action,
            "engagement_type": "comment",
            "status": "pending_approval"
        }

    def _create_day2_post2(self, start_date: datetime) -> Dict[str, Any]:
        """Day 2, Post 2 (13:00): Single Image - Quote"""
        scheduled_time = (start_date + timedelta(days=1)).replace(hour=13, minute=0)

        # Default hashtags and CTA
        default_hashtags = ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#FitnessBusiness", "#TrainerCommunity", "#FitPro"]
        call_to_action = "Tag a trainer who needs to hear this 👇"

        # Hardcoded template fallback
        fallback_content_text = """It was 11 PM. I was reconciling invoices—again—when the words hit me like a deadlift PR.

"You became a trainer to change lives. Not to become a part-time accountant."

Read that again. Let it sink in.

Your gift is transforming bodies and minds. Watching someone discover strength they didn't know they had. Seeing the moment belief clicks in their eyes.

Not spreadsheets. Not invoices. Not chasing payments at midnight.

So why are we spending more time on admin than on what we actually love?

That's the thing about passion—it can carry us so far that we forget why we started. The business side creeps in. And before we know it, we're drowning in the details instead of swimming in the work that lights us up.

Tag a trainer who needs this reminder 👇

#PersonalTrainer #FitnessCoach #TrainerLife #FitnessBusiness #TrainerCommunity #FitPro"""

        # Try to generate content using ContentGenerator
        generated = self._generate_image_content(
            theme='growth_mindset',
            hook_type='inspiring_quote'
        )

        # Use generated content if available and non-empty, otherwise use fallback
        content_text = generated.get('content_text', '').strip()
        if not content_text:
            log_info("Using fallback content for Day 2 Post 2 (image)")
            content_text = fallback_content_text

        hashtags = generated.get('hashtags', [])
        if not hashtags:
            hashtags = default_hashtags

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
            "hashtags": hashtags,
            "call_to_action": call_to_action,
            "engagement_type": "tag",
            "status": "pending_approval"
        }

    def _create_day2_post3(self, start_date: datetime) -> Dict[str, Any]:
        """Day 2, Post 3 (18:00): Video 30s - Quick Tip #1"""
        scheduled_time = (start_date + timedelta(days=1)).replace(hour=18, minute=0)

        # Default hashtags and CTA
        default_hashtags = ["#PersonalTrainer", "#FitnessCoach", "#TrainerTips", "#TrainerLife", "#FitnessBusiness", "#ProductivityTips"]
        call_to_action = "Save this for later 📌"

        # Hardcoded template fallback
        fallback_video_script = """It was 9 PM. I was typing the same answer I'd typed a hundred times before.

"What should I eat before training?"

That's when it hit me—I'm spending hours repeating myself. So here's what I did.

I created a 'FAQ voice note library.'

Recorded myself answering the 10 questions clients ask most:
- What should I eat before training?
- How sore is too sore?
- Can I train if I'm sick?

Saved them in a folder on my phone.

Now when someone asks? I forward the voice note. 10 seconds instead of 10 minutes. And here's the beautiful part—it feels more personal than typing.

One system. Hours saved every week.

You're welcome. 😉"""

        # Try to generate content using ContentGenerator
        generated = self._generate_video_content(
            theme='admin_hacks',
            duration=30,
            style='tip',
            hook_type='quick_win'
        )

        # Use generated content if available and non-empty, otherwise use fallback
        video_script = generated.get('video_script', '').strip()
        if not video_script:
            log_info("Using fallback video script for Day 2 Post 3")
            video_script = fallback_video_script

        hashtags = generated.get('hashtags', [])
        if not hashtags:
            hashtags = default_hashtags

        content_text = self._create_social_caption(
            video_script=video_script,
            hashtags=hashtags,
            cta=call_to_action
        )

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
            "avatar_id_env": DEFAULT_AVATAR_ID,
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": hashtags,
            "call_to_action": call_to_action,
            "engagement_type": "save",
            "status": "pending_approval"
        }

    # ========================================================================
    # DAY 3 - ENGAGEMENT (Build Community)
    # ========================================================================

    def _create_day3_post1(self, start_date: datetime) -> Dict[str, Any]:
        """Day 3, Post 1 (08:00): Video 45s - The Dream"""
        scheduled_time = (start_date + timedelta(days=2)).replace(hour=8, minute=0)

        # Default hashtags and CTA
        default_hashtags = ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#FitnessBusiness", "#WorkLifeBalance", "#TrainerSuccess"]
        call_to_action = "Drop a 🙋 if this is the dream"

        # Hardcoded template fallback
        fallback_video_script = """Close your eyes for a moment. Picture this:

You wake up. Not to a 5am alarm panic, but naturally. Rested.

Your schedule for the day? Already set. No back-and-forth messages. No calendar Tetris.

Payments came in overnight—automatically. No awkward "just following up" texts sent.

Your clients received their programs. Customized. Delivered. Without you copy-pasting a single thing.

You just... train people. The thing you actually love. The reason you started this journey.

Here's what I've learned: this isn't fantasy. There are trainers living this reality right now.

The difference between drowning in admin and flowing through your days? Systems. Smart ones. Built for how trainers actually work.

Over the coming weeks, I'm going to share exactly how they do it.

If you want in on that journey, make sure you're following.

And drop a 🙋 if this sounds like the dream you're chasing."""

        # Try to generate content using ContentGenerator
        generated = self._generate_video_content(
            theme='growth_mindset',
            duration=45,
            style='inspirational',
            hook_type='story'
        )

        # Use generated content if available and non-empty, otherwise use fallback
        video_script = generated.get('video_script', '').strip()
        if not video_script:
            log_info("Using fallback video script for Day 3 Post 1")
            video_script = fallback_video_script

        hashtags = generated.get('hashtags', [])
        if not hashtags:
            hashtags = default_hashtags

        content_text = self._create_social_caption(
            video_script=video_script,
            hashtags=hashtags,
            cta=call_to_action
        )

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
            "avatar_id_env": DEFAULT_AVATAR_ID,
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": hashtags,
            "call_to_action": call_to_action,
            "engagement_type": "emoji_react",
            "status": "pending_approval"
        }

    def _create_day3_post2(self, start_date: datetime) -> Dict[str, Any]:
        """Day 3, Post 2 (13:00): Carousel 4 images - 'The 3 Types of Trainers'"""
        scheduled_time = (start_date + timedelta(days=2)).replace(hour=13, minute=0)

        # Default hashtags and CTA
        default_hashtags = ["#PersonalTrainer", "#TrainerLife", "#FitnessCoach", "#TrainerCommunity", "#FitnessBusiness", "#PTLife"]
        call_to_action = "Comment 🏃, 📊, or 🧠 - be honest!"

        # Hardcoded template fallback
        fallback_content_text = """It was during a coffee break between clients when I had the realisation.

Looking around the gym, I could spot them instantly—the three types of trainers.

The 3 Types of Trainers (Which one are you?) 🤔

Swipe to find yourself →

No judgment here. I've been at least two of these at different points in my journey. Maybe all three.

The Hustler who never says no. The Organizer with colour-coded chaos. The Smart One who figured out the secret.

But here's the thing about types—they're not prisons. They're starting points. Every Hustler can become Smart. Every Organizer can find flow.

The question isn't where you are. It's where you're headed.

Comment 🏃, 📊, or 🧠 - be honest about where you are right now.

(And if you're the Organizer drowning in spreadsheets... I see you. I was you. 😅)

#PersonalTrainer #TrainerLife #FitnessCoach #TrainerCommunity #FitnessBusiness #PTLife"""

        fallback_carousel_slides = [
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

        # Try to generate content using ContentGenerator
        generated = self._generate_carousel_content(
            theme='engagement_questions',
            topic_hint='trainer personality types',
            num_slides=4,
            hook_type='community_question'
        )

        # Use generated content if available and non-empty, otherwise use fallback
        content_text = generated.get('content_text', '').strip()
        if not content_text:
            log_info("Using fallback content for Day 3 Post 2 (carousel)")
            content_text = fallback_content_text

        carousel_slides = generated.get('carousel_slides', [])
        if not carousel_slides:
            carousel_slides = fallback_carousel_slides

        hashtags = generated.get('hashtags', [])
        if not hashtags:
            hashtags = default_hashtags

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
            "hashtags": hashtags,
            "call_to_action": call_to_action,
            "engagement_type": "comment",
            "status": "pending_approval"
        }

    def _create_day3_post3(self, start_date: datetime) -> Dict[str, Any]:
        """Day 3, Post 3 (18:00): Video 30s - Community Question"""
        scheduled_time = (start_date + timedelta(days=2)).replace(hour=18, minute=0)

        # Default hashtags and CTA
        default_hashtags = ["#PersonalTrainer", "#FitnessCoach", "#TrainerLife", "#TrainerCommunity", "#FitnessBusiness", "#FitPro"]
        call_to_action = "Comment your biggest frustration 👇"

        # Hardcoded template fallback
        fallback_video_script = """I want to ask you something real.

I'm not here to broadcast at you. I'm here to build something useful. For you. With you.

So tell me:

What's the ONE thing about running your training business that haunts you most?

Is it the scheduling chaos that never ends?
The awkward money conversations you dread?
Clients who ghost after promising they're "committed this time"?
Something else that gnaws at you in quiet moments?

Drop it in the comments. Be specific. Be honest.

Here's my promise: I'll create content specifically to help with whatever you're struggling with most.

This page isn't about me. It's about us—the community of trainers trying to build something meaningful without losing ourselves in the process.

So tell me what you need. I'm listening."""

        # Try to generate content using ContentGenerator
        generated = self._generate_video_content(
            theme='engagement_questions',
            duration=30,
            style='conversational',
            hook_type='community_question'
        )

        # Use generated content if available and non-empty, otherwise use fallback
        video_script = generated.get('video_script', '').strip()
        if not video_script:
            log_info("Using fallback video script for Day 3 Post 3")
            video_script = fallback_video_script

        hashtags = generated.get('hashtags', [])
        if not hashtags:
            hashtags = default_hashtags

        content_text = self._create_social_caption(
            video_script=video_script,
            hashtags=hashtags,
            cta=call_to_action
        )

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
            "avatar_id_env": DEFAULT_AVATAR_ID,
            "carousel_slides": None,
            "image_prompt": None,
            "hashtags": hashtags,
            "call_to_action": call_to_action,
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


def seed_launch_content(supabase_client, start_date: Optional[datetime] = None, config_path: str = None) -> List[str]:
    """Generate and save all 9 VALUE-FIRST launch posts to the database.

    Args:
        supabase_client: Supabase client instance for database operations
        start_date: Starting date for the launch (defaults to tomorrow if None)
        config_path: Path to config.yaml file (defaults to ../config.yaml)

    Returns:
        List of created post IDs

    Raises:
        Exception: If database operations fail
    """
    from database import SocialMediaDatabase

    log_info("Starting VALUE-FIRST launch content generation and seeding...")

    # Initialize generator with ContentGenerator support
    generator = LaunchContentGenerator(supabase_client=supabase_client, config_path=config_path)

    # Generate all posts
    posts = generator.generate_all_posts(start_date)
    log_info(f"Generated {len(posts)} VALUE-FIRST launch posts")

    # Initialize database
    db = SocialMediaDatabase(supabase_client)

    # Save each post with comprehensive error handling
    created_ids = []
    failed_posts = []
    total_posts = len(posts)

    log_info(f"💾 Saving {total_posts} posts to database...")

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

            # Attempt to save the post
            post_id = db.save_post(post_data)

            if post_id:
                created_ids.append(post_id)
                log_info(f"✅ Saved post {idx}/{total_posts}: Day {post['day']}, Post {post['post_number']} - {post['content_theme']} (ID: {post_id})")
            else:
                failed_posts.append({
                    'index': idx,
                    'day': post['day'],
                    'post_number': post['post_number'],
                    'theme': post['content_theme'],
                    'error': 'save_post returned empty ID'
                })
                log_error(f"❌ Failed to save post {idx}/{total_posts}: Day {post['day']}, Post {post['post_number']} - save_post returned empty ID")

        except Exception as e:
            failed_posts.append({
                'index': idx,
                'day': post.get('day', 'unknown'),
                'post_number': post.get('post_number', 'unknown'),
                'theme': post.get('content_theme', 'unknown'),
                'error': str(e)
            })
            log_error(f"❌ Exception saving post {idx}/{total_posts}: {str(e)}")
            import traceback
            log_error(f"Traceback: {traceback.format_exc()}")
            continue

    # Summary logging
    success_count = len(created_ids)
    fail_count = len(failed_posts)

    if success_count == total_posts:
        log_info(f"✅ VALUE-FIRST launch content seeding complete: {success_count}/{total_posts} posts created successfully")
    elif success_count > 0:
        log_warning(f"⚠️  VALUE-FIRST launch content seeding partial success: {success_count}/{total_posts} posts created, {fail_count} failed")
        log_warning(f"Failed posts: {failed_posts}")
    else:
        log_error(f"❌ VALUE-FIRST launch content seeding failed: 0/{total_posts} posts created")
        log_error(f"All posts failed: {failed_posts}")

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

        # First, get all posts with launch_content flag
        result = supabase_client.table('social_posts').select('id').like(
            'generation_prompt', '%"launch_content": true%'
        ).execute()

        if not result.data:
            log_info("No launch content posts found to delete")
            return 0

        post_ids = [post['id'] for post in result.data]
        log_info(f"Found {len(post_ids)} launch content posts to delete")

        # Delete each post by ID
        deleted_count = 0
        for post_id in post_ids:
            try:
                supabase_client.table('social_posts').delete().eq('id', post_id).execute()
                deleted_count += 1
            except Exception as e:
                log_error(f"Failed to delete post {post_id}: {e}")

        log_info(f"Deleted {deleted_count}/{len(post_ids)} launch content posts")
        return deleted_count

    except Exception as e:
        log_error(f"Error clearing launch content: {str(e)}")
        return 0


def clear_all_test_posts(supabase_client) -> int:
    """Delete all test posts and old content to start fresh with comprehensive error handling."""

    try:
        log_info("🗑️  Starting deletion of old/test posts...")

        # Delete ALL pending_approval posts
        log_info("🗑️  Deleting ALL pending_approval posts...")

        deleted_count = 0
        try:
            # Get all pending_approval posts
            result = supabase_client.table('social_posts').select('id').eq('status', 'pending_approval').execute()

            if result.data:
                pending_ids = [post['id'] for post in result.data]
                log_info(f"Found {len(pending_ids)} pending_approval posts to delete")

                # Delete each post
                for post_id in pending_ids:
                    try:
                        supabase_client.table('social_posts').delete().eq('id', post_id).execute()
                        deleted_count += 1
                    except Exception as e:
                        log_error(f"Failed to delete post {post_id}: {e}")

                log_info(f"✅ Successfully deleted {deleted_count} posts")
            else:
                log_info("ℹ️  No pending_approval posts found to delete")

        except Exception as e:
            log_error(f"❌ Error deleting pending_approval posts: {e}")

        total_deleted = deleted_count
        if total_deleted > 0:
            log_info(f"✅ Total deleted: {total_deleted} pending_approval posts")
        else:
            log_info("ℹ️  No posts needed to be deleted")

        return total_deleted

    except Exception as e:
        log_error(f"❌ Error clearing test posts: {e}")
        import traceback
        log_error(f"Traceback: {traceback.format_exc()}")
        return 0


__all__ = [
    "LaunchContentGenerator",
    "get_launch_content_preview",
    "seed_launch_content",
    "clear_launch_content",
    "clear_all_test_posts"
]
