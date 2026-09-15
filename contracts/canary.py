"""Per-host success contracts + a canary that tells you whose fault a failure is.

Companion to: https://dev.to/roamproxy/http-200-is-not-success-write-a-contract-per-host-192i

Companion to sessions/sticky_unit.py: that module decides how long one exit IP
should carry a journey; this one decides whether the journey is still working.

A 200 is not success. A response passes only if it satisfies the host's
contract: the container exists (shape), the record count is plausible (volume),
and the payload is about what you asked for (identity).

The canary is one stable URL per host whose correct answer is already known.
Run it through the same session and exit IP as real traffic, at the seams of a
unit of work -- never on a fixed timer, which is the most machine-shaped
pattern you can emit.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

Parsed = dict


@dataclass
class Contract:
    """What a good response from one host looks like."""

    host: str
    shape: Callable[[Parsed], bool]
    volume: range
    identity: Callable[[Parsed, str], bool]

    def violation(self, parsed: Parsed, requested_id: str) -> Optional[str]:
        """Return the failing clause, or None if the response is acceptable."""
        if not self.shape(parsed):
            return "shape"
        if len(parsed.get("records", [])) not in self.volume:
            return "volume"
        if not self.identity(parsed, requested_id):
            return "identity"
        return None


@dataclass
class Canary:
    """A known-good request used to attribute failures.

    `fetch` must issue the request through the *same* session and exit IP as
    real traffic, otherwise a passing canary proves nothing about the session
    doing the work.
    """

    url: str
    requested_id: str
    contract: Contract
    fetch: Callable[[str], Parsed]
    min_spacing: float = 45.0
    jitter: float = 0.4
    _last_run: float = field(default=0.0, repr=False)

    def due(self) -> bool:
        return (time.monotonic() - self._last_run) >= self._spacing()

    def _spacing(self) -> float:
        return self.min_spacing * (1.0 + random.uniform(-self.jitter, self.jitter))

    def healthy(self) -> bool:
        self._last_run = time.monotonic()
        try:
            parsed = self.fetch(self.url)
        except Exception:
            return False
        return self.contract.violation(parsed, self.requested_id) is None


class Verdict:
    HEALTHY = "healthy"
    PAGE_BAD = "page_bad"      # canary passed, target failed -> skip the page
    SESSION_BAD = "session_bad"  # canary failed too -> rotate at the seam
    CANARY_FLAKY = "canary_flaky"  # canary failed, target fine -> fix the canary


def diagnose(canary_ok: bool, target_ok: bool) -> str:
    if canary_ok and target_ok:
        return Verdict.HEALTHY
    if canary_ok and not target_ok:
        return Verdict.PAGE_BAD
    if not canary_ok and not target_ok:
        return Verdict.SESSION_BAD
    return Verdict.CANARY_FLAKY


def run_unit(
    targets: Iterable[tuple[str, str]],
    contract: Contract,
    canary: Canary,
    fetch: Callable[[str], Parsed],
) -> dict:
    """Walk one unit of work, stopping early if the session stops being trusted.

    Returns a summary; a SESSION_BAD verdict means the caller should rotate the
    sticky session before starting the next unit -- at the seam, not mid-journey.
    """
    summary = {"ok": [], "skipped": [], "verdict": Verdict.HEALTHY}

    if not canary.healthy():
        summary["verdict"] = Verdict.SESSION_BAD
        return summary

    for url, requested_id in targets:
        try:
            parsed = fetch(url)
            failure = contract.violation(parsed, requested_id)
        except Exception:
            failure = "exception"

        if failure is None:
            summary["ok"].append(url)
            continue

        # A bad response is ambiguous until the canary answers.
        canary_ok = canary.healthy() if canary.due() else True
        verdict = diagnose(canary_ok, target_ok=False)
        if verdict == Verdict.SESSION_BAD:
            summary["verdict"] = verdict
            break
        summary["skipped"].append((url, failure))

    return summary


if __name__ == "__main__":
    # Offline demo: a host that starts degrading halfway through the unit.
    calls = {"n": 0}

    def fake_fetch(url: str) -> Parsed:
        calls["n"] += 1
        degraded = calls["n"] > 4
        return {
            "container": True,
            "canonical": url,
            "records": [] if degraded else [{"id": i} for i in range(25)],
        }

    contract = Contract(
        host="example.com",
        shape=lambda p: bool(p.get("container")),
        volume=range(20, 61),
        identity=lambda p, rid: rid in str(p.get("canonical", "")),
    )
    canary = Canary(
        url="https://example.com/catalog/stable",
        requested_id="catalog/stable",
        contract=contract,
        fetch=fake_fetch,
        min_spacing=0.0,
    )
    pages = [(f"https://example.com/p/{i}", f"p/{i}") for i in range(1, 6)]
    print(run_unit(pages, contract, canary, fake_fetch))
