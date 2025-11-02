
"""
Refiloe Marketing - Main Flask Application
Social Media Automation System

This is the entry point for the Railway deployment.
"""

import os
from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import pytz

from dotenv import load_dotenv

# Import configuration
from config import config

# Import utilities
from utils.logger import log_info, log_error, log_warning
from utils.heygen_avatars import collect_avatar_env_values, check_avatar_availability

from social_media.approval_routes import approval_bp


load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Load configuration
env = os.getenv('FLASK_ENV', 'production')
app.config.from_object(config[env])

# Global variables
scheduler = None
supabase_client = None

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
    
    try:
        # Check if social media is enabled
        if not app.config.get('ENABLE_SOCIAL_MEDIA', True):
            log_warning("Social media automation is disabled")
            return False
        
        # Import scheduler
        from social_media.scheduler import create_social_media_scheduler
        
        # Create scheduler instance
        scheduler = create_social_media_scheduler(app, supabase_client)
        
        if scheduler:
            # Start scheduler
            scheduler.start()
            log_info("✅ Social media scheduler started successfully")
            return True
        else:
            log_error("Failed to create scheduler instance")
            return False
            
    except Exception as e:
        log_error(f"Failed to initialize scheduler: {str(e)}")
        log_error(f"Error details: {type(e).__name__}")
        return False


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
            'scheduler': scheduler is not None,
            'social_media_enabled': app.config.get('ENABLE_SOCIAL_MEDIA', False),
            'heygen': heygen_avatar_status,
        },
        'links': {
            'approval_pending': '/approval/pending'
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
            'scheduler': 'running' if scheduler and scheduler.scheduler.running else 'stopped',
            'social_media': 'enabled' if app.config.get('ENABLE_SOCIAL_MEDIA') else 'disabled',
            'heygen': heygen_avatar_status,
        },
        'configuration': {
            'timezone': 'Africa/Johannesburg',
            'log_level': app.config.get('LOG_LEVEL', 'INFO')
        }
    }
    
    return jsonify(status_info), 200


@app.route('/api/scheduler/jobs')
def scheduler_jobs():
    """Get list of scheduled jobs"""
    if not scheduler:
        return jsonify({'error': 'Scheduler not initialized'}), 503
    
    try:
        jobs = []
        for job in scheduler.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return jsonify({
            'jobs': jobs,
            'total': len(jobs),
            'scheduler_running': scheduler.scheduler.running
        }), 200
        
    except Exception as e:
        log_error(f"Error getting scheduler jobs: {str(e)}")
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


app.register_blueprint(approval_bp, url_prefix='/approval')


