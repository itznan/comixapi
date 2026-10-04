"""
src/browser_worker.py - Managed Playwright daemon with persistent context,
dynamic engine detection, proxy routing, and behavioral latency.
"""
import os
import re
import random
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from playwright.async_api import async_playwright, BrowserContext, Playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    Playwright = None
    BrowserContext = None

logger = logging.getLogger(__name__)


def map_user_agent_to_impersonate(ua_string: str) -> str:
    """Extract major Chrome/Edge/Firefox version and map to closest curl_cffi impersonate target."""
    if not ua_string:
        return "chrome"

    # Match Chrome version
    match = re.search(r"Chrome/(\d+)", ua_string)
    if match:
        major = int(match.group(1))
        # Map known curl_cffi targets
        if major >= 131:
            return "chrome131"
        elif major >= 124:
            return "chrome124"
        elif major >= 120:
            return "chrome120"
        elif major >= 116:
            return "chrome116"
        elif major >= 110:
            return "chrome110"
        elif major >= 104:
            return "chrome104"
        return "chrome"

    # Match Safari version
    if "Safari" in ua_string and "Chrome" not in ua_string:
        return "safari15_5"

    return "chrome"


class PlaywrightWorker:
    """Manages persistent browser lifecycle, humanistic delays, and session synchronization."""

    def __init__(
        self,
        profile_dir: Optional[str] = None,
        headless: bool = True,
        refresh_interval: int = 1800,
        proxy: Optional[Dict[str, str]] = None
    ):
        self.profile_dir = Path(profile_dir) if profile_dir else (Path.home() / ".cache" / "comixapi" / "profile")
        self.headless = headless
        self.refresh_interval = refresh_interval
        self.proxy = proxy

        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._bg_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self.detected_impersonate_target = "chrome"

    async def start(self, use_persistent_profile: bool = True):
        """Boot persistent Playwright Chromium context."""
        if not HAS_PLAYWRIGHT:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return

        if self._playwright is not None:
            return

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()

        # Prefer installed Google Chrome over Chrome for Testing to avoid test binary flags
        chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        use_chrome_channel = os.path.exists(chrome_exe)

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]

        context_kwargs = {
            "user_data_dir": str(self.profile_dir),
            "headless": self.headless,
            "args": launch_args,
            "ignore_default_args": ["--enable-automation"],
            "viewport": {"width": 1366, "height": 768},
        }

        if use_chrome_channel:
            context_kwargs["channel"] = "chrome"

        if self.proxy:
            context_kwargs["proxy"] = self.proxy

        self._context = await self._playwright.chromium.launch_persistent_context(**context_kwargs)
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        logger.info(f"Playwright worker initialized with profile at {self.profile_dir}")

    async def _simulate_human_behavior(self, page):
        """Execute non-linear micro-interactions and jittered delays."""
        # 1. Random cognitive jitter
        await asyncio.sleep(random.uniform(0.8, 2.2))

        # 2. Smooth natural mouse jitter
        try:
            start_x, start_y = random.randint(100, 400), random.randint(100, 300)
            end_x, end_y = random.randint(500, 900), random.randint(400, 600)
            await page.mouse.move(start_x, start_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.move(end_x, end_y, steps=random.randint(5, 12))
        except Exception:
            pass

        # 3. Micro scroll
        try:
            await page.mouse.wheel(0, random.randint(80, 240))
            await asyncio.sleep(random.uniform(0.5, 1.2))
        except Exception:
            pass

    async def fetch(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Navigate to a target URL in a managed browser page and return content metadata."""
        if not self._context:
            await self.start()

        timeout_ms = timeout or 30_000
        async with self._lock:
            page = await self._context.new_page()
            try:
                response = await page.goto(
                    url,
                    wait_until=wait_until,
                    timeout=timeout_ms
                )
                await self._simulate_human_behavior(page)
                status = response.status if response else 200
                title = await page.title()
                html = await page.content()

                return {
                    "url": page.url,
                    "status": status,
                    "title": title,
                    "html": html,
                }
            finally:
                await page.close()

    async def sync_session(self, target_url: str = "https://comix.to") -> Dict[str, Any]:
        """Navigate to target site, wait for completion, and extract session payload."""
        if not self._context:
            await self.start()

        async with self._lock:
            page = await self._context.new_page()
            try:
                response = await page.goto(target_url, wait_until="domcontentloaded", timeout=45_000)
                await self._simulate_human_behavior(page)

                cookies = await self._context.cookies()
                cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                user_agent = await page.evaluate("navigator.userAgent")
                self.detected_impersonate_target = map_user_agent_to_impersonate(user_agent)

                return {
                    "cookies": cookie_str,
                    "cookie_list": cookies,
                    "user_agent": user_agent,
                    "impersonate_target": self.detected_impersonate_target,
                    "proxy": self.proxy.get("server") if self.proxy else None,
                    "url": page.url,
                    "title": await page.title(),
                    "status": response.status if response else 200
                }
            finally:
                await page.close()

    async def start_background_loop(self, session_broker, target_url: str = "https://comix.to"):
        """Periodic background refresh loop to keep session tokens warm."""
        async def _loop():
            while True:
                try:
                    logger.info("Background session refresh triggered...")
                    session_payload = await self.sync_session(target_url)
                    await session_broker.set_session(payload=session_payload, ttl=self.refresh_interval * 2)
                    logger.info("Session state refreshed in broker.")
                except Exception as e:
                    logger.error(f"Background session sync error: {e}")

                await asyncio.sleep(self.refresh_interval)

        self._bg_task = asyncio.create_task(_loop())

    async def close(self):
        """Clean up tasks and browser context."""
        if self._bg_task:
            self._bg_task.cancel()
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


BrowserWorker = PlaywrightWorker
