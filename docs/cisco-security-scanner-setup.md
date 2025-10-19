# MCP Security Scanner Setup

## Overview

The MCP Security Scanner is integrated into the service management workflow to scan MCP servers for security vulnerabilities before deployment.

## Prerequisites

### Admin password
Make sure the ADMIN_USER, ADMIN_PASSWORD are set in .env file for disabling unhealthy servers

### Install mcp-scanner

```bash
# Install the scanner package
uv pip install cisco-ai-mcp-scanner
```

### Set LLM API Key (Optional - Required for LLM Analyzer)

The default analyzer is **YARA only**, which requires no API key. If you want to use the LLM analyzer, add your API key to the `.env` file:

**Method 1: Add to .env file (Recommended)**

```bash
# Add to your .env file in the project root
echo "MCP_SCANNER_LLM_API_KEY=sk-your-api-key" >> .env
```

Or edit `.env` manually:
```bash
# .env file
MCP_SCANNER_LLM_API_KEY=sk-your-api-key
```

**Method 2: Export as environment variable**

```bash
export MCP_SCANNER_LLM_API_KEY=sk-your-api-key
```

**Method 3: Pass directly via command line**

```bash
./cli/service_mgmt.sh scan https://mcp.example.com/mcp yara,llm sk-your-api-key
```

## Usage

### Scan a Single Server

```bash
# Basic scan with YARA analyzer (default, no API key needed)
./cli/service_mgmt.sh scan https://mcp.deepwki.com/mcp

# Scan with both YARA and LLM analyzers (requires API key in .env file)
./cli/service_mgmt.sh scan https://mcp.deepwki.com/mcp yara,llm

# Scan with LLM only
./cli/service_mgmt.sh scan https://mcp.deepwki.com/mcp llm

# Or pass API key directly as argument
./cli/service_mgmt.sh scan https://mcp.deepwki.com/mcp yara,llm sk-your-key
```

### Direct Python CLI Usage

```bash
# Basic scan with YARA (default, no API key needed)
uv run cli/mcp_security_scanner.py --server-url https://mcp.deepwki.com/mcp

# With both analyzers (requires API key in .env file)
uv run cli/mcp_security_scanner.py --server-url https://mcp.deepwki.com/mcp --analyzers yara,llm

# With LLM only
uv run cli/mcp_security_scanner.py --server-url https://mcp.deepwki.com/mcp --analyzers llm

# Or pass API key directly (overrides .env)
uv run cli/mcp_security_scanner.py --server-url https://mcp.deepwki.com/mcp --analyzers llm --api-key sk-your-key

# With debug logging
uv run cli/mcp_security_scanner.py --server-url https://mcp.deepwki.com/mcp --debug

# Output as JSON
uv run cli/mcp_security_scanner.py --server-url https://mcp.deepwki.com/mcp --json
```

## Output

### Console Output

The scanner provides an executive summary:

```
============================================================
SECURITY SCAN SUMMARY
============================================================
Server URL: https://mcp.deepwki.com/mcp
Scan Time: 2025-10-16T10:30:45Z

EXECUTIVE SUMMARY OF ISSUES:
  Critical Issues: 0
  High Severity: 4
  Medium Severity: 0
  Low Severity: 2

Overall Assessment: UNSAFE ✗

Detailed output saved to: security_scans/scan_mcp.deepwki.com_mcp_20251016_103045.json
============================================================
```

### JSON Output Files

Detailed scan results are saved to the `security_scans/` directory:

```
security_scans/
├── scan_mcp.deepwki.com_mcp_20251016_103045.json
├── scan_example.com_mcp_20251016_104500.json
└── ...
```

Each file contains:
- Full scanner output
- Detailed findings for each analyzer
- Severity levels and descriptions
- Timestamps and metadata

## Security Assessment

### Safety Criteria

- **SAFE**: No critical or high severity issues found
- **UNSAFE**: One or more critical or high severity issues detected

### Exit Codes

- `0`: Scan completed successfully, server is SAFE
- `1`: Scan completed successfully, server is UNSAFE
- `2`: Scan failed with error

## Automatic Security Scanning

**NEW**: Security scanning is now **automatically integrated** into the service registration workflow!

