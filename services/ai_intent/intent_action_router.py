"""
Intent-to-Action Router for Refiloe AI Handler

Maps detected intents to actual command handlers, extracts relevant entities,
and returns friendly responses or initiates multi-step flows.
"""

from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re
import pytz

from utils.logger import log_info, log_error, log_warning

SA_TZ = pytz.timezone('Africa/Johannesburg')


class UserType(Enum):
    """User types in the system."""
    TRAINER = 'trainer'
    CLIENT = 'client'


class IntentCategory(Enum):
    """Categories of intents."""
    BOOKING = 'booking'
    WORKOUT = 'workout'
    PAYMENT = 'payment'
    ASSESSMENT = 'assessment'
    CLIENT_MANAGEMENT = 'client_management'
    GENERAL = 'general'


@dataclass
class ExtractedEntities:
    """Container for entities extracted from user message."""
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    trainer_name: Optional[str] = None
    date: Optional[datetime] = None
    time: Optional[datetime] = None
    datetime_combined: Optional[datetime] = None
    amount: Optional[float] = None
    currency: str = 'ZAR'
    session_type: Optional[str] = None
    workout_name: Optional[str] = None
    workout_type: Optional[str] = None
    duration_minutes: Optional[int] = None
    description: Optional[str] = None
    reason: Optional[str] = None
    booking_id: Optional[str] = None
    raw_entities: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'client_name': self.client_name,
            'client_phone': self.client_phone,
            'trainer_name': self.trainer_name,
            'date': self.date.isoformat() if self.date else None,
            'time': self.time.isoformat() if self.time else None,
            'datetime_combined': self.datetime_combined.isoformat() if self.datetime_combined else None,
            'amount': self.amount,
            'currency': self.currency,
            'session_type': self.session_type,
            'workout_name': self.workout_name,
            'workout_type': self.workout_type,
            'duration_minutes': self.duration_minutes,
            'description': self.description,
            'reason': self.reason,
            'booking_id': self.booking_id,
            'raw_entities': self.raw_entities,
        }


@dataclass
class IntentResult:
    """Result of intent detection and action routing."""
    success: bool
    intent: str
    category: IntentCategory
    confidence: float
    entities: ExtractedEntities
    response_message: Optional[str] = None
    task_started: bool = False
    task_type: Optional[str] = None
    requires_confirmation: bool = False
    handler_result: Optional[Dict] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'success': self.success,
            'intent': self.intent,
            'category': self.category.value,
            'confidence': self.confidence,
            'entities': self.entities.to_dict(),
            'response_message': self.response_message,
            'task_started': self.task_started,
            'task_type': self.task_type,
            'requires_confirmation': self.requires_confirmation,
            'handler_result': self.handler_result,
            'error': self.error,
        }


