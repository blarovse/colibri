#!/usr/bin/env python3
"""
Test Model Providers

Example script demonstrating the unified model provider interface.
Sends the same prompt to all three providers (Claude, DeepSeek, Qwen)
and prints unified results.

Usage:
    # Set API keys in environment
    export CLAUDE_API_KEY="your-claude-key"
    export DEEPSEEK_API_KEY="your-deepseek-key"
    export QWEN_API_KEY="your-qwen-key"
    
    # Run the test
    python examples/test_providers.py
"""

import asyncio
import os
import sys

# Add monday to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monday.models import (
    ModelRouter,
    ProviderRegistry,
    TokenUsageTracker,
    get_settings,
)
from monday.models.providers import ClaudeProvider, DeepSeekProvider, QwenProvider


async def test_all_providers():
    """Test all providers with the same prompt."""
    
    print("=" * 60)
    print("MONDAY MODEL PROVIDER TEST")
    print("=" * 60)
    
    # Get settings
    settings = get_settings()
    
    # Check for API keys
    has_claude = bool(settings.claude_api_key)
    has_deepseek = bool(settings.deepseek_api_key)
    has_qwen = bool(settings.qwen_api_key)
    
    if not any([has_claude, has_deepseek, has_qwen]):
        print("\n⚠️  No API keys found in environment.")
        print("Set one or more of:")
        print("  - CLAUDE_API_KEY")
        print("  - DEEPSEEK_API_KEY")
        print("  - QWEN_API_KEY")
        print("\nRunning in demo mode with mocked responses...")
        
        # Demo mode - show structure without actual API calls
        await demo_mode()
        return
    
    # Create router and register available providers
    router = ModelRouter()
    tracker = TokenUsageTracker()
    
    if has_claude:
        claude = ClaudeProvider(
            api_key=settings.claude_api_key,
            default_model="claude-3-5-sonnet-20241022",
        )
        router.register_provider("claude", claude)
        print("\n✓ Claude provider registered")
    
    if has_deepseek:
        deepseek = DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            default_model="deepseek-chat",
        )
        router.register_provider("deepseek", deepseek)
        print("✓ DeepSeek provider registered")
    
    if has_qwen:
        qwen = QwenProvider(
            api_key=settings.qwen_api_key,
            default_model="qwen-coder",
        )
        router.register_provider("qwen", qwen)
        print("✓ Qwen provider registered")
    
    # Test prompt
    prompt = "Explain the concept of recursion in programming in 2-3 sentences."
    system_prompt = "You are a helpful programming tutor."
    
    print(f"\n{'=' * 60}")
    print(f"PROMPT: {prompt}")
    print(f"{'=' * 60}\n")
    
    # Test each provider
    providers_to_test = []
    if has_claude:
        providers_to_test.append(("claude", "coding"))
    if has_deepseek:
        providers_to_test.append(("deepseek", "coding"))
    if has_qwen:
        providers_to_test.append(("qwen", "coding"))
    
    for provider_name, task_type in providers_to_test:
        print(f"\n--- Testing {provider_name.upper()} ---\n")
        
        try:
            result = await router.generate_with_retry(
                prompt=prompt,
                system_prompt=system_prompt,
                task_type=task_type,
                preferred_provider=provider_name,
                max_tokens=150,
                temperature=0.7,
            )
            
            print(f"Model: {result.model_id}")
            print(f"Provider: {result.provider_name}")
            print(f"Finish reason: {result.finish_reason}")
            print(f"Latency: {result.latency_ms:.2f}ms")
            print(f"\nTokens:")
            print(f"  Prompt: {result.usage.prompt_tokens}")
            print(f"  Completion: {result.usage.completion_tokens}")
            print(f"  Total: {result.usage.total_tokens}")
            
            # Record usage
            tracker.record_from_result(result)
            
            print(f"\nResponse:\n{result.content}\n")
            
            if result.metadata.get('attempted_providers'):
                print(f"Attempted providers: {result.metadata['attempted_providers']}")
            
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}\n")
    
    # Print summary
    print("\n" + "=" * 60)
    print("USAGE SUMMARY")
    print("=" * 60)
    
    report = tracker.get_report()
    for provider, usage in report['by_provider'].items():
        print(f"\n{provider.upper()}:")
        print(f"  Total tokens: {usage['total_tokens']}")
        print(f"  Prompt tokens: {usage['prompt_tokens']}")
        print(f"  Completion tokens: {usage['completion_tokens']}")
    
    totals = report['totals']
    print(f"\nTOTAL ACROSS ALL PROVIDERS:")
    print(f"  Total tokens: {totals['total_tokens']}")
    
    # Print router stats
    print("\n" + "=" * 60)
    print("ROUTER STATS")
    print("=" * 60)
    
    stats = router.get_stats()
    print(f"\nRegistered providers: {stats['registered_providers']}")
    print("\nProvider health:")
    for name, health in stats['provider_health'].items():
        status = "✓" if health['is_healthy'] else "✗"
        print(f"  {status} {name}: {health['consecutive_failures']} failures, "
              f"{health['avg_latency_ms']:.2f}ms avg latency")


