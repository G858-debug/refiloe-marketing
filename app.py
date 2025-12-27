
"""
Refiloe Marketing - Main Flask Application
Social Media Automation System

This is the entry point for the Railway deployment.
"""

import os
import atexit
import uuid
import json
import random
import traceback
import threading
from flask import Flask, Blueprint, jsonify, request, render_template
from datetime import datetime, timedelta, timezone
import pytz

from dotenv import load_dotenv

# Import configuration
from config import config

# Import utilities
from utils.logger import log_info, log_error, log_warning
from utils.whatsapp_notifier import get_whatsapp_notifier
from utils.supabase_storage import upload_carousel_slide

from social_media.approval_routes import approval_bp, _upload_image_to_facebook_scheduler
from social_media.analytics_routes import analytics_bp
from social_media.admin_routes import admin_bp
from social_media.scheduler import SocialMediaScheduler, create_social_media_scheduler
from social_media.looks_generator import LooksGenerator, REFILOE_LOOKS


load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Load configuration
env = os.getenv('FLASK_ENV', 'production')
app.config.from_object(config[env])

# Global variables
scheduler = None
supabase_client = None
_scheduler_initialized = False

# Background generation status tracker
generation_status = {
    'is_running': False,
    'successful': [],
    'failed': [],
    'start_time': None,
    'start_date': None,
    'end_date': None
}

heygen_avatar_status = {
    "checked": False,
    "available": None,
    "details": [],
}

HEYGEN_API_KEY_ENV = "HEYGEN_API_KEY"

# South African timezone
SA_TZ = pytz.timezone('Africa/Johannesburg')

# Predefined motion prompts for video generation
MOTION_PROMPTS = [
    {
        'id': 'auto',
        'name': '🤖 Auto (Let AI decide)',
        'prompt': None,
        'description': 'Avatar IV automatically generates natural gestures based on script content'
    },
    {
        'id': 'warm_encouraging',
        'name': '😊 Warm & Encouraging',
        'prompt': 'Warm and encouraging demeanor, uses open hand gestures, friendly smile, welcoming body language',
        'description': 'Perfect for motivational and supportive content'
    },
    {
        'id': 'energetic_presenter',
        'name': '⚡ Energetic Presenter',
        'prompt': 'Energetic and dynamic presenter, emphatic hand gestures, points for emphasis, animated expressions',
        'description': 'Great for exciting announcements and tips'
    },
    {
        'id': 'calm_professional',
        'name': '💼 Calm & Professional',
        'prompt': 'Calm and professional, minimal but purposeful gestures, confident posture, measured movements',
        'description': 'Ideal for educational and business content'
    },
    {
        'id': 'empathetic_understanding',
        'name': '🤝 Empathetic & Understanding',
        'prompt': 'Empathetic and understanding, gentle hand movements, soft expressions, occasional nods, compassionate demeanor',
        'description': 'Best for relatable and emotional content'
    },
    {
        'id': 'excited_enthusiastic',
        'name': '🎉 Excited & Enthusiastic',
        'prompt': 'Excited and enthusiastic, big expressive gestures, wide eyes, animated facial expressions, high energy',
        'description': 'Perfect for celebrations and exciting news'
    },
    {
        'id': 'thoughtful_expert',
        'name': '🧠 Thoughtful Expert',
        'prompt': 'Thoughtful expert sharing insights, chin touches, contemplative pauses, knowing nods, authoritative but approachable',
        'description': 'Great for sharing expertise and insights'
    },
    {
        'id': 'conversational_friendly',
        'name': '💬 Conversational & Friendly',
        'prompt': 'Casual conversational style, natural hand movements, relaxed posture, like talking to a friend',
        'description': 'Ideal for casual, relatable content'
    },
    {
        'id': 'inspirational_leader',
        'name': '🌟 Inspirational Leader',
        'prompt': 'Inspirational leader, strong purposeful gestures, direct eye contact, commanding presence, motivating energy',
        'description': 'Best for leadership and motivational speeches'
    },
    {
        'id': 'storyteller',
        'name': '📖 Storyteller',
        'prompt': 'Engaging storyteller, varied expressions matching narrative, descriptive hand movements, dramatic pauses',
        'description': 'Perfect for sharing stories and experiences'
    }
]


def get_posting_time_for_content_type(config, content_type):
    """Get posting time from config based on content type.

    Args:
        config: Loaded config dictionary
        content_type: One of 'video', 'carousel', 'image', 'text_card', 'veo3'

    Returns:
        str: Time string like '13:30' or '14:00'
    """
    content_posting_times = config.get('content_type_posting_times', {})
    return content_posting_times.get(content_type, content_posting_times.get('default', '14:00'))


def init_supabase():
    """Initialize Supabase client with connection verification"""
    global supabase_client

    try:
        from utils.supabase_rest import SupabaseRestClient

        url = app.config['SUPABASE_URL']
        key = app.config.get('SUPABASE_SERVICE_KEY') or app.config.get('SUPABASE_ANON_KEY')

        if not url or not key:
            log_error("Supabase credentials not found in environment")
            return False, "Missing credentials"

        # Mask the key for logging
        masked_key = f"{key[:8]}...{key[-4:]}" if key and len(key) > 12 else "***"
        log_info(f"🔗 Connecting to Supabase URL: {url}")
        log_info(f"🔑 Using key: {masked_key}")

        # Create the client
        supabase_client = SupabaseRestClient(url, key)
        log_info("✅ Supabase REST client instance created")

        # Verify connection by testing a simple query
        try:
            log_info("🔍 Verifying connection by querying social_posts table...")
            result = supabase_client.table('social_posts').select('id').limit(1).execute()
            log_info(f"✅ Connection verified successfully - query returned {len(result.data) if hasattr(result, 'data') else 0} rows")
            return True, None
        except Exception as verify_error:
            log_error(f"❌ Connection verification failed: {str(verify_error)}")
            supabase_client = None
            return False, f"Verification failed: {str(verify_error)}"

    except Exception as e:
        log_error(f"❌ Failed to initialize Supabase: {str(e)}")
        import traceback
        log_error(f"Full traceback:\n{traceback.format_exc()}")
        supabase_client = None
        return False, str(e)


def verify_supabase_connection():
    """Verify Supabase connection is working by testing a query.

    Returns:
        dict: {
            'connected': bool,
            'error': str or None,
            'details': dict
        }
    """
    if not supabase_client:
        log_warning("⚠️  Supabase client not initialized")
        return {
            'connected': False,
            'error': 'Client not initialized',
            'details': {'url': app.config.get('SUPABASE_URL')}
        }

    try:
        # Test query on social_posts table
        log_info("🔍 Testing Supabase connection...")
        result = supabase_client.table('social_posts').select('id').limit(1).execute()

        # Check if query succeeded
        row_count = len(result.data) if hasattr(result, 'data') else 0
        log_info(f"✅ Connection test successful - query returned {row_count} rows")

        return {
            'connected': True,
            'error': None,
            'details': {
                'test_query': 'success',
                'url': app.config.get('SUPABASE_URL'),
                'rows_returned': row_count,
                'timestamp': datetime.now(SA_TZ).isoformat()
            }
        }
    except Exception as e:
        log_error(f"❌ Connection verification failed: {str(e)}")
        return {
            'connected': False,
            'error': str(e),
            'details': {
                'url': app.config.get('SUPABASE_URL'),
                'timestamp': datetime.now(SA_TZ).isoformat()
            }
        }


def generate_scroll_stopping_image_prompt(content_theme: str, content_text: str = "", post_type: str = "image") -> str:
    """
    Generate a scroll-stopping image prompt based on content theme.

    These prompts are optimized for Leonardo AI with the Nano Banana Pro model
    to create engaging, thumb-stopping social media images.

    IMPORTANT: Physical characteristics (age, skin tone, hair, facial features) are NOT
    included here because they are already defined by:
    1. The reference image used in Leonardo AI generation
    2. The REFILOE_CHARACTER_DESCRIPTION constant in leonardo_generator.py

    This prompt focuses ONLY on contextual elements:
    - Setting/location
    - Outfit/clothing
    - Pose/action
    - Mood/expression
    - Makeup/accessories
    - Lighting/atmosphere

    Args:
        content_theme: The theme of the post (e.g., 'motivation', 'admin_hacks', etc.)
        content_text: The post caption (used for context)
        post_type: Type of post (video, image, carousel)

    Returns:
        A detailed image prompt string (without physical characteristics)
    """

    # Theme-specific scroll-stopping prompts
    # NOTE: Physical traits are handled by reference image + REFILOE_CHARACTER_DESCRIPTION
    theme_prompts = {
        'introduction': """
            Professional social media photo of Refiloe.
            Setting: Modern co-working space with floor-to-ceiling windows, golden hour sunlight streaming in, blurred laptops, green plants, warm wood tones.
            Outfit: Stylish burnt orange blazer over a cream silk blouse.
            Pose: Standing confidently, direct eye contact with camera, one hand gesturing as if mid-conversation.
            Mood: Approachable, professional, trustworthy, inspiring, warm welcoming smile.
            Lighting: Golden hour natural light, warm ambient glow.
            Style: Editorial portrait, shallow depth of field, warm color grading, Instagram-ready.
        """,

        'motivation': """
            Professional social media photo of Refiloe.
            Setting: Bright modern gym at sunrise, sleek gym equipment softly blurred in background.
            Outfit: Vibrant coral athletic top with REFILOE branding.
            Pose: Powerful stance, hands on hips, slight forward lean conveying energy, looking directly at camera.
            Mood: Fierce determination, empowering, unstoppable, "you've got this" energy.
            Lighting: Dramatic golden light creating lens flare, high-contrast cinematic.
            Style: High-contrast, cinematic lighting, bold colors, scroll-stopping intensity.
        """,

        'admin_hacks': """
            Professional social media photo of Refiloe.
            Setting: Minimalist home office, clean organized desk with rose gold laptop, floating shelves with plants.
            Outfit: Soft sage green cardigan over a white tee, effortlessly put-together.
            Pose: Sitting at desk, looking up at camera, one eyebrow slightly raised as if sharing a secret hack.
            Mood: Knowing smile, "I figured it out so you don't have to" energy, helpful, smart.
            Lighting: Warm ambient lighting, soft natural light from window.
            Style: Lifestyle editorial, warm tones, relatable yet aspirational.
        """,

        'client_management': """
            Professional social media photo of Refiloe.
            Setting: Cozy coffee shop corner, warm wood, exposed brick, blurred café patrons creating life.
            Outfit: Cream knit sweater, holding a latte.
            Pose: Leaning forward engagingly as if in deep conversation.
            Mood: Genuine caring expression, understanding, empathetic, "I get it" connection.
            Lighting: Soft window light illuminating face, bokeh of café life behind.
            Style: Candid lifestyle shot, warm color palette, intimate feeling.
        """,

        'relatable_trainer_life': """
            Professional social media photo of Refiloe.
            Setting: Empty gym, equipment visible, between-sessions moment.
            Outfit: Black leggings and a lived-in grey hoodie.
            Pose: Candid moment sitting on gym floor, back against mirror, phone in hand.
            Mood: Slight exhausted but amused expression, real unposed moment, "This is the real life" vulnerability.
            Lighting: Gym fluorescent lights for authenticity.
            Style: Documentary-style, slightly desaturated, raw and real.
        """,

        'business_growth': """
            Professional social media photo of Refiloe.
            Setting: Modern office space with whiteboard filled with growth charts and strategies, charts showing upward trends.
            Outfit: Sharp navy blazer, professional attire.
            Pose: Standing in front of whiteboard, marker in hand, confident teaching posture, mid-explanation gesture.
            Mood: Warm smile but serious eyes - she means business, authority, expertise, "level up" energy.
            Lighting: Professional office lighting, clean and bright.
            Style: Corporate editorial, clean lines, aspirational business aesthetic.
        """,

        'fitness_tips': """
            Professional social media photo of Refiloe.
            Setting: Bright fitness studio with mirrors, natural light, clean minimalist design.
            Outfit: Bold purple sports bra with REFILOE branding and high-waisted black leggings.
            Pose: Mid-movement demonstrating perfect form on an exercise, dynamic pose captured mid-action, muscles engaged.
            Mood: Focused expression, powerful presence, expert, capable, inspiring action.
            Lighting: Bright natural light through studio windows.
            Style: Fitness editorial, sharp focus on movement, energetic composition.
        """,

        'community_engagement': """
            Professional social media photo of Refiloe.
            Setting: Bright airy studio, other blurred figures suggesting community atmosphere.
            Outfit: Comfy athleisure, casual and approachable.
            Pose: Sitting cross-legged on a yoga mat, breaking the fourth wall - looking directly at viewer as if sharing a joke.
            Mood: Laughing genuinely with hand partially covering mouth, eyes crinkled with joy, inclusive, fun, "you belong here" warmth.
            Lighting: Soft studio lighting, bright and welcoming.
            Style: Candid lifestyle, high energy, contagious joy.
        """,

        'special_event': """
            Professional social media photo of Refiloe.
            Setting: Festive but not cluttered background, color-coordinated to the occasion.
            Outfit: Statement piece that pops against the background, something special for celebrations.
            Pose: Celebratory pose with confetti or sparkles, arms raised or clapping, caught in a moment of pure celebration.
            Mood: Genuine excited expression, exciting, milestone moment, share the joy.
            Lighting: High energy, vibrant colors.
            Style: High energy, vibrant colors, celebratory mood.
        """,

        'educational': """
            Professional social media photo of Refiloe.
            Setting: Clean, simple, non-distracting background to focus on expertise, with space for text overlay.
            Outfit: Smart casual - a structured top in warm terracotta.
            Pose: Slight head tilt suggesting active thinking, finger touching chin as if considering a question.
            Mood: Thoughtful expression, engaged eyes, knowledgeable, approachable teacher.
            Lighting: Soft, even lighting for professional look.
            Style: Portrait with negative space for text overlay potential.
        """,
    }

    # Default prompt if theme not found
    default_prompt = """
        Professional social media photo of Refiloe.
        Setting: Warm, modern professional space.
        Outfit: Stylish but relatable athleisure or smart casual.
        Pose: Confident stance, approachable, direct eye contact.
        Mood: Professional, trustworthy, aspirational yet relatable.
        Lighting: Soft natural lighting, shallow depth of field.
        Style: Editorial lifestyle photography, warm color grading, Instagram-ready composition.
    """

    # Get theme-specific prompt or default
    prompt = theme_prompts.get(content_theme, default_prompt)

    # Clean up whitespace
    prompt = ' '.join(prompt.split())

    return prompt


def convert_carousel_format(data: dict, content_type: str = 'educational') -> dict:
    """Convert carousel data from cover/content_slides/cta format to slides format.

    Args:
        data: Carousel data with 'cover', 'content_slides', 'cta_slide' keys
        content_type: Content type for styling

    Returns:
        Dict with 'slides' key in the format carousel_template_generator expects
    """
    slides = []

    # Cover slide
    cover = data.get('cover', {})
    slides.append({
        "type": "COVER",
        "title": cover.get('title', 'Tips for Personal Trainers'),
        "avatar_path": ""
    })

    # Content slides
    content_slides = data.get('content_slides', [])
    for i, slide in enumerate(content_slides, 1):
        slides.append({
            "type": "CONTENT",
            "step_title": slide.get('title', f"Step {i}"),
            "bullets": slide.get('bullets', [])
        })

    # CTA slide - use random from varied messages if not provided
    cta = data.get('cta_slide', {})
    if not cta or not cta.get('headline'):
        import random
        # Varied CTA messages (25% each category)
        cta_messages = [
            # === FOLLOW CTAs (25%) ===
            {"headline": "Ready to scale?", "cta_text": "Hit follow!", "subtext": "Tips to grow your PT business"},
            {"headline": "Want more tips?", "cta_text": "Follow for daily insights", "subtext": "Join the community"},

            # === INSPIRATIONAL QUOTES (25%) ===
            {"headline": "Remember why you started", "cta_text": "Your clients need YOU", "subtext": "Keep pushing forward"},
            {"headline": "Success is built daily", "cta_text": "Small steps, big results", "subtext": "You've got this"},

            # === SAVE/SHARE PROMPTS (25%) ===
            {"headline": "Found this helpful?", "cta_text": "Save for later!", "subtext": "Share with a fellow trainer"},
            {"headline": "Bookmark this", "cta_text": "You'll thank yourself later", "subtext": "Tag a trainer who needs this"},

            # === ENGAGEMENT QUESTIONS (25%) ===
            {"headline": "What's your biggest challenge?", "cta_text": "Drop a comment below", "subtext": "Let's solve it together"},
            {"headline": "Which tip resonated most?", "cta_text": "Tell us in the comments", "subtext": "We read every one"},
        ]
        cta = random.choice(cta_messages)

    slides.append({
        "type": "CTA",
        "headline": cta.get('headline', 'Ready to scale?'),
        "cta_text": cta.get('cta_text', 'Hit follow!'),
        "subtext": cta.get('subtext', 'Tips to grow your PT business')
    })

    return {"slides": slides, "content_type": content_type}


def transform_raw_slides_to_carousel_format(raw_slides: list) -> list:
    """Transform raw slide data from metadata into carousel generator format.

    Handles MULTIPLE input formats:
    1. Legacy format: slide_number, text, description
    2. AI-generated format: step_number, title, bullets
    3. Mixed format: combination of the above

    Creates: COVER (1) + CONTENT slides (remaining items) + CTA (1)

    Args:
        raw_slides: List of slides with various field formats

    Returns:
        List of slides in carousel generator format
    """
    import random

    def clean_text(text: str) -> str:
        """Remove non-ASCII and special characters from text."""
        if not text:
            return ""
        cleaned = ''.join(char for char in text if 32 <= ord(char) < 128)
        return cleaned.strip()

    def clean_slide_prefix(text: str) -> str:
        """Remove 'Slide X:' prefix from text."""
        import re
        if not text:
            return ""
        # Remove "Slide X:" or "Slide X :" prefix (case insensitive)
        cleaned = re.sub(r'^Slide\s*\d+\s*:\s*', '', text, flags=re.IGNORECASE)
        # Remove standalone slide references
        cleaned = re.sub(r'^Slide\s*\d+\s*$', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    if not raw_slides:
        return []

    # CTA messages to rotate through (varied mix - 25% each category)
    cta_messages = [
        # === FOLLOW CTAs (25%) ===
        {"headline": "Ready to scale?", "cta_text": "Hit follow!", "subtext": "Tips to grow your PT business"},
        {"headline": "Want more tips?", "cta_text": "Follow for daily insights", "subtext": "Join the community"},

        # === INSPIRATIONAL QUOTES (25%) ===
        {"headline": "Remember why you started", "cta_text": "Your clients need YOU", "subtext": "Keep pushing forward"},
        {"headline": "Success is built daily", "cta_text": "Small steps, big results", "subtext": "You've got this"},

        # === SAVE/SHARE PROMPTS (25%) ===
        {"headline": "Found this helpful?", "cta_text": "Save for later!", "subtext": "Share with a fellow trainer"},
        {"headline": "Bookmark this", "cta_text": "You'll thank yourself later", "subtext": "Tag a trainer who needs this"},

        # === ENGAGEMENT QUESTIONS (25%) ===
        {"headline": "What's your biggest challenge?", "cta_text": "Drop a comment below", "subtext": "Let's solve it together"},
        {"headline": "Which tip resonated most?", "cta_text": "Tell us in the comments", "subtext": "We read every one"},
    ]

    transformed = []

    # Extract title from the first slide for the COVER
    # Check both 'text' (legacy) and 'title' (AI-generated) fields
    first_slide = raw_slides[0]
    first_text = clean_text(first_slide.get('text', '') or first_slide.get('title', ''))
    cover_title = first_text[:60] if first_text else 'Tips for Personal Trainers'

    # Slide 1: COVER
    transformed.append({
        'type': 'COVER',
        'title': cover_title,
        'avatar_path': ''
    })

    # SKIP first slide - it's used for cover only
    # All REMAINING raw slides become CONTENT slides
    content_slides = raw_slides[1:] if len(raw_slides) > 1 else []

    for i, slide in enumerate(content_slides):
        # Handle both legacy ('text') and AI-generated ('title') formats
        text = clean_text(slide.get('text', '') or slide.get('title', ''))

        # Handle both legacy ('description') and AI-generated ('bullets') formats
        description = clean_text(slide.get('description', ''))
        ai_bullets = slide.get('bullets', [])

        # Clean "Slide X:" prefix from all content sources
        text = clean_slide_prefix(text)
        description = clean_slide_prefix(description)

        # Create step title - use cleaned text or fall back to generic
        if text:
            header = f"Step {i + 1}: {text}"
        else:
            header = f"Step {i + 1}"

        # Build bullets - check AI-generated 'bullets' first, then fall back to 'description'
        bullets = []

        # Priority 1: Use AI-generated bullets array if available
        if ai_bullets and isinstance(ai_bullets, list) and len(ai_bullets) > 0:
            # Clean each AI bullet - remove "Slide X:" prefixes
            cleaned_bullets = []
            for b in ai_bullets:
                if b:
                    cleaned_b = clean_slide_prefix(clean_text(b))
                    if cleaned_b and len(cleaned_b) > 3:  # Skip very short or empty bullets
                        cleaned_bullets.append(cleaned_b)
            bullets = cleaned_bullets[:5]  # Max 5 bullets
            log_info(f"  Slide {i+2}: Using {len(bullets)} AI-generated bullets (cleaned)")

        # Priority 2: Parse description field (legacy format)
        elif description:
            if '. ' in description:
                sentences = [s.strip() for s in description.split('. ') if s.strip()]
                # Clean each sentence
                bullets = [clean_slide_prefix(s) for s in sentences[:3] if clean_slide_prefix(s)]
            else:
                bullets = [description]
            log_info(f"  Slide {i+2}: Parsed {len(bullets)} bullets from description")

        # Priority 3: Use the title text as fallback content
        if not bullets:
            if text:
                bullets = [text]
                log_info(f"  Slide {i+2}: Using title text as fallback content")
            else:
                bullets = ["More tips coming soon!"]
                log_warning(f"  Slide {i+2}: No content found - using placeholder!")

        # Final filter - remove empty bullets
        bullets = [b for b in bullets if b and len(b) > 3]

        transformed.append({
            'type': 'CONTENT',
            'step_title': header,
            'bullets': bullets
        })

    # Final slide: CTA
    cta = random.choice(cta_messages)
    transformed.append({
        'type': 'CTA',
        'headline': cta['headline'],
        'cta_text': cta['cta_text'],
        'subtext': cta['subtext']
    })

    return transformed


def parse_caption_to_carousel(caption: str, content_type: str = 'educational') -> dict:
    """Parse a caption/content text into carousel slide structure.

    Args:
        caption: The post caption/content text
        content_type: Content type for styling

    Returns:
        Dict with 'slides' key containing slide configurations
    """
    slides = []

    # Extract title from first line or first sentence
    lines = [l.strip() for l in caption.split('\n') if l.strip()]

    if not lines:
        # Fallback title
        title = "Tips for Personal Trainers"
    else:
        # Use first line as title, truncate if needed
        title = lines[0][:60]
        if title.endswith(('...', '.', '!')):
            pass
        elif len(lines[0]) > 60:
            title = title.rsplit(' ', 1)[0] + '...'

    # Slide 1: COVER
    slides.append({
        "type": "COVER",
        "title": title,
        "avatar_path": ""
    })

    # Try to extract bullet points or key points from content
    key_points = []

    for line in lines[1:]:  # Skip title
        # Skip very short lines or hashtag lines
        if len(line) < 10 or line.startswith('#'):
            continue
        # Look for bullet-like patterns
        clean_line = line.lstrip('•-*→✓✅1234567890.)')
        clean_line = clean_line.strip()
        if clean_line and len(clean_line) > 15:
            key_points.append(clean_line)

    # If no bullet points found, split content into chunks
    if not key_points:
        # Join all non-title content
        content = ' '.join(lines[1:])
        # Split into sentences
        sentences = content.replace('!', '.').replace('?', '.').split('.')
        key_points = [s.strip() for s in sentences if len(s.strip()) > 20][:5]

    # Ensure we have at least 3 key points
    default_points = [
        "Automate your client communication",
        "Save hours on admin tasks every week",
        "Focus on what you do best - training clients"
    ]
    while len(key_points) < 3:
        if default_points:
            key_points.append(default_points.pop(0))
        else:
            key_points.append("More tips coming soon")

    # Slides 2-4: CONTENT (3 content slides)
    for i, point in enumerate(key_points[:3], 1):
        # Truncate bullet text if too long
        bullet_text = point[:80] if len(point) > 80 else point

        slides.append({
            "type": "CONTENT",
            "step_title": f"Step {i}",
            "bullets": [bullet_text]
        })

    # Slide 5: CTA
    slides.append({
        "type": "CTA",
        "headline": "Ready to Save Time?",
        "cta_text": "Follow for more tips!",
        "subtext": "Save this post for later"
    })

    return {"slides": slides, "content_type": content_type}


def generate_trainer_hashtags(content_type: str = 'educational') -> list:
    """Generate relevant hashtags for personal trainer content.

    Args:
        content_type: Type of content - 'educational', 'motivational', 'admin_hacks',
                      'relatable', or 'business'

    Returns:
        List of hashtags (7-8 tags) including core, content-specific, SA, and brand tags
    """
    # Core hashtags (always include 3 of these)
    core_hashtags = [
        '#PersonalTrainer', '#FitnessCoach', '#PTLife', '#FitnessBusiness',
        '#PersonalTraining', '#FitnessIndustry', '#TrainerLife'
    ]

    # Content-type specific hashtags
    type_hashtags = {
        'educational': ['#FitnessTips', '#TrainerTips', '#FitnessEducation', '#LearnFitness'],
        'motivational': ['#FitnessMotivation', '#GymMotivation', '#FitInspiration', '#MondayMotivation'],
        'admin_hacks': ['#BusinessTips', '#ProductivityHacks', '#TimeManagement', '#WorkSmarter'],
        'relatable': ['#TrainerProblems', '#GymLife', '#FitnessHumor', '#PTProblems'],
        'business': ['#FitnessBusiness', '#EntrepreneurLife', '#BusinessGrowth', '#SideHustle']
    }

    # South African hashtags (include 1)
    sa_hashtags = ['#SouthAfrica', '#SAFitness', '#MzansiFitness', '#FitnessSA']

    hashtags = []
    hashtags.extend(random.sample(core_hashtags, 3))
    hashtags.extend(random.sample(type_hashtags.get(content_type, type_hashtags['educational']), 2))
    hashtags.extend(random.sample(sa_hashtags, 1))
    hashtags.append('#Refiloe')  # Brand hashtag

    return hashtags


def init_scheduler():
    """Initialize social media scheduler"""
    global scheduler

    if scheduler and scheduler.is_running():
        log_info("Scheduler already running; skipping initialization.")
        return True

    if not app.config.get('ENABLE_SOCIAL_MEDIA', True):
        log_warning("Social media automation is disabled via configuration.")
        return False

    if supabase_client is None:
        log_warning("Supabase client not initialized; scheduler setup deferred.")
        return False

    try:
        if scheduler is None:
            scheduler_instance = create_social_media_scheduler(app, supabase_client)
            if not scheduler_instance:
                log_error("Failed to create scheduler instance.")
                return False
            scheduler = scheduler_instance

        if scheduler.start():
            log_info("✅ Social media scheduler started successfully")
            return True

        log_error("Scheduler start returned False; scheduler may not be running.")
        return False

    except Exception as e:
        log_error(f"Failed to initialize scheduler: {str(e)}")
        import traceback
        log_error(traceback.format_exc())
        return False


def start_scheduler():
    """Start the scheduler if enabled and initialized."""
    if not app.config.get('ENABLE_SOCIAL_MEDIA', True):
        return False
    return init_scheduler()


def stop_scheduler():
    """Stop the scheduler if it is running."""
    global scheduler
    if scheduler:
        try:
            scheduler.stop()
        except Exception as e:
            log_error(f"Error stopping scheduler: {str(e)}")


# Health check endpoint
@app.route('/')
@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'refiloe-marketing',
        'timestamp': datetime.now(SA_TZ).isoformat(),
        'components': {
            'supabase': supabase_client is not None,
            'scheduler': scheduler.is_running() if scheduler else False,
            'social_media_enabled': app.config.get('ENABLE_SOCIAL_MEDIA', False),
            'heygen': heygen_avatar_status,
        },
        'links': {
            'approval_pending': '/approval/pending',
            'content_pipeline_health': '/health/content-pipeline',
            'admin_avatar_looks': '/admin/avatar-looks'
        }
    }), 200


@app.route('/api/status')
def status():
    """Detailed status endpoint"""
    # Determine Supabase status
    supabase_status = 'disconnected'
    if supabase_client and app.config.get('SUPABASE_CONNECTED', False):
        supabase_status = 'connected'
    elif supabase_client:
        supabase_status = 'initialized_but_not_verified'

    status_info = {
        'service': 'refiloe-marketing',
        'version': '1.0.0',
        'timestamp': datetime.now(SA_TZ).isoformat(),
        'environment': os.getenv('FLASK_ENV', 'production'),
        'components': {
            'flask': 'running',
            'supabase': supabase_status,
            'scheduler': 'running' if scheduler and scheduler.is_running() else 'stopped',
            'social_media': 'enabled' if app.config.get('ENABLE_SOCIAL_MEDIA') else 'disabled',
            'heygen': heygen_avatar_status,
        },
        'configuration': {
            'timezone': 'Africa/Johannesburg',
            'log_level': app.config.get('LOG_LEVEL', 'INFO')
        }
    }

    return jsonify(status_info), 200


@app.route('/api/connection-status')
def connection_status():
    """Get detailed Supabase connection status"""
    # Run a fresh verification check
    verification_result = verify_supabase_connection()

    # Update the stored values
    app.config['SUPABASE_CONNECTED'] = verification_result['connected']
    app.config['SUPABASE_ERROR'] = verification_result.get('error')
    app.config['SUPABASE_LAST_CHECK'] = datetime.now(SA_TZ)

    response = {
        'connected': verification_result['connected'],
        'error': verification_result.get('error'),
        'last_check': app.config.get('SUPABASE_LAST_CHECK').isoformat() if app.config.get('SUPABASE_LAST_CHECK') else None,
        'details': verification_result.get('details', {}),
        'client_initialized': supabase_client is not None
    }

    status_code = 200 if verification_result['connected'] else 503
    return jsonify(response), status_code


@app.route('/health/content-pipeline')
def content_pipeline_health():
    """Content pipeline health monitoring endpoint"""
    if not supabase_client or not app.config.get('SUPABASE_CONNECTED', False):
        error_msg = app.config.get('SUPABASE_ERROR', 'Database not connected')
        return jsonify({
            'error': 'Database not connected',
            'details': error_msg
        }), 503

    try:
        from social_media.content_monitor import ContentPipelineMonitor

        monitor = ContentPipelineMonitor(supabase_client)

        # Get comprehensive health report
        health_report = monitor.check_pipeline_health()

        # Get content counts by status
        content_counts = monitor.get_content_counts_by_status()

        # Get 7-day coverage details
        coverage = monitor.get_next_7_days_coverage()

        # Get recommended actions
        recommended_actions = monitor.get_recommended_actions(health_report)

        # Build response
        response = {
            'pipeline_status': health_report['status'],
            'checked_at': health_report['checked_at'],
            'metrics': {
                'pending_approval': health_report['pending_approval_count'],
                'scheduled_next_7_days': health_report['scheduled_count'],
                'days_with_content': health_report['scheduled_days_coverage'],
                'content_gaps_count': len(health_report['content_gaps']),
                'video_failure_rate': health_report['video_failure_rate']
            },
            'content_counts_by_status': content_counts,
            'next_7_days_coverage': coverage,
            'alerts': health_report['alerts'],
            'recommended_actions': recommended_actions,
            'content_gaps': health_report['content_gaps']
        }

        # Set HTTP status based on pipeline status
        http_status = 200
        if health_report['status'] == 'warning':
            http_status = 200  # Still 200, but with warnings
        elif health_report['status'] == 'critical':
            http_status = 200  # Still 200, client should check 'pipeline_status' field

        return jsonify(response), http_status

    except Exception as e:
        log_error(f"Error checking content pipeline health: {str(e)}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({
            'error': str(e),
            'pipeline_status': 'unknown'
        }), 500


