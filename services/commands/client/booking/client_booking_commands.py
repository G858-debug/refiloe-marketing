"""
Client Booking Command Handlers for Refiloe WhatsApp Assistant
Handles client-side booking operations with friendly, conversational interactions
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pytz
import uuid
from utils.logger import log_info, log_error, log_warning

SA_TZ = pytz.timezone('Africa/Johannesburg')

# Session type configuration
SESSION_TYPES = {
    'personal_training': {
        'name': 'Personal Training',
        'duration_minutes': 60,
        'price': 350.00
    },
    'group_session': {
        'name': 'Group Session',
        'duration_minutes': 60,
        'price': 200.00
    },
    'assessment': {
        'name': 'Assessment',
        'duration_minutes': 45,
        'price': 250.00
    },
    'follow_up': {
        'name': 'Follow-up Session',
        'duration_minutes': 30,
        'price': 150.00
    }
}

# Default working hours for trainers
DEFAULT_WORKING_HOURS = {
    'Monday': {'start': '06:00', 'end': '20:00'},
    'Tuesday': {'start': '06:00', 'end': '20:00'},
    'Wednesday': {'start': '06:00', 'end': '20:00'},
    'Thursday': {'start': '06:00', 'end': '20:00'},
    'Friday': {'start': '06:00', 'end': '20:00'},
    'Saturday': {'start': '07:00', 'end': '14:00'},
    'Sunday': None  # Closed
}


def format_rand(amount: float) -> str:
    """Format amount as South African Rand."""
    return f"R{amount:,.2f}"


def format_datetime(dt: datetime) -> str:
    """Format datetime for display in Africa/Johannesburg timezone."""
    if dt.tzinfo is None:
        dt = SA_TZ.localize(dt)
    else:
        dt = dt.astimezone(SA_TZ)
    return dt.strftime('%d %b %Y at %I:%M %p SAST')


def format_date(dt: datetime) -> str:
    """Format date for display."""
    if dt.tzinfo is None:
        dt = SA_TZ.localize(dt)
    else:
        dt = dt.astimezone(SA_TZ)
    return dt.strftime('%d %b %Y')


def format_time(dt: datetime) -> str:
    """Format time for display."""
    if dt.tzinfo is None:
        dt = SA_TZ.localize(dt)
    else:
        dt = dt.astimezone(SA_TZ)
    return dt.strftime('%I:%M %p')


def _get_client_trainers(phone: str, db) -> List[Dict]:
    """
    Get list of trainers connected to a client.

    A client can be connected to multiple trainers through the clients table.
    Each record in clients table links a phone to a trainer.

    Args:
        phone: Client's phone number
        db: Database service instance

    Returns:
        List of trainer dictionaries with id and name
    """
    try:
        # Get all client records for this phone (may have multiple trainers)
        result = db.db.table('clients').select(
            'trainer_id'
        ).eq('phone', phone).execute()

        if not result or not hasattr(result, 'data') or not result.data:
            return []

        trainer_ids = list(set([r['trainer_id'] for r in result.data if r.get('trainer_id')]))

        if not trainer_ids:
            return []

        # Get trainer details
        trainers_result = db.db.table('trainers').select(
            'id, name, working_hours'
        ).in_('id', trainer_ids).execute()

        if trainers_result and hasattr(trainers_result, 'data'):
            return trainers_result.data
        return []

    except Exception as e:
        log_error(f"Error fetching client trainers: {str(e)}")
        return []


def _get_trainer_working_hours(trainer_id: str, db) -> Dict:
    """Get trainer's working hours from database."""
    try:
        result = db.db.table('trainers').select(
            'working_hours'
        ).eq('id', trainer_id).execute()

        if result and hasattr(result, 'data') and result.data:
            hours = result.data[0].get('working_hours')
            if hours:
                return hours
        return DEFAULT_WORKING_HOURS
    except Exception as e:
        log_warning(f"Error fetching working hours: {str(e)}")
        return DEFAULT_WORKING_HOURS


def _get_next_available_dates(trainer_id: str, db, num_days: int = 7) -> List[Dict]:
    """Get the next available dates based on trainer's working hours."""
    working_hours = _get_trainer_working_hours(trainer_id, db)
    dates = []
    current = datetime.now(SA_TZ).date() + timedelta(days=1)  # Start from tomorrow

    days_checked = 0
    while len(dates) < num_days and days_checked < 14:
        day_name = current.strftime('%A')
        hours = working_hours.get(day_name)

        if hours:  # Trainer works on this day
            dates.append({
                'date': current.strftime('%Y-%m-%d'),
                'display': current.strftime('%a %d %b'),
                'day_name': day_name
            })

        current += timedelta(days=1)
        days_checked += 1

    return dates


