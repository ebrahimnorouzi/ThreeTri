"""One-time: mint a Strava REFRESH TOKEN for one athlete.

Each of the three of you runs this ONCE on your own laptop, logged into your own
Strava account. It prints a refresh token — send that to whoever administers the
GitHub repo to store as the athlete's secret (STRAVA_REFRESH_TOKEN_<NAME>).

    # get CLIENT_ID / CLIENT_SECRET from https://www.strava.com/settings/api
    set STRAVA_CLIENT_ID=12345          (Windows: set, macOS/Linux: export)
    set STRAVA_CLIENT_SECRET=abc...
    python scripts/mint_strava_token.py

It opens your browser, you click Authorize, and it captures the response on
http://localhost:8721 automatically. Requires `requests` (pip install requests).

IMPORTANT: in your Strava API application settings, set the
"Authorization Callback Domain" to exactly:  localhost
"""

from __future__ import annotations

import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

PORT = 8721
REDIRECT_URI = f"http://localhost:{PORT}"
SCOPE = "activity:read_all"
AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"

_captured = {}
_done = threading.Event()
_expected_state = None  # CSRF guard, set in main()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = params.get("code", [None])[0]
        err = params.get("error", [None])[0]
        state = params.get("state", [None])[0]
        if code is None and err is None and state is None:
            # Not the OAuth redirect (e.g. a favicon request) — ignore it.
            self.send_response(204)
            self.end_headers()
            return
        if _expected_state is not None and state != _expected_state:
            # Ignore forged / replayed redirects that don't carry our state.
            _captured["error"] = "state mismatch"
            ok = False
        else:
            _captured["code"] = params.get("code", [None])[0]
            _captured["error"] = params.get("error", [None])[0]
            ok = bool(_captured.get("code")) and not _captured.get("error")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "✅ Authorized! Return to your terminal." if ok else "❌ Authorization failed. Check the terminal."
        self.wfile.write(f"<html><body style='font-family:sans-serif;background:#070b12;color:#eaf1fb;text-align:center;padding-top:80px'><h2>ThreeTri</h2><p>{msg}</p></body></html>".encode())
        _done.set()

    def log_message(self, *_):  # silence the server logs
        pass


def main() -> int:
    client_id = os.environ.get("STRAVA_CLIENT_ID") or input("Strava Client ID: ").strip()
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET") or input("Strava Client Secret: ").strip()
    if not client_id or not client_secret:
        print("Need both client id and secret (https://www.strava.com/settings/api).")
        return 1

    global _expected_state
    _expected_state = secrets.token_urlsafe(16)  # CSRF guard

    auth = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "force",   # always show consent + apply requested scope
        "scope": SCOPE,
        "state": _expected_state,
    })

    server = HTTPServer(("localhost", PORT), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print("\nOpening your browser to authorize…")
    print("If it doesn't open, paste this URL manually:\n  " + auth + "\n")
    try:
        webbrowser.open(auth)
    except Exception:
        pass

    print(f"Waiting for the redirect on {REDIRECT_URI} …  (Ctrl+C to cancel)")
    try:
        if not _done.wait(timeout=180):
            print("Timed out after 3 minutes waiting for authorization.")
            return 1
    except KeyboardInterrupt:
        return 1
    finally:
        server.shutdown()

    if _captured.get("error") or not _captured.get("code"):
        print(f"Authorization failed: {_captured.get('error')}")
        return 1

    resp = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": _captured["code"],
        "grant_type": "authorization_code",
    }, timeout=30)
    if resp.status_code != 200:
        print(f"Token exchange failed: HTTP {resp.status_code}\n{resp.text}")
        return 1
    tok = resp.json()
    ath = tok.get("athlete", {})
    name = f"{ath.get('firstname', '')} {ath.get('lastname', '')}".strip() or "(unknown)"

    print("\n" + "=" * 64)
    print(f"  Authorized athlete : {name}")
    print(f"  Granted scope      : {tok.get('scope', SCOPE)}")
    print("  REFRESH TOKEN (store as STRAVA_REFRESH_TOKEN_<NAME> in GitHub):")
    print("  " + tok["refresh_token"])
    print("=" * 64)
    print("Keep this secret. It grants read access to your activities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
