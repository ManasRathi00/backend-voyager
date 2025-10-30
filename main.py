import asyncio
from voyager import Voyager
from voyager.types import VoyagerTask

from services.browser_pool import BrowserPool # Import the browser_pool instance

async def execute_voyager_task(browser_pool : BrowserPool, voyager_instance: Voyager, task: VoyagerTask):
    """
    Gets a browser context from the pool and executes a Voyager task within it.
    """
    async with browser_pool.get_context() as context:
        await voyager_instance.start_task(context, task)

async def main():
    browser_pool = BrowserPool(launch_options={"headless" : False}, enable_anti_bot=True)
    await browser_pool.start() # Start the browser pool

    # Create Voyager instance (no longer launches browser)
    voyager = Voyager(return_images=True)

    # Define dummy VoyagerTasks
    task_1 = VoyagerTask(
        start_url="https://www.businesswire.com/news/home/20251022069147/en/Tesla-Releases-Third-Quarter-2025-Financial-Results",
        prompt="This is a press release about tesla, I want the link of the latest IR call",
        
    )
    task_2 = VoyagerTask(
        start_url="https://news.ycombinator.com/",
        prompt="""
        Go to Hacker News Show Tab
        
        Then get the top news from the last one month (30 days)
        Try to get the links from the elements as well?
        
        
        """
    )


    await asyncio.gather(
        execute_voyager_task(browser_pool,voyager, task_2),

    )

    await browser_pool.stop() # Stop the browser pool

if __name__ == "__main__":
    asyncio.run(main())