def _get_bookings_for_date(trainer_id: str, date_str: str, db) -> List[Dict]:
    """Get all bookings for a specific date."""
    try:
        start = f"{date_str}T00:00:00"
        end = f"{date_str}T23:59:59"

        result = db.db.table('bookings').select(
            'id, session_datetime, duration_minutes, status'
        ).eq('trainer_id', trainer_id).gte(
            'session_datetime', start
        ).lte(
            'session_datetime', end
        ).in_(
            'status', ['confirmed', 'pending']
        ).execute()

        if result and hasattr(result, 'data'):
            return result.data
        return []
    except Exception as e:
        log_error(f"Error fetching bookings for date: {str(e)}")
        return []


def _get_available_time_slots(trainer_id: str, date_str: str, db,
                               duration: int = 60) -> List[Dict]:
    """Get available time slots for a specific date."""
    working_hours = _get_trainer_working_hours(trainer_id, db)
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    day_name = date_obj.strftime('%A')

    hours = working_hours.get(day_name)
    if not hours:
        return []

    # Parse working hours
    start_time = datetime.strptime(hours['start'], '%H:%M').time()
    end_time = datetime.strptime(hours['end'], '%H:%M').time()

    # Get existing bookings for this date
    existing = _get_bookings_for_date(trainer_id, date_str, db)
    booked_times = set()

    for booking in existing:
        dt = datetime.fromisoformat(booking['session_datetime'].replace('Z', '+00:00'))
        dt_local = dt.astimezone(SA_TZ)
        if dt_local.date() == date_obj:
            # Block out the booking duration
            booking_duration = booking.get('duration_minutes', 60)
            for offset in range(0, booking_duration, 30):
                block_time = (dt_local + timedelta(minutes=offset)).strftime('%H:%M')
                booked_times.add(block_time)

    # Generate slots (every 30 minutes)
    slots = []
    current_dt = datetime.combine(date_obj, start_time)
    end_dt = datetime.combine(date_obj, end_time)
    end_dt -= timedelta(minutes=duration)  # Ensure full duration fits

    while current_dt <= end_dt:
        time_str = current_dt.strftime('%H:%M')

        # Check if slot is available
        is_available = True
        for offset in range(0, duration, 30):
            check_time = (current_dt + timedelta(minutes=offset)).strftime('%H:%M')
            if check_time in booked_times:
                is_available = False
                break

        if is_available:
            slots.append({
                'time': time_str,
                'display': current_dt.strftime('%I:%M %p')
            })

        current_dt += timedelta(minutes=30)

    return slots


def _get_trainer_name(trainer_id: str, db) -> str:
    """Get trainer's name from database."""
    try:
        result = db.db.table('trainers').select('name').eq('id', trainer_id).execute()

        if result and hasattr(result, 'data') and result.data:
            return result.data[0].get('name', 'Your Trainer')
        return 'Your Trainer'
    except Exception as e:
        log_warning(f"Error fetching trainer name: {str(e)}")
        return 'Your Trainer'


def _notify_trainer_booking_request(trainer_id: str, booking_data: Dict,
                                     client_phone: str, db, whatsapp) -> None:
    """Notify trainer of a new booking request that needs approval."""
    try:
        # Get trainer's phone
        result = db.db.table('trainers').select('phone, name').eq('id', trainer_id).execute()

        if not result or not hasattr(result, 'data') or not result.data:
            log_error(f"Could not find trainer {trainer_id} for notification")
            return

        trainer_phone = result.data[0].get('phone')
        if not trainer_phone:
            log_warning(f"Trainer {trainer_id} has no phone number")
            return

        # Get client name
        client_result = db.db.table('clients').select('name').eq('phone', client_phone).limit(1).execute()
        client_name = "A client"
        if client_result and hasattr(client_result, 'data') and client_result.data:
            client_name = client_result.data[0].get('name', f"Client {client_phone[-4:]}")

        message = (
            "New booking request!\n\n"
            f"Client: {client_name}\n"
            f"Phone: {client_phone}\n"
            f"Type: {booking_data.get('session_type_name')}\n"
            f"Date: {booking_data.get('selected_date_display')}\n"
            f"Time: {booking_data.get('selected_time')}\n"
            f"Duration: {booking_data.get('duration_minutes')} min\n"
            f"Price: {format_rand(booking_data.get('price', 0))}\n\n"
            "Reply 'approve' or 'reject' to respond."
        )

        whatsapp.send_message(trainer_phone, message)
        log_info(f"Booking request notification sent to trainer {trainer_id}")

    except Exception as e:
        log_error(f"Error notifying trainer of booking request: {str(e)}")


