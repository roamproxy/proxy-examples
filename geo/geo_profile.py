"""One source of truth for locale-ish client settings, derived from the exit country.

A geo-targeted proxy fixes one signal (the IP). Accept-Language, timezone, locale,
DNS origin and TLS state are all still votes, and a target that geolocates at all
is counting them. Pick the exit country once and derive everything else from it.

Companion post: https://dev.to/roamproxy/your-proxy-is-in-germany-the-rest-of-your-client-isnt-208b
"""
import httpx

try:
    import h2  # noqa: F401  (pip install "httpx[http2]")
    _HTTP2 = True
except ImportError:
    _HTTP2 = False

PROFILES = {
    "de": {"lang": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7", "tz": "Europe/Berlin",    "locale": "de-DE"},
    "gb": {"lang": "en-GB,en;q=0.9",                       "tz": "Europe/London",    "locale": "en-GB"},
    "us": {"lang": "en-US,en;q=0.9",                       "tz": "America/New_York", "locale": "en-US"},
    "fr": {"lang": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7", "tz": "Europe/Paris",     "locale": "fr-FR"},
    "jp": {"lang": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7", "tz": "Asia/Tokyo",       "locale": "ja-JP"},
    "br": {"lang": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7", "tz": "America/Sao_Paulo","locale": "pt-BR"},
}

GATEWAY = "gw.roamproxy.com:41080"


def proxy_url(user: str, password: str, country: str, session: str | None = None) -> str:
    """Build the gateway URL with the -country- (and optional -session-) modifiers."""
    u = f"{user}-country-{country}"
    if session:
        u += f"-session-{session}"
    return f"http://{u}:{password}@{GATEWAY}"


def client_for(country: str, proxy: str) -> httpx.Client:
    """httpx client whose Accept-Language agrees with the exit country."""
    p = PROFILES[country]
    return httpx.Client(
        proxy=proxy,
        headers={"Accept-Language": p["lang"]},
        http2=_HTTP2,
        timeout=20,
    )


def playwright_context_kwargs(country: str) -> dict:
    """Pass as **kwargs to browser.new_context(proxy=..., ...).

    `locale` and `timezone_id` fix navigator.language, Intl and the header in one go.
    """
    p = PROFILES[country]
    return {
        "locale": p["locale"],
        "timezone_id": p["tz"],
        "extra_http_headers": {"Accept-Language": p["lang"]},
    }
