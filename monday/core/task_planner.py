"""
Task Planner - Creates structured task plans from specifications

The Task Planner converts task specifications into executable task graphs
with dependencies, parallel execution opportunities, and agent assignments.
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time

from .task_analyzer import TaskSpecification, TaskType, Intent


class TaskStatus(Enum):
    """Status of a task in the execution graph."""
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """
    A node in the task execution graph.
    
    Each node represents an atomic unit of work that can be assigned
    to a specific agent.
    """
    task_id: str
    name: str
    description: str
    agent_type: str
    status: TaskStatus = TaskStatus.PENDING
    parent_ids: List[str] = field(default_factory=list)
    child_ids: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[float] = None
    priority: int = 0
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_ready(self) -> bool:
        """Check if all parent tasks are completed successfully."""
        return self.status == TaskStatus.READY
    
    @property
    def is_blocking(self) -> bool:
        """Check if this task is blocking children."""
        return self.status in [TaskStatus.FAILED, TaskStatus.IN_PROGRESS]
    
    @property
    def duration(self) -> Optional[float]:
        """Get the execution duration if completed."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class TaskGraph:
    """
    Complete task execution graph for a user request.
    
    The graph manages dependencies and determines which tasks can
    execute in parallel.
    """
    graph_id: str
    root_task_id: str
    nodes: Dict[str, TaskNode] = field(default_factory=dict)
    edges: List[tuple] = field(default_factory=list)  # (from_id, to_id)
    original_request: str = ""
    created_at: float = field(default_factory=time.time)
    status: TaskStatus = TaskStatus.PENDING
    
    def add_node(self, node: TaskNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.task_id] = node
    
    def add_edge(self, from_id: str, to_id: str) -> None:
        """Add a dependency edge between nodes."""
        self.edges.append((from_id, to_id))
        
        if from_id in self.nodes:
            self.nodes[from_id].child_ids.append(to_id)
        
        if to_id in self.nodes:
            self.nodes[to_id].parent_ids.append(from_id)
    
    def get_ready_tasks(self) -> List[TaskNode]:
        """Get all tasks that are ready to execute."""
        ready = []
        for node in self.nodes.values():
            if node.status == TaskStatus.PENDING:
                # Check if all parents are completed
                all_parents_done = all(
                    self.nodes[pid].status == TaskStatus.COMPLETED
                    for pid in node.parent_ids
                    if pid in self.nodes
                )
                if all_parents_done:
                    node.status = TaskStatus.READY
                    ready.append(node)
        return ready
    
    def get_next_tasks(self, agent_type: Optional[str] = None) -> List[TaskNode]:
        """
        Get next tasks that can be executed, optionally filtered by agent type.
        
        Returns tasks sorted by priority.
        """
        ready = self.get_ready_tasks()
        if agent_type:
            ready = [t for t in ready if t.agent_type == agent_type]
        return sorted(ready, key=lambda t: t.priority, reverse=True)
    
    def mark_completed(self, task_id: str, outputs: Optional[Dict[str, Any]] = None) -> None:
        """Mark a task as completed."""
        if task_id in self.nodes:
            node = self.nodes[task_id]
            node.status = TaskStatus.COMPLETED
            node.completed_at = time.time()
            if outputs:
                node.outputs = outputs
    
    def mark_failed(self, task_id: str, errors: List[str]) -> None:
        """Mark a task as failed."""
        if task_id in self.nodes:
            node = self.nodes[task_id]
            node.status = TaskStatus.FAILED
            node.errors = errors
            node.completed_at = time.time()
    
    def can_retry(self, task_id: str) -> bool:
        """Check if a failed task can be retried."""
        if task_id not in self.nodes:
            return False
        node = self.nodes[task_id]
        return node.retry_count < node.max_retries
    
    def increment_retry(self, task_id: str) -> int:
        """Increment retry count and return new count."""
        if task_id in self.nodes:
            self.nodes[task_id].retry_count += 1
            self.nodes[task_id].status = TaskStatus.PENDING
            return self.nodes[task_id].retry_count
        return 0
    
    def get_execution_order(self) -> List[List[str]]:
        """
        Get tasks grouped by execution level (tasks in same level can run in parallel).
        
        Returns:
            List of lists, where each inner list contains task IDs that can run together
        """
        levels = []
        completed: Set[str] = set()
        remaining = set(self.nodes.keys())
        
        while remaining:
            # Find all tasks whose parents are completed
            current_level = []
            for task_id in remaining:
                node = self.nodes[task_id]
                parents = set(node.parent_ids)
                if parents.issubset(completed):
                    current_level.append(task_id)
            
            if not current_level:
                # Circular dependency or error
                break
            
            levels.append(current_level)
            completed.update(current_level)
            remaining -= set(current_level)
        
        return levels
    
    def get_progress(self) -> Dict[str, Any]:
        """Get execution progress statistics."""
        total = len(self.nodes)
        completed = sum(1 for n in self.nodes.values() if n.status == TaskStatus.COMPLETED)
        failed = sum(1 for n in self.nodes.values() if n.status == TaskStatus.FAILED)
        in_progress = sum(1 for n in self.nodes.values() if n.status == TaskStatus.IN_PROGRESS)
        pending = sum(1 for n in self.nodes.values() if n.status == TaskStatus.PENDING)
        
        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'in_progress': in_progress,
            'pending': pending,
            'percent_complete': (completed / total * 100) if total > 0 else 0
        }