def _notify_trainer_cancellation(trainer_id: str, booking: Dict,
                                  client_phone: str, db, whatsapp) -> None:
    """Notify trainer that a client has cancelled their session."""
    try:
        # Get trainer's phone
        result = db.db.table('trainers').select('phone').eq('id', trainer_id).execute()

        if not result or not hasattr(result, 'data') or not result.data:
            return

        trainer_phone = result.data[0].get('phone')
        if not trainer_phone:
            return

        # Get client name
        client_result = db.db.table('clients').select('name').eq('phone', client_phone).limit(1).execute()
        client_name = f"Client {client_phone[-4:]}"
        if client_result and hasattr(client_result, 'data') and client_result.data:
            client_name = client_result.data[0].get('name', client_name)

        dt = datetime.fromisoformat(booking['session_datetime'].replace('Z', '+00:00'))
        formatted_dt = dt.astimezone(SA_TZ).strftime('%d %b %Y at %I:%M %p')
        session_type = booking.get('session_type', 'Session').replace('_', ' ').title()

        message = (
            "Session cancelled by client\n\n"
            f"Client: {client_name}\n"
            f"Session: {session_type}\n"
            f"Was scheduled: {formatted_dt}\n\n"
            "This time slot is now available."
        )

        whatsapp.send_message(trainer_phone, message)
        log_info(f"Cancellation notification sent to trainer {trainer_id}")

    except Exception as e:
        log_error(f"Error notifying trainer of cancellation: {str(e)}")


def handle_request_booking(phone: str, client_id: str, db, whatsapp, task_service) -> Dict:
    """
    Start the booking request flow for a client.

    This initiates a multi-step booking process where the client will:
    1. Select from their connected trainers
    2. Choose session type
    3. Select date and time from trainer's available slots
    4. Confirm the booking request

    The booking is created with 'pending' status and trainer is notified for approval.

    Args:
        phone: Client's phone number
        client_id: Client's ID (can be same as phone)
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status and message
    """
    try:
        log_info(f"Starting client booking request flow for {phone}")

        # Check if client already has an active booking task
        if task_service.has_active_task(phone, 'client_book_session'):
            message = ("You already have a booking in progress!\n\n"
                      "Please complete your current booking or type 'cancel' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Booking already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get client's connected trainers
        trainers = _get_client_trainers(phone, db)

        if not trainers:
            message = ("You're not connected to any trainers yet.\n\n"
                      "Please contact a trainer to get started with your fitness journey!")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'No connected trainers',
                'whatsapp_sent': result.get('success', False)
            }

        # Start the booking task
        task_service.start_task(phone, 'client_book_session', {
            'client_phone': phone,
            'client_id': client_id,
            'trainers': trainers,
            'step': 'select_trainer' if len(trainers) > 1 else 'select_type'
        })

        # If only one trainer, skip trainer selection
        if len(trainers) == 1:
            trainer = trainers[0]
            task_service.update_task(phone, 'client_book_session', {
                'trainer_id': trainer['id'],
                'trainer_name': trainer.get('name', 'Your Trainer')
            })

            # Send session type options
            message = (f"Let's book a session with {trainer.get('name', 'your trainer')}!\n\n"
                      "What type of session would you like?\n\n"
                      "1. Personal Training (60 min) - R350\n"
                      "2. Group Session (60 min) - R200\n"
                      "3. Assessment (45 min) - R250\n"
                      "4. Follow-up Session (30 min) - R150\n\n"
                      "Reply with the number of your choice or type 'cancel' to exit.")

            result = whatsapp.send_message(phone, message)
        else:
            # Show trainer selection
            message_parts = ["Let's book a training session!\n\nSelect your trainer:\n"]

            for idx, trainer in enumerate(trainers[:10], 1):
                message_parts.append(f"\n{idx}. {trainer.get('name', 'Trainer')}")

            message_parts.append("\n\nReply with the number of your choice or type 'cancel' to exit.")
            message = ''.join(message_parts)

            result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Client booking flow started successfully for {phone}")
            return {
                'success': True,
                'message': 'Booking flow initiated',
                'whatsapp_sent': True,
                'task_started': True,
                'trainers_count': len(trainers)
            }
        else:
            log_error(f"Failed to send booking message to {phone}: {result.get('error')}")
            task_service.cancel_task(phone, 'client_book_session')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_request_booking for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting booking flow: {str(e)}',
            'whatsapp_sent': False
        }


