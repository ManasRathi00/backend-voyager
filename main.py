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
    browser_pool = BrowserPool(launch_options={"headless" : False})
    await browser_pool.start() # Start the browser pool

    # Create Voyager instance (no longer launches browser)
    voyager = await Voyager.create()

    # Define dummy VoyagerTasks
    task_1 = VoyagerTask(
        start_url="https://www.cruxal.in/",
        prompt="Login to cruxal and get data."
    )


    await asyncio.gather(
        execute_voyager_task(browser_pool,voyager, task_1),

    )

    await browser_pool.stop() # Stop the browser pool

if __name__ == "__main__":
    asyncio.run(main())
