"""
Commands Module
Exports all command handlers for the Refiloe WhatsApp assistant
"""

from .trainer import (
    handle_book_session,
    handle_view_bookings,
    handle_cancel_booking,
    handle_reschedule,
)

from .client import (
    handle_request_booking,
    handle_my_sessions,
    handle_cancel_my_session,
    handle_client_book_session_step,
    handle_client_cancel_session_step,
)

__all__ = [
    # Trainer commands
    'handle_book_session',
    'handle_view_bookings',
    'handle_cancel_booking',
    'handle_reschedule',
    # Client commands
    'handle_request_booking',
    'handle_my_sessions',
    'handle_cancel_my_session',
    'handle_client_book_session_step',
    'handle_client_cancel_session_step',
]
