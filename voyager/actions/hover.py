from playwright.async_api import Page, Locator
from typing import Optional

async def execute_hover(page : Page, element : Optional[Locator], content : Optional[str] = None):
    if element:
        await element.hover()
    else:
        raise ValueError("Element not provided for hover action.")
