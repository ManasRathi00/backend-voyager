from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Optional, Callable

from playwright.async_api import Playwright, Browser
from .prompts.system_prompt import SYSTEM_PROMPT
from .types import LaunchOptions, VoyagerTask, VoyagerStep  # assume these are defined

class Voyager:
    """
    High-level wrapper around Playwright for scripted browsing 'tasks'.
    """

    def __init__(
        self,
        playwright: Playwright,
        browser: Browser,  # Pass the launched browser instance
        scripts: str,
        max_concurrency: int = 10,
        return_images: bool = True,
    ) -> None:
        self.playwright = playwright
        self.browser = browser  # Store the browser instance
        self.scripts = scripts
        self.concurrency_semaphore = asyncio.Semaphore(max_concurrency)
        self.return_images = return_images

        self.system_prompt: Optional[str] = None
        # self.browser: Optional[Browser] = None # Removed, now passed in __init__

        self.actions_history: list = []

    @classmethod
    async def create(
        cls,
        playwright: Playwright,
        max_concurrency: int = 10,
        return_images: bool = False,
        save_images: bool = False,
        browser_cdp: Optional[str] = None, # Added for CDP connection
        **kwargs: LaunchOptions, # Added for launch options
    ) -> "Voyager":
        """
        Async factory. Reads the browser helper script and returns instance.
        Launches the browser here.
        """
        with open("voyager/scripts/browser-annotate.js", "r", encoding="utf-8") as f:
            scripts = f.read()

        if browser_cdp:
            browser = await playwright.chromium.connect_over_cdp(endpoint_url=browser_cdp)
        else:
            browser = await playwright.chromium.launch(**kwargs)

        instance = cls(
            playwright=playwright,
            browser=browser,
            scripts=scripts,
            max_concurrency=max_concurrency,
            return_images=return_images,
        )
        instance._save_images = save_images
        return instance

    async def start_task(
        self,
        task: VoyagerTask,
        callback: Optional[Callable[[VoyagerStep], None]] = None,
    ) -> None:
        """
        Start a browser session for a task.
        Each task gets its own browser context for isolation.
        `callback` will be invoked for each step with the VoyagerStep data.
        """
        async with self.concurrency_semaphore:
            context = None
            page = None
            try:
                context = await self.browser.new_context()
                page = await context.new_page()

                self.system_prompt = SYSTEM_PROMPT
                self.actions_history = []
                self._task = task
                
                if callback:
                    self._callback = callback
                    
                await page.goto(task.start_url)
                data = await page.evaluate(self.scripts)
                await asyncio.sleep(5)
                print(data)
            finally:
                if page:
                    await page.close()
                if context:
                    await context.close()

    async def stop(self) -> None:
        """Close the browser if open."""
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                print(f"Error closing browser: {e}")
            finally:
                self.browser = None

    # Action execution stubs (single definitions, clear params)
    async def execute_action_click(self, web_ele) -> None:
        """Perform a click on a web element (web_ele should be a Playwright element handle)."""
        pass

    async def execute_action_scroll_element(self, element_index: int, direction: str, web_ele) -> None:
        """
        Scroll a specific element (or window).
        `element_index` = numeric index (or a sentinel for WINDOW),
        `direction` = "up"|"down".
        """
        pass

    async def execute_action_type(self, text: str, web_ele) -> None:
        """Type text into element."""
        pass

    async def execute_action_extract(self) -> None:
        """Extract data from page (implement as needed)."""
        pass

    async def execute_action_success(self) -> None:
        """Mark a step/task as successful."""
        pass

    # convenience context manager support (optional)
    async def __aenter__(self) -> "Voyager":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()
