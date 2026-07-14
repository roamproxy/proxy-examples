"""Route a Scrapy spider through RoamProxy.

    pip install scrapy

Scrapy has no per-request proxy field; you set `proxy` in each request's
`meta`. This spider sends every request through a rotating US exit, so each
retry naturally lands on a fresh IP.

Run it standalone:

    ROAM_USER=your-username ROAM_PASS=your-password python roam_spider.py

Set ROAM_USER and ROAM_PASS in your environment first.
"""
import os

import scrapy
from scrapy.crawler import CrawlerProcess

USER = os.environ["ROAM_USER"]
PASS = os.environ["ROAM_PASS"]
GATEWAY = "gw.roamproxy.com:41080"


def proxy_url(username: str) -> str:
    return f"http://{username}:{PASS}@{GATEWAY}"


class IPSpider(scrapy.Spider):
    name = "roam_ip"
    # Rotating US exit: no session id, so every request gets a fresh IP.
    proxy = proxy_url(f"{USER}-country-us")

    def start_requests(self):
        for _ in range(3):
            # dont_filter=True so the 3 identical URLs aren't deduped away.
            yield scrapy.Request(
                "https://ipinfo.io/json",
                meta={"proxy": self.proxy},
                dont_filter=True,
                callback=self.parse,
            )

    def parse(self, response):
        data = response.json()
        self.logger.info("exit IP: %s (%s)", data.get("ip"), data.get("country"))
        yield {"ip": data.get("ip"), "country": data.get("country")}


if __name__ == "__main__":
    # RETRY_ENABLED + a generous retry count: on a block, Scrapy retries and the
    # rotating gateway hands out a new IP without any extra code.
    process = CrawlerProcess(settings={
        "LOG_LEVEL": "INFO",
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 5,
        "DOWNLOAD_TIMEOUT": 30,
        "CONCURRENT_REQUESTS": 4,
    })
    process.crawl(IPSpider)
    process.start()
