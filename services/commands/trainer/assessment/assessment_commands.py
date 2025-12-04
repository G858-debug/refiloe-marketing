"""
Fitness Assessment Command Handlers for Refiloe WhatsApp Assistant
Handles sending assessments to clients, viewing assessments, and checking status
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pytz

from utils.logger import log_info, log_error, log_warning
from services.assessment import get_assessment_service, EnhancedAssessmentService

SA_TZ = pytz.timezone('Africa/Johannesburg')


def handle_send_assessment(phone: str, trainer_id: str, db, whatsapp, task_service) -> Dict:
    """
    Start the send assessment flow.

    This initiates a multi-step process:
    1. Select client
    2. Select template (or use default)
    3. Set due date (optional)
    4. Send link via WhatsApp

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
        log_info(f"Starting send_assessment flow for trainer {trainer_id}")

        # Check if already has an active task
        if task_service.has_active_task(phone, 'send_assessment'):
            message = ("📋 You already have an assessment in progress!\n\n"
                      "Please complete it or type 'cancel' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Assessment flow already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get trainer's clients
        clients = _get_trainer_clients(trainer_id, db)

        if not clients:
            message = ("📋 No clients found!\n\n"
                      "Add clients first before sending assessments.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'No clients available',
                'whatsapp_sent': result.get('success', False)
            }

        # Start the task
        task_service.start_task(phone, 'send_assessment', {
            'trainer_id': trainer_id,
            'step': 'select_client',
            'clients': clients
        })

        # Format client selection message
        message_parts = ["📋 *Send Fitness Assessment*\n\nSelect a client:\n"]

        for idx, client in enumerate(clients[:10], 1):
            name = client.get('name', 'Unknown')
            client_phone = client.get('phone', '')[-4:]
            message_parts.append(f"{idx}. {name} (...{client_phone})")

        message_parts.append("\n\nReply with the number or type 'cancel' to exit.")

        message = '\n'.join(message_parts)

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Send assessment flow started for {phone}")
            return {
                'success': True,
                'message': 'Send assessment flow initiated',
                'whatsapp_sent': True,
                'task_started': True
            }
        else:
            log_error(f"Failed to send message to {phone}: {result.get('error')}")
            task_service.cancel_task(phone, 'send_assessment')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_send_assessment for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting send assessment flow: {str(e)}',
            'whatsapp_sent': False
        }


