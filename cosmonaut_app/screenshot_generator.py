"""Screenshot generator for COSMONAUT documentation using Playwright."""

import logging
import time
from pathlib import Path
from typing import Tuple

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

# Import page lists from doc_pages_config (single source of truth)
from cosmonaut_app.doc_pages_config import USER_WORKFLOW_PAGES, ADMIN_PAGES

# Page URL configuration: maps module_name -> (url_path, wait_seconds)
# This is the ONLY place where URLs and timing need to be configured
PAGE_CONFIG = {
    # User workflow pages
    "home": ("/", 1),
    "user_info": ("/job/{job_id}/user-info", 2),
    "data_upload": ("/job/{job_id}/data-upload", 3),
    "street_selection": ("/job/{job_id}/street_selection", 5),
    "routing_params": ("/job/{job_id}/routing-params", 2),
    "route_computation": ("/job/{job_id}/route-computation", 3),
    "route_download": ("/job/{job_id}/route-download", 3),
    # Admin pages
    "logs": ("/logs", 1),
    "worker_management": ("/worker-management", 2),
    "job_manager": ("/job-manager", 2),
}


def build_pages_to_screenshot() -> list[Tuple[int, str, str, str]]:
    """Build screenshot list from doc_generator page lists.

    This ensures page lists stay in sync - if a page is added to documentation,
    it must also have a URL configured in PAGE_CONFIG, otherwise this will raise
    an error.

    Returns:
        List of tuples: (wait_seconds, module_name, url_path, display_title)

    Raises:
        KeyError: If a page in doc_generator lists is missing from PAGE_CONFIG
    """
    pages = []

    # Build from user workflow pages
    for module_name, display_title in USER_WORKFLOW_PAGES:
        if module_name not in PAGE_CONFIG:
            raise KeyError(
                f"Page '{module_name}' is in USER_WORKFLOW_PAGES but missing from "
                f"PAGE_CONFIG in screenshot_generator.py. Add URL and timing configuration."
            )
        url_path, wait_seconds = PAGE_CONFIG[module_name]
        pages.append((wait_seconds, module_name, url_path, display_title))

    # Build from admin pages
    for module_name, display_title in ADMIN_PAGES:
        if module_name not in PAGE_CONFIG:
            raise KeyError(
                f"Page '{module_name}' is in ADMIN_PAGES but missing from "
                f"PAGE_CONFIG in screenshot_generator.py. Add URL and timing configuration."
            )
        url_path, wait_seconds = PAGE_CONFIG[module_name]
        pages.append((wait_seconds, module_name, url_path, display_title))

    return pages


# Build the screenshot list dynamically from doc_generator lists
# This will raise an error at import time if lists are out of sync
PAGES_TO_SCREENSHOT = build_pages_to_screenshot()


