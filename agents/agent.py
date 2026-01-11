#!/usr/bin/env python3
"""
Interactive LangGraph Agent with Registry Tool Discovery

This agent discovers and invokes MCP tools using semantic search on the registry.
It supports multi-turn conversation and maintains conversation history.

Authentication:
    The agent requires a JWT token for authenticating with the MCP Registry.
    The token can be obtained from different sources depending on your setup.

Usage Examples:
    # Using token from api/.token file (simple cat):
    python agents/agent.py \
        --mcp-registry-url https://mcpgateway.ddns.net/mcpgw/mcp \
        --jwt-token "$(cat api/.token)" \
        --provider bedrock \
        --prompt "What time is it in New York?"

    # Using token from .oauth-tokens/ingress.json (requires jq):
    python agents/agent.py \
        --mcp-registry-url https://mcpgateway.ddns.net/mcpgw/mcp \
        --jwt-token "$(jq -r '.access_token' .oauth-tokens/ingress.json)" \
        --provider bedrock \
        --prompt "What time is it in New York?"

    # Interactive mode for multi-turn conversations:
    python agents/agent.py \
        --mcp-registry-url https://mcpgateway.ddns.net/mcpgw/mcp \
        --jwt-token "$(cat api/.token)" \
        --provider bedrock \
        --interactive

    # With verbose logging for debugging:
    python agents/agent.py \
        --mcp-registry-url https://mcpgateway.ddns.net/mcpgw/mcp \
        --jwt-token "$(cat api/.token)" \
        --provider bedrock \
        --prompt "What time is it in New York?" \
        --verbose

Available Tools:
    - calculator: For mathematical calculations
    - search_registry_tools: Discover MCP tools via semantic search
    - invoke_mcp_tool: Invoke discovered tools on MCP servers

Environment Variables:
    - ANTHROPIC_API_KEY: Required when using --provider anthropic
"""

import asyncio
import argparse
import json
import logging
import os
import re
import yaml
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from urllib.parse import (
    urlparse,
    urljoin,
)

import mcp
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrock
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from registry_client import (
    RegistryClient,
    _format_tool_result,
)

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

# Get logger
logger = logging.getLogger(__name__)

# Global registry client instance (initialized in main)
registry_client: Optional[RegistryClient] = None


def load_server_config(config_file: str = "server_config.yml") -> Dict[str, Any]:
    """
    Load server configuration from YAML file.
    
    Args:
        config_file: Path to the configuration file
        
    Returns:
        Dict containing server configurations
    """
    try:
        # Try to find config file in the same directory as this script
        config_path = os.path.join(os.path.dirname(__file__), config_file)
        if not os.path.exists(config_path):
            # Try current working directory
            config_path = config_file
            if not os.path.exists(config_path):
                logger.warning(f"Server config file not found: {config_file}. Using default configuration.")
                return {"servers": {}}
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Loaded server config from: {config_path}")
            return config or {"servers": {}}
    except Exception as e:
        logger.warning(f"Failed to load server config: {e}. Using default configuration.")
        return {"servers": {}}


def resolve_env_vars(value: str, server_name: str = None) -> str:
    """
    Resolve environment variable references in a string.
    Supports ${VAR_NAME} syntax.
    
    Args:
        value: String that may contain environment variable references
        server_name: Name of the server (for error context)
        
    Returns:
        String with environment variables resolved
        
    Raises:
        ValueError: If a required environment variable is not found
    """
    import re
    
    missing_vars = []
    
    def replace_env_var(match):
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            missing_vars.append(var_name)
            return match.group(0)  # Return original if not found
        return env_value
    
    # Find all ${VAR_NAME} patterns and replace them
    pattern = r'\$\{([^}]+)\}'
    resolved_value = re.sub(pattern, replace_env_var, value)
    
    # If any environment variables were missing, raise an error
    if missing_vars:
        server_context = f" for server '{server_name}'" if server_name else ""
        missing_list = "', '".join(missing_vars)
        raise ValueError(
            f"Missing required environment variable(s): '{missing_list}'{server_context}. "
            f"Please set these environment variables and try again."
        )
    
    return resolved_value


