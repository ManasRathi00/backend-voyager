from playwright.async_api import Page, Locator
from typing import Optional

async def execute_scroll(page : Page, element : Optional[Locator] = None, content : Optional[str] = None):
    scroll_amount = 0.5 # Scroll by half the visible height
    if element:
        if content == "up":
            await element.evaluate(f"node => node.scrollBy(0, -node.clientHeight * {scroll_amount})")
        elif content == "down":
            await element.evaluate(f"node => node.scrollBy(0, node.clientHeight * {scroll_amount})")
    else: # Scroll the entire page
        if content == "up":
            await page.evaluate(f"window.scrollBy(0, -window.innerHeight * {scroll_amount})")
        elif content == "down":
            await page.evaluate(f"window.scrollBy(0, window.innerHeight * {scroll_amount})")
