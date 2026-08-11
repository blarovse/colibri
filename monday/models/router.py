"""
Model Provider Router

Provider registry and intelligent routing with fallback and circuit breaker patterns.
"""

import asyncio
import time
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass, field
import random

from .base_provider import (
    ModelProvider,
    GenerationResult,
    StreamChunk,
    TokenUsage,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ContextLengthError,
    ModelProviderError,
)
from .config import get_settings, ModelProviderSettings


@dataclass
class ProviderHealth:
    """Health status for a provider."""
    is_healthy: bool = True
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    total_requests: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0
    _latency_samples: List[float] = field(default_factory=list)
    
    def record_success(self, latency_ms: float) -> None:
        """Record a successful request."""
        self.consecutive_failures = 0
        self.total_requests += 1
        
        # Track latency with exponential moving average
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > 100:
            self._latency_samples = self._latency_samples[-100:]
        self.avg_latency_ms = sum(self._latency_samples) / len(self._latency_samples)
    
    def record_failure(self) -> None:
        """Record a failed request."""
        self.consecutive_failures += 1
        self.total_requests += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        
        # Mark unhealthy after threshold failures
        settings = get_settings()
        if self.consecutive_failures >= settings.circuit_breaker_threshold:
            self.is_healthy = False
    
    def check_recovery(self) -> bool:
        """Check if the provider should be marked healthy again."""
        if not self.is_healthy and self.last_failure_time:
            settings = get_settings()
            elapsed = time.time() - self.last_failure_time
            if elapsed >= settings.circuit_breaker_timeout:
                self.is_healthy = True
                self.consecutive_failures = 0
                return True
        return False


