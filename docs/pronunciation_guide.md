# Pronunciation Guide for HeyGen Narration

## Overview

The Refiloe marketing system automatically handles pronunciation substitutions for AI-generated video narration. This ensures HeyGen's voice AI pronounces names and terms correctly.

## How It Works

When generating videos, the system:
1. Takes the original script text
2. Applies phonetic substitutions for narration
3. Sends the phonetic version to HeyGen
4. Keeps the original spelling for captions, posts, and display

## Current Pronunciations

| Original | Phonetic (for HeyGen) | Usage |
|----------|----------------------|--------|
| Refiloe | Reh FILL weh | Name pronunciation |
| Refiloe's | Reh FILL weh's | Possessive form |

## Implementation

The `_prepare_script_for_narration()` method in `VideoGenerator` handles all substitutions automatically before sending scripts to HeyGen API.

**Affected methods:**
- `generate_avatar_video()` (Photo Avatars)
- `generate_avatar_iv_video()` (Avatar IV)

## Adding New Pronunciations

To add new phonetic substitutions, edit the `pronunciation_map` dictionary in `_prepare_script_for_narration()`:
```python
pronunciation_map = {
    'Refiloe': 'Reh FILL weh',
    'NewTerm': 'Phonetic Spelling',
}
```

## Testing

Test pronunciation by:
1. Generating a test video: POST to `/api/test-video`
2. Listen to the narration
3. Adjust phonetic spelling if needed
4. Regenerate and verify

## Notes

- Substitutions use word boundary matching to avoid partial replacements
- Case-insensitive matching ensures consistency
- Original script text remains unchanged for all non-narration uses
- Logging confirms when substitutions are applied