### Basic Usage (YARA Only - No API Key Required)

```bash
# Default: YARA analyzer only (fast, no API key needed)
./cli/service_mgmt.sh add cli/examples/server-config.json
```

### Advanced Usage (Multiple Analyzers)

```bash
# With both YARA and LLM analyzers (API key from .env file)
./cli/service_mgmt.sh add cli/examples/server-config.json yara,llm

# With LLM analyzer only (API key from .env file)
./cli/service_mgmt.sh add cli/examples/server-config.json llm
```

### How It Works

When you add a service, the system will:
1. Validate the configuration
2. **Pre-flight check**: Verify API key if LLM analyzer is requested
3. **Automatically scan the server for security vulnerabilities** (default: YARA only)
4. Display security scan results (Critical, High, Medium, Low severity issues)
5. Register the server regardless of scan results
6. If `is_safe: false` (critical or high severity issues found):
   - Add `security-pending` tag to the server configuration
   - Server is registered but automatically disabled
   - Warning message displayed
   - Detailed security report saved to `security_scans/` directory
7. Complete normal registration verification and health checks

### Example Output - Safe Server

```
=== Security Scan ===
ℹ Scanning server for security vulnerabilities...
✓ Security scan passed - Server is SAFE

=== Adding Service: example-server ===
...
✓ Service example-server successfully added, verified, and passed security scan!
```

### Example Output - Unsafe Server

```
=== Security Scan ===
ℹ Scanning server for security vulnerabilities...
✗ Security scan failed - Server has critical or high severity issues
ℹ Server will be registered but marked as UNHEALTHY with security-pending status

Security Issues Found:
  Critical: 2
  High: 3
  Medium: 1
  Low: 0

Detailed report: security_scans/scan_example.com_mcp_20251016_103045.json

=== Security Status Update ===
ℹ Marking server as UNHEALTHY due to failed security scan...
ℹ Server registered but flagged as security-pending
ℹ Review the security scan report before enabling this server

✓ Service example-server successfully added and verified
✗ ⚠️  WARNING: Server failed security scan - Review required before use
```

## Importing from Anthropic Registry

The import script also supports configurable analyzers:

```bash
# Import with default YARA analyzer (no API key needed)
./cli/import_from_anthropic_registry.sh

# Import with both YARA and LLM analyzers (API key from .env file)
./cli/import_from_anthropic_registry.sh --analyzers yara,llm

# Import with LLM only (API key from .env file)
./cli/import_from_anthropic_registry.sh --analyzers llm

# Dry run to test without registration
./cli/import_from_anthropic_registry.sh --analyzers yara,llm --dry-run
```

## Manual Security Scanning

You can also manually scan servers without registering them:

```bash
# Scan a specific server URL (default: YARA only)
./cli/service_mgmt.sh scan https://mcp.deepwki.com/mcp

# Scan with both analyzers (API key from .env file)
./cli/service_mgmt.sh scan https://mcp.deepwki.com/mcp yara,llm

# Or pass API key directly (overrides .env)
./cli/service_mgmt.sh scan https://mcp.deepwki.com/mcp yara,llm sk-your-key
```

## Disabling Automatic Scans

Currently, automatic security scanning is always enabled during `add` operations. If you need to skip scanning (not recommended), you can:

1. Manually register using the MCP client directly
2. Or modify the `add_service()` function in `cli/service_mgmt.sh` to comment out the security scan section

## Future Enhancements

Potential future improvements:

1. **Configurable Scan Policies**: Add flag to skip scans or use different analyzer configurations
2. **Batch Scanning**: Scan multiple servers from a list file
3. **Report Generation**: Aggregate security reports across all registered servers
4. **Automated Remediation**: Suggest fixes for common security issues

## Analyzer Comparison

| Analyzer | Speed | API Key Required | Use Case |
|----------|-------|------------------|----------|
| **YARA** | Fast | No | Pattern-based detection, SQL injection, XSS, command injection |
| **LLM** | Slower | Yes | Context-aware analysis, complex logic vulnerabilities |
| **Both** | Slower | Yes (for LLM) | Comprehensive coverage, cross-validation |