def handle_my_sessions(phone: str, client_id: str, db, whatsapp) -> Dict:
    """
    Show all upcoming sessions for the client across all their trainers.

    Retrieves and displays upcoming sessions with key details like trainer name,
    date, time, session type, and price. Shows the next 10 upcoming bookings.

    Args:
        phone: Client's phone number
        client_id: Client's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance

    Returns:
        Dictionary with success status and booking count
    """
    try:
        log_info(f"Retrieving sessions for client {phone}")

        # Get current time in SAST
        now = datetime.now(SA_TZ)

        # Get client's trainers first to get trainer names
        trainers = _get_client_trainers(phone, db)
        trainer_names = {t['id']: t.get('name', 'Trainer') for t in trainers}

        # Query upcoming bookings for this client across all trainers
        result = db.db.table('bookings').select(
            'id, trainer_id, session_datetime, duration_minutes, session_type, price, status, notes'
        ).eq(
            'client_id', phone
        ).gte(
            'session_datetime', now.isoformat()
        ).in_(
            'status', ['confirmed', 'pending']
        ).order(
            'session_datetime'
        ).limit(10).execute()

        bookings = result.data if result and hasattr(result, 'data') else []

        if not bookings:
            message = ("You don't have any upcoming sessions.\n\n"
                      "Ready to book your next session?\n"
                      "Type 'book' to get started!")

            result = whatsapp.send_message(phone, message)

            return {
                'success': True,
                'message': 'No sessions found',
                'booking_count': 0,
                'whatsapp_sent': result.get('success', False)
            }

        # Format bookings message
        message_parts = ["Your upcoming sessions:\n"]

        for idx, booking in enumerate(bookings, 1):
            # Parse session datetime
            session_dt = datetime.fromisoformat(booking['session_datetime'].replace('Z', '+00:00'))

            # Get trainer name
            trainer_name = trainer_names.get(booking.get('trainer_id'), 'Trainer')

            # Format booking details
            session_type = booking.get('session_type', 'Training session').replace('_', ' ').title()
            price = format_rand(booking.get('price', 0))
            formatted_datetime = format_datetime(session_dt)
            duration = booking.get('duration_minutes', 60)
            status_emoji = '' if booking.get('status') == 'confirmed' else ' (pending)'

            booking_text = (f"\n{idx}. {session_type}{status_emoji}\n"
                          f"   Trainer: {trainer_name}\n"
                          f"   {formatted_datetime}\n"
                          f"   {duration} min | {price}")

            # Add notes if present
            notes = booking.get('notes', '').strip()
            if notes:
                booking_text += f"\n   Note: {notes}"

            message_parts.append(booking_text)

        # Add footer
        message_parts.append("\n\nNeed to make changes?\n"
                           "Type 'cancel session' to cancel a booking.")

        message = '\n'.join(message_parts)

        # Ensure message doesn't exceed 1600 characters
        if len(message) > 1600:
            message = message[:1550] + "\n\n... (showing first few sessions only)"

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Sent {len(bookings)} sessions to client {phone}")
            return {
                'success': True,
                'message': 'Sessions sent successfully',
                'booking_count': len(bookings),
                'whatsapp_sent': True
            }
        else:
            log_error(f"Failed to send sessions to {phone}: {result.get('error')}")
            return {
                'success': False,
                'message': 'Failed to send sessions',
                'booking_count': len(bookings),
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_my_sessions for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error retrieving sessions: {str(e)}',
            'whatsapp_sent': False
        }


def handle_cancel_my_session(phone: str, client_id: str, db, whatsapp, task_service) -> Dict:
    """
    Start the session cancellation flow for a client.

    Initiates a multi-step process to cancel a booking:
    1. Shows upcoming bookings across all trainers
    2. Asks client to select which one to cancel
    3. Confirms cancellation
    4. Updates booking status and notifies trainer

    Args:
        phone: Client's phone number
        client_id: Client's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status and message
    """
    try:
        log_info(f"Starting client cancellation flow for {phone}")

        # Check if client already has an active cancellation task
        if task_service.has_active_task(phone, 'client_cancel_session'):
            message = ("You already have a cancellation in progress!\n\n"
                      "Please complete your current request or type 'exit' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Cancellation already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get current time in SAST
        now = datetime.now(SA_TZ)

        # Get client's trainers for names
        trainers = _get_client_trainers(phone, db)
        trainer_names = {t['id']: t.get('name', 'Trainer') for t in trainers}

        # Query upcoming bookings that can be cancelled
        result = db.db.table('bookings').select(
            'id, trainer_id, session_datetime, session_type, price, status'
        ).eq(
            'client_id', phone
        ).gte(
            'session_datetime', now.isoformat()
        ).in_(
            'status', ['confirmed', 'pending']
        ).order(
            'session_datetime'
        ).limit(10).execute()

        bookings = result.data if result and hasattr(result, 'data') else []

        if not bookings:
            message = ("You don't have any upcoming sessions to cancel.\n\n"
                      "Type 'my sessions' to see your booking history.")

            result = whatsapp.send_message(phone, message)

            return {
                'success': False,
                'message': 'No bookings to cancel',
                'whatsapp_sent': result.get('success', False)
            }

        # Start the cancellation task
        task_service.start_task(phone, 'client_cancel_session', {
            'client_phone': phone,
            'bookings': bookings,
            'trainer_names': trainer_names,
            'step': 'select_booking'
        })

        # Format bookings selection message
        message_parts = ["Which session would you like to cancel?\n"]

        for idx, booking in enumerate(bookings, 1):
            session_dt = datetime.fromisoformat(booking['session_datetime'].replace('Z', '+00:00'))
            session_type = booking.get('session_type', 'Training session').replace('_', ' ').title()
            formatted_datetime = format_datetime(session_dt)
            trainer_name = trainer_names.get(booking.get('trainer_id'), 'Trainer')

            message_parts.append(f"\n{idx}. {session_type}")
            message_parts.append(f"   Trainer: {trainer_name}")
            message_parts.append(f"   {formatted_datetime}")

        message_parts.append("\n\nReply with the number of the session to cancel, or type 'exit' to go back.")

        message = '\n'.join(message_parts)

        # Ensure message doesn't exceed 1600 characters
        if len(message) > 1600:
            message = message[:1550] + "\n\n... (too many bookings)"

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Client cancellation flow started successfully for {phone}")
            return {
                'success': True,
                'message': 'Cancellation flow initiated',
                'whatsapp_sent': True,
                'task_started': True,
                'available_bookings': len(bookings)
            }
        else:
            log_error(f"Failed to send cancellation message to {phone}: {result.get('error')}")
            task_service.cancel_task(phone, 'client_cancel_session')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_cancel_my_session for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting cancellation flow: {str(e)}',
            'whatsapp_sent': False
        }


