from playwright.async_api import Page, Locator
from typing import Optional

async def execute_type(page : Page, element : Optional[Locator], content : Optional[str] = None):
    if element and content is not None:
        await element.clear()
        await element.type(content, delay=45)
    else:
        raise ValueError("Element or content not provided for type action.")
