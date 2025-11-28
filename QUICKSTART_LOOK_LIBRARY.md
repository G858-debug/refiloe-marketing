# Quick Start: Avatar Look Library Generation

Generate 20 unique avatar looks for Refiloe in minutes!

## Prerequisites ✅

Before running the script, ensure:

1. **Flask app is running**:
   ```bash
   python app.py
   ```
   The app should be accessible at `http://localhost:5050`

2. **Environment variables are set** (in `.env`):
   ```bash
   HEYGEN_API_KEY=your-api-key
   HEYGEN_PHOTO_AVATAR_GROUP_ID=your-group-id
   SUPABASE_URL=your-supabase-url
   SUPABASE_SERVICE_KEY=your-service-key
   ```

3. **Dependencies installed**:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start 🚀

### Step 1: Preview (Recommended)

First, see what will be generated without making any API calls:

```bash
python scripts/generate_look_library.py --dry-run
```

This shows all 20 scenarios and sample prompts.

### Step 2: Test with Limited Generation

Test with just 3 looks to verify everything works:

```bash
python scripts/generate_look_library.py --limit 3
```

**Expected Output:**
```
🚀 Starting Look Library Generation

📊 Scenarios to generate: 3
💾 Output file: generated_looks_library.json
🔗 API endpoint: http://localhost:5050/api/generate-look

✅ [1/3] Generated Morning Workout Energy - ID: abc123...
✅ [2/3] Generated Professional Consultation - ID: def456...
✅ [3/3] Generated Weekend Motivation - ID: ghi789...

======================================================================
📊 LOOK LIBRARY GENERATION SUMMARY
======================================================================

✅ Successfully generated: 3
❌ Failed: 0
⏭️  Skipped (already exists): 0
📚 Total in library: 3
```

**Time:** ~6-9 minutes (2-3 min per look)

### Step 3: Generate Full Library

Once testing works, generate all 20 looks:

```bash
python scripts/generate_look_library.py
```

**Time:** ~40-60 minutes
**Output:** `generated_looks_library.json`

### Step 4: Generate Railway Commands

Create environment variable commands for Railway:

```bash
python scripts/generate_look_library.py --railway-commands set_env_vars.sh
```

This creates a bash script with commands like:
```bash
railway variables set HEYGEN_AVATAR_MORNING_WORKOUT_ENERGY=abc123...
railway variables set HEYGEN_AVATAR_PROFESSIONAL_CONSULTATION=def456...
# ... etc
```

### Step 5: Deploy to Railway

Set the environment variables:

```bash
chmod +x set_env_vars.sh
./set_env_vars.sh
```

Or manually copy the variables from the summary report to your Railway dashboard.

## Output Files 📁

After generation, you'll have:

1. **generated_looks_library.json** - Complete library with all look data
2. **set_env_vars.sh** (if requested) - Railway commands script

## Resume Interrupted Generation 🔄

If generation is interrupted, simply run the script again:

```bash
python scripts/generate_look_library.py
```

The script automatically:
- Loads existing `generated_looks_library.json`
- Skips looks that are already generated
- Continues with remaining looks

To force regeneration of specific looks, use `--force`:

```bash
python scripts/generate_look_library.py --force
```

## Verify Generated Looks ✓

Check the preview URLs in the summary report or JSON file:

```bash
# Quick view
python -m json.tool generated_looks_library.json | grep preview_url

# Or open the JSON file
cat generated_looks_library.json
```

Preview URLs look like:
```
https://resource.heygen.ai/photo_avatar/preview/abc123.jpg
```

Open these in your browser to verify each look.

## Common Scenarios 📋

### Generate Specific Look Only

```bash
python scripts/generate_look_library.py --scenario morning_workout_energy
```

### Use Custom API URL

If your Flask app runs on a different port:

```bash
python scripts/generate_look_library.py --api-url http://localhost:8080/api/generate-look
```

### Save to Custom File

```bash
python scripts/generate_look_library.py --output my_looks.json
```