class ScreenshotGenerator:
    """Automate screenshot capture for documentation pages using Playwright.

    This class handles browser automation to capture screenshots of all COSMONAUT
    pages for inclusion in the generated documentation. It uses Playwright to
    navigate to each page, wait for content to load, and capture high-quality
    screenshots.
    """

    def __init__(
        self,
        job_id: str,
        headless: bool = True,
        viewport_size: Tuple[int, int] = (1920, 1080),
        base_url: str = "http://localhost:8080",
    ):
        """Initialize the screenshot generator.

        Args:
            job_id: Job ID with complete workflow data for page screenshots
            headless: Run browser in headless mode (default: True)
            viewport_size: Browser viewport dimensions (default: 1920x1080)
            base_url: Base URL of the running COSMONAUT application
        """
        self.job_id = job_id
        self.headless = headless
        self.viewport_size = viewport_size
        self.base_url = base_url

        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

        logging.info(
            f"Screenshot generator initialized for job_id: {job_id}",
            extra={"tag": "frontend"},
        )

    def setup_browser(self) -> Page:
        """Configure and launch Playwright browser.

        Returns:
            Playwright Page object ready for navigation
        """
        logging.info("Starting Playwright browser", extra={"tag": "frontend"})

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=self.headless, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        self.context = self.browser.new_context(
            viewport={"width": self.viewport_size[0], "height": self.viewport_size[1]}
        )

        self.page = self.context.new_page()

        logging.info(
            f"Browser launched (headless={self.headless}, "
            f"viewport={self.viewport_size[0]}x{self.viewport_size[1]})",
            extra={"tag": "frontend"},
        )

        return self.page

    def wait_for_page_ready(self, timeout: int = 10) -> bool:
        """Wait for Dash callbacks and page content to fully load.

        Waits for:
        - Dash callback updates to complete (_dash-updating)
        - Network to become idle
        - All images to load

        Args:
            timeout: Maximum wait time in seconds (default: 10)

        Returns:
            True if page loaded successfully, False otherwise
        """
        try:
            # Wait for Dash to stop updating (Dash adds ._dash-updating class during callbacks)
            try:
                self.page.wait_for_selector(
                    "._dash-updating", state="detached", timeout=timeout * 1000
                )
            except Exception:
                # If _dash-updating never appears, that's fine - no callbacks running
                pass

            # Wait for network idle
            self.page.wait_for_load_state("networkidle", timeout=timeout * 1000)

            # Wait for all images to load
            self.page.evaluate("""
                () => Promise.all(
                    Array.from(document.images)
                        .filter(img => !img.complete)
                        .map(img => new Promise(resolve => {
                            img.onload = img.onerror = resolve;
                        }))
                )
            """)

            logging.info("Page fully loaded", extra={"tag": "frontend"})
            return True

        except Exception as e:
            logging.warning(
                f"Page load timeout or error: {e}", extra={"tag": "frontend"}
            )
            return False

    def capture_screenshot(
        self,
        page_name: str,
        page_url: str,
        output_dir: Path,
        init_wait_time: int,
    ) -> None:
        """Navigate to a page and capture a screenshot.

        Args:
            page_name: Module name for the output file (e.g., 'home', 'data_upload')
            page_url: URL path to navigate to (can include {job_id} placeholder)
            output_dir: Directory to save the screenshot
            init_wait_time: Initial wait time in seconds before capturing

        Raises:
            ValueError: If page returns 404 Not Found
            Exception: If screenshot capture fails for other reasons
        """
        # Substitute job_id in URL if needed
        if "{job_id}" in page_url:
            page_url = page_url.format(job_id=self.job_id)

        full_url = f"{self.base_url}{page_url}"
        output_path = output_dir / f"{page_name}.png"

        logging.info(
            f"Capturing screenshot: {page_name} from {full_url}",
            extra={"tag": "frontend"},
        )

        try:
            # Navigate to page and capture response
            response = self.page.goto(
                full_url, wait_until="domcontentloaded", timeout=30000
            )

            # CRITICAL: Check for 404 errors
            if response and response.status == 404:
                error_msg = (
                    f"\n{'='*80}\n"
                    f"ERROR: 404 Not Found for page '{page_name}'\n"
                    f"URL: {full_url}\n"
                    f"{'='*80}\n"
                    f"This means the URL in PAGE_CONFIG does not match the actual page route.\n"
                    f"Check the 'path' or 'path_template' in cosmonaut_app/pages/{page_name}.py\n"
                    f"and update PAGE_CONFIG in screenshot_generator.py accordingly.\n"
                    f"{'='*80}\n"
                )
                logging.error(error_msg, extra={"tag": "frontend"})
                raise ValueError(error_msg)

            # Check for other HTTP errors (5xx, etc.)
            if response and response.status >= 400:
                error_msg = (
                    f"HTTP {response.status} error for page '{page_name}' at {full_url}"
                )
                logging.error(error_msg, extra={"tag": "frontend"})
                raise ValueError(error_msg)

            # Initial wait for page-specific content
            time.sleep(init_wait_time)

            # Wait for Dash callbacks and content
            self.wait_for_page_ready(timeout=15)

            # Capture screenshot
            self.page.screenshot(path=str(output_path), full_page=False)

            logging.info(f"Screenshot saved: {output_path}", extra={"tag": "frontend"})

        except ValueError:
            # Re-raise ValueError (404 errors) without wrapping
            raise
        except Exception as e:
            logging.error(
                f"Failed to capture screenshot for {page_name}: {e}",
                extra={"tag": "frontend"},
            )
            raise

    def generate_all_screenshots(self, output_dir: Path) -> None:
        """Generate screenshots for all documented pages.

        Args:
            output_dir: Directory to save all screenshots

        Raises:
            Exception: If any screenshot capture fails
        """
        # Setup browser
        self.setup_browser()

        logging.info(
            f"Generating screenshots for {len(PAGES_TO_SCREENSHOT)} pages",
            extra={"tag": "frontend"},
        )

        try:
            for wait_time, page_name, page_url, page_title in PAGES_TO_SCREENSHOT:
                self.capture_screenshot(page_name, page_url, output_dir, wait_time)

            logging.info(
                "All screenshots captured successfully", extra={"tag": "frontend"}
            )

        except Exception as e:
            logging.error(
                f"Screenshot generation failed: {e}", extra={"tag": "frontend"}
            )
            raise
        finally:
            # Always cleanup even if screenshots fail
            self.cleanup()

    def cleanup(self) -> None:
        """Close browser and cleanup resources."""
        logging.info("Cleaning up Playwright resources", extra={"tag": "frontend"})

        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

        logging.info("Cleanup complete", extra={"tag": "frontend"})
