#!/usr/bin/env python3
"""
MCP Gateway Registry Management CLI.

High-level wrapper for the RegistryClient providing command-line interface
for server registration, management, and group operations.

Usage:
    # Register a server from JSON config
    uv run python registry_management.py register --config /path/to/config.json

    # List all servers
    uv run python registry_management.py list

    # Toggle server status
    uv run python registry_management.py toggle --path /cloudflare-docs

    # Remove server
    uv run python registry_management.py remove --path /cloudflare-docs

    # Health check
    uv run python registry_management.py healthcheck

    # Group operations
    uv run python registry_management.py add-to-groups --server my-server --groups group1,group2
    uv run python registry_management.py list-groups

Environment Variables:
    REGISTRY_URL: Registry base URL (default: https://registry.mycorp.click)
    CLIENT_NAME: Keycloak client name (default: registry-admin-bot)
    GET_TOKEN_SCRIPT: Path to get-m2m-token.sh script
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from registry_client import (
    RegistryClient,
    InternalServiceRegistration,
    ServerListResponse,
    ToggleResponse,
    GroupListResponse
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)


def _get_registry_url() -> str:
    """
    Get registry URL from environment variable or terraform-outputs.json.

    Priority:
    1. REGISTRY_URL environment variable
    2. terraform-outputs.json file
    3. Default value

    Returns:
        Registry base URL
    """
    # Check environment variable first
    registry_url = os.getenv("REGISTRY_URL")
    if registry_url:
        logger.debug(f"Using registry URL from environment: {registry_url}")
        return registry_url

    # Try to load from terraform-outputs.json
    try:
        script_dir = Path(__file__).parent
        tf_outputs_file = script_dir / "terraform-outputs.json"
        if tf_outputs_file.exists():
            with open(tf_outputs_file, 'r') as f:
                tf_outputs = json.load(f)
                registry_url = tf_outputs.get('registry_url', {}).get('value')
                if registry_url:
                    logger.debug(f"Using registry URL from terraform-outputs.json: {registry_url}")
                    return registry_url
    except Exception as e:
        logger.debug(f"Could not load registry URL from terraform-outputs.json: {e}")

    # Fall back to default
    default_url = "https://registry.mycorp.click"
    logger.debug(f"Using default registry URL: {default_url}")
    return default_url


def _get_client_name() -> str:
    """
    Get Keycloak client name from environment variable or default.

    Returns:
        Client name
    """
    client_name = os.getenv("CLIENT_NAME", "registry-admin-bot")
    logger.debug(f"Using client name: {client_name}")
    return client_name


def _get_token_script() -> str:
    """
    Get path to get-m2m-token.sh script.

    Returns:
        Script path
    """
    # Default to get-m2m-token.sh in the same directory as this script
    script_dir = Path(__file__).parent
    default_script = str(script_dir / "get-m2m-token.sh")
    script_path = os.getenv("GET_TOKEN_SCRIPT", default_script)
    logger.debug(f"Using token script: {script_path}")
    return script_path


def _get_jwt_token() -> str:
    """
    Retrieve JWT token using get-m2m-token.sh script.

    Returns:
        JWT access token

    Raises:
        RuntimeError: If token retrieval fails
    """
    client_name = _get_client_name()
    script_path = _get_token_script()

    try:
        # Redact client name in logs for security
        logger.debug(f"Retrieving token for client: {client_name}")

        result = subprocess.run(
            [script_path, client_name],
            capture_output=True,
            text=True,
            check=True
        )

        token = result.stdout.strip()

        if not token:
            raise RuntimeError("Empty token returned from get-m2m-token.sh")

        # Redact token in logs - show only first 8 characters
        redacted_token = f"{token[:8]}..." if len(token) > 8 else "***"
        logger.debug(f"Successfully retrieved JWT token: {redacted_token}")
        return token

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to retrieve token: {e.stderr}")
        raise RuntimeError(f"Token retrieval failed: {e.stderr}") from e
    except Exception as e:
        logger.error(f"Unexpected error retrieving token: {e}")
        raise RuntimeError(f"Token retrieval error: {e}") from e


def _load_json_config(config_path: str) -> Dict[str, Any]:
    """
    Load JSON configuration file.

    Args:
        config_path: Path to JSON config file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file not found
        json.JSONDecodeError: If config file is invalid JSON
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, 'r') as f:
        config = json.load(f)

    logger.debug(f"Loaded configuration from {config_path}")
    return config


def _create_client() -> RegistryClient:
    """
    Create and return a configured RegistryClient instance.

    Returns:
        RegistryClient instance

    Raises:
        RuntimeError: If token retrieval fails
    """
    token = _get_jwt_token()
    return RegistryClient(
        registry_url=_get_registry_url(),
        token=token
    )


