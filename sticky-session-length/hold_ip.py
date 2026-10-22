"""How long a RoamProxy sticky session keeps its exit IP, and how to choose that length.

A username with `-session-<id>` keeps the same exit IP for about 10 minutes by default.
Append `-sesstime-<minutes>` (10 to 120) to hold it longer. Change the session id to get
a new IP right away; omit `-session-...` to rotate on every request.

If the residential device behind your IP goes offline, the session moves to a new IP in the
same region before the time is up. For an IP that never changes, use a static IP instead.

Usage:
    export ROAM_USER="your-username"
    export ROAM_PASS="your-password"
    python hold_ip.py                 # default hold (~10 min)
    python hold_ip.py --minutes 30    # hold the IP for up to 30 minutes
"""

from __future__ import annotations

import argparse
import os
import time
import uuid

import requests

GATEWAY = "gw.roamproxy.com:41080"
ECHO_URL = "https://api.ipify.org"


def username(base: str, country: str | None, session: str | None, minutes: int | None) -> str:
    """Build the proxy username. Order: country, then session, then sesstime."""
    user = base
    if country:
        user += f"-country-{country}"
    if session:
        user += f"-session-{session}"
        if minutes:
            user += f"-sesstime-{minutes}"   # only meaningful together with a session
    return user


def exit_ip(user: str, password: str) -> str:
    proxy = f"http://{user}:{password}@{GATEWAY}"
    r = requests.get(ECHO_URL, proxies={"http": proxy, "https": proxy}, timeout=30)
    r.raise_for_status()
    return r.text.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="us")
    ap.add_argument("--minutes", type=int, default=None, help="10-120; omit for the ~10 min default")
    ap.add_argument("--checks", type=int, default=5)
    ap.add_argument("--interval", type=int, default=60, help="seconds between checks")
    args = ap.parse_args()

    base, password = os.environ["ROAM_USER"], os.environ["ROAM_PASS"]
    sid = uuid.uuid4().hex[:8]
    user = username(base, args.country, sid, args.minutes)
    print(f"session {sid}, hold {args.minutes or 'default (~10)'} min")

    first = None
    for i in range(args.checks):
        ip = exit_ip(user, password)
        first = first or ip
        print(f"  check {i + 1}: {ip}{'' if ip == first else '  <- changed'}")
        if i + 1 < args.checks:
            time.sleep(args.interval)

    # A new session id means a new IP immediately; no need to wait out the timer.
    new_ip = exit_ip(username(base, args.country, uuid.uuid4().hex[:8], args.minutes), password)
    print(f"new session id -> {new_ip}")


if __name__ == "__main__":
    main()