def get_server_headers(server_name: str, config: Dict[str, Any]) -> Dict[str, str]:
    """
    Get server-specific headers from configuration with environment variable resolution.
    
    Args:
        server_name: Name of the server (e.g., 'sre-gateway', 'atlassian')
        config: Loaded server configuration
        
    Returns:
        Dictionary of headers for the server
        
    Raises:
        ValueError: If required environment variables for the server are missing
    """
    servers = config.get("servers", {})
    server_config = servers.get(server_name, {})
    raw_headers = server_config.get("headers", {})
    
    if not raw_headers:
        logger.debug(f"No custom headers configured for server '{server_name}'")
        return {}
    
    # Resolve environment variables in header values
    resolved_headers = {}
    try:
        for header_name, header_value in raw_headers.items():
            resolved_value = resolve_env_vars(header_value, server_name)
            if resolved_value != header_value:
                logger.debug(f"Resolved header {header_name} for server {server_name}")
            resolved_headers[header_name] = resolved_value
        
        logger.info(f"Applied {len(resolved_headers)} custom headers for server '{server_name}'")
        return resolved_headers
        
    except ValueError as e:
        # Re-raise with additional context about which server failed
        logger.error(f"Failed to configure headers for server '{server_name}': {e}")
        raise


def enable_verbose_logging():
    """Enable verbose debug logging for HTTP libraries and main logger."""
    # Set main logger to DEBUG level
    logger.setLevel(logging.DEBUG)
    
    # Enable debug logging for httpx to see request/response details
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.DEBUG)
    httpx_logger.propagate = True

    # Enable debug logging for httpcore (underlying HTTP library)
    httpcore_logger = logging.getLogger("httpcore")
    httpcore_logger.setLevel(logging.DEBUG)
    httpcore_logger.propagate = True

    # Enable debug logging for mcp client libraries
    mcp_logger = logging.getLogger("mcp")
    mcp_logger.setLevel(logging.DEBUG)
    mcp_logger.propagate = True
    
    logger.info("Verbose logging enabled for httpx, httpcore, mcp libraries, and main logger")

def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments for the Interactive LangGraph Agent.

    Returns:
        argparse.Namespace: The parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description='Interactive LangGraph Agent with Registry Tool Discovery',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Using token from api/.token file:
    python agents/agent.py --jwt-token "$(cat api/.token)" --prompt "What time is it?"

    # Using token from .oauth-tokens/ingress.json:
    python agents/agent.py --jwt-token "$(jq -r '.access_token' .oauth-tokens/ingress.json)" --prompt "What time is it?"

    # Interactive mode:
    python agents/agent.py --jwt-token "$(cat api/.token)" --interactive
"""
    )

    # Server connection arguments
    parser.add_argument(
        '--mcp-registry-url',
        type=str,
        default='https://mcpgateway.ddns.net/mcpgw/mcp',
        help='URL of the MCP Registry (default: https://mcpgateway.ddns.net/mcpgw/mcp)',
    )

    # Authentication - JWT token required
    parser.add_argument(
        '--jwt-token',
        type=str,
        required=True,
        help='JWT token for authentication (required)',
    )

    # Model and provider arguments
    parser.add_argument(
        '--provider',
        type=str,
        choices=['anthropic', 'bedrock'],
        default='bedrock',
        help='Model provider to use (default: bedrock)',
    )
    parser.add_argument(
        '--model',
        type=str,
        default='us.anthropic.claude-3-7-sonnet-20250219-v1:0',
        help='Model ID to use',
    )

    # Prompt arguments
    parser.add_argument(
        '--prompt',
        type=str,
        default=None,
        help='Initial prompt to send to the agent',
    )

    # Interactive mode argument
    parser.add_argument(
        '--interactive',
        '-i',
        action='store_true',
        help='Enable interactive mode for multi-turn conversations',
    )

    # Verbose logging argument
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose HTTP debugging output',
    )

    args = parser.parse_args()

    # Enable verbose logging if requested
    if args.verbose:
        enable_verbose_logging()

    return args

@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression and return the result.
    
    This tool can perform basic arithmetic operations like addition, subtraction,
    multiplication, division, and exponentiation.
    
    Args:
        expression (str): The mathematical expression to evaluate (e.g., "2 + 2", "5 * 10", "(3 + 4) / 2")
    
    Returns:
        str: The result of the evaluation as a string
    
    Example:
        calculator("2 + 2") -> "4"
        calculator("5 * 10") -> "50"
        calculator("(3 + 4) / 2") -> "3.5"
    """
    # Security check: only allow basic arithmetic operations and numbers
    # Remove all whitespace
    expression = expression.replace(" ", "")
    
    # Check if the expression contains only allowed characters
    if not re.match(r'^[0-9+\-*/().^ ]+$', expression):
        return "Error: Only basic arithmetic operations (+, -, *, /, ^, (), .) are allowed."
    
    try:
        # Replace ^ with ** for exponentiation
        expression = expression.replace('^', '**')
        
        # Evaluate the expression
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"