## Troubleshooting 🔧

### Problem: Connection Refused

```
Error: Connection refused to http://localhost:5050
```

**Solution:** Start Flask app first:
```bash
python app.py
```

### Problem: Missing API Key

```
Error: HEYGEN_API_KEY environment variable is required
```

**Solution:** Add to `.env` file:
```bash
HEYGEN_API_KEY=your-api-key-here
```

### Problem: Generation Timeout

```
Error: Timed out waiting for look to complete
```

**Solution:** Increase timeout in `.env`:
```bash
HEYGEN_LOOK_POLL_TIMEOUT=600  # 10 minutes
```

### Problem: Look Already Exists

```
⏭️ Skipping Morning Workout Energy - already exists
```

**Solution:** Use `--force` to regenerate:
```bash
python scripts/generate_look_library.py --force
```

Or delete specific look from JSON file and re-run.

## Next Steps 🎯

After generating the library:

1. **Review preview URLs** - Verify each look meets expectations

2. **Update .env file** - Add avatar IDs:
   ```bash
   HEYGEN_AVATAR_MORNING_WORKOUT_ENERGY=abc123...
   HEYGEN_AVATAR_PROFESSIONAL_CONSULTATION=def456...
   ```

3. **Use in video generation**:
   ```python
   avatar_id = os.getenv('HEYGEN_AVATAR_MORNING_WORKOUT_ENERGY')
   video_generator.generate_video(script="...", avatar_id=avatar_id)
   ```

4. **Implement content-based selection**:
   ```python
   def get_avatar_for_content(content_type):
       mapping = {
           'morning': 'HEYGEN_AVATAR_MORNING_WORKOUT_ENERGY',
           'business': 'HEYGEN_AVATAR_PROFESSIONAL_CONSULTATION',
           'weekend': 'HEYGEN_AVATAR_WEEKEND_MOTIVATION',
       }
       env_var = mapping.get(content_type, 'HEYGEN_AVATAR_DEFAULT')
       return os.getenv(env_var)
   ```

## Available Looks 🎭

The script generates these 20 looks:

| # | Look Name | Best For |
|---|-----------|----------|
| 1 | Morning Workout Energy | Dawn workouts, morning motivation |
| 2 | Professional Consultation | Business advice, client sessions |
| 3 | Weekend Motivation | Casual wellness, lifestyle tips |
| 4 | Success Celebration | Transformations, milestones |
| 5 | Educational Tutorial | How-to videos, technique guides |
| 6 | Community Gathering | Group challenges, social posts |
| 7 | Nutrition Advice | Meal planning, healthy eating |
| 8 | Mindfulness & Wellness | Meditation, stress management |
| 9 | Business Strategy | Leadership, growth tips |
| 10 | Client Transformation | Before/after showcases |
| 11 | Morning Routine | Daily habits, sunrise sessions |
| 12 | Strength Training | Form demos, weight training |
| 13 | Yoga Flow | Yoga tutorials, flexibility |
| 14 | Cardio Energy Blast | HIIT, high-energy workouts |
| 15 | Recovery & Rest | Rest days, self-care |
| 16 | Outdoor Adventure | Nature fitness, trail running |
| 17 | Evening Wind-Down | Night routines, relaxation |
| 18 | Podcast Conversation | Q&A, deep discussions |
| 19 | Beach Wellness | Retreats, beach workouts |
| 20 | Studio Headshot | Branding, profile pictures |

## Cost Estimation 💰

- **HeyGen Credits:** Check HeyGen pricing for photo avatar generation
- **Time Investment:** ~40-60 minutes for all 20 looks
- **One-time Generation:** Looks can be reused indefinitely

## Support 💬

For issues:
1. Check Flask logs: `tail -f logs/app.log`
2. Review script output for error details
3. Verify HeyGen API key and quota
4. See full documentation: `scripts/README_LOOK_LIBRARY.md`

---

**Ready?** Start with:
```bash
python scripts/generate_look_library.py --dry-run
```
