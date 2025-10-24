from playwright.async_api import Page, Locator
from typing import Optional

async def execute_click(page : Page, element : Optional[Locator], content : Optional[str] = None):
    if element:
        await element.click()
    else:
        raise ValueError("Element not provided for click action.")