**Recommendation**: Use YARA for fast, automated scanning. Add LLM for critical services or when you need deeper analysis.

## Troubleshooting

### Scanner Not Found

```bash
# Install the scanner package
uv pip install cisco-ai-mcp-scanner
```

### API Key Issues

#### Pre-flight Check Failure

If you see:
```
✗ LLM analyzer requested but MCP_SCANNER_LLM_API_KEY environment variable is not set
```

**Solution**:
```bash
# Add to .env file (recommended)
echo "MCP_SCANNER_LLM_API_KEY=sk-your-key" >> .env

# Or set as environment variable (temporary)
export MCP_SCANNER_LLM_API_KEY=sk-your-key

# Verify it's set
echo $MCP_SCANNER_LLM_API_KEY

# Or pass it explicitly as an argument
./cli/service_mgmt.sh scan https://example.com/mcp yara,llm sk-your-key
```

#### Wrong Environment Variable Name

⚠️ **Important**: The scanner uses `MCP_SCANNER_LLM_API_KEY`, not `OPENAI_API_KEY`.

```bash
# Correct - Add to .env file
MCP_SCANNER_LLM_API_KEY=sk-your-key

# Incorrect (old variable name)
OPENAI_API_KEY=sk-your-key  # This will NOT work
```

### Permission Issues

Ensure the `security_scans/` directory is writable:

```bash
mkdir -p security_scans
chmod 755 security_scans
```

### JSON Parsing Issues

If you see errors like:
```
JSONDecodeError: Expecting ',' delimiter
```

This was fixed in the latest version. The scanner now:
- Removes ANSI color codes from output
- Uses robust JSON detection patterns
- Handles mixed log/JSON output

**Solution**: Ensure you're using the latest version of `mcp_security_scanner.py`.

### Internal Docker Services

If scanning internal Docker services (like `http://fininfo-server:8001/sse`), the scan may fail with:
```
Error connecting to MCP server: nodename nor servname provided, or not known
```

**Reason**: Internal Docker hostnames aren't resolvable from the host machine.

**Solutions**:
1. Use the gateway URL instead: `http://localhost/fininfo/mcp`
2. Use localhost with mapped port: `http://localhost:8001/sse`
3. Accept the scan failure (server will still be registered but marked unsafe)

## Recent Improvements (October 2025)

### Version 2.0 - Configurable Analyzers

- ✅ **Default changed to YARA only** (no API key required)
- ✅ **LLM analyzer is opt-in** via `--analyzers` flag
- ✅ **Single environment variable**: `MCP_SCANNER_LLM_API_KEY` (simplified from multiple variables)
- ✅ **Pre-flight API key validation**: Clear error messages before scan starts
- ✅ **Fixed JSON parsing**: Handles ANSI colors and mixed output
- ✅ **Import script support**: `import_from_anthropic_registry.sh` now supports `--analyzers`
- ✅ **Better error messages**: Helpful guidance when configuration is missing

### Migration Guide

If you were using the old version:

**Old way** (required API key even for YARA):
```bash
export OPENAI_API_KEY=sk-...
./cli/service_mgmt.sh add config.json
```

**New way** (YARA by default, LLM opt-in):
```bash
# YARA only (no API key needed)
./cli/service_mgmt.sh add config.json

# Both analyzers (add API key to .env file first)
echo "MCP_SCANNER_LLM_API_KEY=sk-..." >> .env
./cli/service_mgmt.sh add config.json yara,llm
```

**Environment variable changes**:
- Old: `OPENAI_API_KEY` (export command)
- New: `MCP_SCANNER_LLM_API_KEY` (add to `.env` file)

**Update your .env file**:
```bash
# Remove old variable (if present)
sed -i '' '/OPENAI_API_KEY/d' .env

# Add new variable
echo "MCP_SCANNER_LLM_API_KEY=sk-your-key" >> .env
```

## Additional Resources

- MCP Scanner Documentation: https://github.com/cisco-ai/mcp-scanner
- Service Management Script: `cli/service_mgmt.sh`
- Security Scanner CLI: `cli/mcp_security_scanner.py`
- Import Script: `cli/import_from_anthropic_registry.sh`
