# Sticky session length

`hold_ip.py` opens one sticky session, checks its exit IP once a minute, then shows that a new session id gets a new IP immediately.

| Username | Behaviour |
| --- | --- |
| `USER-country-us` | New IP on every request (rotating) |
| `USER-country-us-session-abc123` | Same IP for about 10 minutes |
| `USER-country-us-session-abc123-sesstime-30` | Same IP for up to 30 minutes (any value from 10 to 120) |

Values outside 10–120 are clamped to that range. `-sesstime-...` has no effect without `-session-...`.

Pick the length to match one unit of work (a login plus the pages behind it), not your whole job: see [`sessions/`](../sessions/) for rotating at the seams. If the device behind the IP goes offline, the session moves to a new IP in the same region before the time is up; use a static IP when the address must never change.

```bash
pip install requests
export ROAM_USER="your-username"
export ROAM_PASS="your-password"
python hold_ip.py --minutes 30 --checks 5 --interval 60
```