@app.route('/test-video-form')
def test_video_form():
    """Simple form to trigger test video generation"""
    
    # Get available avatars from environment
    import os
    avatars = {
        'Default': os.getenv('HEYGEN_AVATAR_DEFAULT'),
        'Professional Closeup': os.getenv('HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP'),
        'Casual Closeup': os.getenv('HEYGEN_AVATAR_CASUAL_CLOSEUP'),
        'Fitness Fullbody': os.getenv('HEYGEN_AVATAR_FITNESS_FULLBODY'),
        'Confident Swimwear': os.getenv('HEYGEN_AVATAR_CONFIDENT_SWIMWEAR_FULLBODY'),
        'Serious Closeup': os.getenv('HEYGEN_AVATAR_SERIOUS_CLOSEUP'),
        'Warm Smile Closeup': os.getenv('HEYGEN_AVATAR_WARMSMILE_CLOSEUP'),
        'Three Quarters Closeup': os.getenv('HEYGEN_AVATAR_THREEQUARTERS_CLOSEUP'),
        'Summer Casual': os.getenv('HEYGEN_AVATAR_SUMMERCASUAL_THREEQUARTERBODY'),
    }
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Video Generation</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
            label {{ display: block; margin-top: 15px; font-weight: bold; }}
            textarea, select {{ width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; }}
            textarea {{ height: 100px; }}
            button {{ background: #4CAF50; color: white; padding: 15px 30px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin-top: 20px; }}
            button:hover {{ background: #45a049; }}
            button:disabled {{ background: #ccc; cursor: not-allowed; }}
            .result {{ margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 5px; display: none; }}
            .loading {{ display: none; margin-top: 20px; color: #666; }}
            .avatar-preview {{ margin-top: 10px; color: #666; font-size: 14px; }}
        </style>
    </head>
    <body>
        <h1>🎬 Test Video Generation</h1>
        <p>Generate a test video with HeyGen using different avatars</p>
        
        <label for="avatar">Select Avatar:</label>
        <select id="avatar" onchange="showAvatarId()">
            {''.join(f'<option value="{avatar_id}">{name} ({avatar_id})</option>' for name, avatar_id in avatars.items() if avatar_id)}
        </select>
        <div class="avatar-preview" id="avatarPreview"></div>
        
        <label for="script">Video Script:</label>
        <textarea id="script">Hello from Refiloe! This is a test video to verify our HeyGen integration is working perfectly in production.</textarea>
        
        <button onclick="generateVideo()">Generate Test Video</button>
        
        <div class="loading" id="loading">
            <p>⏳ Generating video... This takes 2-5 minutes. Please wait...</p>
        </div>
        
        <div class="result" id="result"></div>
        
        <script>
            function showAvatarId() {{
                const select = document.getElementById('avatar');
                const preview = document.getElementById('avatarPreview');
                preview.textContent = 'Avatar ID: ' + select.value;
            }}
            
            showAvatarId(); // Show initial selection
            
            async function generateVideo() {{
                const button = event.target;
                const script = document.getElementById('script').value;
                const avatarId = document.getElementById('avatar').value;
                const loading = document.getElementById('loading');
                const result = document.getElementById('result');
                
                button.disabled = true;
                button.textContent = 'Generating...';
                loading.style.display = 'block';
                result.style.display = 'none';
                
                try {{
                    const response = await fetch('/api/test/generate-video', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ 
                            script: script,
                            avatar_id: avatarId
                        }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.success) {{
                        result.innerHTML = `
                            <h3>✅ Success!</h3>
                            <p><strong>Video ID:</strong> ${{data.video_id}}</p>
                            <p><strong>Video URL:</strong> <a href="${{data.video_url}}" target="_blank">View Video</a></p>
                            <p><strong>Post ID:</strong> ${{data.post_id}}</p>
                            <p><a href="/approval/pending" target="_blank">👉 Go to Approval Dashboard</a></p>
                        `;
                    }} else {{
                        result.innerHTML = `<h3>❌ Error:</h3><p>${{data.error}}</p>`;
                    }}
                }} catch (error) {{
                    result.innerHTML = `<h3>❌ Error:</h3><p>${{error.message}}</p>`;
                }}
                
                loading.style.display = 'none';
                result.style.display = 'block';
                button.disabled = false;
                button.textContent = 'Generate Test Video';
            }}
        </script>
    </body>
    </html>
    '''
    return html


@app.route('/api/test/generate-video', methods=['POST'])
def test_generate_video():
    """Manually trigger a test video generation"""
    if not supabase_client:
        return jsonify({'error': 'Supabase not initialized'}), 503
    
    try:
        log_info("=== Starting test video generation ===")
        
        from social_media.video_generator import VideoGenerator
        import os
        
        # Initialize video generator
        log_info("Initializing VideoGenerator...")
        video_gen = VideoGenerator(
            config_path='social_media/config.yaml',
            supabase_client=supabase_client
        )
        log_info("VideoGenerator initialized successfully")
        
        # Get request data
        data = request.get_json() or {}
        script = data.get('script', 'Hello from Refiloe! This is a test video to verify our HeyGen integration is working perfectly in production.')
        
        # Get voice and avatar from request or environment
        voice_id = data.get('voice_id') or os.getenv('HEYGEN_DEFAULT_VOICE_ID', '1bd001e7e50f421d891986aad5158bc8')
        avatar_id = data.get('avatar_id') or os.getenv('HEYGEN_AVATAR_DEFAULT')
        
        log_info(f"Using avatar: {avatar_id}, voice: {voice_id}")
        log_info(f"Script: {script[:100]}...")
        
        # Generate video
        log_info("Calling generate_avatar_video...")
        result = video_gen.generate_avatar_video(
            script_text=script,
            avatar_id=avatar_id,
            voice_id=voice_id,
            style='educational',
            background_music=True,
            metadata={
                'test': True,
                'purpose': 'production_test',
                'triggered_by': 'api'
            }
        )
        
        log_info(f"Video generation result: {result}")
        
        # Check if we got a video URL
        video_url = result.get('video_url')
        video_id = result.get('video_id')
        
        if not video_url:
            log_error(f"No video URL in result: {result}")
            return jsonify({
                'success': False,
                'error': 'Video generated but no URL returned',
                'result': result
            }), 500
        
        log_info(f"Video URL obtained: {video_url}")
        
        # Create post with pending_approval status
        from datetime import datetime, timedelta
        scheduled_time = datetime.now(SA_TZ) + timedelta(hours=2)
        
        post_data = {
            'format': 'video',
            'platform': 'facebook',
            'status': 'pending_approval',
            'scheduled_time': scheduled_time.isoformat(),
            'video_url': video_url,  # Add video_url directly
            'thumbnail_url': result.get('thumbnail_url'),  # Add thumbnail
            'metadata': {
                'video_url': video_url,
                'video_id': video_id,
                'avatar_id': result.get('avatar_id'),
                'test': True,
                'caption': f'Test video - {script[:100]}...'
            }
        }
        
        log_info(f"Saving post to database: {post_data}")
        
        # Save to database
        from social_media.database import SocialMediaDatabase
        db = SocialMediaDatabase(supabase_client)
        post_id = db.save_post(post_data)
        
        log_info(f"Post saved with ID: {post_id}")
        
        if not post_id:
            log_error("Failed to save post - no ID returned")
            return jsonify({
                'success': False,
                'error': 'Failed to save post to database',
                'video_url': video_url,
                'video_id': video_id
            }), 500
        
        log_info("=== Test video generation completed successfully ===")
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'video_url': video_url,
            'post_id': post_id,
            'message': 'Video generated successfully! Check /approval/pending to review.',
            'approval_url': f'/approval/view/{post_id}'
        }), 200
        
    except Exception as e:
        log_error(f"Error generating test video: {str(e)}")
        import traceback
        error_traceback = traceback.format_exc()
        log_error(f"Full traceback:\n{error_traceback}")
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': error_traceback
        }), 500


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