def cmd_register(args: argparse.Namespace) -> int:
    """
    Register a new server from JSON configuration.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        config = _load_json_config(args.config)

        # Convert config to InternalServiceRegistration
        # Handle both old and new config formats
        registration = InternalServiceRegistration(
            service_path=config.get("path") or config.get("service_path"),
            name=config.get("server_name") or config.get("name"),
            description=config.get("description"),
            proxy_pass_url=config.get("proxy_pass_url"),
            auth_provider=config.get("auth_provider"),
            auth_type=config.get("auth_type"),
            supported_transports=config.get("supported_transports"),
            headers=config.get("headers"),
            tool_list_json=config.get("tool_list_json"),
            overwrite=args.overwrite
        )

        client = _create_client()
        response = client.register_service(registration)

        logger.info(f"Server registered successfully: {response.path}")
        logger.info(f"Message: {response.message}")
        return 0

    except FileNotFoundError as e:
        logger.error(f"Configuration file error: {e}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON configuration: {e}")
        return 1
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """
    List all registered servers.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        client = _create_client()
        response = client.list_services()

        if not response.servers:
            logger.info("No servers registered")
            return 0

        logger.info(f"Found {len(response.servers)} registered servers:\n")

        for server in response.servers:
            status_icon = "✓" if server.is_enabled else "✗"
            health_icon = {
                "healthy": "🟢",
                "unhealthy": "🔴",
                "unknown": "⚪"
            }.get(server.health_status.value, "⚪")

            print(f"{status_icon} {health_icon} {server.path}")
            print(f"   Name: {server.name}")
            print(f"   Description: {server.description}")
            print(f"   Enabled: {server.is_enabled}")
            print(f"   Health: {server.health_status.value}")
            print()

        return 0

    except Exception as e:
        logger.error(f"List operation failed: {e}")
        return 1


def cmd_toggle(args: argparse.Namespace) -> int:
    """
    Toggle server enabled/disabled status.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        client = _create_client()
        response = client.toggle_service(args.path)

        status = "enabled" if response.is_enabled else "disabled"
        logger.info(f"Server {response.path} is now {status}")
        logger.info(f"Message: {response.message}")
        return 0

    except Exception as e:
        logger.error(f"Toggle operation failed: {e}")
        return 1


def cmd_remove(args: argparse.Namespace) -> int:
    """
    Remove a server from the registry.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        if not args.force:
            confirmation = input(f"Remove server {args.path}? (yes/no): ")
            if confirmation.lower() != "yes":
                logger.info("Operation cancelled")
                return 0

        client = _create_client()
        response = client.remove_service(args.path)

        logger.info(f"Server removed successfully: {args.path}")
        return 0

    except Exception as e:
        logger.error(f"Remove operation failed: {e}")
        return 1


def cmd_healthcheck(args: argparse.Namespace) -> int:
    """
    Perform health check on all servers.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        client = _create_client()
        response = client.healthcheck()

        logger.info(f"Health check status: {response.get('status', 'unknown')}")
        logger.info("\nHealth check results:")
        print(json.dumps(response, indent=2))
        return 0

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return 1


def cmd_add_to_groups(args: argparse.Namespace) -> int:
    """
    Add server to user groups.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        groups = [g.strip() for g in args.groups.split(",")]
        client = _create_client()
        response = client.add_server_to_groups(args.server, groups)

        logger.info(f"Server {args.server} added to groups: {', '.join(groups)}")
        return 0

    except Exception as e:
        logger.error(f"Add to groups failed: {e}")
        return 1


def cmd_remove_from_groups(args: argparse.Namespace) -> int:
    """
    Remove server from user groups.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        groups = [g.strip() for g in args.groups.split(",")]
        client = _create_client()
        response = client.remove_server_from_groups(args.server, groups)

        logger.info(f"Server {args.server} removed from groups: {', '.join(groups)}")
        return 0

    except Exception as e:
        logger.error(f"Remove from groups failed: {e}")
        return 1


def cmd_create_group(args: argparse.Namespace) -> int:
    """
    Create a new user group.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        client = _create_client()
        response = client.create_group(
            group_name=args.name,
            description=args.description,
            create_in_keycloak=args.keycloak
        )

        logger.info(f"Group created successfully: {args.name}")
        return 0

    except Exception as e:
        logger.error(f"Create group failed: {e}")
        return 1


