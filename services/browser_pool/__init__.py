import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext
from typing import Optional, List, AsyncGenerator
from contextlib import asynccontextmanager

from .types.launch_options import LaunchOptions

class BrowserPool:
    def __init__(
        self,
        max_contexts_per_browser: int = 10,
        max_browsers: int = 4,
        cdp_endpoints: Optional[List[str]] = None,
        launch_options: Optional[LaunchOptions] = None,
    ):
        self.max_contexts_per_browser = max_contexts_per_browser
        self.max_browsers = max_browsers
        self.cdp_endpoints = cdp_endpoints or []
        self.launch_options = launch_options or {"headless": True}
        self.browsers: List[Browser] = []
        self.browser_semaphores: List[asyncio.Semaphore] = []
        self.playwright = None
        self.lock = asyncio.Lock()

    async def start(self):
        self.playwright = await async_playwright().start()

        # Connect to CDP endpoints first (if provided)
        for endpoint in self.cdp_endpoints:
            browser = await self.playwright.chromium.connect_over_cdp(endpoint)
            self.browsers.append(browser)
            self.browser_semaphores.append(asyncio.Semaphore(self.max_contexts_per_browser))

        # Optionally prelaunch a browser if none connected
        if not self.browsers:
            await self._create_browser()

    async def stop(self):
        for browser in self.browsers:
            try:
                await browser.close()
            except Exception:
                pass
        if self.playwright:
            await self.playwright.stop()

    async def _create_browser(self) -> Browser:
        browser = await self.playwright.chromium.launch(**self.launch_options)
        self.browsers.append(browser)
        self.browser_semaphores.append(asyncio.Semaphore(self.max_contexts_per_browser))
        return browser

    async def _get_available_browser(self) -> tuple[Browser, asyncio.Semaphore]:
        for browser, sem in zip(self.browsers, self.browser_semaphores):
            if sem.locked() is False:
                return browser, sem

        # If all browsers are full and we can create more
        async with self.lock:
            if len(self.browsers) < self.max_browsers:
                browser = await self._create_browser()
                sem = self.browser_semaphores[-1]
                return browser, sem

        # Otherwise, wait for any semaphore to free up
        while True:
            for browser, sem in zip(self.browsers, self.browser_semaphores):
                if sem.locked() is False:
                    return browser, sem
            await asyncio.sleep(0.1)

    @asynccontextmanager
    async def get_context(self, **context_kwargs) ->  AsyncGenerator[BrowserContext, None]:
        """
        Yields a Playwright BrowserContext.
        Accepts any arguments supported by browser.new_context(), e.g.:

        - user_agent
        - viewport
        - permissions
        - geolocation
        - storage_state
        - proxy
        """
        browser, sem = await self._get_available_browser()
        async with sem:
            context = await browser.new_context(**context_kwargs)
            try:
                yield context
            finally:
                await context.close()
                
if __name__ == "__main__":  
    browser_pool = BrowserPool()
                    
    async def get_browser_context():
        async with browser_pool.get_context() as context:
            yield context