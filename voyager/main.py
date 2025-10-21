import asyncio
import litellm
from playwright.async_api import async_playwright, Playwright




class Voyager:
    pass


async def run(playwright: Playwright):
    chromium = playwright.chromium # or "firefox" or "webkit".
    browser = await chromium.launch(headless=False)
    page = await browser.new_page()
    await page.goto("http://google.com")
    # other actions...
    await asyncio.sleep(10)
    await browser.close()

async def main():
    async with async_playwright() as playwright:
        await run(playwright)
asyncio.run(main())