"""
Monday Orchestrator - The central AI brain

The orchestrator coordinates all components of Monday:
- Receives user input
- Analyzes intent with TaskAnalyzer
- Creates execution plan with TaskPlanner
- Routes tasks to agents with AgentRouter
- Manages execution and validation
- Reports results to user
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import time
import uuid

from .task_analyzer import TaskAnalyzer, TaskSpecification, TaskType
from .task_planner import TaskPlanner, TaskGraph, TaskNode, TaskStatus
from .agent_router import AgentRouter, RoutingDecision
from .base_agent import AgentResponse


@dataclass
class ExecutionResult:
    """Result of executing a complete user request."""
    request_id: str
    original_input: str
    status: str  # success, partial, failed
    outputs: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    task_graph: Optional[TaskGraph] = None
    model_usage: Dict[str, Any] = field(default_factory=dict)


class MondayOrchestrator:
    """
    Central orchestrator for the Monday AI system.
    
    This is the main entry point for user requests. It coordinates
    all subsystems to fulfill user requests end-to-end.
    """
    
    def __init__(
        self,
        task_analyzer: Optional[TaskAnalyzer] = None,
        task_planner: Optional[TaskPlanner] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        """
        Initialize the Monday Orchestrator.
        
        Args:
            task_analyzer: Task analyzer instance (creates default if not provided)
            task_planner: Task planner instance (creates default if not provided)
            agent_router: Agent router instance (creates default if not provided)
        """
        self.task_analyzer = task_analyzer or TaskAnalyzer()
        self.task_planner = task_planner or TaskPlanner()
        self.agent_router = agent_router or AgentRouter()

        # Make sure the agents that ship with Monday (including Jarvis,
        # the prediction specialist) are available for routing.
        from ..agents import register_default_agents
        register_default_agents()
        
        self._execution_history: List[ExecutionResult] = []
        self._active_graphs: Dict[str, TaskGraph] = {}
        self._request_callbacks: List[Callable[[str], None]] = []
        self._progress_callbacks: List[Callable[[Dict[str, Any]], None]] = []
    
    def process(self, user_input: str) -> ExecutionResult:
        """
        Process a user request from start to finish.
        
        This is the main entry point for user requests.
        
        Args:
            user_input: The natural language input from the user
            
        Returns:
            ExecutionResult with outputs, artifacts, and any errors
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        
        # Notify callbacks
        self._notify_request(user_input)
        
        try:
            # Step 1: Analyze the request
            spec = self.task_analyzer.analyze(user_input)
            
            # Step 2: Create task plan
            graph = self.task_planner.plan(spec)
            self._active_graphs[request_id] = graph
            
            # Step 3: Execute the task graph
            result = self._execute_graph(graph, request_id)
            
            # Record execution time
            result.execution_time = time.time() - start_time
            result.request_id = request_id
            result.original_input = user_input
            
            # Store in history
            self._execution_history.append(result)
            
            # Clean up active graph
            del self._active_graphs[request_id]
            
            return result
            
        except Exception as e:
            return ExecutionResult(
                request_id=request_id,
                original_input=user_input,
                status='failed',
                errors=[str(e)],
                execution_time=time.time() - start_time,
            )
    
    def _execute_graph(self, graph: TaskGraph, request_id: str) -> ExecutionResult:
        """
        Execute a task graph.
        
        Args:
            graph: The task graph to execute
            request_id: The request identifier
            
        Returns:
            ExecutionResult with all outputs and artifacts
        """
        outputs = {}
        all_artifacts = []
        all_errors = []
        all_warnings = []
        total_model_usage = {}
        
        # Get execution order (levels of parallel tasks)
        levels = graph.get_execution_order()
        
        for level_idx, level in enumerate(levels):
            # Execute all tasks in this level
            level_results = []
            
            for task_id in level:
                task_node = graph.nodes[task_id]
                
                # Skip root node (initialization always counts as progress)
                if 'root' in task_id:
                    graph.mark_completed(task_id)
                    level_results.append(True)
                    continue
                
                # Check for confirmation requirement
                if task_node.requires_confirmation:
                    if not self._request_confirmation(task_node):
                        graph.mark_failed(task_id, ["User declined confirmation"])
                        all_errors.append(f"Task '{task_node.name}' requires confirmation")
                        continue
                
                # Execute the task
                self._notify_progress({
                    'level': level_idx,
                    'task': task_node.name,
                    'status': 'in_progress',
                    'graph_progress': graph.get_progress()
                })
                
                response = self.agent_router.execute_task(task_node)
                
                if response.success:
                    graph.mark_completed(
                        task_id,
                        response.output if isinstance(response.output, dict)
                        else {'output': response.output},
                    )
                    outputs[task_id] = response.output
                    
                    if response.artifacts:
                        all_artifacts.extend(response.artifacts)
                    
                    if response.warnings:
                        all_warnings.extend(response.warnings)
                    
                    # Aggregate model usage
                    for key, value in response.model_usage.items():
                        if key in total_model_usage:
                            total_model_usage[key] += value
                        else:
                            total_model_usage[key] = value
                    
                    level_results.append(True)
                else:
                    # Handle failure
                    if graph.can_retry(task_id):
                        retry_count = graph.increment_retry(task_id)
                        all_warnings.append(
                            f"Task '{task_node.name}' failed, retrying ({retry_count}/{task_node.max_retries})"
                        )
                        # Re-execute this task
                        response = self.agent_router.execute_task(task_node)
                        if response.success:
                            graph.mark_completed(task_id, response.outputs)
                            outputs[task_id] = response.output
                            level_results.append(True)
                        else:
                            graph.mark_failed(task_id, response.errors)
                            all_errors.extend(response.errors)
                            level_results.append(False)
                    else:
                        graph.mark_failed(task_id, response.errors)
                        all_errors.extend(response.errors)
                        level_results.append(False)
                
                self._notify_progress({
                    'level': level_idx,
                    'task': task_node.name,
                    'status': 'completed' if response.success else 'failed',
                    'graph_progress': graph.get_progress()
                })
            
            # Check if we should continue to next level
            if not any(level_results) and level_idx < len(levels) - 1:
                # Critical failure, stop execution
                break
        
        # Determine overall status
        progress = graph.get_progress()
        if progress['failed'] == 0:
            status = 'success'
        elif progress['completed'] > 0:
            status = 'partial'
        else:
            status = 'failed'
        
        return ExecutionResult(
            request_id=request_id,
            original_input="",
            status=status,
            outputs=outputs,
            artifacts=all_artifacts,
            errors=all_errors,
            warnings=all_warnings,
            task_graph=graph,
            model_usage=total_model_usage,
        )
    
    def _request_confirmation(self, task_node: TaskNode) -> bool:
        """
        Request user confirmation for a task.
        
        In a real implementation, this would interact with the user.
        For now, it returns True by default.
        
        Args:
            task_node: The task requiring confirmation
            
        Returns:
            True if confirmed, False otherwise
        """
        # Placeholder - in real implementation, this would:
        # 1. Display task details to user
        # 2. Wait for user response
        # 3. Return user's decision
        print(f"[CONFIRMATION REQUIRED] {task_node.name}: {task_node.description}")
        return True
    
    def _notify_request(self, user_input: str) -> None:
        """Notify callbacks of a new request."""
        for callback in self._request_callbacks:
            try:
                callback(user_input)
            except Exception:
                pass
    
    def _notify_progress(self, progress: Dict[str, Any]) -> None:
        """Notify callbacks of execution progress."""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception:
                pass
    
    def on_request(self, callback: Callable[[str], None]) -> None:
        """Register a callback for new requests."""
        self._request_callbacks.append(callback)
    
    def on_progress(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for progress updates."""
        self._progress_callbacks.append(callback)
    
    def get_execution_history(self, limit: int = 100) -> List[ExecutionResult]:
        """Get recent execution results."""
        return self._execution_history[-limit:]
    
    def get_active_graphs(self) -> Dict[str, TaskGraph]:
        """Get currently active task graphs."""
        return self._active_graphs.copy()
    
    def cancel_request(self, request_id: str) -> bool:
        """
        Cancel an active request.
        
        Args:
            request_id: The request ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        if request_id in self._active_graphs:
            graph = self._active_graphs[request_id]
            for node in graph.nodes.values():
                if node.status in [TaskStatus.PENDING, TaskStatus.READY, TaskStatus.IN_PROGRESS]:
                    node.status = TaskStatus.CANCELLED
            return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status."""
        return {
            'active_requests': len(self._active_graphs),
            'total_executions': len(self._execution_history),
            'agent_stats': self.agent_router.get_agent_stats(),
            'recent_routing': len(self.agent_router.get_routing_history()),
        }
