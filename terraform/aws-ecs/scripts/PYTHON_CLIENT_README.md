# MCP Gateway Registry Python Client

Type-safe Python client for the MCP Gateway Registry API with automatic JWT token management via AWS SSM.

## Components

### registry_client.py
Standalone Pydantic-based client library providing:
- Full type safety with Pydantic models
- Automatic JWT token retrieval from AWS SSM via get-m2m-token.sh
- Methods for all Registry API endpoints
- Comprehensive error handling

### registry_management.py
High-level CLI wrapper providing:
- Command-line interface for all registry operations
- Environment variable configuration support
- User-friendly output formatting
- Interactive confirmations for destructive operations

## Prerequisites

Install Python dependencies:
```bash
uv pip install -r requirements.txt
```

## Configuration

Both scripts support configuration via environment variables:

```bash
# Registry URL (default: https://registry.mycorp.click)
export REGISTRY_URL="https://registry.mycorp.click"

# Keycloak client name (default: registry-admin-bot)
export CLIENT_NAME="registry-admin-bot"

# Path to get-m2m-token.sh script (default: auto-detected)
export GET_TOKEN_SCRIPT="/path/to/get-m2m-token.sh"
```

## Usage Examples

### Using registry_management.py CLI

#### Register a Server
```bash
# Register from JSON config
uv run python registry_management.py register --config /path/to/server-config.json

# Overwrite if exists
uv run python registry_management.py register --config server-config.json --overwrite
```

Example config file:
```json
{
  "service_path": "/cloudflare-docs",
  "name": "Cloudflare Documentation Server",
  "description": "Search Cloudflare developer documentation",
  "proxy_pass_url": "https://cloudflare-docs.example.com/mcp",
  "supported_transports": ["streamable-http"],
  "auth_provider": "keycloak",
  "auth_type": "bearer"
}
```

#### List All Servers
```bash
uv run python registry_management.py list
```

Output:
```
✓ 🟢 /cloudflare-docs
   Name: Cloudflare Documentation Server
   Description: Search Cloudflare developer documentation
   Enabled: True
   Health: healthy

✗ 🔴 /example-server
   Name: Example Server
   Description: Example MCP server
   Enabled: False
   Health: unhealthy
```

#### Toggle Server Status
```bash
# Enable or disable a server
uv run python registry_management.py toggle --path /cloudflare-docs
```

#### Remove a Server
```bash
# With confirmation prompt
uv run python registry_management.py remove --path /cloudflare-docs

# Skip confirmation
uv run python registry_management.py remove --path /cloudflare-docs --force
```

#### Health Check
```bash
uv run python registry_management.py healthcheck
```

#### Group Management
```bash
# Add server to groups
uv run python registry_management.py add-to-groups --server cloudflare-docs --groups finance,analytics

# Remove server from groups
uv run python registry_management.py remove-from-groups --server cloudflare-docs --groups finance

# Create a new group
uv run python registry_management.py create-group --name engineering --description "Engineering team"

# Create group in both registry and Keycloak
uv run python registry_management.py create-group --name finance --keycloak

# List all groups
uv run python registry_management.py list-groups

# Delete a group
uv run python registry_management.py delete-group --name old-group

# Force delete system group
uv run python registry_management.py delete-group --name system-group --force
```

### Using registry_client.py as a Library

```python
import subprocess
from registry_client import RegistryClient, InternalServiceRegistration

# Retrieve JWT token using get-m2m-token.sh
def get_token(client_name: str = "registry-admin-bot") -> str:
    result = subprocess.run(
        ["/path/to/get-m2m-token.sh", client_name],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()

# Create client with token
token = get_token()
client = RegistryClient(
    registry_url="https://registry.mycorp.click",
    token=token
)

# Register a server
registration = InternalServiceRegistration(
    service_path="/my-server",
    name="My MCP Server",
    description="Custom MCP server",
    proxy_pass_url="https://my-server.example.com/mcp",
    supported_transports=["streamable-http"],
    overwrite=True
)

response = client.register_service(registration)
print(f"Registered: {response.path}")

# List all servers
servers = client.list_services()
for server in servers.servers:
    print(f"{server.path}: {server.health_status.value}")

# Toggle server
toggle_response = client.toggle_service("/my-server")
print(f"Enabled: {toggle_response.is_enabled}")

# Health check
health = client.healthcheck()
print(f"Status: {health['status']}")

# Group operations
client.add_server_to_groups("my-server", ["finance", "analytics"])
groups = client.list_groups()
print(f"Total groups: {len(groups.groups)}")
```

## Authentication Flow

