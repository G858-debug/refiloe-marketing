"""
Task Service for Multi-Step WhatsApp Conversation Flows
Manages conversation state for complex interactions like booking sessions
"""

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import pytz
from utils.logger import log_info, log_error

SA_TZ = pytz.timezone('Africa/Johannesburg')


class TaskService:
    """Service for managing multi-step conversation flows"""

    def __init__(self):
        """Initialize task service with in-memory storage"""
        # Store active tasks: {phone_number: {task_type: task_data}}
        self.active_tasks: Dict[str, Dict[str, Dict]] = {}

    def start_task(self, phone: str, task_type: str, initial_data: Optional[Dict] = None) -> Dict:
        """
        Start a new multi-step task for a user

        Args:
            phone: User's phone number
            task_type: Type of task (e.g., 'book_session', 'reschedule', 'cancel')
            initial_data: Optional initial data for the task

        Returns:
            Dictionary with task data
        """
        if phone not in self.active_tasks:
            self.active_tasks[phone] = {}

        task_data = {
            'task_type': task_type,
            'started_at': datetime.now(SA_TZ).isoformat(),
            'current_step': 0,
            'data': initial_data or {},
            'completed': False
        }

        self.active_tasks[phone][task_type] = task_data
        log_info(f"Started task '{task_type}' for {phone}")

        return task_data

    def get_active_task(self, phone: str, task_type: str) -> Optional[Dict]:
        """
        Get active task for a user

        Args:
            phone: User's phone number
            task_type: Type of task

        Returns:
            Task data dictionary or None if no active task
        """
        if phone in self.active_tasks and task_type in self.active_tasks[phone]:
            return self.active_tasks[phone][task_type]
        return None

    def update_task(self, phone: str, task_type: str, data_update: Dict) -> bool:
        """
        Update task data

        Args:
            phone: User's phone number
            task_type: Type of task
            data_update: Dictionary with data to update

        Returns:
            True if successful, False otherwise
        """
        task = self.get_active_task(phone, task_type)
        if not task:
            log_error(f"No active task '{task_type}' for {phone}")
            return False

        task['data'].update(data_update)
        task['updated_at'] = datetime.now(SA_TZ).isoformat()
        log_info(f"Updated task '{task_type}' for {phone}")

        return True

    def advance_step(self, phone: str, task_type: str) -> int:
        """
        Advance to the next step in the task

        Args:
            phone: User's phone number
            task_type: Type of task

        Returns:
            New step number, or -1 if task not found
        """
        task = self.get_active_task(phone, task_type)
        if not task:
            return -1

        task['current_step'] += 1
        log_info(f"Advanced task '{task_type}' for {phone} to step {task['current_step']}")

        return task['current_step']

    def complete_task(self, phone: str, task_type: str) -> bool:
        """
        Mark a task as completed and clean up

        Args:
            phone: User's phone number
            task_type: Type of task

        Returns:
            True if successful, False otherwise
        """
        if phone not in self.active_tasks or task_type not in self.active_tasks[phone]:
            return False

        self.active_tasks[phone][task_type]['completed'] = True
        self.active_tasks[phone][task_type]['completed_at'] = datetime.now(SA_TZ).isoformat()

        # Clean up completed task
        del self.active_tasks[phone][task_type]

        # Clean up user entry if no more tasks
        if not self.active_tasks[phone]:
            del self.active_tasks[phone]

        log_info(f"Completed task '{task_type}' for {phone}")
        return True

    def cancel_task(self, phone: str, task_type: str) -> bool:
        """
        Cancel an active task

        Args:
            phone: User's phone number
            task_type: Type of task

        Returns:
            True if successful, False otherwise
        """
        if phone not in self.active_tasks or task_type not in self.active_tasks[phone]:
            return False

        # Clean up task
        del self.active_tasks[phone][task_type]

        # Clean up user entry if no more tasks
        if not self.active_tasks[phone]:
            del self.active_tasks[phone]

        log_info(f"Cancelled task '{task_type}' for {phone}")
        return True

    def has_active_task(self, phone: str, task_type: Optional[str] = None) -> bool:
        """
        Check if user has an active task

        Args:
            phone: User's phone number
            task_type: Optional specific task type to check

        Returns:
            True if user has active task, False otherwise
        """
        if phone not in self.active_tasks:
            return False

        if task_type:
            return task_type in self.active_tasks[phone]

        return len(self.active_tasks[phone]) > 0


# Create singleton instance
_task_service_instance = None


def get_task_service() -> TaskService:
    """
    Get or create the task service singleton instance

    Returns:
        TaskService instance
    """
    global _task_service_instance
    if _task_service_instance is None:
        _task_service_instance = TaskService()
    return _task_service_instance
