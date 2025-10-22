from __future__ import annotations  # top of file (for forward references)
from playwright.async_api import Playwright, Browser
from .prompt import SYSTEM_PROMPT
import asyncio
from typing import Optional


from .types import LaunchOptions
class Voyager:
    def __init__(self, playwright: Playwright, scripts: str, max_concurrency : int = 10, return_images : bool = True):
        self.playwright = playwright
        self.scripts = scripts
        self.max_concurrency = asyncio.Semaphore(max_concurrency)
        self.return_images = True
        
        
        self.system_prompt = None
        self.browser : Browser | None = None
        
        #init variables
        self.actions_history = []

    @classmethod
    async def create(
        cls,
        playwright: Playwright,
        max_concurrency: int = 10,
        return_images: bool = False,
        save_images: bool = False,
    ) -> "Voyager":   # 👈 THIS is the key line
        with open("voyager/browser-annotate.js", "r") as file:
            scripts = file.read()
            

        instance = cls(playwright, scripts, max_concurrency)

        return instance
    
    
    async def start_task(self, task, browser_cdp : Optional[str] = None, **kwargs: LaunchOptions):
        if browser_cdp:
            self.browser = await self.playwright.chromium.connect_over_cdp(endpoint_url=browser_cdp)
        else:
            self.browser = await self.playwright.chromium.launch(**kwargs)

        self.system_prompt = SYSTEM_PROMPT
        self.actions_history = []
        

    
    async def execute_action_click(self, web_ele):
        pass
    
    async def execute_action_scroll(self, info_content, web_ele):
        pass
    
    async def execute_action_type(self, info_content, web_ele):
        pass
    
    async def execute_action_scroll(self, scroll_ele_number,scroll_content, web_ele):
        pass
    
    async def execute_action_extract(self):
        pass
    
    async def execute_action_success(self):
        pass
