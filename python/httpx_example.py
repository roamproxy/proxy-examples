"""Async RoamProxy requests with `httpx`.

    pip install httpx

Set ROAM_USER and ROAM_PASS in your environment first.
"""
import asyncio
import os

import httpx

USER = os.environ["ROAM_USER"]
PASS = os.environ["ROAM_PASS"]
GATEWAY = "gw.roamproxy.com:41080"


async def get_ip(username: str) -> str:
    proxy = f"http://{username}:{PASS}@{GATEWAY}"
    async with httpx.AsyncClient(proxy=proxy, timeout=30) as client:
        r = await client.get("https://ipinfo.io/json")
        return r.json()["ip"]


async def main() -> None:
    # Fire several rotating requests concurrently — each gets its own exit IP.
    usernames = [f"{USER}-country-us" for _ in range(5)]
    ips = await asyncio.gather(*(get_ip(u) for u in usernames))
    for ip in ips:
        print(ip)


if __name__ == "__main__":
    asyncio.run(main())
