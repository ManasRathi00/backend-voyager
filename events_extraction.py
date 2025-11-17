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
    voyager = Voyager(return_images=True, save_images_for_debugging=True, max_images_to_include=2, save_message_history_for_debugging=True, mimic_human_behaviour=True)

    # Define dummy VoyagerTasks
    task_1 = VoyagerTask(
        start_url="https://www.businesswire.com/news/home/20251106844216/en/Paymentus-to-Participate-in-Upcoming-Investor-Conferences-in-November",
        prompt='''
This is a press release about an upcoming investor relations earnings call event.

TASK: Find the actual webcast streaming link where the live event will occur.

INSTRUCTIONS:
1. First, scan the entire press release for any links containing keywords like:
   - "webcast"
   - "live stream"
   - "earnings call"
   - "investor relations"
   - "listen to the call"

2. Look for links to major IR platforms such as:
   - Q4 (q4inc.com, q4web.com)
   - Webcasts.com
   - Events platforms (event.on24.com, events.q4inc.com)
   - Investis Digital
   - IR website (typically ir.companyname.com)
   - Conference call providers

3. If you find a potential webcast link:
   - Navigate to that link
   - Scroll through the entire page to locate the final streaming destination
   - Look for registration pages, event details, or embedded player links
   - The final link should be where participants will actually watch/listen to the event

4. Search behavior:
   - Scroll down and explore the full page if content is not immediately visible
   - Check for "Register," "Join Webcast," or "Listen Live" buttons
   - If redirected, follow through to find the ultimate streaming page
   

5. Return the final webcast URL where the event will be streamed, NOT just the announcement page.

Make sure to get a call that is in the future! Refer to today's date, navigate to calls that are just in the future

NOTE: The link you're looking for is typically NOT the press release itself, but rather a dedicated event page on an IR platform.
''',
        
    )
    # task_2 = VoyagerTask(
    #     start_url="https://github.com",
    #     prompt="""
    #     Extract the top github repos on the topic of portfolio dev pages in react
        
    #     """
    # )


    await asyncio.gather(
        execute_voyager_task(browser_pool,voyager, task_1),

    )

    await browser_pool.stop() # Stop the browser pool

if __name__ == "__main__":
    asyncio.run(main())
