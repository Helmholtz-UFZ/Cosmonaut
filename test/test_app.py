"""Test the Dash app with Playwright."""

import time

import pytest


def check_all_errors(page):
    """Check for errors on the page.

    This function checks for:
    - Console errors (SEVERE/ERROR level, excluding favicon errors)
    - JavaScript errors
    - Broken images
    """
    time.sleep(1)  # Allow page to load
    errors = []

    # Console errors - get from browser console logs
    console_logs = page.context.pages[0].evaluate(
        """() => {
            return window.__CONSOLE_LOGS__ || [];
        }"""
    )

    # Filter severe/error console messages
    console_errors = [
        log
        for log in console_logs
        if isinstance(log, dict)
        and log.get("level") in ["SEVERE", "ERROR"]
        and "favicon" not in str(log.get("message", "")).lower()
    ]
    if console_errors:
        errors.extend([f"Console: {log['message']}" for log in console_errors])

    # JavaScript errors - check for error elements or window.jsErrors
    js_errors = page.evaluate(
        """() => {
            const errors = window.jsErrors || [];
            const errorElements = Array.from(document.querySelectorAll('[data-error]'))
                .map(el => el.dataset.error);
            return errors.concat(errorElements);
        }"""
    )
    if js_errors:
        errors.extend([f"JS Error: {err}" for err in js_errors if err])

    # Wait for images to load
    page.wait_for_load_state("networkidle", timeout=5000)

    # Check for broken images
    broken_images = page.evaluate(
        """() => {
            return Array.from(document.querySelectorAll('img'))
                .filter(img => img.complete && img.naturalWidth === 0 && img.src !== '')
                .map(img => img.src);
        }"""
    )
    if broken_images:
        errors.extend([f"Broken image: {img}" for img in broken_images])

    if errors:
        pytest.fail("Errors detected:\n" + "\n".join(errors))


def test_homepage_loads(page, dash_app):
    """Test that the homepage loads without errors."""
    # Navigate to the homepage
    page.goto("http://localhost:8050")

    # Check for any errors on the page
    check_all_errors(page)