def handle_send_assessment_step(phone: str, task: Dict, user_input: str,
                                 db, whatsapp, task_service) -> Dict:
    """
    Handle each step of the send_assessment flow.

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
        return _cancel_flow(phone, 'send_assessment', task_service, whatsapp)

    step = task['data'].get('step', 'select_client')

    if step == 'select_client':
        return _send_assessment_select_client(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'select_template':
        return _send_assessment_select_template(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'set_due_date':
        return _send_assessment_set_due_date(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'confirm':
        return _send_assessment_confirm(phone, task, user_input, db, whatsapp, task_service)
    else:
        return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}


def _send_assessment_select_client(phone: str, task: Dict, user_input: str,
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

    # Get assessment templates
    assessment_service = get_assessment_service(db)
    templates = assessment_service.get_assessment_templates(trainer_id)

    # Save client selection and move to template selection
    task_service.update_task(phone, 'send_assessment', {
        'client_id': selected_client.get('id'),
        'client_name': selected_client.get('name'),
        'client_phone': selected_client.get('phone'),
        'templates': templates,
        'step': 'select_template'
    })
    task_service.advance_step(phone, 'send_assessment')

    # Format template selection message
    message_parts = [f"Selected: *{selected_client.get('name')}*\n\n"]
    message_parts.append("📋 *Select Assessment Template:*\n")

    for idx, tmpl in enumerate(templates[:5], 1):
        name = tmpl.get('name', 'Unnamed')
        description = tmpl.get('description', '')[:50]
        if tmpl.get('id') == 'default':
            message_parts.append(f"{idx}. *{name}* (Recommended)")
        else:
            message_parts.append(f"{idx}. {name}")
        if description:
            message_parts.append(f"   _{description}_")

    message_parts.append("\n\nReply with the number:")

    message = '\n'.join(message_parts)
    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _send_assessment_select_template(phone: str, task: Dict, user_input: str,
                                      db, whatsapp, task_service) -> Dict:
    """Handle template selection step."""
    templates = task['data'].get('templates', [])

    # Validate selection
    if not user_input.isdigit():
        whatsapp.send_message(phone, "Please enter a number to select a template.")
        return {'success': False, 'handled': True}

    idx = int(user_input) - 1
    if idx < 0 or idx >= len(templates):
        whatsapp.send_message(phone, "Invalid selection. Please try again.")
        return {'success': False, 'handled': True}

    selected_template = templates[idx]

    # Save template selection and move to due date
    task_service.update_task(phone, 'send_assessment', {
        'template_id': selected_template.get('id'),
        'template_name': selected_template.get('name'),
        'step': 'set_due_date'
    })
    task_service.advance_step(phone, 'send_assessment')

    # Show due date options
    message = (f"Template: *{selected_template.get('name')}*\n\n"
              "When should the client complete this?\n\n"
              "1. In 3 days\n"
              "2. In 7 days (recommended)\n"
              "3. In 14 days\n"
              "4. No deadline\n\n"
              "Reply with the number:")

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _send_assessment_set_due_date(phone: str, task: Dict, user_input: str,
                                   db, whatsapp, task_service) -> Dict:
    """Handle due date setting step."""
    choice = user_input.strip()

    due_date = None
    due_display = "No deadline"

    if choice == '1':
        due_date = datetime.now(SA_TZ) + timedelta(days=3)
        due_display = due_date.strftime('%d %B %Y')
    elif choice == '2':
        due_date = datetime.now(SA_TZ) + timedelta(days=7)
        due_display = due_date.strftime('%d %B %Y')
    elif choice == '3':
        due_date = datetime.now(SA_TZ) + timedelta(days=14)
        due_display = due_date.strftime('%d %B %Y')
    elif choice == '4':
        due_date = None
        due_display = "No deadline"
    else:
        whatsapp.send_message(phone, "Please reply with 1, 2, 3, or 4")
        return {'success': False, 'handled': True}

    # Save due date and show confirmation
    task_service.update_task(phone, 'send_assessment', {
        'due_date': due_date.isoformat() if due_date else None,
        'due_display': due_display,
        'step': 'confirm'
    })
    task_service.advance_step(phone, 'send_assessment')

    # Show summary for confirmation
    task_data = task['data']
    client_name = task_data.get('client_name')
    template_name = task_data.get('template_name')

    message = ("*Review Assessment Details:*\n\n"
              f"Client: *{client_name}*\n"
              f"Template: *{template_name}*\n"
              f"Due: *{due_display}*\n\n"
              "─────────────────\n"
              "Send this assessment?\n\n"
              "1. Yes, send it!\n"
              "2. No, cancel")

    whatsapp.send_message(phone, message)

    return {'success': True, 'handled': True}


def _send_assessment_confirm(phone: str, task: Dict, user_input: str,
                              db, whatsapp, task_service) -> Dict:
    """Handle assessment send confirmation."""
    choice = user_input.strip().lower()

    if choice in ['1', 'yes', 'send', 'y']:
        task_data = task['data']
        trainer_id = task_data.get('trainer_id')
        client_id = task_data.get('client_id')
        client_phone = task_data.get('client_phone')
        client_name = task_data.get('client_name')
        template_id = task_data.get('template_id', 'default')
        due_date_str = task_data.get('due_date')

        # Parse due date
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str)
            except (ValueError, TypeError):
                due_date = datetime.now(SA_TZ) + timedelta(days=7)

        # Create the assessment
        assessment_service = get_assessment_service(db)
        assessment = assessment_service.create_assessment(
            trainer_id=trainer_id,
            client_id=client_id,
            client_phone=client_phone,
            client_name=client_name,
            template_id=template_id,
            due_date=due_date
        )

        if not assessment:
            whatsapp.send_message(phone, "Failed to create assessment. Please try again.")
            return {'success': False, 'handled': True}

        # Get access token and format client message
        access_token = assessment.get('access_token')
        client_message = assessment_service.format_client_assessment_message(assessment, access_token)

        # Send to client
        result = whatsapp.send_message(client_phone, client_message)

        if result.get('success'):
            # Complete task
            task_service.complete_task(phone, 'send_assessment')

            # Confirm to trainer
            assessment_link = assessment_service.get_assessment_link(access_token)
            whatsapp.send_message(phone,
                f"Assessment sent to *{client_name}*!\n\n"
                f"Link: {assessment_link}\n\n"
                "You'll be notified when they complete it.")

            log_info(f"Assessment sent to {client_phone} by trainer {trainer_id}")

            return {
                'success': True,
                'message': 'Assessment sent successfully',
                'assessment_id': assessment.get('id'),
                'handled': True
            }
        else:
            whatsapp.send_message(phone,
                f"Failed to send to {client_name}. Please try again.")
            return {'success': False, 'handled': True}

    elif choice in ['2', 'no', 'cancel', 'n']:
        return _cancel_flow(phone, 'send_assessment', task_service, whatsapp)

    else:
        whatsapp.send_message(phone, "Please reply with 1 (Yes) or 2 (No)")
        return {'success': False, 'handled': True}


def handle_view_assessments(phone: str, trainer_id: str, db, whatsapp) -> Dict:
    """
    View all assessments for a trainer.

    Args:
        phone: Trainer's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance

    Returns:
        Dictionary with success status and assessment count
    """
    try:
        log_info(f"Viewing assessments for trainer {trainer_id}")

        assessment_service = get_assessment_service(db)
        assessments = assessment_service.get_trainer_assessments(trainer_id, limit=15)

        if not assessments:
            message = ("📋 *Your Assessments*\n\n"
                      "No assessments sent yet!\n\n"
                      "Use 'send assessment' to send your first fitness assessment to a client.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': True,
                'message': 'No assessments found',
                'assessment_count': 0,
                'whatsapp_sent': result.get('success', False)
            }

        # Get stats
        stats = assessment_service.get_assessment_stats(trainer_id)

        # Format message
        message_parts = ["📋 *Your Assessments*\n"]

        # Add summary stats
        message_parts.append(f"Total: {stats['total']} | "
                           f"Pending: {stats['pending']} | "
                           f"Completed: {stats['completed']}")

        if stats['overdue'] > 0:
            message_parts.append(f"*{stats['overdue']} overdue*")

        message_parts.append("\n")

        # Format assessment list
        summary = assessment_service.format_assessment_summary(assessments)
        message_parts.append(summary)

        message_parts.append("─────────────────")
        message_parts.append("'send assessment' - Send new assessment")
        message_parts.append("'assessment status' - Check pending")

        message = '\n'.join(message_parts)

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Sent assessment list to {phone}")
            return {
                'success': True,
                'message': 'Assessment list sent',
                'assessment_count': len(assessments),
                'whatsapp_sent': True
            }
        else:
            return {
                'success': False,
                'message': 'Failed to send assessment list',
                'assessment_count': len(assessments),
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_view_assessments for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error viewing assessments: {str(e)}',
            'whatsapp_sent': False
        }


def handle_assessment_status(phone: str, trainer_id: str, db, whatsapp) -> Dict:
    """
    Check pending assessments status.

    Args:
        phone: Trainer's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance

    Returns:
        Dictionary with success status and pending count
    """
    try:
        log_info(f"Checking assessment status for trainer {trainer_id}")

        assessment_service = get_assessment_service(db)
        pending = assessment_service.get_pending_assessments(trainer_id, limit=10)
        stats = assessment_service.get_assessment_stats(trainer_id)

        if not pending:
            message = ("*Assessment Status*\n\n"
                      "No pending assessments!\n\n"
                      "All your clients have completed their assessments, "
                      "or you haven't sent any yet.\n\n"
                      "Use 'send assessment' to send a new one.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': True,
                'message': 'No pending assessments',
                'pending_count': 0,
                'whatsapp_sent': result.get('success', False)
            }

        # Format pending assessments
        message_parts = ["*Pending Assessments*\n"]

        if stats['overdue'] > 0:
            message_parts.append(f"*{stats['overdue']} overdue*\n")

        now = datetime.now(SA_TZ)

        for idx, assessment in enumerate(pending, 1):
            client_name = assessment.get('client_name', 'Unknown')
            template_name = assessment.get('template_name', 'Assessment')
            due_date_str = assessment.get('due_date', '')

            # Check if overdue
            is_overdue = False
            due_display = ''
            if due_date_str:
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                    due_sa = due_date.astimezone(SA_TZ)
                    due_display = due_sa.strftime('%d %b')
                    is_overdue = due_date < now
                except (ValueError, TypeError):
                    pass

            # Format entry
            if is_overdue:
                message_parts.append(f"{idx}. *{client_name}* (OVERDUE)")
            else:
                message_parts.append(f"{idx}. {client_name}")

            message_parts.append(f"   {template_name}")
            if due_display:
                message_parts.append(f"   Due: {due_display}")
            message_parts.append("")

        # Add action hints
        message_parts.append("─────────────────")
        message_parts.append("Tip: Send a reminder to clients who are overdue.")

        message = '\n'.join(message_parts)

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Sent assessment status to {phone}")
            return {
                'success': True,
                'message': 'Assessment status sent',
                'pending_count': len(pending),
                'overdue_count': stats['overdue'],
                'whatsapp_sent': True
            }
        else:
            return {
                'success': False,
                'message': 'Failed to send assessment status',
                'pending_count': len(pending),
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_assessment_status for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error checking assessment status: {str(e)}',
            'whatsapp_sent': False
        }


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def _cancel_flow(phone: str, task_type: str, task_service, whatsapp) -> Dict:
    """Cancel the current flow."""
    task_service.cancel_task(phone, task_type)
    whatsapp.send_message(phone, "Cancelled. What would you like to do?")
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