def cmd_delete_group(args: argparse.Namespace) -> int:
    """
    Delete a user group.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        if not args.force:
            confirmation = input(f"Delete group {args.name}? (yes/no): ")
            if confirmation.lower() != "yes":
                logger.info("Operation cancelled")
                return 0

        client = _create_client()
        response = client.delete_group(
            group_name=args.name,
            delete_from_keycloak=args.keycloak,
            force=args.force
        )

        logger.info(f"Group deleted successfully: {args.name}")
        return 0

    except Exception as e:
        logger.error(f"Delete group failed: {e}")
        return 1


def cmd_list_groups(args: argparse.Namespace) -> int:
    """
    List all user groups.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        client = _create_client()
        response = client.list_groups(
            include_keycloak=not args.no_keycloak,
            include_scopes=not args.no_scopes
        )

        if not response.groups:
            logger.info("No groups found")
            return 0

        logger.info(f"Found {len(response.groups)} groups:\n")

        for group in response.groups:
            print(f"Group: {group.get('name', 'Unknown')}")
            if 'description' in group:
                print(f"  Description: {group['description']}")
            if 'servers' in group:
                print(f"  Servers: {', '.join(group['servers']) if group['servers'] else 'None'}")
            print()

        return 0

    except Exception as e:
        logger.error(f"List groups failed: {e}")
        return 1


def main() -> int:
    """
    Main entry point for the CLI.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="MCP Gateway Registry Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  REGISTRY_URL        Registry base URL (default: https://registry.mycorp.click)
  CLIENT_NAME         Keycloak client name (default: registry-admin-bot)
  GET_TOKEN_SCRIPT    Path to get-m2m-token.sh script

Examples:
  # Register a server
  uv run python registry_management.py register --config server-config.json

  # List all servers
  uv run python registry_management.py list

  # Toggle server status
  uv run python registry_management.py toggle --path /cloudflare-docs

  # Add server to groups
  uv run python registry_management.py add-to-groups --server my-server --groups finance,analytics
        """
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Register command
    register_parser = subparsers.add_parser("register", help="Register a new server")
    register_parser.add_argument(
        "--config",
        required=True,
        help="Path to server configuration JSON file"
    )
    register_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite if server already exists"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List all servers")

    # Toggle command
    toggle_parser = subparsers.add_parser("toggle", help="Toggle server status")
    toggle_parser.add_argument(
        "--path",
        required=True,
        help="Server path to toggle"
    )

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a server")
    remove_parser.add_argument(
        "--path",
        required=True,
        help="Server path to remove"
    )
    remove_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )

    # Healthcheck command
    healthcheck_parser = subparsers.add_parser("healthcheck", help="Health check all servers")

    # Add to groups command
    add_groups_parser = subparsers.add_parser("add-to-groups", help="Add server to groups")
    add_groups_parser.add_argument(
        "--server",
        required=True,
        help="Server name"
    )
    add_groups_parser.add_argument(
        "--groups",
        required=True,
        help="Comma-separated group names"
    )

    # Remove from groups command
    remove_groups_parser = subparsers.add_parser("remove-from-groups", help="Remove server from groups")
    remove_groups_parser.add_argument(
        "--server",
        required=True,
        help="Server name"
    )
    remove_groups_parser.add_argument(
        "--groups",
        required=True,
        help="Comma-separated group names"
    )

    # Create group command
    create_group_parser = subparsers.add_parser("create-group", help="Create a new group")
    create_group_parser.add_argument(
        "--name",
        required=True,
        help="Group name"
    )
    create_group_parser.add_argument(
        "--description",
        help="Group description"
    )
    create_group_parser.add_argument(
        "--keycloak",
        action="store_true",
        help="Also create in Keycloak"
    )

    # Delete group command
    delete_group_parser = subparsers.add_parser("delete-group", help="Delete a group")
    delete_group_parser.add_argument(
        "--name",
        required=True,
        help="Group name"
    )
    delete_group_parser.add_argument(
        "--keycloak",
        action="store_true",
        help="Also delete from Keycloak"
    )
    delete_group_parser.add_argument(
        "--force",
        action="store_true",
        help="Force deletion of system groups and skip confirmation"
    )

    # List groups command
    list_groups_parser = subparsers.add_parser("list-groups", help="List all groups")
    list_groups_parser.add_argument(
        "--no-keycloak",
        action="store_true",
        help="Exclude Keycloak information"
    )
    list_groups_parser.add_argument(
        "--no-scopes",
        action="store_true",
        help="Exclude scope information"
    )

    args = parser.parse_args()

    # Enable debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Dispatch to command handler
    if not args.command:
        parser.print_help()
        return 1

    command_handlers = {
        "register": cmd_register,
        "list": cmd_list,
        "toggle": cmd_toggle,
        "remove": cmd_remove,
        "healthcheck": cmd_healthcheck,
        "add-to-groups": cmd_add_to_groups,
        "remove-from-groups": cmd_remove_from_groups,
        "create-group": cmd_create_group,
        "delete-group": cmd_delete_group,
        "list-groups": cmd_list_groups
    }

    handler = command_handlers.get(args.command)
    if not handler:
        logger.error(f"Unknown command: {args.command}")
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