# =========================================================================
# TASK STEP HANDLERS - Used by the message router for multi-step flows
# =========================================================================

def handle_client_book_session_step(phone: str, task: Dict, user_input: str,
                                     db, whatsapp, task_service) -> Dict:
    """
    Handle each step of the client booking flow.

    Steps:
    1. select_trainer - Select trainer (if multiple)
    2. select_type - Select session type
    3. select_date - Select booking date
    4. select_time - Select time slot
    5. confirm - Confirm and create booking request
    """
    step = task['data'].get('step', 'select_trainer')

    # Check for cancel/exit commands
    if user_input.lower().strip() in ['cancel', 'exit', 'quit', 'stop']:
        task_service.cancel_task(phone, 'client_book_session')
        whatsapp.send_message(phone, "Booking cancelled. What would you like to do?")
        return {'success': True, 'message': 'Flow cancelled', 'handled': True}

    if step == 'select_trainer':
        return _client_book_select_trainer(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'select_type':
        return _client_book_select_type(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'select_date':
        return _client_book_select_date(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'select_time':
        return _client_book_select_time(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'confirm':
        return _client_book_confirm(phone, task, user_input, db, whatsapp, task_service)
    else:
        return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}


def _client_book_select_trainer(phone: str, task: Dict, user_input: str,
                                 db, whatsapp, task_service) -> Dict:
    """Handle trainer selection step."""
    trainers = task['data'].get('trainers', [])
    selected_trainer = None

    # Check if input is a number
    if user_input.isdigit():
        idx = int(user_input) - 1
        if 0 <= idx < len(trainers):
            selected_trainer = trainers[idx]
        else:
            whatsapp.send_message(phone, "Invalid selection. Please try again.")
            return {'success': False, 'message': 'Invalid trainer selection', 'handled': True}
    else:
        # Try matching by name
        for t in trainers:
            if t.get('name', '').lower() == user_input.lower():
                selected_trainer = t
                break

        if not selected_trainer:
            whatsapp.send_message(phone, "Couldn't find that trainer. Please enter the number.")
            return {'success': False, 'message': 'Trainer not found', 'handled': True}

    # Save trainer and move to session type selection
    task_service.update_task(phone, 'client_book_session', {
        'trainer_id': selected_trainer['id'],
        'trainer_name': selected_trainer.get('name', 'Your Trainer'),
        'step': 'select_type'
    })
    task_service.advance_step(phone, 'client_book_session')

    # Send session type options
    trainer_name = selected_trainer.get('name', 'your trainer')
    message = (f"Booking with {trainer_name}\n\n"
              "What type of session would you like?\n\n"
              "1. Personal Training (60 min) - R350\n"
              "2. Group Session (60 min) - R200\n"
              "3. Assessment (45 min) - R250\n"
              "4. Follow-up Session (30 min) - R150\n\n"
              "Reply with the number of your choice.")

    whatsapp.send_message(phone, message)
    return {'success': True, 'message': 'Trainer selected', 'handled': True}


def _client_book_select_type(phone: str, task: Dict, user_input: str,
                              db, whatsapp, task_service) -> Dict:
    """Handle session type selection step."""
    input_lower = user_input.lower().strip()
    type_map = {
        '1': 'personal_training',
        'personal_training': 'personal_training',
        'personal': 'personal_training',
        '2': 'group_session',
        'group_session': 'group_session',
        'group': 'group_session',
        '3': 'assessment',
        '4': 'follow_up',
        'follow_up': 'follow_up',
        'follow-up': 'follow_up',
        'followup': 'follow_up'
    }

    session_type = type_map.get(input_lower)

    if not session_type:
        whatsapp.send_message(phone, "Please select a valid session type (1-4).")
        return {'success': False, 'message': 'Invalid session type', 'handled': True}

    type_config = SESSION_TYPES[session_type]
    trainer_id = task['data'].get('trainer_id')

    # Save and advance
    task_service.update_task(phone, 'client_book_session', {
        'session_type': session_type,
        'session_type_name': type_config['name'],
        'duration_minutes': type_config['duration_minutes'],
        'price': type_config['price'],
        'step': 'select_date'
    })
    task_service.advance_step(phone, 'client_book_session')

    # Get available dates from trainer
    dates = _get_next_available_dates(trainer_id, db, 7)

    if not dates:
        whatsapp.send_message(
            phone,
            "No available dates found. Please contact your trainer directly."
        )
        task_service.cancel_task(phone, 'client_book_session')
        return {'success': False, 'message': 'No dates available', 'handled': True}

    # Send date options
    message_parts = [f"{type_config['name']} - {type_config['duration_minutes']} min\n\n"
                    "Select a date:\n"]

    for idx, d in enumerate(dates, 1):
        message_parts.append(f"\n{idx}. {d['display']}")

    message_parts.append("\n\nReply with the number of your choice.")

    # Store dates for validation
    task_service.update_task(phone, 'client_book_session', {
        'available_dates': dates
    })

    whatsapp.send_message(phone, ''.join(message_parts))
    return {'success': True, 'message': 'Session type selected', 'handled': True}


def _client_book_select_date(phone: str, task: Dict, user_input: str,
                              db, whatsapp, task_service) -> Dict:
    """Handle date selection step."""
    trainer_id = task['data'].get('trainer_id')
    dates = task['data'].get('available_dates', [])

    # If dates not stored, regenerate
    if not dates:
        dates = _get_next_available_dates(trainer_id, db, 7)

    selected_date = None

    # Check if input is a number
    if user_input.isdigit():
        idx = int(user_input) - 1
        if 0 <= idx < len(dates):
            selected_date = dates[idx]['date']
    else:
        # Try to match date string
        for d in dates:
            if d['date'] == user_input or d['display'].lower() == user_input.lower():
                selected_date = d['date']
                break

    if not selected_date:
        whatsapp.send_message(phone, "Please select a valid date from the options.")
        return {'success': False, 'message': 'Invalid date', 'handled': True}

    # Parse the date
    date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()

    # Save and advance
    task_service.update_task(phone, 'client_book_session', {
        'selected_date': selected_date,
        'selected_date_display': date_obj.strftime('%d %b %Y'),
        'step': 'select_time'
    })
    task_service.advance_step(phone, 'client_book_session')

    # Get available time slots for this date
    duration = task['data'].get('duration_minutes', 60)
    slots = _get_available_time_slots(trainer_id, selected_date, db, duration)

    if not slots:
        whatsapp.send_message(
            phone,
            f"No available slots on {date_obj.strftime('%d %b')}.\n\nPlease choose a different date."
        )
        # Go back to date selection
        task_service.update_task(phone, 'client_book_session', {'step': 'select_date'})
        return {'success': False, 'message': 'No slots available', 'handled': True}

    # Send time slots
    message_parts = [f"Date: {date_obj.strftime('%d %b %Y')}\n\nSelect a time:\n"]

    for idx, s in enumerate(slots, 1):
        message_parts.append(f"\n{idx}. {s['display']}")

    message_parts.append("\n\nReply with the number of your choice.")

    # Store slots for validation
    task_service.update_task(phone, 'client_book_session', {
        'available_slots': slots
    })

    whatsapp.send_message(phone, ''.join(message_parts))
    return {'success': True, 'message': 'Date selected', 'handled': True}


def _client_book_select_time(phone: str, task: Dict, user_input: str,
                              db, whatsapp, task_service) -> Dict:
    """Handle time slot selection step."""
    slots = task['data'].get('available_slots', [])
    selected_time = None

    # Check if input is a number
    if user_input.isdigit():
        idx = int(user_input) - 1
        if 0 <= idx < len(slots):
            selected_time = slots[idx]['time']
    else:
        # Try to match time string
        for s in slots:
            if s['time'] == user_input or s['display'].lower() == user_input.lower():
                selected_time = s['time']
                break

    if not selected_time:
        whatsapp.send_message(phone, "Please select a valid time from the options.")
        return {'success': False, 'message': 'Invalid time', 'handled': True}

    # Save and advance to confirmation
    task_service.update_task(phone, 'client_book_session', {
        'selected_time': selected_time,
        'step': 'confirm'
    })
    task_service.advance_step(phone, 'client_book_session')

    # Build confirmation message
    task_data = task_service.get_active_task(phone, 'client_book_session')['data']

    confirm_msg = (
        "Please confirm your booking request:\n\n"
        f"Trainer: {task_data.get('trainer_name')}\n"
        f"Type: {task_data.get('session_type_name')}\n"
        f"Date: {task_data.get('selected_date_display')}\n"
        f"Time: {selected_time}\n"
        f"Duration: {task_data.get('duration_minutes')} min\n"
        f"Price: {format_rand(task_data.get('price', 0))}\n\n"
        "Reply 'yes' to confirm or 'no' to cancel.\n\n"
        "Note: Your trainer will be notified and will confirm your booking."
    )

    whatsapp.send_message(phone, confirm_msg)
    return {'success': True, 'message': 'Time selected', 'handled': True}


def _client_book_confirm(phone: str, task: Dict, user_input: str,
                          db, whatsapp, task_service) -> Dict:
    """Handle booking confirmation step."""
    input_lower = user_input.lower().strip()

    if input_lower in ['confirm', 'yes', 'y', '1']:
        # Create the booking with pending status
        task_data = task['data']
        trainer_id = task_data.get('trainer_id')

        # Build session datetime
        date_str = task_data.get('selected_date')
        time_str = task_data.get('selected_time')

        # Parse time
        try:
            if len(time_str) == 5 and ':' in time_str:
                time_obj = datetime.strptime(time_str, '%H:%M').time()
            else:
                time_obj = datetime.strptime(time_str.upper(), '%I:%M %p').time()
        except ValueError:
            time_obj = datetime.strptime(time_str[:5], '%H:%M').time()

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        session_dt = SA_TZ.localize(datetime.combine(date_obj, time_obj))

        booking_data = {
            'id': str(uuid.uuid4()),
            'trainer_id': trainer_id,
            'client_id': phone,
            'session_datetime': session_dt.isoformat(),
            'session_type': task_data.get('session_type'),
            'duration_minutes': task_data.get('duration_minutes'),
            'price': task_data.get('price'),
            'status': 'pending',  # Pending until trainer approves
            'notes': 'Requested by client',
            'created_at': datetime.now(SA_TZ).isoformat(),
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        try:
            result = db.db.table('bookings').insert(booking_data).execute()

            if result and hasattr(result, 'data') and result.data:
                # Complete the task
                task_service.complete_task(phone, 'client_book_session')

                # Send confirmation to client
                success_msg = (
                    "Booking request submitted!\n\n"
                    f"Trainer: {task_data.get('trainer_name')}\n"
                    f"Date: {task_data.get('selected_date_display')}\n"
                    f"Time: {time_str}\n"
                    f"Type: {task_data.get('session_type_name')}\n\n"
                    "Your trainer has been notified and will confirm your booking soon."
                )
                whatsapp.send_message(phone, success_msg)

                # Notify the trainer
                _notify_trainer_booking_request(trainer_id, task_data, phone, db, whatsapp)

                log_info(f"Client booking request created: {booking_data['id']}")
                return {
                    'success': True,
                    'message': 'Booking request created',
                    'booking_id': booking_data['id'],
                    'handled': True
                }
            else:
                raise Exception("Failed to insert booking")

        except Exception as e:
            log_error(f"Error creating booking request: {str(e)}")
            whatsapp.send_message(
                phone,
                "Sorry, there was an error submitting your request. Please try again."
            )
            return {'success': False, 'message': str(e), 'handled': True}

    elif input_lower in ['cancel', 'no', 'n', '2']:
        task_service.cancel_task(phone, 'client_book_session')
        whatsapp.send_message(phone, "Booking cancelled. What would you like to do?")
        return {'success': True, 'message': 'Booking cancelled', 'handled': True}
    else:
        whatsapp.send_message(phone, "Please reply 'yes' to confirm or 'no' to cancel.")
        return {'success': False, 'message': 'Invalid confirmation', 'handled': True}


def handle_client_cancel_session_step(phone: str, task: Dict, user_input: str,
                                       db, whatsapp, task_service) -> Dict:
    """
    Handle each step of the client cancellation flow.

    Steps:
    1. select_booking - Select which booking to cancel
    2. confirm - Confirm cancellation
    """
    step = task['data'].get('step', 'select_booking')

    # Check for cancel/exit commands
    if user_input.lower().strip() in ['exit', 'quit', 'stop', 'back']:
        task_service.cancel_task(phone, 'client_cancel_session')
        whatsapp.send_message(phone, "Cancellation aborted. What would you like to do?")
        return {'success': True, 'message': 'Flow cancelled', 'handled': True}

    if step == 'select_booking':
        return _client_cancel_select_booking(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'confirm':
        return _client_cancel_confirm(phone, task, user_input, db, whatsapp, task_service)
    else:
        return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}


def _client_cancel_select_booking(phone: str, task: Dict, user_input: str,
                                   db, whatsapp, task_service) -> Dict:
    """Handle booking selection for cancellation."""
    bookings = task['data'].get('bookings', [])
    trainer_names = task['data'].get('trainer_names', {})
    selected_booking = None

    # Check if input is a number
    if user_input.isdigit():
        idx = int(user_input) - 1
        if 0 <= idx < len(bookings):
            selected_booking = bookings[idx]
        else:
            whatsapp.send_message(phone, "Invalid selection. Please try again.")
            return {'success': False, 'message': 'Invalid selection', 'handled': True}
    else:
        # Try to match by ID
        for b in bookings:
            if b['id'] == user_input:
                selected_booking = b
                break

        if not selected_booking:
            whatsapp.send_message(phone, "Please select a valid booking number.")
            return {'success': False, 'message': 'Booking not found', 'handled': True}

    # Save selection and advance
    dt = datetime.fromisoformat(selected_booking['session_datetime'].replace('Z', '+00:00'))
    formatted_dt = dt.astimezone(SA_TZ).strftime('%d %b %Y at %I:%M %p')
    session_type = selected_booking.get('session_type', 'Session').replace('_', ' ').title()
    trainer_name = trainer_names.get(selected_booking.get('trainer_id'), 'Trainer')

    task_service.update_task(phone, 'client_cancel_session', {
        'selected_booking': selected_booking,
        'selected_booking_display': formatted_dt,
        'selected_trainer_name': trainer_name,
        'step': 'confirm'
    })
    task_service.advance_step(phone, 'client_cancel_session')

    # Ask for confirmation
    confirm_msg = (
        f"Cancel this session?\n\n"
        f"{session_type}\n"
        f"Trainer: {trainer_name}\n"
        f"{formatted_dt}\n\n"
        "Reply 'yes' to confirm cancellation or 'no' to keep it."
    )

    whatsapp.send_message(phone, confirm_msg)
    return {'success': True, 'message': 'Booking selected', 'handled': True}


def _client_cancel_confirm(phone: str, task: Dict, user_input: str,
                            db, whatsapp, task_service) -> Dict:
    """Handle cancellation confirmation."""
    input_lower = user_input.lower().strip()

    if input_lower in ['confirm', 'yes', 'y', '1']:
        selected = task['data'].get('selected_booking')
        trainer_name = task['data'].get('selected_trainer_name', 'Trainer')

        try:
            # Update booking status
            update_data = {
                'status': 'cancelled',
                'notes': 'Cancelled by client',
                'updated_at': datetime.now(SA_TZ).isoformat()
            }
            result = db.db.table('bookings').update(update_data).eq(
                'id', selected['id']
            ).execute()

            if result and hasattr(result, 'data'):
                # Complete task
                task_service.complete_task(phone, 'client_cancel_session')

                # Send confirmation
                whatsapp.send_message(
                    phone,
                    f"Session cancelled.\n\n"
                    f"{task['data'].get('selected_booking_display')}\n\n"
                    f"{trainer_name} has been notified."
                )

                # Notify trainer
                _notify_trainer_cancellation(
                    selected.get('trainer_id'),
                    selected,
                    phone,
                    db,
                    whatsapp
                )

                log_info(f"Client cancelled booking: {selected['id']}")
                return {
                    'success': True,
                    'message': 'Booking cancelled',
                    'booking_id': selected['id'],
                    'handled': True
                }
            else:
                raise Exception("Failed to update booking")

        except Exception as e:
            log_error(f"Error cancelling booking: {str(e)}")
            whatsapp.send_message(
                phone,
                "Sorry, there was an error. Please try again or contact your trainer."
            )
            return {'success': False, 'message': str(e), 'handled': True}

    elif input_lower in ['no', 'n', '2', 'keep']:
        task_service.complete_task(phone, 'client_cancel_session')
        whatsapp.send_message(phone, "Session kept. No changes made.")
        return {'success': True, 'message': 'Cancellation aborted', 'handled': True}
    else:
        whatsapp.send_message(phone, "Please reply 'yes' to cancel or 'no' to keep the session.")
        return {'success': False, 'message': 'Invalid response', 'handled': True}
