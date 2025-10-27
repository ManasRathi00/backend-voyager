import asyncio
import pytest
from playwright.async_api import BrowserContext
from .__init__ import BrowserPool

@pytest.mark.asyncio
async def test_anti_bot_user_agent():
    pool = BrowserPool(enable_anti_bot=True)
    await pool.start()
    try:
        async with pool.get_context() as context:
            user_agent = await context.evaluate("navigator.userAgent")
            assert user_agent is not None
            assert "Mozilla" in user_agent # Most common user agents contain Mozilla
            print(f"User Agent: {user_agent}")
    finally:
        await pool.stop()

@pytest.mark.asyncio
async def test_anti_bot_user_agent_disabled():
    pool = BrowserPool(enable_anti_bot=False)
    await pool.start()
    try:
        async with pool.get_context() as context:
            user_agent = await context.evaluate("navigator.userAgent")
            assert user_agent is not None
            # When anti-bot is disabled, Playwright's default user agent should be used.
            # This is typically a Chromium-based user agent.
            assert "HeadlessChrome" in user_agent or "Chromium" in user_agent
            print(f"User Agent (disabled anti-bot): {user_agent}")
    finally:
        await pool.stop()

@pytest.mark.asyncio
async def test_anti_bot_user_agent_overridden():
    custom_user_agent = "MyCustomUserAgent/1.0"
    pool = BrowserPool(enable_anti_bot=True)
    await pool.start()
    try:
        async with pool.get_context(user_agent=custom_user_agent) as context:
            user_agent = await context.evaluate("navigator.userAgent")
            assert user_agent == custom_user_agent
            print(f"User Agent (overridden): {user_agent}")
    finally:
        await pool.stop()
