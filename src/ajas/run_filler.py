import asyncio

from playwright.async_api import async_playwright

from ajas.filler import fill_application
from ajas.logger import log


def run_filler_sync(url: str, master_cv: dict):
    """Bridge for Streamlit to run the async Playwright filler."""

    async def _run():
        async with async_playwright() as p:
            # We use headless=False so the user can see/take over
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                await fill_application(page, url, master_cv)
                # Keep browser open for user review
                log.info("Browser is open. Close it manually when done.")
                # We wait until the page is closed or a long timeout
                while True:
                    if page.is_closed():
                        break
                    await asyncio.sleep(1)
            except Exception as e:
                log.error(f"Filler execution failed: {e}")
            finally:
                await browser.close()

    asyncio.run(_run())
