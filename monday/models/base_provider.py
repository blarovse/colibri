"""
Model Provider Base Interface

Abstract base class for all AI model providers in Monday.
Provides a unified interface for generating text, streaming, and embeddings
across different AI providers (Claude, DeepSeek, Qwen, etc.).
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field
import time


@dataclass
class TokenUsage:
    """Token usage statistics from a model response."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def __post_init__(self):
        if self.total_tokens == 0:
            self.total_tokens = self.prompt_tokens + self.completion_tokens


@dataclass
class GenerationResult:
    """
    Unified result from a model generation request.
    
    All providers map their native response formats to this structure.
    """
    content: str
    usage: TokenUsage
    model_id: str
    provider_name: str
    finish_reason: Optional[str] = None  # stop, length, error, etc.
    latency_ms: float = 0.0
    raw_response: Optional[dict] = None
    metadata: dict = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Check if generation was successful."""
        return self.finish_reason != 'error' and len(self.content) > 0


@dataclass
class StreamChunk:
    """
    A single chunk from a streaming generation.
    
    Only the final chunk contains usage statistics.
    """
    delta_text: str
    finish_reason: Optional[str] = None
    usage: Optional[TokenUsage] = None
    chunk_index: int = 0


class ModelProviderError(Exception):
    """Base exception for model provider errors."""
    def __init__(self, message: str, provider: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class ProviderError(ModelProviderError):
    """Generic provider error."""
    pass


class RateLimitError(ModelProviderError):
    """Rate limit exceeded error."""
    def __init__(self, message: str, provider: str, retry_after: Optional[int] = None):
        super().__init__(message, provider, status_code=429)
        self.retry_after = retry_after


class AuthenticationError(ModelProviderError):
    """Authentication failed error."""
    def __init__(self, message: str, provider: str):
        super().__init__(message, provider, status_code=401)


class ContextLengthError(ModelProviderError):
    """Context length exceeded error."""
    def __init__(self, message: str, provider: str, max_context: Optional[int] = None):
        super().__init__(message, provider, status_code=400)
        self.max_context = max_context


class ModelProvider(ABC):
    """
    Abstract base class for all AI model providers.
    
    All concrete providers must implement these async methods.
    """
    
    def __init__(
        self,
        api_key: str,
        default_model: str,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        """
        Initialize the model provider.
        
        Args:
            api_key: API key for authentication
            default_model: Default model ID to use
            base_url: Optional custom base URL for the API
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url
        self.timeout = timeout
        self._request_count = 0
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider."""
        pass
    
    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """Return list of supported model IDs."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        model: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Generate a completion from the model.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt/instruction
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 2.0)
            model: Model ID to use (defaults to default_model)
            **kwargs: Provider-specific additional parameters
            
        Returns:
            GenerationResult with content, usage, and metadata
        """
        pass
    
    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        model: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion from the model.
        
        Yields:
            StreamChunk objects containing delta text
        """
        pass
    
    @abstractmethod
    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        """
        Generate embeddings for text.
        
        Args:
            text: Text to embed
            model: Optional embedding model ID
            
        Returns:
            List of floats representing the embedding vector
        """
        pass
    
    def record_success(self) -> None:
        """Record a successful request."""
        self._request_count += 1
        self._failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed request."""
        self._request_count += 1
        self._failure_count += 1
        self._last_failure_time = time.time()
    
    @property
    def consecutive_failures(self) -> int:
        """Get the number of consecutive failures."""
        return self._failure_count
    
    @property
    def is_healthy(self) -> bool:
        """Check if the provider is considered healthy."""
        # Consider unhealthy after 5 consecutive failures
        return self._failure_count < 5
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the provider.
        
        Returns:
            True if the provider is responsive and authenticated
        """
        try:
            # Simple test with minimal tokens
            result = await self.generate(
                prompt="Hello",
                max_tokens=5,
                temperature=0.0,
            )
            return result.success
        except Exception:
            return False
    
    def get_stats(self) -> dict:
        """Get provider statistics."""
        return {
            'provider': self.provider_name,
            'default_model': self.default_model,
            'total_requests': self._request_count,
            'consecutive_failures': self._failure_count,
            'is_healthy': self.is_healthy,
            'last_failure_time': self._last_failure_time,
        }
