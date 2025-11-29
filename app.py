
"""
Refiloe Marketing - Main Flask Application
Social Media Automation System

This is the entry point for the Railway deployment.
"""

import os
import atexit
import uuid
import json
from flask import Flask, jsonify, request, render_template
from datetime import datetime, timedelta
import pytz

from dotenv import load_dotenv

# Import configuration
from config import config

# Import utilities
from utils.logger import log_info, log_error, log_warning
from utils.heygen_avatars import collect_avatar_env_values, check_avatar_availability

from social_media.approval_routes import approval_bp
from social_media.analytics_routes import analytics_bp
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

heygen_avatar_status = {
    "checked": False,
    "available": None,
    "details": [],
}

HEYGEN_API_KEY_ENV = "HEYGEN_API_KEY"

# South African timezone
SA_TZ = pytz.timezone('Africa/Johannesburg')


def init_supabase():
    """Initialize Supabase client"""
    global supabase_client
    
    try:
        from utils.supabase_rest import SupabaseRestClient
        
        url = app.config['SUPABASE_URL']
        key = app.config.get('SUPABASE_SERVICE_KEY') or app.config.get('SUPABASE_ANON_KEY')
        
        if not url or not key:
            log_error("Supabase credentials not found in environment")
            return False
        
        supabase_client = SupabaseRestClient(url, key)
        log_info("✅ Supabase REST client initialized successfully")
        return True
        
    except Exception as e:
        log_error(f"Failed to initialize Supabase: {str(e)}")
        import traceback
        log_error(f"Full traceback:\n{traceback.format_exc()}")
        return False


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


def validate_heygen_configuration():
    """Validate HeyGen avatar environment and API availability."""

    global heygen_avatar_status

    log_info("Validating HeyGen avatar configuration...")

    heygen_avatar_status = {
        "checked": True,
        "available": None,
        "details": [],
    }

    avatars, missing = collect_avatar_env_values()
    if missing:
        log_warning(
            "Missing HeyGen avatar environment variables: " + ", ".join(sorted(missing))
        )
        heygen_avatar_status["details"].append(
            {
                "type": "missing_env",
                "variables": sorted(missing),
            }
        )
    else:
        log_info("All HeyGen avatar environment variables are set.")

    api_key = os.getenv(HEYGEN_API_KEY_ENV)
    if not api_key:
        log_warning("HEYGEN_API_KEY is not configured; skipping avatar availability check.")
        heygen_avatar_status["details"].append(
            {
                "type": "missing_api_key",
                "message": "HEYGEN_API_KEY is not configured; availability not checked.",
            }
        )
        return

    if not avatars:
        log_warning("No HeyGen avatar IDs configured; skipping availability check.")
        heygen_avatar_status["details"].append(
            {
                "type": "missing_ids",
                "message": "No HeyGen avatar IDs available for validation.",
            }
        )
        return

    try:
        results = check_avatar_availability(api_key, avatars)
    except Exception as exc:  # pragma: no cover - network errors
        log_warning(f"HeyGen availability check encountered an error: {exc}")
        heygen_avatar_status["details"].append(
            {
                "type": "error",
                "message": str(exc),
            }
        )
        return

    failures = {key: status for key, status in results.items() if not status.get("ok")}
    if failures:
        for env_key, status in failures.items():
            detail = status.get("detail", "Unknown error")
            avatar_id = status.get("avatar_id", "unknown")
            log_warning(
                f"HeyGen avatar unavailable: {env_key} ({avatar_id}) -> {detail}"
            )
            heygen_avatar_status["details"].append(
                {
                    "type": "unavailable",
                    "env": env_key,
                    "avatar_id": avatar_id,
                    "detail": detail,
                }
            )
        heygen_avatar_status["available"] = False
        log_warning("Some HeyGen avatars are unavailable. Video generation may fail until resolved.")
    else:
        log_info("HeyGen avatar availability verified.")
        heygen_avatar_status["available"] = True


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
            'content_pipeline_health': '/health/content-pipeline'
        }
    }), 200


