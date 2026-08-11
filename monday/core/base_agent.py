"""
Base Agent - Abstract base class for all specialist agents

All agents in Monday inherit from this base class, ensuring consistent
interfaces for task execution, communication, and result handling.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time


class AgentStatus(Enum):
    """Status of an agent during task execution."""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING = "waiting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentRequest:
    """
    Structured request sent to an agent.
    
    This ensures structured communication between Monday's orchestrator
    and specialist agents, improving reliability over free-form text.
    """
    task_id: str
    parent_task_id: Optional[str]
    agent_type: str
    objective: str
    context: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    constraints: List[str] = field(default_factory=list)
    deadline: Optional[float] = None
    risk_level: str = "low"  # low, medium, high
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """
    Structured response from an agent.
    
    Contains the output, artifacts, errors, and confidence level.
    """
    task_id: str
    status: AgentStatus
    output: Any = None
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence: float = 1.0
    recommended_next_action: Optional[str] = None
    execution_time: float = 0.0
    model_usage: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Check if the agent completed successfully."""
        return self.status == AgentStatus.COMPLETED and len(self.errors) == 0


class BaseAgent(ABC):
    """
    Abstract base class for all Monday agents.
    
    Agents are specialist components that handle specific types of tasks.
    They receive structured requests and return structured responses.
    """
    
    def __init__(self, agent_type: str):
        """
        Initialize the agent.
        
        Args:
            agent_type: The type identifier for this agent
        """
        self.agent_type = agent_type
        self.status = AgentStatus.IDLE
        self.current_task_id: Optional[str] = None
        self._capabilities: List[str] = []
        self._model_requirements: List[str] = []
    
    @abstractmethod
    def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute a task request.
        
        This is the main entry point for agent execution.
        Subclasses must implement this method.
        
        Args:
            request: The structured task request
            
        Returns:
            AgentResponse with results, artifacts, and any errors
        """
        pass
    
    def can_handle(self, capability: str) -> bool:
        """
        Check if this agent can handle a specific capability.
        
        Args:
            capability: The capability to check
            
        Returns:
            True if the agent supports this capability
        """
        return capability in self._capabilities
    
    def get_capabilities(self) -> List[str]:
        """Get the list of capabilities this agent provides."""
        return self._capabilities.copy()
    
    def get_model_requirements(self) -> List[str]:
        """Get the model capabilities required by this agent."""
        return self._model_requirements.copy()
    
    def _create_response(
        self,
        task_id: str,
        status: AgentStatus,
        output: Any = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        confidence: float = 1.0,
        recommended_next_action: Optional[str] = None,
        execution_time: float = 0.0,
        model_usage: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """
        Helper method to create a standardized response.
        
        Args:
            task_id: The task identifier
            status: Current status of the agent
            output: The main output data
            artifacts: List of artifact dictionaries
            errors: List of error messages
            warnings: List of warning messages
            confidence: Confidence level (0.0 to 1.0)
            recommended_next_action: Suggested next step
            execution_time: Time taken in seconds
            model_usage: Model usage statistics
            
        Returns:
            AgentResponse instance
        """
        return AgentResponse(
            task_id=task_id,
            status=status,
            output=output,
            artifacts=artifacts or [],
            errors=errors or [],
            warnings=warnings or [],
            confidence=confidence,
            recommended_next_action=recommended_next_action,
            execution_time=execution_time,
            model_usage=model_usage or {},
        )
    
    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        return f"{self.agent_type}_{uuid.uuid4().hex[:8]}"
    
    def validate_request(self, request: AgentRequest) -> List[str]:
        """
        Validate an incoming request.
        
        Subclasses can override this to add agent-specific validation.
        
        Args:
            request: The request to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not request.objective:
            errors.append("Objective is required")
        
        if request.deadline and request.deadline < time.time():
            errors.append("Deadline is in the past")
        
        if request.risk_level not in ['low', 'medium', 'high']:
            errors.append(f"Invalid risk level: {request.risk_level}")
        
        return errors
    
    def cancel(self) -> bool:
        """
        Cancel the current task.
        
        Returns:
            True if cancellation was successful
        """
        if self.status in [AgentStatus.THINKING, AgentStatus.EXECUTING, AgentStatus.WAITING]:
            self.status = AgentStatus.CANCELLED
            self.current_task_id = None
            return True
        return False
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.agent_type}, status={self.status.value})"
