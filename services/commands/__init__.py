"""
Commands Module
Exports all command handlers for the Refiloe WhatsApp assistant
"""

from .trainer import (
    handle_book_session,
    handle_view_bookings,
    handle_cancel_booking,
    handle_reschedule,
    handle_send_workout,
    handle_send_workout_step,
    handle_create_workout,
    handle_create_workout_step,
    handle_view_workouts,
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
    # Workout commands
    'handle_send_workout',
    'handle_send_workout_step',
    'handle_create_workout',
    'handle_create_workout_step',
    'handle_view_workouts',
    # Client commands
    'handle_request_booking',
    'handle_my_sessions',
    'handle_cancel_my_session',
    'handle_client_book_session_step',
    'handle_client_cancel_session_step',
]
