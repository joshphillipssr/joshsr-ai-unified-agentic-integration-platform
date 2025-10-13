#!/bin/bash

set -e

# Configuration
ANTHROPIC_API_BASE="https://registry.modelcontextprotocol.io"
TEMP_DIR=".tmp/anthropic-import"
BASE_PORT=8100

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }

# Generate deployment instructions for a server
detect_transport() {
    local anthropic_json="$1"
    # Most MCP servers from Anthropic registry use stdio transport
    # Only a few support HTTP/SSE
    echo "stdio"
}

validate_package() {
    local package_type="$1"
    local package_name="$2"
    
    if [ -z "$package_name" ] || [ "$package_name" = "null" ]; then
        return 1
    fi
    
    case "$package_type" in
        "npm")
            # Check if NPM package exists (simplified check)
            return 0
            ;;
        "pypi")
            # Check if PyPI package exists (simplified check)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

generate_deployment_instructions() {
    local server_name="$1"
    local config_file="$2"
    local assigned_port="$3"

    local anthropic_json=$(cat "${TEMP_DIR}/${server_name}-anthropic.json")
    local npm_package=$(echo "$anthropic_json" | jq -r '.server.packages[]? | select(.registryType == "npm") | .identifier' | head -1)
    local pypi_package=$(echo "$anthropic_json" | jq -r '.server.packages[]? | select(.registryType == "pypi") | .identifier' | head -1)
    local repo_url=$(echo "$anthropic_json" | jq -r '.server.repository.url // ""')

    cat >> "${TEMP_DIR}/DEPLOYMENT_INSTRUCTIONS.md" <<EOF

## $server_name

**Assigned Port:** $assigned_port
**Path:** /$server_name
**Config File:** $config_file

### Installation

EOF

    if [ -n "$npm_package" ] && [ "$npm_package" != "null" ]; then
        cat >> "${TEMP_DIR}/DEPLOYMENT_INSTRUCTIONS.md" <<EOF
**NPM Package:**
\`\`\`bash
npx $npm_package
\`\`\`

EOF
    fi

    if [ -n "$pypi_package" ] && [ "$pypi_package" != "null" ]; then
        cat >> "${TEMP_DIR}/DEPLOYMENT_INSTRUCTIONS.md" <<EOF
**Python Package:**
\`\`\`bash
pip install $pypi_package
# Or with uvx:
uvx $pypi_package
\`\`\`

EOF
    fi

    if [ -n "$repo_url" ] && [ "$repo_url" != "null" ]; then
        cat >> "${TEMP_DIR}/DEPLOYMENT_INSTRUCTIONS.md" <<EOF
**Repository:** $repo_url

EOF
    fi

    cat >> "${TEMP_DIR}/DEPLOYMENT_INSTRUCTIONS.md" <<EOF
### Configuration

The server has been registered but needs to be deployed. Update the \`proxy_pass_url\` in the configuration if needed:

\`\`\`bash
# Edit config
vim $config_file

# Update the service
./cli/service_mgmt.sh update $server_name
\`\`\`

---

EOF
}

# Generate final deployment instructions
generate_final_instructions() {
    cat > "${TEMP_DIR}/DEPLOYMENT_INSTRUCTIONS.md" <<EOF
# MCP Server Deployment Instructions

Generated: $(date)

This file contains deployment instructions for servers imported from the Anthropic MCP Registry.

**Important:** The servers have been registered in the gateway but need to be deployed before they can be used.

## Quick Start

1. Choose a deployment option for each server below
2. Deploy the server on the assigned port
3. Verify the server is accessible
4. The server will automatically appear as "healthy" in the registry UI

## Servers

EOF

    # Re-process each server to add to the instructions
    for server_name in "${servers[@]}"; do
        local safe_name=$(echo "$server_name" | sed 's|/|-|g')
        local anthropic_file="${TEMP_DIR}/${safe_name}-anthropic.json"
        if [ -f "$anthropic_file" ]; then
            local anthropic_json=$(cat "$anthropic_file")
            local port=$((BASE_PORT + $(printf '%s\n' "${servers[@]}" | grep -n "^$server_name$" | cut -d: -f1) - 1))
            generate_deployment_instructions "$server_name" "${TEMP_DIR}/${safe_name}-config.json" "$port"
        fi
    done

    cat >> "${TEMP_DIR}/DEPLOYMENT_INSTRUCTIONS.md" <<EOF

## Next Steps

1. **Deploy servers** using the options above
2. **Verify connectivity** by checking the registry UI for "healthy" status
3. **Test tools** using the MCP client or AI coding assistants
4. **Update configurations** if needed for your environment

## Troubleshooting

- **Server shows as unhealthy:** Check if the service is running on the assigned port
- **Port conflicts:** Update the proxy_pass_url in the server config to use a different port
- **Missing dependencies:** Install required packages or API keys as mentioned in the repository

EOF
}

# Parse arguments
DRY_RUN=false
IMPORT_LIST="import_server_list.txt"

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --import-list) IMPORT_LIST="$2"; shift 2 ;;
        --help)
            echo "Usage: $0 [--dry-run] [--import-list <file>]"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Check prerequisites
command -v jq >/dev/null || { print_error "jq required"; exit 1; }
command -v curl >/dev/null || { print_error "curl required"; exit 1; }
[ -f "$IMPORT_LIST" ] || { print_error "Import list not found: $IMPORT_LIST"; exit 1; }

mkdir -p "$TEMP_DIR"

# Read server list
servers=()
while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// }" ]] && continue
    servers+=("$(echo "$line" | xargs)")
done < "$IMPORT_LIST"

print_info "Found ${#servers[@]} servers to import"

# Process each server
success_count=0
current_port=$BASE_PORT

for server_name in "${servers[@]}"; do
    print_info "Processing: $server_name"
    
    # Fetch from Anthropic API (URL encode server name)
    encoded_name=$(echo "$server_name" | sed 's|/|%2F|g')
    api_url="${ANTHROPIC_API_BASE}/v0/servers/${encoded_name}"
    safe_name=$(echo "$server_name" | sed 's|/|-|g')
    anthropic_file="${TEMP_DIR}/${safe_name}-anthropic.json"
    
    if ! curl -s -f "$api_url" > "$anthropic_file"; then
        print_error "Failed to fetch $server_name"
        continue
    fi
    
    # Transform to registry format
    config_file="${TEMP_DIR}/${safe_name}-config.json"
    anthropic_json=$(cat "$anthropic_file")
    
    # Extract from nested server object
    description=$(echo "$anthropic_json" | jq -r '.server.description // "Imported from Anthropic MCP Registry"')
    version=$(echo "$anthropic_json" | jq -r '.server.version // "latest"')
    repo_url=$(echo "$anthropic_json" | jq -r '.server.repository.url // ""')
    
    # Detect transport type from packages or remotes
    transport_type="stdio"
    if echo "$anthropic_json" | jq -e '.server.packages[]? | .transport.type' > /dev/null 2>&1; then
        transport_type=$(echo "$anthropic_json" | jq -r '.server.packages[]? | .transport.type' | head -1)
    elif echo "$anthropic_json" | jq -e '.server.remotes[]? | .type' > /dev/null 2>&1; then
        transport_type=$(echo "$anthropic_json" | jq -r '.server.remotes[]? | .type' | head -1)
    fi
    
    # Detect if Python
    is_python="false"
    if echo "$anthropic_json" | jq -e '.server.packages[]? | select(.registryType == "pypi")' > /dev/null 2>&1; then
        is_python="true"
    fi
    
    # Generate tags from server name
    IFS='/' read -ra name_parts <<< "$server_name"
    server_basename="${name_parts[${#name_parts[@]}-1]}"
    IFS='-' read -ra tag_parts <<< "$server_basename"
    tags_json=$(printf '%s\n' "${tag_parts[@]}" "anthropic-registry" | jq -R . | jq -s .)
    
    # Generate safe path and proxy URL
    safe_path=$(echo "$server_name" | sed 's|/|-|g')
    
    # For imported servers, use a placeholder URL since they're not deployed yet
        proxy_url="http://localhost:${current_port}/"
    
    # Use Python transformer for complete transformation
    python3 -c "
import json, sys
sys.path.append('cli')
from anthropic_transformer import transform_anthropic_to_gateway

with open('$anthropic_file') as f:
    data = json.load(f)
    
result = transform_anthropic_to_gateway(data, $current_port)
result['path'] = '/$safe_path'

# Store remote URL in headers for health check use
remote_url = result.get('remote_url')
if remote_url and result.get('supported_transports', [''])[0] in ['streamable-http', 'sse']:
    # Add remote URL as a special header for health checks
    result['headers'] = [{'X-Health-Check-URL': remote_url}]

# Remove unsupported fields for register_service tool
unsupported_fields = ['repository_url', 'website_url', 'package_npm', 'remote_url']
for field in unsupported_fields:
    result.pop(field, None)

with open('$config_file', 'w') as f:
    json.dump(result, f, indent=2)
"
    
    print_success "Created config for $server_name (transport: $transport_type)"
    
    # Register with service_mgmt.sh (if not dry run)
    if [ "$DRY_RUN" = false ]; then
        if ./cli/service_mgmt.sh add "$config_file"; then
            print_success "Registered $server_name"
            success_count=$((success_count + 1))
        else
            print_error "Failed to register $server_name"
        fi
    else
        print_info "[DRY RUN] Would register $server_name"
        success_count=$((success_count + 1))
    fi
    
    # Generate deployment instructions
    generate_deployment_instructions "$server_name" "$config_file" "$current_port"
    
    current_port=$((current_port + 1))
done

# Generate final deployment instructions file
generate_final_instructions

print_info "Import completed: $success_count/${#servers[@]} successful"
print_info "Configuration files saved to: $TEMP_DIR"
print_info "Deployment instructions: ${TEMP_DIR}/DEPLOYMENT_INSTRUCTIONS.md"
