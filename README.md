# Dialogflow CX BYOVA Gateway

[![License: Cisco Sample Code](https://img.shields.io/badge/License-Cisco%20Sample%20Code-blue.svg)](LICENSE)

Python gateway between **Webex Contact Center (WxCC)** and virtual agent backends (e.g. **Google Dialogflow CX**, AWS Lex). It implements the BYOVA gRPC service and routes audio to your connector.

This README is the **single setup guide**: prerequisites, secrets, Google authentication, optional Webex token refresh, TLS, running the server, and troubleshooting.

---

## Table of contents

1. [Prerequisites](#prerequisites)
2. [Security: files and values never to commit](#security-files-and-values-never-to-commit)
3. [Quick start](#quick-start)
4. [Configuration](#configuration)
5. [Google Dialogflow CX — authentication](#google-dialogflow-cx--authentication)
6. [Optional: Webex access token refresh & BYODS URL](#optional-webex-access-token-refresh--byods-url)
7. [Optional: Workload Identity Federation (WIF)](#optional-workload-identity-federation-wif)
8. [TLS](#tls)
9. [Run the gateway](#run-the-gateway)
10. [Monitoring](#monitoring)
11. [Troubleshooting](#troubleshooting)
12. [Further reading](#further-reading)
13. [License](#license)

---

## Prerequisites

- **Python 3.8+**
- **Google Cloud**: project with **Dialogflow API** enabled, Dialogflow CX agent created
- **Webex Contact Center** environment if you are testing end-to-end with WxCC
- **gRPC stubs** generated from `proto/` (see [Quick start](#quick-start))

---

## Security: files and values never to commit

| Item | Notes |
|------|--------|
| `oauth_token.pickle` / `*_oauth_token.pickle` | Google OAuth user tokens |
| `client_secret*.json`, `*-key.json`, service account JSON | Google credentials |
| `config/webex_oauth_secrets.json`, `config/webex_token.json`, `config/webex_access_token.txt` | Webex OAuth / access tokens |
| `wif-config.json`, `oidc_token.json` | Workload Identity Federation and OIDC JWT |
| TLS `*.pem`, `*.key` | Certificates and keys |
| **Any** real `project_id`, client secrets, refresh tokens, or JWTs in YAML/JSON | Use placeholders in examples |

Copy the **example** files and fill in locally (examples are safe to commit):

- `config/webex_oauth_secrets.example.json` → `config/webex_oauth_secrets.json` (gitignored)
- `config/wif-config.json.example` → `wif-config.json` (gitignored)
- `oidc_token.json.example` → `oidc_token.json` (gitignored)

`.gitignore` already excludes common secret paths; verify before every push.

---

## Quick start

```bash
git clone <your-fork-or-repo-url>
cd webex-byova-gateway-python

python -m venv venv
# Windows:
venv\Scripts\Activate.ps1
# macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt

python -m grpc_tools.protoc -I./proto --python_out=src/generated --grpc_python_out=src/generated proto/*.proto
```

Edit `config/config.yaml`: set `project_id`, `agent_id`, and `location` for Dialogflow CX (see [Configuration](#configuration)).

Choose a [Google authentication](#google-dialogflow-cx--authentication) method, then:

```bash
python main.py
```

Open **http://localhost:8080** for the monitoring UI (port from `config/config.yaml`).

---

## Configuration

Main file: **`config/config.yaml`**.

Minimal connector block (placeholders):

```yaml
connectors:
  dialogflow_cx_connector:
    type: "dialogflow_cx_connector"
    class: "DialogflowCXConnector"
    module: "connectors.dialogflow_cx_connector"
    config:
      project_id: "YOUR_GCP_PROJECT_ID"
      agent_id: "YOUR_DIALOGFLOW_CX_AGENT_ID"
      location: "global"
      language_code: "en-US"
      sample_rate_hertz: 16000
      audio_encoding: "AUDIO_ENCODING_LINEAR_16"
      force_input_format: "wxcc"
      agents:
        - "Dialogflow CX Agent"
```

- **`gateway.port`**: gRPC listen port (WxCC / your network must reach `host:port`).
- **`force_input_format: wxcc`**: Typical for WxCC telephony (8 kHz μ-law); adjust if you use different audio.
- More options: see `config/dialogflow_cx_example.yaml` and `config/config_example.yaml`.

---

## Google Dialogflow CX — authentication

Enable the API:

```bash
gcloud services enable dialogflow.googleapis.com
```

Grant your user or service account **`roles/dialogflow.client`** (or equivalent) on the project.

The connector supports (in rough priority order):

1. **Workload Identity Federation** — set `GOOGLE_APPLICATION_CREDENTIALS` to a `wif-config.json` path (see [WIF](#optional-workload-identity-federation-wif)).
2. **Short-lived access token** — `access_token` in config or `GCP_ACCESS_TOKEN` env (expires ~1h; no auto-refresh in code).
3. **Service account JSON** — `service_account_key` in config.
4. **OAuth 2.0 (user)** — `oauth_client_id`, `oauth_client_secret`, optional `oauth_token_file` (default `oauth_token.pickle`). First run opens a browser; redirect URI **must** include `http://localhost:8090/` in Google Cloud Console.
5. **Application Default Credentials (ADC)** — if none of the above apply: run `gcloud auth application-default login` and omit OAuth/service account fields.

**OAuth redirect URI:** add exactly `http://localhost:8090/` to the OAuth client (Desktop app) in Google Cloud Console and wait a few minutes after saving.

**IAM example:**

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/dialogflow.client"
```

---

## Webex access token refresh & BYODS URL

If you use a **Webex integration** (service app) to refresh access tokens or update the **BYOVA data source** URL in Control Hub:

1. Install `requests` if needed: `pip install requests`.
2. Copy `config/webex_oauth_secrets.example.json` to `config/webex_oauth_secrets.json` and fill in **client_id**, **client_secret**, **refresh_token** from your Webex developer / admin flow.
3. Optionally set **`datasource_id`** and **`datasource_url`** (your gateway’s public `https://host:port` gRPC endpoint as required by your organization).

**Environment variables** (alternative to the JSON file for secrets):

| Variable | Purpose |
|----------|---------|
| `WEBEX_CLIENT_ID`, `WEBEX_CLIENT_SECRET`, `WEBEX_REFRESH_TOKEN` | OAuth refresh |
| `WEBEX_SECRETS_FILE` | Path to JSON secrets file (default `config/webex_oauth_secrets.json`) |
| `WEBEX_ACCESS_TOKEN_FILE` | Where to write the new access token (default `config/webex_access_token.txt`) |
| `WEBEX_TOKEN_JSON_FILE` | Optional full JSON response path |
| `WEBEX_DATASOURCE_ID`, `WEBEX_DATASOURCE_URL` | BYODS data source UUID and gateway URL |
| `WEBEX_DATASOURCE_SCHEMA_ID` | Schema UUID for the data source **PUT** payload (from Webex / org documentation) |

Run:

```bash
python scripts/refresh_webex_token.py
```

If `WEBEX_DATASOURCE_SCHEMA_ID` is not set, token refresh still runs; the data-source **PUT** is skipped with a warning until you set it.

---

## Workload Identity Federation (WIF)

For **Google WIF** with an external OIDC token:

1. Create `wif-config.json` from **`config/wif-config.json.example`** using values from Google Cloud (pool, provider, service account to impersonate).
2. Place **`oidc_token.json`** next to it (see **`oidc_token.json.example`**) with a short-lived JWT from your identity provider.
3. Set in `config/config.yaml` (or env):

   - `wif_config_path` / `GOOGLE_APPLICATION_CREDENTIALS` → path to `wif-config.json`

Rotate OIDC tokens as required by your IdP. Do not commit real `wif-config.json` or `oidc_token.json`.

---

## TLS

- **Recommended in production:** terminate TLS on a **load balancer** or reverse proxy and forward plain gRPC to this app on your internal port.
- **In-process TLS:** uncomment `gateway.tls` in `config/config.yaml` and place PEM files under `config/certs/` (see `config/certs/README.md`). Do not commit private keys.

---

## Run the gateway

```bash
venv\Scripts\Activate.ps1   # Windows
# source venv/bin/activate  # macOS/Linux

python main.py
```

Expected log lines include Dialogflow connector initialization and the gRPC server listening on the configured port.

Stop with **Ctrl+C**.

---

## Monitoring

| URL | Purpose |
|-----|---------|
| http://localhost:8080 | Dashboard (if `monitoring.enabled`) |
| http://localhost:8080/api/status | JSON status |
| http://localhost:8080/health | Health check |

---

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| `redirect_uri_mismatch` (Google OAuth) | Add `http://localhost:8090/` to OAuth client redirect URIs; include trailing slash; wait a few minutes. |
| `invalid_client` (Google OAuth) | Check client ID/secret; no extra spaces in `config.yaml`. |
| `Could not automatically determine credentials` (ADC) | Run `gcloud auth application-default login`. |
| Permission denied on Dialogflow | Grant `roles/dialogflow.client` to the signed-in user or service account. |
| Port in use | Change `gateway.port` or free the port (`netstat` / `taskkill` on Windows). |

---

## Further reading

| Topic | Location |
|-------|----------|
| Dialogflow CX setup (longer walkthrough) | [docs/guides/byova-dialogflow-cx-setup.md](docs/guides/byova-dialogflow-cx-setup.md) |
| AWS Lex setup | [docs/guides/byova-aws-lex-setup.md](docs/guides/byova-aws-lex-setup.md) |
| Custom connectors | [src/connectors/README.md](src/connectors/README.md) |
| AI/agent notes for this repo | [AGENTS.MD](AGENTS.MD) |

**gRPC:** `ListVirtualAgents`, `ProcessCallerInput`. **HTTP:** `/api/status`, `/api/connections`, `/health`.

---

## License

[Cisco Sample Code License v1.1](LICENSE) © 2018 Cisco and/or its affiliates.

This sample is not supported by Cisco TAC and is provided **AS IS** for example purposes only.
