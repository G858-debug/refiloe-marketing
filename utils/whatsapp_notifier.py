"""
WhatsApp Notification Service for Refiloe Marketing
Uses Meta Cloud API to send notifications via WhatsApp
"""

import os
import re
import time
from typing import Dict, Optional
from datetime import datetime
import requests

from utils.logger import log_info, log_error, log_warning, SA_TZ


class WhatsAppNotifier:
    """
    WhatsApp notification service using Meta Cloud API
    """

    def __init__(self):
        """Initialize WhatsApp notifier with environment variables"""
        # Load environment variables
        self.phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
        self.api_token = os.getenv('WHATSAPP_API_TOKEN')
        self.notification_phone = os.getenv('NOTIFICATION_PHONE_NUMBER')
        self.enabled = os.getenv('ENABLE_WHATSAPP_NOTIFICATIONS', 'false').lower() == 'true'

        # Construct API URL
        api_url = os.getenv('WHATSAPP_API_URL')
        if api_url:
            self.api_url = api_url
        elif self.phone_number_id:
            self.api_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
        else:
            self.api_url = None

        # Validate credentials
        self._validate_credentials()

    def _validate_credentials(self):
        """Validate that required credentials are present"""
        if not self.enabled:
            log_info("WhatsApp notifications are disabled")
            return

        missing = []
        if not self.phone_number_id:
            missing.append('WHATSAPP_PHONE_NUMBER_ID')
        if not self.api_token:
            missing.append('WHATSAPP_API_TOKEN')
        if not self.notification_phone:
            missing.append('NOTIFICATION_PHONE_NUMBER')
        if not self.api_url:
            missing.append('WHATSAPP_API_URL or WHATSAPP_PHONE_NUMBER_ID')

        if missing:
            log_warning(f"WhatsApp notifications enabled but missing credentials: {', '.join(missing)}")
        else:
            log_info("WhatsApp notifier initialized successfully")

    def _format_phone_number(self, phone: str) -> str:
        """
        Format phone number to international format without +

        Args:
            phone: Phone number in any format

        Returns:
            Clean phone number string with country code
        """
        # Remove spaces, dashes, parentheses
        clean = re.sub(r'[\s\-\(\)]', '', phone)

        # Remove leading + if present
        clean = clean.lstrip('+')

        # If number doesn't start with country code, add 27 (South Africa)
        if not clean.startswith(('27', '1', '44', '61', '91')):  # Common country codes
            # If it starts with 0, remove it (SA mobile format)
            if clean.startswith('0'):
                clean = '27' + clean[1:]
            else:
                clean = '27' + clean

        return clean

    def send_message(self, to_number: str, message: str) -> Dict:
        """
        Send a WhatsApp message

        Args:
            to_number: Recipient phone number
            message: Message text to send

        Returns:
            Dictionary with success status, message_id, and error (if any)
        """
        # Check if notifications are enabled
        if not self.enabled:
            log_info("WhatsApp notifications disabled - skipping message send")
            return {
                'success': False,
                'message_id': None,
                'error': 'WhatsApp notifications are disabled'
            }

        # Validate credentials
        if not self.api_token or not self.api_url:
            log_error("WhatsApp credentials not configured")
            return {
                'success': False,
                'message_id': None,
                'error': 'WhatsApp credentials not configured'
            }

        # Format phone number
        formatted_phone = self._format_phone_number(to_number)

        # Handle message length (split if > 4096 chars)
        messages = []
        if len(message) > 4096:
            # Split into chunks
            for i in range(0, len(message), 4096):
                chunk = message[i:i+4096]
                messages.append(chunk)
            log_info(f"Message split into {len(messages)} parts due to length")
        else:
            messages.append(message)

        # Send all message parts
        results = []
        for idx, msg_text in enumerate(messages):
            result = self._send_single_message(formatted_phone, msg_text, idx + 1, len(messages))
            results.append(result)

            # If any message fails, return the failure
            if not result['success']:
                return result

        # Return the last successful result
        return results[-1] if results else {
            'success': False,
            'message_id': None,
            'error': 'No messages to send'
        }

    def _send_single_message(self, to_number: str, message: str, part: int = 1, total: int = 1) -> Dict:
        """
        Send a single WhatsApp message with retry logic

        Args:
            to_number: Formatted recipient phone number
            message: Message text to send
            part: Part number (for split messages)
            total: Total number of parts

        Returns:
            Dictionary with success status, message_id, and error (if any)
        """
        # Build payload
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message}
        }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        # Retry logic: 3 attempts with exponential backoff
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                log_info(f"Sending WhatsApp message to {to_number} (attempt {attempt}/{max_retries}, part {part}/{total})")

                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=30
                )

                if response.status_code == 200:
                    response_data = response.json()
                    message_id = response_data.get('messages', [{}])[0].get('id')
                    log_info(f"WhatsApp message sent successfully - ID: {message_id}")
                    return {
                        'success': True,
                        'message_id': message_id,
                        'error': None
                    }
                else:
                    error_msg = f"WhatsApp API error: {response.status_code} - {response.text}"
                    log_error(error_msg)

                    # Don't retry on client errors (4xx)
                    if 400 <= response.status_code < 500:
                        return {
                            'success': False,
                            'message_id': None,
                            'error': error_msg
                        }

                    # Retry on server errors (5xx)
                    if attempt < max_retries:
                        wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                        log_warning(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        return {
                            'success': False,
                            'message_id': None,
                            'error': error_msg
                        }

            except requests.exceptions.Timeout:
                error_msg = f"WhatsApp API timeout (attempt {attempt}/{max_retries})"
                log_error(error_msg)

                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    log_warning(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return {
                        'success': False,
                        'message_id': None,
                        'error': error_msg
                    }

            except requests.exceptions.RequestException as e:
                error_msg = f"WhatsApp API request failed: {str(e)}"
                log_error(error_msg)

                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    log_warning(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return {
                        'success': False,
                        'message_id': None,
                        'error': error_msg
                    }

            except Exception as e:
                error_msg = f"Unexpected error sending WhatsApp message: {str(e)}"
                log_error(error_msg)
                return {
                    'success': False,
                    'message_id': None,
                    'error': error_msg
                }

        # Should not reach here, but just in case
        return {
            'success': False,
            'message_id': None,
            'error': 'Max retries exceeded'
        }

    def send_weekly_report(self, report_text: str) -> Dict:
        """
        Send weekly report to notification phone number

        Args:
            report_text: Report content to send

        Returns:
            Dictionary with success status, message_id, and error (if any)
        """
        if not self.notification_phone:
            log_error("NOTIFICATION_PHONE_NUMBER not configured")
            return {
                'success': False,
                'message_id': None,
                'error': 'NOTIFICATION_PHONE_NUMBER not configured'
            }

        # Get current timestamp in SAST
        timestamp = datetime.now(SA_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')

        # Format report with header
        formatted_report = f"""📊 *Refiloe Marketing - Weekly Report*
{timestamp}

{report_text}

View full report: {os.getenv('DASHBOARD_URL', 'https://your-dashboard-url.com')}"""

        # Send message
        result = self.send_message(self.notification_phone, formatted_report)

        if result['success']:
            log_info("Weekly report sent successfully via WhatsApp")
        else:
            log_error(f"Failed to send weekly report: {result.get('error')}")

        return result

    def send_alert(self, alert_type: str, title: str, details: Dict) -> Dict:
        """
        Send an alert notification

        Args:
            alert_type: Type of alert ('success', 'warning', 'error', 'viral', 'milestone')
            title: Alert title
            details: Dictionary with alert details

        Returns:
            Dictionary with success status, message_id, and error (if any)
        """
        if not self.notification_phone:
            log_error("NOTIFICATION_PHONE_NUMBER not configured")
            return {
                'success': False,
                'message_id': None,
                'error': 'NOTIFICATION_PHONE_NUMBER not configured'
            }

        # Map alert types to emojis
        emoji_map = {
            'success': '✅',
            'warning': '⚠️',
            'error': '🚨',
            'viral': '🔥',
            'milestone': '🎉'
        }

        emoji = emoji_map.get(alert_type, '🔔')

        # Get current timestamp in SAST
        timestamp = datetime.now(SA_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')

        # Format details
        details_text = ""
        for key, value in details.items():
            details_text += f"\n• {key}: {value}"

        # Generate actionable next steps based on alert type
        next_steps = self._generate_next_steps(alert_type, details)

        # Format message
        message = f"""{emoji} *{title}*
{timestamp}

*Details:*{details_text}

*Next Steps:*
{next_steps}"""

        # Send message
        result = self.send_message(self.notification_phone, message)

        if result['success']:
            log_info(f"Alert sent successfully: {alert_type} - {title}")
        else:
            log_error(f"Failed to send alert: {result.get('error')}")

        return result

    def _generate_next_steps(self, alert_type: str, details: Dict) -> str:
        """
        Generate actionable next steps based on alert type

        Args:
            alert_type: Type of alert
            details: Alert details

        Returns:
            Formatted next steps text
        """
        if alert_type == 'success':
            return "✓ Review the success metrics in the dashboard\n✓ Consider scaling this strategy"

        elif alert_type == 'warning':
            return "⚠ Review the warning details immediately\n⚠ Take corrective action if needed\n⚠ Monitor closely"

        elif alert_type == 'error':
            return "🚨 Urgent: Review error details immediately\n🚨 Check system logs for root cause\n🚨 Contact technical support if issue persists"

        elif alert_type == 'viral':
            return "🔥 Engage with comments immediately\n🔥 Consider boosting this content\n🔥 Prepare similar follow-up content\n🔥 Monitor sentiment and respond"

        elif alert_type == 'milestone':
            return "🎉 Celebrate with your team\n🎉 Share the achievement on social media\n🎉 Review what led to this success\n🎉 Set the next milestone goal"

        else:
            return "• Review the details\n• Take appropriate action\n• Monitor the situation"

    def test_connection(self) -> bool:
        """
        Test WhatsApp connection by sending a test message

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            log_warning("WhatsApp notifications are disabled - cannot test connection")
            return False

        if not self.notification_phone:
            log_error("NOTIFICATION_PHONE_NUMBER not configured - cannot test connection")
            return False

        test_message = "🔔 Refiloe Marketing: WhatsApp notifications connected successfully!"

        result = self.send_message(self.notification_phone, test_message)

        if result['success']:
            log_info("WhatsApp connection test successful")
            return True
        else:
            log_error(f"WhatsApp connection test failed: {result.get('error')}")
            return False


# Create a singleton instance
_notifier_instance = None


def get_whatsapp_notifier() -> WhatsAppNotifier:
    """
    Get or create the WhatsApp notifier singleton instance

    Returns:
        WhatsAppNotifier instance
    """
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = WhatsAppNotifier()
    return _notifier_instance
