# Webex Contact Center BYOVA Gateway

[![License: Cisco Sample Code](https://img.shields.io/badge/License-Cisco%20Sample%20Code-blue.svg)](LICENSE)

A Python-based gateway for Webex Contact Center (WxCC) that provides virtual agent integration with Google Dialogflow CX and other platforms. This gateway acts as a bridge between WxCC and virtual agent providers, enabling seamless voice interactions.

## Table of Contents

- [Quick Start](#quick-start)
- [Google Dialogflow CX Setup](#google-dialogflow-cx-setup)
  - [Prerequisites](#prerequisites)
  - [Authentication Options](#authentication-options)
  - [Option 1: OAuth 2.0 Setup](#option-1-oauth-20-setup)
  - [Option 2: Application Default Credentials (ADC)](#option-2-application-default-credentials-adc)
- [Running the Gateway](#running-the-gateway)
- [Monitoring](#monitoring)
- [Additional Documentation](#additional-documentation)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/webex/webex-byova-gateway-python.git
cd webex-byova-gateway-python

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate gRPC stubs
python -m grpc_tools.protoc -I./proto --python_out=src/generated --grpc_python_out=src/generated proto/*.proto
```

### 2. Configure Authentication

Choose one of two authentication methods:

- **OAuth 2.0** - Best for development and testing
- **Application Default Credentials (ADC)** - Best for production

See [Authentication Options](#authentication-options) below.

### 3. Start the Gateway

```bash
# Make sure virtual environment is activated
python main.py
```

Access the monitoring interface at: http://localhost:8080

---

## Google Dialogflow CX Setup

### Prerequisites

Before connecting to Google Dialogflow CX, you need:

1. **Google Cloud Account** with billing enabled
2. **Dialogflow CX Agent** created and configured
3. **Python 3.8+** installed
4. **Webex Contact Center** environment for testing

### Enable Dialogflow API

```bash
# Using gcloud CLI
gcloud services enable dialogflow.googleapis.com

# Or enable in Google Cloud Console:
# https://console.cloud.google.com/apis/library/dialogflow.googleapis.com
```

### Get Your Project Information

You'll need these from Google Cloud Console:

- **Project ID**: Your Google Cloud project ID
- **Agent ID**: Your Dialogflow CX agent ID (found in agent settings)
- **Location**: Where your agent is hosted (e.g., `global`, `us-central1`)

---

## Authentication Options

The gateway supports two authentication methods for Google Dialogflow CX:

| Method        | Best For                 | Setup Time | Complexity |
| ------------- | ------------------------ | ---------- | ---------- |
| **OAuth 2.0** | Development, Testing     | 5 minutes  | Medium     |
| **ADC**       | Production, Simple Setup | 2 minutes  | Low        |

---

## Option 1: OAuth 2.0 Setup

OAuth 2.0 provides user-based authentication. Best for development when you want to test with your own Google account.

### Step 1: Create OAuth 2.0 Credentials

1. Go to [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. Choose **Application type**: `Desktop app`
4. Enter a name (e.g., "BYOVA Gateway")
5. Click **CREATE**
6. **Copy** the Client ID and Client Secret

### Step 2: Add Redirect URI

1. Click the **edit icon** (pencil) next to your OAuth client
2. In **Authorized redirect URIs**, add:
   ```
   http://localhost:8090/
   ```
3. Click **SAVE**
4. **Wait 5 minutes** for changes to propagate

### Step 3: Configure Gateway

Edit `config/config.yaml`:

```yaml
connectors:
  dialogflow_cx_connector:
    type: "dialogflow_cx_connector"
    class: "DialogflowCXConnector"
    module: "connectors.dialogflow_cx_connector"
    config:
      # Your Dialogflow CX details
      project_id: "your-project-id"
      agent_id: "your-agent-id"
      location: "global"

      # OAuth 2.0 credentials
      oauth_client_id: "YOUR_CLIENT_ID.apps.googleusercontent.com"
      oauth_client_secret: "YOUR_CLIENT_SECRET"
      oauth_token_file: "oauth_token.pickle"

      # Audio settings
      language_code: "en-US"
      sample_rate_hertz: 16000
      audio_encoding: "AUDIO_ENCODING_LINEAR_16"
      force_input_format: "wxcc"

      agents:
        - "Dialogflow CX Agent"
```

### Step 4: Grant User Permissions

```bash
# Grant Dialogflow permissions to your Google account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@gmail.com" \
    --role="roles/dialogflow.client"
```

### Step 5: Start Gateway (First Time)

```bash
# Activate virtual environment
venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate  # macOS/Linux

# Start gateway
python main.py
```

**What happens:**

1. Browser opens automatically
2. Sign in with your Google account
3. Click **Allow** to grant permissions
4. Token is saved to `oauth_token.pickle`
5. Gateway starts successfully

**Subsequent runs:** Just run `python main.py` - no browser needed!

---

## Option 2: Application Default Credentials (ADC)

ADC is the simplest method. Best for production and when you want a one-time setup.

### Step 1: Authenticate with Google

```powershell
# Authenticate with your Google account
gcloud auth application-default login
```

This will:

1. Open your browser
2. Sign in with Google
3. Save credentials automatically
4. Work for all Google Cloud APIs

### Step 2: Grant User Permissions

```bash
# Grant Dialogflow permissions to your account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@gmail.com" \
    --role="roles/dialogflow.client"
```

### Step 3: Configure Gateway

Edit `config/config.yaml`:

```yaml
connectors:
  dialogflow_cx_connector:
    type: "dialogflow_cx_connector"
    class: "DialogflowCXConnector"
    module: "connectors.dialogflow_cx_connector"
    config:
      # Your Dialogflow CX details
      project_id: "your-project-id"
      agent_id: "your-agent-id"
      location: "global"

      # No oauth_client_id or oauth_client_secret = uses ADC automatically

      # Audio settings
      language_code: "en-US"
      sample_rate_hertz: 16000
      audio_encoding: "AUDIO_ENCODING_LINEAR_16"
      force_input_format: "wxcc"

      agents:
        - "Dialogflow CX Agent"
```

### Step 4: Start Gateway

```bash
# Activate virtual environment
venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate  # macOS/Linux

# Start gateway
python main.py
```

That's it! ADC is automatically used.

---

## Running the Gateway

### Start the Server

```bash
# 1. Activate virtual environment (REQUIRED)
venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate  # macOS/Linux

# 2. Start the gateway
python main.py
```

### Verify It's Running

Look for these messages:

```
INFO - DialogflowCXConnector initialized for agent: projects/your-project/locations/global/agents/your-agent
INFO - Dialogflow CX SessionsClient initialized successfully
INFO - Server started on port 50051
INFO - Monitoring interface available at http://0.0.0.0:8080
```

### Stop the Server

Press `Ctrl+C` in the terminal

---

## Monitoring

### Web Interface

Once running, access the monitoring dashboard:

- **Main Dashboard**: http://localhost:8080
- **Status API**: http://localhost:8080/api/status
- **Health Check**: http://localhost:8080/health

### Dashboard Features

- **Real-time Status**: Gateway and connector status
- **Active Connections**: Live session tracking
- **Available Agents**: Configured Dialogflow CX agents
- **Configuration**: View current settings

---

## Configuration Reference

### Complete Configuration Example

```yaml
# Gateway settings
gateway:
  host: "0.0.0.0"
  port: 50051

# Monitoring interface
monitoring:
  enabled: true
  host: "0.0.0.0"
  port: 8080

# Connectors
connectors:
  dialogflow_cx_connector:
    type: "dialogflow_cx_connector"
    class: "DialogflowCXConnector"
    module: "connectors.dialogflow_cx_connector"
    config:
      # Required: Google Cloud project ID
      project_id: "your-project-id"

      # Required: Dialogflow CX agent ID
      agent_id: "your-agent-id"

      # Required: Agent location
      location: "global"

      # Optional: OAuth 2.0 credentials (if using OAuth)
      # oauth_client_id: "YOUR_CLIENT_ID.apps.googleusercontent.com"
      # oauth_client_secret: "YOUR_CLIENT_SECRET"
      # oauth_token_file: "oauth_token.pickle"

      # Audio settings for WxCC
      language_code: "en-US"
      sample_rate_hertz: 16000
      audio_encoding: "AUDIO_ENCODING_LINEAR_16"
      force_input_format: "wxcc"
      min_audio_seconds: 2.5
      max_audio_seconds: 5.0

      # Agent names exposed to WxCC
      agents:
        - "Dialogflow CX Agent"

# Logging
logging:
  gateway:
    level: "INFO"
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: "logs/gateway.log"
```

---

## Troubleshooting

### OAuth Errors

**Error: "redirect_uri_mismatch"**

- Add `http://localhost:8090/` to OAuth redirect URIs in Google Cloud Console
- Include the trailing slash `/`
- Wait 5 minutes after saving

**Error: "invalid_client"**

- Verify Client ID and Client Secret are correct
- Check for extra spaces or line breaks in config.yaml

### ADC Errors

**Error: "Could not automatically determine credentials"**

```bash
# Re-authenticate
gcloud auth application-default login
```

**Error: "Permission denied"**

```bash
# Grant Dialogflow permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@gmail.com" \
    --role="roles/dialogflow.client"
```

### Port Already in Use

```powershell
# Windows - Find and kill process on port 50051
netstat -ano | findstr :50051
taskkill /PID <PID_NUMBER> /F

# Or change port in config/config.yaml
```

### Check Logs

```bash
# View gateway logs
type logs\gateway.log  # Windows
# tail -f logs/gateway.log  # macOS/Linux
```

---

## Additional Documentation

### Detailed Guides

- **[OAuth 2.0 Authentication Guide](docs/OAUTH_AUTHENTICATION.md)** - Complete OAuth setup and troubleshooting
- **[Dialogflow CX Setup Guide](docs/guides/byova-dialogflow-cx-setup.md)** - Comprehensive Dialogflow CX integration guide
- **[AWS Lex Setup Guide](docs/guides/byova-aws-lex-setup.md)** - AWS Lex integration guide

### Development

- **[Connectors Documentation](src/connectors/README.md)** - Creating custom connectors
- **[Audio Files Guide](audio/README.md)** - Audio format and configuration
- **[Agent Architecture](AGENTS.MD)** - AI agent guidelines for this project

### API Reference

- **gRPC Endpoints**: `ListVirtualAgents`, `ProcessCallerInput`
- **HTTP Endpoints**: `/api/status`, `/api/connections`, `/health`

---

## Project Structure

```
webex-byova-gateway-python/
├── audio/                    # Audio files for local connector
├── config/
│   ├── config.yaml          # Main configuration file
│   ├── dialogflow_cx_example.yaml
│   └── aws_lex_example.yaml
├── docs/                     # Documentation
│   ├── guides/
│   │   ├── byova-dialogflow-cx-setup.md
│   │   └── byova-aws-lex-setup.md
│   └── OAUTH_AUTHENTICATION.md
├── proto/                    # Protocol Buffer definitions
├── src/
│   ├── connectors/           # Virtual agent connectors
│   │   ├── dialogflow_cx_connector.py
│   │   ├── local_audio_connector.py
│   │   └── i_vendor_connector.py
│   ├── core/                # Core gateway components
│   ├── generated/           # Generated gRPC stubs
│   ├── monitoring/          # Web monitoring interface
│   └── utils/               # Utility modules
├── main.py                  # Entry point
├── requirements.txt         # Dependencies
└── README.md
```

---

## Features

- ✅ **Google Dialogflow CX Integration** - Full support with OAuth 2.0 and ADC
- ✅ **AWS Lex Integration** - Amazon Lex v2 connector
- ✅ **Local Audio Connector** - Testing with audio files
- ✅ **gRPC Server** - BYOVA protocol implementation
- ✅ **Web Monitoring** - Real-time dashboard
- ✅ **Session Management** - Track active conversations
- ✅ **Extensible Architecture** - Easy to add new connectors

---

## License

[Cisco Sample Code License v1.1](LICENSE) © 2018 Cisco and/or its affiliates

**Note**: This Sample Code is not supported by Cisco TAC and is not tested for quality or performance. This is intended for example purposes only and is provided by Cisco "AS IS" with all faults and without warranty or support of any kind.

---

## Quick Reference

### Authentication Methods

| Method        | Command                                 | Use Case                     |
| ------------- | --------------------------------------- | ---------------------------- |
| **OAuth 2.0** | Configure in `config.yaml`              | Development, user-based auth |
| **ADC**       | `gcloud auth application-default login` | Production, simple setup     |

### Required IAM Roles

```bash
# For OAuth or ADC users
roles/dialogflow.client
```

### OAuth Scopes

```python
# Automatically used by the gateway
https://www.googleapis.com/auth/dialogflow
```

### Essential Commands

```bash
# Setup
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Generate gRPC stubs
python -m grpc_tools.protoc -I./proto --python_out=src/generated --grpc_python_out=src/generated proto/*.proto

# Start gateway
python main.py

# ADC authentication
gcloud auth application-default login
```

---

**Need Help?** Check the [OAuth Authentication Guide](docs/OAUTH_AUTHENTICATION.md) or [Dialogflow CX Setup Guide](docs/guides/byova-dialogflow-cx-setup.md) for detailed instructions.
