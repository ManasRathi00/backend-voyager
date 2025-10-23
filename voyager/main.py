from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Optional, Callable

from config.logger import logger


from playwright.async_api import Playwright, BrowserContext, Page
from .prompts.system_prompt import SYSTEM_PROMPT
from .types import VoyagerTask, VoyagerStep  # assume these are defined

class Voyager:
    """
    High-level wrapper around Playwright for scripted browsing 'tasks'.
    """

    def __init__(
        self,
        scripts: str,
        max_concurrency: int = 10,
        return_images: bool = True,
    ) -> None:
        self.scripts = scripts
        self.concurrency_semaphore = asyncio.Semaphore(max_concurrency)
        self.return_images = return_images

        self.system_prompt: Optional[str] = None
        self.actions_history: list = []

    @classmethod
    async def create(
        cls,
        max_concurrency: int = 10,
        return_images: bool = False,
        save_images: bool = False,
    ) -> "Voyager":
        """
        Async factory. Reads the browser helper script and returns instance.
        """
        with open("voyager/scripts/browser-annotate.js", "r", encoding="utf-8") as f:
            scripts = f.read()

        instance = cls(
            scripts=scripts,
            max_concurrency=max_concurrency,
            return_images=return_images,
        )
        instance._save_images = save_images
        return instance

    async def start_task(
        self,
        browser_context: BrowserContext, # Accept BrowserContext directly
        task: VoyagerTask,
        callback: Optional[Callable[[VoyagerStep], None]] = None,
    ) -> None:
        """
        Start a browser session for a task.
        `callback` will be invoked for each step with the VoyagerStep data.
        """
        async with self.concurrency_semaphore:
            task_page = None
            try:
                task_page = await browser_context.new_page()

                self.system_prompt = SYSTEM_PROMPT
                self.actions_history = []
                self._task = task
                
                await task_page.goto(task.start_url)
                all_indexes = await  self.get_page_web_element_rect(page=task_page)
                element = task_page.locator('[data-voyager-element-index="3"]')
                
                # You can interact with it, e.g. click, read text, etc.
                text = await element.text_content()
                print(text)
#                 await task_page.evaluate("""
#     () => {
#         document.querySelectorAll('[data-voyager-rect-index]').forEach(el => el.remove());
#     }
# """)            
                await asyncio.sleep(3)
                # print(data)
            finally:
                if task_page:
                    await task_page.close()
                    
    async def get_page_web_element_rect(self, page: Page):
        all_indexes = await page.evaluate(self.scripts)
        print(all_indexes)
        return all_indexes

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
        # No browser to stop, context is managed externally
        pass
