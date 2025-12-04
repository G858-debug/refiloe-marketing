"""
Workout Service for Refiloe WhatsApp Assistant
Handles workout template management, exercise library, and workout history tracking
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import pytz
import uuid

from utils.logger import log_info, log_error, log_warning

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