The authentication flow separates token retrieval from API client usage:

### Token Retrieval (registry_management.py)
1. **Script Execution**: Calls `get-m2m-token.sh` subprocess to get JWT token
2. **SSM Cache Check**: Script checks AWS SSM Parameter Store for cached token
3. **Expiration Validation**: Validates token expiration (60 second buffer)
4. **Keycloak Fetch**: If expired/missing, fetches new token from Keycloak
5. **SSM Storage**: Stores new token in SSM for future use
6. **Token Redaction**: Logs show only first 8 characters (e.g., "eyJhbGci...")

### API Client (registry_client.py)
1. **Token Acceptance**: Receives pre-fetched token as constructor argument
2. **Request Authentication**: Adds token to Authorization header for each request
3. **Security Logging**: Redacts tokens in all log messages

This design ensures:
- **Separation of Concerns**: Token management separate from API operations
- **No Local Storage**: Tokens stored only in AWS SSM
- **Smart Caching**: Minimizes Keycloak API calls
- **Security**: Tokens redacted in logs to prevent exposure
- **Reusability**: Same token can be reused across multiple API calls

## API Endpoints

The client supports all Registry API endpoints:

### Server Management
- `register_service()` - Register new server
- `remove_service()` - Remove server
- `toggle_service()` - Enable/disable server
- `list_services()` - List all servers
- `healthcheck()` - Health check all servers

### Group Management
- `add_server_to_groups()` - Add server to groups
- `remove_server_from_groups()` - Remove server from groups
- `create_group()` - Create new group
- `delete_group()` - Delete group
- `list_groups()` - List all groups

## Pydantic Models

All API requests and responses use type-safe Pydantic models:

- `InternalServiceRegistration` - Server registration data
- `Server` - Basic server information
- `ServerDetail` - Detailed server information
- `ServerListResponse` - List of servers
- `ServiceResponse` - Service operation response
- `ToggleResponse` - Toggle operation response
- `GroupListResponse` - List of groups
- `ErrorResponse` - Error details

## Error Handling

Both scripts provide comprehensive error handling:

```python
import requests

try:
    response = client.register_service(registration)
except requests.HTTPError as e:
    print(f"HTTP error: {e}")
    print(f"Status code: {e.response.status_code}")
    print(f"Response: {e.response.text}")
except RuntimeError as e:
    print(f"Token retrieval failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Debug Mode

Enable debug logging for troubleshooting:

```bash
# CLI
uv run python registry_management.py --debug list

# Or via environment
export PYTHONLOGLEVEL=DEBUG
uv run python registry_management.py list
```

```python
# Library
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration with Existing Scripts

The Python client integrates seamlessly with existing bash scripts:

```bash
# service_mgmt.sh can call Python client
export REGISTRY_URL="https://registry.mycorp.click"
export CLIENT_NAME="registry-admin-bot"

uv run python registry_management.py register --config server-config.json
```

## Development

### Running Tests
```bash
# Validate syntax
uv run python -m py_compile registry_client.py registry_management.py

# Run with test configuration
export REGISTRY_URL="http://localhost:7860"
uv run python registry_management.py list
```

### Adding New Features

To add a new API endpoint:

1. **Update registry_client.py**:
   - Add Pydantic model if needed
   - Add method to RegistryClient class
   - Document parameters and return type

2. **Update registry_management.py**:
   - Add command parser
   - Add command handler function
   - Add to command_handlers dict

3. **Update documentation**:
   - Add usage example
   - Update README

## Troubleshooting

### Token Retrieval Fails
```bash
# Test token script directly
/home/ubuntu/repos/mcp-gateway-registry/terraform/aws-ecs/scripts/get-m2m-token.sh registry-admin-bot

# Check AWS credentials
aws sts get-caller-identity

# Check SSM parameter
aws ssm get-parameter --name /keycloak/clients/registry-admin-bot/jwt_token --region us-west-2
```

### Connection Timeout
```bash
# Verify registry URL
curl -v https://registry.mycorp.click/api/internal/list

# Check network connectivity
nslookup registry.mycorp.click
```

### Import Errors
```bash
# Install dependencies
uv pip install -r requirements.txt

# Verify installation
uv run python -c "import pydantic, requests; print('OK')"
```

## See Also

- [Server Management API Specification](../../../docs/api-specs/server-management.yaml)
- [get-m2m-token.sh](./get-m2m-token.sh) - JWT token management script
- [service_mgmt.sh](./service_mgmt.sh) - Bash wrapper for server management
- [Post-Deployment Setup Guide](../README.md#post-deployment-setup)
