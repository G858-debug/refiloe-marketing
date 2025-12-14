#!/usr/bin/env python3
"""
Seed script to populate the photo_avatar_looks table with 13 avatar configurations.

This script:
1. Connects to Supabase using environment variables
2. Inserts 13 avatar look records into photo_avatar_looks table
3. Sets 'educational' as the default look
4. Handles duplicates gracefully by checking before inserting

Usage:
    python scripts/seed_avatar_looks.py

Environment variables required:
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        logger.error("Missing required environment variables")
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")

    logger.info(f"Connecting to Supabase at {url}")
    return create_client(url, key)


# Avatar look configurations
AVATAR_LOOKS = [
    {
        "content_type": "workout",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Workout",
        "outfit_description": "Fitted coral athletic crop top with thin straps, high-waisted burgundy leggings, delicate gold body chain across collarbone, small gold hoop earrings",
        "environment_description": "Modern boutique gym with warm wood-paneled accent wall, chrome dumbbells on beige leather bench, floor-to-ceiling window with golden morning light, snake plant in terracotta pot",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "fitness",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Fitness",
        "outfit_description": "Electric blue racerback athletic top with mesh panel detail, matching blue sports bra visible underneath, thin gold necklace with small pendant, medium gold hoop earrings, hair in two neat cornrow braids",
        "environment_description": "Bright fitness studio with floor-to-ceiling mirrors, polished light oak hardwood floors, ballet barre on cream wall, stacked yoga mats in earthy tones on wooden shelving",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "professional",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Professional",
        "outfit_description": "Structured hot pink blazer with padded shoulders over cream silk camisole with delicate lace trim, thin gold layered necklaces, statement gold drop earrings, hair in sophisticated low bun",
        "environment_description": "Modern co-working space with large beige linen sofa and cognac leather armchair, brass floor lamp with cream shade, floating wooden shelves with books and fiddle leaf fig, abstract art in terracotta and gold",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "business",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Business",
        "outfit_description": "Tailored emerald green power blazer with gold button detail over crisp white V-neck blouse, gold chain-link earrings, delicate gold watch, hair straightened and flowing over one shoulder",
        "environment_description": "Executive office with mahogany desk, beige leather executive chair, floor-to-ceiling bookshelf with leather-bound books and bronze sculptures, city skyline visible through window",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "motivational",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Motivational",
        "outfit_description": "Bold orange off-shoulder crop top showing toned shoulders, high-waisted camel wide-leg trousers, chunky gold statement necklace, large gold hoop earrings, voluminous natural afro with golden highlights",
        "environment_description": "Rooftop terrace at golden hour with city skyline in warm orange and pink sunset, modern outdoor furniture with beige cushions, string lights, tall ornamental grasses in terracotta planters",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "educational",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Educational",
        "outfit_description": "Cozy oversized mustard yellow knit cardigan over fitted white tank top, delicate gold pendant necklace with small charm, small gold stud earrings, loose natural curls with side part",
        "environment_description": "Warm home office with light oak desk, beige ergonomic chair, open laptop and notebook, wooden floating shelves with books and succulents, cork pinboard with quotes, fairy lights along shelf edge",
        "is_active": True,
        "is_default": True,  # Educational is the default
    },
    {
        "content_type": "community",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Community",
        "outfit_description": "Flowy fuchsia wrap blouse with subtle print detail, layered gold chain necklaces of varying lengths, medium bamboo hoop earrings, hair in protective twist-out style with volume",
        "environment_description": "Trendy coffee shop with exposed brick wall painted cream, wooden communal table with cappuccinos, hanging Edison bulb pendant lights, chalkboard menu, monstera plant, vintage cognac leather armchairs",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "relatable",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Relatable",
        "outfit_description": "Oversized sage green hoodie slightly off one shoulder revealing tank strap, simple gold huggie earrings, thin gold chain bracelet, hair in messy topknot with loose face-framing pieces",
        "environment_description": "Cozy living room with plush beige sectional sofa with textured throw pillows in terracotta and cream, soft knit blanket, wooden coffee table with mug and journal, fiddle leaf fig plant, fairy lights, family photos",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "casual",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Casual",
        "outfit_description": "Vibrant yellow linen button-up shirt tied at waist over white fitted tank, gold layered delicate necklaces, statement gold cuff bracelet, loose beachy waves",
        "environment_description": "Outdoor café terrace with wrought iron bistro table, espresso and croissant, potted lavender and olive trees in terracotta pots, cobblestone floor, cream canvas umbrella, pink bougainvillea on cream stucco wall",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "announcement",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Announcement",
        "outfit_description": "Stunning royal blue satin blazer with peak lapels over nude silk camisole, dramatic gold chandelier earrings, sleek gold cuff bracelet, voluminous waves with deep side part",
        "environment_description": "Clean professional backdrop with cream textured wall, subtle branded element in warm beige and gold, modern minimalist console table with single orchid in white ceramic pot, abstract gold metal wall sculpture",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "outdoor",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Outdoor",
        "outfit_description": "Bright coral moisture-wicking fitted tank top, lightweight sage green running vest unzipped, sporty gold-accented smartwatch, small gold stud earrings, high sporty ponytail with matching coral sweatband",
        "environment_description": "Lush green park with manicured lawn and mature trees creating dappled shade, wooden park bench, gravel jogging path, distant runners softly blurred, city skyline through trees, colorful flower beds",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "studio",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Studio",
        "outfit_description": "Sleek black halter-neck athletic crop top with criss-cross back detail, high-waisted purple compression leggings, delicate gold body chain, medium gold hoop earrings, hair slicked back in low ponytail",
        "environment_description": "Bright group fitness studio with polished light wood floors reflecting studio lights, full wall of mirrors, wall-mounted chrome ballet barre, neatly arranged exercise mats in earthy tones, motivational gold wall decal",
        "is_active": True,
        "is_default": False,
    },
    {
        "content_type": "lifestyle",
        "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
        "label": "Lifestyle",
        "outfit_description": "Soft lavender cashmere wrap sweater falling off one shoulder, matching ribbed loungewear pants, delicate gold pendant necklace with small gemstone, tiny gold huggie earrings, loose natural waves with middle part",
        "environment_description": "Peaceful wellness corner with large cream linen armchair, chunky knit beige throw blanket, small wooden side table with herbal tea, lit candle and wellness journal, monstera and snake plants in woven baskets, macramé wall hanging",
        "is_active": True,
        "is_default": False,
    },
]


def check_existing_record(client: Client, content_type: str) -> bool:
    """Check if a record with the given content_type already exists."""
    try:
        result = client.table("photo_avatar_looks").select("content_type").eq("content_type", content_type).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.warning(f"Error checking for existing record {content_type}: {e}")
        return False


def seed_avatar_looks():
    """Seed the photo_avatar_looks table with avatar configurations."""
    logger.info("=" * 80)
    logger.info("Starting Avatar Looks Seeding")
    logger.info("=" * 80)

    try:
        client = get_supabase_client()
        logger.info("Successfully connected to Supabase")

        inserted_count = 0
        skipped_count = 0
        error_count = 0

        logger.info(f"\nProcessing {len(AVATAR_LOOKS)} avatar look configurations...")
        logger.info("-" * 80)

        for i, avatar_data in enumerate(AVATAR_LOOKS, 1):
            content_type = avatar_data["content_type"]
            is_default = avatar_data.get("is_default", False)

            logger.info(f"\n[{i}/{len(AVATAR_LOOKS)}] Processing: {content_type} {'(DEFAULT)' if is_default else ''}")

            # Check if record already exists
            if check_existing_record(client, content_type):
                logger.warning(f"  ⚠️  Record already exists, skipping...")
                skipped_count += 1
                continue

            # Add timestamps
            avatar_data["created_at"] = datetime.now(timezone.utc).isoformat()
            avatar_data["updated_at"] = datetime.now(timezone.utc).isoformat()

            try:
                result = client.table("photo_avatar_looks").insert(avatar_data).execute()
                logger.info(f"  ✅ Successfully inserted {content_type}")
                logger.info(f"     Label: {avatar_data['label']}")
                logger.info(f"     Outfit: {avatar_data['outfit_description'][:60]}...")
                inserted_count += 1
            except Exception as e:
                logger.error(f"  ❌ Failed to insert {content_type}: {e}")
                error_count += 1

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("SEEDING SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✅ Successfully inserted: {inserted_count}")
        logger.info(f"⚠️  Skipped (already exist): {skipped_count}")
        logger.info(f"❌ Errors: {error_count}")
        logger.info(f"📊 Total processed: {len(AVATAR_LOOKS)}")

        if inserted_count > 0:
            logger.info("\n" + "⚡" * 80)
            logger.info("NEXT STEPS:")
            logger.info("⚡" * 80)
            logger.info("1. Update each record's 'photo_avatar_id' with actual HeyGen avatar IDs")
            logger.info("2. Replace 'REPLACE_WITH_ACTUAL_ID' placeholders in the database")
            logger.info("3. Verify the 'educational' look is set as default (is_default=true)")
            logger.info("⚡" * 80)

        if error_count > 0:
            logger.error("\n⚠️  Some records failed to insert. Please check the errors above.")
            sys.exit(1)
        else:
            logger.info("\n🎉 Seeding completed successfully!")
            sys.exit(0)

    except ValueError as e:
        logger.error(f"\n❌ Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    seed_avatar_looks()
