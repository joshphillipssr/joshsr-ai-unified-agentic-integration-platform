#!/usr/bin/env python3
import json

def transform_anthropic_to_gateway(anthropic_response, base_port=8100):
    """Transform Anthropic ServerResponse to Gateway Registry Config format."""
    
    server = anthropic_response.get("server", anthropic_response)
    name = server["name"]
    
    # Generate tags from name parts + anthropic-registry
    name_parts = name.replace("/", "-").split("-")
    tags = name_parts + ["anthropic-registry"]
    
    # Handle packages (can be array or object)
    packages = server.get("packages", {})
    is_python = False
    npm_pkg = None
    
    if isinstance(packages, dict):
        npm_pkg = packages.get("npm")
        is_python = "pypi" in packages or "python" in packages
    elif isinstance(packages, list):
        is_python = any(pkg.get("registryType") == "pypi" for pkg in packages)
        npm_pkg = next((pkg["identifier"] for pkg in packages 
                       if pkg.get("registryType") == "npm"), None)
    
    # Handle remotes for streamable-http/SSE servers
    remotes = server.get("remotes", [])
    remote_url = None
    transport_type = "stdio"  # default
    
    if remotes:
        # Use first remote URL
        remote = remotes[0]
        remote_url = remote.get("url")
        transport_type = remote.get("type", "streamable-http")
    
    # Generate safe path
    safe_path = name.replace("/", "-")
    
    # Use remote URL if available, otherwise localhost
    proxy_url = remote_url if remote_url else f"http://localhost:{base_port}/"
    
    # Build headers list for remote URL and query params
    headers = []
    if remote_url:
        headers.append({"X-Health-Check-URL": remote_url})
    return {
        "server_name": name,
        "description": server.get("description", "MCP server imported from Anthropic Registry"),
        "path": f"/{safe_path}",
        "proxy_pass_url": proxy_url,
        "auth_provider": "keycloak",
        "auth_type": "oauth", 
        "supported_transports": [transport_type],
        "tags": tags,
        "headers": headers,
        "num_tools": 0,
        "num_stars": 0,
        "is_python": is_python,
        "license": "MIT",
        "remote_url": remote_url,  # Store original remote URL for health checks
        "tool_list": []
    }

if __name__ == "__main__":
    import json
    import sys
    
    # Example usage
    example_input = {
        "name": "brave-search",
        "description": "MCP server for Brave Search API", 
        "version": "0.1.0",
        "repository": {
            "type": "github",
            "url": "https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search"
        },
        "websiteUrl": "https://brave.com/search/api/",
        "packages": {
            "npm": "@modelcontextprotocol/server-brave-search"
        }
    }
    
    # Transform and output
    result = transform_anthropic_to_gateway(example_input)
    print(json.dumps(result, indent=2))
