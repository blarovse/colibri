"""
Monday Automation Action Model

Defines the structured action model for automation operations.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, List
import uuid


class ActionType(Enum):
    """Supported automation action types"""
    # App control
    OPEN_APP = auto()
    CLOSE_APP = auto()
    FOCUS_WINDOW = auto()
    
    # Input
    TYPE_TEXT = auto()
    PRESS_KEY = auto()
    CLICK = auto()
    SCROLL = auto()
    
    # Screen
    TAKE_SCREENSHOT = auto()
    
    # File operations
    READ_FILE = auto()
    WRITE_FILE = auto()
    DELETE_FILE = auto()
    COPY_FILE = auto()
    MOVE_FILE = auto()
    LIST_DIRECTORY = auto()
    CREATE_DIRECTORY = auto()
    
    # Shell
    RUN_COMMAND = auto()
    RUN_SCRIPT = auto()
    
    # Browser
    NAVIGATE = auto()
    CLICK_ELEMENT = auto()
    FILL_FORM = auto()
    SUBMIT_FORM = auto()
    EXTRACT_TEXT = auto()
    DOWNLOAD_FILE = auto()
    
    # Other
    SHOW_NOTIFICATION = auto()
    SEND_EMAIL = auto()


class RiskLevel(Enum):
    """Action risk levels for permission gating"""
    NONE = 'none'
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


@dataclass
class Action:
    """Structured representation of an automation action"""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ActionType = ActionType.TAKE_SCREENSHOT
    target: str = ''
    parameters: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    confirmation_prompt: str = ''
    timeout_seconds: int = 30
    retry_policy: dict = field(default_factory=lambda: {'max_retries': 2, 'backoff': 'exponential'})
    verification: str = ''
    requested_by: str = ''
    task_id: str = ''
    
    def validate(self) -> List[str]:
        """Validate action and return list of errors"""
        errors = []
        if not self.target and self.action_type not in [ActionType.TAKE_SCREENSHOT, ActionType.LIST_DIRECTORY]:
            errors.append("Target is required for this action type")
        if self.timeout_seconds <= 0:
            errors.append("Timeout must be positive")
        return errors


@dataclass
class ActionResult:
    """Result of an action execution"""
    success: bool
    output: Any = None
    error: Optional[str] = None
    action_id: Optional[str] = None
    execution_time_ms: Optional[float] = None
