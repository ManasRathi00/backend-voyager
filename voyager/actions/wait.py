from playwright.async_api import Page, Locator
from typing import Optional

async def execute_wait(page : Page, element : Optional[Locator] = None, content : Optional[str] = None):
    await page.wait_for_load_state("networkidle")
