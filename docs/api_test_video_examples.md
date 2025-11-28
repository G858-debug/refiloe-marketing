# /api/test-video Endpoint - Usage Examples

The `/api/test-video` endpoint now supports inline look generation, allowing you to generate a new avatar look and create a video with it in a single API call.

## Endpoint

```
POST /api/test-video
```

## Request Parameters

### Basic Parameters (backward compatible)
- `script` (string): The text script for the video
- `avatar_id` (string, optional): Avatar ID to use for video
- `voice_id` (string, optional): Voice ID to use
- `content_theme` (string, optional): Content theme for avatar selection

### New Look Generation Parameters
- `generate_look` (boolean, default: false): Enable inline look generation
- `look_params` (object): Parameters for look generation
  - `look_type` (string): Predefined look type (e.g., "gym_trainer", "office_professional")
  - `custom_prompt` (string): Custom prompt for look generation
  - `outfit` (string): Outfit description
  - `environment` (string): Environment/background description
  - `pose` (string): Pose description
  - `mood` (string): Mood/expression

## Response Structure

### Success Response (with look generation)
```json
{
  "success": true,
  "message": "Video generated successfully! Check /approval/pending to review.",
  "look_generation": {
    "success": true,
    "look_id": "look_abc123",
    "photo_avatar_id": "avatar_xyz789",
    "preview_url": "https://...",
    "prompt_used": "Person wearing athletic wear...",
    "look_type": "gym_trainer",
    "database_record_id": "uuid-here"
  },
  "video_generation": {
    "success": true,
    "video_id": "video_def456",
    "video_url": "https://...",
    "thumbnail_url": "https://...",
    "duration": 30,
    "post_id": "post_uuid",
    "approval_url": "/approval/view/post_uuid",
    "avatar_id_used": "avatar_xyz789"
  },
  "video_id": "video_def456",
  "video_url": "https://...",
  "post_id": "post_uuid",
  "approval_url": "/approval/view/post_uuid"
}
```

### Error Response Examples

#### Look Generation Failed
```json
{
  "success": false,
  "error": "Look generation failed: Invalid look_type",
  "look_generation": {
    "success": false,
    "error": "Invalid look_type 'invalid_type'"
  },
  "video_generation": null
}
```

#### Video Generation Failed (Look Succeeded)
```json
{
  "success": false,
  "error": "Video generation failed (look generation succeeded): HeyGen API error",
  "partial_success": true,
  "look_generation": {
    "success": true,
    "look_id": "look_abc123",
    "photo_avatar_id": "avatar_xyz789",
    ...
  },
  "video_generation": {
    "success": false,
    "error": "HeyGen API error"
  }
}
```

## Usage Examples

### Example 1: Basic Video (No Look Generation)
```bash
curl -X POST http://localhost:5000/api/test-video \
  -H "Content-Type: application/json" \
  -d '{
    "script": "Hello from Refiloe! This is a test video."
  }'
```

### Example 2: Video with Predefined Look
```bash
curl -X POST http://localhost:5000/api/test-video \
  -H "Content-Type: application/json" \
  -d '{
    "script": "Ready to transform your fitness business?",
    "generate_look": true,
    "look_params": {
      "look_type": "gym_trainer"
    }
  }'
```

### Example 3: Video with Custom Look Components
```bash
curl -X POST http://localhost:5000/api/test-video \
  -H "Content-Type: application/json" \
  -d '{
    "script": "Let me share some nutrition tips with you!",
    "generate_look": true,
    "look_params": {
      "look_type": "custom",
      "outfit": "Casual white chef coat over a blue top",
      "environment": "Modern kitchen with fresh vegetables and fruits on the counter",
      "pose": "Standing confidently with arms crossed",
      "mood": "friendly"
    }
  }'
```

### Example 4: Video with Custom Prompt
```bash
curl -X POST http://localhost:5000/api/test-video \
  -H "Content-Type: application/json" \
  -d '{
    "script": "Welcome to our wellness retreat!",
    "generate_look": true,
    "look_params": {
      "custom_prompt": "Professional wellness coach wearing comfortable linen clothing, standing on a beach at sunset, peaceful expression, ocean and palm trees in background"
    }
  }'
```

### Example 5: Video with Specific Avatar and Voice
```bash
curl -X POST http://localhost:5000/api/test-video \
  -H "Content-Type: application/json" \
  -d '{
    "script": "Here are today's workout tips!",
    "generate_look": true,
    "look_params": {
      "look_type": "home_workout"
    },
    "voice_id": "1bd001e7e50f421d891986aad5158bc8",
    "content_theme": "fitness"
  }'
```

## Available Look Types

- `gym_trainer` - Athletic wear in a modern gym setting
- `office_professional` - Business attire in a corporate office
- `outdoor_wellness` - Casual activewear in an outdoor park setting
- `nutrition_expert` - Smart casual in a modern kitchen
- `yoga_instructor` - Yoga attire in a serene studio
- `motivational_speaker` - Smart dress on a stage setting
- `home_workout` - Workout clothes in a home gym space
- `podcast_host` - Casual smart wear in a podcast studio
- `retreat_leader` - Flowing clothes in a beach/resort setting
- `studio_portrait` - Professional headshot style

## Workflow

1. **If `generate_look` is true:**
   - Generate the avatar look using LooksGenerator
   - Extract the `photo_avatar_id` from the look
   - Save the look to database
   - Use the `photo_avatar_id` for video generation

2. **If `generate_look` is false (default):**
   - Use provided `avatar_id` parameter
   - If not provided, auto-detect from `content_theme`
   - If still not provided, use environment default
   - Proceed with video generation

3. **Error Handling:**
   - Look generation failures stop the workflow immediately
   - Video generation failures after successful look generation return partial success
   - All errors are logged separately for debugging

## Timing Considerations

- **Look Generation**: 2-3 minutes (HeyGen API processing time)
- **Video Generation**: 3-5 minutes (HeyGen API processing time)
- **Total for Look + Video**: 5-8 minutes

## Notes

- The endpoint maintains backward compatibility - existing calls without `generate_look` work as before
- All generated looks are saved to the `avatar_looks` database table
- Videos are created with `pending_approval` status and can be reviewed at `/approval/view/{post_id}`
- The response includes both structured data (`look_generation`, `video_generation`) and backward-compatible fields (`video_id`, `video_url`, etc.)
