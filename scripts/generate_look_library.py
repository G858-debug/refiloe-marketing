#!/usr/bin/env python3
"""Generate a library of predefined avatar looks for Refiloe.

This script generates a comprehensive library of avatar looks for various use cases,
saves the results to a JSON file, and provides Railway environment variable commands.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add parent directory to path to import utilities
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import log_debug, log_error, log_info, log_warning

console = Console()


# ============================================================================
# Look Scenario Definitions
# ============================================================================

REFILOE_LOOK_SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "morning_workout_energy",
        "label": "Morning Workout Energy",
        "outfit": "bright athletic wear (sports bra, leggings) in sunrise colors",
        "environment": "modern gym with large windows showing sunrise, natural morning light",
        "pose": "energetic standing pose with confident stance",
        "mood": "energized and motivational",
        "use_case": "Morning motivation posts, workout challenges, fitness tips at dawn",
        "tags": ["fitness", "morning", "energy", "gym"],
    },
    {
        "name": "professional_consultation",
        "label": "Professional Consultation",
        "outfit": "smart business attire (blazer, professional blouse)",
        "environment": "clean office space with minimalist background, professional lighting",
        "pose": "seated at desk with confident posture, facing camera",
        "mood": "professional and approachable",
        "use_case": "Business advice, client consultations, revenue strategy discussions",
        "tags": ["business", "professional", "consultation", "office"],
    },
    {
        "name": "weekend_motivation",
        "label": "Weekend Motivation",
        "outfit": "casual athleisure (stylish joggers, fitted tank top)",
        "environment": "outdoor park with trees and natural scenery, soft natural lighting",
        "pose": "relaxed standing pose in nature",
        "mood": "friendly and encouraging",
        "use_case": "Weekend wellness tips, casual check-ins, lifestyle content",
        "tags": ["weekend", "casual", "outdoor", "lifestyle"],
    },
    {
        "name": "success_celebration",
        "label": "Success Story Celebration",
        "outfit": "confident athletic wear (stylish sports outfit)",
        "environment": "inspiring backdrop with achievement theme, dramatic lighting",
        "pose": "powerful standing pose with open body language",
        "mood": "triumphant and inspiring",
        "use_case": "Client transformations, milestone celebrations, success stories",
        "tags": ["success", "transformation", "celebration", "inspiration"],
    },
    {
        "name": "educational_tutorial",
        "label": "Educational Tutorial",
        "outfit": "approachable smart-casual (clean blouse, comfortable pants)",
        "environment": "well-lit studio with neutral background, clear visibility",
        "pose": "standing position ready to demonstrate or explain",
        "mood": "knowledgeable and friendly",
        "use_case": "How-to videos, educational content, technique tutorials",
        "tags": ["education", "tutorial", "teaching", "studio"],
    },
    {
        "name": "community_gathering",
        "label": "Community Gathering",
        "outfit": "warm casual outfit (comfortable sweater, jeans)",
        "environment": "cozy group-friendly space with inviting atmosphere",
        "pose": "welcoming open stance",
        "mood": "warm and inclusive",
        "use_case": "Community announcements, group challenges, social engagement",
        "tags": ["community", "social", "gathering", "inclusive"],
    },
    {
        "name": "nutrition_advice",
        "label": "Nutrition Expert",
        "outfit": "clean smart-casual (light blouse, minimal accessories)",
        "environment": "bright modern kitchen or café with fresh ingredients visible",
        "pose": "standing near counter or table",
        "mood": "knowledgeable and relatable",
        "use_case": "Nutrition tips, meal planning advice, healthy eating content",
        "tags": ["nutrition", "kitchen", "health", "food"],
    },
    {
        "name": "mindfulness_wellness",
        "label": "Mindfulness & Wellness",
        "outfit": "flowing comfortable clothes (soft yoga wear or linen)",
        "environment": "peaceful setting with natural elements, soft diffused lighting",
        "pose": "calm seated or standing meditation pose",
        "mood": "serene and centered",
        "use_case": "Meditation guidance, wellness tips, stress management content",
        "tags": ["mindfulness", "wellness", "meditation", "peace"],
    },
    {
        "name": "business_strategy",
        "label": "Business Strategy",
        "outfit": "executive business attire (suit or professional dress)",
        "environment": "corporate office with modern workspace, professional backdrop",
        "pose": "standing or seated at executive desk",
        "mood": "authoritative and confident",
        "use_case": "Business growth tips, strategy sessions, leadership content",
        "tags": ["business", "strategy", "leadership", "corporate"],
    },
    {
        "name": "client_transformation",
        "label": "Client Transformation Showcase",
        "outfit": "confident athletic wear showing physique (sports attire)",
        "environment": "motivational backdrop highlighting progress",
        "pose": "confident power pose",
        "mood": "proud and empowering",
        "use_case": "Before/after showcases, client success stories, transformation reveals",
        "tags": ["transformation", "fitness", "success", "confidence"],
    },
    {
        "name": "morning_routine",
        "label": "Morning Routine Guide",
        "outfit": "fresh morning athleisure (clean workout clothes)",
        "environment": "home setting with morning light streaming through windows",
        "pose": "energetic morning stretch or ready-to-start pose",
        "mood": "fresh and ready",
        "use_case": "Morning routine videos, daily habits, sunrise workouts",
        "tags": ["morning", "routine", "home", "habits"],
    },
    {
        "name": "strength_training",
        "label": "Strength Training Coach",
        "outfit": "functional athletic wear (sports top, shorts, training shoes)",
        "environment": "gym with weight equipment and mirrors",
        "pose": "demonstrating proper form or ready to train",
        "mood": "strong and focused",
        "use_case": "Strength training tips, form guidance, workout demonstrations",
        "tags": ["strength", "training", "gym", "fitness"],
    },
    {
        "name": "yoga_flow",
        "label": "Yoga Flow Instructor",
        "outfit": "flexible yoga wear (fitted top, yoga pants)",
        "environment": "peaceful yoga studio with wooden floors and plants",
        "pose": "graceful yoga pose or ready stance",
        "mood": "balanced and peaceful",
        "use_case": "Yoga tutorials, flexibility training, mindful movement",
        "tags": ["yoga", "flexibility", "studio", "mindful"],
    },
    {
        "name": "cardio_blast",
        "label": "Cardio Energy Blast",
        "outfit": "vibrant high-energy workout clothes (bright colors)",
        "environment": "dynamic fitness space with energetic atmosphere",
        "pose": "mid-movement or high-energy stance",
        "mood": "explosive and energetic",
        "use_case": "HIIT workouts, cardio challenges, high-energy sessions",
        "tags": ["cardio", "HIIT", "energy", "intense"],
    },
    {
        "name": "recovery_rest",
        "label": "Recovery & Rest Day",
        "outfit": "comfortable relaxed loungewear (soft fabrics)",
        "environment": "cozy home environment with calming elements",
        "pose": "relaxed seated or gentle stretch",
        "mood": "calm and restorative",
        "use_case": "Recovery tips, rest day importance, self-care content",
        "tags": ["recovery", "rest", "self-care", "relaxation"],
    },
    {
        "name": "outdoor_adventure",
        "label": "Outdoor Adventure Fitness",
        "outfit": "outdoor athletic gear (trail running or hiking attire)",
        "environment": "outdoor natural setting (park, trail, or nature backdrop)",
        "pose": "active outdoor stance",
        "mood": "adventurous and free",
        "use_case": "Outdoor workouts, nature fitness, adventure content",
        "tags": ["outdoor", "nature", "adventure", "active"],
    },
    {
        "name": "evening_windown",
        "label": "Evening Wind-Down",
        "outfit": "soft evening wellness wear (comfortable evening attire)",
        "environment": "warm evening setting with soft ambient lighting",
        "pose": "relaxed evening pose",
        "mood": "peaceful and reflective",
        "use_case": "Evening routines, wind-down tips, night-time wellness",
        "tags": ["evening", "wind-down", "wellness", "night"],
    },
    {
        "name": "podcast_conversation",
        "label": "Podcast Conversation",
        "outfit": "casual smart outfit (nice sweater or top)",
        "environment": "professional podcast studio with microphone setup",
        "pose": "seated conversational pose",
        "mood": "engaging and conversational",
        "use_case": "Podcast episodes, Q&A sessions, deep-dive conversations",
        "tags": ["podcast", "conversation", "Q&A", "studio"],
    },
    {
        "name": "beach_wellness",
        "label": "Beach Wellness Retreat",
        "outfit": "flowing beach-appropriate wellness wear",
        "environment": "beautiful beach or coastal setting with ocean backdrop",
        "pose": "relaxed beach stance",
        "mood": "tranquil and refreshing",
        "use_case": "Wellness retreats, beach workouts, vacation fitness",
        "tags": ["beach", "retreat", "wellness", "ocean"],
    },
    {
        "name": "studio_headshot",
        "label": "Professional Studio Headshot",
        "outfit": "clean solid-colored top (neutral professional)",
        "environment": "studio with neutral background and professional lighting",
        "pose": "confident headshot pose facing camera",
        "mood": "professional and warm",
        "use_case": "Profile pictures, marketing materials, professional branding",
        "tags": ["headshot", "professional", "studio", "branding"],
    },
]


# ============================================================================
# Helper Functions
# ============================================================================

def load_existing_library(file_path: str) -> Dict[str, Any]:
    """Load existing generated looks library from JSON file."""
    if not os.path.exists(file_path):
        return {"generated_at": None, "looks": {}, "metadata": {}}

    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        log_warning(f"Could not load existing library: {e}")
        return {"generated_at": None, "looks": {}, "metadata": {}}


def save_library(file_path: str, data: Dict[str, Any]) -> None:
    """Save generated looks library to JSON file."""
    os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)

    log_info(f"Library saved to {file_path}")


def build_prompt(scenario: Dict[str, Any]) -> str:
    """Build a complete prompt from scenario components."""
    parts = []

    if scenario.get('outfit'):
        parts.append(f"Person wearing {scenario['outfit']}")

    if scenario.get('pose'):
        parts.append(scenario['pose'])

    if scenario.get('environment'):
        parts.append(f"in {scenario['environment']}")

    if scenario.get('mood'):
        parts.append(f"{scenario['mood']} expression")

    return ", ".join(parts)


def generate_look_via_api(
    scenario: Dict[str, Any],
    api_url: str = "http://localhost:5050/api/generate-look",
    timeout: int = 600,
) -> Dict[str, Any]:
    """Generate a look by calling the API endpoint.

    Args:
        scenario: Scenario definition dictionary
        api_url: API endpoint URL
        timeout: Request timeout in seconds

    Returns:
        API response data

    Raises:
        requests.RequestException: If API call fails
    """
    payload = {
        "outfit": scenario.get("outfit"),
        "environment": scenario.get("environment"),
        "pose": scenario.get("pose"),
        "mood": scenario.get("mood"),
        "save_to_db": True,
    }

    log_info(f"Calling API to generate look: {scenario['name']}")

    response = requests.post(
        api_url,
        json=payload,
        timeout=timeout,
    )

    response.raise_for_status()
    return response.json()


def generate_env_var_name(scenario_name: str) -> str:
    """Generate environment variable name from scenario name."""
    return f"HEYGEN_AVATAR_{scenario_name.upper()}"


def generate_railway_commands(library: Dict[str, Any]) -> List[str]:
    """Generate Railway CLI commands to set environment variables."""
    commands = []

    for name, look_data in library.get("looks", {}).items():
        if look_data.get("photo_avatar_id"):
            env_var = generate_env_var_name(name)
            photo_id = look_data["photo_avatar_id"]
            commands.append(f"railway variables set {env_var}={photo_id}")

    return commands


def print_summary_report(
    library: Dict[str, Any],
    success_count: int,
    failure_count: int,
    skipped_count: int,
) -> None:
    """Print a summary report of the generation process."""
    console.print("\n" + "="*70, style="bold blue")
    console.print("📊 LOOK LIBRARY GENERATION SUMMARY", style="bold blue")
    console.print("="*70, style="bold blue")

    # Statistics
    console.print(f"\n✅ Successfully generated: {success_count}", style="green")
    console.print(f"❌ Failed: {failure_count}", style="red")
    console.print(f"⏭️  Skipped (already exists): {skipped_count}", style="yellow")
    console.print(f"📚 Total in library: {len(library.get('looks', {}))}", style="blue")

    # Table of generated looks
    if library.get("looks"):
        console.print("\n📋 Generated Looks:", style="bold")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Scenario Name", style="cyan", width=25)
        table.add_column("Label", style="yellow", width=25)
        table.add_column("Avatar ID", style="green", width=35)
        table.add_column("Status", style="white", width=10)

        for name, look_data in sorted(library["looks"].items()):
            avatar_id = look_data.get("photo_avatar_id", "N/A")
            status = "✅" if avatar_id != "N/A" else "❌"
            label = look_data.get("label", name)

            # Truncate long IDs
            display_id = avatar_id if len(avatar_id) <= 35 else avatar_id[:32] + "..."

            table.add_row(name, label, display_id, status)

        console.print(table)

    # Preview URLs
    console.print("\n🔗 Preview URLs:", style="bold")
    has_previews = False
    for name, look_data in sorted(library.get("looks", {}).items()):
        if look_data.get("preview_url"):
            has_previews = True
            console.print(f"  {look_data['label']}: {look_data['preview_url']}", style="dim")

    if not has_previews:
        console.print("  No preview URLs available", style="dim")

    # Environment variables
    console.print("\n🔧 Recommended Environment Variables:", style="bold")
    for name, look_data in sorted(library.get("looks", {}).items()):
        if look_data.get("photo_avatar_id"):
            env_var = generate_env_var_name(name)
            console.print(f"  {env_var}={look_data['photo_avatar_id']}", style="dim")

    console.print("\n" + "="*70 + "\n", style="bold blue")


# ============================================================================
# Main Generation Logic
# ============================================================================

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate a library of predefined avatar looks for Refiloe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all looks
  python scripts/generate_look_library.py

  # Preview what would be generated (dry run)
  python scripts/generate_look_library.py --dry-run

  # Generate only 5 looks for testing
  python scripts/generate_look_library.py --limit 5

  # Generate a specific scenario
  python scripts/generate_look_library.py --scenario morning_workout_energy

  # Use custom API URL and output file
  python scripts/generate_look_library.py --api-url http://example.com/api --output my_looks.json
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be generated without actually calling the API",
    )

    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Only generate N looks (useful for testing)",
    )

    parser.add_argument(
        "--scenario",
        type=str,
        metavar="NAME",
        help="Only generate a specific scenario by name",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="generated_looks_library.json",
        help="Output JSON file path (default: generated_looks_library.json)",
    )

    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:5050/api/generate-look",
        help="API endpoint URL (default: http://localhost:5050/api/generate-look)",
    )

    parser.add_argument(
        "--railway-commands",
        type=str,
        metavar="FILE",
        help="Output Railway CLI commands to a file",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regenerate looks that already exist in the library",
    )

    args = parser.parse_args()

    # Filter scenarios based on arguments
    scenarios_to_generate = REFILOE_LOOK_SCENARIOS

    if args.scenario:
        scenarios_to_generate = [
            s for s in scenarios_to_generate
            if s["name"] == args.scenario
        ]
        if not scenarios_to_generate:
            console.print(f"❌ Scenario '{args.scenario}' not found", style="red")
            console.print("\nAvailable scenarios:", style="yellow")
            for s in REFILOE_LOOK_SCENARIOS:
                console.print(f"  - {s['name']}: {s['label']}", style="dim")
            sys.exit(1)

    if args.limit:
        scenarios_to_generate = scenarios_to_generate[:args.limit]

    # Load existing library (for resumability)
    library = load_existing_library(args.output)

    # DRY RUN MODE
    if args.dry_run:
        console.print("🔍 DRY RUN MODE - Preview only\n", style="bold yellow")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Scenario Name", style="cyan", width=25)
        table.add_column("Label", style="yellow", width=25)
        table.add_column("Use Case", style="green", width=40)
        table.add_column("Tags", style="blue", width=30)

        for idx, scenario in enumerate(scenarios_to_generate, 1):
            tags = ", ".join(scenario.get("tags", []))
            table.add_row(
                str(idx),
                scenario["name"],
                scenario["label"],
                scenario["use_case"][:37] + "..." if len(scenario["use_case"]) > 40 else scenario["use_case"],
                tags,
            )

        console.print(table)
        console.print(f"\n📊 Total scenarios to generate: {len(scenarios_to_generate)}", style="bold")
        console.print(f"💾 Output file: {args.output}", style="dim")
        console.print(f"🔗 API endpoint: {args.api_url}", style="dim")

        # Show sample prompt
        if scenarios_to_generate:
            console.print("\n📝 Sample prompt for first scenario:", style="bold")
            sample = scenarios_to_generate[0]
            prompt = build_prompt(sample)
            console.print(f"  {prompt}", style="dim italic")

        return

    # ACTUAL GENERATION
    console.print("🚀 Starting Look Library Generation\n", style="bold green")
    console.print(f"📊 Scenarios to generate: {len(scenarios_to_generate)}", style="blue")
    console.print(f"💾 Output file: {args.output}", style="blue")
    console.print(f"🔗 API endpoint: {args.api_url}\n", style="blue")

    success_count = 0
    failure_count = 0
    skipped_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        for idx, scenario in enumerate(scenarios_to_generate, 1):
            scenario_name = scenario["name"]

            # Check if already exists (resumability)
            if not args.force and scenario_name in library.get("looks", {}):
                existing = library["looks"][scenario_name]
                if existing.get("photo_avatar_id"):
                    console.print(
                        f"⏭️  [{idx}/{len(scenarios_to_generate)}] Skipping {scenario['label']} - already exists",
                        style="yellow",
                    )
                    skipped_count += 1
                    continue

            task = progress.add_task(
                f"[{idx}/{len(scenarios_to_generate)}] Generating {scenario['label']}...",
                total=None,
            )

            try:
                # Generate the look
                result = generate_look_via_api(scenario, api_url=args.api_url)

                if result.get("success"):
                    # Save to library
                    library["looks"][scenario_name] = {
                        "name": scenario_name,
                        "label": scenario["label"],
                        "use_case": scenario["use_case"],
                        "tags": scenario["tags"],
                        "outfit": scenario.get("outfit"),
                        "environment": scenario.get("environment"),
                        "pose": scenario.get("pose"),
                        "mood": scenario.get("mood"),
                        "photo_avatar_id": result.get("photo_avatar_id"),
                        "look_id": result.get("look_id"),
                        "preview_url": result.get("preview_url"),
                        "prompt_used": result.get("prompt_used"),
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                    }

                    library["metadata"] = {
                        "last_updated": datetime.utcnow().isoformat() + "Z",
                        "total_looks": len(library["looks"]),
                        "api_url": args.api_url,
                    }

                    # Save after each successful generation (resumability)
                    save_library(args.output, library)

                    console.print(
                        f"✅ [{idx}/{len(scenarios_to_generate)}] Generated {scenario['label']} - "
                        f"ID: {result.get('photo_avatar_id', 'N/A')[:16]}...",
                        style="green",
                    )
                    success_count += 1
                else:
                    error_msg = result.get("error", "Unknown error")
                    console.print(
                        f"❌ [{idx}/{len(scenarios_to_generate)}] Failed {scenario['label']}: {error_msg}",
                        style="red",
                    )
                    failure_count += 1

            except Exception as e:
                console.print(
                    f"❌ [{idx}/{len(scenarios_to_generate)}] Error generating {scenario['label']}: {str(e)}",
                    style="red",
                )
                log_error(f"Error generating {scenario_name}: {e}")
                failure_count += 1

            finally:
                progress.remove_task(task)

            # Small delay between requests to avoid overwhelming the API
            if idx < len(scenarios_to_generate):
                time.sleep(2)

    # Save final library
    save_library(args.output, library)

    # Generate Railway commands if requested
    if args.railway_commands:
        commands = generate_railway_commands(library)
        with open(args.railway_commands, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Generated Railway environment variable commands\n")
            f.write(f"# Generated at: {datetime.utcnow().isoformat()}Z\n\n")
            for cmd in commands:
                f.write(cmd + "\n")
        console.print(f"\n💾 Railway commands saved to: {args.railway_commands}", style="green")

    # Print summary report
    print_summary_report(library, success_count, failure_count, skipped_count)

    # Exit with appropriate code
    if failure_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
