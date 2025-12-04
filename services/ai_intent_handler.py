"""
AI Intent Handler for Refiloe WhatsApp Assistant

Handles intent detection and routes actionable intents to the IntentActionRouter,
while generating conversational responses for non-actionable intents.
"""

from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

from utils.logger import log_info, log_error, log_warning
from services.ai_intent.intent_action_router import (
    IntentActionRouter,
    IntentResult,
    ExtractedEntities,
    UserType,
    IntentCategory,
    get_intent_action_router,
)


@dataclass
class IntentDetectionResult:
    """Result from AI intent detection."""
    intent: str
    confidence: float
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    raw_response: Optional[str] = None

    def has_actionable_intent(self) -> bool:
        """Check if the detected intent can be mapped to an action."""
        # Non-actionable intents (conversational)
        non_actionable = {
            'greeting', 'farewell', 'thanks', 'help', 'unknown',
            'chitchat', 'question', 'feedback', 'complaint',
            'general_query', 'off_topic', 'clarification',
        }
        return self.intent not in non_actionable and self.confidence >= 0.6


class AIIntentHandler:
    """
    Handles AI-powered intent detection and action routing.

    This handler:
    1. Detects user intent from natural language messages
    2. Routes actionable intents to the IntentActionRouter
    3. Generates conversational responses for non-actionable intents
    """

    # Intent mapping to action router intents
    INTENT_ACTION_MAP = {
        # Booking intents
        'book_session': 'book_session',
        'schedule_session': 'book_session',
        'make_appointment': 'book_session',
        'view_schedule': 'view_schedule',
        'check_schedule': 'view_schedule',
        'my_bookings': 'view_schedule',
        'cancel_booking': 'cancel_booking',
        'cancel_session': 'cancel_booking',
        'reschedule': 'reschedule',
        'change_booking': 'reschedule',
        'move_session': 'reschedule',

        # Workout intents
        'send_workout': 'send_workout',
        'share_workout': 'send_workout',
        'create_workout': 'create_workout',
        'new_workout': 'create_workout',
        'view_workouts': 'view_workouts',
        'my_workouts': 'view_workouts',
        'request_workout': 'request_workout',
        'need_workout': 'request_workout',

        # Payment intents
        'request_payment': 'request_payment',
        'send_invoice': 'request_payment',
        'charge_client': 'request_payment',
        'check_revenue': 'check_revenue',
        'view_payments': 'check_revenue',
        'payment_status': 'check_revenue',
        'setup_payment': 'setup_payment',
        'payment_settings': 'setup_payment',
        'set_payment_day': 'set_payment_day',
        'payment_reminder': 'set_payment_day',
        'check_payments': 'check_payments',
        'payment_history': 'payment_history',

        # Assessment intents
        'start_assessment': 'start_assessment',
        'send_assessment': 'start_assessment',
        'fitness_assessment': 'start_assessment',
        'view_assessments': 'view_assessments',

        # Client management intents
        'add_client': 'add_client',
        'new_client': 'add_client',
        'view_clients': 'view_clients',
        'my_clients': 'view_clients',
    }

    # Conversational response templates
    CONVERSATIONAL_RESPONSES = {
        'greeting': [
            "Hi there! How can I help you today?",
            "Hello! What would you like to do?",
            "Hey! I'm here to help. What do you need?",
        ],
        'farewell': [
            "Goodbye! Have a great day!",
            "See you later! Take care!",
            "Bye! Let me know if you need anything else.",
        ],
        'thanks': [
            "You're welcome! Anything else I can help with?",
            "Happy to help! Let me know if you need more assistance.",
            "No problem! Is there anything else?",
        ],
        'help': [
            "I can help you with:\n"
            "- Booking sessions\n"
            "- Viewing your schedule\n"
            "- Sending workouts\n"
            "- Managing payments\n"
            "- Client assessments\n\n"
            "Just tell me what you'd like to do!",
        ],
        'unknown': [
            "I'm not sure I understand. Could you rephrase that?",
            "I didn't quite catch that. What would you like to do?",
            "Could you tell me more about what you need?",
        ],
    }

    def __init__(self, db, whatsapp, task_service, payment_manager=None, ai_client=None):
        """
        Initialize the AI intent handler.

        Args:
            db: Database service instance
            whatsapp: WhatsApp notifier instance
            task_service: Task service for managing conversation state
            payment_manager: Optional payment manager instance
            ai_client: Optional AI client for intent detection
        """
        self.db = db
        self.whatsapp = whatsapp
        self.task_service = task_service
        self.payment_manager = payment_manager
        self.ai_client = ai_client

        # Initialize or get the action router
        self._action_router = get_intent_action_router(
            db=db,
            whatsapp=whatsapp,
            task_service=task_service,
            payment_manager=payment_manager,
        )

        log_info("AIIntentHandler initialized")

    def handle_message(
        self,
        phone: str,
        message: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Handle an incoming message by detecting intent and routing appropriately.

        Args:
            phone: User's phone number
            message: The user's message text
            context: Optional context including user info, conversation history, etc.

        Returns:
            Dictionary with response details
        """
        context = context or {}

        # Detect intent from message
        intent_result = self._detect_intent(message, context)

        log_info(f"Detected intent '{intent_result.intent}' with confidence {intent_result.confidence}")

        # Check if intent has an action mapping
        if self._has_action_mapping(intent_result.intent):
            # Route to action router
            return self._execute_intent_action(intent_result, context, phone)
        else:
            # Generate conversational response
            return self._generate_conversational_response(intent_result, context, phone)

    def _detect_intent(
        self,
        message: str,
        context: Optional[Dict] = None
    ) -> IntentDetectionResult:
        """
        Detect intent from user message.

        Uses AI client if available, otherwise falls back to pattern matching.

        Args:
            message: User's message text
            context: Optional context for better detection

        Returns:
            IntentDetectionResult with detected intent and extracted data
        """
        # If AI client is available, use it for detection
        if self.ai_client:
            try:
                return self._detect_intent_with_ai(message, context)
            except Exception as e:
                log_error(f"AI intent detection failed: {e}")
                # Fall back to pattern matching

        # Pattern-based intent detection
        return self._detect_intent_patterns(message, context)

    def _detect_intent_with_ai(
        self,
        message: str,
        context: Optional[Dict] = None
    ) -> IntentDetectionResult:
        """
        Detect intent using AI client.

        Args:
            message: User's message text
            context: Optional context

        Returns:
            IntentDetectionResult from AI analysis
        """
        # This would integrate with your AI client
        # For now, return a placeholder that falls through to pattern matching
        raise NotImplementedError("AI detection not configured")

    def _detect_intent_patterns(
        self,
        message: str,
        context: Optional[Dict] = None
    ) -> IntentDetectionResult:
        """
        Detect intent using pattern matching.

        Args:
            message: User's message text
            context: Optional context

        Returns:
            IntentDetectionResult from pattern matching
        """
        message_lower = message.lower().strip()
        extracted_data = {}

        # Greeting patterns
        if any(g in message_lower for g in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']):
            return IntentDetectionResult(intent='greeting', confidence=0.9)

        # Farewell patterns
        if any(f in message_lower for f in ['bye', 'goodbye', 'see you', 'later']):
            return IntentDetectionResult(intent='farewell', confidence=0.9)

        # Thanks patterns
        if any(t in message_lower for t in ['thank', 'thanks', 'appreciate']):
            return IntentDetectionResult(intent='thanks', confidence=0.9)

        # Help patterns
        if any(h in message_lower for h in ['help', 'what can you do', 'how do i']):
            return IntentDetectionResult(intent='help', confidence=0.9)

        # Booking patterns
        if any(b in message_lower for b in ['book', 'schedule', 'appointment']):
            extracted_data = self._extract_booking_data(message)
            if 'cancel' in message_lower:
                return IntentDetectionResult(
                    intent='cancel_booking', confidence=0.85,
                    extracted_data=extracted_data
                )
            if any(r in message_lower for r in ['reschedule', 'move', 'change']):
                return IntentDetectionResult(
                    intent='reschedule', confidence=0.85,
                    extracted_data=extracted_data
                )
            return IntentDetectionResult(
                intent='book_session', confidence=0.85,
                extracted_data=extracted_data
            )

        # View schedule patterns
        if any(v in message_lower for v in ['schedule', 'upcoming', 'my sessions', 'my bookings']):
            return IntentDetectionResult(intent='view_schedule', confidence=0.8)

        # Workout patterns
        if 'workout' in message_lower:
            extracted_data = self._extract_workout_data(message)
            if any(s in message_lower for s in ['send', 'share', 'give']):
                return IntentDetectionResult(
                    intent='send_workout', confidence=0.85,
                    extracted_data=extracted_data
                )
            if any(c in message_lower for c in ['create', 'new', 'make']):
                return IntentDetectionResult(
                    intent='create_workout', confidence=0.85,
                    extracted_data=extracted_data
                )
            if any(v in message_lower for v in ['view', 'see', 'show', 'my']):
                return IntentDetectionResult(intent='view_workouts', confidence=0.8)
            if any(r in message_lower for r in ['need', 'want', 'request']):
                return IntentDetectionResult(intent='request_workout', confidence=0.8)

        # Payment patterns
        if any(p in message_lower for p in ['payment', 'pay', 'invoice', 'charge', 'money']):
            extracted_data = self._extract_payment_data(message)
            if any(r in message_lower for r in ['request', 'send', 'ask']):
                return IntentDetectionResult(
                    intent='request_payment', confidence=0.85,
                    extracted_data=extracted_data
                )
            if any(v in message_lower for v in ['view', 'check', 'status', 'history']):
                return IntentDetectionResult(intent='check_revenue', confidence=0.8)
            if any(s in message_lower for s in ['setup', 'configure', 'settings']):
                return IntentDetectionResult(intent='setup_payment', confidence=0.8)

        # Assessment patterns
        if 'assessment' in message_lower:
            if any(s in message_lower for s in ['send', 'start', 'begin']):
                extracted_data = self._extract_client_data(message)
                return IntentDetectionResult(
                    intent='start_assessment', confidence=0.85,
                    extracted_data=extracted_data
                )
            if any(v in message_lower for v in ['view', 'see', 'check']):
                return IntentDetectionResult(intent='view_assessments', confidence=0.8)

        # Client patterns
        if 'client' in message_lower:
            if any(a in message_lower for a in ['add', 'new', 'register']):
                extracted_data = self._extract_client_data(message)
                return IntentDetectionResult(
                    intent='add_client', confidence=0.85,
                    extracted_data=extracted_data
                )
            if any(v in message_lower for v in ['view', 'see', 'list', 'my']):
                return IntentDetectionResult(intent='view_clients', confidence=0.8)

        # Unknown intent
        return IntentDetectionResult(intent='unknown', confidence=0.3)

    def _extract_booking_data(self, message: str) -> Dict[str, Any]:
        """Extract booking-related data from message."""
        import re
        data = {}

        # Extract client name (look for patterns like "Book Sarah" or "session with John")
        name_patterns = [
            r'(?:book|schedule|session with|for)\s+([A-Z][a-z]+)',
            r'([A-Z][a-z]+)(?:\'s)?\s+(?:session|booking)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, message)
            if match:
                data['client_name'] = match.group(1)
                break

        # Extract date references
        message_lower = message.lower()
        if 'today' in message_lower:
            data['date'] = 'today'
        elif 'tomorrow' in message_lower:
            data['date'] = 'tomorrow'
        else:
            # Check for day names
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            for day in days:
                if day in message_lower:
                    data['date'] = day.capitalize()
                    break

        # Extract time
        time_pattern = r'(?:at\s+)?(\d{1,2})[:\.]?(\d{2})?\s*(am|pm)?'
        time_match = re.search(time_pattern, message_lower)
        if time_match:
            data['time'] = time_match.group(0).strip()

        return data

    def _extract_workout_data(self, message: str) -> Dict[str, Any]:
        """Extract workout-related data from message."""
        import re
        data = {}

        # Extract client name
        name_pattern = r'(?:send|share|give)\s+(?:\w+\s+)?(?:workout\s+)?(?:to\s+)?([A-Z][a-z]+)'
        match = re.search(name_pattern, message)
        if match:
            data['client_name'] = match.group(1)

        # Extract workout type
        workout_types = ['strength', 'cardio', 'hiit', 'yoga', 'full body', 'upper body', 'lower body']
        message_lower = message.lower()
        for wtype in workout_types:
            if wtype in message_lower:
                data['workout_type'] = wtype
                break

        return data

    def _extract_payment_data(self, message: str) -> Dict[str, Any]:
        """Extract payment-related data from message."""
        import re
        data = {}

        # Extract amount
        amount_pattern = r'R\s*(\d+(?:[,\s]\d{3})*(?:\.\d{2})?)'
        match = re.search(amount_pattern, message)
        if match:
            amount_str = match.group(1).replace(' ', '').replace(',', '')
            try:
                data['amount'] = float(amount_str)
            except ValueError:
                pass

        # Extract client name
        name_pattern = r'(?:from|charge|invoice)\s+([A-Z][a-z]+)'
        match = re.search(name_pattern, message)
        if match:
            data['client_name'] = match.group(1)

        return data

    def _extract_client_data(self, message: str) -> Dict[str, Any]:
        """Extract client-related data from message."""
        import re
        data = {}

        # Extract name
        name_patterns = [
            r'(?:add|new|register)\s+(?:client\s+)?([A-Z][a-z]+)',
            r'([A-Z][a-z]+)\s+(?:as\s+)?(?:a\s+)?(?:new\s+)?client',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, message)
            if match:
                data['client_name'] = match.group(1)
                break

        # Extract phone number
        phone_pattern = r'(?:0|\+27)\s*\d{2}\s*\d{3}\s*\d{4}'
        match = re.search(phone_pattern, message.replace(' ', ''))
        if match:
            data['phone'] = match.group(0)

        return data

    def _has_action_mapping(self, intent: str) -> bool:
        """
        Check if an intent has a corresponding action mapping.

        Args:
            intent: The detected intent name

        Returns:
            True if intent can be mapped to an action
        """
        return intent in self.INTENT_ACTION_MAP

    def _execute_intent_action(
        self,
        intent_result: IntentDetectionResult,
        context: Dict,
        phone: str
    ) -> Dict[str, Any]:
        """
        Execute an action for the detected intent.

        Args:
            intent_result: The detected intent with extracted data
            context: Context including user info
            phone: User's phone number

        Returns:
            Dictionary with action result
        """
        # Get user's role and ID
        user_type, user_id = self._get_user_role_and_id(phone, context)

        if not user_id:
            log_warning(f"Could not determine user for phone {phone}")
            return {
                'success': False,
                'message': "I couldn't identify your account. Please try again or contact support.",
                'action_taken': False,
            }

        # Look up action for intent
        mapped_intent = self.INTENT_ACTION_MAP.get(intent_result.intent)
        if not mapped_intent:
            log_warning(f"No action mapping for intent '{intent_result.intent}'")
            return self._generate_conversational_response(intent_result, context, phone)

        log_info(f"Routing intent '{intent_result.intent}' -> '{mapped_intent}' for {user_type.value} {user_id}")

        # Execute action handler via router
        try:
            result = self._action_router.route_intent(
                phone=phone,
                user_id=user_id,
                user_type=user_type,
                intent=mapped_intent,
                confidence=intent_result.confidence,
                message=context.get('original_message', ''),
                entities_from_ai=intent_result.extracted_data,
            )

            return {
                'success': result.success,
                'message': result.response_message,
                'action_taken': True,
                'intent': result.intent,
                'category': result.category.value,
                'task_started': result.task_started,
                'task_type': result.task_type,
                'extracted_entities': result.entities.to_dict(),
                'handler_result': result.handler_result,
            }

        except Exception as e:
            log_error(f"Error executing intent action: {e}")
            return {
                'success': False,
                'message': "Something went wrong. Please try again.",
                'action_taken': False,
                'error': str(e),
            }

    def _get_user_role_and_id(
        self,
        phone: str,
        context: Dict
    ) -> Tuple[UserType, Optional[str]]:
        """
        Determine user's role and ID from phone number.

        Args:
            phone: User's phone number
            context: Context that may contain user info

        Returns:
            Tuple of (UserType, user_id) or (UserType.CLIENT, None) if not found
        """
        # Check if role/ID provided in context
        if context.get('user_type') and context.get('user_id'):
            user_type = UserType(context['user_type']) if isinstance(
                context['user_type'], str
            ) else context['user_type']
            return user_type, context['user_id']

        # Look up in database
        try:
            # Check if trainer
            trainer = self.db.get_trainer_by_phone(phone)
            if trainer:
                return UserType.TRAINER, trainer.get('id') or trainer.get('trainer_id')

            # Check if client
            client = self.db.get_client_by_phone(phone)
            if client:
                return UserType.CLIENT, client.get('id') or client.get('client_id')

        except Exception as e:
            log_error(f"Error looking up user by phone: {e}")

        # Default to client if not found
        return UserType.CLIENT, None

    def _generate_conversational_response(
        self,
        intent_result: IntentDetectionResult,
        context: Dict,
        phone: str
    ) -> Dict[str, Any]:
        """
        Generate a conversational response for non-actionable intents.

        Args:
            intent_result: The detected intent
            context: Context for personalization
            phone: User's phone number

        Returns:
            Dictionary with conversational response
        """
        import random

        intent = intent_result.intent
        responses = self.CONVERSATIONAL_RESPONSES.get(
            intent, self.CONVERSATIONAL_RESPONSES['unknown']
        )

        # Pick a random response for variety
        response = random.choice(responses)

        # Personalize if we have user info
        user_name = context.get('user_name')
        if user_name and '{name}' in response:
            response = response.replace('{name}', user_name)

        return {
            'success': True,
            'message': response,
            'action_taken': False,
            'intent': intent,
            'confidence': intent_result.confidence,
            'conversational': True,
        }


# Singleton instance
_ai_intent_handler_instance = None


def get_ai_intent_handler(
    db=None,
    whatsapp=None,
    task_service=None,
    payment_manager=None,
    ai_client=None
) -> Optional[AIIntentHandler]:
    """
    Get or create the AI intent handler singleton.

    Args:
        db: Database service instance (required on first call)
        whatsapp: WhatsApp notifier instance (required on first call)
        task_service: Task service instance (required on first call)
        payment_manager: Optional payment manager instance
        ai_client: Optional AI client for intent detection

    Returns:
        AIIntentHandler instance or None if dependencies not provided
    """
    global _ai_intent_handler_instance

    if _ai_intent_handler_instance is None:
        if db is None or whatsapp is None or task_service is None:
            log_error("AIIntentHandler requires db, whatsapp, and task_service on first call")
            return None
        _ai_intent_handler_instance = AIIntentHandler(
            db, whatsapp, task_service, payment_manager, ai_client
        )

    return _ai_intent_handler_instance
