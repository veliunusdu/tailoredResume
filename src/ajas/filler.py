"""
Playwright Form Filler for Greenhouse and Lever.
"""

from typing import Any, Dict

from ajas.logger import log


async def fill_application(page_handler: Any, url: str, master_cv: Dict[str, Any]):
    """
    Detect the platform (Greenhouse/Lever) and fill basic info.
    Does NOT click submit.
    """
    log.info(f"Navigating to {url} for auto-fill...")
    await page_handler.goto(url)

    # Wait for the page or form to load
    await page_handler.wait_for_load_state("networkidle")

    pii = master_cv.get("pii", {})
    full_name = pii.get("[[FULL_NAME]]", "")
    email = pii.get("[[EMAIL]]", "")
    phone = pii.get("[[PHONE]]", "")
    linkedin = pii.get("[[LINKEDIN]]", "")

    # Detect Platform
    html = await page_handler.content()

    if "greenhouse.io" in url or "application_form" in html:
        log.info("Detected Greenhouse form.")
        await _fill_greenhouse(page_handler, full_name, email, phone, linkedin)
    elif "lever.co" in url or "application-form" in html:
        log.info("Detected Lever form.")
        await _fill_lever(page_handler, full_name, email, phone, linkedin)
    else:
        log.warning("Unknown job portal. Attempting generic fill...")
        await _fill_generic(page_handler, full_name, email, phone, linkedin)

    log.info("Auto-fill complete. Pausing for human review...")
    # Open Playwright Inspector for manual check before submission
    try:
        await page_handler.pause()
    except Exception as e:
        log.warning(f"Could not pause page (likely headless or no display): {e}")


async def _fill_greenhouse(page, name, email, phone, linkedin):
    try:
        # greenhouse typically uses id='first_name', id='last_name' or id='name'
        if await page.query_selector("#first_name"):
            names = name.split(" ")
            await page.fill("#first_name", names[0])
            if len(names) > 1:
                await page.fill("#last_name", " ".join(names[1:]))
        elif await page.query_selector("#name"):
            await page.fill("#name", name)

        await page.fill("#email", email)
        await page.fill("#phone", phone)

        # Linkdin field often has 'linkedin' in name or id
        li_field = await page.query_selector("input[name*='linkedin'], #linkedin_url")
        if li_field:
            await li_field.fill(linkedin)

    except Exception as e:
        log.error(f"Greenhouse fill error: {e}")


async def _fill_lever(page, name, email, phone, linkedin):
    try:
        await page.fill("input[name='name']", name)
        await page.fill("input[name='email']", email)
        await page.fill("input[name='phone']", phone)
        await page.fill("input[name='urls[LinkedIn]']", linkedin)
    except Exception as e:
        log.error(f"Lever fill error: {e}")


async def _fill_generic(page, name, email, phone, linkedin):
    """Fallback: try common input names."""
    try:
        for selector in ["input[name*='name']", "input[id*='name']"]:
            element = await page.query_selector(selector)
            if element:
                await element.fill(name)

        for selector in ["input[name*='email']", "input[type='email']"]:
            element = await page.query_selector(selector)
            if element:
                await element.fill(email)
    except Exception:
        pass
