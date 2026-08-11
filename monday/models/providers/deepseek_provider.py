"""
DeepSeek Provider

Provider implementation for DeepSeek models.
Supports deepseek-chat and deepseek-coder models.
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


class DeepSeekProvider(ModelProvider):
    """
    Provider for DeepSeek models.
    
    Supports:
    - deepseek-chat
    - deepseek-coder
    """
    
    DEEPSEEK_MODELS = [
        "deepseek-chat",
        "deepseek-coder",
    ]
    
    def __init__(
        self,
        api_key: str,
        default_model: str = "deepseek-chat",
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        super().__init__(api_key, default_model, base_url, timeout)
        self.base_url = base_url or "https://api.deepseek.com"
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def provider_name(self) -> str:
        return "deepseek"
    
    @property
    def supported_models(self) -> list[str]:
        return self.DEEPSEEK_MODELS.copy()
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
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
        """Generate a completion from DeepSeek."""
        start_time = time.time()
        model_id = model or self.default_model
        
        try:
            client = await self._get_client()
            
            # Build request payload (OpenAI-compatible format)
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if key in ["stop", "top_p", "frequency_penalty", "presence_penalty"]:
                    payload[key] = value
            
            response = await client.post("/v1/chat/completions", json=payload)
            
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
            
            # Parse response (OpenAI-compatible format)
            content = ""
            finish_reason = None
            
            if data.get("choices"):
                choice = data["choices"][0]
                message = choice.get("message", {})
                content = message.get("content", "")
                finish_reason = choice.get("finish_reason")
            
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            self.record_success()
            
            return GenerationResult(
                content=content,
                usage=usage,
                model_id=model_id,
                provider_name=self.provider_name,
                finish_reason=finish_reason,
                latency_ms=latency_ms,
                raw_response=data,
                metadata={
                    "id": data.get("id"),
                    "created": data.get("created"),
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
        """Stream a completion from DeepSeek."""
        model_id = model or self.default_model
        
        try:
            client = await self._get_client()
            
            # Build request payload with streaming enabled
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
            
            response = await client.post("/v1/chat/completions", json=payload, stream=True)
            
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
                
                # Parse SSE data (OpenAI-compatible format)
                if event_data.get("choices"):
                    choice = event_data["choices"][0]
                    delta = choice.get("delta", {})
                    text = delta.get("content", "")
                    finish_reason = choice.get("finish_reason")
                    
                    # Usage is only in the final chunk
                    usage = None
                    if "usage" in event_data:
                        usage_data = event_data["usage"]
                        usage = TokenUsage(
                            prompt_tokens=usage_data.get("prompt_tokens", 0),
                            completion_tokens=usage_data.get("completion_tokens", 0),
                            total_tokens=usage_data.get("total_tokens", 0),
                        )
                    
                    if text or finish_reason:
                        yield StreamChunk(
                            delta_text=text,
                            finish_reason=finish_reason,
                            usage=usage,
                            chunk_index=chunk_index,
                        )
                        chunk_index += 1
            
            self.record_success()
            
        except httpx.RequestError as e:
            self.record_failure()
            raise ProviderError(
                f"Streaming request failed: {str(e)}", self.provider_name
            ) from e
    
    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        """
        Generate embeddings.
        
        Note: DeepSeek may support embeddings via separate endpoint.
        This method raises NotImplementedError for now.
        """
        raise NotImplementedError(
            f"{self.provider_name} embeddings not yet implemented. "
            "Use a different provider for embedding tasks."
        )
