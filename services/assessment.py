"""
Enhanced Assessment Service for Refiloe WhatsApp Assistant
Handles fitness assessment template management, sending assessments, and tracking responses
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pytz
import uuid
import secrets

from utils.logger import log_info, log_error, log_warning

SA_TZ = pytz.timezone('Africa/Johannesburg')

# Default assessment template
DEFAULT_ASSESSMENT_TEMPLATE = {
    'id': 'default',
    'name': 'Standard Fitness Assessment',
    'description': 'Comprehensive fitness evaluation covering goals, health history, and lifestyle',
    'sections': [
        {
            'title': 'Personal Goals',
            'questions': [
                'What are your primary fitness goals?',
                'What is your target timeline for achieving these goals?',
                'Have you worked with a trainer before?'
            ]
        },
        {
            'title': 'Health History',
            'questions': [
                'Do you have any injuries or health conditions?',
                'Are you currently taking any medications?',
                'Do you have any dietary restrictions or allergies?'
            ]
        },
        {
            'title': 'Current Fitness Level',
            'questions': [
                'How often do you currently exercise?',
                'What types of exercise do you enjoy?',
                'Rate your current fitness level (1-10)'
            ]
        },
        {
            'title': 'Lifestyle',
            'questions': [
                'How many hours of sleep do you get per night?',
                'How would you describe your daily activity level?',
                'How many meals do you eat per day?'
            ]
        }
    ]
}


class EnhancedAssessmentService:
    """
    Service for managing fitness assessments.

    Provides methods for:
    - Assessment template management
    - Sending assessments to clients
    - Tracking assessment status and responses
    - Generating secure access links
    """

    def __init__(self, db):
        """
        Initialize the assessment service.

        Args:
            db: Database service instance
        """
        self.db = db

    # =========================================================================
    # ASSESSMENT TEMPLATES
    # =========================================================================

    def get_assessment_templates(self, trainer_id: str, limit: int = 20) -> List[Dict]:
        """
        Get assessment templates for a trainer.

        Args:
            trainer_id: Trainer's ID
            limit: Maximum templates to return

        Returns:
            List of assessment template dictionaries
        """
        try:
            result = self.db.db.table('assessment_templates').select(
                'id, name, description, sections, created_at'
            ).eq('trainer_id', trainer_id).order(
                'created_at', desc=True
            ).limit(limit).execute()

            templates = []
            if result and hasattr(result, 'data') and result.data:
                templates = result.data

            # Always include the default template
            templates.insert(0, DEFAULT_ASSESSMENT_TEMPLATE)

            return templates

        except Exception as e:
            log_error(f"Error fetching assessment templates: {str(e)}")
            # Return default template on error
            return [DEFAULT_ASSESSMENT_TEMPLATE]

    def get_template_by_id(self, template_id: str) -> Optional[Dict]:
        """
        Get a single assessment template by ID.

        Args:
            template_id: Template UUID or 'default'

        Returns:
            Template dictionary or None
        """
        if template_id == 'default':
            return DEFAULT_ASSESSMENT_TEMPLATE

        try:
            result = self.db.db.table('assessment_templates').select('*').eq(
                'id', template_id
            ).execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error fetching template {template_id}: {str(e)}")
            return None

    def create_assessment_template(self, trainer_id: str, name: str,
                                    description: str, sections: List[Dict]) -> Optional[Dict]:
        """
        Create a new assessment template.

        Args:
            trainer_id: Trainer's ID
            name: Template name
            description: Template description
            sections: List of section dictionaries with questions

        Returns:
            Created template dictionary or None
        """
        try:
            template_data = {
                'id': str(uuid.uuid4()),
                'trainer_id': trainer_id,
                'name': name,
                'description': description,
                'sections': sections,
                'created_at': datetime.now(SA_TZ).isoformat(),
                'updated_at': datetime.now(SA_TZ).isoformat()
            }

            result = self.db.db.table('assessment_templates').insert(template_data).execute()

            if result and hasattr(result, 'data') and result.data:
                log_info(f"Created assessment template: {template_data['id']}")
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error creating assessment template: {str(e)}")
            return None

    # =========================================================================
    # SEND ASSESSMENTS
    # =========================================================================

    def create_assessment(self, trainer_id: str, client_id: str, client_phone: str,
                          client_name: str, template_id: str = 'default',
                          due_date: datetime = None) -> Optional[Dict]:
        """
        Create a new assessment for a client.

        Generates a secure access token for the client to complete the assessment
        via a web form.

        Args:
            trainer_id: Trainer's ID
            client_id: Client's ID
            client_phone: Client's phone number
            client_name: Client's name
            template_id: Assessment template ID (default: 'default')
            due_date: Optional due date for the assessment

        Returns:
            Created assessment dictionary with access token
        """
        try:
            # Generate secure access token
            access_token = secrets.token_urlsafe(32)

            # Set default due date (7 days from now)
            if not due_date:
                due_date = datetime.now(SA_TZ) + timedelta(days=7)

            # Get template
            template = self.get_template_by_id(template_id)
            if not template:
                template = DEFAULT_ASSESSMENT_TEMPLATE

            assessment_data = {
                'id': str(uuid.uuid4()),
                'trainer_id': trainer_id,
                'client_id': client_id,
                'client_phone': client_phone,
                'client_name': client_name,
                'template_id': template_id,
                'template_name': template.get('name', 'Fitness Assessment'),
                'access_token': access_token,
                'status': 'pending',
                'due_date': due_date.isoformat() if isinstance(due_date, datetime) else due_date,
                'created_at': datetime.now(SA_TZ).isoformat(),
                'sent_at': datetime.now(SA_TZ).isoformat(),
                'completed_at': None,
                'responses': None
            }

            result = self.db.db.table('assessments').insert(assessment_data).execute()

            if result and hasattr(result, 'data') and result.data:
                log_info(f"Created assessment for client {client_phone}: {assessment_data['id']}")
                return result.data[0]
            return assessment_data  # Return data even if insert had issues

        except Exception as e:
            log_error(f"Error creating assessment: {str(e)}")
            return None

    def get_assessment_link(self, access_token: str) -> str:
        """
        Generate the assessment link for a client.

        Args:
            access_token: The secure access token

        Returns:
            Full URL to the assessment form
        """
        return f"https://refiloe.africa/assessment/{access_token}"

    # =========================================================================
    # VIEW ASSESSMENTS
    # =========================================================================

    def get_trainer_assessments(self, trainer_id: str, status: str = None,
                                 limit: int = 20) -> List[Dict]:
        """
        Get all assessments for a trainer.

        Args:
            trainer_id: Trainer's ID
            status: Optional status filter ('pending', 'completed', 'expired')
            limit: Maximum assessments to return

        Returns:
            List of assessment dictionaries
        """
        try:
            query = self.db.db.table('assessments').select(
                'id, client_id, client_phone, client_name, template_name, '
                'status, due_date, created_at, sent_at, completed_at'
            ).eq('trainer_id', trainer_id)

            if status:
                query = query.eq('status', status)

            result = query.order('created_at', desc=True).limit(limit).execute()

            if result and hasattr(result, 'data'):
                return result.data
            return []

        except Exception as e:
            log_error(f"Error fetching trainer assessments: {str(e)}")
            return []

    def get_pending_assessments(self, trainer_id: str, limit: int = 20) -> List[Dict]:
        """
        Get pending assessments for a trainer.

        Args:
            trainer_id: Trainer's ID
            limit: Maximum assessments to return

        Returns:
            List of pending assessment dictionaries
        """
        return self.get_trainer_assessments(trainer_id, status='pending', limit=limit)

    def get_completed_assessments(self, trainer_id: str, limit: int = 20) -> List[Dict]:
        """
        Get completed assessments for a trainer.

        Args:
            trainer_id: Trainer's ID
            limit: Maximum assessments to return

        Returns:
            List of completed assessment dictionaries
        """
        return self.get_trainer_assessments(trainer_id, status='completed', limit=limit)

    def get_assessment_by_id(self, assessment_id: str) -> Optional[Dict]:
        """
        Get a single assessment by ID.

        Args:
            assessment_id: Assessment UUID

        Returns:
            Assessment dictionary or None
        """
        try:
            result = self.db.db.table('assessments').select('*').eq(
                'id', assessment_id
            ).execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error fetching assessment {assessment_id}: {str(e)}")
            return None

    def get_assessment_by_token(self, access_token: str) -> Optional[Dict]:
        """
        Get assessment by access token.

        Args:
            access_token: The secure access token

        Returns:
            Assessment dictionary or None
        """
        try:
            result = self.db.db.table('assessments').select('*').eq(
                'access_token', access_token
            ).execute()

            if result and hasattr(result, 'data') and result.data:
                return result.data[0]
            return None

        except Exception as e:
            log_error(f"Error fetching assessment by token: {str(e)}")
            return None

    # =========================================================================
    # ASSESSMENT STATUS
    # =========================================================================

    def get_assessment_stats(self, trainer_id: str) -> Dict:
        """
        Get assessment statistics for a trainer.

        Args:
            trainer_id: Trainer's ID

        Returns:
            Dictionary with statistics
        """
        try:
            all_assessments = self.get_trainer_assessments(trainer_id, limit=100)

            stats = {
                'total': len(all_assessments),
                'pending': 0,
                'completed': 0,
                'expired': 0,
                'overdue': 0
            }

            now = datetime.now(SA_TZ)

            for assessment in all_assessments:
                status = assessment.get('status', 'pending')
                stats[status] = stats.get(status, 0) + 1

                # Check for overdue
                if status == 'pending':
                    due_date_str = assessment.get('due_date')
                    if due_date_str:
                        try:
                            due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                            if due_date < now:
                                stats['overdue'] += 1
                        except (ValueError, TypeError):
                            pass

            return stats

        except Exception as e:
            log_error(f"Error getting assessment stats: {str(e)}")
            return {'total': 0, 'pending': 0, 'completed': 0, 'expired': 0, 'overdue': 0}

    def update_assessment_status(self, assessment_id: str, status: str,
                                  responses: Dict = None) -> bool:
        """
        Update assessment status (e.g., mark as completed).

        Args:
            assessment_id: Assessment UUID
            status: New status ('pending', 'completed', 'expired')
            responses: Optional client responses

        Returns:
            True if successful
        """
        try:
            updates = {
                'status': status,
                'updated_at': datetime.now(SA_TZ).isoformat()
            }

            if status == 'completed':
                updates['completed_at'] = datetime.now(SA_TZ).isoformat()

            if responses:
                updates['responses'] = responses

            result = self.db.db.table('assessments').update(updates).eq(
                'id', assessment_id
            ).execute()

            if result and hasattr(result, 'data'):
                log_info(f"Updated assessment {assessment_id} status to {status}")
                return True
            return False

        except Exception as e:
            log_error(f"Error updating assessment status: {str(e)}")
            return False

    # =========================================================================
    # CLIENT MESSAGES
    # =========================================================================

    def format_client_assessment_message(self, assessment: Dict, access_token: str) -> str:
        """
        Format the WhatsApp message to send to client with assessment link.

        Args:
            assessment: Assessment dictionary
            access_token: The access token for the link

        Returns:
            Formatted message string
        """
        template_name = assessment.get('template_name', 'Fitness Assessment')
        due_date_str = assessment.get('due_date', '')
        link = self.get_assessment_link(access_token)

        # Format due date
        due_display = ''
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                due_display = due_date.astimezone(SA_TZ).strftime('%d %B %Y')
            except (ValueError, TypeError):
                due_display = ''

        message = f"""Hi there! Your trainer has sent you a fitness assessment.