@tool
async def search_registry_tools(
    query: str,
    max_results: int = 10,
) -> str:
    """
    Search for MCP tools using semantic search on the registry.

    Use this tool to discover available MCP tools that can help accomplish a task.
    The search uses natural language understanding to find the most relevant tools.

    Args:
        query (str): Natural language description of the capability you need
            (e.g., "get current time", "search jira issues", "manage files")
        max_results (int): Maximum number of results to return (default: 10)

    Returns:
        str: JSON string containing matching tools with their details including:
            - tool_name: Name of the tool
            - server_path: Path to invoke the tool on
            - server_name: Human-readable server name
            - description: What the tool does
            - relevance_score: How well it matches your query (0-1)
            - supported_transports: Transport protocols supported
            - auth_provider: Authentication provider if needed
            - tool_schema: Input parameters for the tool

    Example:
        search_registry_tools("get the current time in different timezones")
        search_registry_tools("search for jira issues", max_results=5)
    """
    global registry_client

    if registry_client is None:
        return json.dumps({
            "error": "Registry client not initialized. Check authentication configuration."
        })

    try:
        logger.info(f"Searching registry for tools: '{query}' (max_results={max_results})")

        # Search for tools using semantic search
        search_response = await registry_client.search_tools(
            query=query,
            max_results=max_results,
            entity_types=["mcp_server", "tool"],
        )

        results = []

        # Process tool results first (most specific)
        # The search API now returns inputSchema directly, no need for get_server_info
        for tool_result in search_response.tools:
            formatted = _format_tool_result(tool_result)
            results.append(formatted)

        # Also include matching tools from server results
        for server_result in search_response.servers:
            for matching_tool in server_result.matching_tools:
                # Check if this tool is already in results
                existing = [
                    r for r in results
                    if r["tool_name"] == matching_tool.tool_name
                    and r["server_path"] == server_result.path
                ]
                if existing:
                    continue

                tool_data = {
                    "tool_name": matching_tool.tool_name,
                    "server_path": server_result.path,
                    "server_name": server_result.server_name,
                    "description": matching_tool.description or "No description available",
                    "relevance_score": matching_tool.relevance_score,
                    "supported_transports": ["streamable_http"],
                }

                # Use inputSchema from matching tool if available
                if matching_tool.inputSchema:
                    tool_data["tool_schema"] = matching_tool.inputSchema

                results.append(tool_data)

        # Sort by relevance score
        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # Limit to max_results
        results = results[:max_results]

        logger.info(f"Found {len(results)} matching tools for query: '{query}'")

        return json.dumps({
            "query": query,
            "tools": results,
            "total_found": len(results),
        }, indent=2)

    except Exception as e:
        logger.error(f"Error searching registry: {e}", exc_info=True)
        return json.dumps({
            "error": f"Search failed: {str(e)}"
        })


