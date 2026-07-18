"""Playwright + RoamProxy with resource blocking — cut residential bandwidth 60-85%.

Residential traffic is billed per GB, and a typical page spends most of its
bytes on images, fonts and CSS you never parse. This example blocks those
resource types at the route layer, and rotates identity per browser context
(one sticky session id per context = one exit IP per identity).

    pip install playwright
    playwright install chromium

    ROAM_USER=your-username ROAM_PASS=your-password python roam_playwright_lean.py
"""
import os

from playwright.sync_api import sync_playwright

USER = os.environ["ROAM_USER"]
PASS = os.environ["ROAM_PASS"]
GATEWAY = "http://gw.roamproxy.com:41080"

# Keep stylesheets if you rely on :visible selectors; never block xhr/fetch —
# that's usually where the data lives.
BLOCK = {"image", "media", "font", "stylesheet"}


def register_blocking(page):
    page.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type in BLOCK
        else route.continue_(),
    )


def main():
    with sync_playwright() as p:
        # One browser process, several identities: pass `proxy=` per context.
        browser = p.chromium.launch(headless=True)
        for worker in ("w1", "w2"):
            context = browser.new_context(
                proxy={
                    "server": GATEWAY,
                    # New session id = new exit IP; same id = same IP.
                    "username": f"{USER}-country-us-session-{worker}",
                    "password": PASS,
                }
            )
            page = context.new_page()
            register_blocking(page)
            page.goto("https://httpbin.org/ip", timeout=60_000)
            print(worker, page.inner_text("body").strip())
            context.close()
        browser.close()


if __name__ == "__main__":
    main()
