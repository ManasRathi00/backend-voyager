from playwright.async_api import Page, Locator
from typing import Optional

async def execute_click(page : Page, element : Optional[Locator], content : Optional[str] = None):
    if element:
        # Before clicking, remove target="_blank" to prevent new tabs
        await element.evaluate("""(el) => {
            if (el.tagName === 'A' && el.getAttribute('target') === '_blank') {
                el.removeAttribute('target');
            }
        }""")
        await element.click()
    else:
        raise ValueError("Element not provided for click action.")
