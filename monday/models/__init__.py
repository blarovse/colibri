"""
Monday Models Package

Unified interface for AI model providers including Claude, DeepSeek, and Qwen.

Usage:
    from monday.models import ModelRouter, ProviderRegistry
    from monday.models.providers import ClaudeProvider, DeepSeekProvider, QwenProvider
    
    # Create router and register providers
    router = ModelRouter()
    router.register_provider("claude", ClaudeProvider(api_key="..."))
    router.register_provider("deepseek", DeepSeekProvider(api_key="..."))
    router.register_provider("qwen", QwenProvider(api_key="..."))
    
    # Generate with automatic routing and fallback
    result = await router.generate_with_retry(
        prompt="Hello, world!",
        task_type="general",
    )
    print(result.content)
"""

from .base_provider import (
    ModelProvider,
    GenerationResult,
    StreamChunk,
    TokenUsage,
    ModelProviderError,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ContextLengthError,
)

from .router import (
    ProviderRegistry,
    ProviderHealth,
    ModelRouter,
    get_provider,
    TokenUsageTracker,
)

from .config import (
    ModelProviderSettings,
    get_settings,
    reload_settings,
)

__all__ = [
    # Base classes
    "ModelProvider",
    "GenerationResult",
    "StreamChunk",
    "TokenUsage",
    # Exceptions
    "ModelProviderError",
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "ContextLengthError",
    # Router
    "ProviderRegistry",
    "ProviderHealth",
    "ModelRouter",
    "get_provider",
    "TokenUsageTracker",
    # Config
    "ModelProviderSettings",
    "get_settings",
    "reload_settings",
]
