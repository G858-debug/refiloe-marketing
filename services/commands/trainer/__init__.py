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

from .payment import (
    handle_request_payment,
    handle_request_payment_step,
    handle_view_payments,
    handle_setup_payment,
    handle_setup_payment_step,
    handle_set_payment_day,
    handle_set_payment_day_step,
)

from .assessment import (
    handle_send_assessment,
    handle_send_assessment_step,
    handle_view_assessments,
    handle_assessment_status,
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
    # Payment commands
    'handle_request_payment',
    'handle_request_payment_step',
    'handle_view_payments',
    'handle_setup_payment',
    'handle_setup_payment_step',
    'handle_set_payment_day',
    'handle_set_payment_day_step',
    # Assessment commands
    'handle_send_assessment',
    'handle_send_assessment_step',
    'handle_view_assessments',
    'handle_assessment_status',
]
