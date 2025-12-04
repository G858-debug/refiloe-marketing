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

__all__ = [
    'handle_book_session',
    'handle_view_bookings',
    'handle_cancel_booking',
    'handle_reschedule',
]
