# Direct Access Token Authentication

This guide explains how to use a direct access token for Google Dialogflow CX authentication instead of OAuth 2.0 flow or ADC.

## Overview

The gateway now supports **4 authentication methods**:

| Method | Auto-Refresh | Validity | Best For |
|--------|--------------|----------|----------|
| **1. Access Token** | ❌ No | ~1 hour | Testing, CI/CD with short jobs |
| **2. Service Account** | ✅ Yes | Until revoked | Production, automated systems |
| **3. OAuth 2.0** | ✅ Yes | Months | Development, user-based access |
| **4. ADC** | ✅ Yes | Varies | Production on GCP |

## When to Use Access Tokens

### ✅ Good Use Cases

- **Short-lived testing** (< 1 hour)
- **CI/CD pipelines** where jobs complete quickly
- **One-time scripts** or data migrations
- **Debugging** authentication issues
- **Temporary access** for contractors/external users

### ❌ Bad Use Cases

- **Long-running services** (gateway will fail after 1 hour)
- **Production deployments** (no auto-refresh)
- **Unattended operations** (requires manual token refresh)

## How to Get an Access Token

### Method 1: Using gcloud CLI (Recommended)

```bash
# Get access token for your user account
gcloud auth print-access-token

# Output example:
# ya29.a0Aa4xrXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

**Official Documentation:** https://cloud.google.com/sdk/gcloud/reference/auth/print-access-token

### Method 2: Using OAuth 2.0 Playground

1. Go to [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Click settings (⚙️) and check "Use your own OAuth credentials"
3. Enter your OAuth Client ID and Secret
4. In Step 1, select scope: `https://www.googleapis.com/auth/dialogflow`
5. Click "Authorize APIs"
6. In Step 2, click "Exchange authorization code for tokens"
7. Copy the **access_token** value

### Method 3: Using curl (OAuth Flow)

```bash
# Step 1: Get authorization code (opens browser)
# Step 2: Exchange code for token
curl -X POST https://oauth2.googleapis.com/token \
  -d "code=YOUR_AUTH_CODE" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob" \
  -d "grant_type=authorization_code"

# Response includes access_token
```

### Method 4: From Existing OAuth Token File

```python
import pickle

# Load existing OAuth token
with open('oauth_token.pickle', 'rb') as f:
    creds = pickle.load(f)

# Extract access token
print(f"Access Token: {creds.token}")
print(f"Expires: {creds.expiry}")
```

## Configuration

### config.yaml

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
      
      # Direct Access Token (Option 1)
      access_token: "ya29.a0Aa4xrXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
      
      # Audio settings
      language_code: "en-US"
      sample_rate_hertz: 16000
      audio_encoding: "AUDIO_ENCODING_LINEAR_16"
      force_input_format: "wxcc"
      
      agents:
        - "Dialogflow CX Agent"
```

### Using Environment Variables (Recommended)

**Better approach** - don't hardcode tokens in config files:

```yaml
connectors:
  dialogflow_cx_connector:
    config:
      project_id: "your-project-id"
      agent_id: "your-agent-id"
      
      # Use environment variable
      access_token: "${GCP_ACCESS_TOKEN}"
```

Then set the environment variable:

```bash
# Windows PowerShell
$env:GCP_ACCESS_TOKEN = "ya29.a0Aa4xr..."

# Windows Command Prompt
set GCP_ACCESS_TOKEN=ya29.a0Aa4xr...

# Linux/macOS
export GCP_ACCESS_TOKEN="ya29.a0Aa4xr..."
```

## Usage Example

### Quick Test Script

```bash
# 1. Get access token
$TOKEN = gcloud auth print-access-token

# 2. Set environment variable
$env:GCP_ACCESS_TOKEN = $TOKEN

# 3. Update config.yaml to use ${GCP_ACCESS_TOKEN}

# 4. Run gateway
python main.py
```

### CI/CD Pipeline Example

```yaml
# GitHub Actions example
name: Test Gateway

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Get Access Token
        run: |
          TOKEN=$(gcloud auth print-access-token)
          echo "GCP_ACCESS_TOKEN=$TOKEN" >> $GITHUB_ENV
      
      - name: Run Gateway Tests
        run: |
          python main.py &
          sleep 10
          # Run tests (gateway will work for ~1 hour)
          pytest tests/
```

## Important Warnings

### ⚠️ Token Expiration

Access tokens expire after **~1 hour** and **will NOT be auto-refreshed**:

```
Time 0:00  → Gateway starts successfully
Time 0:30  → Still working fine
Time 1:00  → Token expires
Time 1:01  → API calls start failing!
```

**Gateway logs will show:**
```
WARNING - ⚠️  Access token will expire in ~1 hour without refresh!
ERROR - Failed to detect intent: 401 Unauthorized
```

### ⚠️ No Automatic Refresh

Unlike OAuth 2.0 or Service Accounts, access tokens **cannot be refreshed**:

```python
# OAuth 2.0 (has refresh token)
creds.refresh(Request())  # ✅ Works

# Access Token (no refresh token)
creds.refresh(Request())  # ❌ Fails - no refresh token!
```

### ⚠️ Security Considerations

Access tokens are **bearer tokens** - anyone with the token can use it:

```bash
# ❌ BAD - Token visible in config file
access_token: "ya29.a0Aa4xr..."

# ✅ GOOD - Token in environment variable
access_token: "${GCP_ACCESS_TOKEN}"

