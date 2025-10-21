from __future__ import annotations  # top of file (for forward references)
from playwright.async_api import Playwright, Browser
from .prompts import SYSTEM_PROMPT
import asyncio

class Voyager:
    def __init__(self, playwright: Playwright, scripts: str, browser : Browser, system_prompt : str):
        self.playwright = playwright
        self.scripts = scripts
        self.system_prompt = system_prompt
        self.browser : Browser = browser
        self.new_page = None
        self.max_tasks_semaphore = None

    @classmethod
    async def create(
        self,
        playwright: Playwright,
        max_tasks: int = 10,
        return_images: bool = False,
        save_images: bool = False,
    ) -> "Voyager":   # 👈 THIS is the key line
        with open("voyager/browser-annotate.js", "r") as file:
            scripts = file.read()
            

        browser = await playwright.chromium.launch()
        instance = self(playwright, scripts, browser, SYSTEM_PROMPT)


        instance.new_page = await browser.new_page()
        await instance.new_page.evaluate(instance.scripts)
        instance.max_tasks_semaphore = asyncio.Semaphore(max_tasks)

        return instance