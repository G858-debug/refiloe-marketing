"""
Trainer Commands Module
Exports all trainer-related command handlers
"""

from .booking import (
    handle_book_session,
    handle_view_bookings,
    handle_cancel_booking,
    handle_reschedule,
)

from .workout import (
    handle_send_workout,
    handle_send_workout_step,
    handle_create_workout,
    handle_create_workout_step,
    handle_view_workouts,
)

__all__ = [
    # Booking commands
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
]