@tool
async def invoke_mcp_tool(
    mcp_registry_url: str,
    server_name: str,
    tool_name: str,
    arguments: Dict[str, Any],
    supported_transports: List[str] = None,
    auth_provider: str = None,
) -> str:
    """
    Invoke a tool on an MCP server using the MCP Registry URL and server name with authentication.
    
    This tool creates an MCP client and calls the specified tool with the provided arguments.
    Authentication details are automatically retrieved from the system configuration.
    
    Args:
        mcp_registry_url (str): The URL of the MCP Registry
        server_name (str): The name of the MCP server to connect to
        tool_name (str): The name of the tool to invoke
        arguments (Dict[str, Any]): Dictionary containing the arguments for the tool
        supported_transports (List[str]): Transport protocols supported by the server (["streamable_http"] or ["sse"])
        auth_provider (str): The authentication provider for the server (e.g., "atlassian", "bedrock-agentcore")
    
    Returns:
        str: The result of the tool invocation as a string
    
    Example:
        invoke_mcp_tool("registry url", "currenttime", "current_time_by_timezone", {"tz_name": "America/New_York"}, ["streamable_http"])
    """
    # Construct the MCP server URL from the registry URL and server name using standard URL parsing
    parsed_url = urlparse(mcp_registry_url)
    
    # Extract the scheme, netloc and path from the parsed URL
    scheme = parsed_url.scheme
    netloc = parsed_url.netloc
    path = parsed_url.path
    
    # Use only the base URL (scheme + netloc) without any path
    base_url = f"{scheme}://{netloc}"
    
    # Create the server URL by joining the base URL with the server name
    # Remove leading slash from server_name if present to avoid double slashes
    if server_name.startswith('/'):
        server_name = server_name[1:]
    server_url = urljoin(base_url + '/', server_name)
    logger.info(f"invoke_mcp_tool, Initial Server URL: {server_url}")
    
    # Get authentication parameters from global agent_settings object
    # These will be populated by the main function when it generates the token
    auth_token = agent_settings.auth_token
    user_pool_id = agent_settings.user_pool_id
    client_id = agent_settings.client_id
    region = agent_settings.region or 'us-east-1'
    session_cookie = agent_settings.session_cookie
    
    # Determine auth method based on what's available
    if session_cookie:
        auth_method = 'session_cookie'
    else:
        auth_method = 'm2m'
    
    # Use ingress headers if available, otherwise fall back to the original auth
    if agent_settings.ingress_token:
        headers = {
            'X-Authorization': f'Bearer {agent_settings.ingress_token}',
            'X-User-Pool-Id': agent_settings.ingress_user_pool_id or '',
            'X-Client-Id': agent_settings.ingress_client_id or '',
            'X-Region': agent_settings.ingress_region or 'us-east-1'
        }
    else:
        # Fallback to original headers
        headers = {
            'X-User-Pool-Id': user_pool_id or '',
            'X-Client-Id': client_id or '',
            'X-Region': region or 'us-east-1'
        }
    
    # TRACE: Print all parameters received by invoke_mcp_tool
    logger.debug(f"invoke_mcp_tool TRACE - Parameters received:")
    logger.debug(f"  mcp_registry_url: {mcp_registry_url}")
    logger.debug(f"  server_name: {server_name}")
    logger.debug(f"  tool_name: {tool_name}")
    logger.debug(f"  arguments: {arguments}")
    logger.debug(f"  auth_token: {auth_token[:50] if auth_token else 'None'}...")
    logger.debug(f"  user_pool_id: {user_pool_id}")
    logger.debug(f"  client_id: {client_id}")
    logger.debug(f"  region: {region}")
    logger.debug(f"  auth_method: {auth_method}")
    logger.debug(f"  session_cookie: {session_cookie}")
    logger.debug(f"  supported_transports: {supported_transports}")
    logger.debug(f"invoke_mcp_tool TRACE - Headers built: {headers}")
    
    # Get server-specific headers from configuration
    server_name_clean = server_name.strip('/')
    server_headers = get_server_headers(server_name_clean, server_config)
    
    # Apply server-specific headers
    for header_name, header_value in server_headers.items():
        headers[header_name] = header_value
        
    # Check for egress authentication if auth_provider is specified
    if auth_provider:
        # Try to load egress token from {auth_provider}-{server_name}-egress.json
        oauth_tokens_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.oauth-tokens')
        # Convert server_name to lowercase and remove leading slash if present
        server_name_clean = server_name.strip('/').lower()
        egress_file = os.path.join(oauth_tokens_dir, f"{auth_provider.lower()}-{server_name_clean}-egress.json")
        
        # Also try without server name if the first file doesn't exist
        egress_file_alt = os.path.join(oauth_tokens_dir, f"{auth_provider.lower()}-egress.json")
        
        egress_data = None
        if os.path.exists(egress_file):
            logger.info(f"Found egress token file: {egress_file}")
            with open(egress_file, 'r') as f:
                egress_data = json.load(f)
        elif os.path.exists(egress_file_alt):
            logger.info(f"Found alternative egress token file: {egress_file_alt}")
            with open(egress_file_alt, 'r') as f:
                egress_data = json.load(f)
        
        if egress_data:
            # Add egress authorization header
            egress_token = egress_data.get('access_token')
            if egress_token:
                headers['Authorization'] = f'Bearer {egress_token}'
                logger.info(f"Added egress Authorization header for {auth_provider}")
            
            # Add provider-specific headers
            if auth_provider.lower() == 'atlassian':
                cloud_id = egress_data.get('cloud_id')
                if cloud_id:
                    headers['X-Atlassian-Cloud-Id'] = cloud_id
                    logger.info(f"Added X-Atlassian-Cloud-Id header: {cloud_id}")
        else:
            logger.warning(f"No egress token file found for auth_provider: {auth_provider}")
    
    if auth_method == "session_cookie" and session_cookie:
        headers['Cookie'] = f'mcp_gateway_session={session_cookie}'
    else:
        headers['X-Authorization'] = f'Bearer {auth_token}'
        # If no auth header from config and no egress token, use the general auth_token
        if 'Authorization' not in headers:
            headers['Authorization'] = f'Bearer {auth_token}'
    
    # Create redacted headers for logging (redact all sensitive values)
    redacted_headers = {}
    for header_name, header_value in headers.items():
        if header_name in ['Authorization', 'X-Authorization', 'Cookie', 'X-User-Pool-Id', 'X-Client-Id', 'X-Atlassian-Cloud-Id']:
            # Redact sensitive headers
            if header_name == 'Cookie':
                redacted_headers[header_name] = f'mcp_gateway_session={redact_sensitive_value(session_cookie if session_cookie else "")}'
            elif header_name in ['Authorization', 'X-Authorization'] and header_value.startswith('Bearer '):
                token_part = header_value[7:]  # Remove 'Bearer ' prefix
                redacted_headers[header_name] = f'Bearer {redact_sensitive_value(token_part)}'
            else:
                redacted_headers[header_name] = redact_sensitive_value(header_value)
        else:
            # Keep non-sensitive headers as-is
            redacted_headers[header_name] = header_value
    logger.info(f"headers after redaction: {headers}")
    try:
        # Determine transport based on supported_transports
        # Default to streamable_http, only use SSE if explicitly supported and no streamable_http
        use_sse = (supported_transports and 
                   "sse" in supported_transports and 
                   "streamable_http" not in supported_transports)
        transport_name = "SSE" if use_sse else "streamable_http"
        
        # For transport through the gateway, we need to append the transport endpoint
        # The nginx gateway expects the full path including the transport endpoint
        if use_sse:
            if not server_url.endswith('/'):
                server_url += '/'
            server_url += 'sse'
            logger.info(f"invoke_mcp_tool, Using SSE transport with gateway URL: {server_url}")
        else:
            # Don't add /mcp suffix - the gateway routes to the MCP endpoint directly
            logger.info(f"invoke_mcp_tool, Using streamable_http transport with gateway URL: {server_url}")
        
        # Connect to MCP server and execute tool call
        logger.info(f"invoke_mcp_tool, Connecting to MCP server using {transport_name}: {server_url}, headers: {redacted_headers}")
        
        if use_sse:
            # Create an MCP SSE client
            async with sse_client(server_url, headers=headers) as (read, write):
                async with mcp.ClientSession(read, write, sampling_callback=None) as session:
                    # Initialize the connection
                    await session.initialize()
                    
                    # Call the specified tool with the provided arguments
                    result = await session.call_tool(tool_name, arguments=arguments)
                    
                    # Format the result as a string
                    response = ""
                    for r in result.content:
                        response += r.text + "\n"
                    
                    return response.strip()
        else:
            # Create an MCP streamable-http client
            async with streamablehttp_client(url=server_url, headers=headers) as (read, write, get_session_id):
                async with mcp.ClientSession(read, write, sampling_callback=None) as session:
                    # Initialize the connection
                    await session.initialize()
                    
                    # Call the specified tool with the provided arguments
                    result = await session.call_tool(tool_name, arguments=arguments)
                    
                    # Format the result as a string
                    response = ""
                    for r in result.content:
                        response += r.text + "\n"
                    
                    return response.strip()
    except Exception as e:
        return f"Error invoking MCP tool: {str(e)}"

