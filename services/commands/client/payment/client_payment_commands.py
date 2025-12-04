"""
Client Payment Command Handlers for Refiloe WhatsApp Assistant
Handles client-side payment operations including viewing payments and configuring auto-pay
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pytz

from utils.logger import log_info, log_error, log_warning

SA_TZ = pytz.timezone('Africa/Johannesburg')


def format_rand(amount: float) -> str:
    """Format amount as South African Rand."""
    return f"R{amount:,.2f}"


def _get_payment_status_display(status: str, created_at: str) -> str:
    """Get display text for payment status, including overdue detection."""
    if status == 'completed':
        return 'Paid'
    elif status == 'pending':
        # Check if overdue (more than 7 days old)
        try:
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.now(SA_TZ)
            if created.tzinfo is None:
                created = SA_TZ.localize(created)
            else:
                created = created.astimezone(SA_TZ)

            days_old = (now - created).days
            if days_old > 7:
                return 'Overdue'
        except Exception:
            pass
        return 'Pending'
    elif status == 'rejected':
        return 'Declined'
    else:
        return status.title()


# =========================================================================
# CHECK PAYMENTS COMMAND
# =========================================================================

def handle_check_payments(phone: str, client_id: str, db, whatsapp) -> Dict:
    """
    View pending payment requests for the client.

    Shows all pending and overdue payment requests from trainers,
    displaying trainer name, amount, and status.

    Args:
        phone: Client's phone number
        client_id: Client's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance

    Returns:
        Dictionary with success status and payment data
    """
    try:
        log_info(f"Checking payments for client {client_id}")

        # Get pending payment requests for this client
        pending_payments = _get_client_payments_by_status(phone, 'pending', db)

        if not pending_payments:
            message = ("*My Payment Requests*\n\n"
                      "No pending payment requests.\n\n"
                      "You're all caught up!")

            result = whatsapp.send_message(phone, message)
            return {
                'success': True,
                'message': 'No pending payments',
                'pending_count': 0,
                'whatsapp_sent': result.get('success', False)
            }

        # Calculate totals
        total_pending = sum(p.get('amount', 0) for p in pending_payments)

        # Build message
        message = "*My Payment Requests*\n"
        message += "=" * 20 + "\n\n"
        message += f"*{len(pending_payments)} pending request(s)*\n"
        message += f"Total: {format_rand(total_pending)}\n\n"

        for idx, payment in enumerate(pending_payments[:10], 1):
            trainer_name = _get_trainer_name(payment.get('trainer_id'), db)
            amount = format_rand(payment.get('amount', 0))
            status = _get_payment_status_display(
                payment.get('status', 'pending'),
                payment.get('created_at', '')
            )
            description = payment.get('description', 'Training session')
            created = payment.get('created_at', '')[:10]

            message += f"*{idx}. {trainer_name}*\n"
            message += f"   Amount: {amount}\n"
            message += f"   For: {description}\n"
            message += f"   Status: {status}\n"
            message += f"   Date: {created}\n\n"

        if len(pending_payments) > 10:
            message += f"... and {len(pending_payments) - 10} more\n\n"

        message += "-" * 20
        message += "\nReply 'pay' to make a payment"

        result = whatsapp.send_message(phone, message)

        return {
            'success': True,
            'message': 'Pending payments sent',
            'pending_count': len(pending_payments),
            'total_pending': total_pending,
            'whatsapp_sent': result.get('success', False)
        }

    except Exception as e:
        log_error(f"Error in handle_check_payments for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error checking payments: {str(e)}',
            'whatsapp_sent': False
        }


# =========================================================================
# PAYMENT HISTORY COMMAND
# =========================================================================

def handle_payment_history(phone: str, client_id: str, db, whatsapp) -> Dict:
    """
    View payment history for the client.

    Shows recent completed and pending payments with trainer names,
    amounts, and payment status.

    Args:
        phone: Client's phone number
        client_id: Client's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance

    Returns:
        Dictionary with success status and payment history
    """
    try:
        log_info(f"Getting payment history for client {client_id}")

        # Get all recent payments for this client
        all_payments = _get_client_payment_history(phone, db, limit=15)

        if not all_payments:
            message = ("*Payment History*\n\n"
                      "No payment history found.\n\n"
                      "Your payments will appear here once you receive "
                      "payment requests from your trainer.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': True,
                'message': 'No payment history',
                'payment_count': 0,
                'whatsapp_sent': result.get('success', False)
            }

        # Separate by status
        paid_payments = [p for p in all_payments if p.get('status') == 'completed']
        pending_payments = [p for p in all_payments if p.get('status') == 'pending']

        # Calculate totals
        total_paid = sum(p.get('amount', 0) for p in paid_payments)
        total_pending = sum(p.get('amount', 0) for p in pending_payments)

        # Build message
        message = "*Payment History*\n"
        message += "=" * 20 + "\n\n"

        # Summary
        message += "*Summary:*\n"
        message += f"Total Paid: {format_rand(total_paid)}\n"
        if total_pending > 0:
            message += f"Outstanding: {format_rand(total_pending)}\n"
        message += "\n"

        # Recent payments
        message += "*Recent Transactions:*\n\n"

        for payment in all_payments[:10]:
            trainer_name = _get_trainer_name(payment.get('trainer_id'), db)
            amount = format_rand(payment.get('amount', 0))
            status = _get_payment_status_display(
                payment.get('status', 'pending'),
                payment.get('created_at', '')
            )
            description = payment.get('description', 'Training session')

            # Use paid_at date for completed, created_at for pending
            if payment.get('status') == 'completed' and payment.get('paid_at'):
                date = payment.get('paid_at', '')[:10]
            else:
                date = payment.get('created_at', '')[:10]

            # Status indicator
            if status == 'Paid':
                status_icon = '[PAID]'
            elif status == 'Overdue':
                status_icon = '[OVERDUE]'
            else:
                status_icon = '[PENDING]'

            message += f"{status_icon} {trainer_name}\n"
            message += f"  {amount} - {description}\n"
            message += f"  {date}\n\n"

        if len(all_payments) > 10:
            message += f"... showing 10 of {len(all_payments)} payments\n"

        result = whatsapp.send_message(phone, message)

        return {
            'success': True,
            'message': 'Payment history sent',
            'payment_count': len(all_payments),
            'total_paid': total_paid,
            'total_pending': total_pending,
            'whatsapp_sent': result.get('success', False)
        }

    except Exception as e:
        log_error(f"Error in handle_payment_history for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error getting payment history: {str(e)}',
            'whatsapp_sent': False
        }


# =========================================================================
# AUTO-PAYMENT SETTINGS COMMAND
# =========================================================================

def handle_auto_payment_settings(phone: str, client_id: str, db, whatsapp, task_service) -> Dict:
    """
    Configure auto-pay settings for the client.

    Initiates a multi-step flow to configure automatic payment settings
    including enabling/disabling auto-pay and setting payment limits.

    Args:
        phone: Client's phone number
        client_id: Client's ID
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status
    """
    try:
        log_info(f"Starting auto-payment settings for client {client_id}")

        # Check if already has an active task
        if task_service.has_active_task(phone, 'auto_payment_settings'):
            message = ("You already have auto-pay setup in progress!\n\n"
                      "Please complete it or type 'cancel' to start over.")

            result = whatsapp.send_message(phone, message)
            return {
                'success': False,
                'message': 'Auto-pay setup already in progress',
                'whatsapp_sent': result.get('success', False)
            }

        # Get current settings
        current_settings = _get_client_payment_settings(phone, db)

        # Start task
        task_service.start_task(phone, 'auto_payment_settings', {
            'client_id': client_id,
            'step': 'select_option',
            'current_settings': current_settings
        })

        # Build message
        message = "*Auto-Pay Settings*\n"
        message += "=" * 20 + "\n\n"

        if current_settings:
            auto_pay_enabled = current_settings.get('auto_pay_enabled', False)
            auto_pay_limit = current_settings.get('auto_pay_limit')

            message += "*Current Settings:*\n"
            message += f"Auto-pay: {'Enabled' if auto_pay_enabled else 'Disabled'}\n"
            if auto_pay_limit:
                message += f"Max amount: {format_rand(auto_pay_limit)}\n"
            message += "\n"
        else:
            message += "Auto-pay is currently disabled.\n\n"

        message += "What would you like to do?\n\n"
        message += "1. Enable auto-pay\n"
        message += "2. Disable auto-pay\n"
        message += "3. Set payment limit\n"
        message += "4. Exit\n\n"
        message += "Reply with your choice:"

        result = whatsapp.send_message(phone, message)

        if result.get('success'):
            log_info(f"Auto-payment settings flow started for {phone}")
            return {
                'success': True,
                'message': 'Auto-pay settings flow started',
                'task_started': True,
                'whatsapp_sent': True
            }
        else:
            log_error(f"Failed to send message to {phone}: {result.get('error')}")
            task_service.cancel_task(phone, 'auto_payment_settings')
            return {
                'success': False,
                'message': 'Failed to send message',
                'whatsapp_sent': False,
                'error': result.get('error')
            }

    except Exception as e:
        log_error(f"Error in handle_auto_payment_settings for {phone}: {str(e)}")
        return {
            'success': False,
            'message': f'Error starting auto-pay settings: {str(e)}',
            'whatsapp_sent': False
        }


def handle_auto_payment_settings_step(phone: str, task: Dict, user_input: str,
                                       db, whatsapp, task_service) -> Dict:
    """
    Handle each step of the auto-payment settings flow.

    Args:
        phone: Client's phone number
        task: Current task data
        user_input: User's message input
        db: Database service instance
        whatsapp: WhatsApp notifier instance
        task_service: Task service for multi-step flows

    Returns:
        Dictionary with success status
    """
    # Check for cancel
    if user_input.lower().strip() in ['cancel', 'exit', 'quit', 'stop', '4']:
        return _cancel_flow(phone, 'auto_payment_settings', task_service, whatsapp)

    step = task['data'].get('step', 'select_option')

    if step == 'select_option':
        return _auto_pay_select_option(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'set_limit':
        return _auto_pay_set_limit(phone, task, user_input, db, whatsapp, task_service)
    elif step == 'confirm_enable':
        return _auto_pay_confirm_enable(phone, task, user_input, db, whatsapp, task_service)
    else:
        return {'success': False, 'message': f'Unknown step: {step}', 'handled': False}


def _auto_pay_select_option(phone: str, task: Dict, user_input: str,
                             db, whatsapp, task_service) -> Dict:
    """Handle option selection in auto-pay settings."""
    choice = user_input.strip()

    if choice == '1':
        # Enable auto-pay - ask for confirmation
        task_service.update_task(phone, 'auto_payment_settings', {
            'step': 'confirm_enable',
            'action': 'enable'
        })
        task_service.advance_step(phone, 'auto_payment_settings')

        current_settings = task['data'].get('current_settings', {})
        limit = current_settings.get('auto_pay_limit') if current_settings else None

        message = "*Enable Auto-Pay*\n\n"
        message += "When enabled, payment requests from your trainer "
        message += "will be automatically processed.\n\n"

        if limit:
            message += f"Current limit: {format_rand(limit)}\n"
            message += "(Payments above this amount will require manual approval)\n\n"
        else:
            message += "No payment limit set - all payments will auto-process.\n\n"

        message += "Confirm enabling auto-pay?\n\n"
        message += "1. Yes, enable\n"
        message += "2. No, go back"

        whatsapp.send_message(phone, message)
        return {'success': True, 'handled': True}

    elif choice == '2':
        # Disable auto-pay
        client_id = task['data'].get('client_id')
        success = _update_client_payment_settings(phone, {'auto_pay_enabled': False}, db)

        if success:
            task_service.complete_task(phone, 'auto_payment_settings')
            whatsapp.send_message(phone,
                "Auto-pay has been disabled.\n\n"
                "You will need to manually approve all payment requests.")
            log_info(f"Auto-pay disabled for client {phone}")
            return {'success': True, 'message': 'Auto-pay disabled', 'handled': True}
        else:
            whatsapp.send_message(phone, "Failed to update settings. Please try again.")
            return {'success': False, 'handled': True}

    elif choice == '3':
        # Set payment limit
        task_service.update_task(phone, 'auto_payment_settings', {'step': 'set_limit'})
        task_service.advance_step(phone, 'auto_payment_settings')

        message = ("*Set Auto-Pay Limit*\n\n"
                  "Enter the maximum amount that can be auto-paid:\n"
                  "(e.g., 500 or R500)\n\n"
                  "Payments above this amount will require your approval.")

        whatsapp.send_message(phone, message)
        return {'success': True, 'handled': True}

    else:
        whatsapp.send_message(phone, "Please select 1, 2, 3, or 4.")
        return {'success': False, 'handled': True}


def _auto_pay_set_limit(phone: str, task: Dict, user_input: str,
                         db, whatsapp, task_service) -> Dict:
    """Handle setting auto-pay limit."""
    # Parse amount
    clean_input = user_input.strip().upper().replace('R', '').replace(',', '').replace(' ', '')

    try:
        limit = float(clean_input)
    except ValueError:
        whatsapp.send_message(phone, "Invalid amount. Please enter a number (e.g., 500 or R500).")
        return {'success': False, 'handled': True}

    if limit <= 0:
        whatsapp.send_message(phone, "Amount must be greater than zero.")
        return {'success': False, 'handled': True}

    if limit > 10000:
        whatsapp.send_message(phone, "Limit cannot exceed R10,000. Please enter a valid amount.")
        return {'success': False, 'handled': True}

    # Update settings
    success = _update_client_payment_settings(phone, {'auto_pay_limit': limit}, db)

    if success:
        task_service.complete_task(phone, 'auto_payment_settings')
        whatsapp.send_message(phone,
            f"Auto-pay limit set to {format_rand(limit)}!\n\n"
            f"Payments up to {format_rand(limit)} will be auto-processed.\n"
            "Larger amounts will require your approval.")
        log_info(f"Auto-pay limit set to {limit} for client {phone}")
        return {'success': True, 'message': 'Limit set', 'handled': True}
    else:
        whatsapp.send_message(phone, "Failed to save limit. Please try again.")
        return {'success': False, 'handled': True}


def _auto_pay_confirm_enable(phone: str, task: Dict, user_input: str,
                              db, whatsapp, task_service) -> Dict:
    """Handle confirming auto-pay enablement."""
    choice = user_input.strip().lower()

    if choice in ['1', 'yes', 'y', 'enable']:
        # Enable auto-pay
        success = _update_client_payment_settings(phone, {'auto_pay_enabled': True}, db)

        if success:
            task_service.complete_task(phone, 'auto_payment_settings')
            whatsapp.send_message(phone,
                "Auto-pay has been enabled!\n\n"
                "Payment requests from your trainer will be "
                "automatically processed.")
            log_info(f"Auto-pay enabled for client {phone}")
            return {'success': True, 'message': 'Auto-pay enabled', 'handled': True}
        else:
            whatsapp.send_message(phone, "Failed to enable auto-pay. Please try again.")
            return {'success': False, 'handled': True}

    elif choice in ['2', 'no', 'n', 'back']:
        # Go back to options
        task_service.update_task(phone, 'auto_payment_settings', {'step': 'select_option'})

        message = "What would you like to do?\n\n"
        message += "1. Enable auto-pay\n"
        message += "2. Disable auto-pay\n"
        message += "3. Set payment limit\n"
        message += "4. Exit\n\n"
        message += "Reply with your choice:"

        whatsapp.send_message(phone, message)
        return {'success': True, 'handled': True}

    else:
        whatsapp.send_message(phone, "Please reply with 1 (Yes) or 2 (No)")
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


def _get_trainer_name(trainer_id: str, db) -> str:
    """Get trainer's name by ID."""
    if not trainer_id:
        return 'Unknown Trainer'

    try:
        result = db.db.table('trainers').select('name').eq('id', trainer_id).execute()

        if result and hasattr(result, 'data') and result.data:
            return result.data[0].get('name', 'Unknown Trainer')
        return 'Unknown Trainer'
    except Exception as e:
        log_warning(f"Error fetching trainer name: {str(e)}")
        return 'Unknown Trainer'


