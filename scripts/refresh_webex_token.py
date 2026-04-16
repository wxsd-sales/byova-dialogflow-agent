#!/usr/bin/env python3
"""Refresh Webex access token via OAuth refresh token; optionally update BYOVA data source URL.

Credentials: WEBEX_CLIENT_ID, WEBEX_CLIENT_SECRET, WEBEX_REFRESH_TOKEN and/or
config/webex_oauth_secrets.json (WEBEX_SECRETS_FILE). Output: WEBEX_ACCESS_TOKEN_FILE.

For data source PUT: WEBEX_DATASOURCE_ID, WEBEX_DATASOURCE_URL, and WEBEX_DATASOURCE_SCHEMA_ID
(schema UUID from your Webex / org documentation).
"""

import json
import os
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_SECRETS_FILE = PROJECT_ROOT / "config" / "webex_oauth_secrets.json"
DEFAULT_OUTPUT_FILE = PROJECT_ROOT / "config" / "webex_access_token.txt"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "config" / "webex_token.json"

WEBEX_TOKEN_URL = "https://webexapis.com/v1/access_token"
WEBEX_DATASOURCE_API = "https://webexapis.com/v1/dataSources"


def load_credentials():
    """Load client_id, client_secret, refresh_token from env or secrets file."""
    client_id = os.environ.get("WEBEX_CLIENT_ID")
    client_secret = os.environ.get("WEBEX_CLIENT_SECRET")
    refresh_token = os.environ.get("WEBEX_REFRESH_TOKEN")
    secrets_path = os.environ.get("WEBEX_SECRETS_FILE", str(DEFAULT_SECRETS_FILE))
    if os.path.isfile(secrets_path):
        with open(secrets_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        client_id = client_id or data.get("client_id")
        client_secret = client_secret or data.get("client_secret")
        refresh_token = refresh_token or data.get("refresh_token")
    return client_id, client_secret, refresh_token


def refresh_access_token(client_id, client_secret, refresh_token):
    """Exchange refresh_token for a new access_token via Webex API."""
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    resp = requests.post(
        WEBEX_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def save_token(access_token, output_file, output_json=None, full_response=None):
    """Write access token to text file and optionally JSON."""
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(access_token.strip(), encoding="utf-8")

    if output_json and full_response is not None:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(full_response, indent=2), encoding="utf-8")


def update_refresh_token_in_secrets(new_refresh_token):
    """If Webex returned a new refresh_token, update the secrets file."""
    secrets_path = os.environ.get("WEBEX_SECRETS_FILE", str(DEFAULT_SECRETS_FILE))
    if not os.path.isfile(secrets_path) or not new_refresh_token:
        return
    with open(secrets_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["refresh_token"] = new_refresh_token
    with open(secrets_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_datasource_config():
    """Load datasource ID and gateway URL from env or secrets file (both optional)."""
    datasource_id = os.environ.get("WEBEX_DATASOURCE_ID")
    url = os.environ.get("WEBEX_DATASOURCE_URL")
    secrets_path = os.environ.get("WEBEX_SECRETS_FILE", str(DEFAULT_SECRETS_FILE))
    if os.path.isfile(secrets_path):
        with open(secrets_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        datasource_id = datasource_id or data.get("datasource_id")
        url = url or data.get("datasource_url")
    return datasource_id, url


def update_data_source(access_token, datasource_id, url):
    """PUT Webex data source to register/update the BYOVA gateway URL."""
    schema_id = os.environ.get("WEBEX_DATASOURCE_SCHEMA_ID", "").strip()
    if not schema_id:
        raise ValueError(
            "Set WEBEX_DATASOURCE_SCHEMA_ID to the schema UUID for your BYOVA data source "
            "(from Webex Control Hub / organization documentation)."
        )
    token_lifetime_minutes = 1440
    expiry = datetime.now(timezone.utc) + timedelta(minutes=token_lifetime_minutes)
    token_expiry_time = expiry.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    nonce = str(random.randint(10**15, 10**16 - 1))

    put_url = f"{WEBEX_DATASOURCE_API}/{datasource_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "schemaId": schema_id,
        "tokenExpiryTime": token_expiry_time,
        "nonce": nonce,
        "audience": "BYOVAGateway",
        "url": url,
        "subject": "callAudioData",
        "tokenLifetimeMinutes": "1440",
        "status": "active",
    }
    resp = requests.put(put_url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    return resp


def main():
    client_id, client_secret, refresh_token = load_credentials()
    if not all((client_id, client_secret, refresh_token)):
        print(
            "ERROR: Missing credentials. Set WEBEX_CLIENT_ID, WEBEX_CLIENT_SECRET, "
            "WEBEX_REFRESH_TOKEN or create config/webex_oauth_secrets.json",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        data = refresh_access_token(client_id, client_secret, refresh_token)
    except requests.RequestException as e:
        print(f"ERROR: Token refresh failed: {e}", file=sys.stderr)
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)

    access_token = data.get("access_token")
    if not access_token:
        print("ERROR: No access_token in response", file=sys.stderr)
        sys.exit(1)

    output_txt = os.environ.get("WEBEX_ACCESS_TOKEN_FILE", str(DEFAULT_OUTPUT_FILE))
    output_json_path = os.environ.get("WEBEX_TOKEN_JSON_FILE", str(DEFAULT_OUTPUT_JSON))
    save_token(access_token, output_txt, output_json_path, data)

    new_refresh = data.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        update_refresh_token_in_secrets(new_refresh)

    expires_in = data.get("expires_in", 0)
    print(f"OK: Access token refreshed. Expires in {expires_in} seconds. Written to {output_txt}")

    datasource_id, gateway_url = get_datasource_config()
    if datasource_id and gateway_url:
        try:
            update_data_source(access_token, datasource_id, gateway_url)
            print(f"OK: Data source {datasource_id} updated with URL {gateway_url}")
        except ValueError as e:
            print(f"WARN: {e}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"WARN: Data source update failed: {e}", file=sys.stderr)
            if hasattr(e, "response") and e.response is not None:
                print(f"Response: {e.response.text}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
