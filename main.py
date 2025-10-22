import asyncio
from playwright.async_api import async_playwright
from voyager import Voyager
from voyager.types import VoyagerTask

async def main():
    async with async_playwright() as playwright:
        # Create Voyager instance, launching the browser here
        voyager = await Voyager.create(playwright, headless=False) # headless=False so you can see it open

        # Define a dummy VoyagerTask
        task_1 = VoyagerTask(
            start_url="https://www.google.com/",
            prompt="Just open Google."
        )
        task_2 = VoyagerTask(
            start_url="https://www.google.com",
            prompt="Just open Google."
        )


        await asyncio.gather(voyager.start_task(task_1), voyager.start_task(task_2))

        # The browser will be closed automatically by the 'async with voyager:' block
        # No need for explicit voyager.stop() here.

if __name__ == "__main__":
    asyncio.run(main())
