"""
Trainer Command Router for Refiloe WhatsApp Assistant
Routes trainer commands to appropriate handlers including booking, workout, and payment commands
"""

from typing import Dict, Optional, Callable, Any
import json
import os

from utils.logger import log_info, log_error, log_warning

# Import command handlers
from services.commands.trainer.booking import (
    handle_book_session,
    handle_view_bookings,
    handle_cancel_booking,
    handle_reschedule,
)

from services.commands.trainer.workout import (
    handle_send_workout,
    handle_send_workout_step,
    handle_create_workout,
    handle_create_workout_step,
    handle_view_workouts,
)

from services.commands.trainer.payment import (
    handle_request_payment,
    handle_request_payment_step,
    handle_view_payments,
    handle_setup_payment,
    handle_setup_payment_step,
    handle_set_payment_day,
    handle_set_payment_day_step,
)


class TrainerCommandRouter:
    """
    Routes trainer commands to appropriate handlers.

    Supports booking, workout, and payment commands with multi-step flows.
    """

    # Command to handler mapping
    COMMAND_HANDLERS = {
        # Booking commands
        '/book-session': 'handle_book_session',
        '/view-bookings': 'handle_view_bookings',
        '/cancel-booking': 'handle_cancel_booking',
        '/reschedule': 'handle_reschedule',

        # Workout commands
        '/send-workout': 'handle_send_workout',
        '/create-workout': 'handle_create_workout',
        '/view-workouts': 'handle_view_workouts',

        # Payment commands
        '/request-payment': 'handle_request_payment',
        '/view-payments': 'handle_view_payments',
        '/setup-payment': 'handle_setup_payment',
        '/set-payment-day': 'handle_set_payment_day',
    }

    # Multi-step task handlers
    STEP_HANDLERS = {
        'send_workout': handle_send_workout_step,
        'create_workout': handle_create_workout_step,
        'request_payment': handle_request_payment_step,
        'setup_payment': handle_setup_payment_step,
        'set_payment_day': handle_set_payment_day_step,
    }

    def __init__(self, db, whatsapp, task_service, payment_manager=None):
        """
        Initialize the trainer command router.

        Args:
            db: Database service instance
            whatsapp: WhatsApp notifier instance
            task_service: Task service for managing conversation state
            payment_manager: Optional payment manager instance
        """
        self.db = db
        self.whatsapp = whatsapp
        self.task_service = task_service
        self.payment_manager = payment_manager

        # Build handler registry
        self._handlers = {
            # Booking handlers
            'handle_book_session': handle_book_session,
            'handle_view_bookings': handle_view_bookings,
            'handle_cancel_booking': handle_cancel_booking,
            'handle_reschedule': handle_reschedule,

            # Workout handlers
            'handle_send_workout': handle_send_workout,
            'handle_create_workout': handle_create_workout,
            'handle_view_workouts': handle_view_workouts,

            # Payment handlers
            'handle_request_payment': handle_request_payment,
            'handle_view_payments': handle_view_payments,
            'handle_setup_payment': handle_setup_payment,
            'handle_set_payment_day': handle_set_payment_day,
        }

        log_info("TrainerCommandRouter initialized")

    def route_command(self, phone: str, trainer_id: str, command: str) -> Dict:
        """
        Route a command to the appropriate handler.

        Args:
            phone: Trainer's phone number
            trainer_id: Trainer's ID
            command: The command string (e.g., '/request-payment')

        Returns:
            Dictionary with success status and response details
        """
        # Normalize command
        command_lower = command.lower().strip()

        # Check for exact match first
        handler_name = self.COMMAND_HANDLERS.get(command_lower)

        # Try without slash prefix
        if not handler_name and not command_lower.startswith('/'):
            handler_name = self.COMMAND_HANDLERS.get(f'/{command_lower}')

        # Try matching by partial command (for natural language)
        if not handler_name:
            handler_name = self._match_natural_command(command_lower)

        if not handler_name:
            log_warning(f"Unknown command: {command}")
            return {
                'success': False,
                'message': f'Unknown command: {command}',
                'handled': False
            }

        handler = self._handlers.get(handler_name)
        if not handler:
            log_error(f"Handler not found: {handler_name}")
            return {
                'success': False,
                'message': f'Handler not implemented: {handler_name}',
                'handled': False
            }

        try:
            # Determine required arguments based on handler
            if handler_name in ['handle_view_bookings', 'handle_view_workouts', 'handle_view_payments']:
                # View handlers don't need task_service
                if handler_name == 'handle_view_payments':
                    result = handler(phone, trainer_id, self.db, self.whatsapp, self.payment_manager)
                else:
                    result = handler(phone, trainer_id, self.db, self.whatsapp)
            elif handler_name in ['handle_request_payment', 'handle_setup_payment', 'handle_set_payment_day']:
                # Payment handlers may need payment_manager
                result = handler(phone, trainer_id, self.db, self.whatsapp,
                               self.task_service, self.payment_manager)
            else:
                # Standard handlers with task_service
                result = handler(phone, trainer_id, self.db, self.whatsapp, self.task_service)

            result['handled'] = True
            return result

        except Exception as e:
            log_error(f"Error executing command {command}: {str(e)}")
            return {
                'success': False,
                'message': f'Error executing command: {str(e)}',
                'handled': False
            }

    def route_task_input(self, phone: str, trainer_id: str, task_type: str,
                         user_input: str) -> Dict:
        """
        Route user input for an active multi-step task.

        Args:
            phone: Trainer's phone number
            trainer_id: Trainer's ID
            task_type: Type of active task
            user_input: User's message input

        Returns:
            Dictionary with success status and response details
        """
        handler = self.STEP_HANDLERS.get(task_type)

        if not handler:
            log_warning(f"No step handler for task type: {task_type}")
            return {
                'success': False,
                'message': f'No handler for task type: {task_type}',
                'handled': False
            }

        try:
            # Get active task
            task = self.task_service.get_active_task(phone, task_type)
            if not task:
                return {
                    'success': False,
                    'message': f'No active {task_type} task found',
                    'handled': False
                }

            # Payment handlers may need payment_manager
            if task_type in ['request_payment', 'setup_payment', 'set_payment_day']:
                result = handler(phone, task, user_input, self.db, self.whatsapp,
                               self.task_service, self.payment_manager)
            else:
                result = handler(phone, task, user_input, self.db, self.whatsapp,
                               self.task_service)

            return result

        except Exception as e:
            log_error(f"Error handling task input for {task_type}: {str(e)}")
            return {
                'success': False,
                'message': f'Error handling task input: {str(e)}',
                'handled': False
            }

    def has_active_task(self, phone: str) -> Optional[str]:
        """
        Check if the user has any active task.

        Args:
            phone: User's phone number

        Returns:
            Task type string if active task exists, None otherwise
        """
        for task_type in self.STEP_HANDLERS.keys():
            if self.task_service.has_active_task(phone, task_type):
                return task_type
        return None

    def get_supported_commands(self) -> Dict[str, str]:
        """
        Get all supported commands with descriptions.

        Returns:
            Dictionary mapping commands to descriptions
        """
        return {
            # Booking commands
            '/book-session': 'Book a training session with a client',
            '/view-bookings': 'View your upcoming sessions',
            '/cancel-booking': 'Cancel a scheduled session',
            '/reschedule': 'Reschedule an existing session',

            # Workout commands
            '/send-workout': 'Send a workout to a client',
            '/create-workout': 'Create a new workout template',
            '/view-workouts': 'View your workout library',

            # Payment commands
            '/request-payment': 'Request payment from a client',
            '/view-payments': 'View payment status and history',
            '/setup-payment': 'Configure payment settings',
            '/set-payment-day': 'Set monthly payment reminder day',
        }

    def get_payment_commands(self) -> Dict[str, str]:
        """
        Get payment-specific commands.

        Returns:
            Dictionary mapping payment commands to descriptions
        """
        return {
            '/request-payment': 'Request payment from a client',
            '/view-payments': 'View payment status and history',
            '/setup-payment': 'Configure payment settings',
            '/set-payment-day': 'Set monthly payment reminder day',
        }

    def _match_natural_command(self, text: str) -> Optional[str]:
        """
        Match natural language input to a command.

        Args:
            text: User's natural language input

        Returns:
            Handler name if matched, None otherwise
        """
        text = text.lower().strip()

        # Payment command patterns
        payment_patterns = {
            'handle_request_payment': [
                'request payment', 'send payment', 'ask for payment',
                'payment request', 'get paid', 'charge client'
            ],
            'handle_view_payments': [
                'view payment', 'payment status', 'check payment',
                'payment history', 'my payments', 'see payments'
            ],
            'handle_setup_payment': [
                'setup payment', 'payment setup', 'configure payment',
                'payment settings', 'set up payment'
            ],
            'handle_set_payment_day': [
                'set payment day', 'payment day', 'reminder day',
                'change payment day', 'set reminder'
            ],
        }

        for handler_name, patterns in payment_patterns.items():
            for pattern in patterns:
                if pattern in text:
                    return handler_name

        # Workout command patterns
        workout_patterns = {
            'handle_send_workout': [
                'send workout', 'workout to', 'share workout'
            ],
            'handle_create_workout': [
                'create workout', 'new workout', 'make workout'
            ],
            'handle_view_workouts': [
                'view workout', 'my workout', 'workout library'
            ],
        }

        for handler_name, patterns in workout_patterns.items():
            for pattern in patterns:
                if pattern in text:
                    return handler_name

        # Booking command patterns
        booking_patterns = {
            'handle_book_session': ['book session', 'new booking', 'schedule session'],
            'handle_view_bookings': ['view booking', 'my session', 'upcoming session'],
            'handle_cancel_booking': ['cancel session', 'cancel booking'],
            'handle_reschedule': ['reschedule', 'change time', 'move session'],
        }

        for handler_name, patterns in booking_patterns.items():
            for pattern in patterns:
                if pattern in text:
                    return handler_name

        return None


# Singleton instance
_trainer_router_instance = None


def get_trainer_command_router(db=None, whatsapp=None, task_service=None,
                                payment_manager=None) -> Optional[TrainerCommandRouter]:
    """
    Get or create the trainer command router singleton.

    Args:
        db: Database service instance (required on first call)
        whatsapp: WhatsApp notifier instance (required on first call)
        task_service: Task service instance (required on first call)
        payment_manager: Optional payment manager instance

    Returns:
        TrainerCommandRouter instance or None if dependencies not provided
    """
    global _trainer_router_instance

    if _trainer_router_instance is None:
        if db is None or whatsapp is None or task_service is None:
            log_error("TrainerCommandRouter requires db, whatsapp, and task_service on first call")
            return None
        _trainer_router_instance = TrainerCommandRouter(
            db, whatsapp, task_service, payment_manager
        )

    return _trainer_router_instance
