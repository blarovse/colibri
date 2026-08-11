"""
Agent Router - Selects appropriate agents for each subtask

The Agent Router uses intelligent routing to select the best agent
for each task based on capabilities, model requirements, and availability.
"""

from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field
import time

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from .agent_registry import AgentRegistry, AgentType, get_registry
from .task_planner import TaskNode, TaskGraph, TaskStatus


@dataclass
class RoutingDecision:
    """Represents a routing decision made by the router."""
    task_id: str
    selected_agent_type: str
    alternative_agents: List[str] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    model_selected: Optional[str] = None


class AgentRouter:
    """
    Intelligent router that selects appropriate agents for tasks.
    
    The router considers:
    - Task type and requirements
    - Agent capabilities
    - Model availability and suitability
    - Agent load and health
    - Cost optimization
    """
    
    def __init__(self, registry: Optional[AgentRegistry] = None):
        """
        Initialize the Agent Router.
        
        Args:
            registry: Agent registry instance (uses global if not provided)
        """
        self.registry = registry or get_registry()
        self._agent_instances: Dict[str, BaseAgent] = {}
        self._routing_history: List[RoutingDecision] = []
        self._agent_stats: Dict[str, Dict[str, Any]] = {}
    
    def route(self, task_node: TaskNode) -> RoutingDecision:
        """
        Route a task node to an appropriate agent.
        
        Args:
            task_node: The task node to route
            
        Returns:
            RoutingDecision with selected agent and reasoning
        """
        # Find candidate agents
        candidates = self._find_candidates(task_node)
        
        if not candidates:
            return RoutingDecision(
                task_id=task_node.task_id,
                selected_agent_type='general',
                reasoning="No specialized agent found, using general agent",
                confidence=0.5
            )
        
        # Score and rank candidates
        scored = self._score_candidates(candidates, task_node)
        
        # Select best candidate
        best = max(scored, key=lambda x: x['score'])
        
        decision = RoutingDecision(
            task_id=task_node.task_id,
            selected_agent_type=best['agent_type'],
            alternative_agents=[c['agent_type'] for c in scored[1:3]],
            reasoning=best['reasoning'],
            confidence=best['score']
        )
        
        self._routing_history.append(decision)
        return decision
    
    def _find_candidates(self, task_node: TaskNode) -> List[Dict[str, Any]]:
        """Find candidate agents for a task."""
        candidates = []
        
        # Get all registered agents
        all_agents = self.registry.get_all()
        
        for agent_type, agent_class in all_agents.items():
            # Create temporary instance to check capabilities
            try:
                agent = agent_class()
                
                # Check if agent can handle this task
                capability_match = self._check_capability_match(agent, task_node)
                
                if capability_match:
                    candidates.append({
                        'agent_type': agent_type.value,
                        'class': agent_class,
                        'instance': agent,
                        'capabilities': agent.get_capabilities(),
                    })
            except Exception:
                continue
        
        return candidates
    
    def _check_capability_match(self, agent: BaseAgent, task_node: TaskNode) -> bool:
        """Check if an agent's capabilities match the task requirements."""
        # If task doesn't specify requirements, assume match
        if not hasattr(task_node, 'inputs') or not task_node.inputs:
            return True
        
        spec = task_node.inputs.get('specification', {})
        required_caps = spec.get('required_capabilities', [])
        
        if not required_caps:
            return True
        
        agent_caps = agent.get_capabilities()
        
        # Check if agent has at least one required capability
        return any(cap in agent_caps for cap in required_caps)
    
    def _score_candidates(
        self,
        candidates: List[Dict[str, Any]],
        task_node: TaskNode
    ) -> List[Dict[str, Any]]:
        """Score candidates based on multiple factors."""
        scored = []
        
        for candidate in candidates:
            score = 0.0
            reasons = []
            
            agent = candidate['instance']
            agent_type = candidate['agent_type']
            
            # Factor 1: Capability match strength
            spec = task_node.inputs.get('specification', {})
            required_caps = spec.get('required_capabilities', [])
            
            if required_caps:
                agent_caps = set(agent.get_capabilities())
                matching_caps = len(set(required_caps) & agent_caps)
                cap_score = (matching_caps / len(required_caps)) * 30
                score += cap_score
                reasons.append(f"capability_match={cap_score:.1f}")
            
            # Factor 2: Agent priority
            agent_info = self.registry.get_agent_info(AgentType(agent_type))
            if agent_info:
                priority_score = agent_info.get('priority', 0) * 5
                score += priority_score
                reasons.append(f"priority={priority_score:.1f}")
            
            # Factor 3: Historical performance
            stats = self._agent_stats.get(agent_type, {})
            success_rate = stats.get('success_rate', 0.5)
            perf_score = success_rate * 20
            score += perf_score
            reasons.append(f"performance={perf_score:.1f}")
            
            # Factor 4: Availability (not currently executing)
            if agent.status.value == 'idle':
                score += 10
                reasons.append("available=true")
            
            candidate['score'] = score
            candidate['reasoning'] = ', '.join(reasons)
            scored.append(candidate)
        
        return scored
    
    def get_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """
        Get or create an agent instance.
        
        Args:
            agent_type: The type of agent to get
            
        Returns:
            Agent instance or None if not found
        """
        if agent_type in self._agent_instances:
            return self._agent_instances[agent_type]
        
        # Try to instantiate from registry
        try:
            agent_enum = AgentType(agent_type)
            agent_class = self.registry.get(agent_enum)
            if agent_class:
                agent = agent_class()
                self._agent_instances[agent_type] = agent
                return agent
        except ValueError:
            pass
        
        return None
    
    def execute_task(self, task_node: TaskNode) -> AgentResponse:
        """
        Route and execute a task through the appropriate agent.
        
        Args:
            task_node: The task node to execute
            
        Returns:
            AgentResponse from the executed agent
        """
        # Route the task
        decision = self.route(task_node)
        
        # Get the agent
        agent = self.get_agent(decision.selected_agent_type)
        
        if not agent:
            return AgentResponse(
                task_id=task_node.task_id,
                status=TaskStatus.FAILED,
                errors=[f"Agent '{decision.selected_agent_type}' not found"],
                confidence=0.0
            )
        
        # Create request
        request = AgentRequest(
            task_id=task_node.task_id,
            parent_task_id=task_node.parent_ids[0] if task_node.parent_ids else None,
            agent_type=decision.selected_agent_type,
            objective=task_node.description,
            context=task_node.metadata,
            inputs=task_node.inputs,
            constraints=[],
            risk_level='low',
            requires_confirmation=task_node.requires_confirmation,
        )
        
        # Execute
        start_time = time.time()
        try:
            agent.status = type(agent.status).THINKING  # type: ignore
            response = agent.execute(request)
            response.execution_time = time.time() - start_time
            
            # Update stats
            self._update_agent_stats(
                decision.selected_agent_type,
                response.success
            )
            
            return response
        except Exception as e:
            return AgentResponse(
                task_id=task_node.task_id,
                status=TaskStatus.FAILED,
                errors=[str(e)],
                execution_time=time.time() - start_time
            )
    
    def _update_agent_stats(self, agent_type: str, success: bool) -> None:
        """Update statistics for an agent."""
        if agent_type not in self._agent_stats:
            self._agent_stats[agent_type] = {
                'total': 0,
                'successes': 0,
                'failures': 0,
                'avg_time': 0.0,
            }
        
        stats = self._agent_stats[agent_type]
        stats['total'] += 1
        
        if success:
            stats['successes'] += 1
        else:
            stats['failures'] += 1
        
        # Update success rate
        stats['success_rate'] = stats['successes'] / stats['total']
    
    def get_routing_history(self, limit: int = 100) -> List[RoutingDecision]:
        """Get recent routing decisions."""
        return self._routing_history[-limit:]
    
    def get_agent_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all agents."""
        return self._agent_stats.copy()
    
    def clear_history(self) -> None:
        """Clear routing history."""
        self._routing_history.clear()
