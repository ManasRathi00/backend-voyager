import asyncio
from playwright.async_api import async_playwright
from voyager import Voyager
from voyager.types import VoyagerTask

async def main():
    async with async_playwright() as playwright:
        # Create Voyager instance
        voyager = await Voyager.create(playwright)

        # Define a dummy VoyagerTask
        task = VoyagerTask(
            start_url="https://www.google.com",
            prompt="Just open Google."
        )

        # Start a browser for this task
        await voyager.start_task(task, headless=False)  # headless=False so you can see it open

        # # Use the Playwright browser/page directly
        # context = await voyager.browser.new_context()
        # page = await context.new_page()
        # await page.goto(task.start_url)
        # print(f"Opened page title: {await page.title()}")

        # await asyncio.sleep(3)  # wait a few seconds so you can see it open
        # await voyager.stop()  # close browser

if __name__ == "__main__":
    asyncio.run(main())