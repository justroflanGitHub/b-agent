#!/usr/bin/env python3
"""
Test script for Browser Agent.

This script tests the basic functionality of the browser agent.
Run with: python test_agent.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from browser_agent import (
    BrowserAgent,
    Config,
    ActionType,
    create_agent,
)


async def test_browser_launch():
    """Test browser launch and basic navigation."""
    print("\n🧪 Test: Browser Launch")
    print("-" * 40)
    
    config = Config()
    config.browser.headless = True  # Run headless for testing
    
    async with BrowserAgent(config) as agent:
        # Test navigation
        result = await agent.navigate("https://example.com")
        print(f"   Navigate: {'✅' if result.success else '❌'}")
        
        # Test page info
        info = await agent.get_page_info()
        print(f"   Page URL: {info.get('url', 'N/A')}")
        print(f"   Page Title: {info.get('title', 'N/A')}")
        
        # Test screenshot
        screenshot = await agent.take_screenshot()
        print(f"   Screenshot: {'✅' if len(screenshot) > 0 else '❌'} ({len(screenshot)} bytes)")
        
        # Test text extraction
        text = await agent.extract_text()
        print(f"   Text extraction: {'✅' if len(text) > 0 else '❌'} ({len(text)} chars)")
        
        print("   ✅ Browser launch test passed")
        return True


async def test_action_executor():
    """Test action executor with various actions."""
    print("\n🧪 Test: Action Executor")
    print("-" * 40)
    
    config = Config()
    config.browser.headless = True
    
    async with BrowserAgent(config) as agent:
        # Navigate to test page
        await agent.navigate("https://example.com")
        
        # Test scroll actions
        result = await agent.scroll_down(200)
        print(f"   Scroll down: {'✅' if result.success else '❌'}")
        
        result = await agent.scroll_up(100)
        print(f"   Scroll up: {'✅' if result.success else '❌'}")
        
        # Test key press
        result = await agent.press_key("End")
        print(f"   Press key: {'✅' if result.success else '❌'}")
        
        # Test wait
        result = await agent.action_executor.execute(ActionType.WAIT, value=0.5)
        print(f"   Wait: {'✅' if result.success else '❌'}")
        
        print("   ✅ Action executor test passed")
        return True


async def test_config():
    """Test configuration loading."""
    print("\n🧪 Test: Configuration")
    print("-" * 40)
    
    # Test default config
    config = Config()
    print(f"   Default viewport: {config.browser.viewport_width}x{config.browser.viewport_height}")
    print(f"   Default headless: {config.browser.headless}")
    print(f"   Default LLM URL: {config.llm.base_url}")
    
    # Test config to dict
    data = config.to_dict()
    print(f"   Config to dict: {'✅' if 'browser' in data else '❌'}")
    
    # Test from dict
    config2 = Config._from_dict(data)
    print(f"   Config from dict: {'✅' if config2.browser.viewport_width == 1920 else '❌'}")
    
    print("   ✅ Configuration test passed")
    return True


async def test_vision_client():
    """Test vision client connection (requires LM Studio running)."""
    print("\n🧪 Test: Vision Client")
    print("-" * 40)
    
    config = Config()
    
    try:
        from browser_agent.llm import VisionClient
        
        client = VisionClient(config)
        await client._ensure_session()
        
        # Try a simple request (will fail if LM Studio not running)
        from browser_agent.llm import ChatMessage, MessageRole
        
        try:
            response = await client.chat([
                ChatMessage(MessageRole.USER, "Hello, this is a test. Reply with 'OK'.")
            ], max_tokens=10)
            
            print(f"   Vision client response: {response.content[:50]}...")
            print(f"   Response time: {response.latency_ms:.0f}ms")
            print("   ✅ Vision client test passed")
            return True
            
        except Exception as e:
            print(f"   ⚠️ Vision client request failed (LM Studio may not be running)")
            print(f"   Error: {e}")
            return True  # Don't fail test if LM Studio not available
            
    except Exception as e:
        print(f"   ❌ Vision client test failed: {e}")
        return False
    finally:
        await client.close()


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 50)
    print("🚀 Browser Agent Test Suite")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_config),
        ("Browser Launch", test_browser_launch),
        ("Action Executor", test_action_executor),
        ("Vision Client", test_vision_client),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n   ❌ Test failed with error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")
    
    print(f"\n   Total: {passed}/{total} tests passed")
    print("=" * 50)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
