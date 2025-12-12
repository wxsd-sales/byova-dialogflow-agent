---
layout: guide
title: "Google Dialogflow CX Integration Guide"
description: "Complete guide for integrating Google Dialogflow CX with Webex Contact Center BYOVA Gateway"
---

# Google Dialogflow CX Integration Guide

This guide walks you through setting up and configuring Google Dialogflow CX with the Webex Contact Center BYOVA Gateway.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Google Cloud Setup](#google-cloud-setup)
4. [Dialogflow CX Agent Configuration](#dialogflow-cx-agent-configuration)
5. [Gateway Configuration](#gateway-configuration)
6. [Authentication Setup](#authentication-setup)
7. [Testing the Integration](#testing-the-integration)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Dialogflow CX connector enables your Webex Contact Center to interact with Google's advanced conversational AI platform. This integration supports:

- **Real-time audio streaming** between WxCC and Dialogflow CX
- **Bidirectional conversation flow** for natural interactions
- **Multi-language support** for global deployments
- **Advanced NLU capabilities** with Dialogflow CX's powerful intent recognition
- **Rich response types** including text, audio, and custom payloads

### Architecture

```
┌─────────────────┐      gRPC Audio Stream      ┌──────────────────┐
│  Webex Contact  │ ◄────────────────────────► │  BYOVA Gateway   │
│     Center      │                             │                  │
└─────────────────┘                             └────────┬─────────┘
                                                         │
                                                         │ Dialogflow CX
                                                         │ Sessions API
                                                         │
                                                         ▼
                                                ┌──────────────────┐
                                                │  Google Cloud    │
                                                │  Dialogflow CX   │
                                                │     Agent        │
                                                └──────────────────┘
```

---

## Prerequisites

Before you begin, ensure you have:

1. **Google Cloud Account**

   - Active GCP project with billing enabled
   - Access to Dialogflow CX console

2. **Dialogflow CX Agent**

   - A created and configured Dialogflow CX agent
   - Agent published with at least one flow

3. **BYOVA Gateway**

   - Gateway installed and running
   - Python 3.8 or higher

4. **Required Permissions**
   - Permission to create service accounts in GCP
   - Permission to assign IAM roles
   - Access to create and manage Dialogflow CX agents

---

## Google Cloud Setup

### Step 1: Create or Select a GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your **Project ID** (you'll need this for configuration)

### Step 2: Enable Required APIs

Enable the Dialogflow API for your project:

```bash
# Using gcloud CLI
gcloud services enable dialogflow.googleapis.com
```

Or through the console:

1. Navigate to **APIs & Services** > **Library**
2. Search for "Dialogflow API"
3. Click **Enable**

### Step 3: Create a Service Account

Create a service account for authentication:

```bash
# Create service account
gcloud iam service-accounts create dialogflow-byova \
    --display-name="Dialogflow BYOVA Gateway" \
    --description="Service account for BYOVA Gateway to access Dialogflow CX"
```

### Step 4: Grant Required IAM Roles

Grant the necessary permissions:

```bash
# Get your project ID
export PROJECT_ID=$(gcloud config get-value project)

# Grant Dialogflow API Client role
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:dialogflow-byova@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/dialogflow.client"

# Grant Dialogflow API Admin role (if you need to manage agents)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:dialogflow-byova@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/dialogflow.admin"
```

### Step 5: Create and Download Service Account Key

```bash
# Create key file
gcloud iam service-accounts keys create dialogflow-key.json \
    --iam-account=dialogflow-byova@${PROJECT_ID}.iam.gserviceaccount.com

# Move to secure location
mkdir -p ~/.gcp/keys
mv dialogflow-key.json ~/.gcp/keys/

# Set restrictive permissions
chmod 600 ~/.gcp/keys/dialogflow-key.json
```

⚠️ **Security Warning**: Never commit service account keys to version control!

---

## Dialogflow CX Agent Configuration

### Step 1: Create a Dialogflow CX Agent

1. Go to [Dialogflow CX Console](https://dialogflow.cloud.google.com/cx/)
2. Click **Create Agent**
3. Configure agent settings:

   - **Display Name**: Your agent name
   - **Location**: Choose a region (e.g., `global`, `us-central1`)
   - **Default Language**: Select primary language (e.g., `en-US`)
   - **Time Zone**: Your preferred timezone

4. Note the **Agent ID** from the agent settings (found in the URL or settings page)

### Step 2: Configure for Telephony

1. In your agent, go to **Agent Settings**
2. Navigate to **Speech and IVR** settings
3. Configure audio settings:
   - **Speech Recognition**: Enabled
   - **Text-to-Speech**: Enabled
   - **Audio Encoding**: Set to support μ-law (MULAW)
   - **Sample Rate**: 8000 Hz (for telephony)

### Step 3: Create Intents and Flows

Set up your conversational flows:

1. Create **Intents** for user inputs
2. Design **Flows** for conversation logic
3. Add **Pages** for different conversation states
4. Configure **Fulfillment** for dynamic responses

Example welcome flow:

```
Start Page
  ├── Intent: Default Welcome Intent
  ├── Response: "Hello! How can I help you today?"
  └── Transition to: Main Menu Page
```

### Step 4: Test Your Agent

Use the Dialogflow CX console's test simulator:

1. Click **Test Agent** in the top-right
2. Try voice or text input
3. Verify responses are correct
4. Check flow transitions work as expected

---

## Gateway Configuration

### Step 1: Install Dependencies

Install the required Python packages:

```bash
# Activate your virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Dialogflow CX SDK
pip install google-cloud-dialogflow-cx>=1.33.0
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

### Step 2: Configure the Connector

Edit `config/config.yaml` and add the Dialogflow CX connector configuration:

```yaml
connectors:
  # ... other connectors ...

  dialogflow_cx_connector:
    type: "dialogflow_cx_connector"
    class: "DialogflowCXConnector"
    module: "connectors.dialogflow_cx_connector"
    config:
      # Required: Your GCP project ID
      project_id: "your-project-id"

      # Required: Your Dialogflow CX agent ID
      # Find this in Dialogflow CX console URL or agent settings
      agent_id: "your-agent-id"

      # Required: Location where your agent is hosted
      # Options: 'global', 'us-central1', 'europe-west1', 'asia-northeast1', etc.
      location: "global"

      # Optional: Path to service account key file
      # If not specified, uses Application Default Credentials
      service_account_key: "/path/to/your/dialogflow-key.json"

      # Optional: Language code (default: en-US)
      language_code: "en-US"

      # Optional: Audio sample rate in Hz (default: 8000)
      # WxCC uses 8000 Hz for telephony
      sample_rate_hertz: 8000

      # Optional: Audio encoding (default: AUDIO_ENCODING_MULAW)
      # WxCC typically uses MULAW encoding
      audio_encoding: "AUDIO_ENCODING_MULAW"

      # Optional: List of agent names to expose to WxCC
      agents:
        - "Customer Service Bot"
        - "Sales Assistant"
```

### Step 3: Verify Configuration

Check your configuration file syntax:

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

---

## Authentication Setup

You have two options for authentication:

### Option 1: Service Account Key File (Development)

Best for local development and testing:

1. Download service account key (see [Google Cloud Setup](#step-5-create-and-download-service-account-key))
2. Set `service_account_key` in configuration
3. Ensure file has restrictive permissions (600)

```yaml
config:
  service_account_key: "~/.gcp/keys/dialogflow-key.json"
```

### Option 2: Application Default Credentials (Production)

Recommended for production environments:

1. **On GCP (Compute Engine, GKE, Cloud Run)**:

   - Attach service account to compute resource
   - No configuration needed - automatically uses attached service account

2. **Locally for testing**:

   ```bash
   gcloud auth application-default login
   ```

3. **In Docker/Kubernetes**:

   - Use Workload Identity (GKE)
   - Or mount service account key as secret

4. **Configuration**: Don't set `service_account_key` parameter

```yaml
config:
  # No service_account_key specified - uses ADC
  project_id: "your-project-id"
  agent_id: "your-agent-id"
```

### Environment Variables (Alternative)

You can also use environment variables:

```bash
# Set service account key location
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"

# Or use gcloud CLI default credentials
gcloud auth application-default login
```

---

## Testing the Integration

### Step 1: Start the Gateway

```bash
# Activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# Start the gateway
python main.py
```

Look for successful startup messages:

```
INFO - DialogflowCXConnector initialized for agent: projects/your-project/locations/global/agents/your-agent
INFO - Successfully loaded connector 'dialogflow_cx_connector' (DialogflowCXConnector) with 1 agents
INFO - Server started on port 50051
```

### Step 2: Check Available Agents

Visit the monitoring interface:

```
http://localhost:8080/status
```

You should see your Dialogflow CX agents listed.

### Step 3: Test with WxCC Flow

1. Import the BYOVA flow into Webex Contact Center
2. Configure the Virtual Agent activity to use your Dialogflow CX agent
3. Place a test call
4. Interact with the agent and verify responses

### Step 4: Monitor Logs

Watch the gateway logs for conversation flow:

```bash
# View real-time logs
tail -f logs/gateway.log

# Or run with debug logging
# Edit config.yaml: logging.gateway.level: "DEBUG"
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Authentication Errors

**Error**: `google.auth.exceptions.DefaultCredentialsError`

**Solutions**:

- Verify service account key path is correct
- Check file permissions (should be 600)
- Ensure service account has required roles
- Try: `gcloud auth application-default login`

#### 2. Agent Not Found

**Error**: `Agent 'projects/.../agents/...' not found`

**Solutions**:

- Verify `project_id`, `agent_id`, and `location` are correct
- Check agent exists in Dialogflow CX console
- Ensure agent is published
- Verify region/location matches

#### 3. Permission Denied

**Error**: `Permission denied` or `403 Forbidden`

**Solutions**:

- Verify service account has `roles/dialogflow.client` role
- Check IAM policy bindings:
  ```bash
  gcloud projects get-iam-policy YOUR_PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:dialogflow-byova*"
  ```
- Ensure API is enabled for the project

#### 4. Audio Issues

**Problem**: No audio response or garbled audio

**Solutions**:

- Verify `sample_rate_hertz` is 8000 (for WxCC)
- Check `audio_encoding` is `AUDIO_ENCODING_MULAW`
- Ensure Dialogflow CX agent has TTS enabled
- Test agent in Dialogflow console first

#### 5. Connection Timeout

**Error**: `Deadline exceeded` or timeout errors

**Solutions**:

- Check network connectivity to Google Cloud
- Verify firewall allows outbound HTTPS (443)
- Check for proxy settings that might interfere
- Try increasing timeout in configuration

### Debugging Tips

1. **Enable Debug Logging**:

   ```yaml
   logging:
     gateway:
       level: "DEBUG"
   ```

2. **Test Authentication**:

   ```bash
   python -c "
   from google.cloud import dialogflowcx_v3
   client = dialogflowcx_v3.SessionsClient()
   print('Authentication successful!')
   "
   ```

3. **Verify Agent Access**:

   ```bash
   # Using gcloud
   gcloud dialogflow agents describe YOUR_AGENT_ID \
     --location=global \
     --project=YOUR_PROJECT_ID
   ```

4. **Check Monitoring Dashboard**:
   - Visit `http://localhost:8080` for real-time connection status
   - Review active sessions and agent availability
   - Check for error messages in the dashboard

### Getting Help

If you continue to experience issues:

1. **Check Gateway Logs**: `logs/gateway.log`
2. **Review Google Cloud Logs**: [Cloud Logging Console](https://console.cloud.google.com/logs)
3. **Dialogflow CX Documentation**: [Official Docs](https://cloud.google.com/dialogflow/cx/docs)
4. **BYOVA Gateway Issues**: Check the repository issues page

---

## Best Practices

### Security

- ✅ Use Application Default Credentials in production
- ✅ Never commit service account keys to version control
- ✅ Use Secret Manager for sensitive configuration
- ✅ Grant minimal required IAM permissions
- ✅ Rotate service account keys regularly
- ✅ Use separate service accounts per environment

### Performance

- ✅ Deploy gateway in same region as Dialogflow CX agent
- ✅ Use `global` location for multi-region deployments
- ✅ Monitor latency in Cloud Logging
- ✅ Set appropriate timeout values
- ✅ Enable caching when appropriate

### Monitoring

- ✅ Enable Cloud Logging and Monitoring
- ✅ Set up alerts for errors and latency
- ✅ Monitor conversation metrics in Dialogflow CX console
- ✅ Use gateway monitoring interface for real-time status
- ✅ Track agent performance and user satisfaction

### Cost Optimization

- ✅ Review [Dialogflow CX pricing](https://cloud.google.com/dialogflow/pricing)
- ✅ Monitor API usage in Cloud Console
- ✅ Set up billing alerts
- ✅ Use appropriate agent editions (Basic vs. Enterprise)
- ✅ Clean up unused agents and test sessions

---

## Additional Resources

- [Dialogflow CX Documentation](https://cloud.google.com/dialogflow/cx/docs)
- [Dialogflow CX Python Client](https://github.com/googleapis/python-dialogflow-cx)
- [Google Cloud IAM Documentation](https://cloud.google.com/iam/docs)
- [Webex Contact Center BYOVA Documentation](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cust_contact/contact_center/webexcc/SetupandAdministrationGuide_2/b_mp-release-2/wcc_b_orch-dp-ug-new-2_chapter_0110.html)
- [BYOVA Gateway Main README](../../README.md)

---

## Example Configuration Files

See [`config/dialogflow_cx_example.yaml`](../../config/dialogflow_cx_example.yaml) for complete configuration examples including:

- Development environment setup
- Production environment setup
- Multi-language configuration
- Advanced audio settings

---

## Summary

You've successfully configured Google Dialogflow CX integration with the BYOVA Gateway! Your setup includes:

✅ Google Cloud project with Dialogflow API enabled  
✅ Service account with appropriate IAM roles  
✅ Dialogflow CX agent configured for telephony  
✅ Gateway connector properly configured  
✅ Authentication set up and tested  
✅ Integration verified with test calls

For questions or issues, refer to the [Troubleshooting](#troubleshooting) section or consult the additional resources above.