class ProviderRegistry:
    """
    Registry for model providers.
    
    Allows dynamic registration and lookup of providers by name.
    """
    
    def __init__(self):
        self._providers: Dict[str, ModelProvider] = {}
        self._health: Dict[str, ProviderHealth] = {}
        self._provider_classes: Dict[str, Type[ModelProvider]] = {}
    
    def register(
        self,
        name: str,
        provider: ModelProvider,
        provider_class: Optional[Type[ModelProvider]] = None,
    ) -> None:
        """
        Register a provider instance.
        
        Args:
            name: Unique identifier for the provider
            provider: The provider instance
            provider_class: Optional class reference for metadata
        """
        self._providers[name] = provider
        self._health[name] = ProviderHealth()
        if provider_class:
            self._provider_classes[name] = provider_class
    
    def unregister(self, name: str) -> bool:
        """Unregister a provider by name."""
        if name in self._providers:
            del self._providers[name]
            del self._health[name]
            if name in self._provider_classes:
                del self._provider_classes[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[ModelProvider]:
        """Get a provider by name."""
        return self._providers.get(name)
    
    def list_providers(self) -> List[str]:
        """List all registered provider names."""
        return list(self._providers.keys())
    
    def get_health(self, name: str) -> Optional[ProviderHealth]:
        """Get health status for a provider."""
        health = self._health.get(name)
        if health:
            health.check_recovery()
        return health
    
    def get_all_health(self) -> Dict[str, ProviderHealth]:
        """Get health status for all providers."""
        for health in self._health.values():
            health.check_recovery()
        return self._health.copy()
    
    async def health_check_all(self) -> Dict[str, bool]:
        """
        Perform health checks on all registered providers.
        
        Returns:
            Dictionary mapping provider names to health status
        """
        results = {}
        
        async def check_provider(name: str, provider: ModelProvider) -> tuple[str, bool]:
            try:
                is_healthy = await provider.health_check()
                health = self._health.get(name)
                if health:
                    health.is_healthy = is_healthy
                return (name, is_healthy)
            except Exception:
                health = self._health.get(name)
                if health:
                    health.is_healthy = False
                return (name, False)
        
        tasks = [
            check_provider(name, provider)
            for name, provider in self._providers.items()
        ]
        
        if tasks:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results_list:
                if isinstance(result, Exception):
                    continue
                name, is_healthy = result
                results[name] = is_healthy
        
        return results
    
    async def close_all(self) -> None:
        """Close all registered providers."""
        for provider in self._providers.values():
            try:
                if hasattr(provider, 'close'):
                    await provider.close()
            except Exception:
                pass


class ModelRouter:
    """
    Intelligent router for selecting model providers.
    
    Routes requests based on:
    - Task type
    - Complexity
    - Provider health
    - Cost considerations
    
    Implements fallback chain and circuit breaker patterns.
    """
    
    def __init__(self, registry: Optional[ProviderRegistry] = None):
        self.registry = registry or ProviderRegistry()
        self._settings = get_settings()
        self._request_history: List[Dict[str, Any]] = []
    
    def register_provider(
        self,
        name: str,
        provider: ModelProvider,
        provider_class: Optional[Type[ModelProvider]] = None,
    ) -> 'ModelRouter':
        """Register a provider and return self for chaining."""
        self.registry.register(name, provider, provider_class)
        return self
    
    def route(
        self,
        task_type: str = "general",
        complexity: str = "medium",
        preferred_provider: Optional[str] = None,
    ) -> ModelProvider:
        """
        Route a request to an appropriate provider.
        
        Args:
            task_type: Type of task (coding, creative, analysis, etc.)
            complexity: Task complexity (low, medium, high)
            preferred_provider: Optional preferred provider name
            
        Returns:
            Selected ModelProvider instance
            
        Raises:
            ProviderError: If no healthy provider is available
        """
        # Check if preferred provider is available and healthy
        if preferred_provider:
            provider = self.registry.get(preferred_provider)
            health = self.registry.get_health(preferred_provider)
            
            if provider and health and health.is_healthy:
                return provider
        
        # Get priority list for task type
        priority_list = self._settings.provider_priority.get(
            task_type,
            self._settings.provider_priority.get("general", [])
        )
        
        # Try providers in priority order
        for provider_name in priority_list:
            provider = self.registry.get(provider_name)
            health = self.registry.get_health(provider_name)
            
            if provider and health and health.is_healthy:
                return provider
        
        # Fallback: try any healthy provider
        for name, health in self.registry.get_all_health().items():
            if health.is_healthy:
                provider = self.registry.get(name)
                if provider:
                    return provider
        
        raise ProviderError(
            "No healthy providers available",
            provider="router",
        )
    
    async def route_with_fallback(
        self,
        task_type: str = "general",
        complexity: str = "medium",
        preferred_provider: Optional[str] = None,
        max_attempts: int = 3,
    ) -> tuple[ModelProvider, str]:
        """
        Route with automatic fallback on failure.
        
        Args:
            task_type: Type of task
            complexity: Task complexity
            preferred_provider: Optional preferred provider
            max_attempts: Maximum number of fallback attempts
            
        Returns:
            Tuple of (provider, selected_model_id)
        """
        # Get priority list
        priority_list = self._settings.provider_priority.get(
            task_type,
            self._settings.provider_priority.get("general", [])
        )
        
        if preferred_provider and preferred_provider not in priority_list:
            priority_list.insert(0, preferred_provider)
        
        attempts = 0
        tried_providers = []
        
        for provider_name in priority_list:
            if attempts >= max_attempts:
                break
            
            provider = self.registry.get(provider_name)
            health = self.registry.get_health(provider_name)
            
            if not provider:
                continue
            
            tried_providers.append(provider_name)
            attempts += 1
            
            # Check health but allow trying recently failed providers
            if health and not health.is_healthy:
                # Check if it's time to recover
                if not health.check_recovery():
                    continue
            
            return (provider, provider.default_model)
        
        # If no provider from priority list, try any registered provider
        for name in self.registry.list_providers():
            if name not in tried_providers:
                provider = self.registry.get(name)
                if provider:
                    return (provider, provider.default_model)
        
        raise ProviderError(
            f"No providers available after {attempts} attempts. Tried: {tried_providers}",
            provider="router",
        )
    
    async def generate_with_retry(
        self,
        prompt: str,
        task_type: str = "general",
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        model: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Generate with automatic retry and fallback.
        
        Args:
            prompt: User prompt
            task_type: Task type for routing
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            model: Specific model ID
            preferred_provider: Preferred provider name
            **kwargs: Additional provider-specific parameters
            
        Returns:
            GenerationResult from successful provider
        """
        last_error: Optional[Exception] = None
        attempted_providers = []
        
        for attempt in range(self._settings.max_retries + 2):  # +2 for fallbacks
            try:
                # Route to provider
                provider, selected_model = await self.route_with_fallback(
                    task_type=task_type,
                    preferred_provider=preferred_provider,
                )
                
                attempted_providers.append(provider.provider_name)
                
                # Generate
                result = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    model=model or selected_model,
                    **kwargs,
                )
                
                # Record success
                health = self.registry.get_health(provider.provider_name)
                if health:
                    health.record_success(result.latency_ms)
                
                # Add routing info to metadata
                result.metadata['attempted_providers'] = attempted_providers
                result.metadata['attempt_count'] = attempt + 1
                
                return result
                
            except RateLimitError as e:
                last_error = e
                health = self.registry.get_health(e.provider)
                if health:
                    health.record_failure()
                
                # Wait before retry with exponential backoff
                wait_time = min(2 ** attempt * 0.5, 30)
                if hasattr(e, 'retry_after') and e.retry_after:
                    wait_time = max(wait_time, e.retry_after)
                
                await asyncio.sleep(wait_time + random.uniform(0, 1))
                
            except (AuthenticationError, ContextLengthError) as e:
                # Don't retry these errors
                raise
                
            except ProviderError as e:
                last_error = e
                health = self.registry.get_health(e.provider)
                if health:
                    health.record_failure()
                
                # Short wait before trying next provider
                await asyncio.sleep(0.5 + random.uniform(0, 0.5))
                
            except Exception as e:
                last_error = ProviderError(str(e), provider="unknown")
                await asyncio.sleep(0.5 + random.uniform(0, 0.5))
        
        # All attempts failed
        raise ProviderError(
            f"All providers failed after {attempt + 1} attempts. "
            f"Tried: {attempted_providers}. Last error: {last_error}",
            provider="router",
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router and provider statistics."""
        health_data = {}
        for name, health in self.registry.get_all_health().items():
            health_data[name] = {
                'is_healthy': health.is_healthy,
                'consecutive_failures': health.consecutive_failures,
                'total_requests': health.total_requests,
                'total_failures': health.total_failures,
                'avg_latency_ms': health.avg_latency_ms,
            }
        
        return {
            'registered_providers': self.registry.list_providers(),
            'provider_health': health_data,
            'default_settings': {
                'max_retries': self._settings.max_retries,
                'timeout_seconds': self._settings.timeout_seconds,
                'circuit_breaker_threshold': self._settings.circuit_breaker_threshold,
                'circuit_breaker_timeout': self._settings.circuit_breaker_timeout,
            },
        }


# Convenience function for getting a provider
def get_provider(model_id: str, registry: Optional[ProviderRegistry] = None) -> Optional[ModelProvider]:
    """
    Get a provider by model ID or provider name.
    
    Args:
        model_id: Model ID or provider name
        registry: Optional registry (uses default if not provided)
        
    Returns:
        ModelProvider instance or None
    """
    reg = registry or ProviderRegistry()
    
    # Try direct lookup by provider name
    provider = reg.get(model_id)
    if provider:
        return provider
    
    # Try to find by model ID
    for name, p in reg._providers.items():
        if model_id in p.supported_models or model_id == p.default_model:
            return p
    
    return None


class TokenUsageTracker:
    """Tracks token usage across all providers for cost management."""
    
    def __init__(self):
        self._usage: Dict[str, Dict[str, int]] = {}  # provider -> {prompt, completion, total}
        self._costs: Dict[str, float] = {}  # provider -> estimated cost
    
    def record_usage(
        self,
        provider_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_estimate: float = 0.0,
    ) -> None:
        """Record token usage from a generation."""
        if provider_name not in self._usage:
            self._usage[provider_name] = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
            }
            self._costs[provider_name] = 0.0
        
        self._usage[provider_name]['prompt_tokens'] += prompt_tokens
        self._usage[provider_name]['completion_tokens'] += completion_tokens
        self._usage[provider_name]['total_tokens'] += total_tokens
        self._costs[provider_name] += cost_estimate
    
    def record_from_result(self, result: GenerationResult) -> None:
        """Record usage from a GenerationResult."""
        self.record_usage(
            provider_name=result.provider_name,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
        )
    
    def get_total_usage(self) -> Dict[str, int]:
        """Get aggregated usage across all providers."""
        totals = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
        }
        
        for usage in self._usage.values():
            totals['prompt_tokens'] += usage['prompt_tokens']
            totals['completion_tokens'] += usage['completion_tokens']
            totals['total_tokens'] += usage['total_tokens']
        
        return totals
    
    def get_provider_usage(self, provider_name: str) -> Dict[str, int]:
        """Get usage for a specific provider."""
        return self._usage.get(provider_name, {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
        }).copy()
    
    def get_total_cost(self) -> float:
        """Get total estimated cost."""
        return sum(self._costs.values())
    
    def get_report(self) -> Dict[str, Any]:
        """Get a full usage report."""
        return {
            'by_provider': self._usage.copy(),
            'costs_by_provider': self._costs.copy(),
            'totals': self.get_total_usage(),
            'total_cost': self.get_total_cost(),
        }
    
    def reset(self) -> None:
        """Reset all usage tracking."""
        self._usage.clear()
        self._costs.clear()
