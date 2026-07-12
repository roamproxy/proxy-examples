# RoamProxy code examples

Copy-paste examples for connecting to [RoamProxy](https://roamproxy.com?utm_source=github&utm_medium=referral) residential and datacenter proxies from Python, Node.js, Go, and the command line.

RoamProxy is a pay-as-you-go proxy network: rotating residential from **$2/GB**, static residential, and datacenter IPs across **190+ countries**, over a single gateway that speaks both **HTTP** and **SOCKS5**.

## The gateway

Every example points at one endpoint:

```
gw.roamproxy.com:41080
```

The port auto-detects the protocol — send HTTP CONNECT or a SOCKS5 handshake to the same host and port, whichever your client uses.

## Authentication

Credentials are your account username and password. You shape the request by adding modifiers to the **username**:

```
USERNAME-country-us-session-abc123
```

| Modifier | Example | Effect |
| --- | --- | --- |
| `-country-<cc>` | `-country-us`, `-country-gb`, `-country-jp` | Exit in a specific country (ISO 3166-1 alpha-2). |
| `-session-<id>` | `-session-abc123` | Keep the same exit IP across requests (sticky). Reuse the id to keep it; change it to rotate. |

Omit `-session-...` to get a fresh rotating IP on every request. A full username looks like:

```
USERNAME-country-us-session-abc123
```

Set `USERNAME` / `PASSWORD` from your [dashboard](https://roamproxy.com?utm_source=github&utm_medium=referral) as environment variables before running any example:

```bash
export ROAM_USER="your-username"
export ROAM_PASS="your-password"
```

## Examples

- [`python/`](python/) — `requests` and `httpx`
- [`nodejs/`](nodejs/) — `axios` and native `fetch`
- [`go/`](go/) — `net/http`
- [`curl/`](curl/) — command line, HTTP and SOCKS5

## Links

- Python SDK: [roamproxy/roamproxy-python](https://github.com/roamproxy/roamproxy-python) — sticky sessions, rotation pool, retries
- Website: https://roamproxy.com?utm_source=github&utm_medium=referral
- Locations: https://roamproxy.com/locations
- Guides: https://roamproxy.com/guides

## License

MIT — see [LICENSE](LICENSE).
