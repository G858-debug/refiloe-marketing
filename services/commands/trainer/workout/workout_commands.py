"""
Workout Command Handlers for Refiloe WhatsApp Assistant
Handles workout operations including sending workouts, creating templates, and viewing library
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import pytz
import uuid

from utils.logger import log_info, log_error, log_warning
from services.workout import get_workout_service, WorkoutService

SA_TZ = pytz.timezone('Africa/Johannesburg')

# Workout categories for template creation
WORKOUT_CATEGORIES = [
    {'id': 'strength', 'name': 'Strength Training', 'emoji': '🏋️'},
    {'id': 'cardio', 'name': 'Cardio', 'emoji': '🏃'},
    {'id': 'hiit', 'name': 'HIIT', 'emoji': '⚡'},
    {'id': 'flexibility', 'name': 'Flexibility', 'emoji': '🧘'},
    {'id': 'full_body', 'name': 'Full Body', 'emoji': '💪'},
    {'id': 'upper_body', 'name': 'Upper Body', 'emoji': '💪'},
    {'id': 'lower_body', 'name': 'Lower Body', 'emoji': '🦵'},
    {'id': 'core', 'name': 'Core', 'emoji': '🎯'},
]

DIFFICULTY_LEVELS = [
    {'id': 'beginner', 'name': 'Beginner', 'emoji': '🌱'},
    {'id': 'intermediate', 'name': 'Intermediate', 'emoji': '🌿'},
    {'id': 'advanced', 'name': 'Advanced', 'emoji': '🌳'},
]


def handle_send_workout(phone: str, trainer_id: str, db, whatsapp, task_service) -> Dict:
    """
    Start the send workout flow.

    This initiates a multi-step process:
    1. Select client
    2. Choose template OR create custom
    3. Preview and confirm
    4. Send to client via WhatsApp

    Args:
        phone: Trainer's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status and message
    """
    try:
        log_info(f"Starting send_workout flow for trainer {trainer_id}")

        # Check if already has an active task
        if task_service.has_active_task(phone, 'send_workout'):
            message = ("📋 You already have a workout in progress!\n\n"
                      "Please complete it or type 'cancel' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Workout flow already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get trainer's clients
        clients = _get_trainer_clients(trainer_id, db)

        if not clients:
            message = ("📋 No clients found!\n\n"
                      "Add clients first before sending workouts.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'No clients available',
                'whatsapp_sent': result.get('success', False)
            }

        # Start the task
        task_service.start_task(phone, 'send_workout', {
            'trainer_id': trainer_id,
            'step': 'select_client',
            'clients': clients
        })

        # Format client selection message
        message_parts = ["💪 *Send Workout*\n\nSelect a client:\n"]

        for idx, client in enumerate(clients[:10], 1):
            name = client.get('name', 'Unknown')
            client_phone = client.get('phone', '')[-4:]
            message_parts.append(f"{idx}. {name} (...{client_phone})")

        message_parts.append("\n\nReply with the number or type 'cancel' to exit.")

        message = '\n'.join(message_parts)

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Send workout flow started for {phone}")
            return {
                'success': True,
                'message': 'Send workout flow initiated',
                'whatsapp_sent': True,
                'task_started': True
            }
        else:
            log_error(f"Failed to send message to {phone}: {result.get('error')}")
            task_service.cancel_task(phone, 'send_workout')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_send_workout for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting send workout flow: {str(e)}',
            'whatsapp_sent': False
        }


def handle_send_workout_step(phone: str, task: Dict, user_input: str,
                              db, whatsapp, task_service) -> Dict:
    """
    Handle each step of the send_workout flow.

    Args:
        phone: Trainer's phone number
        task: Current task data
        user_input: User's message input
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status
    """
    # Check for cancel
    if user_input.lower().strip() in ['cancel', 'exit', 'quit', 'stop']:
        return _cancel_flow(phone, 'send_workout', task_service, whatsapp)

    step = task['data'].get('step', 'select_client')

    if step == 'select_client':
        return _send_workout_select_client(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'choose_source':
        return _send_workout_choose_source(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'select_template':
        return _send_workout_select_template(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'custom_exercises':
        return _send_workout_custom_exercises(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'preview':
        return _send_workout_preview(phone, task, user_input, db, whatsapp, task_service)
    else:
        return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}


def _send_workout_select_client(phone: str, task: Dict, user_input: str,
                                 db, whatsapp, task_service) -> Dict:
    """Handle client selection step."""
    clients = task['data'].get('clients', [])

    # Validate selection
    if not user_input.isdigit():
        whatsapp.send_message(phone, "Please enter a number to select a client.")
        return {'success': False, 'handled': True}

    idx = int(user_input) - 1
    if idx < 0 or idx >= len(clients):
        whatsapp.send_message(phone, "Invalid selection. Please try again.")
        return {'success': False, 'handled': True}

    selected_client = clients[idx]
    trainer_id = task['data'].get('trainer_id')

    # Get client's gender for GIF selection
    workout_service = get_workout_service(db)
    client_gender = workout_service.get_client_gender(trainer_id, selected_client.get('phone'))

    # Save client selection
    task_service.update_task(phone, 'send_workout', {
        'client_id': selected_client.get('id'),
        'client_name': selected_client.get('name'),
        'client_phone': selected_client.get('phone'),
        'client_gender': client_gender,
        'step': 'choose_source'
    })
    task_service.advance_step(phone, 'send_workout')

    # Get templates count for message
    templates = workout_service.get_workout_templates(trainer_id, limit=1)

    message = (f"📋 Sending workout to *{selected_client.get('name')}*\n\n"
              "How would you like to create the workout?\n\n"
              "1️⃣ Use a saved template\n"
              "2️⃣ Create custom workout\n\n"
              "Reply with 1 or 2")

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _send_workout_choose_source(phone: str, task: Dict, user_input: str,
                                 db, whatsapp, task_service) -> Dict:
    """Handle source selection (template vs custom)."""
    choice = user_input.strip()

    if choice in ['1', 'template', 'templates']:
        # Show templates
        trainer_id = task['data'].get('trainer_id')
        workout_service = get_workout_service(db)
        templates = workout_service.get_workout_templates(trainer_id)

        if not templates:
            message = ("📋 No templates saved yet!\n\n"
                      "Let's create a custom workout instead.\n\n"
                      "Select exercises from the library:\n")

            # Get exercises
            exercises = workout_service.get_exercises(limit=10)
            for idx, ex in enumerate(exercises[:10], 1):
                name = ex.get('name', 'Exercise')
                category = ex.get('category', '')
                message += f"\n{idx}. {name} ({category})"

            message += "\n\nEnter exercise numbers separated by commas (e.g., 1,3,5):"

            task_service.update_task(phone, 'send_workout', {
                'step': 'custom_exercises',
                'available_exercises': exercises
            })
            task_service.advance_step(phone, 'send_workout')

            whatsapp.send_message(phone, message)
            return {'success': True, 'handled': True}

        # Show templates
        message = "📋 *Select a workout template:*\n"

        for idx, tmpl in enumerate(templates[:10], 1):
            name = tmpl.get('name', 'Unnamed')
            exercises = tmpl.get('exercises', [])
            duration = tmpl.get('duration_minutes', '?')
            message += f"\n{idx}. *{name}*"
            message += f"\n   💪 {len(exercises)} exercises | ⏱️ {duration} min"

        message += "\n\nReply with the template number:"

        task_service.update_task(phone, 'send_workout', {
            'step': 'select_template',
            'templates': templates
        })
        task_service.advance_step(phone, 'send_workout')

        whatsapp.send_message(phone, message)

    elif choice in ['2', 'custom', 'create']:
        # Show exercise library
        trainer_id = task['data'].get('trainer_id')
        workout_service = get_workout_service(db)
        exercises = workout_service.get_exercises(limit=15)

        if not exercises:
            whatsapp.send_message(phone,
                "No exercises in library. Please add exercises first.")
            return {'success': False, 'handled': True}

        message = "📚 *Select exercises for the workout:*\n"

        for idx, ex in enumerate(exercises[:15], 1):
            name = ex.get('name', 'Exercise')
            category = ex.get('category', '')
            muscle = ex.get('muscle_group', '')
            emoji = _get_category_emoji(category)
            message += f"\n{idx}. {emoji} {name}"
            if muscle:
                message += f" ({muscle})"

        message += "\n\n📝 Enter exercise numbers separated by commas"
        message += "\n(e.g., 1,3,5,7)"

        task_service.update_task(phone, 'send_workout', {
            'step': 'custom_exercises',
            'available_exercises': exercises
        })
        task_service.advance_step(phone, 'send_workout')

        whatsapp.send_message(phone, message)

    else:
        whatsapp.send_message(phone, "Please reply with 1 or 2")
        return {'success': False, 'handled': True}

    return {'success': True, 'handled': True}


def _send_workout_select_template(phone: str, task: Dict, user_input: str,
                                   db, whatsapp, task_service) -> Dict:
    """Handle template selection."""
    templates = task['data'].get('templates', [])

    if not user_input.isdigit():
        whatsapp.send_message(phone, "Please enter a number to select a template.")
        return {'success': False, 'handled': True}

    idx = int(user_input) - 1
    if idx < 0 or idx >= len(templates):
        whatsapp.send_message(phone, "Invalid selection. Please try again.")
        return {'success': False, 'handled': True}

    selected_template = templates[idx]

    # Build workout data from template
    workout_data = {
        'name': selected_template.get('name'),
        'description': selected_template.get('description'),
        'category': selected_template.get('category'),
        'difficulty': selected_template.get('difficulty'),
        'duration_minutes': selected_template.get('duration_minutes'),
        'exercises': selected_template.get('exercises', [])
    }

    # Save and show preview
    task_service.update_task(phone, 'send_workout', {
        'template_id': selected_template.get('id'),
        'workout_data': workout_data,
        'step': 'preview'
    })
    task_service.advance_step(phone, 'send_workout')

    # Format preview
    workout_service = get_workout_service(db)
    client_gender = task['data'].get('client_gender')
    preview = workout_service.format_workout_message(workout_data, client_gender)

    message = ("📋 *Preview:*\n\n" + preview[:1500] +
              "\n\n─────────────────\n"
              "Send this workout?\n\n"
              "1️⃣ Yes, send it!\n"
              "2️⃣ No, cancel")

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _send_workout_custom_exercises(phone: str, task: Dict, user_input: str,
                                    db, whatsapp, task_service) -> Dict:
    """Handle custom exercise selection."""
    available_exercises = task['data'].get('available_exercises', [])

    # Parse exercise selection (comma-separated numbers)
    try:
        selections = [int(x.strip()) - 1 for x in user_input.split(',')]
    except ValueError:
        whatsapp.send_message(phone,
            "Please enter exercise numbers separated by commas (e.g., 1,3,5)")
        return {'success': False, 'handled': True}

    # Validate selections
    selected_exercises = []
    for idx in selections:
        if 0 <= idx < len(available_exercises):
            ex = available_exercises[idx]
            selected_exercises.append({
                'id': ex.get('id'),
                'name': ex.get('name'),
                'category': ex.get('category'),
                'muscle_group': ex.get('muscle_group'),
                'gif_url_male': ex.get('gif_url_male'),
                'gif_url_female': ex.get('gif_url_female'),
                'instructions': ex.get('instructions'),
                'sets': 3,  # Default values
                'reps': 10,
                'rest_seconds': 60
            })

    if not selected_exercises:
        whatsapp.send_message(phone, "No valid exercises selected. Please try again.")
        return {'success': False, 'handled': True}

    # Build workout data
    workout_data = {
        'name': f"Custom Workout - {datetime.now(SA_TZ).strftime('%d %b')}",
        'description': 'Custom workout created for you',
        'category': 'custom',
        'difficulty': 'intermediate',
        'duration_minutes': len(selected_exercises) * 5,  # Estimate
        'exercises': selected_exercises
    }

    # Save and show preview
    task_service.update_task(phone, 'send_workout', {
        'workout_data': workout_data,
        'step': 'preview'
    })
    task_service.advance_step(phone, 'send_workout')

    # Format preview
    workout_service = get_workout_service(db)
    client_gender = task['data'].get('client_gender')
    preview = workout_service.format_workout_message(workout_data, client_gender)

    message = ("📋 *Preview:*\n\n" + preview[:1500] +
              "\n\n─────────────────\n"
              "Send this workout?\n\n"
              "1️⃣ Yes, send it!\n"
              "2️⃣ No, cancel")

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _send_workout_preview(phone: str, task: Dict, user_input: str,
                           db, whatsapp, task_service) -> Dict:
    """Handle workout preview confirmation."""
    choice = user_input.strip().lower()

    if choice in ['1', 'yes', 'send', 'y']:
        # Send the workout
        task_data = task['data']
        trainer_id = task_data.get('trainer_id')
        client_phone = task_data.get('client_phone')
        client_name = task_data.get('client_name')
        client_gender = task_data.get('client_gender')
        workout_data = task_data.get('workout_data')
        template_id = task_data.get('template_id')

        workout_service = get_workout_service(db)

        # Format the workout message for the client
        workout_message = workout_service.format_workout_message(workout_data, client_gender)

        # Send to client
        client_msg = (f"🏋️ *Workout from your trainer!*\n\n" + workout_message)

        result = whatsapp.send_message(client_phone, client_msg)

        if result.get('success'):
            # Record in history
            workout_service.record_workout_sent(
                trainer_id=trainer_id,
                client_phone=client_phone,
                workout_data=workout_data,
                template_id=template_id
            )

            # Complete task
            task_service.complete_task(phone, 'send_workout')

            # Confirm to trainer
            whatsapp.send_message(phone,
                f"✅ Workout sent to {client_name}!\n\n"
                "They'll receive it shortly with exercise GIFs and instructions.")

            log_info(f"Workout sent to {client_phone} by trainer {trainer_id}")

            return {
                'success': True,
                'message': 'Workout sent successfully',
                'handled': True
            }
        else:
            whatsapp.send_message(phone,
                "❌ Failed to send workout. Please try again.")
            return {'success': False, 'handled': True}

    elif choice in ['2', 'no', 'cancel', 'n']:
        return _cancel_flow(phone, 'send_workout', task_service, whatsapp)

    else:
        whatsapp.send_message(phone, "Please reply with 1 (Yes) or 2 (No)")
        return {'success': False, 'handled': True}


def handle_create_workout(phone: str, trainer_id: str, db, whatsapp, task_service) -> Dict:
    """
    Start the create workout template flow.

    This initiates a multi-step process:
    1. Enter workout name
    2. Select category
    3. Select difficulty
    4. Add exercises
    5. Confirm and save

    Args:
        phone: Trainer's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status and message
    """
    try:
        log_info(f"Starting create_workout flow for trainer {trainer_id}")

        # Check if already has an active task
        if task_service.has_active_task(phone, 'create_workout'):
            message = ("📋 You already have a workout creation in progress!\n\n"
                      "Please complete it or type 'cancel' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Create workout flow already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Start the task
        task_service.start_task(phone, 'create_workout', {
            'trainer_id': trainer_id,
            'step': 'enter_name'
        })

        message = ("💪 *Create Workout Template*\n\n"
                  "Let's build a new workout!\n\n"
                  "First, enter a name for this workout:\n"
                  "(e.g., 'Full Body Blast', 'Upper Body Strength')")

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Create workout flow started for {phone}")
            return {
                'success': True,
                'message': 'Create workout flow initiated',
                'whatsapp_sent': True,
                'task_started': True
            }
        else:
            task_service.cancel_task(phone, 'create_workout')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_create_workout for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting create workout flow: {str(e)}',
            'whatsapp_sent': False
        }


def handle_create_workout_step(phone: str, task: Dict, user_input: str,
                                db, whatsapp, task_service) -> Dict:
    """
    Handle each step of the create_workout flow.

    Args:
        phone: Trainer's phone number
        task: Current task data
        user_input: User's message input
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status
    """
    # Check for cancel
    if user_input.lower().strip() in ['cancel', 'exit', 'quit', 'stop']:
        return _cancel_flow(phone, 'create_workout', task_service, whatsapp)

    step = task['data'].get('step', 'enter_name')

    if step == 'enter_name':
        return _create_workout_enter_name(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'select_category':
        return _create_workout_select_category(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'select_difficulty':
        return _create_workout_select_difficulty(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'add_exercises':
        return _create_workout_add_exercises(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'set_details':
        return _create_workout_set_details(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'confirm':
        return _create_workout_confirm(phone, task, user_input, db, whatsapp, task_service)
    else:
        return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}


def _create_workout_enter_name(phone: str, task: Dict, user_input: str,
                                db, whatsapp, task_service) -> Dict:
    """Handle workout name entry."""
    name = user_input.strip()

    if len(name) < 3:
        whatsapp.send_message(phone, "Name too short. Please enter at least 3 characters.")
        return {'success': False, 'handled': True}

    if len(name) > 50:
        name = name[:50]

    # Save name and show category selection
    task_service.update_task(phone, 'create_workout', {
        'name': name,
        'step': 'select_category'
    })
    task_service.advance_step(phone, 'create_workout')

    message = f"✅ Workout name: *{name}*\n\nSelect a category:\n"

    for idx, cat in enumerate(WORKOUT_CATEGORIES, 1):
        message += f"\n{idx}. {cat['emoji']} {cat['name']}"

    message += "\n\nReply with the number:"

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _create_workout_select_category(phone: str, task: Dict, user_input: str,
                                     db, whatsapp, task_service) -> Dict:
    """Handle category selection."""
    if not user_input.isdigit():
        whatsapp.send_message(phone, "Please enter a number to select a category.")
        return {'success': False, 'handled': True}

    idx = int(user_input) - 1
    if idx < 0 or idx >= len(WORKOUT_CATEGORIES):
        whatsapp.send_message(phone, "Invalid selection. Please try again.")
        return {'success': False, 'handled': True}

    selected_category = WORKOUT_CATEGORIES[idx]

    # Save and show difficulty selection
    task_service.update_task(phone, 'create_workout', {
        'category': selected_category['id'],
        'category_name': selected_category['name'],
        'step': 'select_difficulty'
    })
    task_service.advance_step(phone, 'create_workout')

    message = f"✅ Category: *{selected_category['name']}*\n\nSelect difficulty level:\n"

    for idx, diff in enumerate(DIFFICULTY_LEVELS, 1):
        message += f"\n{idx}. {diff['emoji']} {diff['name']}"

    message += "\n\nReply with the number:"

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _create_workout_select_difficulty(phone: str, task: Dict, user_input: str,
                                       db, whatsapp, task_service) -> Dict:
    """Handle difficulty selection."""
    if not user_input.isdigit():
        whatsapp.send_message(phone, "Please enter a number to select difficulty.")
        return {'success': False, 'handled': True}

    idx = int(user_input) - 1
    if idx < 0 or idx >= len(DIFFICULTY_LEVELS):
        whatsapp.send_message(phone, "Invalid selection. Please try again.")
        return {'success': False, 'handled': True}

    selected_difficulty = DIFFICULTY_LEVELS[idx]

    # Get exercises for selection
    workout_service = get_workout_service(db)
    exercises = workout_service.get_exercises(limit=20)

    if not exercises:
        whatsapp.send_message(phone,
            "No exercises available. Please add exercises to the library first.")
        task_service.cancel_task(phone, 'create_workout')
        return {'success': False, 'handled': True}

    # Save and show exercise selection
    task_service.update_task(phone, 'create_workout', {
        'difficulty': selected_difficulty['id'],
        'difficulty_name': selected_difficulty['name'],
        'available_exercises': exercises,
        'selected_exercises': [],
        'step': 'add_exercises'
    })
    task_service.advance_step(phone, 'create_workout')

    message = (f"✅ Difficulty: *{selected_difficulty['name']}*\n\n"
              "📚 *Add exercises to your workout:*\n")

    for idx, ex in enumerate(exercises[:20], 1):
        name = ex.get('name', 'Exercise')
        category = ex.get('category', '')
        emoji = _get_category_emoji(category)
        message += f"\n{idx}. {emoji} {name}"

    message += ("\n\n📝 Enter exercise numbers separated by commas"
               "\n(e.g., 1,3,5,7,9)\n\n"
               "Or type 'done' when finished adding exercises.")

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _create_workout_add_exercises(phone: str, task: Dict, user_input: str,
                                   db, whatsapp, task_service) -> Dict:
    """Handle exercise selection for workout template."""
    available_exercises = task['data'].get('available_exercises', [])
    current_selection = task['data'].get('selected_exercises', [])

    if user_input.lower().strip() == 'done':
        if not current_selection:
            whatsapp.send_message(phone,
                "Please add at least one exercise before finishing.")
            return {'success': False, 'handled': True}

        # Move to set details
        task_service.update_task(phone, 'create_workout', {
            'step': 'set_details',
            'current_exercise_idx': 0
        })
        task_service.advance_step(phone, 'create_workout')

        # Ask for sets/reps for first exercise
        first_ex = current_selection[0]
        message = (f"📝 *Set details for: {first_ex['name']}*\n\n"
                  "Enter sets and reps (e.g., '3x12' or '3 sets 12 reps'):\n"
                  "Or type 'skip' to use defaults (3x10)")

        whatsapp.send_message(phone, message)
        return {'success': True, 'handled': True}

    # Parse exercise selection
    try:
        selections = [int(x.strip()) - 1 for x in user_input.split(',')]
    except ValueError:
        whatsapp.send_message(phone,
            "Please enter exercise numbers separated by commas (e.g., 1,3,5)\n"
            "Or type 'done' to finish adding exercises.")
        return {'success': False, 'handled': True}

    # Add selected exercises
    new_exercises = []
    for idx in selections:
        if 0 <= idx < len(available_exercises):
            ex = available_exercises[idx]
            # Check if not already added
            existing_ids = [e.get('id') for e in current_selection]
            if ex.get('id') not in existing_ids:
                new_exercises.append({
                    'id': ex.get('id'),
                    'name': ex.get('name'),
                    'category': ex.get('category'),
                    'muscle_group': ex.get('muscle_group'),
                    'gif_url_male': ex.get('gif_url_male'),
                    'gif_url_female': ex.get('gif_url_female'),
                    'instructions': ex.get('instructions'),
                    'sets': 3,
                    'reps': 10,
                    'rest_seconds': 60
                })

    if new_exercises:
        current_selection.extend(new_exercises)
        task_service.update_task(phone, 'create_workout', {
            'selected_exercises': current_selection
        })

        # Show current selection
        message = f"✅ Added {len(new_exercises)} exercise(s)!\n\n"
        message += f"*Current workout ({len(current_selection)} exercises):*\n"

        for idx, ex in enumerate(current_selection, 1):
            message += f"\n{idx}. {ex['name']}"

        message += "\n\nAdd more exercises (enter numbers) or type 'done' to continue."

        whatsapp.send_message(phone, message)
    else:
        whatsapp.send_message(phone,
            "No new exercises added. Try different numbers or type 'done'.")

    return {'success': True, 'handled': True}


def _create_workout_set_details(phone: str, task: Dict, user_input: str,
                                 db, whatsapp, task_service) -> Dict:
    """Handle sets/reps entry for each exercise."""
    selected_exercises = task['data'].get('selected_exercises', [])
    current_idx = task['data'].get('current_exercise_idx', 0)

    if current_idx >= len(selected_exercises):
        # All exercises configured, move to confirm
        task_service.update_task(phone, 'create_workout', {'step': 'confirm'})
        return _show_workout_preview(phone, task, db, whatsapp, task_service)

    current_ex = selected_exercises[current_idx]

    # Parse sets/reps input
    if user_input.lower().strip() in ['skip', 'default']:
        sets = 3
        reps = 10
    else:
        # Try to parse formats like "3x12", "3 x 12", "3 sets 12 reps"
        input_clean = user_input.lower().strip()
        sets = 3
        reps = 10

        if 'x' in input_clean:
            parts = input_clean.split('x')
            try:
                sets = int(parts[0].strip())
                reps = int(parts[1].strip())
            except (ValueError, IndexError):
                pass
        else:
            # Try to extract numbers
            import re
            numbers = re.findall(r'\d+', input_clean)
            if len(numbers) >= 2:
                sets = int(numbers[0])
                reps = int(numbers[1])
            elif len(numbers) == 1:
                reps = int(numbers[0])

    # Update current exercise
    current_ex['sets'] = min(sets, 10)  # Cap at 10 sets
    current_ex['reps'] = min(reps, 50)  # Cap at 50 reps
    selected_exercises[current_idx] = current_ex

    # Move to next exercise
    next_idx = current_idx + 1
    task_service.update_task(phone, 'create_workout', {
        'selected_exercises': selected_exercises,
        'current_exercise_idx': next_idx
    })

    if next_idx >= len(selected_exercises):
        # All exercises configured, show preview
        task_service.update_task(phone, 'create_workout', {'step': 'confirm'})
        return _show_workout_preview(phone, task, db, whatsapp, task_service)

    # Ask for next exercise
    next_ex = selected_exercises[next_idx]
    message = (f"✅ {current_ex['name']}: {sets} sets × {reps} reps\n\n"
              f"📝 *Set details for: {next_ex['name']}*\n\n"
              "Enter sets and reps (e.g., '3x12'):\n"
              "Or type 'skip' for defaults")

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _show_workout_preview(phone: str, task: Dict, db, whatsapp, task_service) -> Dict:
    """Show workout preview before saving."""
    task_data = task['data']
    name = task_data.get('name')
    category = task_data.get('category_name')
    difficulty = task_data.get('difficulty_name')
    exercises = task_data.get('selected_exercises', [])

    # Calculate estimated duration (2-3 min per exercise)
    duration = len(exercises) * 3

    message = ("📋 *Workout Preview:*\n\n"
              f"*{name}*\n"
              f"🏷️ {category} | 📊 {difficulty} | ⏱️ ~{duration} min\n\n"
              "*Exercises:*\n")

    for idx, ex in enumerate(exercises, 1):
        message += f"\n{idx}. {ex['name']}"
        message += f"\n   🔄 {ex.get('sets', 3)} sets × {ex.get('reps', 10)} reps"

    message += "\n\n─────────────────"
    message += "\nSave this workout template?\n\n"
    message += "1️⃣ Yes, save it!\n"
    message += "2️⃣ No, cancel"

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _create_workout_confirm(phone: str, task: Dict, user_input: str,
                             db, whatsapp, task_service) -> Dict:
    """Handle workout template save confirmation."""
    choice = user_input.strip().lower()

    if choice in ['1', 'yes', 'save', 'y']:
        task_data = task['data']
        trainer_id = task_data.get('trainer_id')

        workout_service = get_workout_service(db)

        # Create the template
        template = workout_service.create_workout_template(
            trainer_id=trainer_id,
            name=task_data.get('name'),
            description=f"{task_data.get('category_name')} workout - {task_data.get('difficulty_name')}",
            exercises=task_data.get('selected_exercises', []),
            category=task_data.get('category'),
            difficulty=task_data.get('difficulty'),
            duration_minutes=len(task_data.get('selected_exercises', [])) * 3
        )

        if template:
            task_service.complete_task(phone, 'create_workout')

            whatsapp.send_message(phone,
                f"✅ Workout template '*{task_data.get('name')}*' saved!\n\n"
                "Use 'send workout' to send it to clients.")

            log_info(f"Workout template created: {template.get('id')}")

            return {
                'success': True,
                'message': 'Template created successfully',
                'template_id': template.get('id'),
                'handled': True
            }
        else:
            whatsapp.send_message(phone,
                "❌ Failed to save workout. Please try again.")
            return {'success': False, 'handled': True}

    elif choice in ['2', 'no', 'cancel', 'n']:
        return _cancel_flow(phone, 'create_workout', task_service, whatsapp)

    else:
        whatsapp.send_message(phone, "Please reply with 1 (Yes) or 2 (No)")
        return {'success': False, 'handled': True}


def handle_view_workouts(phone: str, trainer_id: str, db, whatsapp) -> Dict:
    """
    Show trainer's workout library (templates and exercises).

    Args:
        phone: Trainer's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance

    Returns:
        Dictionary with success status and workout count
    """
    try:
        log_info(f"Viewing workouts for trainer {trainer_id}")

        workout_service = get_workout_service(db)

        # Get templates
        templates = workout_service.get_workout_templates(trainer_id, limit=10)

        if not templates:
            message = ("📋 *Your Workout Library*\n\n"
                      "No workout templates saved yet!\n\n"
                      "Create your first workout template with 'create workout'\n"
                      "or view the exercise library with 'exercises'")

            result = whatsapp.send_message(phone, message)
            return {
                'success': True,
                'message': 'No templates found',
                'template_count': 0,
                'whatsapp_sent': result.get('success', False)
            }

        # Format templates list
        message = "📋 *Your Workout Templates:*\n"

        for idx, tmpl in enumerate(templates, 1):
            name = tmpl.get('name', 'Unnamed')
            category = tmpl.get('category', 'general')
            difficulty = tmpl.get('difficulty', '')
            duration = tmpl.get('duration_minutes', '?')
            exercises = tmpl.get('exercises', [])

            emoji = _get_category_emoji(category)

            message += f"\n{idx}. {emoji} *{name}*"
            message += f"\n   📊 {difficulty.title() if difficulty else 'Any level'}"
            message += f" | ⏱️ {duration} min"
            message += f" | 💪 {len(exercises)} exercises"

        message += "\n\n─────────────────"
        message += "\n📝 'send workout' - Send to a client"
        message += "\n➕ 'create workout' - Create new template"

        # Get recent workout history
        history = workout_service.get_trainer_workout_history(trainer_id, limit=3)

        if history:
            message += "\n\n📬 *Recently Sent:*"
            for h in history[:3]:
                sent_at = h.get('sent_at', '')
                if sent_at:
                    dt = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
                    formatted_date = dt.astimezone(SA_TZ).strftime('%d %b')
                    workout_name = h.get('workout_data', {}).get('name', 'Workout')
                    client_phone = h.get('client_phone', '')[-4:]
                    message += f"\n• {workout_name} ➜ ...{client_phone} ({formatted_date})"

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Sent workout library to {phone}")
            return {
                'success': True,
                'message': 'Workout library sent',
                'template_count': len(templates),
                'whatsapp_sent': True
            }
        else:
            return {
                'success': False,
                'message': 'Failed to send workout library',
                'template_count': len(templates),
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_view_workouts for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error viewing workouts: {str(e)}',
            'whatsapp_sent': False
        }


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def _cancel_flow(phone: str, task_type: str, task_service, whatsapp) -> Dict:
    """Cancel the current flow."""
    task_service.cancel_task(phone, task_type)
    whatsapp.send_message(phone, "❌ Cancelled. What would you like to do?")
    log_info(f"User cancelled {task_type} flow for {phone}")
    return {'success': True, 'message': 'Flow cancelled', 'handled': True}


def _get_trainer_clients(trainer_id: str, db) -> List[Dict]:
    """Get list of trainer's clients."""
    try:
        result = db.db.table('clients').select(
            'id, name, phone, gender'
        ).eq('trainer_id', trainer_id).execute()

        if result and hasattr(result, 'data'):
            return result.data
        return []
    except Exception as e:
        log_error(f"Error fetching clients: {str(e)}")
        return []


def _get_category_emoji(category: str) -> str:
    """Get emoji for exercise/workout category."""
    emoji_map = {
        'strength': '🏋️',
        'cardio': '🏃',
        'hiit': '⚡',
        'flexibility': '🧘',
        'full_body': '💪',
        'upper_body': '💪',
        'lower_body': '🦵',
        'core': '🎯',
        'stretching': '🧘',
        'warmup': '🔥',
        'cooldown': '❄️',
        'custom': '⭐',
    }
    return emoji_map.get(category.lower() if category else '', '💪')
