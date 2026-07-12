#!/usr/bin/env bash
# RoamProxy from the command line. Set ROAM_USER and ROAM_PASS first:
#
#   export ROAM_USER="your-username"
#   export ROAM_PASS="your-password"

GATEWAY="gw.roamproxy.com:41080"

# HTTP proxy, rotating US exit (fresh IP each run).
curl -x "http://$GATEWAY" -U "$ROAM_USER-country-us:$ROAM_PASS" https://ipinfo.io/json

# HTTP proxy, sticky exit — reuse the session id to keep the same IP.
curl -x "http://$GATEWAY" -U "$ROAM_USER-country-gb-session-demo42:$ROAM_PASS" https://ipinfo.io/json

# SOCKS5 over the same host and port (the gateway auto-detects the protocol).
curl -x "socks5h://$GATEWAY" -U "$ROAM_USER-country-us:$ROAM_PASS" https://ipinfo.io/json

# Note: pass credentials with -U, not inside the -x URL. A password containing
# characters like '#' or '@' breaks URL parsing but is fine via -U.
