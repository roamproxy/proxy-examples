"""Drive a real Chromium browser through RoamProxy with Playwright.

    pip install playwright
    playwright install chromium

Playwright takes the proxy at browser launch. Because credentials go in
`username`/`password` (not the URL), the sticky session id lives in the
username — so the whole browser session keeps one exit IP, which is what you
want for logins, carts, and any multi-page flow.

    ROAM_USER=your-username ROAM_PASS=your-password python roam_playwright.py

Set ROAM_USER and ROAM_PASS in your environment first.
"""
import os

from playwright.sync_api import sync_playwright

USER = os.environ["ROAM_USER"]
PASS = os.environ["ROAM_PASS"]
GATEWAY = "http://gw.roamproxy.com:41080"


def main():
    # Sticky GB exit: reuse the session id to keep the same IP for the whole run.
    username = f"{USER}-country-gb-session-browser01"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            proxy={"server": GATEWAY, "username": username, "password": PASS},
            headless=True,
        )
        page = browser.new_page()

        # Two navigations on the same sticky session return the same exit IP.
        page.goto("https://ipinfo.io/json", timeout=30000)
        print("page 1 exit:", page.inner_text("body"))
        page.goto("https://ipinfo.io/json", timeout=30000)
        print("page 2 exit:", page.inner_text("body"))

        browser.close()


if __name__ == "__main__":
    main()
