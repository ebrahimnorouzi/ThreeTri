"""Low-friction Strava token minting — *you* (the admin) run this; your friends
just click a link.

So Sia and Alborz never have to install Python. The flow:

  1. You generate a personalised authorize link:
         python scripts/exchange_strava_code.py --link
     and send it to the athlete.

  2. They open it (logged into THEIR own Strava) and click "Authorize".
     The browser redirects to http://localhost/?code=XXXX...  — that page won't
     load (nothing is listening), but the address bar now shows the code. They
     copy the whole address-bar URL (or just the code) and send it back to you.

  3. You exchange it (the code is single-use and expires in ~10 min, so be prompt):
         python scripts/exchange_strava_code.py
     paste the code/URL, and it prints the athlete's REFRESH TOKEN to store as
     their GitHub secret.

You need STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET set (the shared app). The athlete
needs nothing but a browser. (Prefer them running scripts/mint_strava_token.py
themselves? That works too — this is just the no-Python option for them.)

    pip install requests
"""

from __future__ import annotations

import os
import sys
import urllib.parse

import requests

REDIRECT_URI = "http://localhost"
SCOPE = "activity:read_all"
AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"


def _creds() -> tuple[str, str]:
    cid = os.environ.get("STRAVA_CLIENT_ID") or input("Strava Client ID: ").strip()
    secret = os.environ.get("STRAVA_CLIENT_SECRET") or input("Strava Client Secret: ").strip()
    return cid, secret


def print_link() -> int:
    cid, _ = _creds()
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": SCOPE,
    })
    print("\nSend this link to the athlete. They click Authorize, then copy the")
    print("redirected address-bar URL (or just the 'code=' value) back to you:\n")
    print("  " + url + "\n")
    return 0


def _extract_code(raw: str) -> str | None:
    raw = raw.strip()
    if "code=" in raw:
        qs = urllib.parse.urlparse(raw).query or raw.split("?", 1)[-1]
        return urllib.parse.parse_qs(qs).get("code", [None])[0]
    return raw or None


def exchange() -> int:
    cid, secret = _creds()
    pasted = input("Paste the redirected URL (or just the code): ").strip()
    code = _extract_code(pasted)
    if not code:
        print("Couldn't find a code in that input.")
        return 1
    resp = requests.post(TOKEN_URL, data={
        "client_id": cid, "client_secret": secret,
        "code": code, "grant_type": "authorization_code",
    }, timeout=30)
    if resp.status_code != 200:
        print(f"Token exchange failed: HTTP {resp.status_code} (code may be expired/used — re-issue the link).")
        return 1
    tok = resp.json()
    ath = tok.get("athlete", {})
    name = f"{ath.get('firstname', '')} {ath.get('lastname', '')}".strip() or "(unknown)"
    print("\n" + "=" * 64)
    print(f"  Athlete       : {name}")
    print(f"  Granted scope : {tok.get('scope', SCOPE)}")
    print("  REFRESH TOKEN (store as STRAVA_REFRESH_TOKEN_<NAME> in GitHub):")
    print("  " + tok["refresh_token"])
    print("=" * 64)
    return 0


def main() -> int:
    if "--link" in sys.argv:
        return print_link()
    return exchange()


if __name__ == "__main__":
    sys.exit(main())
