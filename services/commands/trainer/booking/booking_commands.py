"""
Booking Command Handlers for Refiloe WhatsApp Assistant
Handles trainer booking operations with friendly, conversational interactions
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pytz
from utils.logger import log_info, log_error, log_warning

SA_TZ = pytz.timezone('Africa/Johannesburg')


def format_rand(amount: float) -> str:
    """
    Format amount as South African Rand

    Args:
        amount: Amount to format

    Returns:
        Formatted string with R prefix
    """
    return f"R{amount:,.2f}"


def format_datetime(dt: datetime) -> str:
    """
    Format datetime for display in Africa/Johannesburg timezone

    Args:
        dt: Datetime to format

    Returns:
        Formatted datetime string
    """
    if dt.tzinfo is None:
        dt = SA_TZ.localize(dt)
    else:
        dt = dt.astimezone(SA_TZ)

    return dt.strftime('%d %b %Y at %I:%M %p SAST')


def format_date(dt: datetime) -> str:
    """
    Format date for display

    Args:
        dt: Datetime to format

    Returns:
        Formatted date string
    """
    if dt.tzinfo is None:
        dt = SA_TZ.localize(dt)
    else:
        dt = dt.astimezone(SA_TZ)

    return dt.strftime('%d %b %Y')


def format_time(dt: datetime) -> str:
    """
    Format time for display

    Args:
        dt: Datetime to format

    Returns:
        Formatted time string
    """
    if dt.tzinfo is None:
        dt = SA_TZ.localize(dt)
    else:
        dt = dt.astimezone(SA_TZ)

    return dt.strftime('%I:%M %p')


def handle_book_session(phone: str, trainer_id: str, db, whatsapp, task_service) -> Dict:
    """
    Start the session booking flow

    This initiates a multi-step booking process where the client will be guided through:
    1. Selecting session type
    2. Choosing date and time
    3. Adding any notes
    4. Confirming the booking

    Args:
        phone: Client's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status and message
    """
    try:
        log_info(f"Starting booking flow for {phone} with trainer {trainer_id}")

        # Check if client already has an active booking task
        if task_service.has_active_task(phone, 'book_session'):
            message = ("📋 You already have a booking in progress!\n\n"
                      "Please complete your current booking or type 'cancel' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Booking already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Start the booking task
        task_service.start_task(phone, 'book_session', {
            'trainer_id': trainer_id,
            'step': 'select_type'
        })

        # Send welcome message with session type options
        message = ("💪 Let's book your training session!\n\n"
                  "What type of session would you like?\n\n"
                  "1️⃣ Personal training (60 min) - R350\n"
                  "2️⃣ Group session (60 min) - R200\n"
                  "3️⃣ Assessment (45 min) - R250\n"
                  "4️⃣ Follow-up session (30 min) - R150\n\n"
                  "Reply with the number of your choice or type 'cancel' to exit. 🙌")

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Booking flow started successfully for {phone}")
            return {
                'success': True,
                'message': 'Booking flow initiated',
                'whatsapp_sent': True,
                'task_started': True
            }
        else:
            log_error(f"Failed to send booking message to {phone}: {result.get('error')}")
            task_service.cancel_task(phone, 'book_session')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_book_session for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting booking flow: {str(e)}',
            'whatsapp_sent': False
        }


def handle_view_bookings(phone: str, trainer_id: str, db, whatsapp) -> Dict:
    """
    Show all upcoming bookings for the client

    Retrieves and displays upcoming sessions with key details like date, time,
    session type, and price. Shows the next 10 upcoming bookings.

    Args:
        phone: Client's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance

    Returns:
        Dictionary with success status and booking count
    """
    try:
        log_info(f"Retrieving bookings for {phone} with trainer {trainer_id}")

        # Get current time in SAST
        now = datetime.now(SA_TZ)

        # Query upcoming bookings
        # Find bookings where session_datetime is in the future and status is not cancelled
        result = db.db.table('bookings').select(
            'id, session_datetime, duration_minutes, session_type, price, status, notes'
        ).eq(
            'trainer_id', trainer_id
        ).eq(
            'client_id', phone  # Using phone as client_id
        ).gte(
            'session_datetime', now.isoformat()
        ).in_(
            'status', ['confirmed', 'pending']
        ).order(
            'session_datetime'
        ).limit(10).execute()

        bookings = result.data if result and hasattr(result, 'data') else []

        if not bookings:
            message = ("📅 No upcoming bookings found!\n\n"
                      "Ready to book your next session? 💪\n"
                      "Type 'book' to get started!")

            result = whatsapp.send_message(phone, message)

            return {
                'success': True,
                'message': 'No bookings found',
                'booking_count': 0,
                'whatsapp_sent': result.get('success', False)
            }

        # Format bookings message
        message_parts = ["📋 Your upcoming sessions:\n"]

        for idx, booking in enumerate(bookings, 1):
            # Parse session datetime
            session_dt = datetime.fromisoformat(booking['session_datetime'].replace('Z', '+00:00'))

            # Format booking details
            session_type = booking.get('session_type', 'Training session').title()
            price = format_rand(booking.get('price', 0))
            formatted_datetime = format_datetime(session_dt)
            duration = booking.get('duration_minutes', 60)
            status_emoji = '✅' if booking.get('status') == 'confirmed' else '⏳'

            booking_text = (f"\n{status_emoji} {idx}. {session_type}\n"
                          f"   📅 {formatted_datetime}\n"
                          f"   ⏱️ {duration} minutes\n"
                          f"   💰 {price}")

            # Add notes if present
            notes = booking.get('notes', '').strip()
            if notes:
                booking_text += f"\n   📝 {notes}"

            message_parts.append(booking_text)

        # Add footer
        message_parts.append("\n\n💡 Need to make changes?\n"
                           "Type 'cancel' to cancel a session or 'reschedule' to change the time.")

        message = '\n'.join(message_parts)

        # Ensure message doesn't exceed 1600 characters
        if len(message) > 1600:
            # Truncate and add notice
            message = message[:1550] + "\n\n... (showing first few bookings only)"

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Sent {len(bookings)} bookings to {phone}")
            return {
                'success': True,
                'message': 'Bookings sent successfully',
                'booking_count': len(bookings),
                'whatsapp_sent': True
            }
        else:
            log_error(f"Failed to send bookings to {phone}: {result.get('error')}")
            return {
                'success': False,
                'message': 'Failed to send bookings',
                'booking_count': len(bookings),
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_view_bookings for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error retrieving bookings: {str(e)}',
            'whatsapp_sent': False
        }


def handle_cancel_booking(phone: str, trainer_id: str, db, whatsapp, task_service) -> Dict:
    """
    Start the booking cancellation flow

    Initiates a multi-step process to cancel a booking:
    1. Shows upcoming bookings
    2. Asks client to select which one to cancel
    3. Confirms cancellation
    4. Updates booking status and sends confirmation

    Args:
        phone: Client's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status and message
    """
    try:
        log_info(f"Starting cancellation flow for {phone} with trainer {trainer_id}")

        # Check if client already has an active cancellation task
        if task_service.has_active_task(phone, 'cancel_booking'):
            message = ("📋 You already have a cancellation in progress!\n\n"
                      "Please complete your current request or type 'exit' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Cancellation already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get current time in SAST
        now = datetime.now(SA_TZ)

        # Query upcoming bookings that can be cancelled
        result = db.db.table('bookings').select(
            'id, session_datetime, session_type, price, status'
        ).eq(
            'trainer_id', trainer_id
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
            message = ("📅 No upcoming bookings to cancel!\n\n"
                      "If you need help, please contact your trainer directly. 💬")

            result = whatsapp.send_message(phone, message)

            return {
                'success': False,
                'message': 'No bookings to cancel',
                'whatsapp_sent': result.get('success', False)
            }

        # Start the cancellation task
        task_service.start_task(phone, 'cancel_booking', {
            'trainer_id': trainer_id,
            'bookings': bookings,
            'step': 'select_booking'
        })

        # Format bookings selection message
        message_parts = ["🗓️ Which session would you like to cancel?\n"]

        for idx, booking in enumerate(bookings, 1):
            session_dt = datetime.fromisoformat(booking['session_datetime'].replace('Z', '+00:00'))
            session_type = booking.get('session_type', 'Training session').title()
            formatted_datetime = format_datetime(session_dt)

            message_parts.append(f"\n{idx}. {session_type}")
            message_parts.append(f"   📅 {formatted_datetime}")

        message_parts.append("\n\nReply with the number of the session to cancel, or type 'exit' to go back.")

        message = '\n'.join(message_parts)

        # Ensure message doesn't exceed 1600 characters
        if len(message) > 1600:
            message = message[:1550] + "\n\n... (too many bookings, please contact trainer)"

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Cancellation flow started successfully for {phone}")
            return {
                'success': True,
                'message': 'Cancellation flow initiated',
                'whatsapp_sent': True,
                'task_started': True,
                'available_bookings': len(bookings)
            }
        else:
            log_error(f"Failed to send cancellation message to {phone}: {result.get('error')}")
            task_service.cancel_task(phone, 'cancel_booking')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_cancel_booking for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting cancellation flow: {str(e)}',
            'whatsapp_sent': False
        }


def handle_reschedule(phone: str, trainer_id: str, db, whatsapp, task_service) -> Dict:
    """
    Start the booking reschedule flow

    Initiates a multi-step process to reschedule a booking:
    1. Shows upcoming bookings
    2. Asks client to select which one to reschedule
    3. Asks for new date and time
    4. Confirms the change
    5. Updates booking and sends confirmation

    Args:
        phone: Client's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status and message
    """
    try:
        log_info(f"Starting reschedule flow for {phone} with trainer {trainer_id}")

        # Check if client already has an active reschedule task
        if task_service.has_active_task(phone, 'reschedule'):
            message = ("📋 You already have a reschedule in progress!\n\n"
                      "Please complete your current request or type 'exit' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Reschedule already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get current time in SAST
        now = datetime.now(SA_TZ)

        # Query upcoming bookings that can be rescheduled
        # Allow rescheduling at least 24 hours before the session
        min_reschedule_time = now + timedelta(hours=24)

        result = db.db.table('bookings').select(
            'id, session_datetime, session_type, price, duration_minutes, status'
        ).eq(
            'trainer_id', trainer_id
        ).eq(
            'client_id', phone
        ).gte(
            'session_datetime', min_reschedule_time.isoformat()
        ).in_(
            'status', ['confirmed', 'pending']
        ).order(
            'session_datetime'
        ).limit(10).execute()

        bookings = result.data if result and hasattr(result, 'data') else []

        if not bookings:
            message = ("📅 No bookings available to reschedule!\n\n"
                      "Sessions must be at least 24 hours away to reschedule.\n"
                      "For urgent changes, please contact your trainer directly. 💬")

            result = whatsapp.send_message(phone, message)

            return {
                'success': False,
                'message': 'No bookings available to reschedule',
                'whatsapp_sent': result.get('success', False)
            }

        # Start the reschedule task
        task_service.start_task(phone, 'reschedule', {
            'trainer_id': trainer_id,
            'bookings': bookings,
            'step': 'select_booking'
        })

        # Format bookings selection message
        message_parts = ["🔄 Which session would you like to reschedule?\n"]

        for idx, booking in enumerate(bookings, 1):
            session_dt = datetime.fromisoformat(booking['session_datetime'].replace('Z', '+00:00'))
            session_type = booking.get('session_type', 'Training session').title()
            formatted_datetime = format_datetime(session_dt)
            duration = booking.get('duration_minutes', 60)

            message_parts.append(f"\n{idx}. {session_type} ({duration} min)")
            message_parts.append(f"   📅 {formatted_datetime}")

        message_parts.append("\n\nReply with the number of the session to reschedule, or type 'exit' to go back.")

        message = '\n'.join(message_parts)

        # Ensure message doesn't exceed 1600 characters
        if len(message) > 1600:
            message = message[:1550] + "\n\n... (too many bookings, please contact trainer)"

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Reschedule flow started successfully for {phone}")
            return {
                'success': True,
                'message': 'Reschedule flow initiated',
                'whatsapp_sent': True,
                'task_started': True,
                'available_bookings': len(bookings)
            }
        else:
            log_error(f"Failed to send reschedule message to {phone}: {result.get('error')}")
            task_service.cancel_task(phone, 'reschedule')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_reschedule for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting reschedule flow: {str(e)}',
            'whatsapp_sent': False
        }


# Helper function to get booking by ID
def get_booking_by_id(booking_id: str, db) -> Optional[Dict]:
    """
    Retrieve a booking by ID

    Args:
        booking_id: Booking ID
        db: Database service instance

    Returns:
        Booking dictionary or None if not found
    """
    try:
        result = db.db.table('bookings').select('*').eq('id', booking_id).execute()

        if result and hasattr(result, 'data') and result.data:
            return result.data[0]

        return None

    except Exception as e:
        log_error(f"Error retrieving booking {booking_id}: {str(e)}")
        return None


# Helper function to update booking status
def update_booking_status(booking_id: str, status: str, db) -> bool:
    """
    Update booking status

    Args:
        booking_id: Booking ID
        status: New status ('confirmed', 'cancelled', 'pending', 'completed')
        db: Database service instance

    Returns:
        True if successful, False otherwise
    """
    try:
        update_data = {
            'status': status,
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        result = db.db.table('bookings').update(update_data).eq('id', booking_id).execute()

        if result and hasattr(result, 'data') and result.data:
            log_info(f"Updated booking {booking_id} status to {status}")
            return True

        log_error(f"Failed to update booking {booking_id} status")
        return False

    except Exception as e:
        log_error(f"Error updating booking {booking_id} status: {str(e)}")
        return False