@app.route('/scheduler/status')
def scheduler_status():
    """Expose scheduler runtime status and job metadata."""
    if not scheduler:
        return jsonify({
            'running': False,
            'job_count': 0,
            'jobs': [],
            'message': 'Scheduler not initialized'
        }), 503

    try:
        status_payload = scheduler.get_status()
        http_status = 200 if status_payload.get('running') else 503
        return jsonify(status_payload), http_status
    except Exception as e:
        log_error(f"Error retrieving scheduler status: {str(e)}")
        return jsonify({
            'running': False,
            'error': str(e)
        }), 500


@app.route('/api/scheduler/jobs')
def scheduler_jobs():
    """Get list of scheduled jobs"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 503
    
    try:
        status_payload = scheduler.get_status()
        jobs = status_payload.get('jobs', [])
        response_body = {
            'jobs': jobs,
            'total': status_payload.get('job_count', len(jobs)),
            'scheduler_running': status_payload.get('running', False)
        }
        http_status = 200 if status_payload.get('running') else 503
        return jsonify(response_body), http_status

    except Exception as e:
        log_error(f"Error getting scheduler jobs: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/test-database')
def test_database():
    """Test database connectivity and insertion"""
    if not supabase_client or not app.config.get('SUPABASE_CONNECTED', False):
        error_msg = app.config.get('SUPABASE_ERROR', 'Database not connected')
        return jsonify({
            'error': 'Database not connected',
            'details': error_msg
        }), 503

    from social_media.database import SocialMediaDatabase
    db = SocialMediaDatabase(supabase_client)

    # Test connection
    if not db.test_database_connection():
        return jsonify({'error': 'Database connection failed'}), 500

    # Test insertion
    test_post = {
        'post_type': 'test',
        'platform': 'facebook',
        'content_text': f'Test post created at {datetime.now(SA_TZ).isoformat()}',
        'status': 'pending_approval',
        'scheduled_time': (datetime.now(SA_TZ) + timedelta(hours=1)).isoformat()
    }

    post_id = db.save_post(test_post)

    if post_id:
        return jsonify({
            'success': True,
            'post_id': post_id,
            'message': 'Database working correctly!'
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to save test post'
        }), 500


@app.route('/api/debug/posts')
def debug_posts():
    """Debug endpoint to see all posts in database"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        # Get all posts regardless of status
        result = supabase_client.table('social_posts').select('*').order('created_at', desc=True).limit(10).execute()
        posts = result.data if result else []

        # Get count by status
        status_counts = {}
        for post in posts:
            status = post.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        return jsonify({
            'total_posts': len(posts),
            'status_counts': status_counts,
            'recent_posts': posts[:5],  # Show first 5 posts
            'looking_for_status': 'pending_approval'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/debug/pending-posts')
def debug_pending_posts():
    """Debug endpoint to check pending posts structure"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        result = (
            supabase_client
            .table('social_posts')
            .select('*')
            .eq('status', 'pending_approval')
            .execute()
        )

        posts = result.data if hasattr(result, 'data') else []

        return jsonify({
            'total': len(posts),
            'posts': posts,
            'sample_id': posts[0]['id'] if posts else None,
            'sample_url': f"/approval/view/{posts[0]['id']}" if posts else None
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/debug/schema')
def debug_schema():
    """Check the actual columns in the social_posts table"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503
    
    try:
        # Get table schema information
        result = supabase_client.rpc('get_table_columns', {
            'table_name': 'social_posts'
        }).execute()
        
        if result.data:
            return jsonify({
                'columns': result.data,
                'message': 'Table schema retrieved'
            }), 200
    except Exception:
        pass
    
    # Fallback: Try to get a single row to see its structure
    try:
        result = supabase_client.table('social_posts').select('*').limit(1).execute()
        if result.data and len(result.data) > 0:
            columns = list(result.data[0].keys())
        else:
            # Insert a test row to see what columns exist
            test_data = {
                'id': str(uuid.uuid4()),
                'platform': 'test',
                'status': 'test'
            }
            # Insert into database and execute
            result = supabase_client.table('social_posts').insert(test_data).execute()
            if result.data:
                columns = list(result.data[0].keys())
            else:
                columns = []
        
        return jsonify({
            'columns': columns,
            'message': 'Columns detected from table'
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Could not determine table structure'
        }), 500


@app.route('/api/debug/carousel-data/<post_id>')
def debug_carousel_data(post_id):
    """Debug endpoint to inspect carousel post data structure.

    Use this to diagnose why carousel slides might be showing titles instead of content.
    """
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'error': 'Post not found', 'post_id': post_id}), 404

        post = result.data[0]

        # Helper to safely parse JSON
        def safe_parse(val):
            if val is None:
                return None
            if isinstance(val, (dict, list)):
                return val
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return val
            return val

        # Extract all carousel-related data
        carousel_data = safe_parse(post.get('carousel_data'))
        generation_prompt = safe_parse(post.get('generation_prompt'))
        media_url = safe_parse(post.get('media_url'))

        # Find carousel slides from different possible locations
        slides = None
        slides_source = None

        if carousel_data:
            if isinstance(carousel_data, dict) and carousel_data.get('slides'):
                slides = carousel_data.get('slides')
                slides_source = "carousel_data.slides"
            elif isinstance(carousel_data, list):
                slides = carousel_data
                slides_source = "carousel_data (raw list)"

        if not slides and generation_prompt:
            if isinstance(generation_prompt, dict):
                inner = generation_prompt.get('carousel_data') or generation_prompt.get('carousel_slides')
                if inner:
                    inner = safe_parse(inner)
                    if isinstance(inner, dict) and inner.get('slides'):
                        slides = inner.get('slides')
                        slides_source = "generation_prompt.carousel_data.slides"
                    elif isinstance(inner, list):
                        slides = inner
                        slides_source = "generation_prompt.carousel_slides (raw list)"

        # Analyze slide content issues
        slide_analysis = []
        if slides:
            for i, slide in enumerate(slides):
                if isinstance(slide, dict):
                    analysis = {
                        'slide_number': i + 1,
                        'keys': list(slide.keys()),
                        'type': slide.get('type'),
                        'has_text': bool(slide.get('text')),
                        'has_description': bool(slide.get('description')),
                        'has_bullets': bool(slide.get('bullets')),
                        'has_step_title': bool(slide.get('step_title')),
                        'text_preview': str(slide.get('text', ''))[:100] if slide.get('text') else None,
                        'description_preview': str(slide.get('description', ''))[:100] if slide.get('description') else None,
                        'bullets': slide.get('bullets', [])[:3] if slide.get('bullets') else None,
                    }

                    # Check for content issues
                    if i > 0 and slide.get('type', '').upper() != 'CTA':  # Content slides
                        if not slide.get('description') and not slide.get('bullets'):
                            analysis['issue'] = "NO CONTENT - slide will only show title!"
                        else:
                            analysis['issue'] = None

                    slide_analysis.append(analysis)
                else:
                    slide_analysis.append({
                        'slide_number': i + 1,
                        'issue': f"Not a dict: {type(slide)}",
                        'raw_value': str(slide)[:200]
                    })

        return jsonify({
            'post_id': post_id,
            'title': post.get('title'),
            'post_type': post.get('post_type'),
            'status': post.get('status'),
            'carousel_data': carousel_data,
            'carousel_data_type': type(carousel_data).__name__ if carousel_data else None,
            'generation_prompt': generation_prompt,
            'generation_prompt_type': type(generation_prompt).__name__ if generation_prompt else None,
            'content_text': post.get('content_text', '')[:500] if post.get('content_text') else None,
            'caption': str(post.get('caption', ''))[:500] if post.get('caption') else None,
            'media_url': media_url,
            'media_url_count': len(media_url) if isinstance(media_url, list) else (1 if media_url else 0),
            'slides_found': len(slides) if slides else 0,
            'slides_source': slides_source,
            'slide_analysis': slide_analysis,
            'diagnosis': {
                'has_carousel_data': carousel_data is not None,
                'has_slides': slides is not None and len(slides) > 0,
                'slides_in_generation_prompt': slides_source and 'generation_prompt' in slides_source,
                'content_missing': any(s.get('issue') for s in slide_analysis if isinstance(s, dict)),
            }
        }), 200

    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/debug/verify-avatar-group', methods=['GET'])
def verify_avatar_group():
    """Verify if HEYGEN_AVATAR_GROUP is a valid Photo Avatar Group"""
    import os
    import requests

    api_key = os.getenv('HEYGEN_API_KEY')
    group_id = os.getenv('HEYGEN_AVATAR_GROUP')

    if not api_key or not group_id:
        return jsonify({
            'error': 'Missing HEYGEN_API_KEY or HEYGEN_AVATAR_GROUP',
            'has_api_key': bool(api_key),
            'has_group_id': bool(group_id)
        }), 400

    # Try to get group info
    try:
        response = requests.get(
            f'https://api.heygen.com/v2/photo_avatar/group/{group_id}',
            headers={'X-Api-Key': api_key},
            timeout=15
        )

        return jsonify({
            'status_code': response.status_code,
            'is_valid_group': response.ok,
            'group_id': group_id,
            'response': response.json() if response.ok else response.text
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'group_id': group_id
        }), 500