from datetime import datetime, UTC
current_utc_time = str(datetime.now(UTC))

# Global agent settings to store authentication details
class AgentSettings:
    def __init__(self):
        self.auth_token = None
        self.user_pool_id = None
        self.client_id = None
        self.region = None
        self.session_cookie = None
        # Ingress auth fields from .oauth-tokens/ingress.json
        self.ingress_token = None
        self.ingress_user_pool_id = None
        self.ingress_client_id = None
        self.ingress_region = None

agent_settings = AgentSettings()

# Global server configuration
server_config = {}

def redact_sensitive_value(value: str, show_chars: int = 4) -> str:
    """Redact sensitive values, showing only the first few characters"""
    if not value or len(value) <= show_chars:
        return "*" * len(value) if value else ""
    return value[:show_chars] + "*" * (len(value) - show_chars)


def load_system_prompt():
    """
    Load the system prompt template from the system_prompt.txt file.
    
    Returns:
        str: The system prompt template
    """
    import os
    try:
        # Get the directory where this Python file is located
        current_dir = os.path.dirname(__file__)
        system_prompt_path = os.path.join(current_dir, "system_prompt.txt")
        with open(system_prompt_path, "r") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading system prompt: {e}")
        # Provide a minimal fallback prompt in case the file can't be loaded
        return """
        <instructions>
        You are a highly capable AI assistant designed to solve problems for users.
        Current UTC time: {current_utc_time}
        MCP Registry URL: {mcp_registry_url}
        </instructions>
        """