*{template_name}*

Please complete this assessment to help your trainer create the perfect program for you.

Click here to start:
{link}

"""
        if due_display:
            message += f"Please complete by: *{due_display}*\n\n"

        message += """This should take about 5-10 minutes. Your responses will help us understand your goals and create a personalized fitness plan.

Thank you!"""

        return message

    def format_assessment_summary(self, assessments: List[Dict]) -> str:
        """
        Format a summary of assessments for the trainer.

        Args:
            assessments: List of assessment dictionaries

        Returns:
            Formatted summary string
        """
        if not assessments:
            return "No assessments found."

        lines = ["*Your Assessments:*\n"]

        for idx, assessment in enumerate(assessments, 1):
            client_name = assessment.get('client_name', 'Unknown')
            status = assessment.get('status', 'pending')
            template_name = assessment.get('template_name', 'Assessment')

            # Status emoji
            status_emoji = {
                'pending': '⏳',
                'completed': '✅',
                'expired': '❌'
            }.get(status, '📋')

            lines.append(f"{idx}. {status_emoji} *{client_name}*")
            lines.append(f"   {template_name}")

            # Show relevant date based on status
            if status == 'completed':
                completed_at = assessment.get('completed_at', '')
                if completed_at:
                    try:
                        dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        lines.append(f"   Completed: {dt.astimezone(SA_TZ).strftime('%d %b %Y')}")
                    except (ValueError, TypeError):
                        pass
            else:
                due_date = assessment.get('due_date', '')
                if due_date:
                    try:
                        dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                        now = datetime.now(SA_TZ)
                        if dt < now:
                            lines.append(f"   *Overdue* (was due {dt.astimezone(SA_TZ).strftime('%d %b')})")
                        else:
                            lines.append(f"   Due: {dt.astimezone(SA_TZ).strftime('%d %b %Y')}")
                    except (ValueError, TypeError):
                        pass

            lines.append("")

        return "\n".join(lines)


# Singleton instance
_assessment_service_instance = None


def get_assessment_service(db=None) -> Optional[EnhancedAssessmentService]:
    """
    Get or create the assessment service singleton.

    Args:
        db: Database service instance (required on first call)

    Returns:
        EnhancedAssessmentService instance or None
    """
    global _assessment_service_instance

    if _assessment_service_instance is None:
        if db is None:
            log_error("EnhancedAssessmentService requires db on first call")
            return None
        _assessment_service_instance = EnhancedAssessmentService(db)

    return _assessment_service_instance
