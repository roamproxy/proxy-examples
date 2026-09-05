"""Sticky sessions scoped to a unit of work: rotate at the seam, not on a timer.

Companion to: https://dev.to/roamproxy/how-long-should-you-hold-a-sticky-session-2a2b

The idea: one sticky session lives exactly as long as one coherent journey
(login -> paginate -> extract). Inside a journey you keep the IP; between
journeys rotation is free. Rotation is never scheduled -- it is driven by
three observables: an IP-scoped block, exit-IP drift, or soft degradation.

Usage:
    GATEWAY_TEMPLATE="http://user-country-us-session-{sid}:pass@gateway:7777" \
        python sticky_unit.py https://example.com/page1 https://example.com/page2
"""

from __future__ import annotations

import os
import sys
import time
import uuid

import httpx

GATEWAY_TEMPLATE = os.environ.get(
    "GATEWAY_TEMPLATE",
    "http://user-country-us-session-{sid}:pass@gateway:7777",
)
DRIFT_CHECK_EVERY = 10  # requests between origin re-checks
ECHO_URL = "https://httpbin.org/ip"


class IpDrifted(RuntimeError):
    """The exit IP under the sticky session changed mid-journey."""


class StickyUnit:
    """One sticky session bound to one unit of work."""

    def __init__(self) -> None:
        self.sid = uuid.uuid4().hex[:8]
        self.client = httpx.Client(
            proxy=GATEWAY_TEMPLATE.format(sid=self.sid),
            timeout=20,
            follow_redirects=True,
        )
        self.origin = self._origin()
        self.requests_sent = 0

    def _origin(self) -> str:
        return self.client.get(ECHO_URL, timeout=10).json()["origin"]

    def drifted(self) -> bool:
        return self._origin() != self.origin

    def get(self, url: str) -> httpx.Response:
        if self.requests_sent and self.requests_sent % DRIFT_CHECK_EVERY == 0:
            if self.drifted():
                raise IpDrifted(f"session {self.sid}: exit IP changed")
        self.requests_sent += 1
        return self.client.get(url)

    def close(self) -> None:
        self.client.close()


def run_journey(urls: list[str], max_attempts: int = 3) -> list[httpx.Response]:
    """Run one unit of work; on drift, restart cleanly on a fresh session."""
    for attempt in range(1, max_attempts + 1):
        unit = StickyUnit()
        print(f"[unit {unit.sid}] attempt {attempt}, exit={unit.origin}")
        try:
            responses = [unit.get(u) for u in urls]
        except IpDrifted as exc:
            print(f"[unit {unit.sid}] {exc}; restarting journey on a new seam")
            unit.close()
            time.sleep(2)
            continue
        finally:
            unit.close()
        return responses
    raise RuntimeError(f"journey failed after {max_attempts} drift restarts")


if __name__ == "__main__":
    targets = sys.argv[1:] or [ECHO_URL] * 3
    for resp in run_journey(targets):
        print(resp.status_code, str(resp.url))

