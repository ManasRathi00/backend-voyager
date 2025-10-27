from playwright.async_api import Page, Locator
from typing import Optional

async def execute_google(page : Page, element : Optional[Locator] = None, content : Optional[str] = None):
    await page.goto("https://www.google.com")
