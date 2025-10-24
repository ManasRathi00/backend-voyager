from playwright.async_api import Page, Locator
from typing import Optional

async def execute_go_back(page : Page, element : Optional[Locator] = None, content : Optional[str] = None):
    await page.go_back()
