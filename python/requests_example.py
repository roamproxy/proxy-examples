"""Rotating and sticky RoamProxy sessions with the `requests` library.

    pip install requests

Set ROAM_USER and ROAM_PASS in your environment first.
"""
import os

import requests

USER = os.environ["ROAM_USER"]
PASS = os.environ["ROAM_PASS"]
GATEWAY = "gw.roamproxy.com:41080"


def proxy_url(username: str) -> str:
    return f"http://{username}:{PASS}@{GATEWAY}"


def get_ip(username: str) -> dict:
    proxies = {"http": proxy_url(username), "https": proxy_url(username)}
    return requests.get("https://ipinfo.io/json", proxies=proxies, timeout=30).json()


if __name__ == "__main__":
    # Fresh rotating IP in the US on every request (no session id).
    print("rotating:", get_ip(f"{USER}-country-us")["ip"])
    print("rotating:", get_ip(f"{USER}-country-us")["ip"])

    # Sticky IP: same exit as long as you reuse the session id.
    sticky = f"{USER}-country-gb-session-demo42"
    print("sticky:  ", get_ip(sticky)["ip"])
    print("sticky:  ", get_ip(sticky)["ip"])
