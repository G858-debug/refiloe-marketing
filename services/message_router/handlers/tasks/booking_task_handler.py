"""
Booking Task Handler for Refiloe WhatsApp Assistant
Handles multi-step booking flows including book_session, cancel_booking, and reschedule
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pytz
import uuid
import requests
import os

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

# Default working hours if trainer doesn't have custom hours
DEFAULT_WORKING_HOURS = {
    'Monday': {'start': '06:00', 'end': '20:00'},
    'Tuesday': {'start': '06:00', 'end': '20:00'},
    'Wednesday': {'start': '06:00', 'end': '20:00'},
    'Thursday': {'start': '06:00', 'end': '20:00'},
    'Friday': {'start': '06:00', 'end': '20:00'},
    'Saturday': {'start': '07:00', 'end': '14:00'},
    'Sunday': None  # Closed
}


class BookingTaskHandler:
    """
    Handler for booking-related multi-step conversation flows.

    Supports three task types:
    - book_session: Multi-step flow to create a new booking
    - cancel_booking: Two-step flow to cancel an existing booking
    - reschedule: Three-step flow to reschedule an existing booking
    """

    def __init__(self, db, whatsapp, task_service):
        """
        Initialize the booking task handler.

        Args:
            db: Database service instance
            whatsapp: WhatsApp notifier instance
            task_service: Task service for managing conversation state
        """
        self.db = db
        self.whatsapp = whatsapp
        self.task_service = task_service

    # =========================================================================
    # MAIN ENTRY POINTS
    # =========================================================================

    def handle_task_input(self, phone: str, trainer_id: str, task_type: str,
                          user_input: str) -> Dict:
        """
        Main entry point for handling user input during a task flow.

        Routes the input to the appropriate handler based on task type and step.

        Args:
            phone: User's phone number
            trainer_id: Trainer's ID
            task_type: Type of task ('book_session', 'cancel_booking', 'reschedule')
            user_input: User's message input

        Returns:
            Dictionary with success status and response details
        """
        # Get active task
        task = self.task_service.get_active_task(phone, task_type)
        if not task:
            return {
                'success': False,
                'message': f'No active {task_type} task found',
                'handled': False
            }

        # Check for cancel/exit commands
        if user_input.lower().strip() in ['cancel', 'exit', 'quit', 'stop']:
            return self._handle_cancel_flow(phone, task_type)

        # Route to appropriate handler
        if task_type == 'book_session':
            return self._handle_book_session_step(phone, trainer_id, task, user_input)
        elif task_type == 'cancel_booking':
            return self._handle_cancel_booking_step(phone, trainer_id, task, user_input)
        elif task_type == 'reschedule':
            return self._handle_reschedule_step(phone, trainer_id, task, user_input)
        else:
            return {
                'success': False,
                'message': f'Unknown task type: {task_type}',
                'handled': False
            }

    # =========================================================================
    # BOOK SESSION FLOW
    # =========================================================================

    def start_book_session(self, phone: str, trainer_id: str) -> Dict:
        """
        Start the book session flow.

        Step 1: Ask to select or enter a client.

        Args:
            phone: Trainer's phone number initiating the booking
            trainer_id: Trainer's ID

        Returns:
            Dictionary with success status
        """
        try:
            log_info(f"Starting book_session flow for trainer {trainer_id}")

            # Check for existing task
            if self.task_service.has_active_task(phone, 'book_session'):
                message = ("You already have a booking in progress.\n\n"
                          "Please complete it or type 'cancel' to start over.")
                self.whatsapp.send_message(phone, message)
                return {'success': False, 'message': 'Booking already in progress'}

            # Get trainer's clients
            clients = self._get_trainer_clients(trainer_id)

            # Start task
            self.task_service.start_task(phone, 'book_session', {
                'trainer_id': trainer_id,
                'step': 'select_client',
                'clients': clients
            })

            # Send client selection message
            if clients and len(clients) > 0:
                # Show clients with buttons if 3 or fewer
                if len(clients) <= 3:
                    result = self._send_button_message(
                        phone,
                        "Let's book a session!\n\nSelect a client:",
                        [{'id': c['id'], 'title': c['name'][:20]} for c in clients[:3]]
                    )
                else:
                    # List clients with numbers for selection
                    message = "Let's book a session!\n\nSelect a client:\n"
                    for idx, client in enumerate(clients[:10], 1):
                        message += f"\n{idx}. {client['name']}"
                    message += "\n\nReply with the number, or type a new client's phone number."
                    result = self.whatsapp.send_message(phone, message)
            else:
                message = ("Let's book a session!\n\n"
                          "Enter the client's phone number (e.g., 0821234567):")
                result = self.whatsapp.send_message(phone, message)

            return {
                'success': result.get('success', False),
                'message': 'Book session flow started',
                'task_started': True,
                'whatsapp_sent': result.get('success', False)
            }

        except Exception as e:
            log_error(f"Error starting book_session: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _handle_book_session_step(self, phone: str, trainer_id: str,
                                   task: Dict, user_input: str) -> Dict:
        """
        Handle each step of the book_session flow.

        Steps:
        1. select_client - Select or enter client
        2. select_type - Select session type
        3. select_date - Select booking date
        4. select_time - Select time slot
        5. confirm - Confirm and create booking
        """
        step = task['data'].get('step', 'select_client')

        if step == 'select_client':
            return self._book_session_select_client(phone, trainer_id, task, user_input)
        elif step == 'select_type':
            return self._book_session_select_type(phone, trainer_id, task, user_input)
        elif step == 'select_date':
            return self._book_session_select_date(phone, trainer_id, task, user_input)
        elif step == 'select_time':
            return self._book_session_select_time(phone, trainer_id, task, user_input)
        elif step == 'confirm':
            return self._book_session_confirm(phone, trainer_id, task, user_input)
        else:
            return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}

    def _book_session_select_client(self, phone: str, trainer_id: str,
                                     task: Dict, user_input: str) -> Dict:
        """Handle client selection step."""
        clients = task['data'].get('clients', [])
        client_id = None
        client_name = None
        client_phone = None

        # Check if input is a number (selecting from list)
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(clients):
                selected = clients[idx]
                client_id = selected.get('id')
                client_name = selected.get('name')
                client_phone = selected.get('phone')
            else:
                self.whatsapp.send_message(phone, "Invalid selection. Please try again.")
                return {'success': False, 'message': 'Invalid client selection', 'handled': True}
        else:
            # Check if it's a phone number (new client)
            clean_input = user_input.replace(' ', '').replace('-', '')
            if clean_input.isdigit() and len(clean_input) >= 9:
                # It's a phone number - look up or use as new client
                client_phone = self._format_phone_number(clean_input)
                existing = self._get_client_by_phone(trainer_id, client_phone)
                if existing:
                    client_id = existing.get('id')
                    client_name = existing.get('name')
                else:
                    # New client - use phone as identifier
                    client_name = f"Client {client_phone[-4:]}"
            else:
                # Try matching by name from button response or typed name
                for c in clients:
                    if c.get('name', '').lower() == user_input.lower() or c.get('id') == user_input:
                        client_id = c.get('id')
                        client_name = c.get('name')
                        client_phone = c.get('phone')
                        break

                if not client_id:
                    self.whatsapp.send_message(
                        phone,
                        "Couldn't find that client. Please enter their phone number:"
                    )
                    return {'success': False, 'message': 'Client not found', 'handled': True}

        # Save client info and move to next step
        self.task_service.update_task(phone, 'book_session', {
            'client_id': client_id,
            'client_name': client_name,
            'client_phone': client_phone,
            'step': 'select_type'
        })
        self.task_service.advance_step(phone, 'book_session')

        # Send session type selection with buttons
        result = self._send_button_message(
            phone,
            f"Booking for {client_name}\n\nSelect session type:",
            [
                {'id': 'personal_training', 'title': 'Personal (R350)'},
                {'id': 'group_session', 'title': 'Group (R200)'},
                {'id': 'assessment', 'title': 'Assessment (R250)'}
            ]
        )

        # Also send text option for follow-up
        self.whatsapp.send_message(
            phone,
            "Or reply:\n4. Follow-up Session (R150)"
        )

        return {'success': True, 'message': 'Client selected', 'handled': True}

    def _book_session_select_type(self, phone: str, trainer_id: str,
                                   task: Dict, user_input: str) -> Dict:
        """Handle session type selection step."""
        session_type = None

        # Map input to session type
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
            self.whatsapp.send_message(phone, "Please select a valid session type (1-4).")
            return {'success': False, 'message': 'Invalid session type', 'handled': True}

        type_config = SESSION_TYPES[session_type]

        # Save and advance
        self.task_service.update_task(phone, 'book_session', {
            'session_type': session_type,
            'session_type_name': type_config['name'],
            'duration_minutes': type_config['duration_minutes'],
            'price': type_config['price'],
            'step': 'select_date'
        })
        self.task_service.advance_step(phone, 'book_session')

        # Get next 7 days
        dates = self._get_next_available_dates(trainer_id, 7)

        # Send date selection (show first 3 as buttons)
        if dates:
            button_dates = [
                {'id': d['date'], 'title': d['display'][:20]}
                for d in dates[:3]
            ]
            result = self._send_button_message(
                phone,
                f"{type_config['name']} - {type_config['duration_minutes']} min\n\n"
                f"Select a date:",
                button_dates
            )

            # Show remaining dates as text
            if len(dates) > 3:
                extra_dates = "\n\nMore dates:\n"
                for idx, d in enumerate(dates[3:], 4):
                    extra_dates += f"{idx}. {d['display']}\n"
                self.whatsapp.send_message(phone, extra_dates.strip())
        else:
            self.whatsapp.send_message(
                phone,
                "No available dates found. Please contact your admin."
            )
            return {'success': False, 'message': 'No dates available', 'handled': True}

        return {'success': True, 'message': 'Session type selected', 'handled': True}

    def _book_session_select_date(self, phone: str, trainer_id: str,
                                   task: Dict, user_input: str) -> Dict:
        """Handle date selection step."""
        dates = self._get_next_available_dates(trainer_id, 7)
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
            self.whatsapp.send_message(phone, "Please select a valid date from the options.")
            return {'success': False, 'message': 'Invalid date', 'handled': True}

        # Parse the date
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()

        # Save and advance
        self.task_service.update_task(phone, 'book_session', {
            'selected_date': selected_date,
            'selected_date_display': date_obj.strftime('%d %b %Y'),
            'step': 'select_time'
        })
        self.task_service.advance_step(phone, 'book_session')

        # Get available time slots for this date
        duration = task['data'].get('duration_minutes', 60)
        slots = self._get_available_time_slots(trainer_id, selected_date, duration)

        if not slots:
            self.whatsapp.send_message(
                phone,
                f"No available slots on {date_obj.strftime('%d %b')}.\n\n"
                "Please choose a different date."
            )
            # Go back to date selection
            self.task_service.update_task(phone, 'book_session', {'step': 'select_date'})
            return {'success': False, 'message': 'No slots available', 'handled': True}

        # Send time slots (first 3 as buttons)
        button_slots = [
            {'id': s['time'], 'title': s['display'][:20]}
            for s in slots[:3]
        ]
        result = self._send_button_message(
            phone,
            f"Date: {date_obj.strftime('%d %b %Y')}\n\nSelect a time:",
            button_slots
        )

        # Show remaining slots as text
        if len(slots) > 3:
            extra_slots = "\n\nMore times:\n"
            for idx, s in enumerate(slots[3:], 4):
                extra_slots += f"{idx}. {s['display']}\n"
            self.whatsapp.send_message(phone, extra_slots.strip())

        # Store slots for validation
        self.task_service.update_task(phone, 'book_session', {
            'available_slots': slots
        })

        return {'success': True, 'message': 'Date selected', 'handled': True}

    def _book_session_select_time(self, phone: str, trainer_id: str,
                                   task: Dict, user_input: str) -> Dict:
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
            self.whatsapp.send_message(phone, "Please select a valid time from the options.")
            return {'success': False, 'message': 'Invalid time', 'handled': True}

        # Save and advance to confirmation
        self.task_service.update_task(phone, 'book_session', {
            'selected_time': selected_time,
            'step': 'confirm'
        })
        self.task_service.advance_step(phone, 'book_session')

        # Build confirmation message
        task_data = self.task_service.get_active_task(phone, 'book_session')['data']

        confirm_msg = (
            "Please confirm your booking:\n\n"
            f"Client: {task_data.get('client_name')}\n"
            f"Type: {task_data.get('session_type_name')}\n"
            f"Date: {task_data.get('selected_date_display')}\n"
            f"Time: {selected_time}\n"
            f"Duration: {task_data.get('duration_minutes')} min\n"
            f"Price: R{task_data.get('price'):.2f}"
        )

        result = self._send_button_message(
            phone,
            confirm_msg,
            [
                {'id': 'confirm', 'title': 'Confirm'},
                {'id': 'cancel', 'title': 'Cancel'}
            ]
        )

        return {'success': True, 'message': 'Time selected', 'handled': True}

    def _book_session_confirm(self, phone: str, trainer_id: str,
                               task: Dict, user_input: str) -> Dict:
        """Handle booking confirmation step."""
        input_lower = user_input.lower().strip()

        if input_lower in ['confirm', 'yes', 'y', '1']:
            # Create the booking
            task_data = task['data']

            # Build session datetime
            date_str = task_data.get('selected_date')
            time_str = task_data.get('selected_time')
            session_dt = self._parse_session_datetime(date_str, time_str)

            booking_data = {
                'id': str(uuid.uuid4()),
                'trainer_id': trainer_id,
                'client_id': task_data.get('client_phone') or task_data.get('client_id'),
                'session_datetime': session_dt.isoformat(),
                'session_type': task_data.get('session_type'),
                'duration_minutes': task_data.get('duration_minutes'),
                'price': task_data.get('price'),
                'status': 'confirmed',
                'created_at': datetime.now(SA_TZ).isoformat(),
                'updated_at': datetime.now(SA_TZ).isoformat()
            }

            try:
                result = self.db.db.table('bookings').insert(booking_data).execute()

                if result and hasattr(result, 'data') and result.data:
                    # Complete the task
                    self.task_service.complete_task(phone, 'book_session')

                    # Send confirmation to trainer
                    success_msg = (
                        "Booking confirmed!\n\n"
                        f"Client: {task_data.get('client_name')}\n"
                        f"Date: {task_data.get('selected_date_display')}\n"
                        f"Time: {time_str}\n"
                        f"Type: {task_data.get('session_type_name')}\n\n"
                        "Client has been notified."
                    )
                    self.whatsapp.send_message(phone, success_msg)

                    # Notify the client
                    self._notify_client_booking_created(
                        task_data.get('client_phone'),
                        task_data,
                        trainer_id
                    )

                    log_info(f"Booking created: {booking_data['id']}")
                    return {
                        'success': True,
                        'message': 'Booking created',
                        'booking_id': booking_data['id'],
                        'handled': True
                    }
                else:
                    raise Exception("Failed to insert booking")

            except Exception as e:
                log_error(f"Error creating booking: {str(e)}")
                self.whatsapp.send_message(
                    phone,
                    "Sorry, there was an error creating the booking. Please try again."
                )
                return {'success': False, 'message': str(e), 'handled': True}

        elif input_lower in ['cancel', 'no', 'n', '2']:
            return self._handle_cancel_flow(phone, 'book_session')
        else:
            self.whatsapp.send_message(phone, "Please confirm (yes) or cancel (no).")
            return {'success': False, 'message': 'Invalid confirmation', 'handled': True}

    # =========================================================================
    # CANCEL BOOKING FLOW
    # =========================================================================

    def start_cancel_booking(self, phone: str, trainer_id: str) -> Dict:
        """
        Start the cancel booking flow.

        Step 1: Show bookings to cancel.
        """
        try:
            log_info(f"Starting cancel_booking flow for {phone}")

            if self.task_service.has_active_task(phone, 'cancel_booking'):
                message = "You already have a cancellation in progress.\n\nType 'cancel' to start over."
                self.whatsapp.send_message(phone, message)
                return {'success': False, 'message': 'Cancellation in progress'}

            # Get upcoming bookings
            bookings = self._get_upcoming_bookings(trainer_id, phone)

            if not bookings:
                message = "No upcoming bookings to cancel."
                self.whatsapp.send_message(phone, message)
                return {'success': False, 'message': 'No bookings to cancel'}

            # Start task
            self.task_service.start_task(phone, 'cancel_booking', {
                'trainer_id': trainer_id,
                'step': 'select_booking',
                'bookings': bookings
            })

            # Show bookings (first 3 as buttons)
            if len(bookings) <= 3:
                buttons = []
                for b in bookings:
                    dt = datetime.fromisoformat(b['session_datetime'].replace('Z', '+00:00'))
                    title = dt.astimezone(SA_TZ).strftime('%d %b %I:%M%p')[:20]
                    buttons.append({'id': b['id'], 'title': title})

                result = self._send_button_message(
                    phone,
                    "Which booking do you want to cancel?",
                    buttons
                )
            else:
                message = "Which booking do you want to cancel?\n"
                for idx, b in enumerate(bookings[:10], 1):
                    dt = datetime.fromisoformat(b['session_datetime'].replace('Z', '+00:00'))
                    formatted = dt.astimezone(SA_TZ).strftime('%d %b at %I:%M %p')
                    session_type = b.get('session_type', 'Session').replace('_', ' ').title()
                    message += f"\n{idx}. {session_type}\n    {formatted}"
                message += "\n\nReply with the number to cancel."
                self.whatsapp.send_message(phone, message)

            return {
                'success': True,
                'message': 'Cancel flow started',
                'task_started': True,
                'available_bookings': len(bookings)
            }

        except Exception as e:
            log_error(f"Error starting cancel_booking: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _handle_cancel_booking_step(self, phone: str, trainer_id: str,
                                     task: Dict, user_input: str) -> Dict:
        """Handle each step of the cancel_booking flow."""
        step = task['data'].get('step', 'select_booking')

        if step == 'select_booking':
            return self._cancel_booking_select(phone, trainer_id, task, user_input)
        elif step == 'confirm':
            return self._cancel_booking_confirm(phone, trainer_id, task, user_input)
        else:
            return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}

    def _cancel_booking_select(self, phone: str, trainer_id: str,
                                task: Dict, user_input: str) -> Dict:
        """Handle booking selection for cancellation."""
        bookings = task['data'].get('bookings', [])
        selected_booking = None

        # Check if input is a number
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(bookings):
                selected_booking = bookings[idx]
        else:
            # Try to match by ID (from button response)
            for b in bookings:
                if b['id'] == user_input:
                    selected_booking = b
                    break

        if not selected_booking:
            self.whatsapp.send_message(phone, "Please select a valid booking.")
            return {'success': False, 'message': 'Invalid selection', 'handled': True}

        # Save selection and advance
        dt = datetime.fromisoformat(selected_booking['session_datetime'].replace('Z', '+00:00'))
        formatted_dt = dt.astimezone(SA_TZ).strftime('%d %b %Y at %I:%M %p')

        self.task_service.update_task(phone, 'cancel_booking', {
            'selected_booking': selected_booking,
            'selected_booking_display': formatted_dt,
            'step': 'confirm'
        })
        self.task_service.advance_step(phone, 'cancel_booking')

        # Ask for confirmation
        session_type = selected_booking.get('session_type', 'Session').replace('_', ' ').title()
        result = self._send_button_message(
            phone,
            f"Cancel this booking?\n\n{session_type}\n{formatted_dt}",
            [
                {'id': 'confirm', 'title': 'Yes, Cancel'},
                {'id': 'no', 'title': 'No, Keep It'}
            ]
        )

        return {'success': True, 'message': 'Booking selected', 'handled': True}

    def _cancel_booking_confirm(self, phone: str, trainer_id: str,
                                 task: Dict, user_input: str) -> Dict:
        """Handle cancellation confirmation."""
        input_lower = user_input.lower().strip()

        if input_lower in ['confirm', 'yes', 'y', '1', 'yes, cancel']:
            selected = task['data'].get('selected_booking')

            try:
                # Update booking status
                update_data = {
                    'status': 'cancelled',
                    'updated_at': datetime.now(SA_TZ).isoformat()
                }
                result = self.db.db.table('bookings').update(update_data).eq(
                    'id', selected['id']
                ).execute()

                if result and hasattr(result, 'data'):
                    # Complete task
                    self.task_service.complete_task(phone, 'cancel_booking')

                    # Send confirmation
                    self.whatsapp.send_message(
                        phone,
                        f"Booking cancelled.\n\n"
                        f"{task['data'].get('selected_booking_display')}\n\n"
                        "The client has been notified."
                    )

                    # Notify client
                    self._notify_client_booking_cancelled(
                        selected.get('client_id'),
                        selected,
                        trainer_id
                    )

                    log_info(f"Booking cancelled: {selected['id']}")
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
                self.whatsapp.send_message(
                    phone,
                    "Sorry, there was an error. Please try again."
                )
                return {'success': False, 'message': str(e), 'handled': True}

        elif input_lower in ['no', 'n', '2', 'no, keep it']:
            self.task_service.complete_task(phone, 'cancel_booking')
            self.whatsapp.send_message(phone, "Booking kept. No changes made.")
            return {'success': True, 'message': 'Cancellation aborted', 'handled': True}
        else:
            self.whatsapp.send_message(phone, "Please reply Yes or No.")
            return {'success': False, 'message': 'Invalid response', 'handled': True}

    # =========================================================================
    # RESCHEDULE FLOW
    # =========================================================================

    def start_reschedule(self, phone: str, trainer_id: str) -> Dict:
        """
        Start the reschedule flow.

        Step 1: Show bookings available for rescheduling.
        """
        try:
            log_info(f"Starting reschedule flow for {phone}")

            if self.task_service.has_active_task(phone, 'reschedule'):
                message = "You already have a reschedule in progress.\n\nType 'cancel' to start over."
                self.whatsapp.send_message(phone, message)
                return {'success': False, 'message': 'Reschedule in progress'}

            # Get bookings at least 24h away
            now = datetime.now(SA_TZ)
            min_time = now + timedelta(hours=24)
            bookings = self._get_upcoming_bookings(trainer_id, phone, min_datetime=min_time)

            if not bookings:
                message = ("No bookings available to reschedule.\n\n"
                          "Bookings must be at least 24 hours away.")
                self.whatsapp.send_message(phone, message)
                return {'success': False, 'message': 'No bookings to reschedule'}

            # Start task
            self.task_service.start_task(phone, 'reschedule', {
                'trainer_id': trainer_id,
                'step': 'select_booking',
                'bookings': bookings
            })

            # Show bookings
            if len(bookings) <= 3:
                buttons = []
                for b in bookings:
                    dt = datetime.fromisoformat(b['session_datetime'].replace('Z', '+00:00'))
                    title = dt.astimezone(SA_TZ).strftime('%d %b %I:%M%p')[:20]
                    buttons.append({'id': b['id'], 'title': title})

                result = self._send_button_message(
                    phone,
                    "Which booking do you want to reschedule?",
                    buttons
                )
            else:
                message = "Which booking do you want to reschedule?\n"
                for idx, b in enumerate(bookings[:10], 1):
                    dt = datetime.fromisoformat(b['session_datetime'].replace('Z', '+00:00'))
                    formatted = dt.astimezone(SA_TZ).strftime('%d %b at %I:%M %p')
                    session_type = b.get('session_type', 'Session').replace('_', ' ').title()
                    message += f"\n{idx}. {session_type}\n    {formatted}"
                message += "\n\nReply with the number."
                self.whatsapp.send_message(phone, message)

            return {
                'success': True,
                'message': 'Reschedule flow started',
                'task_started': True,
                'available_bookings': len(bookings)
            }

        except Exception as e:
            log_error(f"Error starting reschedule: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _handle_reschedule_step(self, phone: str, trainer_id: str,
                                 task: Dict, user_input: str) -> Dict:
        """Handle each step of the reschedule flow."""
        step = task['data'].get('step', 'select_booking')

        if step == 'select_booking':
            return self._reschedule_select_booking(phone, trainer_id, task, user_input)
        elif step == 'select_date':
            return self._reschedule_select_date(phone, trainer_id, task, user_input)
        elif step == 'select_time':
            return self._reschedule_select_time(phone, trainer_id, task, user_input)
        elif step == 'confirm':
            return self._reschedule_confirm(phone, trainer_id, task, user_input)
        else:
            return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}

    def _reschedule_select_booking(self, phone: str, trainer_id: str,
                                    task: Dict, user_input: str) -> Dict:
        """Handle booking selection for rescheduling."""
        bookings = task['data'].get('bookings', [])
        selected_booking = None

        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(bookings):
                selected_booking = bookings[idx]
        else:
            for b in bookings:
                if b['id'] == user_input:
                    selected_booking = b
                    break

        if not selected_booking:
            self.whatsapp.send_message(phone, "Please select a valid booking.")
            return {'success': False, 'message': 'Invalid selection', 'handled': True}

        # Save and move to date selection
        self.task_service.update_task(phone, 'reschedule', {
            'selected_booking': selected_booking,
            'duration_minutes': selected_booking.get('duration_minutes', 60),
            'step': 'select_date'
        })
        self.task_service.advance_step(phone, 'reschedule')

        # Show available dates
        dates = self._get_next_available_dates(trainer_id, 7)

        if dates:
            button_dates = [
                {'id': d['date'], 'title': d['display'][:20]}
                for d in dates[:3]
            ]
            result = self._send_button_message(
                phone,
                "Select new date:",
                button_dates
            )

            if len(dates) > 3:
                extra = "\n\nMore dates:\n"
                for idx, d in enumerate(dates[3:], 4):
                    extra += f"{idx}. {d['display']}\n"
                self.whatsapp.send_message(phone, extra.strip())

        return {'success': True, 'message': 'Booking selected', 'handled': True}

    def _reschedule_select_date(self, phone: str, trainer_id: str,
                                 task: Dict, user_input: str) -> Dict:
        """Handle new date selection for rescheduling."""
        dates = self._get_next_available_dates(trainer_id, 7)
        selected_date = None

        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(dates):
                selected_date = dates[idx]['date']
        else:
            for d in dates:
                if d['date'] == user_input or d['display'].lower() == user_input.lower():
                    selected_date = d['date']
                    break

        if not selected_date:
            self.whatsapp.send_message(phone, "Please select a valid date.")
            return {'success': False, 'message': 'Invalid date', 'handled': True}

        date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()

        # Save and get time slots
        self.task_service.update_task(phone, 'reschedule', {
            'new_date': selected_date,
            'new_date_display': date_obj.strftime('%d %b %Y'),
            'step': 'select_time'
        })
        self.task_service.advance_step(phone, 'reschedule')

        duration = task['data'].get('duration_minutes', 60)
        slots = self._get_available_time_slots(trainer_id, selected_date, duration)

        if not slots:
            self.whatsapp.send_message(
                phone,
                f"No available slots on {date_obj.strftime('%d %b')}. Choose another date."
            )
            self.task_service.update_task(phone, 'reschedule', {'step': 'select_date'})
            return {'success': False, 'message': 'No slots', 'handled': True}

        button_slots = [
            {'id': s['time'], 'title': s['display'][:20]}
            for s in slots[:3]
        ]
        result = self._send_button_message(
            phone,
            f"Date: {date_obj.strftime('%d %b %Y')}\n\nSelect new time:",
            button_slots
        )

        if len(slots) > 3:
            extra = "\n\nMore times:\n"
            for idx, s in enumerate(slots[3:], 4):
                extra += f"{idx}. {s['display']}\n"
            self.whatsapp.send_message(phone, extra.strip())

        self.task_service.update_task(phone, 'reschedule', {'available_slots': slots})

        return {'success': True, 'message': 'Date selected', 'handled': True}

    def _reschedule_select_time(self, phone: str, trainer_id: str,
                                 task: Dict, user_input: str) -> Dict:
        """Handle new time selection for rescheduling."""
        slots = task['data'].get('available_slots', [])
        selected_time = None

        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(slots):
                selected_time = slots[idx]['time']
        else:
            for s in slots:
                if s['time'] == user_input or s['display'].lower() == user_input.lower():
                    selected_time = s['time']
                    break

        if not selected_time:
            self.whatsapp.send_message(phone, "Please select a valid time.")
            return {'success': False, 'message': 'Invalid time', 'handled': True}

        # Save and confirm
        self.task_service.update_task(phone, 'reschedule', {
            'new_time': selected_time,
            'step': 'confirm'
        })
        self.task_service.advance_step(phone, 'reschedule')

        task_data = self.task_service.get_active_task(phone, 'reschedule')['data']
        booking = task_data.get('selected_booking', {})
        old_dt = datetime.fromisoformat(booking['session_datetime'].replace('Z', '+00:00'))
        old_display = old_dt.astimezone(SA_TZ).strftime('%d %b at %I:%M %p')

        confirm_msg = (
            "Confirm reschedule:\n\n"
            f"From: {old_display}\n"
            f"To: {task_data.get('new_date_display')} at {selected_time}"
        )

        result = self._send_button_message(
            phone,
            confirm_msg,
            [
                {'id': 'confirm', 'title': 'Confirm'},
                {'id': 'cancel', 'title': 'Cancel'}
            ]
        )

        return {'success': True, 'message': 'Time selected', 'handled': True}

    def _reschedule_confirm(self, phone: str, trainer_id: str,
                             task: Dict, user_input: str) -> Dict:
        """Handle reschedule confirmation."""
        input_lower = user_input.lower().strip()

        if input_lower in ['confirm', 'yes', 'y', '1']:
            task_data = task['data']
            booking = task_data.get('selected_booking')

            # Build new datetime
            new_dt = self._parse_session_datetime(
                task_data.get('new_date'),
                task_data.get('new_time')
            )

            try:
                update_data = {
                    'session_datetime': new_dt.isoformat(),
                    'status': 'confirmed',
                    'updated_at': datetime.now(SA_TZ).isoformat()
                }
                result = self.db.db.table('bookings').update(update_data).eq(
                    'id', booking['id']
                ).execute()

                if result and hasattr(result, 'data'):
                    self.task_service.complete_task(phone, 'reschedule')

                    self.whatsapp.send_message(
                        phone,
                        f"Booking rescheduled!\n\n"
                        f"New time: {task_data.get('new_date_display')} at {task_data.get('new_time')}\n\n"
                        "The client has been notified."
                    )

                    # Notify client
                    self._notify_client_booking_rescheduled(
                        booking.get('client_id'),
                        booking,
                        task_data,
                        trainer_id
                    )

                    log_info(f"Booking rescheduled: {booking['id']}")
                    return {
                        'success': True,
                        'message': 'Booking rescheduled',
                        'booking_id': booking['id'],
                        'handled': True
                    }
                else:
                    raise Exception("Failed to update booking")

            except Exception as e:
                log_error(f"Error rescheduling: {str(e)}")
                self.whatsapp.send_message(phone, "Error rescheduling. Please try again.")
                return {'success': False, 'message': str(e), 'handled': True}

        elif input_lower in ['cancel', 'no', 'n', '2']:
            return self._handle_cancel_flow(phone, 'reschedule')
        else:
            self.whatsapp.send_message(phone, "Please confirm or cancel.")
            return {'success': False, 'message': 'Invalid response', 'handled': True}

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _handle_cancel_flow(self, phone: str, task_type: str) -> Dict:
        """Cancel an active flow and notify user."""
        self.task_service.cancel_task(phone, task_type)
        self.whatsapp.send_message(phone, "Cancelled. What would you like to do?")
        log_info(f"User cancelled {task_type} flow for {phone}")
        return {'success': True, 'message': 'Flow cancelled', 'handled': True}

    def _get_trainer_clients(self, trainer_id: str) -> List[Dict]:
        """Get list of trainer's clients."""
        try:
            result = self.db.db.table('clients').select(
                'id, name, phone'
            ).eq('trainer_id', trainer_id).execute()

            if result and hasattr(result, 'data'):
                return result.data
            return []
        except Exception as e:
            log_error(f"Error fetching clients: {str(e)}")
            return []

    def _get_client_by_phone(self, trainer_id: str, phone: str) -> Optional[Dict]:
        """Get a client by phone number."""
        try:
            result = self.db.db.table('clients').select(
                'id, name, phone'
            ).eq('trainer_id', trainer_id).eq('phone', phone).execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0]
            return None
        except Exception as e:
            log_error(f"Error fetching client: {str(e)}")
            return None

    def _get_trainer_working_hours(self, trainer_id: str) -> Dict:
        """Get trainer's working hours from database."""
        try:
            result = self.db.db.table('trainers').select(
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

    def _get_next_available_dates(self, trainer_id: str, num_days: int = 7) -> List[Dict]:
        """Get the next available dates based on working hours."""
        working_hours = self._get_trainer_working_hours(trainer_id)
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

    def _get_available_time_slots(self, trainer_id: str, date_str: str,
                                   duration: int = 60) -> List[Dict]:
        """Get available time slots for a specific date."""
        working_hours = self._get_trainer_working_hours(trainer_id)
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = date_obj.strftime('%A')

        hours = working_hours.get(day_name)
        if not hours:
            return []

        # Parse working hours
        start_time = datetime.strptime(hours['start'], '%H:%M').time()
        end_time = datetime.strptime(hours['end'], '%H:%M').time()

        # Get existing bookings for this date
        existing = self._get_bookings_for_date(trainer_id, date_str)
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

            # Check if slot is available (none of the duration overlaps existing)
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

    def _get_bookings_for_date(self, trainer_id: str, date_str: str) -> List[Dict]:
        """Get all bookings for a specific date."""
        try:
            # Query bookings for the date range
            start = f"{date_str}T00:00:00"
            end = f"{date_str}T23:59:59"

            result = self.db.db.table('bookings').select(
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

    def _get_upcoming_bookings(self, trainer_id: str, client_phone: str = None,
                                min_datetime: datetime = None) -> List[Dict]:
        """Get upcoming bookings, optionally filtered by client."""
        try:
            now = min_datetime or datetime.now(SA_TZ)

            query = self.db.db.table('bookings').select(
                'id, session_datetime, session_type, price, duration_minutes, status, client_id'
            ).eq('trainer_id', trainer_id).gte(
                'session_datetime', now.isoformat()
            ).in_(
                'status', ['confirmed', 'pending']
            ).order('session_datetime').limit(10)

            if client_phone:
                query = query.eq('client_id', client_phone)

            result = query.execute()

            if result and hasattr(result, 'data'):
                return result.data
            return []
        except Exception as e:
            log_error(f"Error fetching upcoming bookings: {str(e)}")
            return []

    def _parse_session_datetime(self, date_str: str, time_str: str) -> datetime:
        """Parse date and time strings into a datetime object."""
        # Handle various time formats
        time_str_clean = time_str.strip().upper()

        try:
            # Try 24-hour format first (HH:MM)
            if len(time_str_clean) == 5 and ':' in time_str_clean:
                time_obj = datetime.strptime(time_str_clean, '%H:%M').time()
            else:
                # Try 12-hour format (HH:MM AM/PM)
                time_obj = datetime.strptime(time_str_clean, '%I:%M %p').time()
        except ValueError:
            # Default to the raw time string
            time_obj = datetime.strptime(time_str_clean[:5], '%H:%M').time()

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        combined = datetime.combine(date_obj, time_obj)

        return SA_TZ.localize(combined)

    def _format_phone_number(self, phone: str) -> str:
        """Format phone number to standard format."""
        clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        clean = clean.lstrip('+')

        # South African number formatting
        if clean.startswith('0') and len(clean) == 10:
            clean = '27' + clean[1:]
        elif not clean.startswith('27') and len(clean) == 9:
            clean = '27' + clean

        return clean

    # =========================================================================
    # WHATSAPP BUTTON MESSAGES
    # =========================================================================

    def _send_button_message(self, to_number: str, body_text: str,
                              buttons: List[Dict]) -> Dict:
        """
        Send a WhatsApp interactive button message.

        Args:
            to_number: Recipient phone number
            body_text: Message body text
            buttons: List of button dicts with 'id' and 'title' keys (max 3)

        Returns:
            Dictionary with success status
        """
        # Ensure max 3 buttons
        buttons = buttons[:3]

        # Format phone number
        formatted_phone = self._format_phone_number(to_number)

        # Build button payload
        button_list = []
        for btn in buttons:
            button_list.append({
                "type": "reply",
                "reply": {
                    "id": str(btn['id']),
                    "title": btn['title'][:20]  # Max 20 chars for button title
                }
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body_text[:1024]  # Max 1024 chars for body
                },
                "action": {
                    "buttons": button_list
                }
            }
        }

        # Try to send button message, fallback to text if unsupported
        result = self._send_whatsapp_payload(payload)

        if not result.get('success'):
            # Fallback to text message with numbered options
            fallback_text = body_text + "\n"
            for idx, btn in enumerate(buttons, 1):
                fallback_text += f"\n{idx}. {btn['title']}"
            fallback_text += "\n\nReply with the number of your choice."

            return self.whatsapp.send_message(to_number, fallback_text)

        return result

    def _send_whatsapp_payload(self, payload: Dict) -> Dict:
        """
        Send a raw WhatsApp API payload.

        Args:
            payload: The API request payload

        Returns:
            Dictionary with success status
        """
        # Get credentials from environment
        phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
        api_token = os.getenv('WHATSAPP_API_TOKEN')
        api_url = os.getenv('WHATSAPP_API_URL')

        if not api_url and phone_number_id:
            api_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"

        if not api_token or not api_url:
            log_error("WhatsApp credentials not configured")
            return {'success': False, 'error': 'Credentials not configured'}

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                message_id = data.get('messages', [{}])[0].get('id')
                log_info(f"WhatsApp message sent: {message_id}")
                return {'success': True, 'message_id': message_id}
            else:
                error_msg = f"WhatsApp API error: {response.status_code} - {response.text}"
                log_error(error_msg)
                return {'success': False, 'error': error_msg}

        except Exception as e:
            log_error(f"Error sending WhatsApp message: {str(e)}")
            return {'success': False, 'error': str(e)}

    # =========================================================================
    # CLIENT NOTIFICATIONS
    # =========================================================================

    def _notify_client_booking_created(self, client_phone: str, booking_data: Dict,
                                         trainer_id: str) -> None:
        """Notify client that a booking has been created."""
        if not client_phone:
            return

        try:
            trainer_name = self._get_trainer_name(trainer_id)

            message = (
                "Your booking is confirmed!\n\n"
                f"Trainer: {trainer_name}\n"
                f"Date: {booking_data.get('selected_date_display')}\n"
                f"Time: {booking_data.get('selected_time')}\n"
                f"Type: {booking_data.get('session_type_name')}\n"
                f"Duration: {booking_data.get('duration_minutes')} min\n"
                f"Price: R{booking_data.get('price', 0):.2f}\n\n"
                "See you there!"
            )

            self.whatsapp.send_message(client_phone, message)
            log_info(f"Booking notification sent to client {client_phone}")

        except Exception as e:
            log_error(f"Error notifying client of booking: {str(e)}")

    def _notify_client_booking_cancelled(self, client_phone: str, booking: Dict,
                                          trainer_id: str) -> None:
        """Notify client that a booking has been cancelled."""
        if not client_phone:
            return

        try:
            trainer_name = self._get_trainer_name(trainer_id)
            dt = datetime.fromisoformat(booking['session_datetime'].replace('Z', '+00:00'))
            formatted_dt = dt.astimezone(SA_TZ).strftime('%d %b %Y at %I:%M %p')
            session_type = booking.get('session_type', 'Session').replace('_', ' ').title()

            message = (
                "Your booking has been cancelled.\n\n"
                f"Trainer: {trainer_name}\n"
                f"Session: {session_type}\n"
                f"Was scheduled: {formatted_dt}\n\n"
                "To book a new session, contact your trainer."
            )

            self.whatsapp.send_message(client_phone, message)
            log_info(f"Cancellation notification sent to client {client_phone}")

        except Exception as e:
            log_error(f"Error notifying client of cancellation: {str(e)}")

    def _notify_client_booking_rescheduled(self, client_phone: str, old_booking: Dict,
                                            new_data: Dict, trainer_id: str) -> None:
        """Notify client that a booking has been rescheduled."""
        if not client_phone:
            return

        try:
            trainer_name = self._get_trainer_name(trainer_id)

            old_dt = datetime.fromisoformat(old_booking['session_datetime'].replace('Z', '+00:00'))
            old_display = old_dt.astimezone(SA_TZ).strftime('%d %b at %I:%M %p')
            session_type = old_booking.get('session_type', 'Session').replace('_', ' ').title()

            message = (
                "Your booking has been rescheduled.\n\n"
                f"Trainer: {trainer_name}\n"
                f"Session: {session_type}\n\n"
                f"Old time: {old_display}\n"
                f"New time: {new_data.get('new_date_display')} at {new_data.get('new_time')}\n\n"
                "See you at the new time!"
            )

            self.whatsapp.send_message(client_phone, message)
            log_info(f"Reschedule notification sent to client {client_phone}")

        except Exception as e:
            log_error(f"Error notifying client of reschedule: {str(e)}")

    def _get_trainer_name(self, trainer_id: str) -> str:
        """Get trainer's name from database."""
        try:
            result = self.db.db.table('trainers').select('name').eq('id', trainer_id).execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0].get('name', 'Your Trainer')
            return 'Your Trainer'
        except Exception as e:
            log_warning(f"Error fetching trainer name: {str(e)}")
            return 'Your Trainer'


# Singleton instance
_booking_handler_instance = None


def get_booking_task_handler(db=None, whatsapp=None, task_service=None) -> Optional[BookingTaskHandler]:
    """
    Get or create the booking task handler singleton.

    Args:
        db: Database service instance (required on first call)
        whatsapp: WhatsApp notifier instance (required on first call)
        task_service: Task service instance (required on first call)

    Returns:
        BookingTaskHandler instance or None if dependencies not provided
    """
    global _booking_handler_instance

    if _booking_handler_instance is None:
        if db is None or whatsapp is None or task_service is None:
            log_error("BookingTaskHandler requires db, whatsapp, and task_service on first call")
            return None
        _booking_handler_instance = BookingTaskHandler(db, whatsapp, task_service)

    return _booking_handler_instance
