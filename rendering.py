import logging

logger = logging.getLogger(__name__)


def render_with_playwright(url, timeout_secs=30, proxies=None):
    """Render page using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "Playwright package not installed. Try running: pip install playwright"
        )
        raise

    with sync_playwright() as p:
        # Map proxy dictionary (protocol -> proxy_url) to Playwright's format
        playwright_proxy = None
        if proxies:
            # Playwright expects a dict with 'server', 'username', 'password'
            # e.g., proxies = {'http': 'http://127.0.0.1:8118'}
            proxy_url = proxies.get("http") or proxies.get("https")
            if proxy_url:
                playwright_proxy = {"server": proxy_url}

        browser = p.chromium.launch(headless=True, proxy=playwright_proxy)
        try:
            page = browser.new_page()
            # Playwright timeout is in milliseconds
            page.goto(url, timeout=timeout_secs * 1000, wait_until="networkidle")
            content = page.content()
            return content
        finally:
            browser.close()


def render_with_selenium(url, timeout_secs=30, proxies=None):
    """Render page using Selenium."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        logger.error(
            "Selenium package not installed. Try running: pip install selenium"
        )
        raise

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    if proxies:
        proxy_url = proxies.get("http") or proxies.get("https")
        if proxy_url:
            chrome_options.add_argument(f"--proxy-server={proxy_url}")

    # Set page load timeout
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(timeout_secs)
    try:
        driver.get(url)
        content = driver.page_source
        return content
    finally:
        driver.quit()


def render_with_puppeteer(url, timeout_secs=30, proxies=None):
    """Render page using Pyppeteer."""
    try:
        import asyncio
        import pyppeteer
    except ImportError:
        logger.error(
            "Pyppeteer package not installed. Try running: pip install pyppeteer"
        )
        raise

    async def _async_render():
        args = ["--no-sandbox", "--disable-setuid-sandbox"]
        if proxies:
            proxy_url = proxies.get("http") or proxies.get("https")
            if proxy_url:
                args.append(f"--proxy-server={proxy_url}")

        browser = await pyppeteer.launch(headless=True, args=args)
        try:
            page = await browser.newPage()
            # Pyppeteer timeout is in milliseconds
            await page.goto(url, timeout=timeout_secs * 1000, waitUntil="networkidle2")
            content = await page.content()
            return content
        finally:
            await browser.close()

    # Run the coroutine in the current thread's event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # If event loop is already running in this thread, run in a separate executor/loop
        import threading

        result = [None]
        err = [None]

        def run_in_thread():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result[0] = new_loop.run_until_complete(_async_render())
            except Exception as e:
                err[0] = e

        t = threading.Thread(target=run_in_thread)
        t.start()
        t.join()
        if err[0]:
            raise err[0]
        return result[0]
    else:
        return loop.run_until_complete(_async_render())


def render_page(url, driver_type="auto", timeout_secs=30, proxies=None):
    """
    Unified entrypoint to render JavaScript heavy pages.
    Supports Playwright, Selenium, Pyppeteer with fallback.
    """
    drivers = []
    if driver_type == "auto":
        drivers = ["playwright", "selenium", "puppeteer"]
    else:
        drivers = [driver_type]

    last_error = None
    for driver in drivers:
        try:
            logger.info(f"Attempting to render JS using driver: {driver} for {url}")
            if driver == "playwright":
                return render_with_playwright(url, timeout_secs, proxies)
            elif driver == "selenium":
                return render_with_selenium(url, timeout_secs, proxies)
            elif driver == "puppeteer":
                return render_with_puppeteer(url, timeout_secs, proxies)
        except Exception as e:
            logger.warning(f"Driver '{driver}' failed to render {url}: {e}")
            last_error = e

    raise RuntimeError(f"All requested JS drivers failed. Last error: {last_error}")
