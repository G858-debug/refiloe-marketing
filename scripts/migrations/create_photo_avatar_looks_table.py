"""
Migration script to create the photo_avatar_looks table in Supabase.
This table stores the mapping between content types and HeyGen photo avatar IDs.

Before running this Python script, execute the SQL in Supabase Dashboard:
1. Go to Supabase Dashboard > SQL Editor
2. Paste and run the contents of scripts/migrations/sql/photo_avatar_looks.sql
3. Then run: python scripts/migrations/create_photo_avatar_looks_table.py
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from supabase import create_client, Client
from utils.logger import log_info, log_error, log_warning


def get_supabase_client() -> Client:
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")
    return create_client(url, key)


# Initial photo avatar data to seed the table
INITIAL_PHOTO_AVATARS = [
    {
        "content_type": "workout",
        "photo_avatar_id": "96c419d3058444069ab8e28308fdc834",
        "label": "Workout",
        "outfit_description": "Fitted coral athletic crop top with thin straps, high-waisted burgundy leggings, delicate gold body chain across collarbone, small gold hoop earrings",
        "environment_description": "Modern boutique gym with warm wood-paneled accent wall, chrome dumbbells on beige leather bench, floor-to-ceiling window with golden morning light, snake plant in terracotta pot",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "fitness",
        "photo_avatar_id": "291df9103e744984be41715e649ae8e6",
        "label": "Fitness",
        "outfit_description": "Electric blue racerback athletic top with mesh panel detail, matching blue sports bra visible underneath, thin gold necklace with small pendant, medium gold hoop earrings, hair in two neat cornrow braids",
        "environment_description": "Bright fitness studio with floor-to-ceiling mirrors, polished light oak hardwood floors, ballet barre on cream wall, stacked yoga mats in earthy tones on wooden shelving",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "professional",
        "photo_avatar_id": "64a1ca313daf488698bebb282aa87dae",
        "label": "Professional",
        "outfit_description": "Structured hot pink blazer with padded shoulders over cream silk camisole with delicate lace trim, thin gold layered necklaces, statement gold drop earrings, hair in sophisticated low bun",
        "environment_description": "Modern co-working space with large beige linen sofa and cognac leather armchair, brass floor lamp with cream shade, floating wooden shelves with books and fiddle leaf fig, abstract art in terracotta and gold",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "business",
        "photo_avatar_id": "331e5ac30c914d5abeb2853be17a8532",
        "label": "Business",
        "outfit_description": "Tailored emerald green power blazer with gold button detail over crisp white V-neck blouse, gold chain-link earrings, delicate gold watch, hair straightened and flowing over one shoulder",
        "environment_description": "Executive office with mahogany desk, beige leather executive chair, floor-to-ceiling bookshelf with leather-bound books and bronze sculptures, city skyline visible through window",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "motivational",
        "photo_avatar_id": "d0c9ad8674ef49b79f618dd5303e50df",
        "label": "Motivational",
        "outfit_description": "Bold orange off-shoulder crop top showing toned shoulders, high-waisted camel wide-leg trousers, chunky gold statement necklace, large gold hoop earrings, voluminous natural afro with golden highlights",
        "environment_description": "Rooftop terrace at golden hour with city skyline in warm orange and pink sunset, modern outdoor furniture with beige cushions, string lights, tall ornamental grasses in terracotta planters",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "educational",
        "photo_avatar_id": "55bdbaaa7ded40458bfc0e498ff24ae6",
        "label": "Educational",
        "outfit_description": "Cozy oversized mustard yellow knit cardigan over fitted white tank top, delicate gold pendant necklace with small charm, small gold stud earrings, loose natural curls with side part, reading glasses on head",
        "environment_description": "Warm home office with light oak desk, beige ergonomic chair, open laptop and notebook, wooden floating shelves with books and succulents, cork pinboard with quotes, fairy lights along shelf edge",
        "is_active": True,
        "is_default": True,
    },
    {
        "content_type": "community",
        "photo_avatar_id": "6a7f86c8c60544d497ae63695af00425",
        "label": "Community",
        "outfit_description": "Flowy fuchsia wrap blouse with subtle print detail, layered gold chain necklaces of varying lengths, medium bamboo hoop earrings, hair in protective twist-out style with volume",
        "environment_description": "Trendy coffee shop with exposed brick wall painted cream, wooden communal table with cappuccinos, hanging Edison bulb pendant lights, chalkboard menu, monstera plant, vintage cognac leather armchairs",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "relatable",
        "photo_avatar_id": "b6bb73219ff54f5eb2934b3047bf028f",
        "label": "Relatable",
        "outfit_description": "Oversized sage green hoodie slightly off one shoulder revealing tank strap, simple gold huggie earrings, thin gold chain bracelet, hair in messy topknot with loose face-framing pieces",
        "environment_description": "Cozy living room with plush beige sectional sofa with textured throw pillows in terracotta and cream, soft knit blanket, wooden coffee table with mug and journal, fiddle leaf fig plant, fairy lights, family photos",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "casual",
        "photo_avatar_id": "a33ab8bbeff5499a96ae613e5497247c",
        "label": "Casual",
        "outfit_description": "Vibrant yellow linen button-up shirt tied at waist over white fitted tank, gold layered delicate necklaces, tortoiseshell sunglasses on head, statement gold cuff bracelet, loose beachy waves",
        "environment_description": "Outdoor café terrace with wrought iron bistro table, espresso and croissant, potted lavender and olive trees in terracotta pots, cobblestone floor, cream canvas umbrella, pink bougainvillea on cream stucco wall",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "announcement",
        "photo_avatar_id": "e4fc74c588ba45ec9eb49020bd95417d",
        "label": "Announcement",
        "outfit_description": "Stunning royal blue satin blazer with peak lapels over nude silk camisole, dramatic gold chandelier earrings, sleek gold cuff bracelet, voluminous waves with deep side part",
        "environment_description": "Clean professional backdrop with cream textured wall, subtle branded element in warm beige and gold, modern minimalist console table with single orchid in white ceramic pot, abstract gold metal wall sculpture",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "outdoor",
        "photo_avatar_id": "79938b6165b649b9b724d1af99a3b4b5",
        "label": "Outdoor",
        "outfit_description": "Bright coral moisture-wicking fitted tank top, lightweight sage green running vest unzipped, sporty gold-accented smartwatch, small gold stud earrings, high sporty ponytail with matching coral sweatband",
        "environment_description": "Lush green park with manicured lawn and mature trees creating dappled shade, wooden park bench, gravel jogging path, distant runners softly blurred, city skyline through trees, colorful flower beds",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "studio",
        "photo_avatar_id": "4a5842d1f4de4d0ab4d0cb832b71a1d3",
        "label": "Studio",
        "outfit_description": "Sleek black halter-neck athletic crop top with criss-cross back detail, high-waisted purple compression leggings, delicate gold body chain, medium gold hoop earrings, hair slicked back in low ponytail",
        "environment_description": "Bright group fitness studio with polished light wood floors reflecting studio lights, full wall of mirrors, wall-mounted chrome ballet barre, neatly arranged exercise mats in earthy tones, motivational gold wall decal",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "lifestyle",
        "photo_avatar_id": "4c621fd3eae84def9dfcc5f25bd83c93",
        "label": "Lifestyle",
        "outfit_description": "Soft lavender cashmere wrap sweater falling off one shoulder, matching ribbed loungewear pants, delicate gold pendant necklace with small gemstone, tiny gold huggie earrings, loose natural waves with middle part",
        "environment_description": "Peaceful wellness corner with large cream linen armchair, chunky knit beige throw blanket, small wooden side table with herbal tea, lit candle and wellness journal, monstera and snake plants in woven baskets, macramé wall hanging",
        "is_active": True,
        "is_default": False,
    },
]


def run_migration():
    """Create the photo_avatar_looks table and seed initial data."""
    log_info("Starting photo_avatar_looks table migration...")

    client = get_supabase_client()

    # Note: Table creation should be done via Supabase Dashboard SQL editor
    # This script will seed the data assuming the table exists

    log_info("Seeding photo_avatar_looks table with initial data...")

    for avatar_data in INITIAL_PHOTO_AVATARS:
        avatar_data["created_at"] = datetime.now(timezone.utc).isoformat()
        avatar_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            # Upsert to handle re-runs
            result = client.table("photo_avatar_looks").upsert(
                avatar_data,
                on_conflict="content_type"
            ).execute()
            log_info(f"Upserted photo avatar for content_type: {avatar_data['content_type']}")
        except Exception as e:
            log_error(f"Failed to upsert {avatar_data['content_type']}: {e}")
            raise

    log_info("Migration completed successfully!")
    log_info(f"Seeded {len(INITIAL_PHOTO_AVATARS)} photo avatar looks")


if __name__ == "__main__":
    run_migration()
