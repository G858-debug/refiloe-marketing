"""
Command Handlers for Message Router
Routes commands to appropriate handlers
"""

from .trainer_commands import TrainerCommandRouter, get_trainer_command_router

__all__ = [
    'TrainerCommandRouter',
    'get_trainer_command_router',
]
