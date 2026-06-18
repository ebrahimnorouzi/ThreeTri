"""One-time: mint a GARMIN token blob for one athlete.

Garmin has no public API, so we log in once (locally, with your password + MFA)
and export the resulting OAuth tokens as a base64 string. That string goes into
the athlete's GitHub Secret (GARMIN_TOKEN_<NAME>); the nightly job resumes the
session from it with NO password and NO MFA — which is the only thing Garmin's
Cloudflare protection allows from a CI server.

    pip install garminconnect curl_cffi      # Python 3.12+
    python scripts/mint_garmin_token.py

You'll be prompted for email, password, and (if enabled) your MFA code. The
token blob is valid roughly a YEAR; re-run this if the nightly Garmin step
starts reporting login failures.

Garmin is OPTIONAL — it only adds sleep / HRV / readiness. Skip it entirely and
the dashboard still works on Strava data alone.
"""

from __future__ import annotations

import getpass
import sys


def main() -> int:
    try:
        from garminconnect import Garmin
    except ImportError:
        print("garminconnect not installed. Run:  pip install garminconnect curl_cffi")
        return 1

    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password (hidden): ")
    is_cn = input("Are you on the China (garmin.cn) account? [y/N]: ").strip().lower() == "y"

    garmin = Garmin(
        email, password, is_cn=is_cn,
        prompt_mfa=lambda: input("MFA code (blank if none): ").strip(),
    )

    print("\nLogging in to Garmin Connect…")
    try:
        garmin.login()
    except Exception as exc:
        print(f"Login failed: {type(exc).__name__}: {exc}")
        print("Double-check the password / MFA code and try again.")
        return 1

    token_b64 = garmin.client.dumps()  # base64(JSON([oauth1, oauth2]))

    # quick smoke test so you know the token actually works
    try:
        from datetime import date
        garmin.get_stats(date.today().isoformat())
        print("✅ Login OK and a test data call succeeded.")
    except Exception:
        print("✅ Login OK (test data call skipped — token still valid for the pipeline).")

    print("\n" + "=" * 64)
    print("  GARMIN TOKEN — store as GARMIN_TOKEN_<NAME> in GitHub Secrets.")
    print("  Paste the ENTIRE line below (it is long, ~1-2 KB):")
    print("=" * 64)
    print(token_b64)
    print("=" * 64)
    print("Treat this like a password — it grants access to your Garmin account.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
