"""
Anthropic Claude Provider

Provider implementation for Anthropic's Claude models.
Supports Claude 3.5 Sonnet, Claude 3 Opus, and other Claude models.
"""

import asyncio
import time
from typing import AsyncIterator, Optional

import httpx

from ..base_provider import (
    ModelProvider,
    GenerationResult,
    StreamChunk,
    TokenUsage,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ContextLengthError,
)


class ClaudeProvider(ModelProvider):
    """
    Provider for Anthropic Claude models.
    
    Supports:
    - claude-3-5-sonnet-20241022
    - claude-3-opus-20240229
    - claude-3-sonnet-20240229
    - claude-3-haiku-20240307
    """
    
    CLAUDE_MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-latest",
        "claude-3-opus-20240229",
        "claude-3-opus-latest",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]
    
    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-3-5-sonnet-20241022",
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        super().__init__(api_key, default_model, base_url, timeout)
        self.base_url = base_url or "https://api.anthropic.com"
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    @property
    def supported_models(self) -> list[str]:
        return self.CLAUDE_MODELS.copy()
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        model: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """Generate a completion from Claude."""
        start_time = time.time()
        model_id = model or self.default_model
        
        try:
            client = await self._get_client()
            
            # Build request payload
            payload = {
                "model": model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if key in ["stop_sequences", "top_p", "top_k"]:
                    payload[key] = value
            
            response = await client.post("/v1/messages", json=payload)
            
            # Handle errors
            if response.status_code == 401:
                self.record_failure()
                raise AuthenticationError(
                    "Invalid API key", self.provider_name
                )
            elif response.status_code == 429:
                self.record_failure()
                retry_after = response.headers.get("retry-after")
                raise RateLimitError(
                    "Rate limit exceeded", self.provider_name,
                    retry_after=int(retry_after) if retry_after else None
                )
            elif response.status_code >= 500:
                self.record_failure()
                raise ProviderError(
                    f"Server error: {response.status_code}", self.provider_name,
                    status_code=response.status_code
                )
            elif response.status_code != 200:
                self.record_failure()
                raise ProviderError(
                    f"Request failed: {response.status_code}", self.provider_name,
                    status_code=response.status_code
                )
            
            data = response.json()
            
            # Parse response
            content = ""
            if data.get("content"):
                for block in data["content"]:
                    if block.get("type") == "text":
                        content += block.get("text", "")
            
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                completion_tokens=usage_data.get("output_tokens", 0),
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            self.record_success()
            
            return GenerationResult(
                content=content,
                usage=usage,
                model_id=model_id,
                provider_name=self.provider_name,
                finish_reason=data.get("stop_reason"),
                latency_ms=latency_ms,
                raw_response=data,
                metadata={
                    "id": data.get("id"),
                    "type": data.get("type"),
                },
            )
            
        except httpx.RequestError as e:
            self.record_failure()
            raise ProviderError(
                f"Request failed: {str(e)}", self.provider_name
            ) from e
    
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        model: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a completion from Claude."""
        model_id = model or self.default_model
        
        try:
            client = await self._get_client()
            
            # Build request payload with streaming enabled
            payload = {
                "model": model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
                "messages": [{"role": "user", "content": prompt}],
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            response = await client.post("/v1/messages", json=payload, stream=True)
            
            if response.status_code != 200:
                raise ProviderError(
                    f"Streaming request failed: {response.status_code}",
                    self.provider_name,
                    status_code=response.status_code,
                )
            
            chunk_index = 0
            
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                
                data_str = line[6:]  # Remove "data: " prefix
                
                if data_str == "[DONE]":
                    break
                
                import json
                try:
                    event_data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                
                # Handle different event types
                event_type = event_data.get("type")
                
                if event_type == "content_block_delta":
                    delta = event_data.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        yield StreamChunk(
                            delta_text=text,
                            finish_reason=None,
                            chunk_index=chunk_index,
                        )
                        chunk_index += 1
                
                elif event_type == "message_delta":
                    delta = event_data.get("delta", {})
                    stop_reason = delta.get("stop_reason")
                    
                    # Get usage from streaming_stats if available
                    usage = None
                    if "usage" in event_data:
                        usage_data = event_data["usage"]
                        usage = TokenUsage(
                            output_tokens=usage_data.get("output_tokens", 0),
                        )
                    
                    yield StreamChunk(
                        delta_text="",
                        finish_reason=stop_reason,
                        usage=usage,
                        chunk_index=chunk_index,
                    )
            
            self.record_success()
            
        except httpx.RequestError as e:
            self.record_failure()
            raise ProviderError(
                f"Streaming request failed: {str(e)}", self.provider_name
            ) from e
    
    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        """
        Generate embeddings.
        
        Note: Claude does not currently support embeddings.
        This method raises NotImplementedError.
        """
        raise NotImplementedError(
            f"{self.provider_name} does not support embeddings. "
            "Use a different provider for embedding tasks."
        )
