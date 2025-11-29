# Avatar Look Library Generator

Automated script to generate a comprehensive library of predefined avatar looks for Refiloe across various use cases.

## Overview

This script generates 20 unique avatar looks optimized for different content scenarios, from professional consultations to outdoor fitness adventures. Each look is carefully designed with specific outfit, environment, pose, and mood combinations.

## Features

- ✅ **20 Predefined Scenarios** - Covering all major use cases for Refiloe's content
- ✅ **API Integration** - Calls HeyGen API via Flask backend
- ✅ **Resumable** - Skip already-generated looks automatically
- ✅ **JSON Output** - Saves all results to structured JSON file
- ✅ **Railway Integration** - Generates environment variable commands
- ✅ **Rich CLI** - Beautiful progress bars and summary reports
- ✅ **Dry-run Mode** - Preview scenarios before generating

## Look Scenarios

| Scenario | Use Case | Tags |
|----------|----------|------|
| **Morning Workout Energy** | Morning motivation, workout challenges | fitness, morning, energy, gym |
| **Professional Consultation** | Business advice, client consultations | business, professional, consultation |
| **Weekend Motivation** | Weekend wellness, lifestyle content | weekend, casual, outdoor |
| **Success Celebration** | Client transformations, milestones | success, transformation, celebration |
| **Educational Tutorial** | How-to videos, technique tutorials | education, tutorial, teaching |
| **Community Gathering** | Group challenges, social engagement | community, social, inclusive |
| **Nutrition Advice** | Nutrition tips, meal planning | nutrition, kitchen, health |
| **Mindfulness & Wellness** | Meditation, stress management | mindfulness, wellness, meditation |
| **Business Strategy** | Business growth, leadership content | business, strategy, leadership |
| **Client Transformation** | Before/after showcases | transformation, fitness, confidence |
| **Morning Routine** | Daily habits, sunrise workouts | morning, routine, home |
| **Strength Training** | Form guidance, workout demos | strength, training, gym |
| **Yoga Flow** | Yoga tutorials, flexibility | yoga, flexibility, studio |
| **Cardio Energy Blast** | HIIT workouts, cardio challenges | cardio, HIIT, energy |
| **Recovery & Rest** | Rest day importance, self-care | recovery, rest, relaxation |
| **Outdoor Adventure** | Nature fitness, outdoor workouts | outdoor, nature, adventure |
| **Evening Wind-Down** | Evening routines, night wellness | evening, wind-down, wellness |
| **Podcast Conversation** | Q&A sessions, deep conversations | podcast, conversation, Q&A |
| **Beach Wellness** | Wellness retreats, beach workouts | beach, retreat, wellness |
| **Studio Headshot** | Profile pictures, branding | headshot, professional, branding |

## Prerequisites

1. **Flask Application Running**
   ```bash
   python app.py
   # Should be running on http://localhost:5050
   ```

2. **Environment Variables Set**
   - `HEYGEN_API_KEY` - Your HeyGen API key
   - `HEYGEN_AVATAR_GROUP` - Your photo avatar group ID
   - Supabase credentials (for database storage)

3. **Python Dependencies**
   ```bash
   pip install requests rich
   ```

## Usage

### Basic Usage

Generate all 20 looks:
```bash
python scripts/generate_look_library.py
```

### Dry Run (Preview Only)

Preview what will be generated without making API calls:
```bash
python scripts/generate_look_library.py --dry-run
```

### Limit Number of Looks

Generate only 5 looks for testing:
```bash
python scripts/generate_look_library.py --limit 5
```

### Generate Specific Scenario

Generate just one specific look:
```bash
python scripts/generate_look_library.py --scenario morning_workout_energy
```

### Custom Output File

Save to a custom JSON file:
```bash
python scripts/generate_look_library.py --output my_custom_library.json
```

### Generate Railway Commands

Create a bash script with Railway environment variable commands:
```bash
python scripts/generate_look_library.py --railway-commands set_env_vars.sh
```

Then run it to set the variables:
```bash
chmod +x set_env_vars.sh
./set_env_vars.sh
```

### Force Regeneration

Regenerate looks that already exist:
```bash
python scripts/generate_look_library.py --force
```

### Custom API URL

Use a different API endpoint:
```bash
python scripts/generate_look_library.py --api-url http://example.com:8080/api/generate-look
```

## Output Files

### generated_looks_library.json

Structured JSON file containing all generated looks:

```json
{
  "generated_at": "2025-11-28T12:34:56.789Z",
  "looks": {
    "morning_workout_energy": {
      "name": "morning_workout_energy",
      "label": "Morning Workout Energy",
      "use_case": "Morning motivation posts, workout challenges, fitness tips at dawn",
      "tags": ["fitness", "morning", "energy", "gym"],
      "outfit": "bright athletic wear (sports bra, leggings) in sunrise colors",
      "environment": "modern gym with large windows showing sunrise, natural morning light",
      "pose": "energetic standing pose with confident stance",
      "mood": "energized and motivational",
      "photo_avatar_id": "abc123...",
      "look_id": "def456...",
      "preview_url": "https://...",
      "prompt_used": "Person wearing bright athletic wear...",
      "generated_at": "2025-11-28T12:35:22.456Z"
    }
  },
  "metadata": {
    "last_updated": "2025-11-28T12:45:30.123Z",
    "total_looks": 20,
    "api_url": "http://localhost:5050/api/generate-look"
  }
}
```