# ❌ NEVER commit access tokens to Git!
```

## Comparison with Other Methods

### Access Token vs OAuth 2.0

| Feature | Access Token | OAuth 2.0 |
|---------|--------------|-----------|
| **Setup** | Get token, paste in config | Browser authorization once |
| **Validity** | ~1 hour | Months (auto-refresh) |
| **Refresh** | ❌ Manual | ✅ Automatic |
| **Best For** | Quick tests | Development |

### Access Token vs Service Account

| Feature | Access Token | Service Account |
|---------|--------------|-----------------|
| **Setup** | Get token | Download key file |
| **Validity** | ~1 hour | Until revoked |
| **Refresh** | ❌ No | ✅ Automatic |
| **Best For** | Testing | Production |

### Access Token vs ADC

| Feature | Access Token | ADC |
|---------|--------------|-----|
| **Setup** | Get token | `gcloud auth application-default login` |
| **Validity** | ~1 hour | Months |
| **Refresh** | ❌ No | ✅ Automatic |
| **Best For** | CI/CD | Production |

## Token Lifecycle

### Getting a Fresh Token

```bash
# Check if current token is valid
gcloud auth print-access-token --verbosity=debug

# Force new token
gcloud auth application-default print-access-token

# Token is valid for ~1 hour from generation time
```

### Checking Token Expiry

```python
from google.oauth2.credentials import Credentials
from datetime import datetime

# Create credentials from access token
creds = Credentials(token="ya29.a0Aa4xr...")

# Check status
print(f"Token valid: {creds.valid}")
print(f"Token expired: {creds.expired}")
print(f"Has refresh token: {creds.refresh_token is not None}")  # Will be False

# Note: expiry time is unknown for direct access tokens
# They typically expire in ~1 hour
```

### Refreshing Expired Token

When the token expires, you must:

1. **Get a new token**:
   ```bash
   gcloud auth print-access-token
   ```

2. **Update configuration**:
   ```bash
   # Update environment variable
   $env:GCP_ACCESS_TOKEN = "new_token_here"
   ```

3. **Restart gateway**:
   ```bash
   # Stop current instance (Ctrl+C)
   # Start new instance
   python main.py
   ```

## Best Practices

### 1. Use Environment Variables

```yaml
# ✅ GOOD
access_token: "${GCP_ACCESS_TOKEN}"

# ❌ BAD
access_token: "ya29.a0Aa4xr..."
```

### 2. Set Token Expiry Reminders

```bash
# Get token with timestamp
echo "Token obtained at: $(date)" > token_timestamp.txt
gcloud auth print-access-token > token.txt

# Set reminder to refresh in 50 minutes
```

### 3. Monitor for Expiration

```python
# Add monitoring to your gateway
import time
from datetime import datetime, timedelta

token_start_time = datetime.now()
TOKEN_LIFETIME = timedelta(minutes=55)  # Refresh before 60 min

while True:
    if datetime.now() - token_start_time > TOKEN_LIFETIME:
        logger.warning("Access token likely expired! Please refresh.")
    time.sleep(60)
```

### 4. Use for Short-Lived Jobs Only

```bash
# ✅ GOOD - Job completes in 30 minutes
./run_migration.sh  # Uses access token

# ❌ BAD - Service runs indefinitely
python main.py  # Don't use access token for this!
```

## Troubleshooting

### Error: "401 Unauthorized"

**Cause**: Token expired or invalid

**Solution**:
```bash
# Get fresh token
gcloud auth print-access-token

# Update environment variable
$env:GCP_ACCESS_TOKEN = "new_token"

# Restart gateway
python main.py
```

### Error: "Token has no refresh token"

**Cause**: Trying to refresh an access token (not possible)

**Solution**: Use OAuth 2.0 or Service Account instead for auto-refresh

### Gateway Works Then Stops After 1 Hour

**Cause**: Access token expired

**Solution**: 
- Switch to OAuth 2.0, Service Account, or ADC for long-running services
- Or implement automatic token refresh in your deployment script

## Migration Guide

### From Access Token to OAuth 2.0

```yaml
# Before (Access Token)
config:
  access_token: "ya29.a0Aa4xr..."

# After (OAuth 2.0 - auto-refresh)
config:
  oauth_client_id: "YOUR_CLIENT_ID.apps.googleusercontent.com"
  oauth_client_secret: "YOUR_CLIENT_SECRET"
  oauth_token_file: "oauth_token.pickle"
```

### From Access Token to ADC

```yaml
# Before (Access Token)
config:
  access_token: "ya29.a0Aa4xr..."

# After (ADC - auto-refresh)
config:
  # No auth parameters - uses ADC
```

Then run:
```bash
gcloud auth application-default login
```

## Official Documentation

- **Access Tokens**: https://cloud.google.com/docs/authentication/token-types#access
- **Token Lifecycle**: https://developers.google.com/identity/protocols/oauth2#expiration
- **gcloud auth**: https://cloud.google.com/sdk/gcloud/reference/auth/print-access-token
- **Google Auth Library**: https://google-auth.readthedocs.io/en/master/reference/google.oauth2.credentials.html

## Summary

### Quick Reference

**Get Token:**
```bash
gcloud auth print-access-token
```

**Configure:**
```yaml
access_token: "${GCP_ACCESS_TOKEN}"
```

**Use:**
```bash
$env:GCP_ACCESS_TOKEN = "ya29.a0Aa4xr..."
python main.py
```

**Remember:**
- ⏰ Expires in ~1 hour
- ❌ No auto-refresh
- ⚠️ Not for production
- ✅ Great for testing

**For production, use:**
- OAuth 2.0 (development)
- Service Account (automated systems)
- ADC (GCP environments)