def print_agent_response(response_dict: Dict[str, Any], verbose: bool = False) -> None:
    """
    Parse and print the agent's response in a user-friendly way
    
    Args:
        response_dict: Dictionary containing the agent response with 'messages' key
        verbose: Whether to show detailed debug information
    """
    # Debug: Log entry to function
    logger.debug(f"print_agent_response called with verbose={verbose}, response_dict keys: {response_dict.keys() if response_dict else 'None'}")
    if verbose:
        # Define ANSI color codes for different message types
        COLORS = {
            "SYSTEM": "\033[1;33m",  # Yellow
            "HUMAN": "\033[1;32m",   # Green
            "AI": "\033[1;36m",      # Cyan
            "TOOL": "\033[1;35m",    # Magenta
            "UNKNOWN": "\033[1;37m", # White
            "RESET": "\033[0m"       # Reset to default
        }
        if 'messages' not in response_dict:
            logger.warning("No messages found in response")
            return
        
        messages = response_dict['messages']
        blue = "\033[1;34m"  # Blue
        reset = COLORS["RESET"]
        logger.info(f"\n{blue}=== Found {len(messages)} messages ==={reset}\n")
        
        for i, message in enumerate(messages, 1):
            # Determine message type based on class name or type
            message_type = type(message).__name__
            
            if "SystemMessage" in message_type:
                msg_type = "SYSTEM"
            elif "HumanMessage" in message_type:
                msg_type = "HUMAN"
            elif "AIMessage" in message_type:
                msg_type = "AI"
            elif "ToolMessage" in message_type:
                msg_type = "TOOL"
            else:
                # Fallback to string matching if type name doesn't match expected patterns
                message_str = str(message)
                if "SystemMessage" in message_str:
                    msg_type = "SYSTEM"
                elif "HumanMessage" in message_str:
                    msg_type = "HUMAN"
                elif "AIMessage" in message_str:
                    msg_type = "AI"
                elif "ToolMessage" in message_str:
                    msg_type = "TOOL"
                else:
                    msg_type = "UNKNOWN"
            
            # Get message content
            content = message.content if hasattr(message, 'content') else str(message)
            
            # Check for tool calls
            tool_calls = []
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.get('name', 'unknown')
                    tool_args = tool_call.get('args', {})
                    tool_calls.append(f"Tool: {tool_name}, Args: {tool_args}")
            
            # Get the color for this message type
            color = COLORS.get(msg_type, COLORS["UNKNOWN"])
            reset = COLORS["RESET"]
            
            # Log message with enhanced formatting and color coding - entire message in color
            logger.info(f"\n{color}{'=' * 20} MESSAGE #{i} - TYPE: {msg_type} {'=' * 20}")
            logger.info(f"{'-' * 80}")
            logger.info(f"CONTENT: {content}")
            
            # Log any tool calls
            if tool_calls:
                logger.info(f"\nTOOL CALLS:")
                for tc in tool_calls:
                    logger.info(f"  {tc}")
            logger.info(f"{'=' * 20} END OF {msg_type} MESSAGE #{i} {'=' * 20}{reset}")
            logger.info("")
    
    # Always show the final AI response (both in verbose and non-verbose mode)
    # This section runs regardless of verbose flag
    if not verbose:
        logger.info("=== Attempting to print final response (non-verbose mode) ===")
    
    if response_dict and "messages" in response_dict and response_dict["messages"]:
        # Debug: Log that we're looking for the final AI message
        if not verbose:
            logger.info(f"Found {len(response_dict['messages'])} messages in response")
        
        # Get the last AI message from the response
        for message in reversed(response_dict["messages"]):
            message_type = type(message).__name__
            
            # Debug logging in non-verbose mode to understand what's happening
            if not verbose:
                logger.debug(f"Checking message type: {message_type}")
            
            # Check if this is an AI message
            if "AIMessage" in message_type or "ai" in str(type(message)).lower():
                # Extract and print the content
                content = None
                
                # Try different ways to extract content
                if hasattr(message, 'content'):
                    content = message.content
                elif isinstance(message, dict) and "content" in message:
                    content = message["content"]
                else:
                    # Try to extract content from string representation as last resort
                    try:
                        content = str(message)
                    except:
                        content = None
                
                # Print the content if we found any
                if content:
                    # Force print the final response regardless of any conditions
                    print("\n" + str(content), flush=True)
                    
                    if not verbose:
                        logger.info(f"Final AI Response printed (length: {len(str(content))} chars)")
                else:
                    if not verbose:
                        logger.warning(f"AI message found but no content extracted. Message type: {message_type}, Message attrs: {dir(message) if hasattr(message, '__dict__') else 'N/A'}")
                
                # We found an AI message, stop looking
                break
        else:
            # No AI message found - try to print the last message regardless
            if not verbose:
                logger.warning("No AI message found in response, attempting to print last message")
                logger.debug(f"Messages in response: {[type(m).__name__ for m in response_dict['messages']]}")
            
            # As a fallback, print the last message if it has content
            if response_dict["messages"]:
                last_message = response_dict["messages"][-1]
                content = None
                
                if hasattr(last_message, 'content'):
                    content = last_message.content
                elif isinstance(last_message, dict) and "content" in last_message:
                    content = last_message["content"]
                
                if content:
                    print("\n[Response]\n" + str(content), flush=True)
                    logger.info(f"Printed last message as fallback (type: {type(last_message).__name__})")


