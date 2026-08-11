"""
Model Provider Configuration

Pydantic settings for model providers loaded from environment variables.
"""

from typing import Optional, List, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class ModelProviderSettings(BaseSettings):
    """Settings for all model providers."""
    
    # API Keys
    claude_api_key: Optional[str] = Field(default=None, alias="CLAUDE_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")
    qwen_api_key: Optional[str] = Field(default=None, alias="QWEN_API_KEY")
    
    # Default model selection
    default_model: str = Field(default="claude-3-5-sonnet-20241022", alias="DEFAULT_MODEL")
    
    # Retry and timeout settings
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    timeout_seconds: float = Field(default=60.0, alias="TIMEOUT_SECONDS")
    
    # Streaming defaults
    enable_streaming_default: bool = Field(default=True, alias="ENABLE_STREAMING_DEFAULT")
    
    # Circuit breaker settings
    circuit_breaker_threshold: int = Field(default=5, alias="CIRCUIT_BREAKER_THRESHOLD")
    circuit_breaker_timeout: float = Field(default=60.0, alias="CIRCUIT_BREAKER_TIMEOUT")
    
    # Task type to provider priority mappings
    # Format: {"coding": ["qwen", "deepseek", "claude"], "creative": ["claude"], ...}
    provider_priority: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "coding": ["qwen", "deepseek", "claude"],
            "creative": ["claude", "qwen"],
            "analysis": ["claude", "deepseek"],
            "cost_sensitive": ["deepseek", "qwen"],
            "reasoning": ["claude", "deepseek"],
            "general": ["claude", "qwen", "deepseek"],
        },
        alias="PROVIDER_PRIORITY",
    )
    
    # Model-specific configurations
    model_configs: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        alias="MODEL_CONFIGS",
    )
    
    @field_validator('provider_priority', mode='before')
    @classmethod
    def parse_provider_priority(cls, v):
        """Parse provider_priority from string if needed."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v
    
    @field_validator('model_configs', mode='before')
    @classmethod
    def parse_model_configs(cls, v):
        """Parse model_configs from string if needed."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
_settings: Optional[ModelProviderSettings] = None


def get_settings() -> ModelProviderSettings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = ModelProviderSettings()
    return _settings


def reload_settings() -> ModelProviderSettings:
    """Reload settings from environment."""
    global _settings
    _settings = ModelProviderSettings()
    return _settings
