"""Flask blueprint providing admin routes for managing photo avatar looks."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
)
from utils.logger import log_error, log_info, log_warning
from utils.supabase_rest import SupabaseRestClient
import pytz

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="templates",
)

SA_TZ = pytz.timezone("Africa/Johannesburg")

_supabase_client: Optional[SupabaseRestClient] = None


def _get_supabase_client() -> Optional[SupabaseRestClient]:
    """Return a cached Supabase client instance."""
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        log_error("Supabase credentials missing for admin routes")
        return None

    try:
        _supabase_client = SupabaseRestClient(url, key)
        log_info("Admin routes connected to Supabase")
    except Exception as exc:
        log_error(f"Failed to initialize Supabase for admin routes: {exc}")
        _supabase_client = None

    return _supabase_client


# =============================================================================
# Photo Avatar Looks Management
# =============================================================================

@admin_bp.route("/avatar-looks")
def avatar_looks_page():
    """Render the photo avatar looks management page."""
    return render_template("admin/avatar_looks.html")


@admin_bp.route("/api/avatar-looks", methods=["GET"])
def get_avatar_looks():
    """API: Get all photo avatar looks."""
    client = _get_supabase_client()
    if not client:
        return jsonify({"success": False, "error": "Database not connected"}), 503

    try:
        result = client.table("photo_avatar_looks").select("*").order("content_type").execute()
        looks = result.data if result.data else []

        log_info(f"Retrieved {len(looks)} photo avatar looks")
        return jsonify({
            "success": True,
            "looks": looks,
            "count": len(looks),
        })

    except Exception as e:
        log_error(f"Error fetching avatar looks: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/avatar-looks/<look_id>", methods=["GET"])
def get_avatar_look(look_id: str):
    """API: Get a single photo avatar look by ID."""
    client = _get_supabase_client()
    if not client:
        return jsonify({"success": False, "error": "Database not connected"}), 503

    try:
        result = client.table("photo_avatar_looks").select("*").eq("id", look_id).single().execute()

        if not result.data:
            return jsonify({"success": False, "error": "Look not found"}), 404

        return jsonify({
            "success": True,
            "look": result.data,
        })

    except Exception as e:
        log_error(f"Error fetching avatar look {look_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/avatar-looks", methods=["POST"])
def create_avatar_look():
    """API: Create a new photo avatar look."""
    client = _get_supabase_client()
    if not client:
        return jsonify({"success": False, "error": "Database not connected"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    required_fields = ["content_type", "photo_avatar_id", "label"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({
            "success": False,
            "error": f"Missing required fields: {', '.join(missing)}"
        }), 400

    try:
        now = datetime.now(timezone.utc).isoformat()

        look_data = {
            "content_type": data["content_type"].lower().strip(),
            "photo_avatar_id": data["photo_avatar_id"].strip(),
            "label": data["label"].strip(),
            "outfit_description": data.get("outfit_description", ""),
            "environment_description": data.get("environment_description", ""),
            "makeup_description": data.get("makeup_description", ""),
            "lighting_description": data.get("lighting_description", ""),
            "is_active": data.get("is_active", True),
            "is_default": data.get("is_default", False),
            "created_at": now,
            "updated_at": now,
        }

        # If setting as default, unset other defaults first
        if look_data["is_default"]:
            client.table("photo_avatar_looks").update({
                "is_default": False,
                "updated_at": now,
            }).eq("is_default", True).execute()

        result = client.table("photo_avatar_looks").insert(look_data).execute()

        if result.data:
            log_info(f"Created avatar look: {look_data['content_type']}")
            return jsonify({
                "success": True,
                "look": result.data[0],
                "message": "Avatar look created successfully",
            }), 201
        else:
            return jsonify({"success": False, "error": "Failed to create look"}), 500

    except Exception as e:
        log_error(f"Error creating avatar look: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/avatar-looks/<look_id>", methods=["PUT"])
def update_avatar_look(look_id: str):
    """API: Update an existing photo avatar look."""
    client = _get_supabase_client()
    if not client:
        return jsonify({"success": False, "error": "Database not connected"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    try:
        now = datetime.now(timezone.utc).isoformat()

        update_data = {"updated_at": now}

        # Only update fields that are provided
        allowed_fields = [
            "content_type", "photo_avatar_id", "label",
            "outfit_description", "environment_description",
            "makeup_description", "lighting_description",
            "is_active", "is_default"
        ]

        for field in allowed_fields:
            if field in data:
                if field == "content_type":
                    update_data[field] = data[field].lower().strip()
                elif isinstance(data[field], str):
                    update_data[field] = data[field].strip()
                else:
                    update_data[field] = data[field]

        # If setting as default, unset other defaults first
        if update_data.get("is_default"):
            client.table("photo_avatar_looks").update({
                "is_default": False,
                "updated_at": now,
            }).eq("is_default", True).neq("id", look_id).execute()

        result = client.table("photo_avatar_looks").update(update_data).eq("id", look_id).execute()

        if result.data:
            log_info(f"Updated avatar look: {look_id}")
            return jsonify({
                "success": True,
                "look": result.data[0],
                "message": "Avatar look updated successfully",
            })
        else:
            return jsonify({"success": False, "error": "Look not found"}), 404

    except Exception as e:
        log_error(f"Error updating avatar look {look_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/avatar-looks/<look_id>", methods=["DELETE"])
def delete_avatar_look(look_id: str):
    """API: Delete a photo avatar look."""
    client = _get_supabase_client()
    if not client:
        return jsonify({"success": False, "error": "Database not connected"}), 503

    try:
        # Check if it's the default - prevent deletion
        check = client.table("photo_avatar_looks").select("is_default").eq("id", look_id).single().execute()

        if check.data and check.data.get("is_default"):
            return jsonify({
                "success": False,
                "error": "Cannot delete the default avatar look. Set another as default first."
            }), 400

        result = client.table("photo_avatar_looks").delete().eq("id", look_id).execute()

        log_info(f"Deleted avatar look: {look_id}")
        return jsonify({
            "success": True,
            "message": "Avatar look deleted successfully",
        })

    except Exception as e:
        log_error(f"Error deleting avatar look {look_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/avatar-looks/<look_id>/set-default", methods=["POST"])
def set_default_avatar_look(look_id: str):
    """API: Set a photo avatar look as the default."""
    client = _get_supabase_client()
    if not client:
        return jsonify({"success": False, "error": "Database not connected"}), 503

    try:
        now = datetime.now(timezone.utc).isoformat()

        # Unset all defaults
        client.table("photo_avatar_looks").update({
            "is_default": False,
            "updated_at": now,
        }).eq("is_default", True).execute()

        # Set new default
        result = client.table("photo_avatar_looks").update({
            "is_default": True,
            "updated_at": now,
        }).eq("id", look_id).execute()

        if result.data:
            log_info(f"Set default avatar look: {look_id}")
            return jsonify({
                "success": True,
                "look": result.data[0],
                "message": "Default avatar look updated",
            })
        else:
            return jsonify({"success": False, "error": "Look not found"}), 404

    except Exception as e:
        log_error(f"Error setting default avatar look: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/avatar-looks/<look_id>/toggle-active", methods=["POST"])
def toggle_avatar_look_active(look_id: str):
    """API: Toggle the active status of a photo avatar look."""
    client = _get_supabase_client()
    if not client:
        return jsonify({"success": False, "error": "Database not connected"}), 503

    try:
        # Get current status
        check = client.table("photo_avatar_looks").select("is_active, is_default").eq("id", look_id).single().execute()

        if not check.data:
            return jsonify({"success": False, "error": "Look not found"}), 404

        # Prevent deactivating the default
        if check.data.get("is_default") and check.data.get("is_active"):
            return jsonify({
                "success": False,
                "error": "Cannot deactivate the default avatar look."
            }), 400

        new_status = not check.data.get("is_active", True)
        now = datetime.now(timezone.utc).isoformat()

        result = client.table("photo_avatar_looks").update({
            "is_active": new_status,
            "updated_at": now,
        }).eq("id", look_id).execute()

        if result.data:
            status_text = "activated" if new_status else "deactivated"
            log_info(f"Avatar look {look_id} {status_text}")
            return jsonify({
                "success": True,
                "look": result.data[0],
                "message": f"Avatar look {status_text}",
            })
        else:
            return jsonify({"success": False, "error": "Failed to update"}), 500

    except Exception as e:
        log_error(f"Error toggling avatar look status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/avatar-looks/test/<content_type>", methods=["GET"])
def test_avatar_selection(content_type: str):
    """API: Test which avatar would be selected for a content type."""
    client = _get_supabase_client()
    if not client:
        return jsonify({"success": False, "error": "Database not connected"}), 503

    try:
        # Query for looks matching this content type
        result = client.table("photo_avatar_looks").select("*").eq("content_type", content_type.lower()).eq("is_active", True).execute()

        looks = result.data if result.data else []

        if not looks:
            # Try to find the default look
            default_result = client.table("photo_avatar_looks").select("*").eq("is_default", True).execute()
            default_look = default_result.data[0] if default_result.data else None

            return jsonify({
                "success": True,
                "content_type": content_type,
                "matched_looks": [],
                "selected_look": default_look,
                "fallback_used": True,
                "message": f"No active looks found for '{content_type}'. Using default look.",
            })

        # Select the default look for this content type, or the first active one
        selected_look = next((l for l in looks if l.get("is_default")), looks[0])

        return jsonify({
            "success": True,
            "content_type": content_type,
            "matched_looks": looks,
            "selected_look": selected_look,
            "fallback_used": False,
            "message": f"Found {len(looks)} active look(s) for '{content_type}'",
        })

    except Exception as e:
        log_error(f"Error testing avatar selection for {content_type}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/debug/check-looks")
def debug_check_looks():
    """Debug endpoint to check photo_avatar_looks table contents."""
    from utils.logger import log_info, log_error

    client = _get_supabase_client()
    if not client:
        error_msg = "Database not connected"
        log_error(error_msg)
        return jsonify({"success": False, "error": error_msg}), 503

    try:
        log_info("=" * 80)
        log_info("CHECKING PHOTO_AVATAR_LOOKS TABLE")
        log_info("=" * 80)

        # Get all records
        result = client.table("photo_avatar_looks").select("*").execute()
        looks = result.data if result.data else []

        log_info(f"📊 Total records found: {len(looks)}")

        if not looks:
            log_info("⚠️  Table is EMPTY - no avatar looks found")
            return jsonify({
                "success": True,
                "total_records": 0,
                "looks": [],
                "message": "Table is empty - needs seeding"
            })

        # Count by content_type
        by_type = {}
        default_look = None

        for look in looks:
            content_type = look.get("content_type", "unknown")
            by_type[content_type] = by_type.get(content_type, 0) + 1

            if look.get("is_default"):
                default_look = look

            log_info(f"  - {content_type}: {look.get('label')} (Active: {look.get('is_active')}, Default: {look.get('is_default')})")

        log_info(f"\n📊 Breakdown by content_type:")
        for ctype, count in by_type.items():
            log_info(f"  - {ctype}: {count}")

        if default_look:
            log_info(f"\n⭐ Default look: {default_look.get('content_type')} - {default_look.get('label')}")
        else:
            log_info("⚠️  No default look set!")

        log_info("=" * 80)

        return jsonify({
            "success": True,
            "total_records": len(looks),
            "by_content_type": by_type,
            "default_look": default_look,
            "looks": looks
        })

    except Exception as e:
        log_error(f"Error checking looks table: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/debug/seed-looks", methods=["POST"])
def debug_seed_looks():
    """Debug endpoint to seed photo_avatar_looks table with default data."""
    from utils.logger import log_info, log_error
    from datetime import datetime, timezone

    client = _get_supabase_client()
    if not client:
        error_msg = "Database not connected"
        log_error(error_msg)
        return jsonify({"success": False, "error": error_msg}), 503

    try:
        log_info("=" * 80)
        log_info("🌱 SEEDING PHOTO_AVATAR_LOOKS TABLE")
        log_info("=" * 80)

        # Check if already has data
        check = client.table("photo_avatar_looks").select("id").limit(1).execute()
        if check.data and len(check.data) > 0:
            log_info("⚠️  Table already has data. Skipping seed.")
            return jsonify({
                "success": False,
                "message": "Table already has data. Clear it first if you want to re-seed."
            }), 400

        now = datetime.now(timezone.utc).isoformat()

        # Define the 13 avatar looks
        avatar_looks = [
            {
                "content_type": "business",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Business Professional",
                "outfit_description": "Professional business attire, blazer",
                "environment_description": "Modern office setting",
                "is_active": True,
                "is_default": True,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "workout",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Gym Workout",
                "outfit_description": "Athletic workout gear",
                "environment_description": "Gym or fitness studio",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "fitness",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Fitness Training",
                "outfit_description": "Fitness training outfit",
                "environment_description": "Training area or outdoor",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "professional",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Professional",
                "outfit_description": "Professional attire",
                "environment_description": "Professional setting",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "motivational",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Motivational",
                "outfit_description": "Confident, inspiring outfit",
                "environment_description": "Inspiring background",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "educational",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Educational",
                "outfit_description": "Smart casual teaching attire",
                "environment_description": "Learning environment",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "community",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Community",
                "outfit_description": "Friendly, approachable outfit",
                "environment_description": "Community space",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "relatable",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Relatable",
                "outfit_description": "Casual, everyday outfit",
                "environment_description": "Everyday setting",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "casual",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Casual",
                "outfit_description": "Relaxed casual wear",
                "environment_description": "Casual environment",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "announcement",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Announcement",
                "outfit_description": "Professional announcement attire",
                "environment_description": "Clean, professional background",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "outdoor",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Outdoor",
                "outfit_description": "Outdoor activity wear",
                "environment_description": "Outdoor natural setting",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "studio",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Studio",
                "outfit_description": "Studio presentation attire",
                "environment_description": "Professional studio",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "content_type": "lifestyle",
                "photo_avatar_id": "REPLACE_WITH_ACTUAL_ID",
                "label": "Lifestyle",
                "outfit_description": "Lifestyle casual wear",
                "environment_description": "Lifestyle setting",
                "is_active": True,
                "is_default": False,
                "created_at": now,
                "updated_at": now
            }
        ]

        # Insert all looks
        inserted_count = 0
        for look in avatar_looks:
            result = client.table("photo_avatar_looks").insert(look).execute()
            if result.data:
                inserted_count += 1
                log_info(f"✅ Inserted: {look['content_type']}")
            else:
                log_error(f"❌ Failed to insert: {look['content_type']}")

        log_info(f"\n🎉 Seeding complete! {inserted_count}/{len(avatar_looks)} looks inserted")
        log_info("=" * 80)

        return jsonify({
            "success": True,
            "inserted": inserted_count,
            "total": len(avatar_looks),
            "message": f"Successfully seeded {inserted_count} avatar looks"
        })

    except Exception as e:
        log_error(f"Error seeding looks: {e}")
        import traceback
        log_error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500