class InteractiveAgent:
    """Interactive agent that maintains conversation history"""
    
    def __init__(self, agent, system_prompt: str, verbose: bool = False):
        """
        Initialize the interactive agent
        
        Args:
            agent: The LangGraph agent instance
            system_prompt: The formatted system prompt
            verbose: Whether to show detailed debug output
        """
        self.agent = agent
        self.system_prompt = system_prompt
        self.verbose = verbose
        self.conversation_history = []
        
    async def process_message(self, user_input: str) -> Dict[str, Any]:
        """
        Process a user message and return the agent's response
        
        Args:
            user_input: The user's input message
            
        Returns:
            Dict containing the agent's response
        """
        # Build messages list with conversation history
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add conversation history
        for msg in self.conversation_history:
            messages.append(msg)
        
        # Add new user message
        messages.append({"role": "user", "content": user_input})
        
        if self.verbose:
            logger.info(f"\nSending {len(messages)} messages to agent (including system prompt)")
        
        # Invoke the agent
        response = await self.agent.ainvoke({"messages": messages})
        
        # Store the user message and AI response in history
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # Extract the AI's response from the messages
        if response and "messages" in response and response["messages"]:
            for message in reversed(response["messages"]):
                message_type = type(message).__name__
                if "AIMessage" in message_type:
                    ai_content = message.content if hasattr(message, 'content') else str(message)
                    self.conversation_history.append({"role": "assistant", "content": ai_content})
                    break
        
        return response
    
    async def run_interactive_session(self):
        """Run an interactive conversation session"""
        print("\n" + "="*60)
        print("烙 Interactive Agent Session Started")
        print("="*60)
        print("Type 'exit', 'quit', or 'bye' to end the session")
        print("Type 'clear' or 'reset' to clear conversation history")
        print("Type 'history' to view conversation history")
        print("="*60 + "\n")
        
        while True:
            try:
                # Get user input
                user_input = input("\n You: ").strip()
                
                # Check for exit commands
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("\n Goodbye! Thanks for chatting.")
                    break
                
                # Check for clear/reset commands
                if user_input.lower() in ['clear', 'reset']:
                    self.conversation_history = []
                    print("\n Conversation history cleared.")
                    continue
                
                # Check for history command
                if user_input.lower() == 'history':
                    if not self.conversation_history:
                        print("\n No conversation history yet.")
                    else:
                        print("\n Conversation History:")
                        print("-" * 40)
                        for i, msg in enumerate(self.conversation_history):
                            role = "You" if msg["role"] == "user" else "Agent"
                            print(f"{i+1}. {role}: {msg['content'][:100]}...")
                    continue
                
                # Skip empty input
                if not user_input:
                    continue
                
                # Process the message
                print("\n樂 Thinking...")
                response = await self.process_message(user_input)
                
                # Print the response
                print("\n烙 Agent:", end="")
                print_agent_response(response, self.verbose)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type 'exit' to quit or continue chatting.")
                continue
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
                if self.verbose:
                    import traceback
                    print(traceback.format_exc())