@app.route('/api/status')
def status():
    """Detailed status endpoint"""
    status_info = {
        'service': 'refiloe-marketing',
        'version': '1.0.0',
        'timestamp': datetime.now(SA_TZ).isoformat(),
        'environment': os.getenv('FLASK_ENV', 'production'),
        'components': {
            'flask': 'running',
            'supabase': 'connected' if supabase_client else 'disconnected',
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


@app.route('/health/content-pipeline')
def content_pipeline_health():
    """Content pipeline health monitoring endpoint"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

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
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

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


@app.route('/api/debug/post/<post_id>')
def debug_single_post(post_id):
    """Debug endpoint to see full post details including video"""
    if not supabase_client:
        return jsonify({'error': 'Database not connected'}), 503

    try:
        # Get the post
        post_result = supabase_client.table('social_posts').select('*').eq('id', post_id).execute()
        post = post_result.data[0] if post_result.data else None

        # Get the video
        video_result = supabase_client.table('generated_videos').select('*').eq('post_id', post_id).execute()
        video = video_result.data[0] if video_result.data else None

        # Get images
        images_result = supabase_client.table('social_images').select('*').eq('post_id', post_id).execute()
        images = images_result.data if images_result.data else []

        return jsonify({
            'post': post,
            'video': video,
            'images': images,
            'field_check': {
                'has_content': 'content' in post if post else False,
                'has_content_text': 'content_text' in post if post else False,
                'has_created_at': 'created_at' in post if post else False,
                'has_scheduled_time': 'scheduled_time' in post if post else False,
                'video_linked': video is not None,
                'video_has_url': video.get('video_url') is not None if video else False
            }
        }), 200
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
        avatar_id = data.get('avatar_id') or os.getenv('HEYGEN_AVATAR_DEFAULT')

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

        post_data = {
            'post_type': 'video',
            'platform': 'facebook',
            'status': 'pending_approval',
            'scheduled_time': scheduled_time.isoformat(),
            'video_url': result.get('video_url'),
            'thumbnail_url': result.get('thumbnail_url'),
            'video_duration': int(result.get('duration') or 0),
            'video_type': 'marketing_video',
            'video_style': data.get('style', 'educational'),
            'content_text': content_text,
            'content_theme': theme,
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


app.register_blueprint(approval_bp, url_prefix='/approval')
app.register_blueprint(analytics_bp, url_prefix='/analytics')


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

        // Main video generation function
        async function generateVideo() {
            const resultDiv = document.getElementById('result');
            const generateBtn = document.getElementById('generateBtn');

            resultDiv.className = 'show';
            generateBtn.disabled = true;

            const useGenerateLook = document.getElementById('generate_new').checked;
            let avatarIdToUse = null;

            try {
                // Step 1: Generate look if selected
                if (useGenerateLook) {
                    resultDiv.innerHTML = updateProgress([
                        { text: 'Generating custom avatar look... (this may take 2-3 minutes)', status: 'active' },
                        { text: 'Creating video...', status: 'pending' }
                    ]);

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

                    // Call the generate-look API
                    const lookResponse = await fetch('/api/generate-look', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(lookPayload)
                    });

                    const lookData = await lookResponse.json();

                    if (!lookResponse.ok || !lookData.success) {
                        throw new Error(lookData.error || 'Failed to generate avatar look');
                    }

                    avatarIdToUse = lookData.photo_avatar_id;

                    resultDiv.innerHTML = updateProgress([
                        { text: 'Look generated successfully!', status: 'complete' },
                        { text: 'Creating video... (this may take 3-5 minutes)', status: 'active' }
                    ]);

                    // Add look preview if available
                    if (lookData.preview_url) {
                        resultDiv.innerHTML += `
                            <div style="margin: 15px 0; padding: 10px; background: #e8f5e9; border-radius: 4px;">
                                <strong>Generated Look Preview:</strong><br>
                                <img src="${lookData.preview_url}" style="max-width: 200px; border-radius: 4px; margin-top: 10px;">
                            </div>
                        `;
                    }
                } else {
                    // Using existing avatar
                    avatarIdToUse = document.getElementById('avatar_id').value.trim() || null;

                    resultDiv.innerHTML = updateProgress([
                        { text: 'Generating video... (this may take 3-5 minutes)', status: 'active' }
                    ]);
                }

                // Step 2: Generate the video
                const script = document.getElementById('script').value;
                const contentTheme = document.getElementById('content_theme').value;
                const voiceId = document.getElementById('voice_id').value;
                const motionPrompt = document.getElementById('motion_prompt').value.trim();

                const videoPayload = {
                    script: script
                };

                if (contentTheme) {
                    videoPayload.content_theme = contentTheme;
                }

                if (avatarIdToUse) {
                    videoPayload.avatar_id = avatarIdToUse;
                }

                if (voiceId) {
                    videoPayload.voice_id = voiceId;
                }

                // Add to payload if provided
                if (motionPrompt) {
                    videoPayload.motion_prompt = motionPrompt;
                }

                const videoResponse = await fetch('/api/test-video', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(videoPayload)
                });

                const videoData = await videoResponse.json();

                if (videoResponse.ok) {
                    let successHtml = updateProgress([
                        ...(useGenerateLook ? [{ text: 'Look generated successfully!', status: 'complete' }] : []),
                        { text: 'Video created successfully!', status: 'complete' }
                    ]);

                    successHtml += '<h3 style="color: #4CAF50; margin-top: 20px;">✅ Success!</h3>';
                    successHtml += '<pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto;">' + JSON.stringify(videoData, null, 2) + '</pre>';

                    if (videoData.post_id) {
                        successHtml += `
                            <div style="margin-top: 15px;">
                                <a href="/approval/view/${videoData.post_id}" style="color: #4CAF50; font-weight: bold; margin-right: 20px;">
                                    📝 Review This Video
                                </a>
                                <a href="/approval/pending" style="color: #4CAF50; font-weight: bold;">
                                    📋 View All Pending Approvals
                                </a>
                            </div>
                        `;
                    }

                    resultDiv.innerHTML = successHtml;
                } else {
                    throw new Error(videoData.error || 'Video generation failed');
                }
            } catch (error) {
                resultDiv.innerHTML = `
                    <h3 style="color: #dc3545;">❌ Error</h3>
                    <p>${error.message}</p>
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
    if not supabase_client:
        return jsonify({'error': 'Supabase not initialized'}), 503

    try:
        log_info("=== Starting test video generation ===")

        from social_media.video_generator import VideoGenerator
        import os

        # Get request data
        data = request.get_json() or {}
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

                log_info(f"  preview_url: {preview_url}")
                log_info(f"  image_urls: {image_urls}")
                log_info(f"  image_keys: {image_keys}")

                # Use preview_url directly (it's the most reliable)
                image_url = preview_url

                # Also get image_key if available (Avatar IV can use either)
                image_key = image_keys[0] if image_keys else None

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

            # Validate we have image data for Avatar IV
            if not image_url and not image_key:
                raise ValueError("Avatar IV requires either image_url or image_key")

            log_info(f"Avatar IV video generation parameters - voice: {voice_id}, theme: {content_theme}, motion_prompt: {motion_prompt}")
            log_info(f"Using Avatar IV with image_url: {image_url}")
            log_info(f"Script: {script[:100]}...")

            # Generate video using Avatar IV API (supports gestures and arm movements)
            log_info("Calling generate_avatar_iv_video...")
            result = video_gen.generate_avatar_iv_video(
                script=script,
                image_url=image_url,
                image_key=image_key,
                voice_id=voice_id,
                custom_motion_prompt=motion_prompt,  # Use provided motion prompt
                enhance_motion=True,
                aspect_ratio="9:16",  # Vertical video for social media
                title=f"Test Video - {look_type or 'custom'}",
                metadata={
                    'test': True,
                    'purpose': 'production_test',
                    'triggered_by': 'api',
                    'content_theme': content_theme,
                    'generated_look': generate_look,
                    'look_id': response_data['look_generation']['look_id'] if response_data['look_generation'] else None,
                    'look_type': look_type,
                    'source': 'test_video_endpoint',
                    'timestamp': datetime.now(pytz.timezone('Africa/Johannesburg')).isoformat()
                }
            )

            log_info(f"Video generation result: {result}")

            # Check if we got a video URL
            video_url = result.get('video_url')
            video_id = result.get('video_id')

            if not video_url:
                log_error(f"No video URL in result: {result}")
                raise ValueError('Video generated but no URL returned')

            log_info(f"Video URL obtained: {video_url}")

            # Create post with pending_approval status
            from datetime import datetime, timedelta
            scheduled_time = datetime.now(SA_TZ) + timedelta(hours=2)

            post_data = {
                'post_type': 'video',
                'platform': 'facebook',
                'status': 'pending_approval',
                'scheduled_time': scheduled_time.isoformat(),
                'video_url': video_url,
                'thumbnail_url': result.get('thumbnail_url'),
                'video_duration': int(result.get('duration', 0)),
                'video_type': 'test_video',
                'video_style': result.get('style', 'educational'),
                'content': script,
                'title': f'Test video - {script[:100]}...',
                'content_theme': content_theme or 'test',
                'has_captions': True,
                'completion_rate': 0,
                'avg_watch_time': 0
            }

            log_info(f"Post data being saved: {json.dumps(post_data, indent=2, default=str)}")

            # Save to database
            from social_media.database import SocialMediaDatabase
            db = SocialMediaDatabase(supabase_client)
            post_id = db.save_post(post_data)

            log_info(f"Post saved with ID: {post_id}")

            if not post_id:
                log_error("Failed to save post - no ID returned")
                raise ValueError('Failed to save post to database')

            # Store video generation result
            response_data['video_generation'] = {
                'success': True,
                'video_id': video_id,
                'video_url': video_url,
                'thumbnail_url': result.get('thumbnail_url'),
                'duration': result.get('duration'),
                'post_id': post_id,
                'approval_url': f'/approval/view/{post_id}',
                'api_type': 'avatar_iv',
                'image_url': image_url,
                'status': result.get('status')
            }

            log_info("=== Video generation completed successfully ===")

        except Exception as video_error:
            log_error(f"Avatar IV video generation failed: {str(video_error)}")
            import traceback
            log_error(f"Avatar IV traceback:\n{traceback.format_exc()}")

            # Store video generation error
            response_data['video_generation'] = {
                'success': False,
                'error': str(video_error),
                'api_type': 'avatar_iv'
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
            final_response['post_id'] = response_data['video_generation']['post_id']
            final_response['approval_url'] = response_data['video_generation']['approval_url']

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
        if date_to:
            # Add one day to include the entire end date
            date_to_dt = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.lt('created_at', date_to_dt.isoformat())

        # Order by created_at DESC
        query = query.order('created_at', desc=True)

        # Execute query
        result = query.execute()
        looks = result.data if result and hasattr(result, 'data') else []

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

        # Get look details
        result = supabase_client.table('avatar_looks').select('*').in_('id', look_ids).execute()
        looks = result.data if result and hasattr(result, 'data') else []

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
            # Update existing rating
            result = supabase_client.table('look_ratings').update({
                'rating': rating,
                'notes': notes,
                'updated_at': datetime.now(SA_TZ).isoformat()
            }).eq('look_id', look_id).eq('content_type', content_type).execute()

            log_info(f"Updated rating for look {look_id}, content_type {content_type}")
        else:
            # Insert new rating
            result = supabase_client.table('look_ratings').insert(db_record).execute()
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


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    log_error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


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
    
    # Validate HeyGen avatars
    validate_heygen_configuration()

    # Initialize Supabase
    log_info("Initializing Supabase connection...")
    if not init_supabase():
        log_warning("⚠️  Supabase initialization failed - some features will be disabled")
    
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