class TaskPlanner:
    """
    Creates task graphs from task specifications.
    
    The planner breaks down complex requests into atomic tasks,
    establishes dependencies, and identifies parallelization opportunities.
    """
    
    def __init__(self):
        """Initialize the Task Planner."""
        self._task_templates: Dict[TaskType, List[Dict[str, Any]]] = self._load_task_templates()
    
    def _load_task_templates(self) -> Dict[TaskType, List[Dict[str, Any]]]:
        """Load predefined task templates for different task types."""
        return {
            TaskType.SOFTWARE_DEVELOPMENT: [
                {'name': 'Requirements Analysis', 'agent_type': 'coding', 'priority': 10},
                {'name': 'Architecture Design', 'agent_type': 'coding', 'priority': 9},
                {'name': 'Project Setup', 'agent_type': 'coding', 'priority': 8},
                {'name': 'Core Implementation', 'agent_type': 'coding', 'priority': 7},
                {'name': 'UI Development', 'agent_type': 'coding', 'priority': 6},
                {'name': 'Integration', 'agent_type': 'coding', 'priority': 5},
                {'name': 'Build', 'agent_type': 'build', 'priority': 4},
                {'name': 'Testing', 'agent_type': 'testing', 'priority': 3},
                {'name': 'Bug Fixes', 'agent_type': 'coding', 'priority': 2},
                {'name': 'Final Build', 'agent_type': 'build', 'priority': 1},
            ],
            TaskType.GAME_DEVELOPMENT: [
                {'name': 'Game Design', 'agent_type': 'game', 'priority': 10},
                {'name': 'Prototype', 'agent_type': 'game', 'priority': 9},
                {'name': 'Core Mechanics', 'agent_type': 'game', 'priority': 8},
                {'name': 'Asset Generation', 'agent_type': 'creative', 'priority': 7},
                {'name': 'Level Design', 'agent_type': 'game', 'priority': 6},
                {'name': 'Integration', 'agent_type': 'game', 'priority': 5},
                {'name': 'Build', 'agent_type': 'build', 'priority': 4},
                {'name': 'Playtesting', 'agent_type': 'testing', 'priority': 3},
                {'name': 'Polish', 'agent_type': 'game', 'priority': 2},
                {'name': 'Final Build', 'agent_type': 'build', 'priority': 1},
            ],
            TaskType.RESEARCH: [
                {'name': 'Search Strategy', 'agent_type': 'research', 'priority': 10},
                {'name': 'Information Gathering', 'agent_type': 'research', 'priority': 9},
                {'name': 'Source Validation', 'agent_type': 'validation', 'priority': 8},
                {'name': 'Analysis', 'agent_type': 'research', 'priority': 7},
                {'name': 'Summary', 'agent_type': 'research', 'priority': 6},
            ],
            TaskType.CREATIVE: [
                {'name': 'Concept Design', 'agent_type': 'creative', 'priority': 10},
                {'name': 'Draft Generation', 'agent_type': 'creative', 'priority': 9},
                {'name': 'Quality Check', 'agent_type': 'validation', 'priority': 8},
                {'name': 'Refinement', 'agent_type': 'creative', 'priority': 7},
                {'name': 'Final Output', 'agent_type': 'creative', 'priority': 6},
            ],
            TaskType.AUTOMATION: [
                {'name': 'Plan Verification', 'agent_type': 'automation', 'priority': 10},
                {'name': 'Permission Check', 'agent_type': 'validation', 'priority': 9},
                {'name': 'Execution', 'agent_type': 'automation', 'priority': 8},
                {'name': 'Verification', 'agent_type': 'validation', 'priority': 7},
            ],
        }
    
    def plan(self, spec: TaskSpecification) -> TaskGraph:
        """
        Create a task graph from a task specification.
        
        Args:
            spec: The task specification from TaskAnalyzer
            
        Returns:
            TaskGraph with all tasks and dependencies
        """
        graph_id = f"graph_{uuid.uuid4().hex[:8]}"
        
        # Create root node
        root_node = TaskNode(
            task_id=f"{graph_id}_root",
            name="Task Initialization",
            description=f"Initialize task: {spec.description}",
            agent_type="orchestrator",
            priority=100,
            inputs={'specification': spec.__dict__},
        )
        
        graph = TaskGraph(
            graph_id=graph_id,
            root_task_id=root_node.task_id,
            original_request=spec.original_input,
        )
        
        graph.add_node(root_node)
        
        # Get template for task type
        template = self._task_templates.get(spec.task_type, [])
        
        if template:
            # Create tasks from template
            previous_task_id = root_node.task_id
            
            for i, task_def in enumerate(template):
                task_node = TaskNode(
                    task_id=f"{graph_id}_task_{i}",
                    name=task_def['name'],
                    description=self._generate_description(task_def['name'], spec),
                    agent_type=task_def['agent_type'],
                    priority=task_def.get('priority', 5),
                    requires_confirmation=spec.requires_confirmation,
                    inputs={'specification': spec.__dict__},
                )
                
                graph.add_node(task_node)
                graph.add_edge(previous_task_id, task_node.task_id)
                previous_task_id = task_node.task_id
        else:
            # Generic single task
            generic_node = TaskNode(
                task_id=f"{graph_id}_task_0",
                name="Execute Task",
                description=spec.description,
                agent_type=self._determine_agent_type(spec.task_type),
                priority=5,
                requires_confirmation=spec.requires_confirmation,
                inputs={'specification': spec.__dict__},
            )
            graph.add_node(generic_node)
            graph.add_edge(root_node.task_id, generic_node.task_id)
        
        return graph
    
    def _generate_description(self, task_name: str, spec: TaskSpecification) -> str:
        """Generate a detailed description for a task."""
        return f"{task_name} for: {spec.description}"
    
    def _determine_agent_type(self, task_type: TaskType) -> str:
        """Determine the primary agent type for a task type."""
        agent_map = {
            TaskType.SOFTWARE_DEVELOPMENT: 'coding',
            TaskType.GAME_DEVELOPMENT: 'game',
            TaskType.RESEARCH: 'research',
            TaskType.CREATIVE: 'creative',
            TaskType.AUTOMATION: 'automation',
            TaskType.BROWSER: 'browser',
            TaskType.SOCIAL_MEDIA: 'social',
        }
        return agent_map.get(task_type, 'general')
    
    def create_parallel_tasks(
        self,
        parent_id: str,
        task_definitions: List[Dict[str, Any]],
        graph: TaskGraph
    ) -> List[str]:
        """
        Create multiple tasks that can execute in parallel.
        
        Args:
            parent_id: ID of the parent task
            task_definitions: List of task definitions
            graph: The task graph to add tasks to
            
        Returns:
            List of created task IDs
        """
        task_ids = []
        
        for i, task_def in enumerate(task_definitions):
            task_node = TaskNode(
                task_id=f"{graph.graph_id}_parallel_{i}",
                name=task_def.get('name', f'Parallel Task {i}'),
                description=task_def.get('description', ''),
                agent_type=task_def.get('agent_type', 'general'),
                priority=task_def.get('priority', 5),
                inputs=task_def.get('inputs', {}),
            )
            
            graph.add_node(task_node)
            graph.add_edge(parent_id, task_node.task_id)
            task_ids.append(task_node.task_id)
        
        return task_ids
    
    def merge_graphs(self, graphs: List[TaskGraph]) -> TaskGraph:
        """
        Merge multiple task graphs into a single graph.
        
        Useful for complex requests that span multiple domains.
        """
        if not graphs:
            raise ValueError("No graphs to merge")
        
        merged = TaskGraph(
            graph_id=f"merged_{uuid.uuid4().hex[:8]}",
            root_task_id=graphs[0].root_task_id,
        )
        
        # Copy all nodes and edges
        for graph in graphs:
            for node in graph.nodes.values():
                merged.add_node(node)
            for edge in graph.edges:
                merged.edges.append(edge)
        
        return merged
