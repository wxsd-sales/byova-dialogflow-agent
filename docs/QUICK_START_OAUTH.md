# Quick Start: OAuth 2.0 Authentication

Get started with OAuth 2.0 authentication for Dialogflow CX in 5 minutes.

## Prerequisites

- Google Cloud account with Dialogflow CX agent
- Python 3.8+ with virtual environment activated
- BYOVA Gateway installed

## Step 1: Install Dependencies (30 seconds)

```bash
# Activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install OAuth package
pip install google-auth-oauthlib>=1.2.0

# Or install all dependencies
pip install -r requirements.txt
```

## Step 2: Create OAuth Credentials (2 minutes)

### In Google Cloud Console:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** > **Credentials**
3. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
4. Choose **Application type**: `Desktop app`
5. Click **CREATE**
6. Copy your **Client ID** and **Client secret**

Example values:

```
Client ID: 123456789-abc123.apps.googleusercontent.com
Client secret: GOCSPX-AbCdEf123456
```

## Step 3: Configure Gateway (1 minute)

Edit `config/config.yaml`:

```yaml
dialogflow_cx_connector:
  type: "dialogflow_cx_connector"
  class: "DialogflowCXConnector"
  module: "connectors.dialogflow_cx_connector"
  config:
    # Your project details
    project_id: "your-project-id"
    agent_id: "your-agent-id"
    location: "global"

    # OAuth credentials (paste from Step 2)
    oauth_client_id: "123456789-abc123.apps.googleusercontent.com"
    oauth_client_secret: "GOCSPX-AbCdEf123456"
    oauth_token_file: "oauth_token.pickle"

    # Standard settings
    language_code: "en-US"
    sample_rate_hertz: 8000
    audio_encoding: "AUDIO_ENCODING_MULAW"

    agents:
      - "Dialogflow CX Agent"
```

## Step 4: Run and Authorize (1 minute)

### Start the gateway:

```bash
python main.py
```

### First-time authorization:

1. **Browser opens automatically** with Google sign-in
2. **Sign in** with your Google account
3. **Click "Allow"** to grant permissions
4. **Close browser** - authorization complete!

### You should see:

```
INFO - Starting OAuth 2.0 authorization flow...
INFO - OAuth authorization successful!
INFO - OAuth credentials saved to oauth_token.pickle
INFO - Using OAuth 2.0 credentials from oauth_token.pickle
INFO - Dialogflow CX SessionsClient initialized successfully
INFO - Server started on port 50051
```

## Step 5: Test (30 seconds)

Open the monitoring interface:

```
http://localhost:8080
```

You should see your Dialogflow CX agent listed!

## Next Runs

**No browser needed!** The token is cached:

```bash
python main.py
```

## Troubleshooting

### Browser doesn't open?

- Copy the URL from terminal
- Open manually in browser
- Complete authorization
- Paste code back in terminal

### "App not verified" warning?

- Click **Advanced**
- Click **Go to [Your App Name] (unsafe)**
- This is normal for unverified apps in development

### Permission denied?

```bash
# Grant your user Dialogflow permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@gmail.com" \
    --role="roles/dialogflow.client"
```

## Security Reminders

Add to `.gitignore`:

```
oauth_token.pickle
*.pickle
```

Never commit:

- ❌ `oauth_client_secret`
- ❌ `oauth_token.pickle`
- ❌ OAuth credentials

## Switching Authentication Methods

### From OAuth to ADC:

```yaml
# Remove these lines from config:
# oauth_client_id: "..."
# oauth_client_secret: "..."
```

### From OAuth to Service Account:

```yaml
# Replace OAuth config with:
service_account_key: "/path/to/key.json"
```

## Complete Example Config

```yaml
gateway:
  host: "0.0.0.0"
  port: 50051

connectors:
  dialogflow_cx_connector:
    type: "dialogflow_cx_connector"
    class: "DialogflowCXConnector"
    module: "connectors.dialogflow_cx_connector"
    config:
      project_id: "my-project-123"
      agent_id: "abc-def-456"
      location: "global"
      oauth_client_id: "123456-xyz.apps.googleusercontent.com"
      oauth_client_secret: "GOCSPX-SecretKey123"
      oauth_token_file: "dialogflow_oauth.pickle"
      language_code: "en-US"
      sample_rate_hertz: 8000
      audio_encoding: "AUDIO_ENCODING_MULAW"
      agents:
        - "My Virtual Agent"

monitoring:
  enabled: true
  host: "0.0.0.0"
  port: 8080
```

## What's Next?

- 📖 Read full documentation: `docs/OAUTH_AUTHENTICATION.md`
- 🔒 Review security practices
- 🧪 Test with Webex Contact Center
- 📊 Monitor at http://localhost:8080

## Need Help?

- Check logs: `logs/gateway.log`
- Review: `docs/OAUTH_AUTHENTICATION.md`
- Verify Google Cloud Console settings
- Ensure IAM permissions are correct

---

**That's it!** You're now using OAuth 2.0 authentication with Dialogflow CX. 🎉
