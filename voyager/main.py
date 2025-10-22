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
        scripts: str,
        max_concurrency: int = 10,
        return_images: bool = True,
    ) -> None:
        self.playwright = playwright
        self.scripts = scripts
        # use an explicit semaphore attribute name
        self.concurrency_semaphore = asyncio.Semaphore(max_concurrency)
        self.return_images = return_images

        self.system_prompt: Optional[str] = None
        self.browser: Optional[Browser] = None

        # history of executed actions/steps
        self.actions_history: list = []

    @classmethod
    async def create(
        cls,
        playwright: Playwright,
        max_concurrency: int = 10,
        return_images: bool = False,
        save_images: bool = False,
    ) -> "Voyager":
        """
        Async factory. Reads the browser helper script and returns instance.
        Consider using aiofiles if this needs to be non-blocking.
        """
        with open("voyager/scripts/browser-annotate.js", "r", encoding="utf-8") as f:
            scripts = f.read()

        instance = cls(
            playwright=playwright,
            scripts=scripts,
            max_concurrency=max_concurrency,
            return_images=return_images,
        )
        # you can store save_images flag if you need it
        instance._save_images = save_images
        return instance

    async def start_task(
        self,
        task: VoyagerTask,
        browser_cdp: Optional[str] = None,
        callback: Optional[Callable[[VoyagerStep], None]] = None,
        **kwargs: LaunchOptions,
    ) -> None:
        """
        Start a browser session for a task.
        `**kwargs` are Playwright launch options (TypedDict LaunchOptions) — IDE should autocomplete.
        `callback` will be invoked for each step with the VoyagerStep data.
        """
        if browser_cdp:
            # endpoint_url is what Playwright expects for connect_over_cdp
            self.browser = await self.playwright.chromium.connect_over_cdp(endpoint_url=browser_cdp)
        else:
            self.browser = await self.playwright.chromium.launch(**kwargs)

        self.system_prompt = SYSTEM_PROMPT
        self.actions_history = []
        self._task = task
        
        if callback:
            self._callback = callback
            
        context= await self.browser.new_context()
            
        page = await self.browser.new_page()
        
        
        await page.goto(task.start_url)
        data = await page.evaluate(self.scripts)
        await asyncio.sleep(5)
        print(data)
        
            
        
        


    async def stop(self) -> None:
        """Close the browser if open."""
        if self.browser:
            try:
                await self.browser.close()
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