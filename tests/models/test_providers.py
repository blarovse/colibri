"""
Tests for Monday Model Providers

Unit tests with mocked HTTP responses for each provider,
router fallback logic, and circuit breaker behavior.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
import json

# Test imports from monday.models
from monday.models.base_provider import (
    ModelProvider,
    GenerationResult,
    StreamChunk,
    TokenUsage,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ContextLengthError,
)
from monday.models.router import (
    ProviderRegistry,
    ProviderHealth,
    ModelRouter,
    TokenUsageTracker,
)
from monday.models.config import ModelProviderSettings


class MockProvider(ModelProvider):
    """Mock provider for testing."""
    
    def __init__(self, name: str = "mock", should_fail: bool = False):
        super().__init__(
            api_key="test-key",
            default_model="mock-model",
            timeout=10.0,
        )
        self._name = name
        self._should_fail = should_fail
        self._call_count = 0
    
    @property
    def provider_name(self) -> str:
        return self._name
    
    @property
    def supported_models(self) -> list[str]:
        return ["mock-model"]
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        model: str | None = None,
        **kwargs,
    ) -> GenerationResult:
        self._call_count += 1
        
        if self._should_fail:
            raise ProviderError("Mock failure", self._name)
        
        return GenerationResult(
            content=f"Response from {self._name}",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            model_id=model or self.default_model,
            provider_name=self._name,
            finish_reason="stop",
            latency_ms=100.0,
        )
    
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        model: str | None = None,
        **kwargs,
    ):
        yield StreamChunk(delta_text="Hello ", chunk_index=0)
        yield StreamChunk(delta_text="world", chunk_index=1)
        yield StreamChunk(delta_text="", finish_reason="stop", chunk_index=2)
    
    async def embed(self, text: str, model: str | None = None) -> list[float]:
        return [0.1, 0.2, 0.3]


class TestTokenUsage:
    """Test TokenUsage dataclass."""
    
    def test_token_usage_creation(self):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20)
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30
    
    def test_token_usage_with_total(self):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=50)
        assert usage.total_tokens == 50


class TestGenerationResult:
    """Test GenerationResult dataclass."""
    
    def test_generation_result_creation(self):
        result = GenerationResult(
            content="Hello",
            usage=TokenUsage(total_tokens=10),
            model_id="test-model",
            provider_name="test-provider",
        )
        assert result.content == "Hello"
        assert result.success is True
    
    def test_generation_result_failure(self):
        result = GenerationResult(
            content="",
            usage=TokenUsage(),
            model_id="test-model",
            provider_name="test-provider",
            finish_reason="error",
        )
        assert result.success is False


class TestProviderExceptions:
    """Test provider exception classes."""
    
    def test_provider_error(self):
        error = ProviderError("Test error", "test-provider", status_code=500)
        assert str(error) == "Test error"
        assert error.provider == "test-provider"
        assert error.status_code == 500
    
    def test_rate_limit_error(self):
        error = RateLimitError("Rate limited", "test-provider", retry_after=60)
        assert error.status_code == 429
        assert error.retry_after == 60
    
    def test_authentication_error(self):
        error = AuthenticationError("Invalid key", "test-provider")
        assert error.status_code == 401
    
    def test_context_length_error(self):
        error = ContextLengthError("Too long", "test-provider", max_context=4096)
        assert error.status_code == 400
        assert error.max_context == 4096


class TestProviderRegistry:
    """Test ProviderRegistry functionality."""
    
    def test_register_and_get(self):
        registry = ProviderRegistry()
        provider = MockProvider(name="test")
        
        registry.register("test", provider)
        
        assert registry.get("test") == provider
        assert "test" in registry.list_providers()
    
    def test_unregister(self):
        registry = ProviderRegistry()
        provider = MockProvider(name="test")
        
        registry.register("test", provider)
        assert registry.unregister("test") is True
        assert registry.get("test") is None
    
    def test_health_tracking(self):
        registry = ProviderRegistry()
        provider = MockProvider(name="test")
        
        registry.register("test", provider)
        health = registry.get_health("test")
        
        assert health is not None
        assert health.is_healthy is True
        assert health.consecutive_failures == 0


class TestProviderHealth:
    """Test ProviderHealth class."""
    
    def test_record_success(self):
        health = ProviderHealth()
        health.record_success(100.0)
        
        assert health.consecutive_failures == 0
        assert health.total_requests == 1
        assert health.avg_latency_ms == 100.0
    
    def test_record_failure(self):
        health = ProviderHealth()
        
        for _ in range(5):
            health.record_failure()
        
        assert health.consecutive_failures == 5
        assert health.total_failures == 5
        assert health.is_healthy is False
    
    def test_check_recovery(self):
        health = ProviderHealth()
        health.is_healthy = False
        health.last_failure_time = time.time() - 70  # 70 seconds ago
        
        # Should recover after timeout (default 60s)
        assert health.check_recovery() is True
        assert health.is_healthy is True


class TestModelRouter:
    """Test ModelRouter functionality."""
    
    def test_route_to_preferred_provider(self):
        router = ModelRouter()
        provider = MockProvider(name="preferred")
        router.register_provider("preferred", provider)
        
        result = router.route(preferred_provider="preferred")
        assert result == provider
    
    def test_route_by_task_type(self):
        router = ModelRouter()
        coding_provider = MockProvider(name="coder")
        creative_provider = MockProvider(name="creative")
        
        router.register_provider("coder", coding_provider)
        router.register_provider("creative", creative_provider)
        
        # Should route coding task to coder
        result = router.route(task_type="coding")
        assert result == coding_provider
    
    def test_route_fallback_when_unhealthy(self):
        router = ModelRouter()
        primary = MockProvider(name="primary", should_fail=True)
        fallback = MockProvider(name="fallback")
        
        router.register_provider("primary", primary)
        router.register_provider("fallback", fallback)
        
        # Mark primary as unhealthy
        health = router.registry.get_health("primary")
        if health:
            health.is_healthy = False
        
        # Should route to fallback
        result = router.route(task_type="general")
        assert result == fallback
    
    def test_no_healthy_providers_error(self):
        router = ModelRouter()
        provider = MockProvider(name="test")
        router.register_provider("test", provider)
        
        # Mark as unhealthy
        health = router.registry.get_health("test")
        if health:
            health.is_healthy = False
            health.consecutive_failures = 5
        
        with pytest.raises(ProviderError):
            router.route()


class TestRouterFallback:
    """Test router fallback and retry logic."""
    
    @pytest.mark.asyncio
    async def test_generate_with_retry_success(self):
        router = ModelRouter()
        provider = MockProvider(name="test")
        router.register_provider("test", provider)
        
        result = await router.generate_with_retry(
            prompt="Test prompt",
            task_type="general",
        )
        
        assert result.content == "Response from test"
        assert result.provider_name == "test"
    
    @pytest.mark.asyncio
    async def test_generate_all_providers_fail(self):
        router = ModelRouter()
        failing = MockProvider(name="failing", should_fail=True)
        router.register_provider("failing", failing)
        
        with pytest.raises(ProviderError) as exc_info:
            await router.generate_with_retry(
                prompt="Test",
                max_attempts=2,
            )
        
        assert "All providers failed" in str(exc_info.value)


class TestCircuitBreaker:
    """Test circuit breaker pattern."""
    
    def test_circuit_breaker_opens_after_failures(self):
        health = ProviderHealth()
        
        # Simulate 5 consecutive failures
        for _ in range(5):
            health.record_failure()
        
        assert health.is_healthy is False
    
    def test_circuit_breaker_closes_after_timeout(self):
        health = ProviderHealth()
        
        # Open circuit
        for _ in range(5):
            health.record_failure()
        
        assert health.is_healthy is False
        
        # Wait for timeout
        health.last_failure_time = time.time() - 61
        
        # Should close
        assert health.check_recovery() is True
        assert health.is_healthy is True


class TestTokenUsageTracker:
    """Test token usage tracking."""
    
    def test_record_usage(self):
        tracker = TokenUsageTracker()
        
        tracker.record_usage(
            provider_name="test",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        
        usage = tracker.get_provider_usage("test")
        assert usage['prompt_tokens'] == 10
        assert usage['completion_tokens'] == 20
        assert usage['total_tokens'] == 30
    
    def test_record_from_result(self):
        tracker = TokenUsageTracker()
        
        result = GenerationResult(
            content="Test",
            usage=TokenUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            model_id="test",
            provider_name="test-provider",
        )
        
        tracker.record_from_result(result)
        
        totals = tracker.get_total_usage()
        assert totals['total_tokens'] == 15
    
    def test_aggregate_usage(self):
        tracker = TokenUsageTracker()
        
        tracker.record_usage("provider-a", 10, 20, 30)
        tracker.record_usage("provider-a", 5, 10, 15)
        tracker.record_usage("provider-b", 8, 12, 20)
        
        totals = tracker.get_total_usage()
        assert totals['total_tokens'] == 65
        
        usage_a = tracker.get_provider_usage("provider-a")
        assert usage_a['total_tokens'] == 45
    
    def test_reset(self):
        tracker = TokenUsageTracker()
        tracker.record_usage("test", 10, 20, 30)
        
        tracker.reset()
        
        totals = tracker.get_total_usage()
        assert totals['total_tokens'] == 0


class TestMockProvider:
    """Test the mock provider used in tests."""
    
    @pytest.mark.asyncio
    async def test_mock_generate(self):
        provider = MockProvider(name="test")
        
        result = await provider.generate("Test prompt")
        
        assert result.content == "Response from test"
        assert result.provider_name == "test"
    
    @pytest.mark.asyncio
    async def test_mock_stream(self):
        provider = MockProvider(name="test")
        
        chunks = []
        async for chunk in provider.stream_generate("Test"):
            chunks.append(chunk)
        
        assert len(chunks) == 3
        assert chunks[0].delta_text == "Hello "
        assert chunks[-1].finish_reason == "stop"
    
    @pytest.mark.asyncio
    async def test_mock_embed(self):
        provider = MockProvider(name="test")
        
        embedding = await provider.embed("Test text")
        
        assert embedding == [0.1, 0.2, 0.3]
    
    @pytest.mark.asyncio
    async def test_mock_failure(self):
        provider = MockProvider(name="test", should_fail=True)
        
        with pytest.raises(ProviderError):
            await provider.generate("Test")


class TestIntegration:
    """Integration tests for the models layer."""
    
    @pytest.mark.asyncio
    async def test_full_routing_flow(self):
        """Test complete routing flow from registration to generation."""
        router = ModelRouter()
        tracker = TokenUsageTracker()
        
        # Register providers
        claude = MockProvider(name="claude")
        deepseek = MockProvider(name="deepseek")
        qwen = MockProvider(name="qwen")
        
        router.register_provider("claude", claude)
        router.register_provider("deepseek", deepseek)
        router.register_provider("qwen", qwen)
        
        # Generate with routing
        result = await router.generate_with_retry(
            prompt="Explain recursion",
            task_type="coding",
            preferred_provider="qwen",
        )
        
        # Record usage
        tracker.record_from_result(result)
        
        # Verify
        assert result.success is True
        assert tracker.get_total_usage()['total_tokens'] == 30
        
        # Check stats
        stats = router.get_stats()
        assert "claude" in stats['registered_providers']
        assert "deepseek" in stats['registered_providers']
        assert "qwen" in stats['registered_providers']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
