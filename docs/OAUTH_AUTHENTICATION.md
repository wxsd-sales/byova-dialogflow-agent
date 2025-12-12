# OAuth 2.0 Authentication for Dialogflow CX

This guide explains how to set up and use OAuth 2.0 authentication for the Dialogflow CX connector in the BYOVA Gateway.

## Overview

The Dialogflow CX connector now supports **three authentication methods**:

1. **Service Account Key File** - Best for service-to-service authentication (development/testing)
2. **OAuth 2.0 User Credentials** - Best for user-based access and development (NEW!)
3. **Application Default Credentials (ADC)** - Best for production environments

## Why Use OAuth 2.0?

OAuth 2.0 user credentials are useful when:

- You want to authenticate as a specific user rather than a service account
- You're developing locally and don't want to manage service account keys
- You need to access resources based on user permissions
- You want to leverage Google's user authentication and authorization

## Setting Up OAuth 2.0

### Step 1: Create OAuth 2.0 Credentials in Google Cloud Console

1. **Go to Google Cloud Console**

   - Navigate to [Google Cloud Console](https://console.cloud.google.com/)
   - Select your project

2. **Enable Required APIs**

   ```bash
   gcloud services enable dialogflow.googleapis.com
   ```

3. **Create OAuth 2.0 Client ID**

   - Go to **APIs & Services** > **Credentials**
   - Click **+ CREATE CREDENTIALS** > **OAuth client ID**
   - Choose **Application type**: `Desktop app`
   - Enter a **Name**: e.g., "BYOVA Gateway Desktop"
   - Click **CREATE**

4. **Download Credentials**

   - After creation, you'll see your **Client ID** and **Client secret**
   - Copy these values - you'll need them for configuration

   Example format:

   ```
   Client ID: 123456789-abcdefg.apps.googleusercontent.com
   Client Secret: GOCSPX-abcd1234efgh5678
   ```

### Step 2: Configure OAuth Consent Screen (If Required)

If you haven't already configured the OAuth consent screen:

1. Go to **APIs & Services** > **OAuth consent screen**
2. Choose **User Type**:
   - **Internal** (for Google Workspace users only)
   - **External** (for any Google account)
3. Fill in required fields:
   - App name
   - User support email
   - Developer contact information
4. Add scopes:
   - `https://www.googleapis.com/auth/cloud-platform`
5. Save and continue

### Step 3: Grant User Permissions

The user account used for OAuth needs IAM permissions:

```bash
# Grant Dialogflow Client role to the user
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@example.com" \
    --role="roles/dialogflow.client"
```

### Step 4: Configure the Gateway

Update your `config/config.yaml`:

```yaml
dialogflow_cx_connector:
  type: "dialogflow_cx_connector"
  class: "DialogflowCXConnector"
  module: "connectors.dialogflow_cx_connector"
  config:
    project_id: "your-project-id"
    agent_id: "your-agent-id"
    location: "global"
    language_code: "en-US"
    sample_rate_hertz: 8000
    audio_encoding: "AUDIO_ENCODING_MULAW"

    # OAuth 2.0 Configuration
    oauth_client_id: "123456789-abcdefg.apps.googleusercontent.com"
    oauth_client_secret: "GOCSPX-abcd1234efgh5678"
    oauth_token_file: "dialogflow_oauth_token.pickle" # Optional, default: oauth_token.pickle

    agents:
      - "Dialogflow CX Agent"
```

### Step 5: Install Required Dependencies

The OAuth functionality requires the `google-auth-oauthlib` package:

```bash
# Activate your virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install/update dependencies
pip install -r requirements.txt
```

### Step 6: First Run - Authorization Flow

When you start the gateway for the first time with OAuth configuration:

1. **Run the gateway**:

   ```bash
   python main.py
   ```

2. **Browser Opens Automatically**:

   - A browser window will open with Google's authorization page
   - You may see a warning if the app is unverified (click "Advanced" > "Go to [App name]")

3. **Sign In and Authorize**:

   - Sign in with your Google account
   - Review the permissions requested
   - Click **Allow**

4. **Success**:

   - The browser will show "The authentication flow has completed"
   - The gateway will save the token to `oauth_token_file`
   - Check the logs for: `OAuth authorization successful!`

5. **Subsequent Runs**:
   - The saved token will be used automatically
   - No browser interaction needed
   - Token is automatically refreshed when expired

### Step 7: Verify Authentication

Check the gateway logs for successful authentication:

```
INFO - Using OAuth 2.0 credentials from dialogflow_oauth_token.pickle
INFO - Dialogflow CX SessionsClient initialized successfully using OAuth 2.0: dialogflow_oauth_token.pickle
```

## Configuration Reference

### OAuth Configuration Parameters

| Parameter             | Required | Default              | Description                                       |
| --------------------- | -------- | -------------------- | ------------------------------------------------- |
| `oauth_client_id`     | Yes\*    | None                 | OAuth 2.0 Client ID from Google Cloud Console     |
| `oauth_client_secret` | Yes\*    | None                 | OAuth 2.0 Client Secret from Google Cloud Console |
| `oauth_token_file`    | No       | `oauth_token.pickle` | Path to store/load the OAuth token                |

\* Required only if using OAuth authentication method

### Authentication Priority

The connector tries authentication methods in this order:

1. **Service Account Key** - If `service_account_key` is configured
2. **OAuth 2.0** - If `oauth_client_id` and `oauth_client_secret` are configured
3. **Application Default Credentials** - If no auth parameters are specified

## OAuth Token Management

### Token Storage

- OAuth tokens are stored in a pickle file (default: `oauth_token.pickle`)
- The file contains access tokens, refresh tokens, and expiry information
- **Important**: Add `*.pickle` to your `.gitignore` file!

### Token Refresh

- Tokens are automatically refreshed when expired
- Refresh happens transparently without user interaction
- If refresh fails, a new authorization flow is initiated

### Revoking Access

To revoke OAuth access:

1. **Delete the token file**:

   ```bash
   rm oauth_token.pickle
   ```

2. **Revoke in Google Account Settings**:
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Navigate to **Third-party apps with account access**
   - Find your app and click **Remove Access**

## Troubleshooting

### Browser Doesn't Open

**Problem**: Authorization flow starts but browser doesn't open

**Solutions**:

- The connector will fall back to console-based auth
- Copy the URL from the terminal and open it manually
- Paste the authorization code back into the terminal

### "Access Blocked: Authorization Error"

**Problem**: Google shows "This app isn't verified"

**Solutions**:

- For development: Click "Advanced" > "Go to [app name]"
- For production: Submit app for verification in Google Cloud Console
- Use internal user type if within Google Workspace organization

### Token Expired or Invalid

**Problem**: `Invalid credentials` or `Token expired` errors

**Solutions**:

```bash
# Delete the token file and re-authorize
rm oauth_token.pickle
python main.py
```

### Permission Denied

**Problem**: `403 Forbidden` or `Permission denied` errors

**Solutions**:

- Verify the user has `roles/dialogflow.client` role
- Check IAM permissions in Google Cloud Console:
  ```bash
  gcloud projects get-iam-policy YOUR_PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:user:your-email@example.com"
  ```

### Import Error: google_auth_oauthlib

**Problem**: `ImportError: No module named 'google_auth_oauthlib'`

**Solution**:

```bash
pip install google-auth-oauthlib>=1.2.0
```

## Security Best Practices

### 1. Never Commit Secrets

```bash
# Add to .gitignore
*.pickle
oauth_token.pickle
*_oauth_token.pickle
client_secret*.json
```

### 2. Use Environment Variables

Instead of hardcoding in config:

```yaml
oauth_client_id: "${OAUTH_CLIENT_ID}"
oauth_client_secret: "${OAUTH_CLIENT_SECRET}"
```

Set environment variables:

```bash
export OAUTH_CLIENT_ID="your-client-id"
export OAUTH_CLIENT_SECRET="your-client-secret"
```

### 3. Restrict OAuth Scopes

The connector uses:

- `https://www.googleapis.com/auth/cloud-platform`

This is a broad scope. For production, consider creating a more restrictive custom scope.

### 4. Regular Token Rotation

- Tokens should be rotated periodically
- Delete old token files after rotation
- Monitor OAuth consent screen for suspicious activity

### 5. Use Internal User Type

For Google Workspace organizations:

- Set OAuth consent screen to "Internal"
- Limits authorization to organization users only
- Reduces security risks

## Comparison of Authentication Methods

| Feature              | Service Account     | OAuth 2.0              | ADC               |
| -------------------- | ------------------- | ---------------------- | ----------------- |
| **Use Case**         | Service-to-service  | User-based development | Production        |
| **Setup Complexity** | Medium              | Medium                 | Low               |
| **User Interaction** | None                | Initial authorization  | None\*            |
| **Token Management** | Manual key rotation | Automatic refresh      | Automatic         |
| **Best For**         | Automated services  | Local development      | GCP environments  |
| **Security**         | Key file risk       | User-based permissions | Environment-based |

\* Depends on environment

## Example Configurations

### Development (OAuth)

```yaml
dialogflow_cx_connector:
  config:
    project_id: "dev-project"
    agent_id: "dev-agent"
    oauth_client_id: "123456-dev.apps.googleusercontent.com"
    oauth_client_secret: "DEV_SECRET"
    oauth_token_file: "dev_oauth_token.pickle"
```

### Production (ADC)

```yaml
dialogflow_cx_connector:
  config:
    project_id: "prod-project"
    agent_id: "prod-agent"
    # No auth params - uses ADC
```

### Testing (Service Account)

```yaml
dialogflow_cx_connector:
  config:
    project_id: "test-project"
    agent_id: "test-agent"
    service_account_key: "/secrets/test-sa-key.json"
```

## Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Dialogflow CX Authentication](https://cloud.google.com/dialogflow/cx/docs/quick/setup)
- [Google Cloud IAM Roles](https://cloud.google.com/dialogflow/cx/docs/concept/access-control)
- [OAuth Consent Screen Configuration](https://support.google.com/cloud/answer/10311615)

## Support

For issues or questions:

- Check the gateway logs for detailed error messages
- Review Google Cloud Console for IAM and OAuth settings
- Consult the main BYOVA documentation
- Contact your Webex Contact Center representative
