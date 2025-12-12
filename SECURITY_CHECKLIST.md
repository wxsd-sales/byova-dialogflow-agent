# Security Checklist: What NOT to Push to GitHub

## ⚠️ CRITICAL - Never Push These Files

These files contain sensitive credentials and should **NEVER** be committed to GitHub:

### OAuth & Authentication Tokens

```
❌ *.pickle                          # OAuth tokens
❌ oauth_token.pickle                # OAuth token file
❌ dialogflow_oauth_token.pickle     # Dialogflow OAuth token
❌ *_token.pickle                    # Any token files
```

### Google Cloud Credentials

```
❌ *-key.json                        # Service account keys
❌ *_credentials.json                # Credential files
❌ client_secret*.json               # OAuth client secrets
❌ service-account*.json             # Service account keys
❌ gcp-credentials.json              # GCP credentials
```

### AWS Credentials

```
❌ .aws/                             # AWS credentials directory
❌ credentials                       # AWS credentials file
❌ *.pem                             # Private key files
```

### API Keys & Secrets

```
❌ .env                              # Environment variables
❌ *.secret                          # Secret files
❌ secrets/                          # Secrets directory
❌ .secrets/                         # Hidden secrets directory
```

### Configuration with Actual Credentials

```
❌ config/config.yaml (if it contains real credentials)
❌ config/production.yaml            # Production config
❌ config/local.yaml                 # Local config
```

---

## 📝 Files Already Ignored (Don't Push)

Your `.gitignore` already handles these:

### Python Generated Files

```
✅ __pycache__/                      # Python cache
✅ *.pyc, *.pyo                      # Compiled Python
✅ venv/, env/                       # Virtual environments
```

### Generated gRPC Files

```
✅ src/generated/*_pb2.py            # Generated protobuf
✅ src/generated/*_pb2_grpc.py       # Generated gRPC stubs
```

### Logs & Temporary Files

```
✅ logs/                             # Log directory
✅ *.log                             # Log files
✅ tmp/, temp/                       # Temporary files
```

### IDE & OS Files

```
✅ .idea/                            # PyCharm
✅ .vscode/                          # VS Code
✅ .DS_Store                         # macOS
✅ Thumbs.db                         # Windows
```

---

## ✅ Safe to Push (Template Files Only)

These files are safe to push **IF** they contain templates/examples only:

### Configuration Templates

```
✅ config/config.yaml                # With placeholder values
✅ config/dialogflow_cx_example.yaml # Example configuration
✅ config/aws_lex_example.yaml       # Example configuration
```

**Example of safe config.yaml:**

```yaml
dialogflow_cx_connector:
  config:
    project_id: "YOUR_PROJECT_ID" # ✅ Placeholder
    agent_id: "YOUR_AGENT_ID" # ✅ Placeholder
    oauth_client_id: "YOUR_CLIENT_ID" # ✅ Placeholder
    oauth_client_secret: "YOUR_CLIENT_SECRET" # ✅ Placeholder
```

**Example of UNSAFE config.yaml (DO NOT PUSH):**

```yaml
dialogflow_cx_connector:
  config:
    project_id: "production-wxcc-12345" # ❌ Real project ID
    agent_id: "abc-123-real-agent" # ❌ Real agent ID
    oauth_client_id: "1086062648388-real..." # ❌ Real client ID
    oauth_client_secret: "GOCSPX-RealSecret" # ❌ Real secret
```

---

## 🔍 Before You Push - Security Checklist

Run this checklist before every `git push`:

### 1. Check for Credentials

```bash
# Search for potential secrets in staged files
git diff --cached | grep -i "secret\|password\|key\|token\|credential"

# Check for pickle files
git status | grep -i "\.pickle"

# Check for JSON credential files
git status | grep -i "\-key\.json\|client_secret"
```

### 2. Verify No Real Credentials in Config

```bash
# Review your config file
cat config/config.yaml

# Look for real values (not placeholders)
# ❌ Bad: oauth_client_id: "1086062648388-vflqmfbkn6hdbg6rbq3i4mileatf2bhq.apps.googleusercontent.com"
# ✅ Good: oauth_client_id: "YOUR_CLIENT_ID.apps.googleusercontent.com"
```

### 3. Check Git Status

```bash
# See what files are staged
git status

# Review actual changes
git diff --cached
```