### Railway Commands Output

If `--railway-commands` is used, generates a bash script:

```bash
#!/bin/bash
# Generated Railway environment variable commands
# Generated at: 2025-11-28T12:45:30Z

railway variables set HEYGEN_AVATAR_MORNING_WORKOUT_ENERGY=abc123...
railway variables set HEYGEN_AVATAR_PROFESSIONAL_CONSULTATION=def456...
railway variables set HEYGEN_AVATAR_WEEKEND_MOTIVATION=ghi789...
# ... etc
```

## Resumability

The script is fully resumable. If generation is interrupted:

1. Already-generated looks are saved to JSON after each success
2. On restart, the script reads the existing JSON file
3. Looks with valid `photo_avatar_id` are automatically skipped
4. Only missing or failed looks are regenerated

To force regeneration of existing looks, use `--force` flag.

## Error Handling

- **API Failures**: Each failed look is logged and counted, but doesn't stop the process
- **Network Issues**: Individual request failures are caught and reported
- **Resumable**: Partial progress is always saved
- **Exit Codes**: Script exits with code 1 if any failures occurred

## Summary Report

After generation, the script displays a comprehensive report:

```
======================================================================
📊 LOOK LIBRARY GENERATION SUMMARY
======================================================================

✅ Successfully generated: 18
❌ Failed: 2
⏭️  Skipped (already exists): 0
📚 Total in library: 18

📋 Generated Looks:
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Scenario Name         ┃ Label                 ┃ Avatar ID       ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ morning_workout...    │ Morning Workout...    │ abc123...       │
│ professional_con...   │ Professional Con...   │ def456...       │
└───────────────────────┴───────────────────────┴─────────────────┘

🔗 Preview URLs:
  Morning Workout Energy: https://resource.heygen.ai/...
  Professional Consultation: https://resource.heygen.ai/...

🔧 Recommended Environment Variables:
  HEYGEN_AVATAR_MORNING_WORKOUT_ENERGY=abc123...
  HEYGEN_AVATAR_PROFESSIONAL_CONSULTATION=def456...
```

## Integration with Application

Once looks are generated, update your application to use them:

### 1. Update .env file

```bash
# Add to .env
HEYGEN_AVATAR_MORNING_WORKOUT_ENERGY=abc123...
HEYGEN_AVATAR_PROFESSIONAL_CONSULTATION=def456...
# ... etc
```

### 2. Use in Video Generation

```python
from social_media.video_generator import VideoGenerator

# Use specific look for morning content
avatar_id = os.getenv('HEYGEN_AVATAR_MORNING_WORKOUT_ENERGY')
video_gen.generate_video(
    script="Good morning! Ready to crush today's workout?",
    avatar_id=avatar_id,
)
```

### 3. Content-Based Avatar Selection

```python
def select_avatar_for_content(content_type: str) -> str:
    """Select appropriate avatar based on content type."""

    avatar_mapping = {
        'morning_motivation': os.getenv('HEYGEN_AVATAR_MORNING_WORKOUT_ENERGY'),
        'business_tip': os.getenv('HEYGEN_AVATAR_PROFESSIONAL_CONSULTATION'),
        'weekend_post': os.getenv('HEYGEN_AVATAR_WEEKEND_MOTIVATION'),
        'success_story': os.getenv('HEYGEN_AVATAR_SUCCESS_CELEBRATION'),
        # ... etc
    }

    return avatar_mapping.get(content_type, os.getenv('HEYGEN_AVATAR_DEFAULT'))
```

## Estimated Time & Cost

- **Generation Time**: ~2-3 minutes per look
- **Total Time for 20 looks**: ~40-60 minutes
- **API Calls**: 20 look generation requests
- **HeyGen Credits**: Check your HeyGen pricing for photo avatar generation costs

## Tips

1. **Start with Dry Run**: Always preview with `--dry-run` first
2. **Test with Limit**: Test with `--limit 3` before generating all
3. **Monitor Progress**: Script saves after each success, safe to interrupt
4. **Check Preview URLs**: Verify looks in browser before using in production
5. **Version Control**: Commit `generated_looks_library.json` to track changes

## Troubleshooting

### Flask app not running
```
Error: Connection refused
→ Solution: Start Flask app with `python app.py`
```

### Missing API key
```
Error: HEYGEN_API_KEY environment variable is required
→ Solution: Set HEYGEN_API_KEY in .env file
```

### Generation timeout
```
Error: Timed out waiting for look to complete
→ Solution: Increase timeout in LooksGenerator (HEYGEN_LOOK_POLL_TIMEOUT)
```

### Already exists
```
⏭️ Skipping X - already exists
→ Solution: Use --force to regenerate, or delete from JSON file
```

## Support

For issues or questions:
1. Check Flask app logs: `tail -f logs/app.log`
2. Review API responses in script output
3. Verify environment variables are set correctly
4. Check HeyGen API status and quota

## License

Part of the Refiloe Marketing project.
