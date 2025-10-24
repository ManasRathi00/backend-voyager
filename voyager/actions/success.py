from playwright.async_api import Page, Locator
from typing import Optional

async def execute_success(page : Page, element : Optional[Locator] = None, content : Optional[str] = None):
    print(f"Task successfully completed: {content}")
    # In a real scenario, this might trigger a signal to stop the agent or report success.
