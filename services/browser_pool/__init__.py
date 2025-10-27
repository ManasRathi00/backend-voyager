import asyncio
from typing import Optional, List, AsyncGenerator, Dict, Any
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
from playwright_stealth import Stealth
from fake_useragent import UserAgent

from .types.launch_options import LaunchOptions


class BrowserPool:
    """
    Manages a pool of Playwright browsers and browser contexts for concurrent automation.
    
    Features:
    - Multiple browser instances with configurable context limits
    - CDP endpoint support for remote browsers
    - Anti-bot detection with stealth mode and user agent rotation
    - Automatic browser creation when pool is exhausted
    """

    def __init__(
        self,
        max_contexts_per_browser: int = 10,
        max_browsers: int = 4,
        cdp_endpoints: Optional[List[str]] = None,
        launch_options: Optional[LaunchOptions] = None,
        enable_anti_bot: bool = False,
    ):
        """
        Initialize the browser pool.
        
        Args:
            max_contexts_per_browser: Maximum concurrent contexts per browser
            max_browsers: Maximum number of browser instances in the pool
            cdp_endpoints: List of CDP URLs for remote browser connections
            launch_options: Browser launch configuration
            enable_anti_bot: Enable stealth mode and user agent rotation
        """
        self.max_contexts_per_browser = max_contexts_per_browser
        self.max_browsers = max_browsers
        self.cdp_endpoints = cdp_endpoints or []
        self.launch_options = launch_options or {"headless": True}
        self.enable_anti_bot = enable_anti_bot
        
        self.browsers: List[Browser] = []
        self.browser_semaphores: List[asyncio.Semaphore] = []
        self.playwright: Optional[Playwright] = None
        self.lock = asyncio.Lock()
        self._started = False
        
        if self.enable_anti_bot:
            self.user_agent_generator = UserAgent()

    async def start(self) -> None:
        """Initialize Playwright and connect to browsers."""
        if self._started:
            return

        self.playwright = await async_playwright().start()

        # Connect to remote browsers via CDP if endpoints provided
        for endpoint in self.cdp_endpoints:
            try:
                browser = await self.playwright.chromium.connect_over_cdp(endpoint)
                self.browsers.append(browser)
                self.browser_semaphores.append(
                    asyncio.Semaphore(self.max_contexts_per_browser)
                )
            except Exception as e:
                print(f"Failed to connect to CDP endpoint {endpoint}: {e}")

        # Launch at least one browser if no CDP connections succeeded
        if not self.browsers:
            await self._create_browser()

        self._started = True

    async def stop(self) -> None:
        """Close all browsers and stop Playwright."""
        if not self._started:
            return

        for browser in self.browsers:
            try:
                await browser.close()
            except Exception as e:
                print(f"Error closing browser: {e}")

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        self.browsers.clear()
        self.browser_semaphores.clear()
        self._started = False

    async def _create_browser(self) -> Browser:
        """Create and register a new browser instance."""
        if not self.playwright:
            raise RuntimeError("BrowserPool not started. Call start() first.")

        browser = await self.playwright.chromium.launch(**self.launch_options)
        self.browsers.append(browser)
        self.browser_semaphores.append(
            asyncio.Semaphore(self.max_contexts_per_browser)
        )
        return browser

    async def _get_available_browser(self) -> tuple[Browser, asyncio.Semaphore]:
        """
        Get an available browser with capacity for new contexts.
        Creates new browsers if needed and within limits.
        """
        # Quick check for immediately available browser
        for browser, sem in zip(self.browsers, self.browser_semaphores):
            if not sem.locked():
                return browser, sem

        # Try to create a new browser if under limit
        async with self.lock:
            if len(self.browsers) < self.max_browsers:
                browser = await self._create_browser()
                return browser, self.browser_semaphores[-1]

        # Wait for any browser to become available
        while True:
            for browser, sem in zip(self.browsers, self.browser_semaphores):
                if not sem.locked():
                    return browser, sem
            await asyncio.sleep(0.1)

    @asynccontextmanager
    async def get_context(
        self, **context_kwargs
    ) -> AsyncGenerator[BrowserContext, None]:
        """
        Acquire a browser context from the pool.
        
        Supports all browser.new_context() arguments:
        - user_agent: Custom user agent string
        - viewport: Viewport dimensions
        - permissions: Browser permissions
        - geolocation: Location data
        - storage_state: Cookies and local storage
        - proxy: Proxy configuration
        - etc.
        
        Automatically applies anti-bot measures if enabled.
        
        Example:
            async with pool.get_context(viewport={"width": 1920, "height": 1080}) as ctx:
                page = await ctx.new_page()
                await page.goto("https://example.com")
        """
        if not self._started:
            raise RuntimeError("BrowserPool not started. Call start() first.")

        browser, sem = await self._get_available_browser()

        async with sem:
            # Apply anti-bot user agent if enabled and not provided
            if self.enable_anti_bot and "user_agent" not in context_kwargs:
                context_kwargs["user_agent"] = self.user_agent_generator.random

            context = await browser.new_context(**context_kwargs)

            # Apply stealth techniques
            if self.enable_anti_bot:
                await self._apply_anti_bot_measures(context)

            try:
                yield context
            finally:
                await context.close()

    async def _apply_anti_bot_measures(self, context: BrowserContext) -> None:
        """Apply stealth mode and webdriver hiding to the context."""
        try:
            stealth = Stealth()
            await stealth.apply_stealth_async(context)
            
            # Hide webdriver property
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
        except Exception as e:
            print(f"Warning: Failed to apply anti-bot measures: {e}")

    async def __aenter__(self) -> "BrowserPool":
        """Context manager entry: start the pool."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit: stop the pool."""
        await self.stop()


# Example usage
async def main():
    """Example of using BrowserPool."""
    async with BrowserPool(
        max_contexts_per_browser=5,
        max_browsers=2,
        enable_anti_bot=True
    ) as pool:
        async with pool.get_context(viewport={"width": 1920, "height": 1080}) as ctx:
            page = await ctx.new_page()
            await page.goto("https://example.com")
            print(await page.title())


if __name__ == "__main__":
    asyncio.run(main())