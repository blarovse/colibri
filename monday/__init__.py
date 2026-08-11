"""
Monday - Multi-AI Personal Operating System

Main entry point for the Monday system.
"""

from .core import (
    MondayOrchestrator,
    TaskAnalyzer,
    TaskPlanner,
    AgentRouter,
    AgentRegistry,
)
from .core.base_agent import BaseAgent, AgentRequest, AgentResponse, AgentStatus
from .core.task_analyzer import TaskType, Intent, TaskSpecification
from .core.task_planner import TaskGraph, TaskNode, TaskStatus
from .core.agent_registry import AgentType, AgentCapability

__version__ = '0.1.0'
__author__ = 'Monday Team'

__all__ = [
    # Core orchestrator
    'MondayOrchestrator',
    
    # Core components
    'TaskAnalyzer',
    'TaskPlanner',
    'AgentRouter',
    'AgentRegistry',
    
    # Base classes
    'BaseAgent',
    'AgentRequest',
    'AgentResponse',
    'AgentStatus',
    
    # Types and enums
    'TaskType',
    'Intent',
    'TaskSpecification',
    'TaskGraph',
    'TaskNode',
    'TaskStatus',
    'AgentType',
    'AgentCapability',
]


def create_orchestrator() -> MondayOrchestrator:
    """
    Create a new Monday orchestrator instance.
    
    Returns:
        Configured MondayOrchestrator ready to process requests
    """
    return MondayOrchestrator()


def process_request(user_input: str) -> dict:
    """
    Process a user request and return results as a dictionary.
    
    This is a convenience function for simple use cases.
    
    Args:
        user_input: Natural language input from the user
        
    Returns:
        Dictionary with status, outputs, errors, and metadata
    """
    orchestrator = create_orchestrator()
    result = orchestrator.process(user_input)
    
    return {
        'status': result.status,
        'outputs': result.outputs,
        'artifacts': result.artifacts,
        'errors': result.errors,
        'warnings': result.warnings,
        'execution_time': result.execution_time,
        'model_usage': result.model_usage,
    }
