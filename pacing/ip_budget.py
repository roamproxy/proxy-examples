"""Per-exit-IP pacing: concurrency cap + jittered token-bucket rate.

Companion code for "Your Residential IP Is Clean. Your Request Rate
Gives You Away." A clean residential IP still reads as a bot if the
rate, concurrency and spacing coming out of it are implausible for
one household. The unit that matters is the exit IP, so the budget
lives per sticky session, not per scraper.

Usage:
    export ROAM_USER="your-username"   # optional; without creds the
    export ROAM_PASS="your-password"   # demo runs without a proxy
    python ip_budget.py

Needs: pip install httpx
"""

import asyncio
import os
import random
import time

import httpx

GATEWAY = "gw.roamproxy.com:41080"


class IPBudget:
    """Pacing for ONE exit IP: concurrency cap + jittered token bucket.

    Acquire it around every request that leaves through that IP:

        async with budget:
            resp = await client.get(url)
            budget.note_response(resp.status_code, elapsed)
    """

    def __init__(self, max_concurrency=4, rps=2.0, jitter=0.4):
        self._sem = asyncio.Semaphore(max_concurrency)
        self._base_gap = 1.0 / rps
        self._gap_scale = 1.0          # grows when the IP looks degraded
        self._jitter = jitter
        self._next_at = 0.0
        self._lock = asyncio.Lock()
        self._slow_responses = 0

    async def __aenter__(self):
        await self._sem.acquire()
        async with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next_at - now)
            gap = self._base_gap * self._gap_scale
            gap *= 1 + random.uniform(0, self._jitter)
            self._next_at = max(now, self._next_at) + gap
        if wait:
            await asyncio.sleep(wait)
        return self

    async def __aexit__(self, *exc):
        self._sem.release()

    # -- the "slow down before you rotate" hook ---------------------------

    def slow_down(self, factor=2.0, cap=8.0):
        """Halve the pace (default) instead of burning the IP."""
        self._gap_scale = min(self._gap_scale * factor, cap)

    def note_response(self, status, elapsed, slow_threshold=5.0):
        """Feed every response back in; degraded IPs get paced down.

        429 -> immediate slow_down. Responses consistently slower than
        `slow_threshold` seconds -> soft degradation, slow down too.
        Rotating at the first sign just moves the same implausible
        behavior to a fresh IP; pacing down is cheaper.
        """
        if status == 429:
            self.slow_down()
        elif elapsed > slow_threshold:
            self._slow_responses += 1
            if self._slow_responses >= 3:
                self.slow_down(factor=1.5)
                self._slow_responses = 0
        else:
            self._slow_responses = 0

    @property
    def paced_down(self):
        return self._gap_scale > 1.0


class BudgetPool:
    """One IPBudget per sticky session id (= per exit IP)."""

    def __init__(self, **budget_kwargs):
        self._budgets = {}
        self._kwargs = budget_kwargs

    def for_session(self, session_id):
        if session_id not in self._budgets:
            self._budgets[session_id] = IPBudget(**self._kwargs)
        return self._budgets[session_id]


def proxy_for(session_id):
    user, pw = os.environ.get("ROAM_USER"), os.environ.get("ROAM_PASS")
    if not user or not pw:
        return None
    return f"http://{user}-session-{session_id}:{pw}@{GATEWAY}"


async def fetch(client, url, budget):
    async with budget:
        t0 = time.monotonic()
        resp = await client.get(url)
        budget.note_response(resp.status_code, time.monotonic() - t0)
        return resp


async def main():
    url = "https://httpbin.org/get"
    pool = BudgetPool(max_concurrency=4, rps=2.0)
    sessions = ["demo1", "demo2"]  # two sticky sessions = two exit IPs

    for sid in sessions:
        proxy = proxy_for(sid)
        budget = pool.for_session(sid)
        async with httpx.AsyncClient(proxy=proxy, timeout=30) as client:
            t0 = time.monotonic()
            # 8 URLs thrown at gather -- the semaphore keeps at most 4
            # in flight, the bucket keeps the sustained rate ~2 rps.
            results = await asyncio.gather(
                *(fetch(client, url, budget) for _ in range(8)),
                return_exceptions=True,
            )
            ok = sum(1 for r in results if not isinstance(r, Exception)
                     and r.status_code == 200)
            print(f"session={sid} via={'proxy' if proxy else 'direct'} "
                  f"ok={ok}/8 elapsed={time.monotonic() - t0:.1f}s "
                  f"paced_down={budget.paced_down}")


if __name__ == "__main__":
    asyncio.run(main())

