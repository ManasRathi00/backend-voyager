from playwright.async_api import async_playwright, Playwright
from voyager import Voyager
import asyncio
async def main():
    async with async_playwright() as playwright:
        voyager = await Voyager.create(playwright)
        await voyager.start_task(None, headless = True, slow_mo = True)
        # print(voyager.scripts[:100])
        # await voyager.browser.close()
        
if __name__ == "__main__":
    asyncio.run(main())