### 4. Verify .gitignore is Working

```bash
# These commands should return EMPTY:
git status | grep "\.pickle"
git status | grep "\-key\.json"
git status | grep "oauth_token"
```

---

## 🚨 What to Do If You Accidentally Pushed Credentials

### If You Just Pushed (< 5 minutes ago)

1. **Immediately remove from history:**

   ```bash
   # Remove file from history
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch path/to/secret-file" \
     --prune-empty --tag-name-filter cat -- --all

   # Force push (WARNING: Dangerous!)
   git push origin --force --all
   ```

2. **Rotate ALL compromised credentials:**

   - OAuth Client Secret → Create new OAuth client
   - Service Account Key → Delete old key, create new one
   - API Keys → Revoke and generate new ones

3. **Notify your team immediately**

### If Credentials Were Pushed Long Ago

1. **Assume credentials are compromised**
2. **Rotate ALL credentials immediately**
3. **Consider the repository compromised**
4. **Audit for any unauthorized access**

---

## 📋 Recommended .gitignore Sections

Your `.gitignore` now includes these security sections:

```gitignore
# Google Cloud & OAuth credentials (SECURITY CRITICAL)
*.pickle
*_token.pickle
oauth_token*.pickle
dialogflow_oauth_token.pickle
*-key.json
*_credentials.json
client_secret*.json
service-account*.json
gcp-credentials.json

# AWS credentials
.aws/
*.pem
credentials

# API keys and secrets
secrets/
.secrets/
*.secret

# Configuration files with sensitive data
config/local.yaml
config/production.yaml
*.env
```

---

## 🎯 Quick Reference

### Files You Have That Should NEVER Be Pushed

Based on your current setup:

```
❌ dialogflow_oauth_token.pickle          # Your OAuth token
❌ oauth_token.pickle                     # Any OAuth token
❌ config/config.yaml (with real values)  # If it has real credentials
```

### Safe Commands

```bash
# Check what would be pushed
git diff --cached

# Check for ignored files
git status --ignored

# See if any sensitive files are tracked
git ls-files | grep -E "\.pickle|key\.json|secret"
```

### Unsafe Commands (Use with Caution)

```bash
# ⚠️ This forces ALL files to be added (bypasses .gitignore)
git add -f                    # DON'T USE THIS

# ⚠️ This adds everything including ignored files
git add --all                 # DANGEROUS if .gitignore is incomplete
```

---

## 🔒 Best Practices

### 1. Use Environment Variables for Secrets

**Bad:**

```yaml
oauth_client_secret: "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"
```

**Good:**

```yaml
oauth_client_secret: "${OAUTH_CLIENT_SECRET}"
```

Then set in environment:

```bash
export OAUTH_CLIENT_SECRET="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"
```

### 2. Use Separate Config Files

- `config/config.example.yaml` → Push to GitHub (template)
- `config/config.yaml` → Never push (real credentials)

### 3. Document Required Credentials

In your README, list what credentials are needed without showing actual values:

```markdown
Required credentials:

- OAuth Client ID (from Google Cloud Console)
- OAuth Client Secret (from Google Cloud Console)
- Project ID (your GCP project)
- Agent ID (your Dialogflow CX agent)
```

### 4. Use Git Hooks (Optional)

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Check for potential secrets
if git diff --cached | grep -iE "secret|password|key.*="; then
    echo "⚠️  Potential secret detected in commit!"
    echo "Review your changes before committing."
    exit 1
fi
```

---

## 📚 Additional Resources

- [GitHub: Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [Git: .gitignore documentation](https://git-scm.com/docs/gitignore)
- [OWASP: Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

---

## ✅ Summary

### NEVER Push:

- ✋ OAuth tokens (\*.pickle)
- ✋ Service account keys (\*-key.json)
- ✋ Client secrets (client_secret\*.json)
- ✋ Real credentials in config files
- ✋ .env files
- ✋ AWS credentials

### ALWAYS Push:

- ✅ Template/example configs
- ✅ Documentation
- ✅ Source code (without secrets)
- ✅ .gitignore file
- ✅ README with setup instructions

### Before Every Push:

1. Run `git diff --cached`
2. Check for real credentials
3. Verify .gitignore is working
4. Review git status

**Remember: Once credentials are pushed to GitHub, assume they are compromised!**
