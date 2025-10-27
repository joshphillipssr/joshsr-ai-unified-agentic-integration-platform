# MCP Gateway Ink CLI - Comprehensive Guide

Complete guide to using the MCP Gateway Ink CLI, including setup, usage, and AI model configuration through AWS Bedrock or Anthropic API.

## Table of Contents
- [About the Ink CLI](#about-the-ink-cli)
- [Quick Start](#quick-start)
- [Provider Selection](#provider-selection)
- [AWS Bedrock Setup](#aws-bedrock-setup)
- [Anthropic API Setup](#anthropic-api-setup)
- [Available Models](#available-models)
- [How to Tell Which Provider is Active](#how-to-tell-which-provider-is-active)
- [Switching Between Providers](#switching-between-providers)
- [Troubleshooting](#troubleshooting)

---

## About the Ink CLI

The **MCP Gateway Ink CLI** is an interactive terminal-based interface that lets you chat with AI models and interact with MCP (Model Context Protocol) servers through natural language.

### What It Does

- **💬 Interactive Chat:** Chat with Claude models (via Bedrock or Anthropic API) in your terminal
- **🔧 MCP Tool Access:** AI can automatically discover and use MCP tools through the gateway
- **⚡ Slash Commands:** Quick commands for MCP operations (`/ping`, `/list`, `/call`)
- **🎨 Rich UI:** Beautiful terminal interface with markdown rendering and syntax highlighting
- **📝 Auto-completion:** Command suggestions as you type

### Prerequisites

Before using the Ink CLI, you need to:

1. **Generate OAuth Tokens** (for MCP Gateway authentication)
2. **Build the CLI**
3. **Configure AI Provider** (AWS Bedrock or Anthropic API)

### Step 1: OAuth Tokens (Automatic)

The CLI automatically generates OAuth tokens when you start it for the first time:

```bash
# Just run npm start - tokens are generated automatically if missing
cd cli
npm start
```

**Automatic Token Management:**
- **First Run:** CLI detects missing tokens and automatically runs `generate_creds.sh`
- **Expired Tokens:** CLI automatically refreshes tokens when they expire or have < 5 minutes remaining
- **Manual Refresh:** Use `/refresh` command to manually regenerate tokens without restarting

**Manual Token Generation (Optional):**
```bash
# Only needed if you want to pre-generate tokens before starting CLI
./credentials-provider/generate_creds.sh --ingress-only

# Force regenerate tokens
./credentials-provider/generate_creds.sh --force
```

**Note:** Tokens are saved to `.oauth-tokens/ingress.json` and automatically managed by the CLI.

### Step 2: Build the CLI

```bash
cd cli
npm install
npm run build
```

### Step 3: Configure AI Provider

Choose one:
- **AWS Bedrock** (see [AWS Bedrock Setup](#aws-bedrock-setup) below)
- **Anthropic API** (see [Anthropic API Setup](#anthropic-api-setup) below)

### Running the CLI

```bash
cd cli
npm start
```

### Using the CLI

Once started, you can:

**1. Chat naturally:**
```
You: What MCP tools are available?
Assistant: Let me check the available tools...
[AI automatically calls /list and shows you the tools]
```

**2. Use slash commands:**
```
You: /ping
[Checks connectivity to MCP gateway]

You: /list
[Lists all available MCP tools]

You: /call tool=weather args='{"city": "Seattle"}'
[Calls a specific MCP tool]
```

**3. Ask the AI to use tools:**
```
You: Check the weather in Seattle using the weather tool
[AI automatically finds and calls the weather tool]
```

**4. Exit:**
```
You: /exit
[or press Ctrl+C]
```

### Key Features

- **Smart Tool Discovery:** AI automatically finds the right MCP tools for your request
- **Context Aware:** Maintains conversation context across multiple turns
- **Error Handling:** Clear error messages with suggestions
- **Model Selection:** Configure which AI model to use (see sections below)

---

## Quick Start

> **💡 Tip:** Set `BEDROCK_MODEL_ID` to use a different model. If not set, defaults to Claude Sonnet 4.5.

> **⚠️ Prerequisites:** Build the CLI first (`npm install && npm run build`). OAuth tokens are generated automatically on first run!

### For Amazon Internal Users (Isengard)

```bash
# 1. Build the CLI
cd cli && npm install && npm run build

# 2. Export credentials from Isengard
isengard credentials export --account <account-id> --role <role-name>

# 3. (Optional) Set region
export AWS_REGION=us-west-2

# 4. (Optional) Choose a different model
export BEDROCK_MODEL_ID=us.anthropic.claude-opus-4-1-20250805-v1:0  # Use Opus instead of Sonnet
# OR
export BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0  # Use Haiku (faster/cheaper)

# 5. Run the CLI (tokens generated automatically on first run)
npm start
```

**Note:** OAuth tokens are now generated automatically when you start the CLI - no need to run `generate_creds.sh` manually!

**Available models:**
- `us.anthropic.claude-sonnet-4-5-20250929-v1:0` - Balanced (default)
- `us.anthropic.claude-opus-4-1-20250805-v1:0` - Most powerful
- `us.anthropic.claude-haiku-4-5-20251001-v1:0` - Fastest/cheapest

See [Available Models](#available-models) section for complete list.

### For External AWS Users

```bash
# 1. Build the CLI
cd cli && npm install && npm run build

# 2. Configure AWS credentials
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1

# 3. Run the CLI (tokens generated automatically on first run)
npm start
```

**Note:** OAuth tokens are now generated automatically when you start the CLI - no need to run `generate_creds.sh` manually!

### For Anthropic API Users

```bash
# 1. Build the CLI
cd cli && npm install && npm run build

# 2. Set your API key
export ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# 3. (Optional) Unset AWS credentials
unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY

# 4. Run the CLI (tokens generated automatically on first run)
npm start
```

**Note:** OAuth tokens are now generated automatically when you start the CLI - no need to run `generate_creds.sh` manually!

### Real-World Examples

**Example 1: Use Opus for complex analysis**
```bash
isengard credentials export --account 577638374636 --role nishdeb-role
export AWS_REGION=us-west-2
export BEDROCK_MODEL_ID=us.anthropic.claude-opus-4-1-20250805-v1:0
npm start
```

**Example 2: Use Haiku for quick queries**
```bash
isengard credentials export --account 577638374636 --role nishdeb-role
export BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
npm start
```

**Example 3: Default Sonnet (no model specified)**
```bash
isengard credentials export --account 577638374636 --role nishdeb-role
npm start  # Uses Claude Sonnet 4.5 by default
```

---

## Provider Selection

The CLI automatically selects the AI provider based on available credentials:

1. **AWS Bedrock (Default)** - If AWS credentials are found
   - `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`
   - `AWS_PROFILE`
   - Isengard-exported credentials
   - EC2/ECS instance metadata

2. **Anthropic API** - If only `ANTHROPIC_API_KEY` is set

3. **Priority** - If both are configured, Bedrock takes precedence

### Force a Specific Provider

To use Anthropic API when both credentials exist:
```bash
# Temporarily disable AWS credentials
unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY

# Set Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-your-api-key-here

npm start
```

---

## AWS Bedrock Setup

### Option 1: Isengard (Amazon Internal)

```bash
# Export credentials for your account and role
isengard credentials export --account <account-id> --role <role-name>

# Example:
isengard credentials export --account 577638374636 --role nishdeb-role

# Set region (optional, defaults to us-east-1)
export AWS_REGION=us-west-2

# Verify credentials
aws sts get-caller-identity
```

The CLI automatically uses credentials from `~/.aws/credentials` after Isengard export.

### Option 2: Environment Variables

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_SESSION_TOKEN=your_session_token  # Optional, for temporary credentials
export AWS_REGION=us-east-1
```

### Option 3: AWS Profile

```bash
export AWS_PROFILE=your_profile_name
export AWS_REGION=us-west-2
```

### Option 4: AWS Credentials File

Configure `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY

[bedrock]
aws_access_key_id = ANOTHER_ACCESS_KEY
aws_secret_access_key = ANOTHER_SECRET_KEY
```

Then:
```bash
export AWS_PROFILE=bedrock
```

### Configuring the Bedrock Model

```bash
# Use Claude Opus 4.1 (most powerful)
export BEDROCK_MODEL_ID=us.anthropic.claude-opus-4-1-20250805-v1:0

# Use Claude Haiku 4.5 (fastest)
export BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0

# Use global routing (multi-region)
export BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-5-20250929-v1:0
```

---

## Anthropic API Setup

### Getting an API Key

1. Sign up at https://console.anthropic.com/
2. Navigate to API Keys
3. Create a new API key

### Configuration

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Optional: Specify a model
export ANTHROPIC_MODEL=claude-opus-4-20250514

# Run the CLI
npm start
```

### Ensuring Anthropic API is Used

If you have AWS credentials and want to use Anthropic API instead:

```bash
# Temporarily disable AWS credentials
unset AWS_PROFILE
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY

# Set Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-your-api-key-here

npm start
```

---

## Available Models

### AWS Bedrock Models

**Claude 4+ Models (Require Inference Profile IDs):**

| Inference Profile ID | Model Name | Context | Best For | Cost |
|---------------------|------------|---------|----------|------|
| `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Claude Sonnet 4.5 | 200K | Balanced (default) | $$$ |
| `us.anthropic.claude-opus-4-1-20250805-v1:0` | Claude Opus 4.1 | 200K | Most capable | $$$$ |
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Claude Haiku 4.5 | 200K | Fast, efficient | $$ |
| `us.anthropic.claude-sonnet-4-20250514-v1:0` | Claude Sonnet 4 | 200K | Previous Sonnet | $$$ |
| `us.anthropic.claude-opus-4-20250514-v1:0` | Claude Opus 4 | 200K | Previous Opus | $$$$ |
| `global.anthropic.claude-sonnet-4-5-20250929-v1:0` | Claude Sonnet 4.5 | 200K | Multi-region routing | $$$ |
| `global.anthropic.claude-haiku-4-5-20251001-v1:0` | Claude Haiku 4.5 | 200K | Multi-region routing | $$ |

**Claude 3.x Models (Inference Profiles or Direct IDs):**

| Model ID | Model Name | Context | Best For |
|----------|------------|---------|----------|
| `us.anthropic.claude-3-7-sonnet-20250219-v1:0` | Claude 3.7 Sonnet | 200K | Previous generation |
| `us.anthropic.claude-3-5-sonnet-20241022-v2:0` | Claude 3.5 Sonnet v2 | 200K | Solid performance |
| `us.anthropic.claude-3-5-haiku-20241022-v1:0` | Claude 3.5 Haiku | 200K | Fast and affordable |
| `us.anthropic.claude-3-opus-20240229-v1:0` | Claude 3 Opus | 200K | Previous Opus |

**Important Notes:**
- Claude 4+ models **must** use inference profile IDs (prefix: `us.anthropic.*` or `global.anthropic.*`)
- Claude 3.x models can use direct model IDs or inference profiles
- Check available models: `aws bedrock list-inference-profiles --region <region>`
- Global profiles route across multiple regions for better availability

### Anthropic API Models

| Model ID | Model Name | Context | Best For |
|----------|------------|---------|----------|
| `claude-opus-4-20250514` | Claude Opus 4 | 200K | Most capable |
| `claude-sonnet-4-20250514` | Claude Sonnet 4 | 200K | Balanced performance |
| `claude-haiku-4-5-20251001` | Claude Haiku 4.5 | 200K | Fast, efficient (default) |
| `claude-3-5-sonnet-20241022` | Claude 3.5 Sonnet | 200K | Previous generation |

Check https://docs.anthropic.com/en/docs/about-claude/models for the latest models.

---

## How to Tell Which Provider is Active

When you start the CLI, it displays the AI configuration on a single line:

**Using AWS Bedrock with profile:**
```
AI: AWS Bedrock (bedrock) | Region: us-west-2 | Model: us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

**Using AWS Bedrock with environment variables:**
```
AI: AWS Bedrock (EnvVars) | Region: us-east-1 | Model: us.anthropic.claude-opus-4-1-20250805-v1:0
```

**Using AWS Bedrock with default/Isengard credentials:**
```
AI: AWS Bedrock (Default) | Region: us-west-2 | Model: us.anthropic.claude-haiku-4-5-20251001-v1:0
```

**Using Anthropic API:**
```
AI: Anthropic API | Model: claude-haiku-4-5-20251001
```

The startup message shows:
- Provider (Bedrock or Anthropic API)
- Credential source (for Bedrock: profile name, env vars, or default chain)
- AWS region (for Bedrock)
- Model being used

---

## Switching Between Providers

### Scenario 1: Switch from Bedrock to Anthropic API

```bash
# Currently using Bedrock via Isengard
isengard credentials export --account 123456789012 --role MyRole

# Switch to Anthropic API
unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
export ANTHROPIC_API_KEY=sk-ant-your-api-key-here

npm start  # Now uses Anthropic API
```

### Scenario 2: Switch from Anthropic API to Bedrock

```bash
# Currently using Anthropic API
export ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Switch to Bedrock
unset ANTHROPIC_API_KEY
isengard credentials export --account 123456789012 --role MyRole

npm start  # Now uses Bedrock
```

### Scenario 3: Multiple AWS Accounts

```bash
# Export to specific profiles
isengard credentials export --account 111111111111 --role Role1 --profile account1
isengard credentials export --account 222222222222 --role Role2 --profile account2

# Switch between accounts
export AWS_PROFILE=account1
npm start  # Uses account1

export AWS_PROFILE=account2
npm start  # Uses account2
```

---

## Troubleshooting

### "Missing OAuth Tokens" or "Authentication Failed" Error

**Error:** Cannot connect to MCP Gateway or "Failed to load ingress tokens"

**Cause:** OAuth tokens not generated or expired

**Fix:**
```bash
# Generate new tokens (run from project root)
./credentials-provider/generate_creds.sh --ingress-only

# Verify tokens exist
ls -la .oauth-tokens/ingress.json

# Force regenerate if needed
./credentials-provider/generate_creds.sh --force --ingress-only
```

**Note:** The CLI automatically loads tokens from `.oauth-tokens/ingress.json`. If this file is missing or invalid, you'll see authentication errors.

### CLI Not Built / TypeScript Errors

**Error:** Module not found or TypeScript compilation errors

**Fix:**
```bash
cd cli
npm install
npm run build

# Verify build succeeded
ls -la dist/

# If issues persist, clean and rebuild
rm -rf dist/ node_modules/
npm install
npm run build
```

### "Agent mode is disabled" Error

This means no valid AI model credentials were found.

**Check:**
- AWS credentials: Run `aws sts get-caller-identity` to verify
- Isengard users: Run `isengard credentials export` to refresh credentials
- Anthropic API: Verify `ANTHROPIC_API_KEY` is set
- Environment: Ensure variables are exported in your current shell

**Fix:**
```bash
# For Bedrock
aws sts get-caller-identity  # Verify AWS credentials

# For Anthropic
echo $ANTHROPIC_API_KEY  # Should show your key

# Re-export if needed
isengard credentials export --account <account-id> --role <role>
# OR
export ANTHROPIC_API_KEY=sk-ant-your-key
```

### Bedrock Access Denied

**Error:** AccessDeniedException

**Causes:**
- Missing IAM permission: `bedrock:InvokeModel`
- Model access not enabled in Bedrock console
- Wrong AWS region

**Fix:**
```bash
# Check your identity
aws sts get-caller-identity

# List available models in your region
aws bedrock list-inference-profiles --region us-west-2

# Verify model access
aws bedrock list-foundation-models --region us-west-2 | grep claude
```

**For Isengard users:**
- Ensure your role has Bedrock permissions
- Contact your team admin to grant access
- Check if Bedrock is enabled in your AWS account

### Isengard Credentials Expired

Isengard credentials are temporary and expire.

**Symptoms:**
- "ExpiredToken" errors
- "The security token included in the request is expired"

**Fix:**
```bash
# Check current credentials
aws sts get-caller-identity

# If expired, re-export
isengard credentials export --account <account-id> --role <role-name>

# Verify new credentials
aws sts get-caller-identity
```

### Model Not Found / Invalid Request

**Error:** "Invocation of model ID ... isn't supported" or "Model not found"

**Cause:** Using direct model ID instead of inference profile ID for Claude 4+ models

**Fix:**
```bash
# ❌ Wrong (direct model ID for Claude 4)
export BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0

# ✅ Correct (inference profile ID)
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

List available profiles:
```bash
aws bedrock list-inference-profiles --region us-west-2
```

### Anthropic API Rate Limiting

**Error:** "Rate limit exceeded" (HTTP 429)

**Fix:**
- Wait before retrying
- Consider using Bedrock for higher throughput
- Check your API tier at https://console.anthropic.com/

### Anthropic API Authentication Failed

**Error:** "Authentication failed" (HTTP 401)

**Fix:**
```bash
# Verify your key is set
echo $ANTHROPIC_API_KEY

# Ensure key is valid (starts with sk-ant-)
# Get a new key from https://console.anthropic.com/

# Re-export
export ANTHROPIC_API_KEY=sk-ant-your-correct-key
```

### Wrong Provider Being Used

**Problem:** CLI uses Bedrock but you want Anthropic API (or vice versa)

**Fix:**
```bash
# To force Anthropic API
unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
export ANTHROPIC_API_KEY=sk-ant-your-key

# To force Bedrock
unset ANTHROPIC_API_KEY
export AWS_PROFILE=your-profile

# Verify on startup - check the "AI Provider:" line
npm start
```

### Common Isengard Commands

```bash
# Check current credentials
aws sts get-caller-identity

# Re-export credentials
isengard credentials export --account <account-id> --role <role-name>

# List available profiles
cat ~/.aws/credentials

# Test Bedrock access
aws bedrock list-inference-profiles --region us-west-2

# Test with specific profile
AWS_PROFILE=myprofile aws sts get-caller-identity
```

---

## Benefits Comparison

### AWS Bedrock
✅ Cost efficiency for high-volume usage
✅ Regional deployment options
✅ AWS IAM integration
✅ Compliance (data stays in AWS)
✅ Centralized AWS billing
✅ No separate API key management
✅ Cross-region routing (global profiles)

### Anthropic API
✅ Simple setup (just API key)
✅ Direct access to latest models
✅ No AWS account required
✅ Easier for development/testing
✅ Clearer per-request pricing

---

## Environment Variables Reference

### AWS Bedrock
```bash
# Authentication
AWS_ACCESS_KEY_ID          # AWS access key
AWS_SECRET_ACCESS_KEY      # AWS secret key
AWS_SESSION_TOKEN          # Optional: for temporary credentials
AWS_PROFILE                # AWS profile name from ~/.aws/credentials

# Configuration
AWS_REGION                 # AWS region (default: us-east-1)
AWS_DEFAULT_REGION         # Alternative to AWS_REGION
BEDROCK_MODEL_ID           # Override default model

# Examples
export AWS_PROFILE=bedrock
export AWS_REGION=us-west-2
export BEDROCK_MODEL_ID=us.anthropic.claude-opus-4-1-20250805-v1:0
```

### Anthropic API
```bash
# Authentication
ANTHROPIC_API_KEY          # Anthropic API key (required)

# Configuration
ANTHROPIC_MODEL            # Override default model

# Examples
export ANTHROPIC_API_KEY=sk-ant-api03-xxxx
export ANTHROPIC_MODEL=claude-opus-4-20250514
```

---

## Additional Resources

- **AWS Bedrock Documentation:** https://docs.aws.amazon.com/bedrock/
- **Anthropic API Documentation:** https://docs.anthropic.com/
- **Anthropic Console:** https://console.anthropic.com/
- **Isengard Documentation:** Internal Amazon wiki
- **AWS CLI Reference:** https://docs.aws.amazon.com/cli/

For issues or questions, open a GitHub issue on the project repository.
