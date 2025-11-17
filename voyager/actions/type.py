from playwright.async_api import Page, Locator
from typing import Optional
import random
async def execute_type(page : Page, element : Optional[Locator], content : Optional[str] = None):
    if element and content is not None:
        await element.type(content, delay=random.randint(40, 90))
    else:
        raise ValueError("Element or content not provided for type action.")
