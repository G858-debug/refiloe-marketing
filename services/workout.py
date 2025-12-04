"""
Workout Service for Refiloe WhatsApp Assistant
Handles workout template management, exercise library, and workout history tracking
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import pytz
import uuid
import os
import json
import re
import random
import time

from anthropic import Anthropic
from utils.logger import log_info, log_error, log_warning

# Maximum characters per WhatsApp message for workout
MAX_WORKOUT_MESSAGE_LENGTH = 1600

SA_TZ = pytz.timezone('Africa/Johannesburg')


class WorkoutService:
    """
    Service for managing workouts, exercises, and workout history.

    Provides methods for:
    - Exercise library management
    - Workout template CRUD operations
    - Workout history tracking
    - Sending workouts to clients
    """

    def __init__(self, db):
        """
        Initialize the workout service.

        Args:
            db: Database service instance
        """
        self.db = db

    # =========================================================================
    # EXERCISE LIBRARY
    # =========================================================================

    def get_exercises(self, category: str = None, limit: int = 50) -> List[Dict]:
        """
        Get exercises from the library.

        Args:
            category: Optional category filter (e.g., 'strength', 'cardio')
            limit: Maximum number of exercises to return

        Returns:
            List of exercise dictionaries
        """
        try:
            query = self.db.db.table('exercises').select(
                'id, name, description, category, muscle_group, equipment, '
                'difficulty, gif_url_male, gif_url_female, instructions'
            ).limit(limit)

            if category:
                query = query.eq('category', category)

            result = query.execute()

            if result and hasattr(result, 'data'):
                return result.data
            return []

        except Exception as e:
            log_error(f"Error fetching exercises: {str(e)}")
            return []

    def get_exercise_by_id(self, exercise_id: str) -> Optional[Dict]:
        """
        Get a single exercise by ID.

        Args:
            exercise_id: Exercise UUID

        Returns:
            Exercise dictionary or None
        """
        try:
            result = self.db.db.table('exercises').select('*').eq(
                'id', exercise_id
            ).execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error fetching exercise {exercise_id}: {str(e)}")
            return None

    def search_exercises(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search exercises by name or muscle group.

        Args:
            query: Search query string
            limit: Maximum results

        Returns:
            List of matching exercises
        """
        try:
            # Search in name (case-insensitive)
            result = self.db.db.table('exercises').select(
                'id, name, description, category, muscle_group, equipment, '
                'difficulty, gif_url_male, gif_url_female'
            ).ilike('name', f'%{query}%').limit(limit).execute()

            if result and hasattr(result, 'data'):
                return result.data
            return []

        except Exception as e:
            log_error(f"Error searching exercises: {str(e)}")
            return []

    def get_exercise_categories(self) -> List[str]:
        """
        Get list of unique exercise categories.

        Returns:
            List of category names
        """
        try:
            result = self.db.db.table('exercises').select('category').execute()

            if result and hasattr(result, 'data'):
                categories = set(ex.get('category') for ex in result.data if ex.get('category'))
                return sorted(list(categories))
            return []

        except Exception as e:
            log_error(f"Error fetching categories: {str(e)}")
            return []

    # =========================================================================
    # WORKOUT TEMPLATES
    # =========================================================================

    def get_workout_templates(self, trainer_id: str, limit: int = 20) -> List[Dict]:
        """
        Get workout templates for a trainer.

        Args:
            trainer_id: Trainer's ID
            limit: Maximum templates to return

        Returns:
            List of workout template dictionaries
        """
        try:
            result = self.db.db.table('workout_templates').select(
                'id, name, description, category, difficulty, duration_minutes, '
                'exercises, created_at'
            ).eq('trainer_id', trainer_id).order(
                'created_at', desc=True
            ).limit(limit).execute()

            if result and hasattr(result, 'data'):
                return result.data
            return []

        except Exception as e:
            log_error(f"Error fetching workout templates: {str(e)}")
            return []

    def get_workout_template_by_id(self, template_id: str) -> Optional[Dict]:
        """
        Get a single workout template by ID.

        Args:
            template_id: Template UUID

        Returns:
            Template dictionary or None
        """
        try:
            result = self.db.db.table('workout_templates').select('*').eq(
                'id', template_id
            ).execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error fetching template {template_id}: {str(e)}")
            return None

    def create_workout_template(self, trainer_id: str, name: str,
                                 description: str, exercises: List[Dict],
                                 category: str = None, difficulty: str = None,
                                 duration_minutes: int = None) -> Optional[Dict]:
        """
        Create a new workout template.

        Args:
            trainer_id: Trainer's ID
            name: Template name
            description: Template description
            exercises: List of exercise configurations with sets/reps
            category: Workout category (e.g., 'strength', 'hiit')
            difficulty: Difficulty level ('beginner', 'intermediate', 'advanced')
            duration_minutes: Estimated workout duration

        Returns:
            Created template dictionary or None
        """
        try:
            template_data = {
                'id': str(uuid.uuid4()),
                'trainer_id': trainer_id,
                'name': name,
                'description': description,
                'category': category,
                'difficulty': difficulty,
                'duration_minutes': duration_minutes,
                'exercises': exercises,
                'created_at': datetime.now(SA_TZ).isoformat(),
                'updated_at': datetime.now(SA_TZ).isoformat()
            }

            result = self.db.db.table('workout_templates').insert(template_data).execute()

            if result and hasattr(result, 'data') and result.data:
                log_info(f"Created workout template: {template_data['id']}")
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error creating workout template: {str(e)}")
            return None

    def update_workout_template(self, template_id: str, updates: Dict) -> bool:
        """
        Update a workout template.

        Args:
            template_id: Template UUID
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        try:
            updates['updated_at'] = datetime.now(SA_TZ).isoformat()

            result = self.db.db.table('workout_templates').update(updates).eq(
                'id', template_id
            ).execute()

            if result and hasattr(result, 'data'):
                log_info(f"Updated workout template: {template_id}")
                return True
            return False

        except Exception as e:
            log_error(f"Error updating template {template_id}: {str(e)}")
            return False

    def delete_workout_template(self, template_id: str) -> bool:
        """
        Delete a workout template.

        Args:
            template_id: Template UUID

        Returns:
            True if successful
        """
        try:
            result = self.db.db.table('workout_templates').delete().eq(
                'id', template_id
            ).execute()

            log_info(f"Deleted workout template: {template_id}")
            return True

        except Exception as e:
            log_error(f"Error deleting template {template_id}: {str(e)}")
            return False

    # =========================================================================
    # WORKOUT HISTORY
    # =========================================================================

    def record_workout_sent(self, trainer_id: str, client_phone: str,
                            workout_data: Dict, template_id: str = None) -> Optional[Dict]:
        """
        Record a workout being sent to a client.

        Args:
            trainer_id: Trainer's ID
            client_phone: Client's phone number
            workout_data: The workout content that was sent
            template_id: Optional template ID if using a template

        Returns:
            Created history record or None
        """
        try:
            history_data = {
                'id': str(uuid.uuid4()),
                'trainer_id': trainer_id,
                'client_phone': client_phone,
                'template_id': template_id,
                'workout_data': workout_data,
                'sent_at': datetime.now(SA_TZ).isoformat(),
                'status': 'sent',
                'created_at': datetime.now(SA_TZ).isoformat()
            }

            result = self.db.db.table('workout_history').insert(history_data).execute()

            if result and hasattr(result, 'data') and result.data:
                log_info(f"Recorded workout sent to {client_phone}")
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error recording workout history: {str(e)}")
            return None

    def get_client_workout_history(self, trainer_id: str, client_phone: str,
                                    limit: int = 10) -> List[Dict]:
        """
        Get workout history for a specific client.

        Args:
            trainer_id: Trainer's ID
            client_phone: Client's phone number
            limit: Maximum records to return

        Returns:
            List of workout history records
        """
        try:
            result = self.db.db.table('workout_history').select(
                'id, template_id, workout_data, sent_at, status, feedback'
            ).eq('trainer_id', trainer_id).eq(
                'client_phone', client_phone
            ).order('sent_at', desc=True).limit(limit).execute()

            if result and hasattr(result, 'data'):
                return result.data
            return []

        except Exception as e:
            log_error(f"Error fetching workout history: {str(e)}")
            return []

    def get_trainer_workout_history(self, trainer_id: str, limit: int = 20) -> List[Dict]:
        """
        Get all workout history for a trainer.

        Args:
            trainer_id: Trainer's ID
            limit: Maximum records to return

        Returns:
            List of workout history records
        """
        try:
            result = self.db.db.table('workout_history').select(
                'id, client_phone, template_id, workout_data, sent_at, status'
            ).eq('trainer_id', trainer_id).order(
                'sent_at', desc=True
            ).limit(limit).execute()

            if result and hasattr(result, 'data'):
                return result.data
            return []

        except Exception as e:
            log_error(f"Error fetching trainer workout history: {str(e)}")
            return []

    def update_workout_history(self, history_id: str, updates: Dict) -> bool:
        """
        Update a workout history record (e.g., mark as completed).

        Args:
            history_id: History record UUID
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        try:
            updates['updated_at'] = datetime.now(SA_TZ).isoformat()

            result = self.db.db.table('workout_history').update(updates).eq(
                'id', history_id
            ).execute()

            if result and hasattr(result, 'data'):
                return True
            return False

        except Exception as e:
            log_error(f"Error updating workout history: {str(e)}")
            return False

    # =========================================================================
    # CLIENT INFORMATION
    # =========================================================================

    def get_client_gender(self, trainer_id: str, client_phone: str) -> Optional[str]:
        """
        Get client's gender for selecting appropriate exercise GIFs.

        Args:
            trainer_id: Trainer's ID
            client_phone: Client's phone number

        Returns:
            'male', 'female', or None if not specified
        """
        try:
            result = self.db.db.table('clients').select('gender').eq(
                'trainer_id', trainer_id
            ).eq('phone', client_phone).execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0].get('gender')
            return None

        except Exception as e:
            log_error(f"Error fetching client gender: {str(e)}")
            return None

    def get_client_info(self, trainer_id: str, client_phone: str) -> Optional[Dict]:
        """
        Get client information.

        Args:
            trainer_id: Trainer's ID
            client_phone: Client's phone number

        Returns:
            Client dictionary or None
        """
        try:
            result = self.db.db.table('clients').select(
                'id, name, phone, gender, fitness_level'
            ).eq('trainer_id', trainer_id).eq('phone', client_phone).execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error fetching client info: {str(e)}")
            return None

    # =========================================================================
    # FORMATTING HELPERS
    # =========================================================================

    def format_workout_message(self, workout_data: Dict, client_gender: str = None) -> str:
        """
        Format a workout into a nicely formatted WhatsApp message.

        Args:
            workout_data: Workout data with exercises
            client_gender: Client's gender for GIF selection ('male' or 'female')

        Returns:
            Formatted message string
        """
        lines = []

        # Header
        name = workout_data.get('name', 'Your Workout')
        lines.append(f"💪 *{name}*")
        lines.append("")

        # Description if present
        description = workout_data.get('description')
        if description:
            lines.append(f"_{description}_")
            lines.append("")

        # Workout details
        duration = workout_data.get('duration_minutes')
        difficulty = workout_data.get('difficulty')

        details = []
        if duration:
            details.append(f"⏱️ {duration} min")
        if difficulty:
            details.append(f"📊 {difficulty.title()}")

        if details:
            lines.append(" | ".join(details))
            lines.append("")

        # Exercises
        exercises = workout_data.get('exercises', [])
        if exercises:
            lines.append("📋 *Exercises:*")
            lines.append("")

            for idx, ex in enumerate(exercises, 1):
                # Exercise name with emoji
                ex_name = ex.get('name', 'Exercise')
                lines.append(f"{idx}. *{ex_name}*")

                # Sets and reps
                sets = ex.get('sets')
                reps = ex.get('reps')
                duration_sec = ex.get('duration_seconds')
                rest = ex.get('rest_seconds')

                details_line = "   "
                if sets and reps:
                    details_line += f"🔄 {sets} sets × {reps} reps"
                elif sets and duration_sec:
                    details_line += f"🔄 {sets} sets × {duration_sec}s"
                elif reps:
                    details_line += f"🔄 {reps} reps"
                elif duration_sec:
                    details_line += f"⏱️ {duration_sec} seconds"

                if rest:
                    details_line += f" | 😮‍💨 {rest}s rest"

                if details_line.strip():
                    lines.append(details_line)

                # Instructions if available
                instructions = ex.get('instructions')
                if instructions:
                    lines.append(f"   📝 {instructions[:100]}")

                # GIF URL based on gender
                gif_url = None
                if client_gender == 'female' and ex.get('gif_url_female'):
                    gif_url = ex.get('gif_url_female')
                elif ex.get('gif_url_male'):
                    gif_url = ex.get('gif_url_male')
                elif ex.get('gif_url_female'):
                    gif_url = ex.get('gif_url_female')

                if gif_url:
                    lines.append(f"   🎬 {gif_url}")

                lines.append("")

        # Footer
        lines.append("─" * 20)
        lines.append("💪 You've got this! 🔥")
        lines.append("")
        lines.append("_Reply 'done' when you finish!_")

        return "\n".join(lines)

    def format_exercise_list(self, exercises: List[Dict]) -> str:
        """
        Format a list of exercises for display.

        Args:
            exercises: List of exercise dictionaries

        Returns:
            Formatted string
        """
        if not exercises:
            return "No exercises found."

        lines = ["📚 *Exercise Library:*", ""]

        for idx, ex in enumerate(exercises, 1):
            name = ex.get('name', 'Unknown')
            category = ex.get('category', '')
            muscle = ex.get('muscle_group', '')
            difficulty = ex.get('difficulty', '')

            line = f"{idx}. *{name}*"
            if category:
                line += f" ({category})"

            lines.append(line)

            details = []
            if muscle:
                details.append(f"💪 {muscle}")
            if difficulty:
                details.append(f"📊 {difficulty}")

            if details:
                lines.append(f"   {' | '.join(details)}")

            lines.append("")

        return "\n".join(lines)

    def format_template_list(self, templates: List[Dict]) -> str:
        """
        Format a list of workout templates for display.

        Args:
            templates: List of template dictionaries

        Returns:
            Formatted string
        """
        if not templates:
            return "📋 No workout templates yet.\n\nCreate one with 'create workout'!"

        lines = ["📋 *Your Workout Templates:*", ""]

        for idx, tmpl in enumerate(templates, 1):
            name = tmpl.get('name', 'Unnamed')
            category = tmpl.get('category', '')
            difficulty = tmpl.get('difficulty', '')
            duration = tmpl.get('duration_minutes')
            exercises = tmpl.get('exercises', [])

            lines.append(f"{idx}. *{name}*")

            details = []
            if category:
                details.append(f"🏷️ {category}")
            if difficulty:
                details.append(f"📊 {difficulty}")
            if duration:
                details.append(f"⏱️ {duration} min")
            details.append(f"💪 {len(exercises)} exercises")

            lines.append(f"   {' | '.join(details)}")
            lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # AI-POWERED WORKOUT GENERATION
    # =========================================================================

    def _get_claude_client(self) -> Optional[Anthropic]:
        """
        Get or create Claude API client.

        Returns:
            Anthropic client instance or None
        """
        if not hasattr(self, '_claude_client'):
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                log_error("ANTHROPIC_API_KEY environment variable is required")
                return None
            self._claude_client = Anthropic(api_key=api_key)
        return self._claude_client

    def _call_claude_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        Call Claude API with retry logic.

        Args:
            prompt: The prompt to send
            max_retries: Maximum number of retries

        Returns:
            Response text or None
        """
        client = self._get_claude_client()
        if not client:
            return None

        for attempt in range(max_retries):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    temperature=0.7,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )

                if response.content and len(response.content) > 0:
                    return response.content[0].text

            except Exception as e:
                log_error(f"Claude API error (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait_time)

        return None

    def _find_client_by_name(self, trainer_id: str, name: str) -> Optional[Dict]:
        """
        Find a client by name (case-insensitive partial match).

        Args:
            trainer_id: Trainer's ID
            name: Client name to search for

        Returns:
            Client dictionary or None
        """
        try:
            result = self.db.db.table('clients').select(
                'id, name, phone, gender, fitness_level, health_conditions, goals, notes'
            ).eq('trainer_id', trainer_id).ilike('name', f'%{name}%').execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error finding client by name: {str(e)}")
            return None

    def _get_exercises_by_criteria(
        self,
        muscle_groups: List[str] = None,
        categories: List[str] = None,
        difficulty: str = None,
        equipment: List[str] = None,
        exclude_exercises: List[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get exercises matching specific criteria.

        Args:
            muscle_groups: List of muscle groups to target
            categories: List of categories (strength, cardio, etc.)
            difficulty: Difficulty level filter
            equipment: List of available equipment
            exclude_exercises: Exercise names to exclude (for health conditions)
            limit: Maximum exercises to return

        Returns:
            List of matching exercises
        """
        try:
            result = self.db.db.table('exercises').select(
                'id, name, description, category, muscle_group, equipment, '
                'difficulty, gif_url_male, gif_url_female, instructions'
            ).limit(limit).execute()

            if not result or not hasattr(result, 'data'):
                return []

            exercises = result.data
            filtered = []

            for ex in exercises:
                # Filter by muscle group
                if muscle_groups:
                    ex_muscle = (ex.get('muscle_group') or '').lower()
                    if not any(mg.lower() in ex_muscle for mg in muscle_groups):
                        continue

                # Filter by category
                if categories:
                    ex_cat = (ex.get('category') or '').lower()
                    if not any(cat.lower() in ex_cat for cat in categories):
                        continue

                # Filter by difficulty
                if difficulty:
                    ex_diff = (ex.get('difficulty') or '').lower()
                    if difficulty.lower() not in ex_diff:
                        continue

                # Exclude certain exercises (for health conditions)
                if exclude_exercises:
                    ex_name = (ex.get('name') or '').lower()
                    if any(excl.lower() in ex_name for excl in exclude_exercises):
                        continue

                filtered.append(ex)

            return filtered

        except Exception as e:
            log_error(f"Error getting exercises by criteria: {str(e)}")
            return []

    def _parse_workout_type(self, prompt: str) -> Dict[str, Any]:
        """
        Parse the workout type from natural language.

        Args:
            prompt: Natural language prompt

        Returns:
            Dictionary with workout parameters
        """
        prompt_lower = prompt.lower()
        result = {
            'muscle_groups': [],
            'categories': [],
            'workout_name': 'Custom Workout'
        }

        # Common workout types
        workout_mappings = {
            'leg': {'muscle_groups': ['legs', 'quadriceps', 'hamstrings', 'glutes', 'calves'], 'name': 'Leg Day'},
            'chest': {'muscle_groups': ['chest', 'pectorals'], 'name': 'Chest Workout'},
            'back': {'muscle_groups': ['back', 'lats', 'traps'], 'name': 'Back Workout'},
            'arm': {'muscle_groups': ['biceps', 'triceps', 'arms', 'forearms'], 'name': 'Arms Workout'},
            'shoulder': {'muscle_groups': ['shoulders', 'deltoids'], 'name': 'Shoulder Workout'},
            'core': {'muscle_groups': ['core', 'abs', 'abdominals', 'obliques'], 'name': 'Core Workout'},
            'full body': {'muscle_groups': [], 'categories': ['strength'], 'name': 'Full Body Workout'},
            'upper body': {'muscle_groups': ['chest', 'back', 'shoulders', 'arms', 'biceps', 'triceps'], 'name': 'Upper Body'},
            'lower body': {'muscle_groups': ['legs', 'glutes', 'quadriceps', 'hamstrings', 'calves'], 'name': 'Lower Body'},
            'hiit': {'categories': ['hiit', 'cardio'], 'name': 'HIIT Workout'},
            'cardio': {'categories': ['cardio'], 'name': 'Cardio Session'},
            'strength': {'categories': ['strength'], 'name': 'Strength Training'},
            'stretch': {'categories': ['flexibility', 'stretching'], 'name': 'Stretching Session'},
            'warm up': {'categories': ['warmup', 'flexibility'], 'name': 'Warm Up'},
            'cool down': {'categories': ['cooldown', 'flexibility'], 'name': 'Cool Down'},
        }

        for keyword, mapping in workout_mappings.items():
            if keyword in prompt_lower:
                result['muscle_groups'].extend(mapping.get('muscle_groups', []))
                result['categories'].extend(mapping.get('categories', []))
                result['workout_name'] = mapping['name']
                break

        return result

    def _get_exercises_to_avoid(self, health_conditions: str) -> List[str]:
        """
        Get list of exercise types to avoid based on health conditions.

        Args:
            health_conditions: Client's health conditions string

        Returns:
            List of exercise keywords to avoid
        """
        if not health_conditions:
            return []

        conditions_lower = health_conditions.lower()
        avoid = []

        # Condition-based exercise restrictions
        condition_restrictions = {
            'knee': ['squat', 'lunge', 'jump', 'running', 'leg press'],
            'back': ['deadlift', 'bent over', 'good morning', 'heavy lift'],
            'shoulder': ['overhead press', 'military press', 'lateral raise', 'shoulder press'],
            'wrist': ['push up', 'plank', 'burpee'],
            'ankle': ['jump', 'running', 'box jump', 'skipping'],
            'neck': ['shoulder shrug', 'neck'],
            'hip': ['squat', 'lunge', 'deadlift', 'hip thrust'],
            'pregnant': ['crunch', 'sit up', 'plank', 'heavy', 'jump', 'lying on back'],
            'heart': ['hiit', 'high intensity', 'heavy', 'sprint'],
            'asthma': ['hiit', 'high intensity', 'sprint'],
        }

        for condition, restrictions in condition_restrictions.items():
            if condition in conditions_lower:
                avoid.extend(restrictions)

        return list(set(avoid))

    def generate_workout_from_prompt(
        self,
        trainer_id: str,
        prompt: str,
        client_phone: str = None
    ) -> Union[str, List[str]]:
        """
        Generate a workout from natural language prompt using AI.

        Accepts prompts like:
        - "Create a leg day workout for Sarah"
        - "Give me a HIIT workout for John"
        - "Upper body strength for Maria"

        Args:
            trainer_id: Trainer's ID
            prompt: Natural language workout request
            client_phone: Optional client phone (if known)

        Returns:
            Formatted workout message(s) ready for WhatsApp.
            Returns a list if message needs to be split for length.
        """
        log_info(f"Generating workout from prompt: {prompt}")

        # Extract client name from prompt
        client_info = None
        client_name = self._extract_client_name(prompt)

        if client_name:
            client_info = self._find_client_by_name(trainer_id, client_name)
            if client_info:
                log_info(f"Found client: {client_info.get('name')}")
        elif client_phone:
            client_info = self.get_client_info(trainer_id, client_phone)

        # Get client details
        client_gender = client_info.get('gender', 'male') if client_info else 'male'
        fitness_level = client_info.get('fitness_level', 'intermediate') if client_info else 'intermediate'
        health_conditions = client_info.get('health_conditions', '') if client_info else ''
        client_goals = client_info.get('goals', '') if client_info else ''
        client_display_name = client_info.get('name', 'Client') if client_info else 'Client'

        # Get exercises to avoid based on health conditions
        exercises_to_avoid = self._get_exercises_to_avoid(health_conditions)

        # Parse workout type from prompt
        workout_params = self._parse_workout_type(prompt)

        # Fetch available exercises from database
        available_exercises = self._get_exercises_by_criteria(
            muscle_groups=workout_params.get('muscle_groups'),
            categories=workout_params.get('categories'),
            difficulty=fitness_level,
            exclude_exercises=exercises_to_avoid,
            limit=100
        )

        if not available_exercises:
            # Fallback: get all exercises
            available_exercises = self.get_exercises(limit=50)

        if not available_exercises:
            return "❌ No exercises available in the library. Please add exercises first."

        # Build AI prompt for workout generation
        ai_prompt = self._build_workout_generation_prompt(
            user_prompt=prompt,
            client_name=client_display_name,
            fitness_level=fitness_level,
            health_conditions=health_conditions,
            client_goals=client_goals,
            available_exercises=available_exercises,
            workout_name=workout_params.get('workout_name', 'Custom Workout')
        )

        # Call Claude to generate workout
        ai_response = self._call_claude_with_retry(ai_prompt)

        if not ai_response:
            # Fallback: generate a simple workout without AI
            return self._generate_fallback_workout(
                available_exercises,
                workout_params,
                client_display_name,
                client_gender
            )

        # Parse AI response and create workout
        workout_data = self._parse_ai_workout_response(
            ai_response,
            available_exercises,
            workout_params.get('workout_name', 'Custom Workout'),
            client_display_name
        )

        # Format the workout message
        formatted_message = self.format_workout_message(workout_data, client_gender)

        # Split if exceeds WhatsApp limit
        return self._split_workout_message(formatted_message)

    def _extract_client_name(self, prompt: str) -> Optional[str]:
        """
        Extract client name from natural language prompt.

        Args:
            prompt: The user's prompt

        Returns:
            Extracted client name or None
        """
        # Common patterns for client names
        patterns = [
            r'for\s+([A-Z][a-z]+)',  # "for Sarah"
            r'to\s+([A-Z][a-z]+)',   # "to John"
            r"([A-Z][a-z]+)'s\s+workout",  # "Sarah's workout"
            r'workout\s+for\s+([A-Z][a-z]+)',  # "workout for Maria"
            r'send\s+(?:to\s+)?([A-Z][a-z]+)',  # "send to Alex"
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt)
            if match:
                return match.group(1)

        return None

    def _build_workout_generation_prompt(
        self,
        user_prompt: str,
        client_name: str,
        fitness_level: str,
        health_conditions: str,
        client_goals: str,
        available_exercises: List[Dict],
        workout_name: str
    ) -> str:
        """
        Build the prompt for Claude to generate workout.

        Args:
            user_prompt: Original user request
            client_name: Client's name
            fitness_level: Client's experience level
            health_conditions: Any health concerns
            client_goals: Client's fitness goals
            available_exercises: List of available exercises
            workout_name: Type of workout

        Returns:
            Formatted prompt for Claude
        """
        # Create exercise list summary
        exercise_list = "\n".join([
            f"- {ex['name']} (muscle: {ex.get('muscle_group', 'N/A')}, "
            f"difficulty: {ex.get('difficulty', 'N/A')})"
            for ex in available_exercises[:30]  # Limit to avoid token overflow
        ])

        health_note = ""
        if health_conditions:
            health_note = f"\n⚠️ IMPORTANT: Client has the following health conditions: {health_conditions}\nAvoid exercises that could aggravate these conditions."

        goals_note = ""
        if client_goals:
            goals_note = f"\nClient's goals: {client_goals}"

        return f"""You are a professional fitness trainer creating a personalized workout.

User request: "{user_prompt}"

Client Information:
- Name: {client_name}
- Fitness Level: {fitness_level}
- Workout Type: {workout_name}{health_note}{goals_note}

Available exercises from our library:
{exercise_list}

Create a workout with 4-6 exercises from the list above. For each exercise, specify:
1. Exercise name (MUST match exactly from the list)
2. Sets (2-4)
3. Reps (8-15) or duration in seconds for timed exercises
4. Rest period (30-90 seconds)

IMPORTANT: Only use exercises from the provided list. Match names exactly.

Respond in this exact JSON format only, no other text:
{{
    "workout_name": "Name for this workout",
    "description": "Brief 1-sentence description",
    "duration_minutes": 30,
    "difficulty": "{fitness_level}",
    "exercises": [
        {{
            "name": "Exercise Name (exact match from list)",
            "sets": 3,
            "reps": 12,
            "rest_seconds": 60
        }}
    ]
}}"""

    def _parse_ai_workout_response(
        self,
        ai_response: str,
        available_exercises: List[Dict],
        default_name: str,
        client_name: str
    ) -> Dict:
        """
        Parse Claude's workout response into structured data.

        Args:
            ai_response: Raw AI response
            available_exercises: Available exercises for matching
            default_name: Default workout name
            client_name: Client's name

        Returns:
            Structured workout dictionary
        """
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', ai_response)
            if not json_match:
                raise ValueError("No JSON found in response")

            workout_json = json.loads(json_match.group())

            # Create exercise lookup by name (case-insensitive)
            exercise_lookup = {
                ex['name'].lower(): ex for ex in available_exercises
            }

            # Enrich exercises with database info
            enriched_exercises = []
            for ex in workout_json.get('exercises', []):
                ex_name = ex.get('name', '').lower()

                # Find matching exercise in database
                db_exercise = exercise_lookup.get(ex_name)
                if not db_exercise:
                    # Try partial match
                    for db_name, db_ex in exercise_lookup.items():
                        if ex_name in db_name or db_name in ex_name:
                            db_exercise = db_ex
                            break

                if db_exercise:
                    enriched_ex = {
                        'name': db_exercise['name'],
                        'sets': ex.get('sets', 3),
                        'reps': ex.get('reps'),
                        'duration_seconds': ex.get('duration_seconds'),
                        'rest_seconds': ex.get('rest_seconds', 60),
                        'instructions': db_exercise.get('instructions', ''),
                        'gif_url_male': db_exercise.get('gif_url_male'),
                        'gif_url_female': db_exercise.get('gif_url_female')
                    }
                    enriched_exercises.append(enriched_ex)

            return {
                'name': f"{workout_json.get('workout_name', default_name)} - {client_name}",
                'description': workout_json.get('description', ''),
                'duration_minutes': workout_json.get('duration_minutes', 30),
                'difficulty': workout_json.get('difficulty', 'intermediate'),
                'exercises': enriched_exercises
            }

        except Exception as e:
            log_error(f"Error parsing AI workout response: {str(e)}")
            # Return fallback structure
            return self._generate_fallback_workout_data(
                available_exercises, default_name, client_name
            )

    def _generate_fallback_workout_data(
        self,
        available_exercises: List[Dict],
        workout_name: str,
        client_name: str
    ) -> Dict:
        """
        Generate fallback workout data when AI fails.

        Args:
            available_exercises: List of available exercises
            workout_name: Name for the workout
            client_name: Client's name

        Returns:
            Workout data dictionary
        """
        # Select 4-5 random exercises
        selected = random.sample(
            available_exercises,
            min(5, len(available_exercises))
        )

        exercises = []
        for ex in selected:
            exercises.append({
                'name': ex['name'],
                'sets': 3,
                'reps': 12,
                'rest_seconds': 60,
                'instructions': ex.get('instructions', ''),
                'gif_url_male': ex.get('gif_url_male'),
                'gif_url_female': ex.get('gif_url_female')
            })

        return {
            'name': f"{workout_name} - {client_name}",
            'description': 'A customized workout just for you!',
            'duration_minutes': 30,
            'difficulty': 'intermediate',
            'exercises': exercises
        }

    def _generate_fallback_workout(
        self,
        available_exercises: List[Dict],
        workout_params: Dict,
        client_name: str,
        client_gender: str
    ) -> Union[str, List[str]]:
        """
        Generate a simple workout without AI as fallback.

        Args:
            available_exercises: List of available exercises
            workout_params: Parsed workout parameters
            client_name: Client's name
            client_gender: Client's gender for GIF URLs

        Returns:
            Formatted workout message(s)
        """
        workout_data = self._generate_fallback_workout_data(
            available_exercises,
            workout_params.get('workout_name', 'Custom Workout'),
            client_name
        )

        formatted_message = self.format_workout_message(workout_data, client_gender)
        return self._split_workout_message(formatted_message)

    def _split_workout_message(
        self,
        message: str,
        max_length: int = MAX_WORKOUT_MESSAGE_LENGTH
    ) -> Union[str, List[str]]:
        """
        Split workout message if it exceeds WhatsApp character limit.

        Args:
            message: The full workout message
            max_length: Maximum characters per message

        Returns:
            Single message string or list of message parts
        """
        if len(message) <= max_length:
            return message

        # Split by exercises
        lines = message.split('\n')
        messages = []
        current_message = []
        current_length = 0

        # Keep header in first message
        header_lines = []
        exercise_started = False

        for line in lines:
            if '📋 *Exercises:*' in line:
                exercise_started = True

            if not exercise_started:
                header_lines.append(line)
            else:
                # Check if adding this line would exceed limit
                line_length = len(line) + 1  # +1 for newline

                if current_length + line_length > max_length - 50:  # Leave buffer
                    if current_message:
                        messages.append('\n'.join(current_message))
                    current_message = [line]
                    current_length = line_length
                else:
                    current_message.append(line)
                    current_length += line_length

        # Add remaining lines
        if current_message:
            messages.append('\n'.join(current_message))

        if not messages:
            return message

        # Add header to first message
        header = '\n'.join(header_lines)
        if messages:
            messages[0] = header + '\n' + messages[0]

        # Add part numbers if multiple messages
        if len(messages) > 1:
            for i, msg in enumerate(messages):
                messages[i] = f"📋 *Part {i + 1}/{len(messages)}*\n\n" + msg

        return messages if len(messages) > 1 else messages[0]


# Singleton instance
_workout_service_instance = None


def get_workout_service(db=None) -> Optional[WorkoutService]:
    """
    Get or create the workout service singleton.

    Args:
        db: Database service instance (required on first call)

    Returns:
        WorkoutService instance or None
    """
    global _workout_service_instance

    if _workout_service_instance is None:
        if db is None:
            log_error("WorkoutService requires db on first call")
            return None
        _workout_service_instance = WorkoutService(db)

    return _workout_service_instance