async def main():
    """
    Main function that:
    1. Parses command line arguments
    2. Uses the provided JWT token for authentication
    3. Sets up the LLM model (Anthropic or Amazon Bedrock)
    4. Creates a LangGraph agent with available tools
    5. Either runs in interactive mode or processes a single prompt
    """
    # Parse command line arguments
    args = parse_arguments()
    logger.info("Parsed command line arguments successfully")
    
    # Use the provided JWT token
    access_token = args.jwt_token
    logger.info("Using JWT token for authentication")

    # Set global auth variables for invoke_mcp_tool
    agent_settings.auth_token = access_token
    agent_settings.ingress_token = access_token

    # Load server configuration
    global server_config
    server_config = load_server_config()

    # Display configuration
    logger.info(f"MCP Registry URL: {args.mcp_registry_url}")
    logger.info(f"Model provider: {args.provider}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Interactive mode: {args.interactive}")
    if args.prompt:
        logger.info(f"Initial prompt: {args.prompt}")

    # Initialize model based on provider
    if args.provider == 'anthropic':
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not anthropic_api_key:
            logger.error("ANTHROPIC_API_KEY not found in environment variables")
            return

        model = ChatAnthropic(
            model=args.model,
            api_key=anthropic_api_key,
            temperature=0,
            max_tokens=8192,
        )
        logger.info(f"Initialized Anthropic model: {args.model}")
    else:
        # Default to Bedrock
        aws_region = os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'us-east-1'))
        logger.info(f"Using Bedrock provider with AWS region: {aws_region}")

        model = ChatBedrock(
            model_id=args.model,
            region_name=aws_region,
            temperature=0,
            max_tokens=8192,
        )
        logger.info(f"Initialized Bedrock model: {args.model} in region {aws_region}")
    
    try:
        # Initialize the registry client for semantic search
        global registry_client

        # Extract base URL from mcp_registry_url (remove /mcpgw/mcp suffix if present)
        parsed_registry_url = urlparse(args.mcp_registry_url)
        registry_base_url = f"{parsed_registry_url.scheme}://{parsed_registry_url.netloc}"
        logger.info(f"Registry base URL: {registry_base_url}")

        registry_client = RegistryClient(
            registry_url=registry_base_url,
            jwt_token=access_token,
        )
        logger.info("Initialized registry client for semantic search")

        # Define all tools available to the agent
        all_tools = [calculator, search_registry_tools, invoke_mcp_tool]
        logger.info(f"Available tools: {[t.name for t in all_tools]}")

        # Create the agent with the model and all tools
        agent = create_react_agent(model, all_tools)

        # Load and format the system prompt
        system_prompt_template = load_system_prompt()
        system_prompt = system_prompt_template.format(
            current_utc_time=current_utc_time,
            mcp_registry_url=args.mcp_registry_url,
        )
        
        # Create the interactive agent
        interactive_agent = InteractiveAgent(agent, system_prompt, args.verbose)
        
        # If an initial prompt is provided, process it first
        if args.prompt:
            logger.info("\nProcessing initial prompt...\n" + "-"*40)
            response = await interactive_agent.process_message(args.prompt)
            
            if not args.interactive:
                # Single-turn mode - just show the response and exit
                logger.info("\nResponse:" + "\n" + "-"*40)
                logger.debug(f"Calling print_agent_response with verbose={args.verbose}")
                logger.debug(f"Response has {len(response.get('messages', []))} messages")
                print_agent_response(response, args.verbose)
                return
            else:
                # Interactive mode - show the response and continue
                print("\n烙 Agent:", end="")
                print_agent_response(response, args.verbose)
        
        # If interactive mode is enabled, start the interactive session
        if args.interactive:
            await interactive_agent.run_interactive_session()
        elif not args.prompt:
            # No prompt and not interactive - show usage
            print("\n⚠️  No prompt provided. Use --prompt to send a message or --interactive for chat mode.")
            print("\nExamples:")
            print('  python agent_interactive.py --prompt "What time is it?"')
            print('  python agent_interactive.py --interactive')
            print('  python agent_interactive.py --prompt "Hello" --interactive')
                
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())