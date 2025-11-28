# Avatar Looks Comparison Feature

## Overview

The Looks Comparison feature allows you to test and compare different avatar "looks" (outfit/environment combinations) side-by-side to determine which performs best for different content types.

## Features

### 1. Side-by-Side Comparison
- Select 2-4 avatar looks from your library
- Generate test videos using the same script for each look
- View all videos simultaneously in a grid layout
- Fair comparison with identical scripts and settings

### 2. Performance Tracking
- Rate each look from 1-5 stars
- Add detailed notes about each look's performance
- Track ratings per content type (admin_tips, motivation, fitness, etc.)
- Visual highlighting of the best-performing look

### 3. Content Type Categories
- Admin Tips
- Motivation
- Fitness
- Nutrition
- Client Success
- Educational
- Announcement
- General Test

### 4. Data Persistence
- Ratings and notes are saved to the database
- Historical performance data for each look
- Automatic retrieval of previous ratings for reference

## How to Use

### Step 1: Select Looks
1. Navigate to `/looks-compare`
2. Browse available avatar looks
3. Click on 2-4 looks to select them
4. Selected looks will be highlighted with a gold border

### Step 2: Configure Test
1. Select the content type from the dropdown
2. Enter the test script (same script will be used for all looks)
3. Click "Generate Comparison Videos"

### Step 3: Wait for Generation
- Video generation takes approximately 3-5 minutes per look
- Progress bar shows overall status
- Individual video generation happens sequentially

### Step 4: Compare & Rate
1. Watch each generated video
2. Click stars to rate each look (1-5)
3. Add notes about performance observations
4. The best-performing look (highest rating) will be highlighted with a green border and trophy badge

### Step 5: Save Preferences
- Ratings are automatically saved when you click stars
- Click "Save Notes" to persist your observations
- Data is stored per look + content type combination

## API Endpoints

### GET `/looks-compare`
Renders the comparison page with all available looks.

**Response:** HTML page

### POST `/api/looks/compare-generate`
Generates comparison videos for selected looks.

**Request Body:**
```json
{
  "look_ids": ["uuid1", "uuid2", "uuid3"],
  "script": "Test script text",
  "content_type": "admin_tips"
}
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "look_id": "uuid1",
      "look_type": "gym_trainer",
      "video_url": "https://...",
      "thumbnail_url": "https://...",
      "duration": 45.5,
      "success": true
    }
  ],
  "successful_count": 3,
  "total_count": 3
}
```

### POST `/api/looks/save-rating`
Saves a rating for a look.

**Request Body:**
```json
{
  "look_id": "uuid",
  "content_type": "admin_tips",
  "rating": 5,
  "notes": "Great energy and professional appearance"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Rating saved successfully"
}
```

### GET `/api/looks/get-ratings`
Retrieves ratings, optionally filtered by content type.

**Query Parameters:**
- `content_type` (optional): Filter ratings by content type

**Response:**
```json
{
  "success": true,
  "ratings": [
    {
      "id": "uuid",
      "look_id": "uuid",
      "content_type": "admin_tips",
      "rating": 5,
      "notes": "Great energy",
      "created_at": "2025-11-28T10:00:00Z",
      "updated_at": "2025-11-28T10:00:00Z"
    }
  ]
}
```

## Database Schema

### `look_ratings` Table

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| look_id | UUID | Foreign key to avatar_looks |
| content_type | VARCHAR(100) | Content category |
| rating | INTEGER (1-5) | User rating |
| notes | TEXT | Performance notes |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

**Indexes:**
- `idx_look_ratings_content_type` - Fast content type lookups
- `idx_look_ratings_look_id` - Fast look ID lookups
- `idx_look_ratings_rating` - Performance rating queries
- `idx_look_ratings_content_rating` - Composite for content + rating

**Constraints:**
- `unique_look_content_rating` - One rating per look per content type
- `fk_look_id` - Foreign key to avatar_looks with CASCADE delete

## Use Cases

### 1. Determining Best Look for Content Type
Test which avatar look resonates best with your audience for specific content categories (e.g., gym trainer look for fitness content vs. office professional for admin tips).

### 2. A/B Testing
Generate multiple videos with different looks and track which performs better with your audience.

### 3. Content Strategy Optimization
Build data-driven insights about which looks work best for different message types, allowing you to optimize future content creation.

### 4. Look Library Curation
Identify underperforming looks that can be retired or improved, and spotlight high-performers for frequent use.

## Best Practices

1. **Use Realistic Scripts**: Test with scripts similar to your actual content
2. **Compare Similar Contexts**: Test looks that are contextually appropriate for the content type
3. **Track Notes**: Record specific observations about what worked or didn't work
4. **Test Multiple Content Types**: A look might perform differently across content categories
5. **Regular Re-evaluation**: Periodically retest looks as your content strategy evolves

## Future Enhancements

Potential improvements for future versions:

- [ ] Automatic look selection based on content type and historical ratings
- [ ] Analytics dashboard showing look performance over time
- [ ] Bulk comparison testing with multiple scripts
- [ ] Video quality metrics integration (watch time, completion rate)
- [ ] Export comparison reports as PDF
- [ ] Social proof integration (audience engagement metrics)

## Technical Notes

- Video generation uses HeyGen API
- Background music is disabled for comparison videos to ensure consistency
- Videos are generated sequentially to avoid API rate limits
- Maximum 4 looks per comparison to maintain page performance
- Ratings are stored with upsert logic (update if exists, insert if new)

## Support

For issues or questions about the Looks Comparison feature, please refer to:
- Main README: `/README.md`
- Database migration: `/docs/migration_look_ratings_table.sql`
- Template: `/templates/looks_compare.html`
- API routes: `/app.py` (lines 2223-2445)
