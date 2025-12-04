"""
Message Router Service
Handles routing of WhatsApp messages to appropriate handlers
"""

from services.message_router.handlers.tasks.booking_task_handler import (
    BookingTaskHandler,
    get_booking_task_handler
)

from services.message_router.handlers.commands.trainer_commands import (
    TrainerCommandRouter,
    get_trainer_command_router
)

__all__ = [
    'BookingTaskHandler',
    'get_booking_task_handler',
    'TrainerCommandRouter',
    'get_trainer_command_router',
]
