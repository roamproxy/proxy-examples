"""Diagnose *what* got blocked before you rotate anything.

Rotating the exit IP is the most expensive remediation available and it is the
one people reach for first. This script runs four cheap probes and reports which
scope the block actually applies to, so that only the IP-scoped case triggers a
rotation.

Scopes:
    none         the failure did not reproduce at all
    request      one request was malformed / unauthorised; others are fine
    session      the cookie jar or TLS session got flagged
    fingerprint  the client is rejected for what it is, not where it is from
    ip           the exit address is on a list
    account      the logged-in account is limited (never rotate here)
    transient    a challenge is being served, not a refusal -- wait it out

Usage:
    python block_scope.py https://example.com/target \
        --old-proxy http://user:pass@gw.roamproxy.com:41080 \
        --new-proxy http://user-session-b:pass@gw.roamproxy.com:41080

Requires: httpx>=0.27 (pip install "httpx[http2]")
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict

import httpx

try:                                    # probe 2 varies the TLS/ALPN shape,
    import h2                           # which needs the http2 extra
    HTTP2 = True
except ImportError:                     # still useful without it, just blunter
    HTTP2 = False

CHALLENGE_MARKERS = (
    "just a moment",
    "un momento",
    "checking your browser",
    "attention required",
    "verify you are human",
    "enable javascript and cookies",
)

BROWSER_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}


@dataclass
class ProbeResult:
    status: int | None
    length: int
    challenged: bool
    hops: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None \
            and self.status < 400 and not self.challenged


def probe(url: str, *, proxy=None, cookies=None, headers=None,
          http2: bool = True, timeout: float = 20.0) -> ProbeResult:
    """One probe. Never raises -- a failed probe is a data point."""
    try:
        with httpx.Client(proxy=proxy, cookies=cookies or {},
                          headers=headers or {}, http2=http2 and HTTP2,
                          timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
    except httpx.HTTPError as exc:
        return ProbeResult(None, 0, False, 0, error=type(exc).__name__)

    body = r.text
    challenged = any(m in body.lower() for m in CHALLENGE_MARKERS)
    return ProbeResult(r.status_code, len(body), challenged, len(r.history))


def diagnose(url: str, old_proxy=None, new_proxy=None,
             old_cookies=None, logged_in: bool = False) -> dict:
    p = {
        # 1. same exit, fresh cookie jar
        "fresh_session_same_ip": probe(url, proxy=old_proxy,
                                       headers=BROWSER_HEADERS),
        # 2. same exit, different client shape (varies TLS/JA3 + header order)
        "diff_client_same_ip": probe(url, proxy=old_proxy, http2=False,
                                     headers={}),
        # 3. different exit, the cookies that were failing
        "old_cookies_new_ip": probe(url, proxy=new_proxy, cookies=old_cookies,
                                    headers=BROWSER_HEADERS),
        # 4. different exit, everything fresh
        "all_fresh_new_ip": probe(url, proxy=new_proxy, headers=BROWSER_HEADERS),
    }
    return {"scope": classify(p, logged_in=logged_in),
            "probes": {k: asdict(v) for k, v in p.items()}}


def classify(p: dict[str, ProbeResult], *, logged_in: bool = False) -> str:
    """Map the four probes onto a scope. Order matters: cheapest cause first."""
    # A served challenge is an invitation, not a door. Waiting is the fix.
    if any(r.challenged for r in p.values()) and \
            not all(r.status in (401, 403) for r in p.values() if r.status):
        return "transient"

    # Nothing reproduced: whatever failed was specific to the exact request
    # and session that failed. Retry it clean before changing anything.
    if all(r.ok for r in p.values()):
        return "none"

    if p["fresh_session_same_ip"].ok:
        return "session"

    # Old cookies poison a brand new exit too -> it was never the address.
    if not p["old_cookies_new_ip"].ok and p["all_fresh_new_ip"].ok:
        return "account" if logged_in else "session"

    # Bare client works where the browser-shaped one does not (or vice versa).
    if p["diff_client_same_ip"].ok != p["fresh_session_same_ip"].ok:
        return "fingerprint"

    if p["all_fresh_new_ip"].ok and not p["fresh_session_same_ip"].ok:
        return "ip"

    return "request"


# Only one branch is allowed to rotate. That is the whole point.
REMEDIATION = {
    "none": "Nothing reproduced. Re-run the original request with a fresh "
            "session before changing anything else.",
    "request": "Fix the headers/method/token. Nothing else is wrong.",
    "session": "Drop the cookie jar. Keep the exit IP.",
    "fingerprint": "Change the client (TLS/header order), not the route.",
    "ip": "Rotate the exit IP -- this is the one case where it is correct.",
    "account": "Slow down. Do NOT move a logged-in account to a new IP.",
    "transient": "Wait. A served challenge usually clears on its own.",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url")
    ap.add_argument("--old-proxy", default=None,
                    help="the exit that started failing")
    ap.add_argument("--new-proxy", default=None,
                    help="a different exit, for comparison only")
    ap.add_argument("--cookies", default=None,
                    help="JSON dict of the cookies that were in use")
    ap.add_argument("--logged-in", action="store_true",
                    help="the failing requests were authenticated")
    args = ap.parse_args()

    cookies = json.loads(args.cookies) if args.cookies else None
    report = diagnose(args.url, args.old_proxy, args.new_proxy,
                      cookies, logged_in=args.logged_in)

    if not HTTP2:
        print("note: h2 not installed -- the fingerprint probe is weaker "
              "(pip install 'httpx[http2]')\n")
    print(json.dumps(report["probes"], indent=2))
    scope = report["scope"]
    print(f"\nscope: {scope}\naction: {REMEDIATION[scope]}")


if __name__ == "__main__":
    main()