@app.route('/api/debug/test-heygen-look-direct', methods=['POST'])
def test_heygen_look_direct():
    """Directly test HeyGen look generation with minimal payload"""
    import os
    import requests
    import json

    api_key = os.getenv('HEYGEN_API_KEY')
    group_id = os.getenv('HEYGEN_AVATAR_GROUP')

    if not api_key or not group_id:
        return jsonify({
            'error': 'Missing credentials',
            'has_api_key': bool(api_key),
            'has_group_id': bool(group_id)
        }), 400

    # Get test prompt from request
    data = request.get_json() or {}
    test_prompt = data.get('prompt', 'Professional fitness trainer wearing athletic wear, standing in a modern gym')

    # Try the API call with absolute minimal payload
    payload = {
        "group_id": group_id,
        "prompt": test_prompt
    }

    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }

    url = "https://api.heygen.com/v2/photo_avatar/look/generate"

    try:
        log_info(f"Direct test API call to: {url}")
        log_info(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        result = {
            'status_code': response.status_code,
            'success': response.ok,
            'url': url,
            'payload_sent': payload,
            'headers_sent': {k: v for k, v in headers.items() if k != 'X-Api-Key'},
        }

        if response.ok:
            result['response_data'] = response.json()
        else:
            result['error_response'] = response.text
            try:
                result['error_json'] = response.json()
            except:
                pass

        return jsonify(result), response.status_code

    except Exception as e:
        return jsonify({
            'error': str(e),
            'payload_attempted': payload
        }), 500

@app.route('/api/test-whatsapp')
def test_whatsapp():
    """Test WhatsApp notification connection"""
    from utils.whatsapp_notifier import WhatsAppNotifier

    try:
        notifier = WhatsAppNotifier()
        result = notifier.test_connection()
        return jsonify({
            'success': result,
            'message': 'WhatsApp test message sent!' if result else 'Failed to send test message'
        }), 200 if result else 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/trigger-weekly-report')
def trigger_weekly_report():
    """Manually trigger weekly report (for testing)"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 503

    try:
        scheduler.run_weekly_report()
        return jsonify({
            'success': True,
            'message': 'Weekly report triggered'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/reports/latest')
def get_latest_report():
    """Get the most recent weekly report"""
    if not supabase_client or not app.config.get('SUPABASE_CONNECTED', False):
        error_msg = app.config.get('SUPABASE_ERROR', 'Database not connected')
        return jsonify({
            'error': 'Database not connected',
            'details': error_msg
        }), 503

    try:
        result = supabase_client.table('weekly_reports').select('*').order(
            'created_at', desc=True
        ).limit(1).execute()

        if result.data:
            return jsonify(result.data[0]), 200
        else:
            return jsonify({'message': 'No reports found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/test/content')
def test_content_generation():
    """Test content generation (for debugging)"""
    if not supabase_client:
        return jsonify({'error': 'Supabase not initialized'}), 503

    try:
        from social_media.content_generator import ContentGenerator

        generator = ContentGenerator('social_media/config.yaml', supabase_client)

        # Generate one test post
        post = generator.generate_single_post('admin_hacks', 'single_image_with_caption')

        if post:
            return jsonify({
                'success': True,
                'post': {
                    'title': post.get('title', 'No title'),
                    'theme': post.get('theme'),
                    'format': post.get('format'),
                    'content_preview': post.get('content', '')[:200] + '...'
                }
            }), 200
        else:
            return jsonify({'error': 'Failed to generate post'}), 500

    except Exception as e:
        log_error(f"Error testing content generation: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/launch-content/preview')
def preview_launch_content():
    """Preview launch content without saving"""
    try:
        from social_media.launch_content import get_launch_content_preview
        content = get_launch_content_preview()
        return jsonify({'success': True, 'posts': content, 'count': len(content)}), 200
    except Exception as e:
        log_error(f"Error previewing launch content: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/launch-content/seed', methods=['POST'])
def seed_launch_content_route():
    """Generate and save launch content to database"""
    if not supabase_client or not app.config.get('SUPABASE_CONNECTED', False):
        error_msg = app.config.get('SUPABASE_ERROR', 'Supabase not initialized')
        return jsonify({
            'error': 'Supabase not initialized',
            'details': error_msg
        }), 503

    try:
        from social_media.launch_content import seed_launch_content as seed_func
        from datetime import datetime

        start_date_str = request.json.get('start_date') if request.json else None
        start_date = None
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)

        post_ids = seed_func(supabase_client, start_date)
        return jsonify({
            'success': True,
            'posts_created': len(post_ids),
            'post_ids': post_ids,
            'message': f'Created {len(post_ids)} launch posts. Review at /approval/pending'
        }), 201
    except Exception as e:
        log_error(f"Error seeding launch content: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/launch-content/clear', methods=['POST'])
def clear_launch_content_route():
    """Clear existing launch content (for regeneration)"""
    if not supabase_client or not app.config.get('SUPABASE_CONNECTED', False):
        error_msg = app.config.get('SUPABASE_ERROR', 'Supabase not initialized')
        return jsonify({
            'error': 'Supabase not initialized',
            'details': error_msg
        }), 503

    try:
        from social_media.launch_content import clear_launch_content

        deleted_count = clear_launch_content(supabase_client)
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Cleared {deleted_count} launch content posts'
        }), 200
    except Exception as e:
        log_error(f"Error clearing launch content: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-real-video', methods=['POST'])
def generate_real_video():
    """Generate a real marketing video with actual content"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        from social_media.video_generator import VideoGenerator
        from social_media.database import SocialMediaDatabase
        import random

        db = SocialMediaDatabase(supabase_client)
        video_gen = VideoGenerator('social_media/config.yaml', supabase_client)

        data = request.get_json() or {}

        content_options = [
            {
                'theme': 'admin_tips',
                'script': (
                    "Hey trainers! Tired of drowning in admin work? "
                    "Here's a game-changer: Automate your client bookings with Refiloe. "
                    "No more back-and-forth WhatsApp messages. "
                    "Your clients book directly, you get notifications, and payments are handled automatically. "
                    "That's 5 hours of admin saved every week. "
                    "Imagine what you could do with that extra time! "
                    "Ready to level up? Check out Refiloe today!"
                ),
                'content_text': (
                    "🚀 Save 5+ hours weekly on admin tasks! Refiloe automates your bookings, payments, and client "
                    "management. Let AI handle the paperwork while you focus on training. "
                    "#PersonalTrainer #FitnessAutomation #RefiloeSA"
                )
            },
            {
                'theme': 'motivation',
                'script': (
                    "Personal trainers, this one's for you! "
                    "Remember why you started this journey? To transform lives, not shuffle paperwork. "
                    "But here's the reality: You're spending more time on admin than actual training. "
                    "What if I told you there's a way to get those hours back? "
                    "Refiloe handles your scheduling, sends workout plans, and tracks client progress automatically. "
                    "It's time to focus on what you do best - changing lives!"
                ),
                'content_text': (
                    "💪 Stop letting admin tasks steal your passion! Refiloe gives you back time to do what you love - "
                    "training clients and changing lives. #TrainerLife #FitnessMotivation #WorkSmarter"
                )
            },
            {
                'theme': 'client_success',
                'script': (
                    "Want to know the secret of successful trainers? "
                    "They don't work harder, they work smarter. "
                    "While others juggle WhatsApp messages at midnight, they're sleeping soundly. "
                    "Their secret weapon? Automated systems that run their business 24/7. "
                    "Refiloe manages bookings, sends reminders, and processes payments even while you sleep. "
                    "Join hundreds of South African trainers who've already made the switch!"
                ),
                'content_text': (
                    "📱 Join 100+ SA trainers who've automated their business with Refiloe. "
                    "Handle bookings, payments & client management on autopilot! 🇿🇦 "
                    "#PersonalTrainerSA #BusinessAutomation"
                )
            }
        ]

        content_lookup = {option['theme']: option for option in content_options}

        def resolve_content(value):
            if not value:
                return None
            if isinstance(value, str):
                if value.lower() == 'random':
                    return None
                return content_lookup.get(value)
            if isinstance(value, dict):
                theme_value = value.get('theme')
                script_value = value.get('script')
                content_text_value = value.get('content_text')

                if script_value:
                    return {
                        'theme': theme_value or 'custom',
                        'script': script_value,
                        'content_text': content_text_value or script_value
                    }

                if theme_value:
                    return content_lookup.get(theme_value)

            return None

        selected_content = resolve_content(data.get('content'))

        if not selected_content and data.get('theme'):
            selected_content = resolve_content(data.get('theme'))

        if not selected_content:
            selected_content = random.choice(content_options)
        else:
            selected_content = dict(selected_content)

        custom_theme = data.get('content_theme')
        custom_script = data.get('script')
        custom_content_text = data.get('content_text')

        if custom_theme:
            selected_content['theme'] = custom_theme
        if custom_script:
            selected_content['script'] = custom_script
        if custom_content_text:
            selected_content['content_text'] = custom_content_text

        script_text = (selected_content.get('script') or '').strip()
        content_text = (selected_content.get('content_text') or '').strip()
        theme = selected_content.get('theme', 'custom')

        if not script_text:
            return jsonify({'success': False, 'error': 'Script content is required'}), 400

        if not content_text:
            content_text = script_text

        voice_id = data.get('voice_id') or os.getenv('HEYGEN_DEFAULT_VOICE_ID', '1bd001e7e50f421d891986aad5158bc8')

        # Get avatar ID based on content theme, with fallback to default
        from social_media.config.avatar_ids import get_avatar_id, DEFAULT_AVATAR_ID
        content_theme = data.get('content_theme') or theme
        avatar_id = data.get('avatar_id') or os.getenv('DEFAULT_PHOTO_AVATAR_ID') or get_avatar_id(content_theme)

        log_info(f"Using avatar_id: {avatar_id} for content_theme: {content_theme}")

        # Get look information for source_image_url
        look_image_url = None
        try:
            from social_media.avatar_mapping import get_avatar_and_look_for_content
            _, look_info = get_avatar_and_look_for_content(
                content_text=content_text,
                content_type=theme
            )
            if look_info:
                look_image_url = look_info.get('preview_url') or look_info.get('image_url')
                log_info(f"Retrieved look image URL for source_image_url: {look_image_url[:50] if look_image_url else 'None'}...")
        except Exception as e:
            log_warning(f"Could not retrieve look information: {e}")

        result = video_gen.generate_avatar_video(
            script_text=script_text,
            avatar_id=avatar_id,
            voice_id=voice_id,
            style=data.get('style', 'educational'),
            background_music=data.get('background_music', True),
            metadata={
                'purpose': 'marketing_video',
                'theme': theme,
                'source': 'api.generate_real_video',
            },
            content_text=content_text,
            content_type=theme
        )

        if not result or not result.get('video_url'):
            return jsonify({
                'success': False,
                'error': 'Video generation failed'
            }), 500

        scheduled_time = datetime.now(SA_TZ) + timedelta(hours=2)

        # Get or generate reel_title for Facebook Reels
        reel_title = (
            selected_content.get('reel_title') or
            data.get('reel_title') or
            data.get('title') or
            f"POV: You just discovered this {theme.replace('_', ' ')} hack..."
        )

        # Ensure reel_title is within Facebook's 255 character limit
        if len(reel_title) > 255:
            reel_title = reel_title[:252] + '...'

        # Generate custom thumbnail with reel title overlay
        custom_thumbnail_path = None
        try:
            from social_media.thumbnail_generator import ThumbnailGenerator

            source_image_url = result.get('thumbnail_url')
            if source_image_url and reel_title:
                log_info(f"Generating custom thumbnail for reel: {reel_title}")
                thumbnail_gen = ThumbnailGenerator()
                thumbnail_result = thumbnail_gen.generate_thumbnail(
                    image_url=source_image_url,
                    title_text=reel_title
                )

                if thumbnail_result.get('success'):
                    custom_thumbnail_path = thumbnail_result.get('thumbnail_path')
                    log_info(f"Custom thumbnail generated: {custom_thumbnail_path}")
                else:
                    log_warning(f"Thumbnail generation failed: {thumbnail_result.get('error')}")
        except Exception as e:
            log_error(f"Error generating custom thumbnail: {str(e)}")

        post_data = {
            'post_type': 'video',
            'platform': 'facebook',
            'status': 'pending_approval',
            'scheduled_time': scheduled_time.isoformat(),
            'video_url': result.get('video_url'),
            'source_image_url': look_image_url,  # HeyGen avatar source image (from look)
            'thumbnail_url': custom_thumbnail_path or result.get('thumbnail_url'),  # Use custom thumbnail if available
            'video_duration': int(result.get('duration') or 0),
            'video_type': 'marketing_video',
            'video_style': data.get('style', 'educational'),
            'content_text': content_text,
            'content_theme': theme,
            'title': reel_title,  # Save reel_title as title field for backwards compatibility
            'reel_title': reel_title,  # Save reel_title to the reel_title database field
            'has_captions': True,
            'completion_rate': 0,
            'avg_watch_time': 0
        }

        post_id = db.save_post(post_data)

        if not post_id:
            return jsonify({
                'success': False,
                'error': 'Failed to save post to database',
                'video_url': result.get('video_url')
            }), 500

        log_info(f"Marketing video created successfully: {post_id}")

        return jsonify({
            'success': True,
            'post_id': post_id,
            'video_url': result.get('video_url'),
            'thumbnail_url': result.get('thumbnail_url'),
            'theme': theme,
            'message': f'Video created! Review at /approval/view/{post_id}',
            'approval_url': f'/approval/view/{post_id}'
        }), 200

    except Exception as e:
        log_error(f"Error generating marketing video: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/generate-video-form')
def generate_video_form():
    """HTML form for generating marketing videos"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Generate Marketing Video</title>
        <style>
            body { 
                font-family: Arial; 
                max-width: 800px; 
                margin: 50px auto; 
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #333; }
            .theme-buttons {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }
            button {
                background: #4CAF50;
                color: white;
                padding: 15px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                transition: all 0.3s;
            }
            button:hover {
                background: #45a049;
                transform: translateY(-2px);
            }
            button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            #result {
                margin-top: 20px;
                padding: 20px;
                background: #f0f0f0;
                border-radius: 5px;
                min-height: 100px;
            }
            .success {
                background: #d4edda;
                border: 1px solid #c3e6cb;
                color: #155724;
            }
            .error {
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                color: #721c24;
            }
            .video-preview {
                margin-top: 20px;
            }
            video {
                width: 100%;
                max-width: 600px;
                border-radius: 5px;
            }
            a {
                color: #4CAF50;
                text-decoration: none;
                font-weight: bold;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Generate Refiloe Marketing Video</h1>
            <p>Choose a content theme to generate a professional marketing video with Refiloe avatar:</p>
            
            <div class="theme-buttons">
                <button onclick="generateVideo('admin_tips')">
                    💼 Admin Tips<br>
                    <small>Save time on paperwork</small>
                </button>
                <button onclick="generateVideo('motivation')">
                    💪 Trainer Motivation<br>
                    <small>Focus on what matters</small>
                </button>
                <button onclick="generateVideo('client_success')">
                    ⭐ Success Stories<br>
                    <small>Work smarter, not harder</small>
                </button>
                <button onclick="generateVideo('random')">
                    🎲 Random Theme<br>
                    <small>Surprise me!</small>
                </button>
            </div>
            
            <div id="result"></div>
        </div>
        
        <script>
        async function generateVideo(theme) {
            const resultDiv = document.getElementById("result");
            resultDiv.className = "";
            resultDiv.innerHTML = "⏳ Generating video... This may take 30-60 seconds...";
            
            document.querySelectorAll("button").forEach(btn => btn.disabled = true);
            
            try {
                const response = await fetch("/api/generate-real-video", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(
                        theme === "random" 
                            ? {} 
                            : { content: { theme } }
                    )
                });
                
                const data = await response.json();
                
                if (data.success) {
                    resultDiv.className = "success";
                    resultDiv.innerHTML = `
                        <h3>✅ Video Generated Successfully!</h3>
                        <p><strong>Theme:</strong> ${data.theme}</p>
                        <p><strong>Post ID:</strong> ${data.post_id}</p>
                        <div class="video-preview">
                            <video controls>
                                <source src="${data.video_url}" type="video/mp4">
                                Your browser does not support video playback.
                            </video>
                        </div>
                        <p>
                            <a href="/approval/view/${data.post_id}" target="_blank">
                                📝 Review and Approve This Video
                            </a>
                        </p>
                        <p>
                            <a href="/approval/pending" target="_blank">
                                📋 View All Pending Posts
                            </a>
                        </p>
                    `;
                } else {
                    throw new Error(data.error || "Video generation failed");
                }
            } catch (error) {
                resultDiv.className = "error";
                resultDiv.innerHTML = `
                    <h3>❌ Error</h3>
                    <p>${error.message}</p>
                `;
            } finally {
                document.querySelectorAll("button").forEach(btn => btn.disabled = false);
            }
        }
        </script>
    </body>
    </html>
    '''
    return html


@app.route('/api/dashboard/posts/<post_id>/reset-to-approved', methods=['POST'])
def reset_to_approved(post_id):
    """Reset post to approved status for media regeneration"""
    try:
        log_info(f"📥 Request: Reset post {post_id} to approved status")

        # Get the post to determine what type of media to clear
        post = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not post.data or len(post.data) == 0:
            return jsonify({'error': 'Post not found'}), 404

        post_data = post.data[0]
        post_type = post_data.get('post_type')

        # Build update dict based on post type
        update_data = {
            'status': 'approved',
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        # Clear media URLs based on post type
        if post_type == 'video':
            update_data['video_url'] = None
            update_data['video_id'] = None
            log_info(f"Clearing video_url and video_id for post {post_id}")
        elif post_type == 'image':
            update_data['image_url'] = None
            log_info(f"Clearing image_url for post {post_id}")
        elif post_type == 'carousel':
            # NOTE: We do NOT clear carousel_image_urls during reset
            # This preserves existing slides when changing looks or regenerating individual slides
            # carousel_image_urls should only be cleared when explicitly regenerating ALL slides
            log_info(f"Preserving carousel_image_urls for post {post_id} during status reset")

        # Update the post
        result = supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

        log_info(f"✅ Post {post_id} reset to approved status")

        return jsonify({
            'message': 'Post reset to approved status',
            'post_id': post_id,
            'cleared_fields': list(update_data.keys())
        }), 200

    except Exception as e:
        log_error(f"❌ Error resetting post {post_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


app.register_blueprint(approval_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(admin_bp)


# ------------------------------------------------------------------------------
# Scheduler lifecycle hooks
# ------------------------------------------------------------------------------
if hasattr(app, "before_serving"):
    @app.before_serving
    def _ensure_scheduler_before_serving():
        start_scheduler()
else:
    @app.before_request
    def _ensure_scheduler_before_first_request():
        """Start scheduler on first request (Flask 2.3+ compatible)"""
        global _scheduler_initialized
        if not _scheduler_initialized:
            _scheduler_initialized = True
            start_scheduler()

atexit.register(stop_scheduler)


@app.route('/test-video-form')
def test_video_form():
    """Enhanced HTML form for testing video generation with avatar selection and look generation"""
    # Get avatar_id from query parameters if provided
    avatar_id_param = request.args.get('avatar_id', '')

    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Video Generation</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                margin-bottom: 30px;
            }
            h2 {
                color: #444;
                font-size: 18px;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 2px solid #4CAF50;
            }
            .form-section {
                margin-bottom: 30px;
                padding: 20px;
                background: #fafafa;
                border-radius: 6px;
                border: 1px solid #eee;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                color: #555;
            }
            input, select, textarea {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                box-sizing: border-box;
                font-size: 14px;
            }
            textarea {
                resize: vertical;
                min-height: 80px;
            }
            button {
                background: #4CAF50;
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
                width: 100%;
                margin-top: 10px;
            }
            button:hover {
                background: #45a049;
            }
            button:disabled {
                background: #cccccc;
                cursor: not-allowed;
            }
            #result {
                margin-top: 20px;
                padding: 15px;
                background: #f0f0f0;
                border-radius: 4px;
                display: none;
            }
            #result.show {
                display: block;
            }
            .help-text {
                font-size: 12px;
                color: #777;
                margin-top: 5px;
            }
            /* Collapsible section styles */
            .collapsible-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                cursor: pointer;
                padding: 10px 0;
            }
            .collapsible-header h2 {
                margin: 0;
                border: none;
                padding: 0;
            }
            .collapsible-toggle {
                font-size: 20px;
                color: #4CAF50;
                transition: transform 0.3s;
            }
            .collapsible-toggle.open {
                transform: rotate(180deg);
            }
            .collapsible-content {
                display: none;
                padding-top: 15px;
            }
            .collapsible-content.open {
                display: block;
            }
            /* Radio button styles */
            .radio-group {
                display: flex;
                gap: 20px;
                margin-bottom: 20px;
            }
            .radio-option {
                display: flex;
                align-items: center;
                padding: 12px 20px;
                border: 2px solid #ddd;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s;
                flex: 1;
            }
            .radio-option:hover {
                border-color: #4CAF50;
            }
            .radio-option.selected {
                border-color: #4CAF50;
                background: #e8f5e9;
            }
            .radio-option input[type="radio"] {
                width: auto;
                margin-right: 10px;
            }
            .radio-option label {
                margin: 0;
                cursor: pointer;
            }
            /* Conditional fields */
            .conditional-fields {
                display: none;
                margin-top: 15px;
                padding: 15px;
                background: #fff;
                border-radius: 4px;
                border: 1px solid #e0e0e0;
            }
            .conditional-fields.show {
                display: block;
            }
            /* Custom look fields */
            .custom-look-fields {
                display: none;
                margin-top: 15px;
                padding: 15px;
                background: #f9f9f9;
                border-radius: 4px;
                border: 1px dashed #ccc;
            }
            .custom-look-fields.show {
                display: block;
            }
            /* Progress indicator styles */
            .progress-step {
                display: flex;
                align-items: center;
                padding: 8px 0;
                color: #666;
            }
            .progress-step.active {
                color: #1976D2;
                font-weight: bold;
            }
            .progress-step.complete {
                color: #4CAF50;
            }
            .progress-step .icon {
                margin-right: 10px;
                font-size: 16px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Test Video Generation</h1>

            <!-- SECTION 1: Avatar Look Generation -->
            <div class="form-section">
                <div class="collapsible-header" onclick="toggleCollapsible(this)">
                    <h2>🎨 Generate New Avatar Look (Optional)</h2>
                    <span class="collapsible-toggle">▼</span>
                </div>
                <div class="collapsible-content">
                    <div class="radio-group">
                        <div class="radio-option selected" onclick="selectAvatarOption('existing')">
                            <input type="radio" name="avatar_option" id="use_existing" value="existing" checked>
                            <label for="use_existing">Use existing avatar</label>
                        </div>
                        <div class="radio-option" onclick="selectAvatarOption('generate')">
                            <input type="radio" name="avatar_option" id="generate_new" value="generate">
                            <label for="generate_new">Generate new look</label>
                        </div>
                    </div>

                    <!-- Look Generation Fields (shown when "Generate new look" is selected) -->
                    <div id="look_generation_fields" class="conditional-fields">
                        <div class="form-group">
                            <label for="look_type">Look Type:</label>
                            <select id="look_type" onchange="toggleCustomLookFields()">
                                <option value="gym_trainer">Gym Trainer</option>
                                <option value="office_professional">Office Professional</option>
                                <option value="outdoor_wellness">Outdoor Wellness</option>
                                <option value="nutrition_expert">Nutrition Expert</option>
                                <option value="yoga_instructor">Yoga Instructor</option>
                                <option value="motivational_speaker">Motivational Speaker</option>
                                <option value="home_workout">Home Workout</option>
                                <option value="podcast_host">Podcast Host</option>
                                <option value="retreat_leader">Retreat Leader</option>
                                <option value="studio_portrait">Studio Portrait</option>
                                <option value="custom">Custom (specify details below)</option>
                            </select>
                            <div class="help-text">Select a predefined look or choose 'custom' to specify details</div>
                        </div>

                        <!-- Custom Look Details (shown only when "custom" is selected) -->
                        <div id="custom_look_fields" class="custom-look-fields">
                            <div class="form-group">
                                <label for="custom_outfit">Outfit:</label>
                                <textarea id="custom_outfit" placeholder="e.g., Bold purple athleisure matching set with white sneakers"></textarea>
                                <div class="help-text">Describe the clothing, colors, and accessories</div>
                            </div>

                            <div class="form-group">
                                <label for="custom_environment">Environment:</label>
                                <textarea id="custom_environment" placeholder="e.g., Modern gym with large windows, city skyline visible, motivational quotes on walls"></textarea>
                                <div class="help-text">Describe the setting and background</div>
                            </div>

                            <div class="form-group">
                                <label for="custom_pose">Pose:</label>
                                <input type="text" id="custom_pose" placeholder="e.g., Standing confidently with shoulders back, arms crossed">
                                <div class="help-text">Describe body language and positioning</div>
                            </div>

                            <div class="form-group">
                                <label for="custom_mood">Mood:</label>
                                <select id="custom_mood">
                                    <option value="confident">Confident</option>
                                    <option value="warm">Warm</option>
                                    <option value="energetic">Energetic</option>
                                    <option value="peaceful">Peaceful</option>
                                    <option value="professional">Professional</option>
                                    <option value="inspiring">Inspiring</option>
                                    <option value="conversational">Conversational</option>
                                    <option value="focused">Focused</option>
                                </select>
                                <div class="help-text">Select the emotional tone/expression</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- SECTION 2: Video Script -->
            <div class="form-section">
                <h2>📝 Video Script</h2>

                <div class="form-group">
                    <label for="script">Script Text:</label>
                    <textarea id="script" placeholder="Enter your video script...">Hello from Refiloe! This is a test video to verify our HeyGen integration is working perfectly.</textarea>
                    <div class="help-text">The text that will be spoken in the video</div>
                </div>

                <div class="form-group">
                    <label for="motion_prompt">Custom Motion Prompt (Optional):</label>
                    <textarea
                        id="motion_prompt"
                        rows="2"
                        placeholder="e.g., 'waves enthusiastically' or 'gestures with open hands' or leave empty for automatic gestures"
                    ></textarea>
                    <div class="help-text">
                        Describe specific gestures or movements. Leave empty for Avatar IV to automatically generate natural gestures based on the script.
                    </div>
                </div>

                <div class="form-group">
                    <label for="content_theme">Content Theme:</label>
                    <select id="content_theme">
                        <option value="">-- Auto-detect from script --</option>
                        <option value="professional">Professional</option>
                        <option value="casual">Casual/Friendly</option>
                        <option value="fitness">Fitness/Workout</option>
                        <option value="success">Success Story</option>
                        <option value="educational">Educational</option>
                        <option value="motivational">Motivational</option>
                        <option value="community">Community</option>
                        <option value="announcement">Announcement</option>
                    </select>
                    <div class="help-text">Select a theme to automatically choose the appropriate avatar</div>
                </div>

                <div class="form-group">
                    <label for="voice_id">Voice ID (Optional):</label>
                    <input type="text" id="voice_id" placeholder="Leave empty for default voice">
                    <div class="help-text">Optional: Specify a custom HeyGen voice ID</div>
                </div>
            </div>

            <!-- SECTION 3: Avatar Selection (shown only when "Use existing avatar" is selected) -->
            <div id="existing_avatar_section" class="form-section">
                <h2>👤 Avatar Selection</h2>

                <div class="form-group">
                    <label for="avatar_id">Avatar ID (Optional):</label>
                    <input type="text" id="avatar_id" placeholder="e.g., 110f75a397604454ba6f822c68f29949" value="AVATAR_ID_PLACEHOLDER">
                    <div class="help-text">Leave empty to use theme-based selection, or enter a specific HeyGen avatar ID</div>
                </div>
            </div>

            <button onclick="previewPrompt()" id="previewBtn" style="background: #2196F3; display: none; margin-bottom: 10px;">👁️ Preview Prompt</button>
            <button onclick="generateVideo()" id="generateBtn">Generate Video</button>

            <div id="result"></div>
        </div>

        <!-- Modal for Preview -->
        <div id="previewModal" style="display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5);">
            <div style="background-color: white; margin: 10% auto; padding: 30px; border-radius: 8px; max-width: 700px; max-height: 70vh; overflow-y: auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h2 style="margin: 0; color: #333;">🎨 Avatar Look Preview</h2>
                    <button onclick="closePreviewModal()" style="background: #f44336; padding: 8px 16px; cursor: pointer;">Close</button>
                </div>
                <div id="previewContent"></div>
            </div>
        </div>

        <script>
        // Toggle collapsible sections
        function toggleCollapsible(header) {
            const content = header.nextElementSibling;
            const toggle = header.querySelector('.collapsible-toggle');
            content.classList.toggle('open');
            toggle.classList.toggle('open');
        }

        // Select avatar option (existing vs generate new)
        function selectAvatarOption(option) {
            // Update radio buttons
            document.querySelectorAll('.radio-option').forEach(el => el.classList.remove('selected'));

            if (option === 'existing') {
                document.getElementById('use_existing').checked = true;
                document.querySelector('.radio-option:first-child').classList.add('selected');
                document.getElementById('look_generation_fields').classList.remove('show');
                document.getElementById('existing_avatar_section').style.display = 'block';
                document.getElementById('previewBtn').style.display = 'none';
            } else {
                document.getElementById('generate_new').checked = true;
                document.querySelector('.radio-option:last-child').classList.add('selected');
                document.getElementById('look_generation_fields').classList.add('show');
                document.getElementById('existing_avatar_section').style.display = 'none';
                document.getElementById('previewBtn').style.display = 'block';
            }
        }

        // Toggle custom look fields based on look_type selection
        function toggleCustomLookFields() {
            const lookType = document.getElementById('look_type').value;
            const customFields = document.getElementById('custom_look_fields');

            if (lookType === 'custom') {
                customFields.classList.add('show');
            } else {
                customFields.classList.remove('show');
            }
        }

        // Preview prompt function
        async function previewPrompt() {
            const previewBtn = document.getElementById('previewBtn');
            const previewContent = document.getElementById('previewContent');

            previewBtn.disabled = true;
            previewContent.innerHTML = '<p>⏳ Loading preview...</p>';
            document.getElementById('previewModal').style.display = 'block';

            try {
                const lookType = document.getElementById('look_type').value;
                const lookPayload = {};

                if (lookType === 'custom') {
                    // Get custom look details
                    const outfit = document.getElementById('custom_outfit').value.trim();
                    const environment = document.getElementById('custom_environment').value.trim();
                    const pose = document.getElementById('custom_pose').value.trim();
                    const mood = document.getElementById('custom_mood').value;

                    if (outfit) lookPayload.outfit = outfit;
                    if (environment) lookPayload.environment = environment;
                    if (pose) lookPayload.pose = pose;
                    if (mood) lookPayload.mood = mood;
                    lookPayload.look_type = 'custom';
                } else {
                    lookPayload.look_type = lookType;
                }

                // Call the preview-look API
                const response = await fetch('/api/preview-look', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(lookPayload)
                });

                const data = await response.json();

                if (!response.ok || !data.success) {
                    let errorHtml = '<h3 style="color: #dc3545;">❌ Validation Errors</h3>';
                    if (data.errors && data.errors.length > 0) {
                        errorHtml += '<ul style="color: #721c24; background: #f8d7da; padding: 15px; border-radius: 4px;">';
                        data.errors.forEach(error => {
                            errorHtml += `<li>${error}</li>`;
                        });
                        errorHtml += '</ul>';
                    } else {
                        errorHtml += `<p style="color: #721c24;">${data.error || 'Unknown error'}</p>`;
                    }
                    previewContent.innerHTML = errorHtml;
                    return;
                }

                // Display the preview
                let previewHtml = `
                    <div style="margin-bottom: 20px;">
                        <h3 style="color: #4CAF50; margin-bottom: 10px;">✅ Prompt Ready for Generation</h3>
                        <p style="color: #666; margin-bottom: 15px;">This is what will be sent to HeyGen to create your avatar look:</p>
                    </div>

                    <div style="background: #f5f5f5; padding: 20px; border-radius: 6px; border-left: 4px solid #2196F3; margin-bottom: 20px;">
                        <h4 style="margin: 0 0 10px 0; color: #333;">Full Prompt:</h4>
                        <p style="font-family: monospace; white-space: pre-wrap; line-height: 1.6; color: #222;">${data.prompt_preview}</p>
                    </div>

                    <div style="background: #e3f2fd; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                        <h4 style="margin: 0 0 10px 0; color: #1976D2;">⏱️ Estimated Generation Time:</h4>
                        <p style="margin: 0; font-size: 16px; font-weight: bold; color: #1565C0;">${data.estimated_time}</p>
                    </div>

                    <div style="background: #fafafa; padding: 15px; border-radius: 6px;">
                        <h4 style="margin: 0 0 15px 0; color: #333;">📋 Prompt Components:</h4>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 8px; font-weight: bold; color: #555;">Look Type:</td>
                                <td style="padding: 8px;">${data.look_type}</td>
                            </tr>
                            ${data.components.outfit ? `
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 8px; font-weight: bold; color: #555;">Outfit:</td>
                                <td style="padding: 8px;">${data.components.outfit}</td>
                            </tr>` : ''}
                            ${data.components.environment ? `
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 8px; font-weight: bold; color: #555;">Environment:</td>
                                <td style="padding: 8px;">${data.components.environment}</td>
                            </tr>` : ''}
                            ${data.components.pose ? `
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 8px; font-weight: bold; color: #555;">Pose:</td>
                                <td style="padding: 8px;">${data.components.pose}</td>
                            </tr>` : ''}
                            ${data.components.mood ? `
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 8px; font-weight: bold; color: #555;">Mood:</td>
                                <td style="padding: 8px;">${data.components.mood}</td>
                            </tr>` : ''}
                            <tr>
                                <td style="padding: 8px; font-weight: bold; color: #555;">Prompt Length:</td>
                                <td style="padding: 8px;">${data.prompt_length} characters</td>
                            </tr>
                        </table>
                    </div>

                    <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 6px; border-left: 4px solid #ffc107;">
                        <p style="margin: 0; color: #856404;">
                            <strong>💡 Tip:</strong> Review the prompt above. If you're happy with it, close this dialog and click "Generate Video" to create your avatar look!
                        </p>
                    </div>
                `;

                previewContent.innerHTML = previewHtml;

            } catch (error) {
                previewContent.innerHTML = `
                    <h3 style="color: #dc3545;">❌ Error</h3>
                    <p style="color: #721c24;">${error.message}</p>
                `;
            } finally {
                previewBtn.disabled = false;
            }
        }

        // Close preview modal
        function closePreviewModal() {
            document.getElementById('previewModal').style.display = 'none';
        }

        // Update progress display
        function updateProgress(steps) {
            let html = '<div class="progress-steps">';
            steps.forEach(step => {
                let iconClass = '';
                let icon = '○';
                if (step.status === 'active') {
                    icon = '⏳';
                    iconClass = 'active';
                } else if (step.status === 'complete') {
                    icon = '✓';
                    iconClass = 'complete';
                }
                html += `<div class="progress-step ${iconClass}"><span class="icon">${icon}</span>${step.text}</div>`;
            });
            html += '</div>';
            return html;
        }

        // Main video generation function - COMBINED REQUEST VERSION
        // Sends a single request with generate_look=true to enable Avatar IV with gestures
        async function generateVideo() {
            const resultDiv = document.getElementById('result');
            const generateBtn = document.getElementById('generateBtn');

            resultDiv.className = 'show';
            generateBtn.disabled = true;

            const useGenerateLook = document.getElementById('generate_new').checked;

            try {
                const script = document.getElementById('script').value;
                const voiceId = document.getElementById('voice_id').value;
                const motionPrompt = document.getElementById('motion_prompt').value.trim();

                const payload = {
                    script: script
                };

                if (voiceId) {
                    payload.voice_id = voiceId;
                }

                if (motionPrompt) {
                    payload.motion_prompt = motionPrompt;
                }

                if (useGenerateLook) {
                    // COMBINED REQUEST: Generate look + video together
                    // This ensures Avatar IV is used with gestures!
                    resultDiv.innerHTML = updateProgress([
                        { text: 'Generating custom avatar look and video... (this may take 5-8 minutes)', status: 'active' }
                    ]);

                    const lookType = document.getElementById('look_type').value;

                    // Add generate_look flag for combined processing
                    payload.generate_look = true;

                    if (lookType === 'custom') {
                        // Custom look parameters
                        const outfit = document.getElementById('custom_outfit').value.trim();
                        const environment = document.getElementById('custom_environment').value.trim();
                        const pose = document.getElementById('custom_pose').value.trim();
                        const mood = document.getElementById('custom_mood').value;

                        payload.look_params = {
                            look_type: 'custom'
                        };

                        if (outfit) payload.look_params.outfit = outfit;
                        if (environment) payload.look_params.environment = environment;
                        if (pose) payload.look_params.pose = pose;
                        if (mood) payload.look_params.mood = mood;
                    } else {
                        // Predefined look type
                        payload.look_params = {
                            look_type: lookType
                        };
                    }
                } else {
                    // Using existing avatar
                    resultDiv.innerHTML = updateProgress([
                        { text: 'Generating video... (this may take 3-5 minutes)', status: 'active' }
                    ]);

                    const avatarId = document.getElementById('avatar_id').value.trim();
                    const contentTheme = document.getElementById('content_theme').value;

                    if (avatarId) {
                        payload.avatar_id = avatarId;
                    }
                    if (contentTheme) {
                        payload.content_theme = contentTheme;
                    }
                }

                // SINGLE API CALL - backend handles look generation + video generation together
                const response = await fetch('/api/test-video', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (response.ok) {
                    let successHtml = updateProgress([
                        { text: 'Video created successfully!', status: 'complete' }
                    ]);

                    // Show look generation details if applicable
                    if (data.look_generation && data.look_generation.success) {
                        successHtml += `
                            <div style="margin: 15px 0; padding: 10px; background: #e8f5e9; border-radius: 4px;">
                                <strong>Generated Look:</strong><br>
                                Look ID: ${data.look_generation.look_id}<br>
                                Photo Avatar ID: ${data.look_generation.photo_avatar_id}<br>
                                ${data.look_generation.preview_url ? `<img src="${data.look_generation.preview_url}" style="max-width: 200px; border-radius: 4px; margin-top: 10px;">` : ''}
                            </div>
                        `;
                    }

                    successHtml += `
                        <div style="margin-top: 20px; padding: 15px; background: #f5f5f5; border-radius: 4px;">
                            <strong>Video Details:</strong><br>
                            Video ID: ${data.video_id}<br>
                            Status: ${data.video_generation?.status || 'processing'}<br>
                            API Used: ${data.video_generation?.api_type || 'unknown'}<br>
                            <br>
                            <a href="${data.approval_url}" target="_blank" style="display: inline-block; background: #4CAF50; color: white; padding: 10px 20px; border-radius: 4px; text-decoration: none; font-weight: bold;">
                                Review Video →
                            </a>
                        </div>
                    `;

                    // Also show raw response for debugging
                    successHtml += '<details style="margin-top: 15px;"><summary style="cursor: pointer; color: #666;">Show raw response</summary>';
                    successHtml += '<pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 10px;">' + JSON.stringify(data, null, 2) + '</pre>';
                    successHtml += '</details>';

                    resultDiv.innerHTML = successHtml;
                } else {
                    throw new Error(data.error || 'Failed to generate video');
                }

            } catch (error) {
                resultDiv.innerHTML = `
                    <div class="error" style="background: #ffebee; padding: 15px; border-radius: 4px; border-left: 4px solid #f44336;">
                        <strong style="color: #c62828;">❌ Error</strong><br>
                        <span style="color: #b71c1c;">${error.message}</span>
                    </div>
                `;
            } finally {
                generateBtn.disabled = false;
            }
        }

        // Initialize: Open the collapsible section by default for visibility
        document.addEventListener('DOMContentLoaded', function() {
            // Collapsible starts closed by default
        });
        </script>
    </body>
    </html>
    '''
    # Replace placeholder with actual avatar_id from URL parameter
    html = html.replace('AVATAR_ID_PLACEHOLDER', avatar_id_param)
    return html


@app.route('/api/generate-look', methods=['POST'])
def generate_look():
    """Generate a new avatar look with custom outfit/environment"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        log_info("=== Starting avatar look generation ===")

        # Get request data
        data = request.get_json() or {}

        look_type = data.get('look_type')
        custom_prompt = data.get('custom_prompt')
        outfit = data.get('outfit')
        environment = data.get('environment')
        pose = data.get('pose')
        mood = data.get('mood')
        save_to_db = data.get('save_to_db', True)

        # Build custom prompt from components if provided
        prompt_to_use = None

        if custom_prompt:
            prompt_to_use = custom_prompt
            log_info(f"Using custom prompt: {prompt_to_use[:100]}...")
        elif outfit or environment or pose or mood:
            # Build prompt from individual components
            # Format: "Person wearing [outfit], [pose], in [environment], [mood] expression"
            parts = []
            if outfit:
                parts.append(f"Person wearing {outfit}")
            if pose:
                parts.append(pose)
            if environment:
                parts.append(f"in {environment}")
            if mood:
                parts.append(f"{mood} expression")

            prompt_to_use = ", ".join(parts)
            log_info(f"Built custom prompt from components: {prompt_to_use}")
        elif look_type:
            # Validate look_type
            if look_type not in REFILOE_LOOKS:
                return jsonify({
                    'success': False,
                    'error': f"Invalid look_type '{look_type}'. Available types: {list(REFILOE_LOOKS.keys())}"
                }), 400
            log_info(f"Using predefined look type: {look_type}")
        else:
            return jsonify({
                'success': False,
                'error': 'Either look_type, custom_prompt, or component fields (outfit, environment, pose, mood) required'
            }), 400

        # Initialize LooksGenerator
        looks_gen = LooksGenerator(supabase_client=supabase_client)

        # Generate the look
        log_info(f"Generating look with type={look_type}, has_custom_prompt={prompt_to_use is not None}")

        result = looks_gen.generate_avatar_look(
            look_type=look_type or 'studio_portrait',
            custom_prompt=prompt_to_use,
        )

        # Save to database if requested
        if save_to_db and result:
            record_id = looks_gen.save_look_to_database(result)
            result['database_record_id'] = record_id
            log_info(f"Look saved to database with ID: {record_id}")

        log_info(f"Avatar look generation completed: look_id={result.get('look_id')}, photo_avatar_id={result.get('photo_avatar_id')}")

        return jsonify({
            'success': True,
            'look_id': result.get('look_id'),
            'photo_avatar_id': result.get('photo_avatar_id'),
            'preview_url': result.get('preview_url'),
            'prompt_used': result.get('prompt'),
            'look_type': result.get('look_type'),
            'database_record_id': result.get('database_record_id'),
        }), 200

    except Exception as e:
        log_error(f"Error generating avatar look: {str(e)}")
        import traceback
        log_error(f"Full traceback:\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/preview-look', methods=['POST'])
def preview_look():
    """Preview what a look prompt will generate (dry run)"""
    try:
        log_info("=== Previewing avatar look prompt ===")

        # Get request data
        data = request.get_json() or {}

        look_type = data.get('look_type')
        custom_prompt = data.get('custom_prompt')
        outfit = data.get('outfit')
        environment = data.get('environment')
        pose = data.get('pose')
        mood = data.get('mood')

        # Validation errors
        errors = []

        # Build custom prompt from components if provided
        prompt_to_use = None
        components = {
            'outfit': outfit or '',
            'environment': environment or '',
            'pose': pose or '',
            'mood': mood or ''
        }

        if custom_prompt:
            prompt_to_use = custom_prompt
            log_info(f"Using custom prompt: {prompt_to_use[:100]}...")
        elif outfit or environment or pose or mood:
            # Build prompt from individual components
            # Format: "Person wearing [outfit], [pose], in [environment], [mood] expression"
            parts = []
            if outfit:
                parts.append(f"Person wearing {outfit}")
            if pose:
                parts.append(pose)
            if environment:
                parts.append(f"in {environment}")
            if mood:
                parts.append(f"{mood} expression")

            prompt_to_use = ", ".join(parts)
            log_info(f"Built custom prompt from components: {prompt_to_use}")
        elif look_type:
            # Validate look_type
            if look_type not in REFILOE_LOOKS:
                errors.append(f"Invalid look_type '{look_type}'. Available types: {', '.join(REFILOE_LOOKS.keys())}")
            else:
                look_config = REFILOE_LOOKS[look_type]
                prompt_to_use = look_config.get('prompt')
                components = {
                    'outfit': look_config.get('attire', ''),
                    'environment': look_config.get('environment', ''),
                    'pose': 'As described in prompt',
                    'mood': look_config.get('mood', '')
                }
                log_info(f"Using predefined look type: {look_type}")
        else:
            errors.append('Either look_type, custom_prompt, or component fields (outfit, environment, pose, mood) required')

        # Additional validation
        if prompt_to_use and len(prompt_to_use) < 10:
            errors.append('Prompt is too short (minimum 10 characters)')

        if prompt_to_use and len(prompt_to_use) > 1000:
            errors.append('Prompt is too long (maximum 1000 characters)')

        # Return validation errors if any
        if errors:
            return jsonify({
                'success': False,
                'errors': errors
            }), 400

        # Estimate generation time based on complexity
        # Look generation typically takes 2-3 minutes
        estimated_time = "2-3 minutes"

        log_info(f"Preview complete: {len(prompt_to_use)} characters")

        return jsonify({
            'success': True,
            'prompt_preview': prompt_to_use,
            'estimated_time': estimated_time,
            'components': components,
            'look_type': look_type or 'custom',
            'prompt_length': len(prompt_to_use) if prompt_to_use else 0
        }), 200

    except Exception as e:
        log_error(f"Error previewing avatar look: {str(e)}")
        import traceback
        log_error(f"Full traceback:\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/test/generate-video', methods=['POST'])
@app.route('/api/test-video', methods=['POST'])
def test_generate_video():
    """Manually trigger a test video generation with optional inline look generation"""

    # VERSION MARKER - Updated 2025-11-29 18:58 UTC
    log_info("="*80)
    log_info("CODE VERSION: 2025-11-29-18:58-DEBUG-ENABLED")
    log_info("test_generate_video() STARTED")
    log_info("="*80)

    if not supabase_client:
        return jsonify({'error': 'Supabase not initialized'}), 503

    try:
        log_info("=== Starting test video generation ===")

        data = request.get_json() or {}
        log_info(f"Received request data keys: {list(data.keys())}")

        from social_media.video_generator import VideoGenerator
        import os

        script = data.get('script', 'Hello from Refiloe! This is a test video to verify our HeyGen integration is working perfectly in production.')

        # Look generation parameters
        generate_look = data.get('generate_look', False)
        look_params = data.get('look_params', {})

        # Response structure
        response_data = {
            'success': True,
            'look_generation': None,
            'video_generation': None
        }

        # Variables to hold image data for Avatar IV video generation
        image_url = None
        image_key = None
        look_type = None

        # STEP 1: Generate look if requested
        if generate_look:
            try:
                log_info("=== Starting inline avatar look generation ===")
                log_info(f"Look generation parameters: {look_params}")

                # Initialize LooksGenerator
                looks_gen = LooksGenerator(supabase_client=supabase_client)

                # Extract look parameters
                look_type = look_params.get('look_type', 'studio_portrait')
                custom_prompt = look_params.get('custom_prompt')
                outfit = look_params.get('outfit')
                environment = look_params.get('environment')
                pose = look_params.get('pose')
                mood = look_params.get('mood')

                # Build custom prompt from components if provided
                prompt_to_use = None
                if custom_prompt:
                    prompt_to_use = custom_prompt
                elif outfit or environment or pose or mood:
                    # Build prompt from individual components
                    parts = []
                    if outfit:
                        parts.append(f"Person wearing {outfit}")
                    if pose:
                        parts.append(pose)
                    if environment:
                        parts.append(f"in {environment}")
                    if mood:
                        parts.append(f"{mood} expression")
                    prompt_to_use = ", ".join(parts)

                log_info(f"Generating look with type='{look_type}', has_custom_prompt={prompt_to_use is not None}")

                # Generate the look
                look_result = looks_gen.generate_avatar_look(
                    look_type=look_type,
                    custom_prompt=prompt_to_use,
                    metadata={
                        'purpose': 'inline_video_generation',
                        'triggered_by': 'api.test_video',
                    }
                )

                # DEBUG: See exactly what look_result contains
                log_info("=" * 80)
                log_info("DEBUG: RECEIVED look_result FROM generate_avatar_look()")
                log_info("=" * 80)
                log_info(f"look_result type: {type(look_result)}")
                log_info(f"look_result keys: {look_result.keys() if isinstance(look_result, dict) else 'NOT A DICT'}")
                log_info(f"Full look_result content:\n{json.dumps(look_result, indent=2, default=str)}")
                log_info("=" * 80)

                # Save to database
                record_id = looks_gen.save_look_to_database(look_result)
                look_result['database_record_id'] = record_id

                log_info(f"Look generation completed: look_id={look_result.get('look_id')}, photo_avatar_id={look_result.get('photo_avatar_id')}")

                # Store look generation result
                response_data['look_generation'] = {
                    'success': True,
                    'look_id': look_result.get('look_id'),
                    'photo_avatar_id': look_result.get('photo_avatar_id'),
                    'preview_url': look_result.get('preview_url'),
                    'prompt_used': look_result.get('prompt'),
                    'look_type': look_result.get('look_type'),
                    'database_record_id': record_id
                }

                # Extract image data from look generation for Avatar IV
                log_info("=== Extracting image data from look_result for Avatar IV ===")
                log_info(f"look_result keys: {look_result.keys()}")

                preview_url = look_result.get('preview_url')
                image_urls = look_result.get('image_urls', [])
                image_keys = look_result.get('image_keys', [])

                # Use preview_url directly (it's the most reliable)
                image_url = preview_url

                # Also get image_key if available (Avatar IV can use either)
                image_key = image_keys[0] if image_keys else None

                # DEBUG: Log extracted values
                log_info(f"Extracted preview_url: {preview_url}")
                log_info(f"Extracted image_urls: {image_urls}")
                log_info(f"Extracted image_keys: {image_keys}")
                log_info(f"Final image_url for Avatar IV: {image_url}")
                log_info(f"Final image_key for Avatar IV: {image_key}")

                log_info(f"Will use for Avatar IV:")
                log_info(f"  image_url: {image_url}")
                log_info(f"  image_key: {image_key}")

                if not image_url and not image_key:
                    log_error(f"FAILED: look_result does not contain image_url or image_key")
                    log_error(f"Full look_result: {json.dumps(look_result, indent=2)}")
                    raise ValueError("Avatar IV requires either image_url or image_key")

                look_type = look_result.get('look_type')
                log_info(f"Will use generated image for Avatar IV - look_type: {look_type}")

            except Exception as look_error:
                log_error(f"Look generation failed: {str(look_error)}")
                import traceback
                log_error(f"Look generation traceback:\n{traceback.format_exc()}")

                # Store look generation error
                response_data['look_generation'] = {
                    'success': False,
                    'error': str(look_error)
                }

                # Return early if look generation fails
                response_data['success'] = False
                response_data['error'] = f"Look generation failed: {str(look_error)}"
                return jsonify(response_data), 500

        # STEP 2: Generate video
        try:
            log_info("=== Starting video generation ===")

            # Initialize video generator
            log_info("Initializing VideoGenerator...")
            video_gen = VideoGenerator(
                config_path='social_media/config.yaml',
                supabase_client=supabase_client
            )
            log_info("VideoGenerator initialized successfully")

            # Get voice and content theme
            voice_id = data.get('voice_id') or os.getenv('HEYGEN_DEFAULT_VOICE_ID', '1bd001e7e50f421d891986aad5158bc8')
            content_theme = data.get('content_theme')

            # Get optional motion prompt from request
            motion_prompt = data.get('motion_prompt', '').strip() or None

            # Initialize api_type_used for error handling
            api_type_used = 'unknown'

            # INTELLIGENT API SELECTION
            # Use Avatar IV if we have image_url (from look generation) - supports gestures
            # Use Photo Avatar API if we have avatar_id only - standard video

            use_avatar_iv = bool(image_url or image_key)
            avatar_id_for_photo_avatar = data.get('avatar_id')

            if use_avatar_iv:
                # AVATAR IV PATH (NEW LOOKS WITH GESTURES)
                log_info("Using Avatar IV API (supports gestures and arm movements)")
                log_info(f"Avatar IV parameters - voice: {voice_id}, theme: {content_theme}, motion_prompt: {motion_prompt}")
                log_info(f"Using Avatar IV with image_url: {image_url}")
                log_info(f"Script: {script[:100]}...")

                result = video_gen.generate_avatar_iv_video(
                    script=script,
                    image_url=image_url,
                    image_key=image_key,
                    voice_id=voice_id,
                    custom_motion_prompt=motion_prompt,
                    enhance_motion=True,
                    aspect_ratio="9:16",
                    title=f"Test Video - {look_type or 'custom'}",
                    metadata={
                        'test': True,
                        'purpose': 'production_test',
                        'triggered_by': 'api',
                        'content_theme': content_theme,
                        'generated_look': generate_look,
                        'look_id': response_data.get('look_generation', {}).get('look_id') if generate_look else None,
                        'look_type': look_type,
                        'source': 'test_video_endpoint',
                        'timestamp': datetime.now(pytz.timezone('Africa/Johannesburg')).isoformat()
                    }
                )

                api_type_used = 'avatar_iv'
                log_info("Avatar IV video generation initiated")

            elif avatar_id_for_photo_avatar:
                # PHOTO AVATAR PATH (EXISTING AVATARS - STANDARD)
                log_info("Using Photo Avatar API (existing avatar)")
                log_info(f"Photo Avatar parameters - avatar_id: {avatar_id_for_photo_avatar}, voice: {voice_id}")
                log_info(f"Script: {script[:100]}...")

                result = video_gen.generate_avatar_video(
                    script_text=script,
                    avatar_id=avatar_id_for_photo_avatar,
                    voice_id=voice_id,
                    style='educational',
                    background_music=False,
                    metadata={
                        'test': True,
                        'purpose': 'production_test',
                        'triggered_by': 'api',
                        'content_theme': content_theme,
                        'source': 'test_video_endpoint',
                        'timestamp': datetime.now(pytz.timezone('Africa/Johannesburg')).isoformat()
                    }
                )

                api_type_used = 'photo_avatar'
                log_info("Photo Avatar video generation initiated")

            else:
                raise ValueError("Must provide either: (1) generate_look=true for Avatar IV, or (2) avatar_id for Photo Avatar")

            log_info(f"Video generation result: {result}")

            # Check if we got a video ID (required for both sync and async)
            video_url = result.get('video_url')
            video_id = result.get('video_id')

            # For async generation (Avatar IV, Photo Avatar), we get video_id and status
            # Video URL will be available after processing completes
            if not video_id:
                log_error(f"No video_id in result: {result}")
                raise ValueError('Video generation failed - no video_id returned')

            log_info(f"Video generation successful - video_id: {video_id}, status: {result.get('status', 'unknown')}")

            # Add video_url if available (sync APIs), otherwise it will come via webhook/status check
            if not video_url:
                log_info(f"Video URL not yet available (async generation). Check status with video_id: {video_id}")
                video_url = None  # Explicitly set to None for clarity
            else:
                log_info(f"Video URL obtained: {video_url}")

            # Database save skipped for test endpoint - not needed for Avatar IV testing
            log_info("Test endpoint completed - database save skipped")
            log_info(f"Avatar IV video generation successful!")
            log_info(f"Video ID: {result['video_id']}")
            log_info(f"Check video status in HeyGen dashboard or via status API")

            # Store video generation result
            response_data['video_generation'] = {
                'success': True,
                'message': 'Video generation successful' if video_url else 'Video generation started (processing async)',
                'video_id': video_id,
                'video_url': video_url,
                'thumbnail_url': result.get('thumbnail_url'),
                'duration': result.get('duration'),
                'api_type': api_type_used,
                'image_url': image_url if api_type_used == 'avatar_iv' else None,
                'avatar_id': avatar_id_for_photo_avatar if api_type_used == 'photo_avatar' else None,
                'status': result.get('status', 'unknown')
            }

            log_info("=== Video generation completed successfully ===")

        except Exception as video_error:
            log_error(f"Video generation failed (API: {api_type_used}): {str(video_error)}")
            import traceback
            log_error(f"Video generation traceback:\n{traceback.format_exc()}")

            # Store video generation error
            response_data['video_generation'] = {
                'success': False,
                'error': str(video_error),
                'api_type': api_type_used
            }

            # Determine overall success based on what was requested
            if generate_look:
                # Look succeeded, video failed - partial success
                response_data['success'] = False
                response_data['error'] = f"Video generation failed (look generation succeeded): {str(video_error)}"
                response_data['partial_success'] = True
                return jsonify(response_data), 500
            else:
                # Only video was requested and it failed
                response_data['success'] = False
                response_data['error'] = f"Video generation failed: {str(video_error)}"
                return jsonify(response_data), 500

        # SUCCESS: Build final response
        log_info("=== Test video generation workflow completed successfully ===")

        final_response = {
            'success': True,
            'message': 'Video generated successfully! Check /approval/pending to review.'
        }

        # Include look generation data if it was performed
        if response_data['look_generation']:
            final_response['look_generation'] = response_data['look_generation']

        # Include video generation data
        if response_data['video_generation']:
            final_response['video_generation'] = response_data['video_generation']
            # Maintain backward compatibility with old response format
            final_response['video_id'] = response_data['video_generation']['video_id']
            final_response['video_url'] = response_data['video_generation']['video_url']
            # Database save skipped for test endpoint - no post_id or approval_url

        return jsonify(final_response), 200

    except Exception as e:
        log_error(f"Error in test video generation: {str(e)}")
        import traceback
        error_traceback = traceback.format_exc()
        log_error(f"Full traceback:\n{error_traceback}")
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': error_traceback
        }), 500


@app.route('/looks-gallery')
def looks_gallery():
    """Display all generated avatar looks with preview images"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        # Get filter parameters from query string
        look_type_filter = request.args.get('look_type', '')
        search_query = request.args.get('search', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')

        # Start building query
        query = supabase_client.table('avatar_looks').select('*')

        # Apply look_type filter
        if look_type_filter:
            query = query.eq('look_type', look_type_filter)

        # Apply search filter (search in prompt)
        if search_query:
            query = query.ilike('prompt', f'%{search_query}%')

        # Apply date filters
        if date_from:
            query = query.gte('created_at', date_from)

        # Order by created_at DESC
        query = query.order('created_at', desc=True)

        # Execute query
        result = query.execute()
        looks = result.data if result and hasattr(result, 'data') else []

        # Filter in Python for date_to (since .lt() is not supported)
        if date_to and looks:
            # Add one day to include the entire end date
            date_to_dt = datetime.fromisoformat(date_to) + timedelta(days=1)
            date_to_iso = date_to_dt.isoformat()
            looks = [
                look for look in looks
                if look.get('created_at', '') < date_to_iso
            ]

        # Get unique look types for filter dropdown
        all_looks_result = supabase_client.table('avatar_looks').select('look_type').execute()
        all_looks = all_looks_result.data if all_looks_result and hasattr(all_looks_result, 'data') else []
        look_types = sorted(set([look['look_type'] for look in all_looks if look.get('look_type')]))

        log_info(f"Found {len(looks)} avatar looks (filters: type={look_type_filter}, search={search_query})")

        return render_template(
            'looks_gallery.html',
            looks=looks,
            look_types=look_types,
            current_filters={
                'look_type': look_type_filter,
                'search': search_query,
                'date_from': date_from,
                'date_to': date_to
            }
        )

    except Exception as e:
        log_error(f"Error fetching avatar looks: {str(e)}")
        import traceback
        log_error(f"Full traceback:\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete-look/<look_id>', methods=['POST', 'DELETE'])
def delete_look(look_id):
    """Delete an avatar look"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        # Delete the look from database
        result = supabase_client.table('avatar_looks').delete().eq('id', look_id).execute()

        if result.data:
            log_info(f"Successfully deleted avatar look: {look_id}")
            return jsonify({'success': True, 'message': 'Look deleted successfully'}), 200
        else:
            log_warning(f"No look found with ID: {look_id}")
            return jsonify({'success': False, 'error': 'Look not found'}), 404

    except Exception as e:
        log_error(f"Error deleting avatar look {look_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/looks-compare')
def looks_compare():
    """Compare up to 4 different avatar looks side by side"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        # Get all available looks for selection
        result = supabase_client.table('avatar_looks').select('*').order('created_at', desc=True).execute()
        looks = result.data if result and hasattr(result, 'data') else []

        log_info(f"Looks compare page loaded with {len(looks)} available looks")

        return render_template('looks_compare.html', looks=looks)

    except Exception as e:
        log_error(f"Error loading looks compare page: {str(e)}")
        import traceback
        log_error(f"Full traceback:\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/looks/compare-generate', methods=['POST'])
def compare_generate_videos():
    """Generate test videos for multiple looks with the same script"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        from social_media.video_generator import VideoGenerator

        data = request.get_json() or {}
        look_ids = data.get('look_ids', [])
        script = data.get('script', '')
        content_type = data.get('content_type', 'test')

        if not look_ids or len(look_ids) < 2:
            return jsonify({'error': 'At least 2 looks required for comparison'}), 400

        if len(look_ids) > 4:
            return jsonify({'error': 'Maximum 4 looks allowed for comparison'}), 400

        if not script:
            return jsonify({'error': 'Script is required'}), 400

        # Get look details (SupabaseRestClient doesn't support .in_() filtering)
        result = supabase_client.table('avatar_looks').select('*').execute()
        all_looks = result.data if result and hasattr(result, 'data') else []

        # Filter in Python for the requested look IDs
        looks = [look for look in all_looks if look.get('id') in look_ids]

        if len(looks) != len(look_ids):
            return jsonify({'error': 'One or more looks not found'}), 404

        # Initialize video generator
        video_gen = VideoGenerator('social_media/config.yaml', supabase_client)
        voice_id = os.getenv('HEYGEN_DEFAULT_VOICE_ID', '1bd001e7e50f421d891986aad5158bc8')

        # Generate videos for each look
        results = []
        for look in looks:
            try:
                log_info(f"Generating comparison video for look: {look['look_type']}")

                result = video_gen.generate_avatar_video(
                    script_text=script,
                    avatar_id=look['photo_avatar_id'],
                    voice_id=voice_id,
                    style='educational',
                    background_music=False,  # Disable for comparison consistency
                    metadata={
                        'comparison_test': True,
                        'look_id': look['id'],
                        'look_type': look['look_type'],
                        'content_type': content_type
                    },
                    content_text=script,
                    content_type=content_type
                )

                if result and result.get('video_url'):
                    results.append({
                        'look_id': look['id'],
                        'look_type': look['look_type'],
                        'video_url': result['video_url'],
                        'thumbnail_url': result.get('thumbnail_url'),
                        'duration': result.get('duration'),
                        'success': True
                    })
                    log_info(f"Video generated successfully for {look['look_type']}")
                else:
                    results.append({
                        'look_id': look['id'],
                        'look_type': look['look_type'],
                        'error': 'Video generation failed - no URL returned',
                        'success': False
                    })
                    log_error(f"Video generation failed for {look['look_type']}")

            except Exception as e:
                log_error(f"Error generating video for look {look['id']}: {str(e)}")
                results.append({
                    'look_id': look['id'],
                    'look_type': look['look_type'],
                    'error': str(e),
                    'success': False
                })

        # Check if at least some videos succeeded
        successful_results = [r for r in results if r.get('success')]

        if not successful_results:
            return jsonify({
                'success': False,
                'error': 'All video generations failed',
                'results': results
            }), 500

        log_info(f"Comparison videos generated: {len(successful_results)}/{len(results)} succeeded")

        return jsonify({
            'success': True,
            'results': results,
            'successful_count': len(successful_results),
            'total_count': len(results)
        }), 200

    except Exception as e:
        log_error(f"Error in compare video generation: {str(e)}")
        import traceback
        log_error(f"Full traceback:\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/looks/save-rating', methods=['POST'])
def save_look_rating():
    """Save user rating/preference for a look in a specific content type"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        data = request.get_json() or {}
        look_id = data.get('look_id')
        content_type = data.get('content_type')
        rating = data.get('rating')
        notes = data.get('notes', '')

        if not look_id or not content_type:
            return jsonify({'error': 'look_id and content_type are required'}), 400

        if rating is not None and (not isinstance(rating, (int, float)) or rating < 1 or rating > 5):
            return jsonify({'error': 'rating must be between 1 and 5'}), 400

        # Create or update rating
        record_id = str(uuid.uuid4())
        db_record = {
            'id': record_id,
            'look_id': look_id,
            'content_type': content_type,
            'rating': rating,
            'notes': notes,
            'created_at': datetime.now(SA_TZ).isoformat(),
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        # Check if rating already exists for this look + content_type combo
        existing = supabase_client.table('look_ratings').select('*').eq('look_id', look_id).eq('content_type', content_type).execute()

        if existing.data:
            # Update existing rating (SupabaseRestClient.update() already executes and returns ExecuteResult)
            result = supabase_client.table('look_ratings').update({
                'rating': rating,
                'notes': notes,
                'updated_at': datetime.now(SA_TZ).isoformat()
            }).eq('look_id', look_id).eq('content_type', content_type)

            log_info(f"Updated rating for look {look_id}, content_type {content_type}")
        else:
            # Insert new rating (SupabaseRestClient.insert() already executes and returns ExecuteResult)
            result = supabase_client.table('look_ratings').insert(db_record)
            log_info(f"Created new rating for look {look_id}, content_type {content_type}")

        if result and hasattr(result, 'data'):
            return jsonify({
                'success': True,
                'message': 'Rating saved successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save rating'
            }), 500

    except Exception as e:
        log_error(f"Error saving look rating: {str(e)}")
        import traceback
        log_error(f"Full traceback:\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/looks/get-ratings', methods=['GET'])
def get_look_ratings():
    """Get ratings for looks, optionally filtered by content_type"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        content_type = request.args.get('content_type')

        query = supabase_client.table('look_ratings').select('*')

        if content_type:
            query = query.eq('content_type', content_type)

        result = query.execute()
        ratings = result.data if result and hasattr(result, 'data') else []

        return jsonify({
            'success': True,
            'ratings': ratings
        }), 200

    except Exception as e:
        log_error(f"Error fetching look ratings: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================
# FACEBOOK WEBHOOK ENDPOINTS
# ============================================

@app.route('/webhook/facebook', methods=['GET'])
def facebook_webhook_verify():
    """
    Facebook webhook verification endpoint.
    Facebook will call this endpoint to verify the webhook URL.
    """
    try:
        # Get verification parameters from Facebook
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        # Verify token (should match your configured verify token)
        verify_token = os.getenv('FACEBOOK_VERIFY_TOKEN', 'refiloe_webhook_token_2025')

        if mode == 'subscribe' and token == verify_token:
            log_info("Facebook webhook verified successfully")
            return challenge, 200
        else:
            log_warning("Facebook webhook verification failed")
            return 'Verification failed', 403

    except Exception as e:
        log_error(f"Error in webhook verification: {e}")
        return 'Error', 500


@app.route('/webhook/facebook', methods=['POST'])
def facebook_webhook_receive():
    """
    Facebook webhook receiver endpoint.
    Receives notifications about comments, reactions, and other page events.
    """
    try:
        # Get webhook data
        data = request.get_json()

        if not data:
            return 'No data received', 400

        log_info(f"Received Facebook webhook: {data.get('object', 'unknown')}")

        # Process webhook entries
        if data.get('object') == 'page':
            entries = data.get('entry', [])

            for entry in entries:
                # Handle comment events
                if 'changes' in entry:
                    for change in entry['changes']:
                        if change.get('field') == 'feed':
                            # This is a comment or post event
                            value = change.get('value', {})

                            # Check if it's a comment
                            if value.get('item') == 'comment':
                                # Process comment asynchronously or add to queue
                                log_info(f"New comment detected: {value.get('comment_id')}")
                                # Note: In production, you'd queue this for processing
                                # For now, we'll rely on the scheduled job to pick it up

        return 'EVENT_RECEIVED', 200

    except Exception as e:
        log_error(f"Error processing Facebook webhook: {e}")
        return 'Error processing webhook', 500


@app.route('/api/comments/flagged', methods=['GET'])
def get_flagged_comments():
    """
    Get comments that have been flagged for human review.
    """
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        limit = int(request.args.get('limit', 50))

        result = supabase_client.table('comment_interactions').select(
            '*'
        ).eq('flagged_for_review', True).order(
            'created_at', desc=True
        ).limit(limit).execute()

        comments = result.data if result.data else []

        return jsonify({
            'success': True,
            'count': len(comments),
            'comments': comments
        }), 200

    except Exception as e:
        log_error(f"Error fetching flagged comments: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/comments/stats', methods=['GET'])
def get_comment_stats():
    """
    Get statistics about comment interactions.
    """
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        # Get date range (default: last 7 days)
        days = int(request.args.get('days', 7))
        cutoff_date = (datetime.now(SA_TZ) - timedelta(days=days)).isoformat()

        # Get all comments in date range
        result = supabase_client.table('comment_interactions').select(
            'category', 'replied_at', 'flagged_for_review', 'sentiment_score'
        ).gte('created_at', cutoff_date).execute()

        comments = result.data if result.data else []

        # Calculate statistics
        stats = {
            'total_comments': len(comments),
            'by_category': {},
            'replied_count': 0,
            'flagged_count': 0,
            'avg_sentiment': 0.0
        }

        sentiment_scores = []

        for comment in comments:
            # Count by category
            category = comment.get('category', 'unknown')
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

            # Count replies
            if comment.get('replied_at'):
                stats['replied_count'] += 1

            # Count flagged
            if comment.get('flagged_for_review'):
                stats['flagged_count'] += 1

            # Collect sentiment scores
            if comment.get('sentiment_score') is not None:
                sentiment_scores.append(comment['sentiment_score'])

        # Calculate average sentiment
        if sentiment_scores:
            stats['avg_sentiment'] = round(sum(sentiment_scores) / len(sentiment_scores), 2)

        # Calculate reply rate
        stats['reply_rate'] = round(
            (stats['replied_count'] / stats['total_comments'] * 100) if stats['total_comments'] > 0 else 0,
            1
        )

        return jsonify({
            'success': True,
            'stats': stats,
            'period_days': days
        }), 200

    except Exception as e:
        log_error(f"Error calculating comment stats: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================
# CONTENT DASHBOARD ROUTES
# ============================================

@app.route('/dashboard')
def content_dashboard():
    """Main content management dashboard"""
    return render_template('dashboard.html')


@app.route('/dashboard/post/<post_id>')
def view_post_detail(post_id):
    """View single post details"""
    if not supabase_client:
        return "Database not connected", 503

    try:
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            return "Post not found", 404

        post = result.data[0]

        # Format scheduled time
        if post.get('scheduled_time'):
            try:
                dt = datetime.fromisoformat(post['scheduled_time'].replace('Z', '+00:00'))
                post['scheduled_time_formatted'] = dt.strftime('%a, %b %d at %H:%M')
            except Exception:
                post['scheduled_time_formatted'] = post['scheduled_time']
        else:
            post['scheduled_time_formatted'] = 'Not scheduled'

        # Parse generation_prompt to get video_script, carousel_slides, hashtags
        if post.get('generation_prompt'):
            try:
                metadata = json.loads(post['generation_prompt'])
                post['video_script'] = metadata.get('video_script')
                post['carousel_slides'] = metadata.get('carousel_slides')
                post['hashtags'] = metadata.get('hashtags')
            except Exception:
                pass

        # Parse carousel slides if JSON string
        if post.get('carousel_slides') and isinstance(post['carousel_slides'], str):
            try:
                post['carousel_slides'] = json.loads(post['carousel_slides'])
            except Exception:
                pass

        # Parse hashtags if JSON string
        if post.get('hashtags') and isinstance(post['hashtags'], str):
            try:
                post['hashtags'] = json.loads(post['hashtags'])
            except Exception:
                pass

        return render_template('post_detail.html', post=post)

    except Exception as e:
        log_error(f"Error fetching post {post_id}: {e}")
        return f"Error: {str(e)}", 500


@app.route('/dashboard/pending-scripts')
def pending_scripts_dashboard():
    """Dashboard for videos awaiting manual Avatar IV creation"""
    if not supabase_client:
        return "Database not connected", 503

    try:
        # Query posts where post_type = 'video' AND video_url IS NULL
        # Order by scheduled_time ascending (soonest first)
        result = supabase_client.table('social_posts').select('*').eq('post_type', 'video').is_('video_url', 'null').order('scheduled_time', desc=False).execute()

        pending_posts = []

        for post in result.data if result.data else []:
            # Parse generation_prompt to get video_script and other metadata
            video_script = ''
            word_count = 0
            estimated_duration = 0

            if post.get('generation_prompt'):
                try:
                    metadata = json.loads(post['generation_prompt'])
                    video_script = metadata.get('video_script', '')

                    # Calculate word count and estimated duration
                    if video_script:
                        word_count = len(video_script.split())
                        # Estimate duration: ~150 words per minute for conversational speech
                        estimated_duration = int((word_count / 150) * 60)  # in seconds
                except Exception as e:
                    log_error(f"Error parsing generation_prompt for post {post.get('id')}: {e}")

            # Format scheduled time
            scheduled_formatted = 'Not scheduled'
            if post.get('scheduled_time'):
                try:
                    dt = datetime.fromisoformat(post['scheduled_time'].replace('Z', '+00:00'))
                    scheduled_formatted = dt.strftime('%a, %b %d, %Y at %H:%M')
                except Exception:
                    scheduled_formatted = post['scheduled_time']

            pending_posts.append({
                'id': post.get('id'),
                'title': post.get('title', 'Untitled'),
                'content_theme': post.get('content_theme', 'General'),
                'content_text': post.get('content_text', ''),
                'video_script': video_script,
                'word_count': word_count,
                'estimated_duration': estimated_duration,
                'scheduled_time': post.get('scheduled_time'),
                'scheduled_formatted': scheduled_formatted,
                'status': post.get('status', 'unknown')
            })

        # TODO: Get Avatar IV credit status from HeyGen API
        # For now, showing placeholder values
        avatar_credits = {
            'used': 0,
            'remaining': 'Unknown',
            'total': 'Unknown'
        }

        return render_template(
            'pending_scripts.html',
            pending_posts=pending_posts,
            pending_count=len(pending_posts),
            avatar_credits=avatar_credits
        )

    except Exception as e:
        log_error(f"Error fetching pending scripts: {e}")
        import traceback
        log_error(traceback.format_exc())
        return f"Error: {str(e)}", 500


@app.route('/api/pending-video-posts')
def api_pending_video_posts():
    """API endpoint to get posts awaiting manual video upload"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        # Query posts where post_type = 'video' AND video_url IS NULL
        result = supabase_client.table('social_posts').select('*').eq('post_type', 'video').is_('video_url', 'null').order('scheduled_time', desc=False).execute()

        pending_posts = []
        for post in result.data if result.data else []:
            # Get script preview (first 50 chars)
            script_preview = ''
            if post.get('generation_prompt'):
                try:
                    metadata = json.loads(post['generation_prompt'])
                    video_script = metadata.get('video_script', '')
                    if video_script:
                        script_preview = video_script[:50] + ('...' if len(video_script) > 50 else '')
                except Exception:
                    pass

            pending_posts.append({
                'id': post.get('id'),
                'scheduled_time': post.get('scheduled_time'),
                'content_theme': post.get('content_theme', 'General'),
                'script_preview': script_preview
            })

        return jsonify({
            'success': True,
            'posts': pending_posts,
            'count': len(pending_posts)
        })

    except Exception as e:
        log_error(f"Error fetching pending video posts: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/upload-video', methods=['GET', 'POST'])
def upload_video():
    """Upload manually-created Avatar IV videos"""
    if not supabase_client:
        return "Database not connected", 503

    # Handle GET request - show upload form
    if request.method == 'GET':
        try:
            # Get pending posts (video posts without video_url)
            result = supabase_client.table('social_posts').select('*').eq('post_type', 'video').is_('video_url', 'null').order('scheduled_time', desc=False).execute()

            pending_posts = []
            for post in result.data if result.data else []:
                # Parse generation_prompt to get video_script
                video_script = ''
                if post.get('generation_prompt'):
                    try:
                        metadata = json.loads(post['generation_prompt'])
                        video_script = metadata.get('video_script', '')
                    except Exception:
                        pass

                # Format scheduled time
                scheduled_formatted = 'Not scheduled'
                if post.get('scheduled_time'):
                    try:
                        dt = datetime.fromisoformat(post['scheduled_time'].replace('Z', '+00:00'))
                        scheduled_formatted = dt.strftime('%a, %b %d, %Y at %H:%M')
                    except Exception:
                        scheduled_formatted = post['scheduled_time']

                pending_posts.append({
                    'id': post.get('id'),
                    'content_theme': post.get('content_theme', 'General'),
                    'content_text': post.get('content_text', ''),
                    'video_script': video_script,
                    'scheduled_time': post.get('scheduled_time'),
                    'scheduled_formatted': scheduled_formatted
                })

            return render_template('upload_video.html', pending_posts=pending_posts)

        except Exception as e:
            log_error(f"Error loading upload video page: {e}")
            import traceback
            log_error(traceback.format_exc())
            return f"Error: {str(e)}", 500

    # Handle POST request - process file upload
    if request.method == 'POST':
        try:
            # Get form data
            post_id = request.form.get('post_id')
            video_file = request.files.get('video_file')

            # Validate inputs
            if not post_id:
                return render_template('upload_video.html', pending_posts=[], error='Post ID is required')

            if not video_file:
                return render_template('upload_video.html', pending_posts=[], error='Video file is required')

            # Validate file type
            if not video_file.filename.lower().endswith('.mp4'):
                return render_template('upload_video.html', pending_posts=[], error='Only MP4 files are allowed')

            # Validate file size (100 MB)
            video_file.seek(0, 2)  # Seek to end
            file_size = video_file.tell()
            video_file.seek(0)  # Reset to beginning

            max_size = 100 * 1024 * 1024  # 100 MB
            if file_size > max_size:
                return render_template('upload_video.html', pending_posts=[], error='File size exceeds 100 MB limit')

            # Get post details
            post_result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

            if not post_result.data or len(post_result.data) == 0:
                return render_template('upload_video.html', pending_posts=[], error='Post not found')

            post = post_result.data[0]

            # Upload to Supabase Storage
            from utils.supabase_storage import get_storage_client

            storage_client = get_storage_client()
            if not storage_client:
                return render_template('upload_video.html', pending_posts=[], error='Storage client not available')

            # Create destination path: manual-videos/post_id/video.mp4
            destination_path = f"manual-videos/{post_id}/video.mp4"

            # Save file temporarily
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            video_file.save(temp_file.name)
            temp_file.close()

            try:
                # Upload to Supabase Storage
                success, public_url, error_msg = storage_client.upload_file(
                    bucket='media',
                    file_path=temp_file.name,
                    destination_path=destination_path,
                    content_type='video/mp4'
                )

                # Clean up temp file
                os.unlink(temp_file.name)

                if not success:
                    log_error(f"Failed to upload video to Supabase: {error_msg}")
                    return render_template('upload_video.html', pending_posts=[], error=f'Upload failed: {error_msg}')

                # Update the social_posts record
                update_data = {
                    'video_url': public_url,
                    'status': 'pending_media_approval'
                }

                # Update the post
                update_result = supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

                if not update_result.data:
                    log_error(f"Failed to update post {post_id} in database")
                    return render_template('upload_video.html', pending_posts=[], error='Failed to update post in database')

                log_info(f"✅ Successfully uploaded manual video for post {post_id}")
                log_info(f"   Video URL: {public_url}")

                # Success - redirect to upload page with success message
                return render_template('upload_video.html', pending_posts=[], success=True)

            except Exception as upload_error:
                # Clean up temp file on error
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
                raise upload_error

        except Exception as e:
            log_error(f"Error uploading video: {e}")
            import traceback
            log_error(traceback.format_exc())
            return render_template('upload_video.html', pending_posts=[], error=str(e))


# =============================================================================
# API Helper Functions
# =============================================================================

def api_error_response(error_msg, status_code=500, details=None):
    """Standardized API error response."""
    response = {
        'success': False,
        'error': error_msg,
        'timestamp': datetime.now(SA_TZ).isoformat()
    }
    if details:
        response['details'] = details
    return jsonify(response), status_code


# =============================================================================
# Dashboard API Endpoints
# =============================================================================

@app.route('/api/dashboard/posts', methods=['GET'])
def api_dashboard_posts():
    """API: Get posts for dashboard with optional media type filter.

    Query params:
        media_type: Optional filter - 'video', 'image', 'carousel', 'text_card', or 'all'
    """
    log_info("📥 Request: /api/dashboard/posts")

    # Check Supabase connection
    if not app.config.get('SUPABASE_CONNECTED'):
        log_error("❌ Supabase not connected")
        return api_error_response(
            'Database not connected',
            503,
            {'reason': 'Supabase initialization failed'}
        )

    if not supabase_client:
        log_error("❌ Supabase client is None")
        return api_error_response('Database client not available', 503)

    try:
        # Get media_type filter from query params
        media_type = request.args.get('media_type', 'all')

        # Active statuses to show
        active_statuses = ['pending_approval', 'approved', 'generating', 'pending_media_approval', 'scheduled']

        # Get ALL posts (SupabaseRestClient doesn't support .in_() filtering)
        result = supabase_client.table('social_posts').select('*').execute()

        if result.data:
            # Filter in Python for active statuses
            active_posts = [
                post for post in result.data
                if post.get('status') in active_statuses
            ]

            # Exclude posts that are already scheduled on Facebook (they're in Facebook's scheduler now)
            pre_filter_count = len(active_posts)
            active_posts = [post for post in active_posts if post.get('status') != 'scheduled_on_facebook']
            facebook_scheduled_count = pre_filter_count - len(active_posts)
            if facebook_scheduled_count > 0:
                log_info(f"📅 Excluded {facebook_scheduled_count} posts already scheduled on Facebook")

            # Apply media type filter if not 'all'
            if media_type != 'all':
                active_posts = [
                    post for post in active_posts
                    if post.get('post_type') == media_type
                ]
                log_info(f"📊 Filtered by media_type: {media_type}")

            # Sort by scheduled_time
            active_posts.sort(key=lambda x: x.get('scheduled_time', ''))

            log_info(f"📊 Found {len(active_posts)} active posts (out of {len(result.data)} total)")

            return jsonify({
                'success': True,
                'posts': active_posts,
                'count': len(active_posts)
            })
        else:
            log_info("ℹ️  No posts found")
            return jsonify({
                'success': True,
                'posts': [],
                'count': 0
            })

    except Exception as e:
        log_error(f"❌ Error fetching dashboard posts: {e}")
        log_error(traceback.format_exc())
        return api_error_response(
            str(e),
            500,
            {'traceback': traceback.format_exc()}
        )


@app.route('/api/dashboard/seed-launch', methods=['POST'])
def api_seed_launch_content():
    """API: Generate and save launch content"""
    if not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        from social_media.launch_content import seed_launch_content

        # Get optional start date from request
        start_date = None
        if request.json and request.json.get('start_date'):
            start_date = datetime.fromisoformat(request.json['start_date'])

        post_ids = seed_launch_content(supabase_client, start_date)

        return jsonify({
            'success': True,
            'posts_created': len(post_ids),
            'post_ids': post_ids,
            'message': f'Created {len(post_ids)} launch posts'
        })

    except Exception as e:
        log_error(f"Error seeding launch content: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/approve/<post_id>', methods=['POST'])
def api_approve_post(post_id):
    """API: Approve post content (Stage 1 approval)"""
    log_info(f"📥 Request: /api/dashboard/approve/{post_id}")

    # Validate post_id format (should be UUID)
    try:
        uuid.UUID(post_id)
    except ValueError:
        log_error(f"❌ Invalid post_id format: {post_id}")
        return api_error_response(
            'Invalid post ID format',
            400,
            {'post_id': post_id, 'expected': 'UUID'}
        )

    # Check Supabase connection
    if not app.config.get('SUPABASE_CONNECTED'):
        log_error("❌ Supabase not connected")
        return api_error_response('Database not connected', 503)

    if not supabase_client:
        log_error("❌ Supabase client is None")
        return api_error_response('Database client not available', 503)

    try:
        # Check if post exists first
        log_info(f"🔍 Checking if post {post_id} exists")
        check_result = supabase_client.table('social_posts').select('id, status, platform, content_text, post_type').eq('id', post_id).execute()

        if not check_result.data:
            log_error(f"❌ Post {post_id} not found")
            return api_error_response('Post not found', 404, {'post_id': post_id})

        post_info = check_result.data[0]
        log_info(f"✅ Post found - Status: {post_info.get('status')}, Platform: {post_info.get('platform')}, Type: {post_info.get('post_type')}")

        # For text cards, skip media generation - image already exists
        if post_info.get('post_type') == 'text_card':
            # Update directly to scheduled (image was created during generation)
            new_status = 'scheduled'
            message = 'Text card approved and scheduled! (Image already generated)'
        else:
            # Normal flow for videos/carousels - go to approved first
            new_status = 'approved'
            message = 'Content approved. Generate media next.'

        # Update status
        start_time = datetime.now()
        result = supabase_client.table('social_posts').update({
            'status': new_status,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('id', post_id).execute()

        update_time = (datetime.now() - start_time).total_seconds()

        if result.data:
            log_info(f"✅ Post {post_id} content approved (Stage 1) in {update_time:.2f}s - Status: {new_status}")
            return jsonify({
                'success': True,
                'message': message,
                'post_id': post_id,
                'update_time': update_time,
                'new_status': new_status
            })
        else:
            log_error(f"❌ Failed to update post {post_id}")
            return api_error_response(
                'Failed to update post',
                500,
                {'post_id': post_id}
            )

    except Exception as e:
        log_error(f"❌ Error approving post {post_id}: {e}")
        log_error(traceback.format_exc())
        return api_error_response(
            str(e),
            500,
            {'post_id': post_id, 'traceback': traceback.format_exc()}
        )


@app.route('/api/dashboard/approve-media/<post_id>', methods=['POST'])
def api_approve_media(post_id):
    """API: Approve generated media (Stage 2 approval)"""
    log_info(f"📥 Request: /api/dashboard/approve-media/{post_id}")

    # Validate post_id format (should be UUID)
    try:
        uuid.UUID(post_id)
    except ValueError:
        log_error(f"❌ Invalid post_id format: {post_id}")
        return api_error_response(
            'Invalid post ID format',
            400,
            {'post_id': post_id, 'expected': 'UUID'}
        )

    # Check Supabase connection
    if not app.config.get('SUPABASE_CONNECTED'):
        log_error("❌ Supabase not connected")
        return api_error_response('Database not connected', 503)

    if not supabase_client:
        log_error("❌ Supabase client is None")
        return api_error_response('Database client not available', 503)

    try:
        # Check if post exists and has media
        log_info(f"🔍 Checking if post {post_id} exists and has media")
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            log_error(f"❌ Post {post_id} not found")
            return api_error_response('Post not found', 404, {'post_id': post_id})

        post = result.data[0]
        log_info(f"✅ Post found - Type: {post.get('post_type')}, Status: {post.get('status')}")

        # Verify media exists
        has_media = False
        if post.get('post_type') == 'video' and post.get('video_url'):
            has_media = True
        elif post.get('post_type') == 'image' and (post.get('media_url') or post.get('image_url')):
            has_media = True
        elif post.get('post_type') == 'text_card' and post.get('image_url'):
            has_media = True
        elif post.get('post_type') == 'carousel':
            carousel_urls = post.get('carousel_image_urls')
            if carousel_urls and isinstance(carousel_urls, list) and len(carousel_urls) > 0:
                has_media = True

        if not has_media:
            log_error(f"❌ Post {post_id} has no media generated yet")
            return api_error_response(
                'No media generated yet',
                400,
                {'post_id': post_id, 'post_type': post.get('post_type')}
            )

        # Update status to 'scheduled' (ready for automated posting)
        start_time = datetime.now()
        update_result = supabase_client.table('social_posts').update({
            'status': 'scheduled',
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('id', post_id).execute()

        update_time = (datetime.now() - start_time).total_seconds()

        if update_result.data:
            log_info(f"✅ Post {post_id} media approved (Stage 2) - status set to 'scheduled' in {update_time:.2f}s")

            # Auto-upload carousel posts to Facebook
            if post.get('post_type') == 'carousel':
                log_info(f"🚀 Carousel post detected - auto-uploading to Facebook...")
                try:
                    from social_media.database import SocialMediaDatabase
                    db = SocialMediaDatabase(supabase_client)

                    # Call the existing Facebook upload function
                    facebook_result = _upload_image_to_facebook_scheduler(db, post)

                    if facebook_result.get('success'):
                        facebook_post_id = facebook_result.get('facebook_post_id')
                        log_info(f"✅ Carousel auto-uploaded to Facebook: {facebook_post_id}")

                        # Update status to 'scheduled_on_facebook' and store facebook_post_id
                        supabase_client.table('social_posts').update({
                            'status': 'scheduled_on_facebook',
                            'facebook_post_id': facebook_post_id,
                            'updated_at': datetime.now(SA_TZ).isoformat()
                        }).eq('id', post_id).execute()

                        return jsonify({
                            'success': True,
                            'message': 'Carousel approved and scheduled on Facebook!',
                            'post_id': post_id,
                            'facebook_post_id': facebook_post_id,
                            'status': 'scheduled_on_facebook',
                            'update_time': update_time
                        })
                    else:
                        # Facebook upload failed - keep as 'scheduled' for manual retry
                        error_msg = facebook_result.get('error', 'Unknown error')
                        log_warning(f"⚠️ Facebook auto-upload failed for {post_id}: {error_msg}")
                        log_warning("Post remains as 'scheduled' - can be manually uploaded later")

                        return jsonify({
                            'success': True,
                            'message': f'Media approved! Post scheduled (Facebook upload pending: {error_msg})',
                            'post_id': post_id,
                            'status': 'scheduled',
                            'facebook_upload_error': error_msg,
                            'update_time': update_time
                        })

                except Exception as fb_error:
                    # Log error but don't fail the approval
                    log_error(f"❌ Exception during Facebook auto-upload for {post_id}: {fb_error}")
                    log_error(traceback.format_exc())
                    log_warning("Post remains as 'scheduled' - can be manually uploaded later")

                    return jsonify({
                        'success': True,
                        'message': f'Media approved! Post scheduled (Facebook upload failed: {str(fb_error)})',
                        'post_id': post_id,
                        'status': 'scheduled',
                        'facebook_upload_error': str(fb_error),
                        'update_time': update_time
                    })

            # Non-carousel posts - just return success
            return jsonify({
                'success': True,
                'message': 'Media approved! Post scheduled for publishing.',
                'post_id': post_id,
                'update_time': update_time
            })
        else:
            log_error(f"❌ Failed to update post {post_id}")
            return api_error_response(
                'Failed to update status',
                500,
                {'post_id': post_id}
            )

    except Exception as e:
        log_error(f"❌ Error approving media for post {post_id}: {e}")
        log_error(traceback.format_exc())
        return api_error_response(
            str(e),
            500,
            {'post_id': post_id, 'traceback': traceback.format_exc()}
        )


@app.route('/api/dashboard/reject/<post_id>', methods=['POST'])
def api_reject_post(post_id):
    """API: Reject a post by updating its status to 'rejected'"""
    log_info(f"📥 Request: /api/dashboard/reject/{post_id}")

    # Validate post_id format (should be UUID)
    try:
        uuid.UUID(post_id)
    except ValueError:
        log_error(f"❌ Invalid post_id format: {post_id}")
        return api_error_response(
            'Invalid post ID format',
            400,
            {'post_id': post_id, 'expected': 'UUID'}
        )

    # Check Supabase connection
    if not app.config.get('SUPABASE_CONNECTED'):
        log_error("❌ Supabase not connected")
        return api_error_response('Database not connected', 503)

    if not supabase_client:
        log_error("❌ Supabase client is None")
        return api_error_response('Database client not available', 503)

    try:
        # Get optional rejection reason from request (use get_json with silent=True to avoid Content-Type errors)
        reason = None
        try:
            json_data = request.get_json(silent=True)
            if json_data:
                reason = json_data.get('reason')
                if reason:
                    log_info(f"📝 Rejection reason provided: {reason}")
        except Exception:
            pass  # Ignore JSON parsing errors

        # Check if post exists first
        log_info(f"🔍 Checking if post {post_id} exists")
        check_result = supabase_client.table('social_posts').select('id, status, platform, content_text, post_type').eq('id', post_id).execute()

        if not check_result.data:
            log_error(f"❌ Post {post_id} not found")
            return api_error_response('Post not found', 404, {'post_id': post_id})

        post_info = check_result.data[0]
        log_info(f"✅ Post found - Status: {post_info.get('status')}, Platform: {post_info.get('platform')}, Type: {post_info.get('post_type')}")

        # Prevent rejecting published posts
        if post_info.get('status') == 'published':
            log_error(f"❌ Cannot reject published post {post_id}")
            return api_error_response(
                'Cannot reject a post that has already been published',
                400,
                {'post_id': post_id, 'current_status': 'published'}
            )

        # Update the post status to 'rejected'
        start_time = datetime.now()
        update_data = {'status': 'rejected'}
        if reason:
            update_data['rejection_reason'] = reason

        result = supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

        update_time = (datetime.now() - start_time).total_seconds()

        if result.data:
            log_info(f"✅ Post {post_id} rejected - status updated to 'rejected' in {update_time:.2f}s")
            response_data = {
                'success': True,
                'message': 'Post rejected',
                'post_id': post_id,
                'new_status': 'rejected',
                'update_time': update_time
            }
            if reason:
                response_data['reason'] = reason
            return jsonify(response_data)
        else:
            log_error(f"❌ Failed to reject post {post_id}")
            return api_error_response(
                'Failed to reject post',
                500,
                {'post_id': post_id}
            )

    except Exception as e:
        log_error(f"❌ Error rejecting post {post_id}: {e}")
        log_error(traceback.format_exc())
        return api_error_response(
            str(e),
            500,
            {'post_id': post_id, 'traceback': traceback.format_exc()}
        )


@app.route('/api/dashboard/reschedule/<string:post_id>', methods=['POST'])
def api_reschedule_post(post_id: str):
    """Reschedule a post to a new date/time."""
    log_info(f"📥 Request: /api/dashboard/reschedule/{post_id}")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        import pytz
        from datetime import datetime

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        # Get new scheduled time from request
        data = request.get_json()
        new_scheduled_time = data.get('scheduled_time')

        if not new_scheduled_time:
            return jsonify({'success': False, 'error': 'No scheduled_time provided'}), 400

        # Validate the post exists and is not published
        log_info(f"🔍 Checking if post {post_id} exists")
        result = supabase_client.table('social_posts').select('id, status, scheduled_time').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]

        if post.get('status') == 'published':
            return jsonify({'success': False, 'error': 'Cannot reschedule a published post'}), 400

        # Parse and validate the new time
        try:
            # Handle ISO format from datetime-local input
            if 'T' in new_scheduled_time and '+' not in new_scheduled_time and 'Z' not in new_scheduled_time:
                # Add SAST timezone if not present
                new_dt = datetime.fromisoformat(new_scheduled_time)
                new_dt = SA_TZ.localize(new_dt)
            else:
                new_dt = datetime.fromisoformat(new_scheduled_time.replace('Z', '+00:00'))
                new_dt = new_dt.astimezone(SA_TZ)

            new_scheduled_iso = new_dt.isoformat()
        except Exception as e:
            log_error(f"Failed to parse scheduled_time: {e}")
            return jsonify({'success': False, 'error': f'Invalid date format: {str(e)}'}), 400

        # Update the post
        log_info(f"📅 Rescheduling post {post_id} to {new_scheduled_iso}")
        update_result = supabase_client.table('social_posts').update({
            'scheduled_time': new_scheduled_iso,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('id', post_id).execute()

        if update_result.data:
            log_info(f"✅ Post {post_id} rescheduled to {new_scheduled_iso}")
            return jsonify({
                'success': True,
                'post_id': post_id,
                'new_scheduled_time': new_scheduled_iso,
                'message': f'Post rescheduled to {new_dt.strftime("%b %d, %Y at %H:%M")} SAST'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update post'}), 500

    except Exception as e:
        log_error(f"❌ Reschedule failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/upload-to-facebook/<string:post_id>', methods=['POST'])
def api_upload_to_facebook(post_id: str):
    """Manually upload a scheduled video post to Facebook as a draft."""
    log_info(f"📥 Request: /api/dashboard/upload-to-facebook/{post_id}")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        import pytz
        from datetime import datetime

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        # Fetch the post
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]

        # Check if it's a video post
        if post.get('post_type') != 'video' and not post.get('video_url'):
            return jsonify({'success': False, 'error': 'This is not a video post'}), 400

        # Check if already uploaded to Facebook
        if post.get('facebook_post_id'):
            return jsonify({
                'success': False,
                'error': 'Already uploaded to Facebook',
                'facebook_post_id': post.get('facebook_post_id')
            }), 400

        # Check credentials
        page_access_token = os.getenv('FACEBOOK_PAGE_ACCESS_TOKEN')
        page_id = os.getenv('FACEBOOK_PAGE_ID')

        if not page_access_token or not page_id:
            return jsonify({'success': False, 'error': 'Facebook credentials not configured'}), 500

        video_url = post.get('video_url')
        if not video_url:
            return jsonify({'success': False, 'error': 'No video URL found for this post'}), 400

        log_info(f"📤 Uploading video to Facebook as draft for post {post_id}")

        # Upload to Facebook as draft
        from facebook_poster import FacebookPoster

        fb_poster = FacebookPoster(page_access_token, page_id, supabase_client)

        # Build description
        description = post.get('content_text', '')

        # Calculate scheduled time
        # If the post has a scheduled_time in the future, use that
        # Otherwise, schedule 10 minutes from now as minimum
        import time as time_module
        from datetime import datetime as dt

        scheduled_time = post.get('scheduled_time')
        schedule_timestamp = None

        if scheduled_time:
            try:
                if isinstance(scheduled_time, str):
                    scheduled_dt = dt.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                else:
                    scheduled_dt = scheduled_time

                # Convert to Unix timestamp
                schedule_timestamp = int(scheduled_dt.timestamp())

                # If scheduled time is in the past, schedule 10 mins from now
                current_time = int(time_module.time())
                if schedule_timestamp < current_time + 600:  # Must be at least 10 mins in future
                    schedule_timestamp = current_time + 600
                    log_info(f"Scheduled time was in the past, rescheduling to 10 mins from now")
            except Exception as e:
                log_warning(f"Could not parse scheduled_time: {e}")
                schedule_timestamp = int(time_module.time()) + 600
        else:
            schedule_timestamp = int(time_module.time()) + 600

        log_info(f"Will schedule video for Unix timestamp: {schedule_timestamp}")

        # Get the reel title for Facebook
        reel_title = post.get('title') or post.get('reel_title', '')

        # Upload video as draft
        fb_result = fb_poster._post_video({
            'content_text': description,
            'video_url': video_url,
            'title': reel_title,  # Reel title for Facebook
            'post_as_draft': True,
            'include_schedule_hint': False,
            'scheduled_publish_time': schedule_timestamp,
        })

        if fb_result and fb_result.get('success') and fb_result.get('post_id'):
            facebook_post_id = fb_result.get('post_id')

            log_info(f"✅ Video uploaded to Facebook as draft: {facebook_post_id}")

            # Update post with Facebook ID and status
            supabase_client.table('social_posts').update({
                'facebook_post_id': facebook_post_id,
                'status': 'awaiting_music',
                'updated_at': datetime.now(SA_TZ).isoformat()
            }).eq('id', post_id).execute()

            # Send WhatsApp notification
            try:
                from utils.whatsapp_notifier import WhatsAppNotifier
                notifier = WhatsAppNotifier()

                creator_studio_url = f"https://business.facebook.com/latest/content_library?asset_id={facebook_post_id}"

                notifier.send_video_ready_template(
                    video_title=post.get('title', 'Video'),
                    creator_studio_url=creator_studio_url,
                    caption_preview=post.get('content_text', '')[:150]
                )
                log_info("✅ WhatsApp notification sent")
            except Exception as e:
                log_warning(f"Could not send WhatsApp notification: {e}")

            return jsonify({
                'success': True,
                'message': 'Video uploaded to Facebook as draft!',
                'facebook_post_id': facebook_post_id,
                'creator_studio_url': f"https://business.facebook.com/latest/content_library?asset_id={facebook_post_id}",
                'status': 'awaiting_music'
            })
        else:
            log_error(f"Facebook upload failed: {fb_result}")
            return jsonify({'success': False, 'error': 'Facebook upload failed'}), 500

    except Exception as e:
        log_error(f"❌ Upload to Facebook failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/mark-published/<string:post_id>', methods=['POST'])
def api_mark_published(post_id: str):
    """Manually mark a post as published (for videos after adding music in Creator Studio)."""
    log_info(f"📥 Request: /api/dashboard/mark-published/{post_id}")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        import pytz
        from datetime import datetime

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        # Verify post exists and is in awaiting_music status
        result = supabase_client.table('social_posts').select('id, status, facebook_post_id').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]

        if post.get('status') != 'awaiting_music':
            return jsonify({
                'success': False,
                'error': f"Post is not awaiting music. Current status: {post.get('status')}"
            }), 400

        # Update to published
        update_data = {
            'status': 'published',
            'published_time': datetime.now(SA_TZ).isoformat(),
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        update_result = supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

        if update_result.data:
            log_info(f"✅ Post {post_id} manually marked as published")
            return jsonify({
                'success': True,
                'post_id': post_id,
                'message': 'Post marked as published!'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update post'}), 500

    except Exception as e:
        log_error(f"❌ Mark published failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/edit/<string:post_id>', methods=['POST'])
def api_edit_post(post_id: str):
    """Edit a post's content, script, or prompts."""
    log_info(f"📥 Request: /api/dashboard/edit/{post_id}")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        import pytz
        from datetime import datetime
        import json

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        data = request.get_json()

        # Validate the post exists and is not published
        log_info(f"🔍 Checking if post {post_id} exists")
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]

        if post.get('status') == 'published':
            return jsonify({'success': False, 'error': 'Cannot edit a published post'}), 400

        # Build update data from provided fields
        update_data = {
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        # Update content_text (caption)
        if 'content_text' in data:
            update_data['content_text'] = data['content_text']
            log_info(f"📝 Updating content_text")

        # Update title
        if 'title' in data:
            update_data['title'] = data['title']
            log_info(f"📝 Updating title")

        # Update hashtags
        if 'hashtags' in data:
            hashtags_value = data['hashtags']

            # If it's a string that looks like comma-separated tags, convert to array
            if isinstance(hashtags_value, str):
                if hashtags_value.startswith('['):
                    # Already JSON-like, try to parse
                    try:
                        hashtags_list = json.loads(hashtags_value)
                        update_data['hashtags'] = json.dumps(hashtags_list)
                    except:
                        # Split by comma or space
                        tags = [t.strip() for t in hashtags_value.replace(',', ' ').split() if t.strip()]
                        # Ensure each tag starts with #
                        tags = ['#' + t.lstrip('#') for t in tags if t]
                        update_data['hashtags'] = json.dumps(tags)
                else:
                    # Plain string, split into tags
                    tags = [t.strip() for t in hashtags_value.replace(',', ' ').split() if t.strip()]
                    # Ensure each tag starts with #
                    tags = ['#' + t.lstrip('#') for t in tags if t]
                    update_data['hashtags'] = json.dumps(tags)
            elif isinstance(hashtags_value, list):
                update_data['hashtags'] = json.dumps(hashtags_value)

            log_info(f"📝 Updating hashtags: {update_data.get('hashtags')}")

        # Update generation_prompt (contains video_script, image_prompt, etc.)
        # We need to merge with existing data
        existing_prompt = {}
        if post.get('generation_prompt'):
            try:
                if isinstance(post['generation_prompt'], str):
                    existing_prompt = json.loads(post['generation_prompt'])
                else:
                    existing_prompt = post['generation_prompt']
            except:
                existing_prompt = {}

        # Update video_script
        if 'video_script' in data:
            existing_prompt['video_script'] = data['video_script']
            log_info(f"📝 Updating video_script")

        # Update image_prompt
        if 'image_prompt' in data:
            existing_prompt['image_prompt'] = data['image_prompt']
            update_data['image_prompt'] = data['image_prompt']  # Also update direct field if exists
            log_info(f"📝 Updating image_prompt")

        # Save updated generation_prompt
        if 'video_script' in data or 'image_prompt' in data:
            update_data['generation_prompt'] = json.dumps(existing_prompt)

        # Update content_theme if provided
        if 'content_theme' in data:
            update_data['content_theme'] = data['content_theme']

        # Perform update
        log_info(f"💾 Saving edits to post {post_id}")
        update_result = supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

        if update_result.data:
            log_info(f"✅ Post {post_id} updated successfully")
            return jsonify({
                'success': True,
                'post_id': post_id,
                'message': 'Post updated successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update post'}), 500

    except Exception as e:
        log_error(f"❌ Edit post failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/post/<string:post_id>', methods=['GET'])
def api_get_post(post_id: str):
    """Get full details of a single post for editing."""
    log_info(f"📥 Request: /api/dashboard/post/{post_id}")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        import json
        log_info(f"🔍 Fetching single post: {post_id}")

        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]
        log_info(f"✅ Found post {post_id}, type={post.get('post_type')}, has_generation_prompt={bool(post.get('generation_prompt'))}")

        # Parse generation_prompt to extract video_script, image_prompt, and motion_prompt
        video_script = ''
        image_prompt = ''
        motion_prompt = None

        if post.get('generation_prompt'):
            try:
                if isinstance(post['generation_prompt'], str):
                    prompt_data = json.loads(post['generation_prompt'])
                else:
                    prompt_data = post['generation_prompt']
                video_script = prompt_data.get('video_script', '')
                image_prompt = prompt_data.get('image_prompt', '')
                motion_prompt = prompt_data.get('motion_prompt')
            except:
                pass

        # Also check direct image_prompt field
        if not image_prompt and post.get('image_prompt'):
            image_prompt = post['image_prompt']

        # Format hashtags for display
        hashtags = post.get('hashtags', [])
        if isinstance(hashtags, list):
            hashtags_str = ' '.join(hashtags)
        else:
            hashtags_str = hashtags or ''

        return jsonify({
            'success': True,
            'post': {
                'id': post['id'],
                'title': post.get('title', ''),
                'content_text': post.get('content_text', ''),
                'post_type': post.get('post_type', ''),
                'platform': post.get('platform', ''),
                'status': post.get('status', ''),
                'scheduled_time': post.get('scheduled_time', ''),
                'content_theme': post.get('content_theme', ''),
                'hashtags': hashtags_str,
                'video_script': video_script,
                'image_prompt': image_prompt,
                'motion_prompt': motion_prompt,
                'is_pinned': post.get('is_pinned', False),
                'video_url': post.get('video_url', ''),
                'media_url': post.get('media_url', ''),
                'generation_prompt': post.get('generation_prompt', '{}')
            }
        })

    except Exception as e:
        log_error(f"❌ Get post failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/generate-media/<post_id>', methods=['POST'])
def api_generate_media(post_id):
    """API: Generate video or image for a post based on media_type"""
    log_info(f"📥 Request: /api/dashboard/generate-media/{post_id}")

    if not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        # Get post details
        post = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not post.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post_data = post.data[0]

        # Set status to 'generating' to show user that process has started
        supabase_client.table('social_posts').update({
            'status': 'generating',
            'updated_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', post_id).execute()
        log_info(f"🎬 Status set to 'generating' for post {post_id}")

        # Parse generation metadata
        metadata = json.loads(post_data.get('generation_prompt', '{}'))

        # Check media_type field first (new approach), fallback to post_type for backwards compatibility
        media_type = post_data.get('media_type') or metadata.get('media_type')
        post_type = post_data.get('post_type')

        # If no media_type, infer from post_type for backwards compatibility
        if not media_type:
            if post_type == 'video':
                media_type = 'video'
            elif post_type == 'carousel':
                media_type = 'carousel'
            else:
                media_type = 'static_image'

        log_info(f"📋 Media type routing: media_type='{media_type}', post_type='{post_type}' for post {post_id}")

        # ============================================================
        # ROUTE 1: VIDEO GENERATION (HeyGen video with avatar)
        # ============================================================
        if media_type == 'video':
            from social_media.video_generator import VideoGenerator
            from database import SocialMediaDatabase

            log_info(f"🎥 Using VIDEO generation workflow for post {post_id}")

            # Get request data
            data = request.get_json(silent=True) or {}
            use_avatar_iv = data.get('use_avatar_iv', False)
            force_fallback = data.get('force_fallback', False)

            log_info(f"Generate media request - use_avatar_iv: {use_avatar_iv}, force_fallback: {force_fallback}")

            db = SocialMediaDatabase(supabase_client)
            video_gen = VideoGenerator('social_media/config.yaml', supabase_client)

            # Get content_type for avatar selection (let VideoGenerator select from database)
            content_type = metadata.get('content_type') or metadata.get('video_generation', {}).get('content_type')
            content_theme = post_data.get('content_theme', 'general')
            avatar_id = None  # Let VideoGenerator select based on content_type
            script = metadata.get('video_script', '')

            if not script:
                return jsonify({'success': False, 'error': 'No video script found'}), 400

            # Get voice ID
            voice_id = os.getenv('HEYGEN_DEFAULT_VOICE_ID', '1bd001e7e50f421d891986aad5158bc8')

            # If Avatar IV requested, generate a look first
            image_url = None
            image_key = None
            if use_avatar_iv:
                log_info("User requested Avatar IV - generating look first...")

                try:
                    from social_media.looks_generator import LooksGenerator
                    looks_gen = LooksGenerator(supabase_client=supabase_client)

                    # Map content themes to valid look types
                    look_type_map = {
                        'relatable_trainer_life': 'gym_trainer',
                        'admin_hacks': 'office_professional',
                        'client_management': 'office_professional',
                        'business_growth': 'office_professional',
                        'fitness_tips': 'gym_trainer',
                        'motivation': 'motivational_speaker',
                        'trainer_motivation': 'motivational_speaker',
                        'client_success': 'motivational_speaker',
                        'workout_tips': 'gym_trainer',
                        'nutrition': 'nutrition_expert',
                        'wellness': 'outdoor_wellness',
                        'yoga': 'yoga_instructor',
                        'home_fitness': 'home_workout',
                    }

                    # Get look type from mapping, default to 'studio_portrait' if not found
                    look_type = look_type_map.get(content_theme, 'studio_portrait')

                    log_info(f"Generating look with type: {look_type} (from content_theme: {content_theme})")

                    look_result = looks_gen.generate_avatar_look(
                        look_type=look_type,
                        metadata={'purpose': 'video_generation', 'post_id': post_id}
                    )

                    # Extract image_url from look result
                    image_url = look_result.get('preview_url') or (look_result.get('image_urls', [None])[0])
                    image_key = look_result.get('photo_avatar_id')  # This is what Avatar IV needs

                    log_info(f"Look generated - image_url: {image_url[:50] if image_url else None}...")
                    log_info(f"Look generated - image_key (photo_avatar_id): {image_key}")

                    # Wait for look to be ready before using with Avatar IV
                    if image_key:
                        log_info(f"Waiting for look to be ready...")
                        ready_result = looks_gen.wait_for_look_ready(image_key, max_wait_seconds=120, poll_interval=5)

                        if not ready_result.get('ready'):
                            error_msg = ready_result.get('error', 'Look processing did not complete in time')
                            log_error(f"Look not ready: {error_msg}")

                            if not force_fallback:
                                return jsonify({
                                    'success': False,
                                    'needs_confirmation': True,
                                    'fallback_reason': 'look_not_ready',
                                    'message': f'Avatar IV look not ready: {error_msg}. Would you like to use Photo Avatar instead?'
                                }), 200
                            else:
                                log_info("Falling back to Photo Avatar due to force_fallback=True")
                                image_url = None
                                image_key = None
                                use_avatar_iv = False
                        else:
                            log_info(f"✅ Look is ready, proceeding with Avatar IV")

                    if not image_url and not image_key:
                        raise ValueError("Look generation succeeded but no image_url or image_key returned")

                    # Save look info to post for later reference
                    looks_gen.save_look_to_database(look_result)

                except Exception as e:
                    log_error(f"Look generation failed for Avatar IV: {e}")

                    if not force_fallback:
                        return jsonify({
                            'success': False,
                            'needs_confirmation': True,
                            'fallback_reason': 'look_generation_failed',
                            'message': f'Avatar IV look generation failed: {str(e)}. Would you like to use Photo Avatar instead?'
                        }), 200
                    else:
                        log_info("Falling back to Photo Avatar due to force_fallback=True")
                        image_url = None
                        use_avatar_iv = False

            log_info(f"🎬 Generating HeyGen video for post {post_id}")
            log_info(f"🎬 Calling HeyGen to generate video for post {post_id}")

            try:
                # Choose API based on whether we have image_url (Avatar IV) or not (Photo Avatar)
                if image_url or image_key:
                    log_info("Using Avatar IV API")
                    result = video_gen.generate_avatar_iv_video(
                        script=script,
                        image_url=image_url,
                        image_key=image_key,  # ADD THIS - Avatar IV requires this
                        voice_id=voice_id,
                        aspect_ratio="9:16",
                        title=post_data.get('title', 'Generated Video'),
                        metadata={
                            'post_id': post_id,
                            'content_theme': content_theme,
                            'api_type': 'avatar_iv'
                        }
                    )
                else:
                    log_info("Using Photo Avatar API")
                    result = video_gen.generate_avatar_video(
                        script_text=script,
                        avatar_id=None,  # Let VideoGenerator select from database
                        voice_id=voice_id,
                        style='educational',
                        background_music=False,
                        metadata={
                            'post_id': post_id,
                            'content_theme': content_theme,
                            'api_type': 'photo_avatar'
                        },
                        content_type=content_type,
                        wait_for_completion=False
                    )

                log_info(f"📹 HeyGen response received: {result}")

                # Extract video_id and video_url from result
                video_id = None
                video_url = None

                if isinstance(result, dict):
                    video_id = result.get('video_id')
                    video_url = result.get('video_url')

                log_info(f"📹 Video ID from HeyGen: {video_id}")
                log_info(f"📹 Video URL from HeyGen: {video_url}")

                if not video_id:
                    log_error(f"❌ HeyGen did not return video_id for post {post_id}")
                    log_error(f"❌ Full result: {result}")
                    raise Exception("No video_id returned from HeyGen")

                # Save video to database
                if video_url:
                    # Video completed immediately
                    log_info(f"🎉 Video completed immediately with URL: {video_url}")
                    log_info(f"💾 Saving video_id {video_id} and URL to database for post {post_id}")

                    # Get source image for title card generation
                    source_image_url = None

                    # If we used Avatar IV, we already have the image_url
                    if image_url:
                        source_image_url = image_url
                        log_info(f"📸 Using Avatar IV image_url as source_image_url: {source_image_url[:50]}...")
                    # Otherwise try to get from HeyGen result thumbnail
                    elif isinstance(result, dict):
                        source_image_url = result.get('thumbnail_url')
                        if source_image_url:
                            log_info(f"📸 Using HeyGen thumbnail as source_image_url: {source_image_url[:50]}...")

                    update_data = {
                        'video_id': video_id,
                        'video_url': video_url,
                        'status': 'pending_approval',
                        'media_generation_completed_at': datetime.now(timezone.utc).isoformat(),
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }

                    # Add source_image_url if available
                    if source_image_url:
                        update_data['source_image_url'] = source_image_url

                    supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

                    log_info(f"✅ Video generated successfully for post {post_id}")

                    return jsonify({
                        'success': True,
                        'message': 'Video generated successfully!',
                        'video_id': video_id,
                        'video_url': video_url,
                        'post_id': post_id,
                        'status': 'pending_approval'
                    }), 200
                else:
                    # Video is processing - save video_id and let background job fetch URL
                    log_info(f"⏳ Video processing - saving video_id {video_id} for background fetch")
                    log_info(f"💾 Saving video_id to database: {video_id}")
                    log_info(f"📸 source_image_url will be fetched by background job when video completes")

                    supabase_client.table('social_posts').update({
                        'video_id': video_id,
                        'status': 'generating',
                        'media_generation_started_at': datetime.now(timezone.utc).isoformat(),
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }).eq('id', post_id).execute()

                    log_info(f"✅ Video generation started for post {post_id}")

                    return jsonify({
                        'success': True,
                        'message': 'Video generation started! It will be ready in 30-60 seconds.',
                        'video_id': video_id,
                        'post_id': post_id,
                        'status': 'generating'
                    }), 200

            except Exception as e:
                log_error(f"❌ Media generation failed for {post_id}: {str(e)}")
                import traceback
                log_error(f"Traceback: {traceback.format_exc()}")

                # Reset status so user can retry
                supabase_client.table('social_posts').update({
                    'status': 'approved',
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }).eq('id', post_id).execute()

                return jsonify({
                    'success': False,
                    'error': f'Video generation failed: {str(e)}'
                }), 500

        # ============================================================
        # ROUTE 2: STATIC IMAGE GENERATION (Leonardo AI)
        # ============================================================
        elif media_type == 'static_image':
            log_info(f"🖼️  Using STATIC IMAGE generation workflow (Leonardo AI) for post {post_id}")

            # Get caption/theme from metadata
            caption = post_data.get('content_text', '')
            content_type = metadata.get('content_type', 'motivational')

            if not caption:
                return jsonify({'success': False, 'error': 'No caption found for image'}), 400

            log_info(f"🎨 Generating Leonardo AI image for post {post_id} (content_type: {content_type})")

            try:
                from social_media.leonardo_generator import LeonardoGenerator, LeonardoGenerationError

                leonardo = LeonardoGenerator(supabase_client=supabase_client)

                # Determine if this should be a quote graphic or character image
                from social_media.leonardo_generator import CONTENT_TYPE_PROMPTS
                config = CONTENT_TYPE_PROMPTS.get(content_type, {})

                if config.get("style") == "quote_graphic":
                    log_info(f"🎨 Generating quote graphic for content_type: {content_type}")
                    result = leonardo.generate_quote_graphic(
                        quote_text=caption,
                        content_type=content_type,
                    )
                else:
                    log_info(f"🎨 Generating character image for content_type: {content_type}")
                    result = leonardo.generate_image(
                        prompt=caption,
                        content_type=content_type,
                    )

                image_url = result.get("image_url")

                if not image_url:
                    raise LeonardoGenerationError("No image URL returned from Leonardo AI")

                # Update post with image URL
                supabase_client.table('social_posts').update({
                    'status': 'pending_media_approval',
                    'image_url': image_url,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }).eq('id', post_id).execute()

                log_info(f"✅ Leonardo AI image generated for post {post_id}: {image_url}")

                return jsonify({
                    'success': True,
                    'message': 'Image generated successfully',
                    'post_id': post_id,
                    'image_url': image_url,
                    'generation_id': result.get('generation_id'),
                    'content_type': content_type,
                }), 200

            except ImportError as e:
                log_error(f"❌ Leonardo AI module not available: {e}")
                supabase_client.table('social_posts').update({
                    'status': 'approved',
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }).eq('id', post_id).execute()
                return jsonify({
                    'success': False,
                    'error': 'Leonardo AI integration not configured. Please check LEONARDO_API_KEY.'
                }), 500

            except LeonardoGenerationError as e:
                log_error(f"❌ Leonardo AI generation failed for {post_id}: {str(e)}")
                supabase_client.table('social_posts').update({
                    'status': 'approved',
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }).eq('id', post_id).execute()
                return jsonify({
                    'success': False,
                    'error': f'Image generation failed: {str(e)}'
                }), 500

            except Exception as e:
                log_error(f"❌ Static image generation failed for {post_id}: {str(e)}")
                import traceback
                log_error(f"Traceback: {traceback.format_exc()}")
                supabase_client.table('social_posts').update({
                    'status': 'approved',
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }).eq('id', post_id).execute()
                return jsonify({
                    'success': False,
                    'error': f'Static image generation failed: {str(e)}'
                }), 500

        # ============================================================
        # ROUTE 3: CAROUSEL GENERATION
        # ============================================================
        elif media_type == 'carousel':
            log_info(f"📊 Using CAROUSEL generation workflow for post {post_id}")

            try:
                # Step 1: Get carousel data from metadata or parse from caption
                caption = post_data.get('content_text', '')

                # Get carousel content from metadata
                # Note: metadata may use 'carousel_data' OR 'carousel_slides' depending on how it was created
                carousel_data = metadata.get('carousel_data') or metadata.get('carousel_slides')
                content_type = metadata.get('content_type', 'educational')

                log_info(f"📝 Caption length: {len(caption)} chars")
                log_info(f"🎨 Content type: {content_type}")

                # Check if carousel_slides is a list (raw slides) vs dict with 'slides' key
                if carousel_data:
                    if isinstance(carousel_data, list):
                        # It's a raw list of slides - need to transform to expected format
                        log_info(f"📊 Found carousel_slides as list with {len(carousel_data)} items")

                        # Transform slides to the format carousel_template_generator expects
                        transformed_slides = transform_raw_slides_to_carousel_format(carousel_data)
                        carousel_data = {'slides': transformed_slides, 'content_type': content_type}
                        log_info(f"✅ Transformed {len(transformed_slides)} slides to carousel format")
                    elif isinstance(carousel_data, dict) and not carousel_data.get('slides'):
                        # It might have cover, content_slides, cta_slide format - convert it
                        log_info(f"📊 Found carousel_data dict, converting to slides format")
                        carousel_data = convert_carousel_format(carousel_data, content_type)
                    else:
                        log_info(f"📊 Found carousel_data with {len(carousel_data.get('slides', []))} slides")

                if not carousel_data or not carousel_data.get('slides'):
                    log_warning(f"⚠️  No valid carousel_data in metadata, parsing from caption")
                    carousel_data = parse_caption_to_carousel(caption, content_type)
                    log_info(f"✅ Parsed carousel from caption with {len(carousel_data.get('slides', []))} slides")

                # Ensure content_type is set
                carousel_data['content_type'] = content_type

                # Step 2: Validate carousel data structure
                log_info(f"🔍 Validating carousel_data structure...")
                log_info(f"📊 carousel_data type: {type(carousel_data)}")
                log_info(f"📊 carousel_data keys: {carousel_data.keys() if isinstance(carousel_data, dict) else 'Not a dict'}")

                if not isinstance(carousel_data, dict):
                    log_error(f"❌ carousel_data is not a dictionary: {type(carousel_data)}")
                    raise ValueError(f"carousel_data must be a dictionary, got {type(carousel_data)}")

                slides = carousel_data.get('slides', [])
                if not slides:
                    log_error("❌ No valid carousel slides found in carousel_data")
                    log_error(f"📊 carousel_data content: {carousel_data}")
                    raise ValueError("Carousel data must contain 'slides' array")

                log_info(f"✅ Carousel has {len(slides)} slides")
                for i, slide in enumerate(slides[:3]):  # Log first 3 slides
                    log_info(f"   Slide {i+1} keys: {slide.keys() if isinstance(slide, dict) else type(slide)}")

                # Step 3: Add content_type to carousel_data for Leonardo cover
                if 'content_type' not in carousel_data:
                    carousel_data['content_type'] = content_type
                    log_info(f"✅ Added content_type '{content_type}' to carousel_data")
                else:
                    log_info(f"ℹ️  carousel_data already has content_type: {carousel_data['content_type']}")

                # Step 4: Initialize carousel generator
                log_info("🔧 Initializing CarouselTemplateGenerator...")
                try:
                    from social_media.carousel_template_generator import CarouselTemplateGenerator

                    config_path = os.path.join(os.path.dirname(__file__), 'social_media', 'config.yaml')
                    log_info(f"📁 Config path: {config_path}")

                    if not os.path.exists(config_path):
                        log_error(f"❌ Config file not found: {config_path}")
                        log_error(f"📁 Current directory: {os.getcwd()}")
                        log_error(f"📁 __file__: {__file__}")
                        raise FileNotFoundError(f"Config not found: {config_path}")

                    log_info(f"✅ Config file exists, file size: {os.path.getsize(config_path)} bytes")

                    carousel_generator = CarouselTemplateGenerator(config_path, supabase_client=supabase_client)
                    log_info("✅ CarouselTemplateGenerator initialized successfully")

                except ImportError as import_error:
                    log_error(f"❌ Failed to import CarouselTemplateGenerator: {import_error}")
                    import traceback
                    log_error(f"Import traceback: {traceback.format_exc()}")
                    raise
                except Exception as init_error:
                    log_error(f"❌ Failed to initialize CarouselTemplateGenerator: {init_error}")
                    import traceback
                    log_error(f"Init traceback: {traceback.format_exc()}")
                    raise

                # Step 5: Generate carousel slides
                log_info("🎨 Generating carousel slides...")
                log_info(f"📊 Calling create_carousel with {len(carousel_data.get('slides', []))} slides")

                try:
                    slide_paths = carousel_generator.create_carousel(carousel_data)

                    if not slide_paths:
                        log_error("❌ create_carousel returned None or empty list")
                        raise ValueError("Carousel generation returned no slides")

                    log_info(f"✅ Generated {len(slide_paths)} carousel slides")
                    for i, path in enumerate(slide_paths):
                        log_info(f"   Slide {i+1}: {path}")
                        # Verify file exists if it's a local path
                        if path and not path.startswith('http'):
                            if os.path.exists(path):
                                log_info(f"      ✅ File exists, size: {os.path.getsize(path)} bytes")
                            else:
                                log_warning(f"      ⚠️  File not found at path: {path}")

                except Exception as gen_error:
                    log_error(f"❌ Carousel slide generation failed: {gen_error}")
                    log_error(f"Error type: {type(gen_error).__name__}")
                    import traceback
                    log_error(f"Generation traceback: {traceback.format_exc()}")
                    raise

                # Step 6: Upload slides to Supabase Storage
                carousel_urls = []
                upload_errors = []

                log_info(f"📤 Uploading {len(slide_paths)} slides to Supabase Storage...")

                for i, path in enumerate(slide_paths):
                    slide_num = i + 1
                    success, public_url, error = upload_carousel_slide(path, post_id, slide_num)

                    if success and public_url:
                        carousel_urls.append(public_url)
                        log_info(f"   ✅ Slide {slide_num}: {public_url}")
                    else:
                        log_error(f"   ❌ Slide {slide_num} upload failed: {error}")
                        upload_errors.append(f"Slide {slide_num}: {error}")

                if not carousel_urls:
                    raise ValueError(f"All slide uploads failed: {upload_errors}")

                if upload_errors:
                    log_warning(f"⚠️  Some slides failed to upload: {upload_errors}")

                log_info(f"📊 Successfully uploaded {len(carousel_urls)} slides")

                # Step 7: Update post with carousel URLs
                log_info("💾 Updating post with generated slides...")
                try:
                    log_info(f"📊 Saving {len(carousel_urls)} carousel URLs to database")
                    for i, url in enumerate(carousel_urls):
                        log_info(f"   Slide {i+1}: {url}")

                    supabase_client.table('social_posts').update({
                        'status': 'pending_media_approval',
                        'carousel_image_urls': carousel_urls,  # Use the correct column name and pass the list directly
                        'updated_at': datetime.now(SA_TZ).isoformat()
                    }).eq('id', post_id).execute()

                    log_info(f"✅ Post {post_id} updated with {len(carousel_urls)} carousel slides")

                except Exception as update_error:
                    log_error(f"❌ Failed to update post in database: {update_error}")
                    import traceback
                    log_error(f"Update traceback: {traceback.format_exc()}")
                    raise

                # Step 7b: Ensure hashtags exist for carousel post
                try:
                    existing_hashtags = post_data.get('hashtags')
                    if not existing_hashtags or len(existing_hashtags) == 0:
                        hashtags = generate_trainer_hashtags(content_type)

                        # Update post with hashtags
                        supabase_client.table('social_posts').update({
                            'hashtags': hashtags
                        }).eq('id', post_id).execute()

                        log_info(f"📌 Added {len(hashtags)} hashtags to carousel post: {hashtags}")
                    else:
                        log_info(f"📌 Carousel post already has hashtags: {existing_hashtags}")
                except Exception as hashtag_error:
                    log_warning(f"⚠️ Failed to add hashtags to carousel: {hashtag_error}")
                    # Don't fail the whole request if hashtags fail

                # Step 8: Return success
                log_info(f"🎉 Carousel generation complete for post {post_id}")
                return jsonify({
                    'success': True,
                    'message': f'Carousel generated successfully with {len(carousel_urls)} slides',
                    'slide_count': len(carousel_urls),
                    'slide_paths': carousel_urls
                })

            except Exception as e:
                log_error(f"❌ CAROUSEL GENERATION FAILED for post {post_id}: {str(e)}")
                log_error(f"Error type: {type(e).__name__}")
                import traceback
                log_error(f"Full traceback: {traceback.format_exc()}")

                # Reset post to approved status so user can try again
                try:
                    supabase_client.table('social_posts').update({
                        'status': 'approved',
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }).eq('id', post_id).execute()
                    log_info(f"✅ Post {post_id} status reset to 'approved' for retry")
                except Exception as reset_error:
                    log_error(f"❌ Failed to reset post status: {reset_error}")

                return jsonify({
                    'success': False,
                    'error': f'Carousel generation failed: {str(e)}',
                    'error_type': type(e).__name__
                }), 500

        else:
            return jsonify({'success': False, 'error': f'Unsupported media type: {media_type}'}), 400

    except Exception as e:
        log_error(f"❌ Error generating media for {post_id}: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dashboard/regenerate-media/<post_id>', methods=['POST'])
def api_regenerate_media(post_id):
    """API: Regenerate media for a post"""
    log_info(f"📥 Request: /api/dashboard/regenerate-media/{post_id}")

    if not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        # Reset status back to pending_approval and clear video URL
        supabase_client.table('social_posts').update({
            'status': 'pending_approval',
            'video_url': None,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('id', post_id).execute()

        log_info(f"✅ Post {post_id} reset for regeneration")
        return jsonify({'success': True, 'message': 'Ready to regenerate'})

    except Exception as e:
        log_error(f"❌ Error resetting media for {post_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/regenerate-carousel-look/<post_id>', methods=['POST'])
def regenerate_carousel_look(post_id):
    """Queue carousel for regeneration with a different avatar look."""
    try:
        data = request.get_json() or {}
        look_id = data.get('look_id')

        if not look_id:
            return jsonify({'success': False, 'error': 'No look_id provided'}), 400

        # Get the post
        post_result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()
        if not post_result.data or len(post_result.data) == 0:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = post_result.data[0]

        if post.get('post_type') != 'carousel':
            return jsonify({'success': False, 'error': 'Post is not a carousel'}), 400

        # Get the avatar look
        look_result = supabase_client.table('photo_avatar_looks').select('*').eq('id', look_id).execute()
        if not look_result.data or len(look_result.data) == 0:
            return jsonify({'success': False, 'error': 'Avatar look not found'}), 404

        look = look_result.data[0]

        # Update the post's generation_prompt with the new look
        import json
        generation_prompt = post.get('generation_prompt', '{}')
        if isinstance(generation_prompt, str):
            try:
                generation_prompt = json.loads(generation_prompt)
            except:
                generation_prompt = {}

        generation_prompt['selected_look_id'] = look_id
        generation_prompt['photo_avatar_id'] = look.get('photo_avatar_id')
        generation_prompt['look_label'] = look.get('label', look.get('content_type', 'custom'))

        # Update post: reset status to approved and clear existing images to trigger regeneration
        update_data = {
            'generation_prompt': json.dumps(generation_prompt),
            'status': 'approved',
            'carousel_image_urls': None,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

        log_info(f"Carousel {post_id} queued for regeneration with look: {look.get('label', look_id)}")

        return jsonify({
            'success': True,
            'message': f"Carousel queued for regeneration with '{look.get('label', 'selected')}' look. Generate media to see the new look.",
            'look_label': look.get('label')
        })

    except Exception as e:
        log_error(f"Error in regenerate_carousel_look: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/carousel/change-look/<post_id>', methods=['POST'])
def change_carousel_look(post_id):
    """Change the look (avatar style) of carousel cover slide only, keeping other slides intact."""
    log_info(f"📥 Request: /api/carousel/change-look/{post_id}")

    if not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        # Get request data
        data = request.get_json() or {}
        look_label = data.get('look_label')

        if not look_label:
            return jsonify({'success': False, 'error': 'No look_label provided'}), 400

        log_info(f"🎨 Changing carousel look to: {look_label}")

        # Step 1: Get the post from database
        post_result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()
        if not post_result.data or len(post_result.data) == 0:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = post_result.data[0]

        # Step 2: Validate it's a carousel
        if post.get('post_type') != 'carousel':
            return jsonify({'success': False, 'error': 'Post is not a carousel'}), 400

        # Step 3: Get existing carousel_image_urls
        carousel_urls = post.get('carousel_image_urls')
        if not carousel_urls or len(carousel_urls) == 0:
            return jsonify({'success': False, 'error': 'Carousel has no slides'}), 400

        log_info(f"📊 Carousel has {len(carousel_urls)} slides")

        # Step 4: Get the photo avatar look by label
        look_result = supabase_client.table('photo_avatar_looks').select('*').eq('label', look_label).execute()
        if not look_result.data or len(look_result.data) == 0:
            return jsonify({'success': False, 'error': f'Avatar look not found with label: {look_label}'}), 404

        look = look_result.data[0]
        content_type = look.get('content_type', 'educational')

        log_info(f"✅ Found look: {look.get('label')} (content_type: {content_type})")

        # Step 5: Get carousel data from post (check carousel_data field first, then generation_prompt)
        carousel_data = post.get('carousel_data')

        # If carousel_data doesn't exist, try generation_prompt
        if not carousel_data:
            generation_prompt = post.get('generation_prompt', '{}')
            if isinstance(generation_prompt, str):
                try:
                    generation_prompt = json.loads(generation_prompt)
                except:
                    generation_prompt = {}
            carousel_data = generation_prompt.get('carousel_data') or generation_prompt.get('carousel_slides')

        # Parse carousel_data if it's a string
        if isinstance(carousel_data, str):
            try:
                carousel_data = json.loads(carousel_data)
            except:
                carousel_data = None

        if not carousel_data:
            return jsonify({'success': False, 'error': 'No carousel data found in post'}), 400

        # Handle different carousel_data formats
        if isinstance(carousel_data, list):
            # Transform to dict format
            carousel_data = {'slides': carousel_data}

        slides = carousel_data.get('slides', [])
        if not slides or len(slides) == 0:
            return jsonify({'success': False, 'error': 'No slides found in carousel data'}), 400

        # Step 6: Extract cover title from carousel data
        # The title may be stored in carousel_data.cover.title or in the first slide
        cover_title = carousel_data.get('cover', {}).get('title', '')

        # If no title in cover key, try the first slide's title
        if not cover_title:
            cover_slide = slides[0]
            cover_title = cover_slide.get('title', 'Untitled')
        else:
            cover_slide = slides[0]

        log_info(f"📝 Extracted cover title: {cover_title}")

        # Ensure the cover slide has the proper title
        cover_slide_with_title = {
            'type': 'COVER',
            'title': cover_title,
            'avatar_path': cover_slide.get('avatar_path', ''),
            'text': cover_title  # Some templates might use 'text' instead of 'title'
        }

        # Create carousel data for just the cover slide with new content_type
        cover_carousel_data = {
            'slides': [cover_slide_with_title],
            'content_type': content_type
        }

        log_info(f"🎨 Generating new cover slide with content_type: {content_type}")

        # Step 7: Initialize carousel generator and generate new cover
        from social_media.carousel_template_generator import CarouselTemplateGenerator

        config_path = os.path.join(os.path.dirname(__file__), 'social_media', 'config.yaml')
        if not os.path.exists(config_path):
            return jsonify({'success': False, 'error': 'Config file not found'}), 500

        carousel_generator = CarouselTemplateGenerator(config_path, supabase_client=supabase_client)

        # Generate the cover slide
        slide_paths = carousel_generator.create_carousel(cover_carousel_data)

        if not slide_paths or len(slide_paths) == 0:
            return jsonify({'success': False, 'error': 'Failed to generate cover slide'}), 500

        new_cover_path = slide_paths[0]
        log_info(f"✅ Generated new cover at: {new_cover_path}")

        # Step 8: Upload new cover slide to Supabase
        success, new_cover_url, error = upload_carousel_slide(new_cover_path, post_id, 1)

        if not success or not new_cover_url:
            return jsonify({'success': False, 'error': f'Failed to upload cover slide: {error}'}), 500

        log_info(f"📤 Uploaded new cover: {new_cover_url}")

        # Step 9: Replace slide 1 URL, keep slides 2-N unchanged
        new_carousel_urls = [new_cover_url] + carousel_urls[1:]

        log_info(f"🔄 Updated carousel URLs: {len(new_carousel_urls)} slides")

        # Step 10: Update post with new carousel_image_urls, keep status as pending_media_approval
        supabase_client.table('social_posts').update({
            'carousel_image_urls': new_carousel_urls,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('id', post_id).execute()

        log_info(f"✅ Carousel cover updated with look: {look_label}")

        # Step 11: Return success with new carousel URLs
        return jsonify({
            'success': True,
            'message': f'Carousel cover updated with {look_label} look',
            'carousel_urls': new_carousel_urls,
            'look_label': look_label,
            'content_type': content_type,
            'new_cover_url': new_cover_url
        }), 200

    except Exception as e:
        log_error(f"❌ Error changing carousel look: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/regenerate-carousel-cover/<post_id>', methods=['POST'])
def regenerate_carousel_cover(post_id):
    """Regenerate ONLY the cover image (slide 1) of a carousel, keeping other slides intact.

    This uses the same Refiloe look/avatar selection logic as the original generation.
    """
    log_info(f"📥 Request: /api/dashboard/regenerate-carousel-cover/{post_id}")

    if not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        # Step 1: Get the post from database
        post_result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()
        if not post_result.data or len(post_result.data) == 0:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = post_result.data[0]

        # Step 2: Validate it's a carousel
        if post.get('post_type') != 'carousel':
            return jsonify({'success': False, 'error': 'Post is not a carousel'}), 400

        # Step 3: Get existing carousel_image_urls
        carousel_urls = post.get('carousel_image_urls')
        if not carousel_urls or len(carousel_urls) == 0:
            return jsonify({'success': False, 'error': 'Carousel has no slides to regenerate'}), 400

        log_info(f"📊 Carousel has {len(carousel_urls)} slides, regenerating cover (slide 1)")

        # Step 4: Get carousel data from post (check carousel_data field first, then generation_prompt)
        carousel_data = post.get('carousel_data')

        # If carousel_data doesn't exist, try generation_prompt
        if not carousel_data:
            generation_prompt = post.get('generation_prompt', '{}')
            if isinstance(generation_prompt, str):
                try:
                    generation_prompt = json.loads(generation_prompt)
                except:
                    generation_prompt = {}
            carousel_data = generation_prompt.get('carousel_data') or generation_prompt.get('carousel_slides')

        # Parse carousel_data if it's a string
        if isinstance(carousel_data, str):
            try:
                carousel_data = json.loads(carousel_data)
            except:
                carousel_data = None

        if not carousel_data:
            # Fallback: Create minimal carousel_data from post title/caption
            log_warning(f"⚠️ No carousel_data found, using post title/caption as fallback")

            # Get title from post
            post_title = post.get('title') or post.get('caption', '')[:60] or 'Tips for Personal Trainers'

            # Create minimal carousel data structure
            carousel_data = {
                'slides': [
                    {'type': 'COVER', 'title': post_title}
                ],
                'content_type': 'educational'
            }
            log_info(f"📝 Created fallback carousel_data with title: {post_title[:50]}...")

        # Handle different carousel_data formats
        if isinstance(carousel_data, list):
            # Transform to dict format
            carousel_data = {'slides': carousel_data}

        slides = carousel_data.get('slides', [])
        if not slides or len(slides) == 0:
            return jsonify({'success': False, 'error': 'No slides found in carousel data'}), 400

        # Step 5: Get content_type from metadata (same logic as original generation)
        content_type = carousel_data.get('content_type', 'educational')

        # Also check generation_prompt for content_type
        generation_prompt = post.get('generation_prompt', '{}')
        if isinstance(generation_prompt, str):
            try:
                generation_prompt = json.loads(generation_prompt)
            except:
                generation_prompt = {}

        if not content_type or content_type == 'educational':
            content_type = generation_prompt.get('content_type', 'educational')

        log_info(f"🎨 Using content_type: {content_type}")

        # Step 6: Extract cover title from carousel data
        cover_title = carousel_data.get('cover', {}).get('title', '')

        # If no title in cover key, try the first slide's title
        if not cover_title:
            if slides and len(slides) > 0:
                first_slide = slides[0]
                cover_title = first_slide.get('title', '') or first_slide.get('text', '')

        # Final fallback to post title
        if not cover_title:
            cover_title = post.get('title') or post.get('caption', '')[:60] or 'Tips for Personal Trainers'

        cover_slide = slides[0] if slides else {'type': 'COVER', 'title': cover_title}

        log_info(f"📝 Using cover title: {cover_title[:50]}...")

        # Ensure the cover slide has the proper title
        cover_slide_with_title = {
            'type': 'COVER',
            'title': cover_title,
            'avatar_path': cover_slide.get('avatar_path', ''),
            'text': cover_title  # Some templates might use 'text' instead of 'title'
        }

        # Create carousel data for just the cover slide
        cover_carousel_data = {
            'slides': [cover_slide_with_title],
            'content_type': content_type
        }

        log_info(f"🎨 Generating new cover slide with content_type: {content_type}")

        # Step 7: Initialize carousel generator and generate new cover
        from social_media.carousel_template_generator import CarouselTemplateGenerator

        config_path = os.path.join(os.path.dirname(__file__), 'social_media', 'config.yaml')
        if not os.path.exists(config_path):
            return jsonify({'success': False, 'error': 'Config file not found'}), 500

        carousel_generator = CarouselTemplateGenerator(config_path, supabase_client=supabase_client)

        # Generate the cover slide
        slide_paths = carousel_generator.create_carousel(cover_carousel_data)

        if not slide_paths or len(slide_paths) == 0:
            return jsonify({'success': False, 'error': 'Failed to generate cover slide'}), 500

        new_cover_path = slide_paths[0]
        log_info(f"✅ Generated new cover at: {new_cover_path}")

        # Step 8: Upload new cover slide to Supabase
        success, new_cover_url, error = upload_carousel_slide(new_cover_path, post_id, 1)

        if not success or not new_cover_url:
            return jsonify({'success': False, 'error': f'Failed to upload cover slide: {error}'}), 500

        log_info(f"📤 Uploaded new cover: {new_cover_url}")

        # Step 9: Replace slide 1 URL, keep slides 2-N unchanged
        new_carousel_urls = [new_cover_url] + carousel_urls[1:]

        log_info(f"🔄 Updated carousel URLs: {len(new_carousel_urls)} slides")

        # Step 10: Update post with new carousel_image_urls
        supabase_client.table('social_posts').update({
            'carousel_image_urls': new_carousel_urls,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('id', post_id).execute()

        log_info(f"✅ Carousel cover regenerated successfully")

        # Step 11: Return success with new carousel URLs
        return jsonify({
            'success': True,
            'message': 'Carousel cover regenerated successfully',
            'carousel_urls': new_carousel_urls,
            'new_cover_url': new_cover_url
        }), 200

    except Exception as e:
        log_error(f"❌ Error regenerating carousel cover: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/motion-prompts', methods=['GET'])
def api_get_motion_prompts():
    """Get list of available motion prompts for video generation."""
    log_info("📥 Request: /api/dashboard/motion-prompts")
    return jsonify({
        'success': True,
        'prompts': MOTION_PROMPTS
    })


@app.route('/api/dashboard/regenerate-video/<string:post_id>', methods=['POST'])
def api_regenerate_video(post_id: str):
    """Regenerate video for a post using the current script and selected motion prompt."""
    log_info(f"📥 Request: /api/dashboard/regenerate-video/{post_id}")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        import pytz
        from datetime import datetime
        import json

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        # Get request data
        data = request.get_json(silent=True) or {}
        motion_prompt = data.get('motion_prompt', '').strip() if data.get('motion_prompt') else None
        use_avatar_iv = data.get('use_avatar_iv', False)
        force_fallback = data.get('force_fallback', False)

        log_info(f"🎭 Motion prompt received: {motion_prompt}")
        log_info(f"🎭 Use Avatar IV: {use_avatar_iv}")
        log_info(f"🔄 Force fallback: {force_fallback}")

        # Fetch the post
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]

        # Check if post is a video type
        if post.get('post_type') != 'video' and not post.get('video_url'):
            return jsonify({'success': False, 'error': 'This post is not a video post'}), 400

        # Don't allow regenerating published posts
        if post.get('status') == 'published':
            return jsonify({'success': False, 'error': 'Cannot regenerate a published video'}), 400

        # Get the video script from generation_prompt
        generation_prompt = post.get('generation_prompt')
        video_script = None
        gen_data = {}

        if generation_prompt:
            try:
                if isinstance(generation_prompt, str):
                    gen_data = json.loads(generation_prompt)
                else:
                    gen_data = generation_prompt
                video_script = gen_data.get('video_script', '')
            except Exception as e:
                log_error(f"Error parsing generation_prompt: {e}")

        if not video_script:
            return jsonify({'success': False, 'error': 'No video script found for this post'}), 400

        log_info(f"🎬 Regenerating video for post {post_id}")
        log_info(f"📝 Script length: {len(video_script)} chars")
        log_info(f"🎭 Motion prompt: {motion_prompt or 'None (auto)'}")

        # Update post status to generating
        supabase_client.table('social_posts').update({
            'status': 'generating',
            'video_url': None,
            'video_id': None,
            'media_generation_started_at': datetime.now(SA_TZ).isoformat(),
            'media_generation_completed_at': None,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('id', post_id).execute()

        # Initialize video generator
        from social_media.video_generator import VideoGenerator

        config_path = os.path.join(os.path.dirname(__file__), 'social_media', 'config.yaml')
        video_gen = VideoGenerator(config_path, supabase_client)

        # Get content theme for avatar selection
        content_theme = post.get('content_theme', 'general')
        content_type = content_theme

        # Get voice ID
        voice_id = os.getenv('HEYGEN_DEFAULT_VOICE_ID', '1bd001e7e50f421d891986aad5158bc8')

        # Try to get avatar and look for Avatar IV
        image_url = None
        image_key = None
        avatar_id = None

        # If Avatar IV requested, generate a look
        if use_avatar_iv:
            log_info("User requested Avatar IV - generating look...")

            try:
                from social_media.looks_generator import LooksGenerator
                looks_gen = LooksGenerator(supabase_client=supabase_client)

                # Map content themes to valid look types
                look_type_map = {
                    'relatable_trainer_life': 'gym_trainer',
                    'admin_hacks': 'office_professional',
                    'client_management': 'office_professional',
                    'business_growth': 'office_professional',
                    'fitness_tips': 'gym_trainer',
                    'motivation': 'motivational_speaker',
                    'trainer_motivation': 'motivational_speaker',
                    'client_success': 'motivational_speaker',
                    'workout_tips': 'gym_trainer',
                    'nutrition': 'nutrition_expert',
                    'wellness': 'outdoor_wellness',
                    'yoga': 'yoga_instructor',
                    'home_fitness': 'home_workout',
                }

                # Get look type from mapping, default to 'studio_portrait' if not found
                look_type = look_type_map.get(content_theme, 'studio_portrait')

                log_info(f"Generating look with type: {look_type} (from content_theme: {content_theme})")

                look_result = looks_gen.generate_avatar_look(
                    look_type=look_type,
                    metadata={'purpose': 'video_regeneration', 'post_id': post_id}
                )

                # Extract image_url from look result
                image_url = look_result.get('preview_url') or (look_result.get('image_urls', [None])[0])
                image_key = look_result.get('photo_avatar_id')  # This is what Avatar IV needs

                log_info(f"Look generated - image_url: {image_url[:50] if image_url else None}...")
                log_info(f"Look generated - image_key (photo_avatar_id): {image_key}")

                # Wait for look to be ready before using with Avatar IV
                if image_key:
                    log_info(f"Waiting for look to be ready...")
                    ready_result = looks_gen.wait_for_look_ready(image_key, max_wait_seconds=120, poll_interval=5)

                    if not ready_result.get('ready'):
                        error_msg = ready_result.get('error', 'Look processing did not complete in time')
                        log_error(f"Look not ready: {error_msg}")

                        if not force_fallback:
                            # Reset status back since we're not generating yet
                            supabase_client.table('social_posts').update({
                                'status': post.get('status', 'pending_approval'),
                                'updated_at': datetime.now(SA_TZ).isoformat()
                            }).eq('id', post_id).execute()

                            return jsonify({
                                'success': False,
                                'needs_confirmation': True,
                                'fallback_reason': 'look_not_ready',
                                'message': f'Avatar IV look not ready: {error_msg}. Would you like to use Photo Avatar instead?'
                            }), 200
                        else:
                            log_info("Falling back to Photo Avatar due to force_fallback=True")
                            image_url = None
                            image_key = None
                            use_avatar_iv = False
                    else:
                        log_info(f"✅ Look is ready, proceeding with Avatar IV")

                if not image_url and not image_key:
                    raise ValueError("Look generation succeeded but no image_url or image_key returned")

                # Save look info to post for later reference
                looks_gen.save_look_to_database(look_result)

            except Exception as e:
                log_error(f"Look generation failed for Avatar IV: {e}")

                if not force_fallback:
                    # Reset status back since we're not generating yet
                    supabase_client.table('social_posts').update({
                        'status': post.get('status', 'pending_approval'),
                        'updated_at': datetime.now(SA_TZ).isoformat()
                    }).eq('id', post_id).execute()

                    return jsonify({
                        'success': False,
                        'needs_confirmation': True,
                        'fallback_reason': 'look_generation_failed',
                        'message': f'Avatar IV look generation failed: {str(e)}. Would you like to use Photo Avatar instead?'
                    }), 200
                else:
                    log_info("Falling back to Photo Avatar due to force_fallback=True")
                    image_url = None
                    use_avatar_iv = False

        # Get fallback avatar_id
        if not avatar_id:
            from social_media.config.avatar_ids import get_avatar_id, DEFAULT_AVATAR_ID

            # Get avatar ID based on content theme, with fallback to default
            avatar_id = os.getenv('DEFAULT_PHOTO_AVATAR_ID') or get_avatar_id(content_theme)

            log_info(f"Using avatar_id: {avatar_id} for content_theme: {content_theme}")

        log_info(f"🎭 Avatar ID: {avatar_id}")
        log_info(f"🖼️ Image URL: {image_url[:50] + '...' if image_url else 'None'}")

        # Generate video - choose API based on whether we have an image
        video_result = None
        api_used = None

        if image_url or image_key:
            # Use Avatar IV (supports gestures) - only if we have a valid image
            log_info("Using Avatar IV API (supports gestures)")
            api_used = 'avatar_iv'
            try:
                video_result = video_gen.generate_avatar_iv_video(
                    script=video_script,
                    image_url=image_url,
                    image_key=image_key,  # ADD THIS - Avatar IV requires this
                    voice_id=voice_id,
                    custom_motion_prompt=motion_prompt,
                    enhance_motion=True,
                    aspect_ratio="9:16",
                    title=post.get('title', 'Regenerated Video'),
                    metadata={
                        'post_id': post_id,
                        'regenerated': True,
                        'motion_prompt': motion_prompt,
                        'content_theme': content_theme
                    }
                )
            except Exception as e:
                log_error(f"Avatar IV generation failed: {e}")
                video_result = None

                # Avatar IV failed - ask for confirmation to use fallback
                if not force_fallback:
                    log_info("Avatar IV failed - requesting confirmation for fallback")

                    supabase_client.table('social_posts').update({
                        'status': post.get('status', 'pending_approval'),
                        'updated_at': datetime.now(SA_TZ).isoformat()
                    }).eq('id', post_id).execute()

                    return jsonify({
                        'success': False,
                        'needs_confirmation': True,
                        'fallback_reason': 'avatar_iv_failed',
                        'message': f'Avatar IV generation failed: {str(e)}. Would you like to try the standard Photo Avatar API instead?',
                        'avatar_id': avatar_id
                    }), 200

        # Use Photo Avatar API (either as primary choice when forced, or as fallback)
        if not video_result and avatar_id:
            log_info("Using Photo Avatar API")
            api_used = 'photo_avatar'
            try:
                video_result = video_gen.generate_avatar_video(
                    script_text=video_script,
                    avatar_id=avatar_id,
                    voice_id=voice_id,
                    style='educational',
                    background_music=True,
                    metadata={
                        'post_id': post_id,
                        'regenerated': True,
                        'motion_prompt': motion_prompt
                    },
                    content_type=content_theme,
                    wait_for_completion=False
                )
            except Exception as e:
                log_error(f"Photo Avatar generation failed: {e}")
                video_result = None

        if not video_result:
            # Reset status on failure
            supabase_client.table('social_posts').update({
                'status': 'pending_approval',
                'updated_at': datetime.now(SA_TZ).isoformat()
            }).eq('id', post_id).execute()

            return jsonify({'success': False, 'error': 'Video generation failed - all methods exhausted'}), 500

        video_id = video_result.get('video_id')
        video_url = video_result.get('video_url')

        log_info(f"📹 Video ID: {video_id}")
        log_info(f"📹 Video URL: {video_url or 'Processing...'}")

        # Update generation_prompt with motion_prompt and image_url
        if motion_prompt:
            gen_data['motion_prompt'] = motion_prompt
        if image_url:
            gen_data['image_url'] = image_url  # Store for scheduler to retrieve later

        # Update post with video info
        update_data = {
            'video_id': video_id,
            'generation_prompt': json.dumps(gen_data),
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        # Add source_image_url if available (HeyGen avatar source image)
        if image_url:
            update_data['source_image_url'] = image_url

        if video_url:
            # Video completed immediately
            update_data['video_url'] = video_url
            update_data['status'] = 'pending_approval'
            update_data['media_generation_completed_at'] = datetime.now(SA_TZ).isoformat()

            supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

            log_info(f"✅ Video regenerated successfully for post {post_id}")

            return jsonify({
                'success': True,
                'message': 'Video regenerated successfully!',
                'video_id': video_id,
                'video_url': video_url,
                'status': 'completed'
            })
        else:
            # Video still processing
            update_data['status'] = 'generating'

            supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

            log_info(f"⏳ Video generation started for post {post_id}, video_id: {video_id}")

            return jsonify({
                'success': True,
                'message': 'Video generation started. Check back in a few minutes.',
                'video_id': video_id,
                'status': 'processing'
            })

    except Exception as e:
        log_error(f"❌ Regenerate video failed: {e}")
        import traceback
        log_error(traceback.format_exc())

        # Try to reset status
        try:
            supabase_client.table('social_posts').update({
                'status': 'pending_approval',
                'updated_at': datetime.now(pytz.timezone('Africa/Johannesburg')).isoformat()
            }).eq('id', post_id).execute()
        except:
            pass

        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/regenerate-thumbnail/<string:post_id>', methods=['POST'])
def api_regenerate_thumbnail(post_id: str):
    """Regenerate thumbnail for a video post without regenerating the video."""
    log_info(f"📥 Request: /api/dashboard/regenerate-thumbnail/{post_id}")

    try:
        # Fetch the post
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()
        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]

        # Get required data
        source_image_url = post.get('source_image_url') or post.get('thumbnail_url')
        reel_title = post.get('reel_title') or post.get('title')

        if not source_image_url:
            return jsonify({'success': False, 'error': 'No source image URL available for thumbnail generation'}), 400

        if not reel_title:
            return jsonify({'success': False, 'error': 'No reel_title or title available for thumbnail generation'}), 400

        log_info(f"🎨 Regenerating thumbnail for post {post_id}")
        log_info(f"📝 Title: {reel_title[:50]}...")
        log_info(f"🖼️ Source: {source_image_url[:50]}...")

        # Generate thumbnail
        from social_media.thumbnail_generator import ThumbnailGenerator
        import tempfile

        thumbnail_gen = ThumbnailGenerator()
        local_thumbnail_path = os.path.join(tempfile.gettempdir(), f"thumbnail_{post_id}.jpg")

        thumbnail_result = thumbnail_gen.generate_thumbnail(
            image_url=source_image_url,
            title_text=reel_title,
            output_path=local_thumbnail_path
        )

        if not thumbnail_result.get('success'):
            return jsonify({'success': False, 'error': f"Thumbnail generation failed: {thumbnail_result.get('error')}"}), 500

        log_info(f"✅ Thumbnail generated locally: {local_thumbnail_path}")

        # Upload to Supabase Storage
        from utils.supabase_storage import get_storage_client

        storage_client = get_storage_client()
        if not storage_client:
            return jsonify({'success': False, 'error': 'Storage client not available'}), 500

        storage_dest = f"thumbnails/{post_id}.jpg"
        upload_success, public_url, upload_error = storage_client.upload_file(
            bucket='media',
            file_path=local_thumbnail_path,
            destination_path=storage_dest,
            content_type='image/jpeg'
        )

        if not upload_success or not public_url:
            return jsonify({'success': False, 'error': f"Upload failed: {upload_error}"}), 500

        log_info(f"✅ Thumbnail uploaded: {public_url}")

        # Clean up local file
        try:
            os.remove(local_thumbnail_path)
        except Exception:
            pass

        # Update database with cache buster to force refresh
        import time
        cache_buster = int(time.time())
        thumbnail_url_with_cache = f"{public_url}?v={cache_buster}"

        supabase_client.table('social_posts').update({
            'thumbnail_url': thumbnail_url_with_cache,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('id', post_id).execute()

        log_info(f"✅ Post {post_id} thumbnail updated successfully")

        return jsonify({
            'success': True,
            'message': 'Thumbnail regenerated successfully',
            'thumbnail_url': thumbnail_url_with_cache
        })

    except Exception as e:
        log_error(f"❌ Regenerate thumbnail failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/fetch-videos', methods=['POST'])
def api_fetch_videos_now():
    """Manually trigger video fetching from HeyGen"""
    try:
        log_info("📥 Manual video fetch triggered from dashboard")

        # First check what posts are in generating status
        result = supabase_client.table('social_posts').select('*').eq('status', 'generating').execute()
        log_info(f"Found {len(result.data)} posts with status='generating'")

        for post in result.data:
            log_info(f"Post {post['id']}: video_id={post.get('video_id')}, post_type={post.get('post_type')}")

        # Import and run the fetch job immediately
        if scheduler:
            scheduler.fetch_orphaned_videos_job()

            # Check status after fetch
            result_after = supabase_client.table('social_posts').select('*').eq('status', 'generating').execute()
            log_info(f"After fetch: {len(result_after.data)} posts still in 'generating' status")

            return jsonify({
                'message': 'Video fetch completed',
                'before_count': len(result.data),
                'after_count': len(result_after.data),
                'success': True
            }), 200
        else:
            return jsonify({
                'message': 'Scheduler not available',
                'success': False
            }), 503

    except Exception as e:
        log_error(f"Error in manual fetch: {str(e)}")
        log_error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dashboard/approve-all', methods=['POST'])
def api_approve_all_posts():
    """API: Approve all pending posts"""
    log_info("📥 Request: /api/dashboard/approve-all")

    # Check Supabase connection
    if not app.config.get('SUPABASE_CONNECTED'):
        log_error("❌ Supabase not connected")
        return api_error_response('Database not connected', 503)

    if not supabase_client:
        log_error("❌ Supabase client is None")
        return api_error_response('Database client not available', 503)

    try:
        # First, check if any pending posts exist
        log_info("🔍 Checking for pending posts")
        check_result = supabase_client.table('social_posts').select('id, platform, content').eq('status', 'pending_approval').execute()

        posts_found = len(check_result.data) if check_result.data else 0
        log_info(f"📊 Found {posts_found} pending posts")

        if posts_found == 0:
            log_info("ℹ️ No pending posts to approve")
            return jsonify({
                'success': True,
                'approved_count': 0,
                'posts_found': 0,
                'message': 'No pending posts to approve'
            })

        # Update all pending posts to scheduled
        start_time = datetime.now()
        result = supabase_client.table('social_posts').update({
            'status': 'scheduled',
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('status', 'pending_approval').execute()

        update_time = (datetime.now() - start_time).total_seconds()

        approved_count = len(result.data) if result.data else 0
        log_info(f"✅ Approved {approved_count}/{posts_found} posts in {update_time:.2f}s")

        if approved_count != posts_found:
            log_warning(f"⚠️ Mismatch: Found {posts_found} posts but only approved {approved_count}")

        return jsonify({
            'success': True,
            'approved_count': approved_count,
            'posts_found': posts_found,
            'update_time': update_time,
            'message': f'Approved {approved_count} posts'
        })

    except Exception as e:
        log_error(f"❌ Error approving all posts: {e}")
        log_error(traceback.format_exc())
        return api_error_response(
            str(e),
            500,
            {'traceback': traceback.format_exc()}
        )


@app.route('/api/dashboard/fresh-start', methods=['POST'])
def api_fresh_start():
    """Delete all old posts and create fresh launch content with comprehensive error handling."""
    if not supabase_client:
        log_error("❌ Fresh start failed: Database not connected")
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        from social_media.launch_content import clear_all_test_posts, seed_launch_content

        log_info("🔄 Starting fresh start process...")

        # Step 1: Delete old/test posts
        log_info("📝 Step 1: Deleting old/test posts...")
        try:
            deleted_count = clear_all_test_posts(supabase_client)
            log_info(f"✅ Successfully deleted {deleted_count} old posts")
        except Exception as delete_error:
            log_error(f"❌ Failed to delete old posts: {delete_error}")
            return jsonify({
                'success': False,
                'error': f'Failed to delete old posts: {str(delete_error)}',
                'step': 'delete'
            }), 500

        # Step 2: Seed fresh launch content
        log_info("📝 Step 2: Generating and saving fresh launch content...")
        try:
            post_ids = seed_launch_content(supabase_client)
            created_count = len(post_ids)

            if created_count == 0:
                log_error("❌ Fresh start failed: No posts were created")
                return jsonify({
                    'success': False,
                    'error': 'No posts were created. Check logs for details.',
                    'deleted_count': deleted_count,
                    'created_count': 0,
                    'step': 'create'
                }), 500

            log_info(f"✅ Fresh start complete: {created_count} posts created successfully")

            return jsonify({
                'success': True,
                'deleted_count': deleted_count,
                'created_count': created_count,
                'post_ids': post_ids,
                'message': f'✅ Fresh start complete: Deleted {deleted_count} old posts, created {created_count} fresh launch posts'
            })

        except Exception as create_error:
            log_error(f"❌ Failed to create fresh posts: {create_error}")
            import traceback
            log_error(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': f'Failed to create fresh posts: {str(create_error)}',
                'deleted_count': deleted_count,
                'created_count': 0,
                'step': 'create'
            }), 500

    except Exception as e:
        log_error(f"❌ Fresh start failed with unexpected error: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Unexpected error during fresh start: {str(e)}',
            'step': 'unknown'
        }), 500


@app.route('/api/dashboard/generate-launch-content', methods=['POST'])
def api_generate_launch_content():
    """Generate the 'Meet Refiloe' introduction post using the curated script."""
    log_info("📥 Request: /api/dashboard/generate-launch-content")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        from social_media.launch_content import clear_all_test_posts
        from database import SocialMediaDatabase
        import json
        from datetime import datetime, timedelta
        import pytz

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        # Step 1: Clear ALL existing pending posts
        log_info("🗑️ Clearing existing pending posts...")
        deleted_count = clear_all_test_posts(supabase_client)
        log_info(f"✅ Deleted {deleted_count} existing posts")

        # Step 2: Use the curated "Meet Refiloe" introduction script
        log_info("🚀 Creating 'Meet Refiloe' introduction post...")

        # The proper introduction script (from launch_content.py)
        video_script = """You know that moment—5:47 AM, gym bag packed, coffee in hand—when you realise you're not just tired. You're drowning.

Not in clients. In everything around the clients.

The scheduling chaos. The payment awkwardness. The endless WhatsApp pings before your eyes are even open.

I've spent years studying what separates trainers who burn out from those who build something sustainable. And here's the uncomfortable truth: it's rarely about training knowledge. It's about the business side—the part nobody taught us.

That's why this page exists. Not for motivation porn. For real talk about the trainer struggle. Time-saving hacks that actually work. Ways to grow without sacrificing your sanity.

Because you didn't become a trainer to drown in admin.

You became a trainer to change lives.

If that resonates, stick around. This is just the beginning. 💪"""

        # Caption for the post (what shows on Facebook)
        content_text = """You know that moment—5:47 AM, gym bag packed, coffee in hand—when you realise you're not just tired. You're drowning. 😤

Not in clients. In everything AROUND the clients.

I've spent years studying what separates trainers who burn out from those who build something sustainable.

That's why this page exists:
→ Real talk about the trainer struggle
→ Time-saving hacks that actually work
→ Ways to grow without sacrificing your sanity

Because you didn't become a trainer to drown in admin.
You became a trainer to change lives. 💪

If that resonates, hit follow. This is just the beginning.

#PersonalTrainer #FitnessCoach #TrainerLife #PTLife #FitnessBusiness #TrainerTips"""

        # Global hashtags
        global_hashtags = [
            "#PersonalTrainer", "#FitnessCoach", "#TrainerLife",
            "#PTLife", "#FitnessBusiness", "#TrainerTips"
        ]

        # Schedule for 14:00 SAST today or tomorrow if past 14:00
        now = datetime.now(SA_TZ)
        scheduled_time = now.replace(hour=14, minute=0, second=0, microsecond=0)
        if now.hour >= 14:
            scheduled_time = scheduled_time + timedelta(days=1)

        log_info(f"📅 Scheduled time: {scheduled_time.isoformat()}")

        # Generate image prompt
        image_prompt = generate_scroll_stopping_image_prompt('introduction', content_text, 'video')

        # Metadata
        metadata = {
            "day": 1,
            "post_number": 1,
            "video_script": video_script,
            "launch_content": True,
            "target_audience": "global",
            "content_theme": "introduction",
            "post_title": "Meet Refiloe - Introduction",
            "image_prompt": image_prompt
        }

        # Save the post
        db = SocialMediaDatabase(supabase_client)

        log_info("💾 Saving introduction post to database...")
        post_data = {
            'platform': 'facebook',
            'content_text': content_text,
            'post_type': 'video',
            'scheduled_time': scheduled_time.isoformat(),
            'content_theme': 'introduction',
            'title': 'Meet Refiloe - Introduction',
            'hashtags': global_hashtags,
            'generation_prompt': json.dumps(metadata),
            'status': 'pending_approval',
            'video_duration': 60,
            'image_prompt': image_prompt
        }
        post_id = db.save_post(post_data)

        if not post_id:
            log_error("❌ Failed to save post to database")
            return jsonify({'success': False, 'error': 'Failed to save introduction post'}), 500

        log_info(f"✅ Saved 'Meet Refiloe' introduction post: {post_id}")

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'created_count': 1,
            'post_ids': [post_id],
            'scheduled_time': scheduled_time.isoformat(),
            'message': f'✅ "Meet Refiloe" introduction post created! Scheduled for {scheduled_time.strftime("%b %d at %H:%M")} SAST.'
        })

    except Exception as e:
        log_error(f"❌ Generate launch content failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


def generate_weekly_content_in_background(start_date, weekly_themes, global_hashtags, config, supabase_client_ref, media_type='all', existing_dates=None):
    """Background worker function to generate weekly content without blocking the request.

    Args:
        start_date: The starting date (today) for content generation
        weekly_themes: List of theme configurations for each day
        global_hashtags: Hashtags to include in posts
        config: Configuration dictionary
        supabase_client_ref: Supabase client reference
        media_type: Filter for post types. When not 'all', forces all posts to use this type.
                   Options: 'all', 'image', 'video', 'carousel', 'text_card'
        existing_dates: Set of dates that already have posts of the specified type (to skip)
    """
    global generation_status
    from social_media.content_generator import ContentGenerator
    from database import SocialMediaDatabase
    import os
    import json
    from datetime import timedelta
    import pytz
    import time

    SA_TZ = pytz.timezone('Africa/Johannesburg')

    # Calculate end_date for logging
    from datetime import timedelta as td_temp
    end_date = start_date + td_temp(days=6)

    log_info("=" * 60)
    log_info("WEEKLY CONTENT GENERATION - BACKGROUND TASK STARTED")
    log_info(f"Media type: {media_type}")
    log_info(f"Start date: {start_date}")
    log_info(f"End date: {end_date}")
    log_info("=" * 60)

    # Check if Leonardo API key is configured
    leonardo_api_key = os.environ.get('LEONARDO_API_KEY')
    if not leonardo_api_key:
        log_error("❌ LEONARDO_API_KEY not set - cannot generate images!")
        log_error("   Posts will be created without images")
    else:
        log_info(f"✅ Leonardo API key configured (length: {len(leonardo_api_key)})")

    # Initialize Leonardo generator for auto image generation
    leonardo = None
    if leonardo_api_key:
        try:
            from social_media.leonardo_generator import LeonardoGenerator, LeonardoGenerationError
            leonardo = LeonardoGenerator(supabase_client=supabase_client_ref)
            log_info("🎨 Leonardo AI initialized for automatic image generation")
        except Exception as e:
            log_warning(f"⚠️ Failed to initialize Leonardo AI: {e}. Images will need to be generated manually.")

    # Initialize existing_dates if not provided
    if existing_dates is None:
        existing_dates = set()

    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
        generator = ContentGenerator(config_path, supabase_client_ref)
        db = SocialMediaDatabase(supabase_client_ref)

        for day_offset, theme_config in enumerate(weekly_themes):
            post_type = theme_config.get('post_type', 'video')

            # Override post_type if media_type filter is specified
            if media_type and media_type != 'all':
                post_type = media_type

            posting_time = get_posting_time_for_content_type(config, post_type)
            hour, minute = map(int, posting_time.split(':'))
            scheduled_time = start_date.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day_offset)

            # Check if this date already has a post of the specified type - skip if so
            scheduled_date = scheduled_time.date()
            if scheduled_date in existing_dates:
                log_info(f"⏭️ [Background] Skipping Day {day_offset + 1} ({scheduled_date}): Already has {post_type} post scheduled")
                generation_status['skipped'].append({
                    'day': day_offset + 1,
                    'theme': theme_config['theme'],
                    'description': theme_config['description'],
                    'date': scheduled_date.isoformat(),
                    'reason': f'Already has {post_type} post scheduled'
                })
                continue

            try:
                log_info(f"📝 Generating post for day {day_offset + 1}: {scheduled_time.strftime('%Y-%m-%d')} at {scheduled_time.strftime('%H:%M')} SAST")
                log_info(f"   Post type: {post_type}")
                log_info(f"   Theme: {theme_config.get('theme', 'unknown')}")
                generation_status['current_action'] = f"Generating Day {day_offset + 1}: {theme_config['description']}"

                # Generate content based on post type
                if post_type == 'video':
                    script_data = generator.create_video_script(
                        theme=theme_config['theme'],
                        duration=45,
                        style='educational'
                    )

                    # Extract the script array for generation_prompt
                    video_script = script_data.get('script', [])
                    reel_title = script_data.get('reel_title', '')

                    # Generate a readable caption from the script for content_text
                    if video_script and isinstance(video_script, list):
                        caption_parts = []
                        if reel_title:
                            caption_parts.append(reel_title)
                            caption_parts.append('')

                        for segment in video_script[:3]:
                            if isinstance(segment, dict) and segment.get('text'):
                                caption_parts.append(segment['text'])

                        hashtags = script_data.get('hashtags', [])
                        if hashtags:
                            caption_parts.append('')
                            caption_parts.append(' '.join(hashtags))

                        content_text = '\n\n'.join(caption_parts)
                    else:
                        content_text = str(video_script)
                elif post_type == 'carousel':
                    content = generator.generate_single_post(
                        theme=theme_config['theme'],
                        format_type='carousel_style'
                    )
                    content_text = content.get('content', '') or content.get('caption', '')
                    if not content_text:
                        log_warning(f"No content generated for carousel {theme_config['theme']}")
                        content_text = ''
                    video_script = None
                    reel_title = content.get('title', '')
                else:
                    content = generator.generate_single_post(
                        theme=theme_config['theme'],
                        format_type='single_image_with_caption'
                    )
                    content_text = content.get('content', '') or content.get('caption', '')
                    if not content_text:
                        log_warning(f"No content generated for image {theme_config['theme']}")
                        content_text = ''
                    video_script = None
                    reel_title = content.get('title', '')

                metadata = {
                    "day": day_offset + 1,
                    "theme_description": theme_config['description'],
                    "video_script": video_script,
                    "weekly_content": True,
                    "target_audience": "global",
                    "image_prompt": generate_scroll_stopping_image_prompt(theme_config['theme'], content_text, post_type)
                }

                post_data = {
                    'platform': 'facebook',
                    'caption_text': content_text,
                    'content_text': content_text,
                    'post_type': post_type,
                    'media_type': post_type,
                    'scheduled_time': scheduled_time.isoformat(),
                    'content_theme': theme_config['theme'],
                    'title': reel_title,
                    'reel_title': reel_title,
                    'hashtags': global_hashtags,
                    'generation_prompt': json.dumps(metadata),
                    'status': 'pending_approval',
                    'is_pinned': False,
                    'image_prompt': generate_scroll_stopping_image_prompt(theme_config['theme'], content_text, theme_config['post_type'])
                }

                post_id = db.save_post(post_data)

                if post_id:
                    post_info = {
                        'day': day_offset + 1,
                        'theme': theme_config['theme'],
                        'description': theme_config['description'],
                        'date': scheduled_time.strftime('%Y-%m-%d'),
                        'post_id': post_id,
                        'image_generated': False
                    }
                    log_info(f"✅ Post record created: {post_id}")

                    # Auto-generate Leonardo AI image for image posts
                    image_url = None  # Track for end-of-day logging
                    if post_type == 'image' and leonardo is not None:
                        image_prompt = post_data.get('image_prompt', '')
                        if image_prompt:
                            log_info(f"🎨 Starting Leonardo AI image generation...")
                            log_info(f"   Image prompt: {image_prompt[:100]}...")
                            content_type = theme_config.get('content_type', 'motivational')
                            log_info(f"   Content type: {content_type}")
                            try:
                                generation_status['current_action'] = f"Generating image for Day {day_offset + 1}"

                                log_info(f"🔄 Calling Leonardo API...")

                                # Generate the image
                                result = leonardo.generate_image(
                                    prompt=image_prompt,
                                    content_type=content_type,
                                )

                                image_url = result.get('image_url')

                                if image_url:
                                    log_info(f"✅ Leonardo image generated successfully!")
                                    log_info(f"   Image URL: {image_url}")
                                    log_info(f"🔄 Updating post {post_id} with image_url...")
                                    # Update the post with the generated image URL
                                    db.update_post(post_id, {'image_url': image_url})
                                    log_info(f"✅ Post {post_id} updated with image_url")
                                    post_info['image_generated'] = True
                                    post_info['image_url'] = image_url
                                else:
                                    log_warning(f"⚠️ [Background] Leonardo returned no image URL for post {post_id}")

                                # Add delay between Leonardo API calls to avoid rate limiting
                                time.sleep(2)

                            except Exception as e:
                                # Import LeonardoGenerationError if not already imported
                                from social_media.leonardo_generator import LeonardoGenerationError
                                log_error(f"❌ Leonardo image generation FAILED for post {post_id}")
                                log_error(f"   Error: {str(e)}")
                                log_error(f"   Post created without image - manual generation required")
                                # Post still created, just without image - user can retry manually
                                post_info['image_error'] = str(e)

                    # End of day logging
                    log_info(f"✅ Day {day_offset + 1} complete - Post ID: {post_id}, Has image: {bool(image_url)}")
                    log_info("-" * 40)

                    generation_status['successful'].append(post_info)
                else:
                    generation_status['failed'].append({
                        'day': day_offset + 1,
                        'theme': theme_config['theme'],
                        'description': theme_config['description'],
                        'date': scheduled_time.strftime('%Y-%m-%d'),
                        'error': 'Failed to save post to database (no post_id returned)'
                    })
                    log_error(f"❌ [Background] Failed to save Day {day_offset + 1}: No post_id returned")

            except Exception as e:
                error_message = str(e)
                generation_status['failed'].append({
                    'day': day_offset + 1,
                    'theme': theme_config['theme'],
                    'description': theme_config['description'],
                    'date': scheduled_time.strftime('%Y-%m-%d') if scheduled_time else 'unknown',
                    'error': error_message
                })
                log_error(f"❌ [Background] Failed to generate Day {day_offset + 1}: {e}")
                continue

        generation_status['current_action'] = 'Complete'

        # Calculate image statistics
        posts_with_images = sum(1 for p in generation_status['successful'] if p.get('image_generated', False))
        posts_without_images = len(generation_status['successful']) - posts_with_images

        log_info("=" * 60)
        log_info("WEEKLY CONTENT GENERATION - COMPLETE")
        log_info(f"Total posts created: {len(generation_status['successful'])}")
        log_info(f"Total posts failed: {len(generation_status['failed'])}")
        log_info(f"Posts with images: {posts_with_images}")
        log_info(f"Posts without images: {posts_without_images}")
        log_info("=" * 60)

    except Exception as e:
        log_error(f"❌ [Background] Generate weekly content failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        generation_status['current_action'] = f'Error: {str(e)}'
    finally:
        generation_status['is_running'] = False


@app.route('/api/dashboard/generate-weekly-content', methods=['POST'])
def api_generate_weekly_content():
    """Generate posts for the next 7 days, filling gaps where posts are missing.

    This is GAP-FILLING - it starts from today and only generates posts for days
    that don't already have a post of the specified type (media_type) scheduled.
    Days with existing posts are skipped.

    Runs in background to avoid timeout - check /api/dashboard/generation-status for progress.
    """
    global generation_status

    log_info("=" * 60)
    log_info("WEEKLY CONTENT GENERATION - ENDPOINT CALLED")
    log_info(f"Request data: {request.get_json()}")
    data = request.get_json() or {}
    media_type_preview = data.get('media_type', 'all')
    log_info(f"Media type filter: {media_type_preview}")
    log_info("=" * 60)

    # Check if generation is already running
    if generation_status['is_running']:
        return jsonify({
            'success': False,
            'message': 'Generation already in progress. Check /api/dashboard/generation-status for progress.',
            'status': 'already_running'
        }), 409

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        from datetime import datetime, timedelta
        import pytz

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        # Extract media_type filter from request (already parsed above)
        media_type = media_type_preview

        # Step 1: Start from TODAY and find existing posts for the next 7 days
        today = datetime.now(SA_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = today
        end_date_range = today + timedelta(days=7)

        log_info(f"📅 Checking existing posts from {today.date()} to {end_date_range.date()} for post_type='{media_type}'")

        # Fetch posts scheduled within the next 7 days
        result = supabase_client.table('social_posts').select('scheduled_time, status, post_type').order(
            'scheduled_time', desc=False
        ).execute()

        # Filter in Python for:
        # - Active statuses
        # - Matching post_type (if media_type filter specified)
        # - Within the next 7 days
        existing_dates = set()
        if result.data:
            active_statuses = ['pending_approval', 'scheduled', 'approved']
            for post in result.data:
                if post.get('status') not in active_statuses:
                    continue
                if not post.get('scheduled_time'):
                    continue

                # Filter by post_type if media_type is specified
                if media_type and media_type != 'all':
                    if post.get('post_type') != media_type:
                        continue

                # Parse the scheduled time and extract the date
                try:
                    scheduled_str = post['scheduled_time']
                    if isinstance(scheduled_str, str):
                        scheduled_dt = datetime.fromisoformat(scheduled_str.replace('Z', '+00:00'))
                        scheduled_dt = scheduled_dt.astimezone(SA_TZ)
                    else:
                        scheduled_dt = scheduled_str

                    # Check if within the next 7 days
                    if today <= scheduled_dt < end_date_range:
                        existing_dates.add(scheduled_dt.date())
                except Exception as e:
                    log_warning(f"⚠️ Could not parse scheduled_time '{post.get('scheduled_time')}': {e}")
                    continue

        log_info(f"🔍 Checking for existing {media_type} posts in next 7 days...")
        log_info(f"📊 Found {len(existing_dates)} days already covered: {sorted(existing_dates)}")
        days_to_generate = 7 - len(existing_dates)
        log_info(f"📊 Days to generate: {days_to_generate}")

        # Weekly themes rotation - cycles through expanded theme categories
        weekly_themes = [
            {"theme": "mindset_psychology", "post_type": "video", "description": "Monday Motivation"},
            {"theme": "admin_hacks", "post_type": "video", "description": "Tips Tuesday"},
            {"theme": "wellness_lifestyle", "post_type": "carousel", "description": "Wellness Wednesday"},
            {"theme": "relatable_trainer_life", "post_type": "video", "description": "Throwback Thursday"},
            {"theme": "content_creator_tips", "post_type": "image", "description": "Feature Friday"},
            {"theme": "business_coaching", "post_type": "video", "description": "Strategy Saturday"},
            {"theme": "engagement_questions", "post_type": "image", "description": "Sunday Engagement"},
        ]

        # Global hashtags to use
        global_hashtags = [
            "#PersonalTrainer", "#FitnessCoach", "#TrainerLife",
            "#PTLife", "#FitnessBusiness", "#TrainerTips",
            "#FitnessIndustry", "#OnlineTrainer"
        ]

        # Get posting time config
        from social_media.config_loader import load_config
        config = load_config('social_media/config.yaml')

        # Calculate end date for response (next 7 days starting from today)
        end_date = start_date + timedelta(days=6)

        # days_to_generate already calculated above (days_to_fill is alias for consistency)
        days_to_fill = days_to_generate

        # Determine if images will be generated (affects timing message)
        # Check if LEONARDO_API_KEY is available and if we're generating image posts
        import os
        leonardo_available = bool(os.environ.get('LEONARDO_API_KEY'))
        will_generate_images = leonardo_available and (media_type == 'image' or media_type == 'all')

        # Initialize generation status
        generation_status['is_running'] = True
        generation_status['successful'] = []
        generation_status['failed'] = []
        generation_status['skipped'] = []
        generation_status['start_time'] = datetime.now(SA_TZ).isoformat()
        generation_status['start_date'] = start_date.strftime('%Y-%m-%d')
        generation_status['end_date'] = end_date.strftime('%Y-%m-%d')
        generation_status['existing_dates'] = [d.isoformat() for d in sorted(existing_dates)]
        generation_status['current_action'] = 'Starting content generation...'
        generation_status['generating_images'] = will_generate_images

        # Start background thread with existing_dates
        thread = threading.Thread(
            target=generate_weekly_content_in_background,
            args=(start_date, weekly_themes, global_hashtags, config, supabase_client, media_type, existing_dates)
        )
        thread.daemon = True
        thread.start()

        log_info(f"🚀 Started background generation for {start_date.date()} - {end_date.date()} (filling {days_to_fill} gaps, skipping {len(existing_dates)} existing)")

        # Build response message with appropriate timing estimate
        if will_generate_images:
            message = f'Generating weekly content with images... This may take 5-7 minutes. Filling {days_to_fill} gaps from {start_date.strftime("%b %d")} - {end_date.strftime("%b %d")}.'
        else:
            message = f'Generation started for {start_date.strftime("%b %d")} - {end_date.strftime("%b %d")}. Filling {days_to_fill} gaps, skipping {len(existing_dates)} existing posts.'

        return jsonify({
            'success': True,
            'message': message,
            'status': 'processing',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'days_to_generate': days_to_fill,
            'existing_dates': [d.isoformat() for d in sorted(existing_dates)],
            'generating_images': will_generate_images,
            'check_status_url': '/api/dashboard/generation-status'
        })

    except Exception as e:
        log_error(f"❌ Generate weekly content failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        generation_status['is_running'] = False
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/generation-status', methods=['GET'])
def api_generation_status():
    """Get the status of background weekly content generation.

    Returns:
        JSON with is_running, successful count, skipped count, failed count, and details
    """
    return jsonify({
        'is_running': generation_status['is_running'],
        'successful': len(generation_status['successful']),
        'skipped': len(generation_status.get('skipped', [])),
        'failed': len(generation_status['failed']),
        'start_time': generation_status['start_time'],
        'start_date': generation_status['start_date'],
        'end_date': generation_status['end_date'],
        'existing_dates': generation_status.get('existing_dates', []),
        'current_action': generation_status.get('current_action', ''),
        'generating_images': generation_status.get('generating_images', False),
        'details': {
            'successful_posts': generation_status['successful'],
            'skipped_posts': generation_status.get('skipped', []),
            'failed_posts': generation_status['failed']
        }
    })


@app.route('/api/dashboard/generate-text-card', methods=['POST'])
def api_generate_text_card():
    """Generate a single text card post.

    Optional JSON body:
    {
        "content_type": "quote" | "tip" | "educational" | "motivation",  // optional
        "scheduled_date": "2024-12-22",  // optional, defaults to tomorrow
        "scheduled_time": "16:00"  // optional, defaults to 16:00
    }

    Returns:
        JSON with success, post_id, scheduled_time, content_type
    """
    log_info("📥 Request: /api/dashboard/generate-text-card")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        from social_media.content_generator import ContentGenerator
        from social_media.text_card_generator import TextCardGenerator
        from database import SocialMediaDatabase
        from utils.supabase_storage import get_storage_client
        import os
        import json
        from datetime import datetime, timedelta
        import pytz

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        # Parse request data
        data = request.get_json() or {}
        content_type = data.get('content_type')  # Can be None for random selection
        scheduled_date = data.get('scheduled_date')
        scheduled_time_str = data.get('scheduled_time', '16:00')

        # Determine scheduled time
        if scheduled_date:
            # Parse provided date
            date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d')
            scheduled_time = SA_TZ.localize(datetime.combine(date_obj.date(), datetime.strptime(scheduled_time_str, '%H:%M').time()))
        else:
            # Default to tomorrow at 16:00 SAST
            tomorrow = datetime.now(SA_TZ) + timedelta(days=1)
            scheduled_time = tomorrow.replace(hour=16, minute=0, second=0, microsecond=0)

        log_info(f"📅 Generating text card for {scheduled_time.strftime('%Y-%m-%d %H:%M')} SAST")

        # Initialize generators
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
        content_gen = ContentGenerator(config_path, supabase_client)
        text_card_gen = TextCardGenerator(config_path)
        db = SocialMediaDatabase(supabase_client)

        # Generate text card content
        content = content_gen.generate_text_card_content(content_type)

        if not content or 'type' not in content:
            log_error("Failed to generate text card content")
            return jsonify({'success': False, 'error': 'Failed to generate content'}), 500

        actual_content_type = content['type']
        log_info(f"📝 Generated {actual_content_type} text card")

        # Generate text card image
        image_content = {k: v for k, v in content.items() if k not in ['type', 'caption', 'hashtags']}
        image_path = text_card_gen.generate_text_card(image_content, actual_content_type)

        # Upload image to Supabase storage
        storage_client = get_storage_client()
        if not storage_client:
            log_error("Storage client not available")
            return jsonify({'success': False, 'error': 'Storage client not available'}), 500

        storage_path = f"text-cards/{uuid.uuid4().hex[:8]}.png"
        upload_success, image_url, upload_error = storage_client.upload_file(
            bucket='media',
            file_path=image_path,
            destination_path=storage_path,
            content_type='image/png'
        )

        if not upload_success or not image_url:
            log_error(f"Failed to upload text card image: {upload_error}")
            return jsonify({'success': False, 'error': f'Failed to upload image: {upload_error}'}), 500

        # Prepare metadata
        metadata = {
            'text_card_type': actual_content_type,
            'text_card_content': image_content,
            'generated_at': datetime.now(SA_TZ).isoformat()
        }

        # Save to database
        post_data = {
            'platform': 'facebook',
            'content_text': content.get('caption', ''),
            'post_type': 'text_card',
            'scheduled_time': scheduled_time.isoformat(),
            'image_url': image_url,
            'hashtags': json.dumps(content.get('hashtags', [])) if content.get('hashtags') else None,
            'generation_prompt': json.dumps(metadata),
            'status': 'pending_approval',
            'is_pinned': False
        }

        post_id = db.save_post(post_data)

        if post_id:
            log_info(f"✅ Created text card post: {post_id}")
            return jsonify({
                'success': True,
                'post_id': post_id,
                'scheduled_time': scheduled_time.isoformat(),
                'content_type': actual_content_type,
                'image_url': image_url
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to save post'}), 500

    except Exception as e:
        log_error(f"❌ Generate text card failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/generate-weekly-text-cards', methods=['POST'])
def api_generate_weekly_text_cards():
    """Generate 7 text card posts for the upcoming week (1 per day at 4pm SAST).

    This is ADDITIVE - finds the latest scheduled text_card and adds 7 more days after it.
    Skips days that already have a text_card scheduled at 4pm.

    Returns:
        JSON with success, posts_created (count), posts_skipped (count),
        first_date, last_date, post_ids (list)
    """
    log_info("📥 Request: /api/dashboard/generate-weekly-text-cards")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        from social_media.content_generator import ContentGenerator
        from social_media.text_card_generator import TextCardGenerator
        from database import SocialMediaDatabase
        from utils.supabase_storage import get_storage_client
        import os
        import json
        from datetime import datetime, timedelta
        import pytz

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        from social_media.config_loader import load_config
        config = load_config('social_media/config.yaml')
        text_card_time = get_posting_time_for_content_type(config, 'text_card')
        hour, minute = map(int, text_card_time.split(':'))

        # Step 1: Find the latest scheduled text_card post
        log_info("📅 Finding latest scheduled text_card...")

        # Fetch text_card posts (SupabaseRestClient doesn't support .in_() filtering)
        result = supabase_client.table('social_posts').select('scheduled_time').eq(
            'post_type', 'text_card'
        ).order('scheduled_time', desc=True).execute()

        # Filter in Python for active statuses
        latest_scheduled = None
        if result.data:
            active_statuses = ['pending_approval', 'scheduled', 'approved', 'pending_media_approval']
            filtered_posts = [
                post for post in result.data
                if post.get('status') in active_statuses and post.get('scheduled_time')
            ]
            if filtered_posts:
                latest_scheduled = filtered_posts[0]['scheduled_time']

        if latest_scheduled:
            # Parse the latest scheduled time
            try:
                if isinstance(latest_scheduled, str):
                    latest_date = datetime.fromisoformat(latest_scheduled.replace('Z', '+00:00'))
                    latest_date = latest_date.astimezone(SA_TZ)
                else:
                    latest_date = latest_scheduled
                # Start from the day after the latest scheduled text_card
                start_date = latest_date.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
                log_info(f"📅 Latest text_card: {latest_date.date()}. Starting from: {start_date.date()}")
            except Exception as e:
                log_warning(f"⚠️ Could not parse latest date '{latest_scheduled}': {e}. Using tomorrow.")
                start_date = datetime.now(SA_TZ).replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
        else:
            # No existing text_card posts, start from tomorrow
            start_date = datetime.now(SA_TZ).replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
            log_info(f"📅 No existing text_card posts. Starting from: {start_date.date()}")

        # Step 2: Initialize generators
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
        content_gen = ContentGenerator(config_path, supabase_client)
        text_card_gen = TextCardGenerator(config_path)
        db = SocialMediaDatabase(supabase_client)

        # Step 3: Generate 7 text cards
        created_ids = []
        skipped_count = 0
        content_types = ['quote', 'tip', 'educational', 'motivation']

        for day_offset in range(7):
            scheduled_time = start_date + timedelta(days=day_offset)

            try:
                # Check if text_card already exists for this day at 4pm
                check_result = supabase_client.table('social_posts').select('id, status').eq(
                    'post_type', 'text_card'
                ).eq(
                    'scheduled_time', scheduled_time.isoformat()
                ).execute()

                # Filter in Python for active statuses
                active_statuses = ['pending_approval', 'scheduled', 'approved', 'pending_media_approval']
                existing_posts = [
                    post for post in (check_result.data or [])
                    if post.get('status') in active_statuses
                ]

                if existing_posts:
                    log_info(f"⏭️  Skipping {scheduled_time.date()} - text_card already exists")
                    skipped_count += 1
                    continue

                log_info(f"📝 Generating text card {day_offset + 1}/7 for {scheduled_time.date()}")

                # Rotate through content types
                content_type = content_types[day_offset % len(content_types)]

                # Generate content
                content = content_gen.generate_text_card_content(content_type)

                if not content or 'type' not in content:
                    log_error(f"Failed to generate content for day {day_offset + 1}")
                    skipped_count += 1
                    continue

                actual_content_type = content['type']

                # Generate image
                image_content = {k: v for k, v in content.items() if k not in ['type', 'caption', 'hashtags']}
                image_path = text_card_gen.generate_text_card(image_content, actual_content_type)

                # Upload to storage
                storage_client = get_storage_client()
                if not storage_client:
                    log_error("Storage client not available")
                    skipped_count += 1
                    continue

                storage_path = f"text-cards/{uuid.uuid4().hex[:8]}.png"
                upload_success, image_url, upload_error = storage_client.upload_file(
                    bucket='media',
                    file_path=image_path,
                    destination_path=storage_path,
                    content_type='image/png'
                )

                if not upload_success or not image_url:
                    log_error(f"Failed to upload image for day {day_offset + 1}: {upload_error}")
                    skipped_count += 1
                    continue

                # Prepare metadata
                metadata = {
                    'text_card_type': actual_content_type,
                    'text_card_content': image_content,
                    'generated_at': datetime.now(SA_TZ).isoformat(),
                    'weekly_batch': True,
                    'day': day_offset + 1
                }

                # Save to database
                post_data = {
                    'platform': 'facebook',
                    'content_text': content.get('caption', ''),
                    'post_type': 'text_card',
                    'scheduled_time': scheduled_time.isoformat(),
                    'image_url': image_url,
                    'hashtags': json.dumps(content.get('hashtags', [])) if content.get('hashtags') else None,
                    'generation_prompt': json.dumps(metadata),
                    'status': 'pending_approval',
                    'is_pinned': False
                }

                post_id = db.save_post(post_data)

                if post_id:
                    created_ids.append(post_id)
                    log_info(f"✅ Created text card {day_offset + 1}/7: {post_id}")
                else:
                    skipped_count += 1

            except Exception as e:
                log_error(f"❌ Failed to generate text card for day {day_offset + 1}: {e}")
                skipped_count += 1
                continue

        # Calculate date range
        end_date = start_date + timedelta(days=6)

        return jsonify({
            'success': True,
            'posts_created': len(created_ids),
            'posts_skipped': skipped_count,
            'first_date': start_date.strftime('%Y-%m-%d'),
            'last_date': end_date.strftime('%Y-%m-%d'),
            'post_ids': created_ids,
            'message': f'✅ Created {len(created_ids)} text cards for {start_date.strftime("%b %d")} - {end_date.strftime("%b %d")} ({text_card_time} SAST daily). Skipped {skipped_count}.'
        })

    except Exception as e:
        log_error(f"❌ Generate weekly text cards failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/text-card/<post_id>/edit', methods=['POST'])
def api_edit_text_card(post_id):
    """Edit text card content and regenerate image.

    JSON body (depends on text_card_type in metadata):
    For quote: {"quote": "...", "attribution": "..."}
    For tip: {"header": "...", "tip": "...", "subtitle": "..."}
    For educational: {"title": "...", "points": ["...", "..."]}
    For motivation: {"statement": "..."}

    Optionally include: {"caption": "...", "hashtags": [...]}

    Returns:
        JSON with success, new_image_url, updated post data
    """
    log_info(f"📥 Request: /api/dashboard/text-card/{post_id}/edit")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        from social_media.text_card_generator import TextCardGenerator
        from utils.supabase_storage import get_storage_client
        import os
        import json
        from datetime import datetime
        import pytz

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Get text_card_type and text_card_content from request
        text_card_type = data.get('text_card_type')
        text_card_content = data.get('text_card_content')
        caption = data.get('caption')

        if not text_card_type:
            return jsonify({'success': False, 'error': 'text_card_type is required'}), 400

        if not text_card_content:
            return jsonify({'success': False, 'error': 'text_card_content is required'}), 400

        log_info(f"📝 Editing {text_card_type} text card with content: {text_card_content}")

        # Fetch the post
        log_info(f"🔍 Fetching post {post_id}")
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]

        # Verify it's a text_card
        if post.get('post_type') != 'text_card':
            return jsonify({'success': False, 'error': 'Post is not a text_card'}), 400

        # Verify it's not published
        if post.get('status') == 'published':
            return jsonify({'success': False, 'error': 'Cannot edit a published post'}), 400

        # Regenerate image with the EDITED content
        log_info(f"🎨 Regenerating {text_card_type} image with edited content")
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
        text_card_gen = TextCardGenerator(config_path)

        image_path = text_card_gen.generate_text_card(text_card_content, text_card_type)

        # Upload new image to Supabase storage
        storage_client = get_storage_client()
        if not storage_client:
            log_error("Storage client not available")
            return jsonify({'success': False, 'error': 'Storage client not available'}), 500

        # Use existing image_url path if available, otherwise create new one
        existing_image_url = post.get('image_url', '')
        if existing_image_url and 'text-cards/' in existing_image_url:
            # Extract the storage path from the URL
            # URL format: https://...supabase.co/storage/v1/object/public/media/text-cards/...
            storage_path = existing_image_url.split('/media/')[-1]
        else:
            # Create new storage path
            storage_path = f"text-cards/{uuid.uuid4().hex[:8]}.png"

        log_info(f"📤 Uploading to: {storage_path}")
        upload_success, image_url, upload_error = storage_client.upload_file(
            bucket='media',
            file_path=image_path,
            destination_path=storage_path,
            content_type='image/png'
        )

        if not upload_success or not image_url:
            log_error(f"Failed to upload updated text card image: {upload_error}")
            return jsonify({'success': False, 'error': f'Failed to upload image: {upload_error}'}), 500

        # Update metadata with new content
        updated_metadata = {
            'text_card_type': text_card_type,
            'text_card_content': text_card_content,
            'last_edited': datetime.now(SA_TZ).isoformat()
        }

        # Build update data
        update_data = {
            'image_url': image_url,
            'generation_prompt': json.dumps(updated_metadata),
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        # Update caption if provided
        if 'caption' in data:
            update_data['content_text'] = data['caption']

        # Update hashtags if provided
        if 'hashtags' in data:
            hashtags_value = data['hashtags']
            if isinstance(hashtags_value, str):
                # Parse string to list
                try:
                    hashtags_list = json.loads(hashtags_value)
                    update_data['hashtags'] = json.dumps(hashtags_list)
                except:
                    # Split by comma or space
                    tags = [t.strip() for t in hashtags_value.replace(',', ' ').split() if t.strip()]
                    tags = ['#' + t.lstrip('#') for t in tags if t]
                    update_data['hashtags'] = json.dumps(tags)
            elif isinstance(hashtags_value, list):
                update_data['hashtags'] = json.dumps(hashtags_value)

        # Save to database
        log_info(f"💾 Updating post {post_id}")
        update_result = supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

        if update_result.data:
            updated_post = update_result.data[0]
            log_info(f"✅ Text card {post_id} updated successfully")
            return jsonify({
                'success': True,
                'post_id': post_id,
                'new_image_url': image_url,
                'post': updated_post,
                'message': 'Text card updated successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update post'}), 500

    except Exception as e:
        log_error(f"❌ Edit text card failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/backfill-image-prompts', methods=['POST'])
def api_backfill_image_prompts():
    """Backfill image prompts for all posts that don't have one."""
    log_info("📥 Request: /api/dashboard/backfill-image-prompts")

    if not app.config.get('SUPABASE_CONNECTED') or not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        import pytz
        from datetime import datetime
        import json

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        # Find all posts without image_prompt (or with empty image_prompt)
        log_info("🔍 Finding posts without image prompts...")

        # Get all non-published posts
        result = supabase_client.table('social_posts').select(
            'id, content_theme, content_text, post_type, generation_prompt, image_prompt, title'
        ).neq('status', 'published').execute()

        if not result.data:
            return jsonify({
                'success': True,
                'message': 'No posts found to update',
                'updated_count': 0
            })

        posts = result.data
        updated_count = 0
        skipped_count = 0

        for post in posts:
            post_id = post['id']

            # Skip if already has image_prompt
            existing_prompt = post.get('image_prompt', '').strip() if post.get('image_prompt') else ''
            if existing_prompt:
                skipped_count += 1
                continue

            # Get content_theme, fallback to extracting from generation_prompt
            content_theme = post.get('content_theme', '')

            if not content_theme:
                # Try to extract from generation_prompt JSON
                gen_prompt = post.get('generation_prompt')
                if gen_prompt:
                    try:
                        if isinstance(gen_prompt, str):
                            gen_data = json.loads(gen_prompt)
                        else:
                            gen_data = gen_prompt
                        content_theme = gen_data.get('content_theme', 'general')
                    except:
                        content_theme = 'general'
                else:
                    content_theme = 'general'

            # Generate the image prompt
            content_text = post.get('content_text', '')
            post_type = post.get('post_type', 'image')

            new_image_prompt = generate_scroll_stopping_image_prompt(
                content_theme,
                content_text,
                post_type
            )

            # Update the post
            try:
                # Also update generation_prompt to include image_prompt
                gen_prompt = post.get('generation_prompt')
                gen_data = {}
                if gen_prompt:
                    try:
                        if isinstance(gen_prompt, str):
                            gen_data = json.loads(gen_prompt)
                        else:
                            gen_data = gen_prompt
                    except:
                        gen_data = {}

                gen_data['image_prompt'] = new_image_prompt

                update_data = {
                    'image_prompt': new_image_prompt,
                    'generation_prompt': json.dumps(gen_data),
                    'updated_at': datetime.now(SA_TZ).isoformat()
                }

                supabase_client.table('social_posts').update(update_data).eq('id', post_id).execute()

                updated_count += 1
                log_info(f"✅ Updated post {post_id[:8]}... with {content_theme} prompt")

            except Exception as e:
                log_error(f"❌ Failed to update post {post_id}: {e}")

        log_info(f"✅ Backfill complete: {updated_count} updated, {skipped_count} skipped (already had prompts)")

        return jsonify({
            'success': True,
            'message': f'Backfill complete! {updated_count} posts updated, {skipped_count} already had prompts.',
            'updated_count': updated_count,
            'skipped_count': skipped_count,
            'total_processed': len(posts)
        })

    except Exception as e:
        log_error(f"❌ Backfill image prompts failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/generate-image/<post_id>', methods=['POST'])
def api_generate_image_for_post(post_id):
    """Generate a Leonardo AI image for a specific post.

    This endpoint:
    1. Fetches the post from database
    2. Generates image using Leonardo AI
    3. Updates the post with the new image_url
    4. Returns success/failure
    """
    log_info(f"🎨 Generate image requested for post: {post_id}")

    try:
        # Fetch the post
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]

        # Verify it's an image post
        if post.get('post_type') != 'image':
            return jsonify({'success': False, 'error': 'Post is not an image type'}), 400

        # Check if it already has an image (unless regenerate is requested)
        regenerate = request.args.get('regenerate', 'false').lower() == 'true'

        if post.get('image_url') and not regenerate:
            return jsonify({
                'success': True,
                'message': 'Post already has an image',
                'image_url': post.get('image_url')
            })

        if regenerate:
            log_info(f"🔄 Regenerating image for post {post_id} (replacing existing)")

        # Get image prompt and content type
        image_prompt = post.get('image_prompt', '')
        content_type = 'motivational'  # default

        try:
            gen_prompt = post.get('generation_prompt')
            if gen_prompt:
                if isinstance(gen_prompt, str):
                    gen_data = json.loads(gen_prompt)
                else:
                    gen_data = gen_prompt
                content_type = gen_data.get('content_type', 'motivational')
        except:
            pass

        # Use caption as prompt if no image_prompt
        if not image_prompt:
            image_prompt = post.get('content_text', '')[:500]

        log_info(f"   Content type: {content_type}")
        log_info(f"   Prompt: {image_prompt[:80]}...")

        # Generate image
        from social_media.leonardo_generator import LeonardoGenerator, LeonardoGenerationError

        leonardo = LeonardoGenerator(supabase_client=supabase_client)

        result = leonardo.generate_image(
            prompt=image_prompt,
            content_type=content_type,
        )

        image_url = result.get('image_url')

        if not image_url:
            return jsonify({'success': False, 'error': 'No image URL returned from Leonardo'}), 500

        # Update post with image URL
        supabase_client.table('social_posts').update({
            'image_url': image_url,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', post_id).execute()

        log_info(f"✅ Image generated for post {post_id}: {image_url}")

        return jsonify({
            'success': True,
            'image_url': image_url,
            'message': 'Image generated successfully'
        })

    except LeonardoGenerationError as e:
        log_error(f"❌ Leonardo error for post {post_id}: {e}")
        return jsonify({'success': False, 'error': f'Leonardo AI error: {str(e)}'}), 500
    except Exception as e:
        log_error(f"❌ Error generating image for post {post_id}: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/generate-missing-images', methods=['POST'])
def api_generate_missing_images():
    """Generate Leonardo AI images for all image posts that have image_url = None.

    This backfills images for posts that were created before auto-generation was enabled.
    """
    log_info("=" * 60)
    log_info("GENERATE MISSING IMAGES - ENDPOINT CALLED")
    log_info("=" * 60)

    try:
        # Find all image posts with relevant statuses
        # Note: Custom SupabaseTable doesn't support is_() for NULL checks,
        # so we fetch all and filter in Python
        result = supabase_client.table('social_posts').select('*').eq(
            'post_type', 'image'
        ).execute()

        all_image_posts = result.data if result.data else []

        # Filter for posts without images and with active statuses
        active_statuses = ['pending_approval', 'approved', 'scheduled']
        posts_without_images = [
            post for post in all_image_posts
            if (post.get('image_url') is None or post.get('image_url') == '')
            and post.get('status') in active_statuses
        ]

        log_info(f"📊 Found {len(posts_without_images)} image posts without images")

        if not posts_without_images:
            return jsonify({
                'success': True,
                'message': 'All image posts already have images!',
                'posts_updated': 0
            })

        # Check Leonardo API key
        leonardo_api_key = os.getenv('LEONARDO_API_KEY')
        if not leonardo_api_key:
            log_error("❌ LEONARDO_API_KEY not set!")
            return jsonify({
                'success': False,
                'error': 'Leonardo API key not configured'
            }), 500

        # Initialize Leonardo
        from social_media.leonardo_generator import LeonardoGenerator, LeonardoGenerationError
        leonardo = LeonardoGenerator(supabase_client=supabase_client)

        updated_count = 0
        failed_count = 0

        for post in posts_without_images:
            post_id = post.get('id')
            image_prompt = post.get('image_prompt', '')

            # Get content_type from generation_prompt metadata
            content_type = 'motivational'  # default
            try:
                gen_prompt = post.get('generation_prompt')
                if gen_prompt:
                    if isinstance(gen_prompt, str):
                        gen_data = json.loads(gen_prompt)
                    else:
                        gen_data = gen_prompt
                    content_type = gen_data.get('content_type', 'motivational')
            except:
                pass

            log_info(f"🎨 Generating image for post {post_id}...")
            log_info(f"   Content type: {content_type}")
            log_info(f"   Prompt: {image_prompt[:80]}..." if image_prompt else "   No prompt - using default")

            try:
                # Use image_prompt if available, otherwise generate from caption
                prompt = image_prompt or post.get('content_text', '')[:200]

                result = leonardo.generate_image(
                    prompt=prompt,
                    content_type=content_type,
                )

                image_url = result.get('image_url')

                if image_url:
                    # Update post with image URL
                    supabase_client.table('social_posts').update({
                        'image_url': image_url,
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }).eq('id', post_id).execute()

                    log_info(f"✅ Image generated for post {post_id}: {image_url}")
                    updated_count += 1
                else:
                    log_error(f"❌ No image URL returned for post {post_id}")
                    failed_count += 1

            except LeonardoGenerationError as e:
                log_error(f"❌ Leonardo error for post {post_id}: {e}")
                failed_count += 1
            except Exception as e:
                log_error(f"❌ Unexpected error for post {post_id}: {e}")
                failed_count += 1

            # Small delay to avoid rate limiting
            import time
            time.sleep(2)

        log_info("=" * 60)
        log_info("GENERATE MISSING IMAGES - COMPLETE")
        log_info(f"Updated: {updated_count}, Failed: {failed_count}")
        log_info("=" * 60)

        return jsonify({
            'success': True,
            'message': f'Generated images for {updated_count} posts ({failed_count} failed)',
            'posts_updated': updated_count,
            'posts_failed': failed_count
        })

    except Exception as e:
        log_error(f"❌ Generate missing images failed: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    log_error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/dashboard/fix-carousel-hashtags/<post_id>', methods=['POST'])
def api_fix_carousel_hashtags(post_id):
    """Fix hashtags for an existing carousel post.

    Can be used to add hashtags to carousel posts that were created without them.
    """
    log_info(f"📥 Request: /api/dashboard/fix-carousel-hashtags/{post_id}")

    if not supabase_client:
        return jsonify({'success': False, 'error': 'Database not connected'}), 503

    try:
        # Get the post
        result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()

        if not result.data:
            return jsonify({'success': False, 'error': 'Post not found'}), 404

        post = result.data[0]

        # Check if it's a carousel post
        if post.get('post_type') != 'carousel' and post.get('media_type') != 'carousel':
            return jsonify({
                'success': False,
                'error': f"Post is not a carousel (type: {post.get('post_type') or post.get('media_type')})"
            }), 400

        # Get content_type from metadata
        content_type = 'educational'  # Default
        if post.get('generation_prompt'):
            try:
                metadata = json.loads(post['generation_prompt'])
                content_type = metadata.get('content_type', 'educational')
            except:
                pass

        # Generate hashtags
        hashtags = generate_trainer_hashtags(content_type)

        # Update the post
        supabase_client.table('social_posts').update({
            'hashtags': hashtags,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }).eq('id', post_id).execute()

        log_info(f"✅ Added {len(hashtags)} hashtags to carousel post {post_id}: {hashtags}")

        return jsonify({
            'success': True,
            'message': f'Added {len(hashtags)} hashtags to carousel post',
            'post_id': post_id,
            'hashtags': hashtags,
            'content_type': content_type
        })

    except Exception as e:
        log_error(f"❌ Error fixing carousel hashtags: {str(e)}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


# Initialize application
def initialize_app():
    """Initialize all application components"""
    log_info("=" * 50)
    log_info("🚀 Starting Refiloe Marketing System")
    log_info("=" * 50)
    
    # Validate configuration
    try:
        app.config.from_object(config[env])
        log_info(f"✅ Configuration loaded: {env}")
    except Exception as e:
        log_error(f"❌ Configuration validation failed: {str(e)}")
        return False

    # Initialize Supabase
    log_info("Initializing Supabase connection...")
    success, error = init_supabase()

    if success:
        # Verify the connection
        verification_result = verify_supabase_connection()
        app.config['SUPABASE_CONNECTED'] = verification_result['connected']
        app.config['SUPABASE_ERROR'] = verification_result.get('error')
        app.config['SUPABASE_LAST_CHECK'] = datetime.now(SA_TZ)

        if verification_result['connected']:
            log_info(f"✅ Supabase connection verified and ready")
            log_info(f"📊 Connection details: {verification_result['details']}")
        else:
            log_warning(f"⚠️  Supabase connection verification failed: {verification_result['error']}")
            log_warning("⚠️  Some features will be disabled")
    else:
        app.config['SUPABASE_CONNECTED'] = False
        app.config['SUPABASE_ERROR'] = error
        app.config['SUPABASE_LAST_CHECK'] = datetime.now(SA_TZ)
        log_warning(f"⚠️  Supabase initialization failed: {error}")
        log_warning("⚠️  Some features will be disabled")
    
    # Initialize Scheduler
    if app.config.get('ENABLE_SOCIAL_MEDIA', True):
        log_info("Initializing social media scheduler...")
        if not init_scheduler():
            log_warning("⚠️  Scheduler initialization failed - automation will be disabled")
    else:
        log_info("Social media automation is disabled in configuration")
    
    log_info("=" * 50)
    log_info("✅ Refiloe Marketing System Ready")
    log_info("=" * 50)
    
    return True


# Initialize on startup
with app.app_context():
    initialize_app()


if __name__ == '__main__':
    # Get port from environment (Railway provides this)
    port = int(os.getenv('PORT', 5000))
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])
