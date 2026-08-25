"""Assert that the client agrees with its own exit before the first real request.

    python geo_audit.py <country> <proxy_url>
    python geo_audit.py de http://USER-country-de:PASS@gw.roamproxy.com:41080

Asks an echo endpoint what the *server* sees (origin IP + headers), geolocates the
origin, and compares both to what the client *intends*. A client that disagrees
with its exit is not allowed into the pool.

Companion post: https://dev.to/roamproxy/your-proxy-is-in-germany-the-rest-of-your-client-isnt-208b
"""
import json
import sys

import httpx

from geo_profile import PROFILES, client_for

ECHO = "https://httpbin.org/anything"          # anything that reflects headers + origin
GEO = "https://ipinfo.io/{ip}/json"


def audit(client: httpx.Client, expect_country: str) -> dict:
    seen = client.get(ECHO).json()
    origin = seen["origin"].split(",")[0].strip()
    lang = seen["headers"].get("Accept-Language", "")
    geo = httpx.get(GEO.format(ip=origin), timeout=10).json()
    country = (geo.get("country") or "").lower()

    want_lang = PROFILES[expect_country]["lang"].split(",")[0].lower()   # e.g. "de-de"
    problems = []
    if country != expect_country:
        problems.append(f"exit country {country!r} != {expect_country!r}")
    if not lang.lower().startswith(want_lang):
        problems.append(f"Accept-Language {lang!r} does not start with {want_lang!r}")

    return {
        "exit": origin,
        "country": country,
        "city": geo.get("city"),
        "accept_language": lang,
        "ok": not problems,
        "problems": problems,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    country, proxy = sys.argv[1].lower(), sys.argv[2]
    with client_for(country, proxy) as c:
        result = audit(c, country)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)