class IntentActionRouter:
    """
    Routes detected intents to appropriate command handlers.

    Handles both trainer and client intents, extracts relevant entities,
    and returns friendly responses or starts multi-step flows.
    """

    # Trainer intent to handler mapping
    TRAINER_INTENT_HANDLERS = {
        # Booking intents
        'book_session': {
            'handler': 'handle_book_session',
            'category': IntentCategory.BOOKING,
            'requires_task': True,
            'task_type': 'book_session',
            'description': 'Book a training session with a client',
            'friendly_start': "Let's book a session! First, select a client:",
        },
        'view_schedule': {
            'handler': 'handle_view_bookings',
            'category': IntentCategory.BOOKING,
            'requires_task': False,
            'description': 'View your upcoming sessions',
            'friendly_start': "Here are your upcoming sessions:",
        },
        'cancel_booking': {
            'handler': 'handle_cancel_booking',
            'category': IntentCategory.BOOKING,
            'requires_task': True,
            'task_type': 'cancel_booking',
            'description': 'Cancel a scheduled session',
            'friendly_start': "Which session would you like to cancel?",
        },
        'reschedule': {
            'handler': 'handle_reschedule',
            'category': IntentCategory.BOOKING,
            'requires_task': True,
            'task_type': 'reschedule',
            'description': 'Reschedule an existing session',
            'friendly_start': "Let's reschedule your session. Select the session to reschedule:",
        },

        # Workout intents
        'send_workout': {
            'handler': 'handle_send_workout',
            'category': IntentCategory.WORKOUT,
            'requires_task': True,
            'task_type': 'send_workout',
            'description': 'Send a workout to a client',
            'friendly_start': "Let's send a workout! Who should receive it?",
        },
        'create_workout': {
            'handler': 'handle_create_workout',
            'category': IntentCategory.WORKOUT,
            'requires_task': True,
            'task_type': 'create_workout',
            'description': 'Create a new workout template',
            'friendly_start': "Let's create a new workout template!",
        },
        'view_workouts': {
            'handler': 'handle_view_workouts',
            'category': IntentCategory.WORKOUT,
            'requires_task': False,
            'description': 'View your workout library',
            'friendly_start': "Here's your workout library:",
        },

        # Payment intents
        'request_payment': {
            'handler': 'handle_request_payment',
            'category': IntentCategory.PAYMENT,
            'requires_task': True,
            'task_type': 'request_payment',
            'description': 'Request payment from a client',
            'friendly_start': "Let's request a payment. Select the client:",
        },
        'check_revenue': {
            'handler': 'handle_view_payments',
            'category': IntentCategory.PAYMENT,
            'requires_task': False,
            'description': 'View payment status and revenue summary',
            'friendly_start': "Here's your payment summary:",
        },
        'setup_payment': {
            'handler': 'handle_setup_payment',
            'category': IntentCategory.PAYMENT,
            'requires_task': True,
            'task_type': 'setup_payment',
            'description': 'Configure payment settings',
            'friendly_start': "Let's set up your payment settings:",
        },
        'set_payment_day': {
            'handler': 'handle_set_payment_day',
            'category': IntentCategory.PAYMENT,
            'requires_task': True,
            'task_type': 'set_payment_day',
            'description': 'Set monthly payment reminder day',
            'friendly_start': "Which day should clients receive payment reminders?",
        },

        # Assessment intents
        'start_assessment': {
            'handler': 'handle_send_assessment',
            'category': IntentCategory.ASSESSMENT,
            'requires_task': True,
            'task_type': 'send_assessment',
            'description': 'Send fitness assessment to a client',
            'friendly_start': "Let's send a fitness assessment! Select the client:",
        },
        'view_assessments': {
            'handler': 'handle_view_assessments',
            'category': IntentCategory.ASSESSMENT,
            'requires_task': False,
            'description': 'View assessment responses',
            'friendly_start': "Here are your client assessments:",
        },

        # Client management intents
        'add_client': {
            'handler': 'handle_add_client',
            'category': IntentCategory.CLIENT_MANAGEMENT,
            'requires_task': True,
            'task_type': 'add_client',
            'description': 'Add a new client',
            'friendly_start': "Let's add a new client! What's their name?",
        },
        'view_clients': {
            'handler': 'handle_view_clients',
            'category': IntentCategory.CLIENT_MANAGEMENT,
            'requires_task': False,
            'description': 'View your client list',
            'friendly_start': "Here are your clients:",
        },
    }

    # Client intent to handler mapping
    CLIENT_INTENT_HANDLERS = {
        # Booking intents
        'book_session': {
            'handler': 'handle_request_booking',
            'category': IntentCategory.BOOKING,
            'requires_task': True,
            'task_type': 'client_book_session',
            'description': 'Request a training session with your trainer',
            'friendly_start': "Let's book a session! Select your trainer:",
        },
        'view_schedule': {
            'handler': 'handle_my_sessions',
            'category': IntentCategory.BOOKING,
            'requires_task': False,
            'description': 'View your upcoming sessions',
            'friendly_start': "Here are your upcoming sessions:",
        },
        'cancel_session': {
            'handler': 'handle_cancel_my_session',
            'category': IntentCategory.BOOKING,
            'requires_task': True,
            'task_type': 'client_cancel_session',
            'description': 'Cancel a scheduled session',
            'friendly_start': "Which session would you like to cancel?",
        },
        'reschedule': {
            'handler': 'handle_request_reschedule',
            'category': IntentCategory.BOOKING,
            'requires_task': True,
            'task_type': 'client_reschedule',
            'description': 'Request to reschedule a session',
            'friendly_start': "Let's reschedule your session. Select the session:",
        },

        # Workout intents
        'request_workout': {
            'handler': 'handle_request_workout',
            'category': IntentCategory.WORKOUT,
            'requires_task': False,
            'description': 'Request a workout from your trainer',
            'friendly_start': "I'll let your trainer know you'd like a workout!",
            'notify_trainer': True,
        },
        'view_workouts': {
            'handler': 'handle_my_workouts',
            'category': IntentCategory.WORKOUT,
            'requires_task': False,
            'description': 'View workouts sent to you',
            'friendly_start': "Here are your workouts:",
        },

        # Payment intents
        'check_payments': {
            'handler': 'handle_check_payments',
            'category': IntentCategory.PAYMENT,
            'requires_task': False,
            'description': 'View pending payment requests',
            'friendly_start': "Here are your payment requests:",
        },
        'payment_history': {
            'handler': 'handle_payment_history',
            'category': IntentCategory.PAYMENT,
            'requires_task': False,
            'description': 'View payment history',
            'friendly_start': "Here's your payment history:",
        },
        'auto_pay_settings': {
            'handler': 'handle_auto_payment_settings',
            'category': IntentCategory.PAYMENT,
            'requires_task': True,
            'task_type': 'auto_payment_settings',
            'description': 'Configure automatic payment settings',
            'friendly_start': "Let's configure your auto-pay settings:",
        },
    }

    # Entity extraction patterns
    AMOUNT_PATTERNS = [
        r'R\s*(\d+(?:[,\s]\d{3})*(?:\.\d{2})?)',  # R500, R1 000, R1,000.00
        r'(\d+(?:[,\s]\d{3})*(?:\.\d{2})?)\s*(?:rand|rands|zar)',  # 500 rand
        r'(?:pay|charge|request|amount)\s*(?:of\s*)?R?\s*(\d+(?:\.\d{2})?)',  # pay 500
    ]

    DATE_PATTERNS = [
        r'(?:on\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?',  # 15/01, 15-01-2024
        r'(?:on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        r'(?:on\s+)?(tomorrow|today|next\s+week)',
        r'(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
    ]

    TIME_PATTERNS = [
        r'(?:at\s+)?(\d{1,2})[:\.](\d{2})\s*(am|pm)?',  # 9:00, 14:30, 9:00am
        r'(?:at\s+)?(\d{1,2})\s*(am|pm)',  # 9am, 2pm
        r'(?:at\s+)?(\d{1,2})\s*(?:o\'?clock|oclock)',  # 9 o'clock
    ]

    PHONE_PATTERNS = [
        r'(?:0|\+27)\s*\d{2}\s*\d{3}\s*\d{4}',  # 082 123 4567, +27 82 123 4567
        r'\d{10}',  # 0821234567
    ]

    def __init__(self, db, whatsapp, task_service, payment_manager=None):
        """
        Initialize the intent action router.

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

        # Import handlers lazily to avoid circular imports
        self._trainer_handlers = None
        self._client_handlers = None

        log_info("IntentActionRouter initialized")

    def _load_trainer_handlers(self):
        """Lazily load trainer command handlers."""
        if self._trainer_handlers is not None:
            return

        self._trainer_handlers = {}

        try:
            # Booking handlers
            from services.commands.trainer.booking import (
                handle_book_session,
                handle_view_bookings,
                handle_cancel_booking,
                handle_reschedule,
            )
            self._trainer_handlers.update({
                'handle_book_session': handle_book_session,
                'handle_view_bookings': handle_view_bookings,
                'handle_cancel_booking': handle_cancel_booking,
                'handle_reschedule': handle_reschedule,
            })

            # Workout handlers
            from services.commands.trainer.workout import (
                handle_send_workout,
                handle_create_workout,
                handle_view_workouts,
            )
            self._trainer_handlers.update({
                'handle_send_workout': handle_send_workout,
                'handle_create_workout': handle_create_workout,
                'handle_view_workouts': handle_view_workouts,
            })

            # Payment handlers
            from services.commands.trainer.payment import (
                handle_request_payment,
                handle_view_payments,
                handle_setup_payment,
                handle_set_payment_day,
            )
            self._trainer_handlers.update({
                'handle_request_payment': handle_request_payment,
                'handle_view_payments': handle_view_payments,
                'handle_setup_payment': handle_setup_payment,
                'handle_set_payment_day': handle_set_payment_day,
            })

            # Assessment handlers
            from services.commands.trainer.assessment import (
                handle_send_assessment,
            )
            self._trainer_handlers.update({
                'handle_send_assessment': handle_send_assessment,
            })

            log_info("Trainer handlers loaded successfully")

        except ImportError as e:
            log_error(f"Failed to import trainer handlers: {e}")

    def _load_client_handlers(self):
        """Lazily load client command handlers."""
        if self._client_handlers is not None:
            return

        self._client_handlers = {}

        try:
            # Booking handlers
            from services.commands.client.booking import (
                handle_request_booking,
                handle_my_sessions,
                handle_cancel_my_session,
            )
            self._client_handlers.update({
                'handle_request_booking': handle_request_booking,
                'handle_my_sessions': handle_my_sessions,
                'handle_cancel_my_session': handle_cancel_my_session,
            })

            # Payment handlers
            from services.commands.client.payment import (
                handle_check_payments,
                handle_payment_history,
                handle_auto_payment_settings,
            )
            self._client_handlers.update({
                'handle_check_payments': handle_check_payments,
                'handle_payment_history': handle_payment_history,
                'handle_auto_payment_settings': handle_auto_payment_settings,
            })

            log_info("Client handlers loaded successfully")

        except ImportError as e:
            log_error(f"Failed to import client handlers: {e}")

    def route_intent(
        self,
        phone: str,
        user_id: str,
        user_type: UserType,
        intent: str,
        confidence: float,
        message: str,
        entities_from_ai: Optional[Dict] = None
    ) -> IntentResult:
        """
        Route a detected intent to the appropriate handler.

        Args:
            phone: User's phone number
            user_id: User's ID (trainer_id or client_id)
            user_type: Type of user (TRAINER or CLIENT)
            intent: Detected intent name
            confidence: Confidence score of intent detection (0-1)
            message: Original user message
            entities_from_ai: Optional pre-extracted entities from AI

        Returns:
            IntentResult with handler result and response
        """
        log_info(f"Routing intent '{intent}' for {user_type.value} {user_id}")

        # Extract entities from message
        entities = self._extract_entities(message, entities_from_ai)

        # Get handler configuration
        if user_type == UserType.TRAINER:
            handler_config = self.TRAINER_INTENT_HANDLERS.get(intent)
            self._load_trainer_handlers()
            handlers = self._trainer_handlers
        else:
            handler_config = self.CLIENT_INTENT_HANDLERS.get(intent)
            self._load_client_handlers()
            handlers = self._client_handlers

        if not handler_config:
            return self._create_unknown_intent_result(intent, entities)

        handler_name = handler_config['handler']
        handler = handlers.get(handler_name) if handlers else None

        if not handler:
            log_warning(f"Handler '{handler_name}' not found for intent '{intent}'")
            return self._create_handler_not_found_result(intent, handler_name, entities)

        # Execute handler
        try:
            result = self._execute_handler(
                handler=handler,
                handler_name=handler_name,
                handler_config=handler_config,
                phone=phone,
                user_id=user_id,
                user_type=user_type,
                entities=entities,
            )

            return IntentResult(
                success=result.get('success', False),
                intent=intent,
                category=handler_config['category'],
                confidence=confidence,
                entities=entities,
                response_message=result.get('message'),
                task_started=result.get('task_started', False),
                task_type=handler_config.get('task_type'),
                handler_result=result,
            )

        except Exception as e:
            log_error(f"Error executing handler for intent '{intent}': {e}")
            return IntentResult(
                success=False,
                intent=intent,
                category=handler_config['category'],
                confidence=confidence,
                entities=entities,
                error=str(e),
                response_message="Sorry, something went wrong. Please try again.",
            )

    def _execute_handler(
        self,
        handler: Callable,
        handler_name: str,
        handler_config: Dict,
        phone: str,
        user_id: str,
        user_type: UserType,
        entities: ExtractedEntities,
    ) -> Dict:
        """
        Execute a command handler with appropriate arguments.

        Args:
            handler: Handler function to execute
            handler_name: Name of the handler
            handler_config: Handler configuration
            phone: User's phone number
            user_id: User's ID
            user_type: Type of user
            entities: Extracted entities

        Returns:
            Handler result dictionary
        """
        # Determine which arguments the handler needs based on handler name
        view_only_handlers = [
            'handle_view_bookings', 'handle_view_workouts', 'handle_view_payments',
            'handle_my_sessions', 'handle_check_payments', 'handle_payment_history',
            'handle_view_assessments', 'handle_view_clients', 'handle_my_workouts',
        ]

        payment_handlers = [
            'handle_request_payment', 'handle_setup_payment',
            'handle_set_payment_day', 'handle_view_payments',
        ]

        if handler_name in view_only_handlers:
            # View handlers - no task_service needed
            if handler_name == 'handle_view_payments':
                return handler(phone, user_id, self.db, self.whatsapp, self.payment_manager)
            return handler(phone, user_id, self.db, self.whatsapp)

        elif handler_name in payment_handlers:
            # Payment handlers - may need payment_manager
            return handler(
                phone, user_id, self.db, self.whatsapp,
                self.task_service, self.payment_manager
            )

        else:
            # Standard handlers with task_service
            return handler(phone, user_id, self.db, self.whatsapp, self.task_service)

    def _extract_entities(
        self,
        message: str,
        entities_from_ai: Optional[Dict] = None
    ) -> ExtractedEntities:
        """
        Extract relevant entities from the user message.

        Combines AI-extracted entities with pattern-based extraction.

        Args:
            message: Original user message
            entities_from_ai: Optional pre-extracted entities from AI

        Returns:
            ExtractedEntities with all extracted data
        """
        entities = ExtractedEntities()
        message_lower = message.lower()

        # Start with AI-extracted entities if provided
        if entities_from_ai:
            entities.client_name = entities_from_ai.get('client_name')
            entities.trainer_name = entities_from_ai.get('trainer_name')
            entities.amount = entities_from_ai.get('amount')
            entities.session_type = entities_from_ai.get('session_type')
            entities.workout_name = entities_from_ai.get('workout_name')
            entities.description = entities_from_ai.get('description')
            entities.reason = entities_from_ai.get('reason')
            entities.raw_entities = entities_from_ai

        # Extract amount using patterns
        if entities.amount is None:
            entities.amount = self._extract_amount(message)

        # Extract date and time
        date_result = self._extract_date(message_lower)
        time_result = self._extract_time(message_lower)

        if date_result:
            entities.date = date_result
        if time_result:
            entities.time = time_result
        if date_result and time_result:
            entities.datetime_combined = datetime.combine(
                date_result.date(),
                time_result.time()
            )

        # Extract phone number
        phone_match = self._extract_phone(message)
        if phone_match:
            entities.client_phone = phone_match

        # Extract session type
        if entities.session_type is None:
            entities.session_type = self._extract_session_type(message_lower)

        # Extract workout type
        if entities.workout_type is None:
            entities.workout_type = self._extract_workout_type(message_lower)

        return entities

    def _extract_amount(self, message: str) -> Optional[float]:
        """Extract monetary amount from message."""
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                amount_str = match.group(1)
                # Remove spaces and commas
                amount_str = amount_str.replace(' ', '').replace(',', '')
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None

    def _extract_date(self, message: str) -> Optional[datetime]:
        """Extract date from message."""
        now = datetime.now(SA_TZ)

        # Check for relative dates first
        if 'today' in message:
            return now
        if 'tomorrow' in message:
            return now + timedelta(days=1)
        if 'next week' in message:
            return now + timedelta(days=7)

        # Check for day names
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(days):
            if day in message:
                # Find next occurrence of this day
                days_ahead = i - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return now + timedelta(days=days_ahead)

        # Check for numeric date patterns
        date_pattern = r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?'
        match = re.search(date_pattern, message)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else now.year
            if year < 100:
                year += 2000
            try:
                return SA_TZ.localize(datetime(year, month, day))
            except ValueError:
                pass

        # Check for month name patterns
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        month_pattern = r'(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
        match = re.search(month_pattern, message)
        if match:
            day = int(match.group(1))
            month = months.index(match.group(2)) + 1
            try:
                return SA_TZ.localize(datetime(now.year, month, day))
            except ValueError:
                pass

        return None

    def _extract_time(self, message: str) -> Optional[datetime]:
        """Extract time from message."""
        now = datetime.now(SA_TZ)

        # Pattern: 9:00, 14:30, 9:00am
        time_pattern = r'(?:at\s+)?(\d{1,2})[:\.](\d{2})\s*(am|pm)?'
        match = re.search(time_pattern, message)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            am_pm = match.group(3)

            if am_pm:
                if am_pm.lower() == 'pm' and hour != 12:
                    hour += 12
                elif am_pm.lower() == 'am' and hour == 12:
                    hour = 0

            try:
                return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except ValueError:
                pass

        # Pattern: 9am, 2pm
        simple_time_pattern = r'(?:at\s+)?(\d{1,2})\s*(am|pm)'
        match = re.search(simple_time_pattern, message)
        if match:
            hour = int(match.group(1))
            am_pm = match.group(2)

            if am_pm.lower() == 'pm' and hour != 12:
                hour += 12
            elif am_pm.lower() == 'am' and hour == 12:
                hour = 0

            try:
                return now.replace(hour=hour, minute=0, second=0, microsecond=0)
            except ValueError:
                pass

        return None

    def _extract_phone(self, message: str) -> Optional[str]:
        """Extract phone number from message."""
        # Remove spaces for easier matching
        clean_message = message.replace(' ', '')

        # South African phone patterns
        patterns = [
            r'(\+27\d{9})',  # +27821234567
            r'(0\d{9})',  # 0821234567
        ]

        for pattern in patterns:
            match = re.search(pattern, clean_message)
            if match:
                return match.group(1)

        return None

    def _extract_session_type(self, message: str) -> Optional[str]:
        """Extract session type from message."""
        session_types = {
            'personal': 'personal_training',
            'personal training': 'personal_training',
            '1 on 1': 'personal_training',
            'one on one': 'personal_training',
            'group': 'group_session',
            'group session': 'group_session',
            'assessment': 'assessment',
            'fitness assessment': 'assessment',
            'follow up': 'follow_up',
            'follow-up': 'follow_up',
            'followup': 'follow_up',
        }

        for keyword, session_type in session_types.items():
            if keyword in message:
                return session_type

        return None

    def _extract_workout_type(self, message: str) -> Optional[str]:
        """Extract workout type from message."""
        workout_types = {
            'strength': 'strength',
            'cardio': 'cardio',
            'hiit': 'hiit',
            'flexibility': 'flexibility',
            'yoga': 'yoga',
            'full body': 'full_body',
            'upper body': 'upper_body',
            'lower body': 'lower_body',
            'core': 'core',
            'abs': 'core',
        }

        for keyword, workout_type in workout_types.items():
            if keyword in message:
                return workout_type

        return None

    def _create_unknown_intent_result(
        self,
        intent: str,
        entities: ExtractedEntities
    ) -> IntentResult:
        """Create result for unknown intent."""
        return IntentResult(
            success=False,
            intent=intent,
            category=IntentCategory.GENERAL,
            confidence=0.0,
            entities=entities,
            response_message=(
                "I'm not sure what you'd like to do. "
                "Try saying things like:\n"
                "- 'Book a session'\n"
                "- 'View my schedule'\n"
                "- 'Send a workout'\n"
                "- 'Request payment'\n"
                "Or type /help for all commands."
            ),
            error=f"Unknown intent: {intent}",
        )

    def _create_handler_not_found_result(
        self,
        intent: str,
        handler_name: str,
        entities: ExtractedEntities
    ) -> IntentResult:
        """Create result when handler is not found."""
        return IntentResult(
            success=False,
            intent=intent,
            category=IntentCategory.GENERAL,
            confidence=0.0,
            entities=entities,
            response_message=(
                "This feature is coming soon! "
                "Try another command or type /help."
            ),
            error=f"Handler not found: {handler_name}",
        )

    def get_available_intents(self, user_type: UserType) -> Dict[str, Dict]:
        """
        Get available intents for a user type.

        Args:
            user_type: Type of user (TRAINER or CLIENT)

        Returns:
            Dictionary of intent configurations
        """
        if user_type == UserType.TRAINER:
            return self.TRAINER_INTENT_HANDLERS.copy()
        return self.CLIENT_INTENT_HANDLERS.copy()

    def get_intent_by_category(
        self,
        user_type: UserType,
        category: IntentCategory
    ) -> Dict[str, Dict]:
        """
        Get intents filtered by category.

        Args:
            user_type: Type of user
            category: Category to filter by

        Returns:
            Filtered dictionary of intent configurations
        """
        intents = self.get_available_intents(user_type)
        return {
            intent: config
            for intent, config in intents.items()
            if config['category'] == category
        }

    def build_help_message(self, user_type: UserType) -> str:
        """
        Build a help message listing available intents.

        Args:
            user_type: Type of user

        Returns:
            Formatted help message
        """
        intents = self.get_available_intents(user_type)

        # Group by category
        by_category: Dict[IntentCategory, List[str]] = {}
        for intent, config in intents.items():
            category = config['category']
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(f"- {config['description']}")

        # Build message
        lines = ["*Available Actions*\n"]

        category_names = {
            IntentCategory.BOOKING: 'Bookings',
            IntentCategory.WORKOUT: 'Workouts',
            IntentCategory.PAYMENT: 'Payments',
            IntentCategory.ASSESSMENT: 'Assessments',
            IntentCategory.CLIENT_MANAGEMENT: 'Client Management',
        }

        for category, actions in by_category.items():
            name = category_names.get(category, category.value.title())
            lines.append(f"\n*{name}*")
            lines.extend(actions)

        lines.append("\n\nJust tell me what you'd like to do!")

        return '\n'.join(lines)


# Singleton instance
_intent_router_instance = None


def get_intent_action_router(
    db=None,
    whatsapp=None,
    task_service=None,
    payment_manager=None
) -> Optional[IntentActionRouter]:
    """
    Get or create the intent action router singleton.

    Args:
        db: Database service instance (required on first call)
        whatsapp: WhatsApp notifier instance (required on first call)
        task_service: Task service instance (required on first call)
        payment_manager: Optional payment manager instance

    Returns:
        IntentActionRouter instance or None if dependencies not provided
    """
    global _intent_router_instance

    if _intent_router_instance is None:
        if db is None or whatsapp is None or task_service is None:
            log_error("IntentActionRouter requires db, whatsapp, and task_service on first call")
            return None
        _intent_router_instance = IntentActionRouter(
            db, whatsapp, task_service, payment_manager
        )

    return _intent_router_instance
