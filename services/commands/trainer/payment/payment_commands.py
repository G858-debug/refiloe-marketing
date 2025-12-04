"""
Payment Command Handlers for Refiloe WhatsApp Assistant
Handles payment operations including requesting payments, viewing status, and payment setup
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pytz
import uuid

from utils.logger import log_info, log_error, log_warning

SA_TZ = pytz.timezone('Africa/Johannesburg')


def format_rand(amount: float) -> str:
    """Format amount as South African Rand."""
    return f"R{amount:,.2f}"


# =========================================================================
# REQUEST PAYMENT COMMAND
# =========================================================================

def handle_request_payment(phone: str, trainer_id: str, db, whatsapp, task_service, payment_manager=None) -> Dict:
    """
    Start the payment request flow.

    This initiates a multi-step process:
    1. Select client
    2. Enter amount or select session
    3. Add description (optional)
    4. Confirm and send payment request

    Args:
        phone: Trainer's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows
        payment_manager: Payment manager instance for processing payments

    Returns:
        Dictionary with success status and message
    """
    try:
        log_info(f"Starting request_payment flow for trainer {trainer_id}")

        # Check if already has an active task
        if task_service.has_active_task(phone, 'request_payment'):
            message = ("You already have a payment request in progress!\n\n"
                      "Please complete it or type 'cancel' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Payment request flow already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get trainer's clients
        clients = _get_trainer_clients(trainer_id, db)

        if not clients:
            message = ("No clients found!\n\n"
                      "Add clients first before requesting payments.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'No clients available',
                'whatsapp_sent': result.get('success', False)
            }

        # Start the task
        task_service.start_task(phone, 'request_payment', {
            'trainer_id': trainer_id,
            'step': 'select_client',
            'clients': clients
        })

        # Format client selection message
        message_parts = ["*Request Payment*\n\nSelect a client:\n"]

        for idx, client in enumerate(clients[:10], 1):
            name = client.get('name', 'Unknown')
            client_phone = client.get('phone', '')[-4:]
            message_parts.append(f"{idx}. {name} (...{client_phone})")

        message_parts.append("\n\nReply with the number or type 'cancel' to exit.")

        message = '\n'.join(message_parts)

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Request payment flow started for {phone}")
            return {
                'success': True,
                'message': 'Request payment flow initiated',
                'whatsapp_sent': True,
                'task_started': True
            }
        else:
            log_error(f"Failed to send message to {phone}: {result.get('error')}")
            task_service.cancel_task(phone, 'request_payment')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_request_payment for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting request payment flow: {str(e)}',
            'whatsapp_sent': False
        }


def handle_request_payment_step(phone: str, task: Dict, user_input: str,
                                 db, whatsapp, task_service, payment_manager=None) -> Dict:
    """
    Handle each step of the request_payment flow.

    Args:
        phone: Trainer's phone number
        task: Current task data
        user_input: User's message input
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows
        payment_manager: Payment manager instance

    Returns:
        Dictionary with success status
    """
    # Check for cancel
    if user_input.lower().strip() in ['cancel', 'exit', 'quit', 'stop']:
        return _cancel_flow(phone, 'request_payment', task_service, whatsapp)

    step = task['data'].get('step', 'select_client')

    if step == 'select_client':
        return _request_payment_select_client(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'enter_amount':
        return _request_payment_enter_amount(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'add_description':
        return _request_payment_add_description(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'confirm':
        return _request_payment_confirm(phone, task, user_input, db, whatsapp, task_service, payment_manager)
    else:
        return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}


def _request_payment_select_client(phone: str, task: Dict, user_input: str,
                                    db, whatsapp, task_service) -> Dict:
    """Handle client selection step."""
    clients = task['data'].get('clients', [])

    if not user_input.isdigit():
        whatsapp.send_message(phone, "Please enter a number to select a client.")
        return {'success': False, 'handled': True}

    idx = int(user_input) - 1
    if idx < 0 or idx >= len(clients):
        whatsapp.send_message(phone, "Invalid selection. Please try again.")
        return {'success': False, 'handled': True}

    selected_client = clients[idx]

    # Save client selection and move to amount entry
    task_service.update_task(phone, 'request_payment', {
        'client_id': selected_client.get('id'),
        'client_name': selected_client.get('name'),
        'client_phone': selected_client.get('phone'),
        'step': 'enter_amount'
    })
    task_service.advance_step(phone, 'request_payment')

    # Get unpaid sessions for quick selection
    trainer_id = task['data'].get('trainer_id')
    unpaid_sessions = _get_unpaid_sessions(trainer_id, selected_client.get('phone'), db)

    message = f"*Payment for {selected_client.get('name')}*\n\n"

    if unpaid_sessions:
        message += "Recent unpaid sessions:\n"
        for idx, session in enumerate(unpaid_sessions[:5], 1):
            session_type = session.get('session_type', 'Session').replace('_', ' ').title()
            price = format_rand(session.get('price', 0))
            date = session.get('session_datetime', '')[:10]
            message += f"\n{idx}. {session_type} - {price} ({date})"
        message += "\n\nReply with session number, or"

    message += "\n\nEnter custom amount (e.g., 350 or R350):"

    task_service.update_task(phone, 'request_payment', {
        'unpaid_sessions': unpaid_sessions
    })

    whatsapp.send_message(phone, message)
    return {'success': True, 'handled': True}


def _request_payment_enter_amount(phone: str, task: Dict, user_input: str,
                                   db, whatsapp, task_service) -> Dict:
    """Handle amount entry step."""
    unpaid_sessions = task['data'].get('unpaid_sessions', [])
    amount = None
    session_id = None
    description = None

    # Check if selecting from unpaid sessions
    if user_input.isdigit():
        idx = int(user_input) - 1
        if 0 <= idx < len(unpaid_sessions):
            session = unpaid_sessions[idx]
            amount = session.get('price', 0)
            session_id = session.get('id')
            session_type = session.get('session_type', 'Session').replace('_', ' ').title()
            date = session.get('session_datetime', '')[:10]
            description = f"{session_type} session on {date}"
        else:
            # It's a custom amount
            amount = float(user_input)
    else:
        # Parse amount from input (handle R prefix)
        clean_input = user_input.strip().upper().replace('R', '').replace(',', '').replace(' ', '')
        try:
            amount = float(clean_input)
        except ValueError:
            whatsapp.send_message(phone, "Invalid amount. Please enter a number (e.g., 350 or R350).")
            return {'success': False, 'handled': True}

    if amount <= 0:
        whatsapp.send_message(phone, "Amount must be greater than zero.")
        return {'success': False, 'handled': True}

    if amount > 50000:
        whatsapp.send_message(phone, "Amount cannot exceed R50,000. Please enter a valid amount.")
        return {'success': False, 'handled': True}

    # Save amount and move to description
    task_service.update_task(phone, 'request_payment', {
        'amount': amount,
        'session_id': session_id,
        'description': description,
        'step': 'add_description' if not description else 'confirm'
    })
    task_service.advance_step(phone, 'request_payment')

    if description:
        # Skip to confirmation
        return _show_payment_confirmation(phone, task, db, whatsapp, task_service)
    else:
        # Ask for description
        message = (f"Amount: {format_rand(amount)}\n\n"
                  "Add a description (optional):\n"
                  "(e.g., 'Personal training session' or type 'skip')")
        whatsapp.send_message(phone, message)
        return {'success': True, 'handled': True}


def _request_payment_add_description(phone: str, task: Dict, user_input: str,
                                      db, whatsapp, task_service) -> Dict:
    """Handle description entry step."""
    description = None

    if user_input.lower().strip() not in ['skip', 's', 'none', '-']:
        description = user_input.strip()[:200]  # Limit to 200 chars

    task_service.update_task(phone, 'request_payment', {
        'description': description or 'Training session payment',
        'step': 'confirm'
    })
    task_service.advance_step(phone, 'request_payment')

    return _show_payment_confirmation(phone, task, db, whatsapp, task_service)


def _show_payment_confirmation(phone: str, task: Dict, db, whatsapp, task_service) -> Dict:
    """Show payment request confirmation."""
    task_data = task_service.get_active_task(phone, 'request_payment')['data']

    message = ("*Confirm Payment Request:*\n\n"
              f"Client: {task_data.get('client_name')}\n"
              f"Amount: {format_rand(task_data.get('amount', 0))}\n"
              f"Description: {task_data.get('description', 'N/A')}\n\n"
              "Send this payment request?\n\n"
              "1. Yes, send it!\n"
              "2. No, cancel")

    whatsapp.send_message(phone, message)
    return {'success': True, 'handled': True}


def _request_payment_confirm(phone: str, task: Dict, user_input: str,
                              db, whatsapp, task_service, payment_manager) -> Dict:
    """Handle payment request confirmation."""
    choice = user_input.strip().lower()

    if choice in ['1', 'yes', 'send', 'y']:
        task_data = task['data']
        trainer_id = task_data.get('trainer_id')
        client_phone = task_data.get('client_phone')
        client_name = task_data.get('client_name')
        amount = task_data.get('amount')
        description = task_data.get('description', 'Training session payment')
        session_id = task_data.get('session_id')

        # Create payment record
        payment_id = str(uuid.uuid4())
        payment_record = {
            'id': payment_id,
            'trainer_id': trainer_id,
            'client_phone': client_phone,
            'amount': amount,
            'description': description,
            'session_id': session_id,
            'status': 'pending',
            'created_at': datetime.now(SA_TZ).isoformat(),
            'updated_at': datetime.now(SA_TZ).isoformat()
        }

        try:
            result = db.db.table('payment_requests').insert(payment_record).execute()

            if result and hasattr(result, 'data') and result.data:
                # Complete task
                task_service.complete_task(phone, 'request_payment')

                # Send payment request to client
                client_message = (f"*Payment Request*\n\n"
                                 f"Amount: {format_rand(amount)}\n"
                                 f"For: {description}\n\n"
                                 "Reply 'pay' to make payment or contact your trainer for questions.")

                whatsapp.send_message(client_phone, client_message)

                # Confirm to trainer
                whatsapp.send_message(phone,
                    f"Payment request sent to {client_name}!\n\n"
                    f"Amount: {format_rand(amount)}\n"
                    f"Status: Pending\n\n"
                    "You'll be notified when they pay.")

                log_info(f"Payment request created: {payment_id} for {format_rand(amount)}")

                return {
                    'success': True,
                    'message': 'Payment request sent',
                    'payment_id': payment_id,
                    'handled': True
                }
            else:
                raise Exception("Failed to create payment request")

        except Exception as e:
            log_error(f"Error creating payment request: {str(e)}")
            whatsapp.send_message(phone, "Failed to send payment request. Please try again.")
            return {'success': False, 'handled': True}

    elif choice in ['2', 'no', 'cancel', 'n']:
        return _cancel_flow(phone, 'request_payment', task_service, whatsapp)

    else:
        whatsapp.send_message(phone, "Please reply with 1 (Yes) or 2 (No)")
        return {'success': False, 'handled': True}


# =========================================================================
# VIEW PAYMENTS COMMAND
# =========================================================================

def handle_view_payments(phone: str, trainer_id: str, db, whatsapp, payment_manager=None) -> Dict:
    """
    Show payment status and history for the trainer.

    Args:
        phone: Trainer's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        payment_manager: Payment manager instance

    Returns:
        Dictionary with success status and payment counts
    """
    try:
        log_info(f"Viewing payments for trainer {trainer_id}")

        # Get payment summary
        pending_payments = _get_payments_by_status(trainer_id, 'pending', db)
        completed_payments = _get_payments_by_status(trainer_id, 'completed', db, limit=5)

        # Calculate totals
        pending_total = sum(p.get('amount', 0) for p in pending_payments)
        completed_total = sum(p.get('amount', 0) for p in completed_payments)

        message = "*Payment Overview*\n"
        message += "=" * 20 + "\n\n"

        # Pending payments
        message += f"*Pending Payments: {len(pending_payments)}*\n"
        if pending_payments:
            message += f"Total Outstanding: {format_rand(pending_total)}\n\n"
            for p in pending_payments[:5]:
                client = p.get('client_phone', '')[-4:]
                amount = format_rand(p.get('amount', 0))
                created = p.get('created_at', '')[:10]
                message += f"- ...{client}: {amount} ({created})\n"
        else:
            message += "No pending payments\n"

        message += "\n"

        # Recent completed payments
        message += f"*Recent Payments Received:*\n"
        if completed_payments:
            message += f"Last 5 total: {format_rand(completed_total)}\n\n"
            for p in completed_payments[:5]:
                client = p.get('client_phone', '')[-4:]
                amount = format_rand(p.get('amount', 0))
                paid_at = p.get('paid_at', p.get('updated_at', ''))[:10]
                message += f"- ...{client}: {amount} ({paid_at})\n"
        else:
            message += "No payments received yet\n"

        message += "\n" + "-" * 20
        message += "\n'request payment' - Send new payment request"
        message += "\n'setup payment' - Configure payment settings"

        result = whatsapp.send_message(phone, message)

        return {
            'success': True,
            'message': 'Payment overview sent',
            'pending_count': len(pending_payments),
            'pending_total': pending_total,
            'whatsapp_sent': result.get('success', False)
        }

    except Exception as e:
        log_error(f"Error in handle_view_payments for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error viewing payments: {str(e)}',
            'whatsapp_sent': False
        }


# =========================================================================
# SETUP PAYMENT COMMAND
# =========================================================================

def handle_setup_payment(phone: str, trainer_id: str, db, whatsapp, task_service, payment_manager=None) -> Dict:
    """
    Start the payment setup flow for tokenization.

    This initiates setting up payment methods and preferences.

    Args:
        phone: Trainer's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows
        payment_manager: Payment manager instance

    Returns:
        Dictionary with success status
    """
    try:
        log_info(f"Starting payment setup for trainer {trainer_id}")

        if task_service.has_active_task(phone, 'setup_payment'):
            message = ("You already have payment setup in progress!\n\n"
                      "Please complete it or type 'cancel' to start over.")
            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Setup already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get current settings
        current_settings = _get_payment_settings(trainer_id, db)

        # Start task
        task_service.start_task(phone, 'setup_payment', {
            'trainer_id': trainer_id,
            'step': 'select_option',
            'current_settings': current_settings
        })

        message = "*Payment Setup*\n\n"

        if current_settings:
            payment_day = current_settings.get('payment_reminder_day', 'Not set')
            bank = current_settings.get('bank_name', 'Not configured')
            message += f"Current settings:\n"
            message += f"- Payment reminder day: {payment_day}\n"
            message += f"- Bank: {bank}\n\n"

        message += "What would you like to configure?\n\n"
        message += "1. Set payment reminder day\n"
        message += "2. Update bank details\n"
        message += "3. Configure payment link\n"
        message += "4. Exit setup\n\n"
        message += "Reply with your choice:"

        result = whatsapp.send_message(phone, message)

        return {
            'success': result.get('success', False),
            'message': 'Payment setup started',
            'task_started': True,
            'whatsapp_sent': result.get('success', False)
        }

    except Exception as e:
        log_error(f"Error in handle_setup_payment for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting payment setup: {str(e)}',
            'whatsapp_sent': False
        }


def handle_setup_payment_step(phone: str, task: Dict, user_input: str,
                               db, whatsapp, task_service, payment_manager=None) -> Dict:
    """
    Handle each step of the setup_payment flow.

    Args:
        phone: Trainer's phone number
        task: Current task data
        user_input: User's message input
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows
        payment_manager: Payment manager instance

    Returns:
        Dictionary with success status
    """
    if user_input.lower().strip() in ['cancel', 'exit', 'quit', 'stop', '4']:
        return _cancel_flow(phone, 'setup_payment', task_service, whatsapp)

    step = task['data'].get('step', 'select_option')

    if step == 'select_option':
        return _setup_payment_select_option(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'set_reminder_day':
        return _setup_payment_set_reminder_day(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'update_bank':
        return _setup_payment_update_bank(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'configure_link':
        return _setup_payment_configure_link(phone, task, user_input, db, whatsapp, task_service)
    else:
        return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}


def _setup_payment_select_option(phone: str, task: Dict, user_input: str,
                                  db, whatsapp, task_service) -> Dict:
    """Handle option selection in setup."""
    choice = user_input.strip()

    if choice == '1':
        task_service.update_task(phone, 'setup_payment', {'step': 'set_reminder_day'})
        task_service.advance_step(phone, 'setup_payment')

        message = ("*Set Payment Reminder Day*\n\n"
                  "On which day of the month should clients receive payment reminders?\n\n"
                  "Enter a day (1-28):")

        whatsapp.send_message(phone, message)
        return {'success': True, 'handled': True}

    elif choice == '2':
        task_service.update_task(phone, 'setup_payment', {'step': 'update_bank'})
        task_service.advance_step(phone, 'setup_payment')

        message = ("*Update Bank Details*\n\n"
                  "Enter your bank name:\n"
                  "(e.g., FNB, Standard Bank, Capitec)")

        whatsapp.send_message(phone, message)
        return {'success': True, 'handled': True}

    elif choice == '3':
        task_service.update_task(phone, 'setup_payment', {'step': 'configure_link'})
        task_service.advance_step(phone, 'setup_payment')

        message = ("*Configure Payment Link*\n\n"
                  "Enter your payment link URL:\n"
                  "(e.g., PayFast, Yoco, or SnapScan link)")

        whatsapp.send_message(phone, message)
        return {'success': True, 'handled': True}

    else:
        whatsapp.send_message(phone, "Please select 1, 2, 3, or 4.")
        return {'success': False, 'handled': True}


def _setup_payment_set_reminder_day(phone: str, task: Dict, user_input: str,
                                     db, whatsapp, task_service) -> Dict:
    """Handle setting payment reminder day."""
    try:
        day = int(user_input.strip())
        if day < 1 or day > 28:
            whatsapp.send_message(phone, "Please enter a day between 1 and 28.")
            return {'success': False, 'handled': True}
    except ValueError:
        whatsapp.send_message(phone, "Please enter a valid number (1-28).")
        return {'success': False, 'handled': True}

    trainer_id = task['data'].get('trainer_id')

    # Update settings
    success = _update_payment_settings(trainer_id, {'payment_reminder_day': day}, db)

    if success:
        task_service.complete_task(phone, 'setup_payment')
        whatsapp.send_message(phone,
            f"Payment reminder day set to day {day} of each month!\n\n"
            "Clients will receive reminders on this day.")
        return {'success': True, 'message': 'Reminder day set', 'handled': True}
    else:
        whatsapp.send_message(phone, "Failed to save settings. Please try again.")
        return {'success': False, 'handled': True}


def _setup_payment_update_bank(phone: str, task: Dict, user_input: str,
                                db, whatsapp, task_service) -> Dict:
    """Handle updating bank details."""
    bank_name = user_input.strip()[:50]

    if len(bank_name) < 2:
        whatsapp.send_message(phone, "Please enter a valid bank name.")
        return {'success': False, 'handled': True}

    trainer_id = task['data'].get('trainer_id')

    # Update settings
    success = _update_payment_settings(trainer_id, {'bank_name': bank_name}, db)

    if success:
        task_service.complete_task(phone, 'setup_payment')
        whatsapp.send_message(phone,
            f"Bank updated to {bank_name}!\n\n"
            "Your payment details have been saved.")
        return {'success': True, 'message': 'Bank updated', 'handled': True}
    else:
        whatsapp.send_message(phone, "Failed to save settings. Please try again.")
        return {'success': False, 'handled': True}


def _setup_payment_configure_link(phone: str, task: Dict, user_input: str,
                                   db, whatsapp, task_service) -> Dict:
    """Handle configuring payment link."""
    payment_link = user_input.strip()

    # Basic URL validation
    if not payment_link.startswith(('http://', 'https://')):
        whatsapp.send_message(phone, "Please enter a valid URL starting with http:// or https://")
        return {'success': False, 'handled': True}

    trainer_id = task['data'].get('trainer_id')

    # Update settings
    success = _update_payment_settings(trainer_id, {'payment_link': payment_link}, db)

    if success:
        task_service.complete_task(phone, 'setup_payment')
        whatsapp.send_message(phone,
            "Payment link configured!\n\n"
            "This link will be included in payment requests to clients.")
        return {'success': True, 'message': 'Payment link configured', 'handled': True}
    else:
        whatsapp.send_message(phone, "Failed to save settings. Please try again.")
        return {'success': False, 'handled': True}


# =========================================================================
# SET PAYMENT DAY COMMAND
# =========================================================================

def handle_set_payment_day(phone: str, trainer_id: str, db, whatsapp, task_service, payment_manager=None) -> Dict:
    """
    Start the set payment day flow.

    Quick command to set the monthly payment reminder day.

    Args:
        phone: Trainer's phone number
        trainer_id: Trainer's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows
        payment_manager: Payment manager instance

    Returns:
        Dictionary with success status
    """
    try:
        log_info(f"Starting set_payment_day flow for trainer {trainer_id}")

        if task_service.has_active_task(phone, 'set_payment_day'):
            message = ("You already have this flow in progress!\n\n"
                      "Please complete it or type 'cancel' to start over.")
            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Flow already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get current setting
        current_settings = _get_payment_settings(trainer_id, db)
        current_day = current_settings.get('payment_reminder_day') if current_settings else None

        # Start task
        task_service.start_task(phone, 'set_payment_day', {
            'trainer_id': trainer_id,
            'step': 'enter_day',
            'current_day': current_day
        })

        message = "*Set Payment Reminder Day*\n\n"

        if current_day:
            message += f"Current setting: Day {current_day}\n\n"

        message += "On which day of the month should clients receive payment reminders?\n\n"
        message += "Enter a day (1-28):"

        result = whatsapp.send_message(phone, message)

        return {
            'success': result.get('success', False),
            'message': 'Set payment day flow started',
            'task_started': True,
            'whatsapp_sent': result.get('success', False)
        }

    except Exception as e:
        log_error(f"Error in handle_set_payment_day for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting set payment day flow: {str(e)}',
            'whatsapp_sent': False
        }


def handle_set_payment_day_step(phone: str, task: Dict, user_input: str,
                                 db, whatsapp, task_service, payment_manager=None) -> Dict:
    """
    Handle the set payment day step.

    Args:
        phone: Trainer's phone number
        task: Current task data
        user_input: User's message input
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows
        payment_manager: Payment manager instance

    Returns:
        Dictionary with success status
    """
    if user_input.lower().strip() in ['cancel', 'exit', 'quit', 'stop']:
        return _cancel_flow(phone, 'set_payment_day', task_service, whatsapp)

    try:
        day = int(user_input.strip())
        if day < 1 or day > 28:
            whatsapp.send_message(phone, "Please enter a day between 1 and 28.")
            return {'success': False, 'handled': True}
    except ValueError:
        whatsapp.send_message(phone, "Please enter a valid number (1-28).")
        return {'success': False, 'handled': True}

    trainer_id = task['data'].get('trainer_id')

    # Update settings
    success = _update_payment_settings(trainer_id, {'payment_reminder_day': day}, db)

    if success:
        task_service.complete_task(phone, 'set_payment_day')
        whatsapp.send_message(phone,
            f"Payment reminder day set to day {day} of each month!\n\n"
            "Clients will receive automatic payment reminders on this day.")
        log_info(f"Payment reminder day set to {day} for trainer {trainer_id}")
        return {'success': True, 'message': 'Reminder day set', 'handled': True}
    else:
        whatsapp.send_message(phone, "Failed to save setting. Please try again.")
        return {'success': False, 'handled': True}


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
            'id, name, phone'
        ).eq('trainer_id', trainer_id).execute()

        if result and hasattr(result, 'data'):
            return result.data
        return []
    except Exception as e:
        log_error(f"Error fetching clients: {str(e)}")
        return []


def _get_unpaid_sessions(trainer_id: str, client_phone: str, db) -> List[Dict]:
    """Get unpaid sessions for a client."""
    try:
        now = datetime.now(SA_TZ)

        result = db.db.table('bookings').select(
            'id, session_datetime, session_type, price'
        ).eq(
            'trainer_id', trainer_id
        ).eq(
            'client_id', client_phone
        ).eq(
            'payment_status', 'unpaid'
        ).lte(
            'session_datetime', now.isoformat()
        ).order(
            'session_datetime', desc=True
        ).limit(5).execute()

        if result and hasattr(result, 'data'):
            return result.data
        return []
    except Exception as e:
        log_warning(f"Error fetching unpaid sessions: {str(e)}")
        return []


def _get_payments_by_status(trainer_id: str, status: str, db, limit: int = 10) -> List[Dict]:
    """Get payments by status for a trainer."""
    try:
        result = db.db.table('payment_requests').select(
            'id, client_phone, amount, description, status, created_at, paid_at, updated_at'
        ).eq(
            'trainer_id', trainer_id
        ).eq(
            'status', status
        ).order(
            'created_at', desc=True
        ).limit(limit).execute()

        if result and hasattr(result, 'data'):
            return result.data
        return []
    except Exception as e:
        log_warning(f"Error fetching payments: {str(e)}")
        return []


def _get_payment_settings(trainer_id: str, db) -> Optional[Dict]:
    """Get payment settings for a trainer."""
    try:
        result = db.db.table('trainer_settings').select(
            'payment_reminder_day, bank_name, payment_link'
        ).eq('trainer_id', trainer_id).execute()

        if result and hasattr(result, 'data') and result.data:
            return result.data[0]
        return None
    except Exception as e:
        log_warning(f"Error fetching payment settings: {str(e)}")
        return None


def _update_payment_settings(trainer_id: str, settings: Dict, db) -> bool:
    """Update payment settings for a trainer."""
    try:
        settings['updated_at'] = datetime.now(SA_TZ).isoformat()

        # Try update first
        result = db.db.table('trainer_settings').update(settings).eq(
            'trainer_id', trainer_id
        ).execute()

        if result and hasattr(result, 'data') and result.data:
            return True

        # If no rows updated, insert new record
        settings['trainer_id'] = trainer_id
        settings['created_at'] = datetime.now(SA_TZ).isoformat()
        insert_result = db.db.table('trainer_settings').insert(settings).execute()

        return insert_result and hasattr(insert_result, 'data') and insert_result.data

    except Exception as e:
        log_error(f"Error updating payment settings: {str(e)}")
        return False
