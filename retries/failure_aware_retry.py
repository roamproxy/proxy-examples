"""Retry logic that distinguishes between failure types.

    pip install httpx

Most retry loops treat every failure the same: sleep, try again, give up after N
attempts. That wastes the run budget on hard blocks (which never open) and gives
up too early on transport noise (which usually clears immediately).

Four cases, three different responses:

    429 + Retry-After  -> sleep exactly that long, same identity
    429 (no header)    -> exponential backoff with jitter
    401/403/407/451    -> do not retry unchanged; rotate identity or shelve it
    timeout / reset    -> retry fast, twice, then give up

The HostBudget below is the part that actually prevents blocks: some targets
count total requests rather than rate, so no backoff schedule saves you. Cap
yourself below the number that killed the last run.

Set ROAM_USER and ROAM_PASS in your environment first.
"""
import os
import random
import time
from collections import defaultdict, deque

import httpx

USER = os.environ["ROAM_USER"]
PASS = os.environ["ROAM_PASS"]
GATEWAY = "gw.roamproxy.com:41080"

HARD_BLOCK = {401, 403, 407, 451}
RETRYABLE_STATUS = {500, 502, 503, 504}


class BlockedError(RuntimeError):
    """Hard rejection — retrying the same request unchanged cannot help."""


def classify(exc_or_resp) -> str:
    if isinstance(exc_or_resp, httpx.HTTPError):
        return "transport"
    code = exc_or_resp.status_code
    if code in HARD_BLOCK:
        return "blocked"
    if code == 429:
        return "throttled"
    if code in RETRYABLE_STATUS:
        return "server"
    return "ok" if code < 400 else "fatal"


def sleep_for(kind: str, attempt: int, resp=None) -> float:
    if kind == "throttled":
        retry_after = (resp.headers.get("retry-after") if resp else None) or ""
        if retry_after.isdigit():
            return int(retry_after)
        return min(60, 5 * 2**attempt) + random.uniform(0, 2)
    if kind == "server":
        return min(30, 2**attempt) + random.uniform(0, 1)
    if kind == "transport":
        return 0.5
    return 0.0


class HostBudget:
    """Rolling request counter per host. Refuses before the server does."""

    def __init__(self, max_requests: int = 200, window_seconds: int = 3600):
        self.max = max_requests
        self.window = window_seconds
        self.hits = defaultdict(deque)

    def allow(self, host: str) -> bool:
        now = time.time()
        q = self.hits[host]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max:
            return False
        q.append(now)
        return True

    def spent(self, host: str) -> int:
        return len(self.hits[host])


def session_client(session_id: str) -> httpx.Client:
    """One sticky exit IP for the life of this client."""
    username = f"{USER}-country-us-session-{session_id}"
    return httpx.Client(proxy=f"http://{username}:{PASS}@{GATEWAY}", timeout=20)


def fetch(client: httpx.Client, url: str, budget: HostBudget, max_attempts: int = 4):
    host = httpx.URL(url).host
    if not budget.allow(host):
        raise RuntimeError(f"self-imposed budget reached for {host}")

    for attempt in range(max_attempts):
        try:
            resp = client.get(url)
        except httpx.HTTPError as exc:
            if attempt >= 2:
                raise
            time.sleep(sleep_for(classify(exc), attempt))
            continue

        kind = classify(resp)
        if kind == "ok":
            return resp
        if kind == "blocked":
            # Record the ceiling for this host, then change identity or move on.
            raise BlockedError(f"{host} blocked after {budget.spent(host)} requests")
        if kind == "fatal":
            resp.raise_for_status()
        time.sleep(sleep_for(kind, attempt, resp))

    raise RuntimeError(f"exhausted attempts for {url}")


if __name__ == "__main__":
    budget = HostBudget(max_requests=50, window_seconds=600)
    client = session_client("retry-demo")

    try:
        r = fetch(client, "https://ipinfo.io/json", budget)
        print(r.json()["ip"])
    except BlockedError as exc:
        # A new session id means a new exit IP — the only retry worth making here.
        print(f"{exc}; rotating identity")
        client = session_client("retry-demo-2")
        print(fetch(client, "https://ipinfo.io/json", budget).json()["ip"])
