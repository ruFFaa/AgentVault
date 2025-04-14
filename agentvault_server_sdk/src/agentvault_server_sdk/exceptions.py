"""
Custom exception classes for the AgentVault Server SDK.
"""

class AgentServerError(Exception):
    """Base exception for errors originating within an AgentVault agent implementation."""
    pass

class TaskNotFoundError(AgentServerError):
    """Raised when an operation is attempted on a non-existent task ID."""
    def __init__(self, task_id: str, message: str = "Task not found"):
        self.task_id = task_id
        super().__init__(f"{message}: {task_id}")

class InvalidStateTransitionError(AgentServerError):
    """Raised when an invalid state transition is attempted for a task."""
    def __init__(self, task_id: str, from_state: str, to_state: str, message: str = "Invalid state transition"):
        self.task_id = task_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"{message} for task '{task_id}': Cannot transition from {from_state} to {to_state}")

class AgentProcessingError(AgentServerError):
    """Raised for general errors during the agent's core task processing logic."""
    pass

class ConfigurationError(AgentServerError):
    """Raised when there is an issue with the agent's configuration."""
    pass

# Add more specific exceptions as needed, inheriting from AgentServerError or more specific types.
