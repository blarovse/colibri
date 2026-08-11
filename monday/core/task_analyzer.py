"""
Task Analyzer - Understands natural language and determines intent

The Task Analyzer is the first step in Monday's processing pipeline.
It converts user input into structured task specifications.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class TaskType(Enum):
    """Types of tasks that Monday can handle."""
    SOFTWARE_DEVELOPMENT = "software_development"
    GAME_DEVELOPMENT = "game_development"
    RESEARCH = "research"
    CREATIVE = "creative"
    AUTOMATION = "automation"
    BROWSER = "browser"
    SOCIAL_MEDIA = "social_media"
    FILE_OPERATION = "file_operation"
    QUESTION_ANSWERING = "question_answering"
    GENERAL = "general"


class Intent(Enum):
    """User intents that Monday recognizes."""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    OPEN = "open"
    CLOSE = "close"
    SEARCH = "search"
    BUILD = "build"
    TEST = "test"
    DEBUG = "debug"
    DEPLOY = "deploy"
    ANALYZE = "analyze"
    EXPLAIN = "explain"
    SUMMARIZE = "summarize"
    COMPARE = "compare"
    GENERATE = "generate"
    CONVERT = "convert"
    AUTOMATE = "automate"
    SCHEDULE = "schedule"
    UNKNOWN = "unknown"


@dataclass
class TaskSpecification:
    """
    Structured specification of a task extracted from user input.
    
    This is the output of the Task Analyzer and serves as input
    to the Task Planner.
    """
    task_type: TaskType
    intent: Intent
    description: str
    original_input: str
    entities: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    risk_level: str = "low"
    requires_confirmation: bool = False
    confidence: float = 1.0
    alternative_interpretations: List[Dict[str, Any]] = field(default_factory=list)
    
    # For software/game development
    target_platform: Optional[str] = None
    features: List[str] = field(default_factory=list)
    
    # For creative tasks
    style: Optional[str] = None
    format: Optional[str] = None
    
    # For automation
    target_application: Optional[str] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)


class TaskAnalyzer:
    """
    Analyzes user input and extracts structured task specifications.
    
    The analyzer uses pattern matching, keyword recognition, and AI-powered
    intent classification to understand what the user wants.
    """
    
    # Keyword mappings for intent detection
    INTENT_KEYWORDS = {
        Intent.CREATE: ['create', 'make', 'build', 'generate', 'develop', 'design', 'start'],
        Intent.MODIFY: ['modify', 'change', 'update', 'edit', 'fix', 'improve', 'refactor'],
        Intent.DELETE: ['delete', 'remove', 'erase', 'clear', 'drop'],
        Intent.OPEN: ['open', 'launch', 'start', 'run', 'show'],
        Intent.CLOSE: ['close', 'quit', 'exit', 'stop', 'terminate'],
        Intent.SEARCH: ['search', 'find', 'look for', 'query', 'research'],
        Intent.BUILD: ['build', 'compile', 'package', 'assemble'],
        Intent.TEST: ['test', 'verify', 'validate', 'check'],
        Intent.DEBUG: ['debug', 'troubleshoot', 'fix error', 'resolve'],
        Intent.DEPLOY: ['deploy', 'publish', 'release', 'ship'],
        Intent.ANALYZE: ['analyze', 'examine', 'inspect', 'review'],
        Intent.EXPLAIN: ['explain', 'describe', 'tell me about', 'what is'],
        Intent.SUMMARIZE: ['summarize', 'brief', 'overview', 'key points'],
        Intent.COMPARE: ['compare', 'versus', 'vs', 'difference between'],
        Intent.GENERATE: ['generate', 'produce', 'create', 'make'],
        Intent.CONVERT: ['convert', 'transform', 'translate', 'migrate'],
        Intent.AUTOMATE: ['automate', 'script', 'auto'],
        Intent.SCHEDULE: ['schedule', 'plan', 'set up', 'arrange'],
    }
    
    # Keyword mappings for task type detection
    TASK_TYPE_KEYWORDS = {
        TaskType.SOFTWARE_DEVELOPMENT: [
            'app', 'application', 'program', 'software', 'code', 'website',
            'android', 'ios', 'mobile', 'web', 'desktop', 'api', 'service',
            'database', 'backend', 'frontend', 'module', 'library', 'package'
        ],
        TaskType.GAME_DEVELOPMENT: [
            'game', 'gaming', 'play', 'player', 'level', 'character',
            '3d', '2d', 'racing', 'puzzle', 'adventure', 'multiplayer',
            'unity', 'unreal', 'engine', 'physics', 'rendering'
        ],
        TaskType.RESEARCH: [
            'research', 'study', 'investigate', 'find information',
            'learn about', 'understand', 'explore', 'gather', 'sources'
        ],
        TaskType.CREATIVE: [
            'poster', 'image', 'picture', 'design', 'logo', 'graphic',
            'art', 'illustration', 'thumbnail', 'banner', 'flyer',
            'visual', 'creative', 'artwork', 'draw', 'paint'
        ],
        TaskType.AUTOMATION: [
            'automate', 'automation', 'script', 'workflow', 'macro',
            'repeat', 'batch', 'scheduled', 'trigger', 'action'
        ],
        TaskType.BROWSER: [
            'browser', 'chrome', 'firefox', 'safari', 'edge',
            'navigate', 'url', 'website', 'page', 'tab', 'bookmark'
        ],
        TaskType.SOCIAL_MEDIA: [
            'instagram', 'twitter', 'facebook', 'tiktok', 'linkedin',
            'post', 'tweet', 'share', 'upload', 'caption', 'hashtag'
        ],
        TaskType.FILE_OPERATION: [
            'file', 'folder', 'directory', 'document', 'save',
            'copy', 'move', 'rename', 'download', 'upload'
        ],
    }
    
    def __init__(self):
        """Initialize the Task Analyzer."""
        self._custom_patterns: List[Dict[str, Any]] = []
    
    def analyze(self, user_input: str) -> TaskSpecification:
        """
        Analyze user input and extract task specification.
        
        Args:
            user_input: The raw user input string
            
        Returns:
            TaskSpecification with structured task information
        """
        input_lower = user_input.lower()
        
        # Detect intent
        intent = self._detect_intent(input_lower)
        
        # Detect task type
        task_type = self._detect_task_type(input_lower)
        
        # Extract entities
        entities = self._extract_entities(input_lower)
        
        # Extract parameters
        parameters = self._extract_parameters(input_lower, intent, task_type)
        
        # Determine required capabilities
        required_capabilities = self._determine_capabilities(task_type, intent)
        
        # Assess risk level
        risk_level = self._assess_risk(intent, entities)
        
        # Check if confirmation is required
        requires_confirmation = self._requires_confirmation(intent, risk_level)
        
        # Extract features for development tasks
        features = self._extract_features(input_lower) if task_type in [
            TaskType.SOFTWARE_DEVELOPMENT, TaskType.GAME_DEVELOPMENT
        ] else []
        
        # Extract target platform
        target_platform = self._extract_target_platform(input_lower) if task_type in [
            TaskType.SOFTWARE_DEVELOPMENT, TaskType.GAME_DEVELOPMENT
        ] else None
        
        return TaskSpecification(
            task_type=task_type,
            intent=intent,
            description=user_input.strip(),
            original_input=user_input,
            entities=entities,
            parameters=parameters,
            constraints=[],
            dependencies=[],
            required_capabilities=required_capabilities,
            risk_level=risk_level,
            requires_confirmation=requires_confirmation,
            confidence=0.85,  # Base confidence, can be improved with ML model
            target_platform=target_platform,
            features=features,
        )
    
    def _detect_intent(self, input_lower: str) -> Intent:
        """Detect the user's intent from keywords."""
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in input_lower:
                    return intent
        return Intent.UNKNOWN
    
    def _detect_task_type(self, input_lower: str) -> TaskType:
        """Detect the task type from keywords."""
        best_match = TaskType.GENERAL
        best_score = 0
        
        for task_type, keywords in self.TASK_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in input_lower)
            if score > best_score:
                best_score = score
                best_match = task_type
        
        return best_match
    
    def _extract_entities(self, input_lower: str) -> Dict[str, Any]:
        """Extract named entities from the input."""
        entities = {}
        
        # Simple entity extraction - can be enhanced with NLP library
        if 'chrome' in input_lower or 'google chrome' in input_lower:
            entities['application'] = 'Chrome'
        elif 'firefox' in input_lower:
            entities['application'] = 'Firefox'
        
        # Extract potential file paths (very basic)
        import re
        path_pattern = r'[a-zA-Z]:\\[^\s<>|]*|/[^\s<>|]+'
        paths = re.findall(path_pattern, input_lower)
        if paths:
            entities['paths'] = paths
        
        return entities
    
    def _extract_parameters(self, input_lower: str, intent: Intent, task_type: TaskType) -> Dict[str, Any]:
        """Extract parameters based on intent and task type."""
        parameters = {}
        
        # Extract style preferences for creative tasks
        if task_type == TaskType.CREATIVE:
            style_keywords = ['modern', 'minimalist', 'colorful', 'professional', 'casual', 'elegant']
            for style in style_keywords:
                if style in input_lower:
                    parameters['style'] = style
                    break
        
        return parameters
    
    def _determine_capabilities(self, task_type: TaskType, intent: Intent) -> List[str]:
        """Determine which capabilities are required for this task."""
        capabilities = []
        
        capability_map = {
            TaskType.SOFTWARE_DEVELOPMENT: ['coding', 'project_generation', 'build', 'testing'],
            TaskType.GAME_DEVELOPMENT: ['game_dev', 'coding', 'asset_generation', 'build'],
            TaskType.RESEARCH: ['web_search', 'information_gathering', 'summarization'],
            TaskType.CREATIVE: ['image_generation', 'design', 'visual_creation'],
            TaskType.AUTOMATION: ['automation', 'scripting', 'tool_execution'],
            TaskType.BROWSER: ['browser_automation', 'navigation'],
            TaskType.SOCIAL_MEDIA: ['social_automation', 'content_preparation'],
        }
        
        capabilities = capability_map.get(task_type, [])
        
        # Add intent-specific capabilities
        if intent == Intent.TEST:
            capabilities.append('testing')
        elif intent == Intent.DEBUG:
            capabilities.extend(['debugging', 'error_analysis'])
        elif intent == Intent.BUILD:
            capabilities.append('build')
        
        return list(set(capabilities))
    
    def _assess_risk(self, intent: Intent, entities: Dict[str, Any]) -> str:
        """Assess the risk level of the task."""
        high_risk_intents = [Intent.DELETE, Intent.DEPLOY]
        medium_risk_intents = [Intent.MODIFY, Intent.AUTOMATE]
        
        if intent in high_risk_intents:
            return 'high'
        elif intent in medium_risk_intents:
            return 'medium'
        
        # Check for risky entities
        if entities.get('application') in ['Terminal', 'cmd', 'PowerShell']:
            return 'medium'
        
        return 'low'
    
    def _requires_confirmation(self, intent: Intent, risk_level: str) -> bool:
        """Determine if the task requires user confirmation."""
        if risk_level == 'high':
            return True
        
        if intent in [Intent.DELETE, Intent.DEPLOY, Intent.MODIFY]:
            return True
        
        return False
    
    def _extract_features(self, input_lower: str) -> List[str]:
        """Extract feature requirements from the input."""
        features = []
        
        # Common feature keywords
        feature_keywords = [
            'login', 'authentication', 'database', 'storage', 'offline',
            'sync', 'notification', 'reminder', 'search', 'filter',
            'export', 'import', 'settings', 'profile', 'dashboard'
        ]
        
        for feature in feature_keywords:
            if feature in input_lower:
                features.append(feature)
        
        return features
    
    def _extract_target_platform(self, input_lower: str) -> Optional[str]:
        """Extract target platform from the input."""
        platform_keywords = {
            'android': ['android', 'apk', 'mobile'],
            'ios': ['ios', 'iphone', 'ipad', 'swift'],
            'web': ['web', 'website', 'browser', 'html'],
            'windows': ['windows', 'desktop', 'exe'],
            'macos': ['macos', 'mac', 'darwin'],
            'linux': ['linux', 'ubuntu', 'debian'],
            'cross-platform': ['cross-platform', 'multi-platform', 'flutter', 'react native']
        }
        
        for platform, keywords in platform_keywords.items():
            if any(kw in input_lower for kw in keywords):
                return platform
        
        return None
    
    def add_custom_pattern(self, pattern: Dict[str, Any]) -> None:
        """
        Add a custom pattern for task recognition.
        
        Args:
            pattern: Dictionary with 'keywords', 'intent', 'task_type' keys
        """
        self._custom_patterns.append(pattern)
