"""
Agent Registry - Manages available specialist agents

The registry allows new agents to be added without redesigning the entire system.
Each agent is registered with its capabilities, making intelligent routing possible.
"""

from typing import Dict, List, Optional, Type
from dataclasses import dataclass, field
from enum import Enum


class AgentType(Enum):
    """Types of specialist agents available in Monday."""
    CODING = "coding"
    RESEARCH = "research"
    CREATIVE = "creative"
    GAME = "game"
    AUTOMATION = "automation"
    BROWSER = "browser"
    SOCIAL = "social"
    TESTING = "testing"
    BUILD = "build"
    VALIDATION = "validation"


@dataclass
class AgentCapability:
    """Represents a capability that an agent provides."""
    name: str
    description: str
    confidence_threshold: float = 0.7


@dataclass
class RegisteredAgent:
    """Metadata for a registered agent."""
    agent_type: AgentType
    class_ref: Type
    capabilities: List[AgentCapability] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    model_requirements: List[str] = field(default_factory=list)


class AgentRegistry:
    """
    Central registry for all specialist agents.
    
    New agents can be registered dynamically without modifying core logic.
    The registry supports capability-based lookup for intelligent routing.
    """
    
    _instance: Optional['AgentRegistry'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[AgentType, RegisteredAgent] = {}
            cls._instance._capabilities_map: Dict[str, List[AgentType]] = {}
        return cls._instance
    
    def register(
        self,
        agent_type: AgentType,
        class_ref: Type,
        capabilities: Optional[List[AgentCapability]] = None,
        priority: int = 0,
        model_requirements: Optional[List[str]] = None
    ) -> None:
        """
        Register a new agent type.
        
        Args:
            agent_type: The type identifier for this agent
            class_ref: The agent class reference
            capabilities: List of capabilities this agent provides
            priority: Priority level for agent selection (higher = preferred)
            model_requirements: List of model capabilities required
        """
        registered = RegisteredAgent(
            agent_type=agent_type,
            class_ref=class_ref,
            capabilities=capabilities or [],
            priority=priority,
            model_requirements=model_requirements or []
        )
        
        self._agents[agent_type] = registered
        
        # Update capability map for fast lookup
        for cap in registered.capabilities:
            if cap.name not in self._capabilities_map:
                self._capabilities_map[cap.name] = []
            self._capabilities_map[cap.name].append(agent_type)
    
    def get(self, agent_type: AgentType) -> Optional[Type]:
        """Get an agent class by type."""
        registered = self._agents.get(agent_type)
        if registered and registered.enabled:
            return registered.class_ref
        return None
    
    def get_all(self) -> Dict[AgentType, Type]:
        """Get all registered and enabled agents."""
        return {
            reg.agent_type: reg.class_ref
            for reg in self._agents.values()
            if reg.enabled
        }
    
    def find_by_capability(self, capability: str) -> List[AgentType]:
        """
        Find agents that provide a specific capability.
        
        Args:
            capability: The capability name to search for
            
        Returns:
            List of agent types that provide this capability, sorted by priority
        """
        agent_types = self._capabilities_map.get(capability, [])
        
        # Sort by priority (higher first)
        sorted_agents = sorted(
            agent_types,
            key=lambda at: self._agents[at].priority,
            reverse=True
        )
        
        return sorted_agents
    
    def unregister(self, agent_type: AgentType) -> bool:
        """
        Unregister an agent type.
        
        Args:
            agent_type: The type to unregister
            
        Returns:
            True if successfully unregistered, False if not found
        """
        if agent_type in self._agents:
            registered = self._agents[agent_type]
            
            # Remove from capability map
            for cap in registered.capabilities:
                if cap.name in self._capabilities_map:
                    self._capabilities_map[cap.name].remove(agent_type)
            
            del self._agents[agent_type]
            return True
        return False
    
    def disable(self, agent_type: AgentType) -> bool:
        """Temporarily disable an agent without unregistering."""
        if agent_type in self._agents:
            self._agents[agent_type].enabled = False
            return True
        return False
    
    def enable(self, agent_type: AgentType) -> bool:
        """Re-enable a disabled agent."""
        if agent_type in self._agents:
            self._agents[agent_type].enabled = True
            return True
        return False
    
    def list_capabilities(self) -> List[str]:
        """List all available capabilities across all agents."""
        return list(self._capabilities_map.keys())
    
    def get_agent_info(self, agent_type: AgentType) -> Optional[Dict]:
        """
        Get detailed information about a registered agent.
        
        Args:
            agent_type: The agent type to get info for
            
        Returns:
            Dictionary with agent metadata, or None if not found
        """
        registered = self._agents.get(agent_type)
        if not registered:
            return None
        
        return {
            'type': registered.agent_type.value,
            'class_name': registered.class_ref.__name__,
            'capabilities': [
                {'name': c.name, 'description': c.description}
                for c in registered.capabilities
            ],
            'priority': registered.priority,
            'enabled': registered.enabled,
            'model_requirements': registered.model_requirements
        }


# Global registry instance
registry = AgentRegistry()


def get_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    return registry