async def demo_mode():
    """Run in demo mode showing expected structure."""
    
    from monday.models import GenerationResult, TokenUsage
    
    print("\n" + "=" * 60)
    print("DEMO MODE - Expected Response Structure")
    print("=" * 60)
    
    # Show what a typical response looks like
    demo_result = GenerationResult(
        content="Recursion is a programming technique where a function calls itself to solve smaller instances of the same problem. It requires a base case to terminate and a recursive case that progresses toward the base case.",
        usage=TokenUsage(prompt_tokens=25, completion_tokens=45, total_tokens=70),
        model_id="claude-3-5-sonnet-20241022",
        provider_name="anthropic",
        finish_reason="end_turn",
        latency_ms=1250.5,
    )
    
    print(f"\nSample GenerationResult:")
    print(f"  content: {demo_result.content[:80]}...")
    print(f"  model_id: {demo_result.model_id}")
    print(f"  provider_name: {demo_result.provider_name}")
    print(f"  finish_reason: {demo_result.finish_reason}")
    print(f"  latency_ms: {demo_result.latency_ms}")
    print(f"  usage.prompt_tokens: {demo_result.usage.prompt_tokens}")
    print(f"  usage.completion_tokens: {demo_result.usage.completion_tokens}")
    print(f"  usage.total_tokens: {demo_result.usage.total_tokens}")
    print(f"  success: {demo_result.success}")
    
    # Show streaming example structure
    print("\n\nStreaming chunks would yield:")
    print("  StreamChunk(delta_text='Re', finish_reason=None)")
    print("  StreamChunk(delta_text='cursion', finish_reason=None)")
    print("  ...")
    print("  StreamChunk(delta_text='', finish_reason='end_turn', usage=TokenUsage(...))")
    
    # Show router routing logic
    print("\n\n" + "=" * 60)
    print("ROUTING EXAMPLES")
    print("=" * 60)
    
    routing_examples = [
        ("coding", "Qwen → DeepSeek → Claude"),
        ("creative", "Claude → Qwen"),
        ("analysis", "Claude → DeepSeek"),
        ("cost_sensitive", "DeepSeek → Qwen"),
    ]
    
    for task_type, route in routing_examples:
        print(f"  {task_type}: {route}")


async def test_streaming():
    """Test streaming generation with a single provider."""
    
    settings = get_settings()
    
    if not settings.claude_api_key:
        print("\n⚠️  CLAUDE_API_KEY not set. Skipping streaming test.")
        return
    
    print("\n" + "=" * 60)
    print("STREAMING TEST")
    print("=" * 60)
    
    claude = ClaudeProvider(api_key=settings.claude_api_key)
    
    prompt = "Count from 1 to 5 with explanations."
    print(f"\nPrompt: {prompt}\n")
    print("Streaming response:\n")
    
    chunk_count = 0
    async for chunk in claude.stream_generate(
        prompt=prompt,
        max_tokens=100,
        temperature=0.0,
    ):
        if chunk.delta_text:
            print(chunk.delta_text, end="", flush=True)
            chunk_count += 1
        
        if chunk.finish_reason:
            print(f"\n\n[Finished: {chunk.finish_reason}]")
            if chunk.usage:
                print(f"Total tokens: {chunk.usage.total_tokens}")
    
    print(f"\nTotal chunks received: {chunk_count}")


async def main():
    """Main entry point."""
    
    # Parse command line args
    if len(sys.argv) > 1:
        if sys.argv[1] == "--stream":
            await test_streaming()
            return
        elif sys.argv[1] == "--help":
            print(__doc__)
            return
    
    await test_all_providers()


if __name__ == "__main__":
    asyncio.run(main())