def _get_client_payments_by_status(client_phone: str, status: str, db, limit: int = 20) -> List[Dict]:
    """Get payments for a client by status."""
    try:
        result = db.db.table('payment_requests').select(
            'id, trainer_id, amount, description, status, created_at, paid_at, updated_at'
        ).eq(
            'client_phone', client_phone
        ).eq(
            'status', status
        ).order(
            'created_at', desc=True
        ).limit(limit).execute()

        if result and hasattr(result, 'data'):
            return result.data
        return []
    except Exception as e:
        log_warning(f"Error fetching client payments: {str(e)}")
        return []


def _get_client_payment_history(client_phone: str, db, limit: int = 15) -> List[Dict]:
    """Get all payment history for a client."""
    try:
        result = db.db.table('payment_requests').select(
            'id, trainer_id, amount, description, status, created_at, paid_at, updated_at'
        ).eq(
            'client_phone', client_phone
        ).order(
            'created_at', desc=True
        ).limit(limit).execute()

        if result and hasattr(result, 'data'):
            return result.data
        return []
    except Exception as e:
        log_warning(f"Error fetching payment history: {str(e)}")
        return []


def _get_client_payment_settings(client_phone: str, db) -> Optional[Dict]:
    """Get payment settings for a client."""
    try:
        result = db.db.table('client_settings').select(
            'auto_pay_enabled, auto_pay_limit'
        ).eq('phone', client_phone).execute()

        if result and hasattr(result, 'data') and result.data:
            return result.data[0]
        return None
    except Exception as e:
        log_warning(f"Error fetching client payment settings: {str(e)}")
        return None


def _update_client_payment_settings(client_phone: str, settings: Dict, db) -> bool:
    """Update payment settings for a client."""
    try:
        settings['updated_at'] = datetime.now(SA_TZ).isoformat()

        # Try update first
        result = db.db.table('client_settings').update(settings).eq(
            'phone', client_phone
        ).execute()

        if result and hasattr(result, 'data') and result.data:
            return True

        # If no rows updated, insert new record
        settings['phone'] = client_phone
        settings['created_at'] = datetime.now(SA_TZ).isoformat()
        insert_result = db.db.table('client_settings').insert(settings).execute()

        return insert_result and hasattr(insert_result, 'data') and insert_result.data

    except Exception as e:
        log_error(f"Error updating client payment settings: {str(e)}")
        return False
