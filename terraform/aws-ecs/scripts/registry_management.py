#!/usr/bin/env python3
"""
MCP Gateway Registry Management CLI.

High-level wrapper for the RegistryClient providing command-line interface
for server registration, management, group operations, and A2A agent management.

Server Management:
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

Group Management:
    # Add server to groups
    uv run python registry_management.py add-to-groups --server my-server --groups group1,group2

    # List all groups
    uv run python registry_management.py list-groups

Agent Management (A2A):
    # Register an agent
    uv run python registry_management.py agent-register --config /path/to/agent.json

    # List all agents
    uv run python registry_management.py agent-list

    # Get agent details
    uv run python registry_management.py agent-get --path /code-reviewer

    # Toggle agent status
    uv run python registry_management.py agent-toggle --path /code-reviewer --enabled true

    # Delete agent
    uv run python registry_management.py agent-delete --path /code-reviewer

    # Discover agents by skills
    uv run python registry_management.py agent-discover --skills code_analysis,bug_detection

    # Semantic agent search
    uv run python registry_management.py agent-search --query "agents that analyze code"

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
    GroupListResponse,
    AgentRegistration,
    AgentProvider,
    AgentVisibility,
    Skill,
    AgentListResponse,
    AgentDetail,
    AgentToggleResponse,
    AgentDiscoveryResponse,
    AgentSemanticDiscoveryResponse
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


# Agent Management Command Handlers


def cmd_agent_register(args: argparse.Namespace) -> int:
    """
    Register a new A2A agent from JSON configuration.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error(f"Config file not found: {config_path}")
            return 1

        with open(config_path, 'r') as f:
            config = json.load(f)

        # Convert skills list of dicts to Skill objects
        # Handle both 'input_schema' and 'parameters' field names
        skills = []
        for skill_data in config.get('skills', []):
            # Normalize field names
            skill_dict = {
                'name': skill_data.get('name', skill_data.get('id', '')),
                'description': skill_data.get('description', '')
            }
            # Use 'input_schema' if present, otherwise use 'parameters'
            if 'input_schema' in skill_data:
                skill_dict['input_schema'] = skill_data['input_schema']
            elif 'parameters' in skill_data:
                skill_dict['input_schema'] = skill_data['parameters']

            skills.append(Skill(**skill_dict))
        config['skills'] = skills

        # Convert provider string to enum with validation
        if 'provider' in config:
            provider_value = config['provider'].lower()
            # Map common values to valid enum values
            provider_map = {
                'anthropic': AgentProvider.ANTHROPIC,
                'custom': AgentProvider.CUSTOM,
                'other': AgentProvider.OTHER,
                'example corp': AgentProvider.CUSTOM,
                'example': AgentProvider.CUSTOM
            }

            if provider_value in provider_map:
                config['provider'] = provider_map[provider_value]
            else:
                logger.warning(f"Unknown provider '{config['provider']}', using 'custom'")
                config['provider'] = AgentProvider.CUSTOM

        # Convert visibility string to enum if present
        if 'visibility' in config:
            try:
                config['visibility'] = AgentVisibility(config['visibility'].lower())
            except ValueError:
                logger.warning(f"Unknown visibility '{config['visibility']}', using 'public'")
                config['visibility'] = AgentVisibility.PUBLIC

        # Handle security_schemes conversion
        # Map common OpenAPI security types to our enum
        if 'security_schemes' in config:
            transformed_schemes = {}
            for scheme_name, scheme_data in config['security_schemes'].items():
                scheme_type = scheme_data.get('type', '').lower()
                # Map OpenAPI types to our enum values
                type_map = {
                    'http': 'bearer',  # HTTP bearer auth
                    'bearer': 'bearer',
                    'apikey': 'api_key',
                    'api_key': 'api_key',
                    'oauth2': 'oauth2'
                }
                mapped_type = type_map.get(scheme_type, 'bearer')
                transformed_schemes[scheme_name] = {
                    'type': mapped_type,
                    'description': scheme_data.get('description', '')
                }
            config['security_schemes'] = transformed_schemes

        # Remove fields that aren't in AgentRegistration model
        valid_fields = {
            'name', 'description', 'path', 'url', 'version', 'provider',
            'security_schemes', 'skills', 'tags', 'visibility', 'license'
        }
        config = {k: v for k, v in config.items() if k in valid_fields}

        agent = AgentRegistration(**config)
        client = _create_client()
        response = client.register_agent(agent)

        logger.info(f"Agent registered successfully: {response.agent.name} at {response.agent.path}")
        print(json.dumps({
            "message": response.message,
            "agent": {
                "name": response.agent.name,
                "path": response.agent.path,
                "url": response.agent.url,
                "num_skills": response.agent.num_skills,
                "is_enabled": response.agent.is_enabled
            }
        }, indent=2))
        return 0

    except Exception as e:
        logger.error(f"Agent registration failed: {e}")
        logger.debug(f"Full error details:", exc_info=True)
        return 1


def cmd_agent_list(args: argparse.Namespace) -> int:
    """
    List all A2A agents.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        client = _create_client()
        response = client.list_agents(
            query=args.query if hasattr(args, 'query') else None,
            enabled_only=args.enabled_only if hasattr(args, 'enabled_only') else False,
            visibility=args.visibility if hasattr(args, 'visibility') else None
        )

        if not response.agents:
            logger.info("No agents found")
            return 0

        logger.info(f"Found {len(response.agents)} agents:\n")
        for agent in response.agents:
            status = "✓" if agent.is_enabled else "✗"
            print(f"{status} {agent.name} ({agent.path})")
            print(f"  {agent.description}")
            print()

        return 0

    except Exception as e:
        logger.error(f"List agents failed: {e}")
        return 1


def cmd_agent_get(args: argparse.Namespace) -> int:
    """
    Get detailed information about a specific agent.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        client = _create_client()
        agent = client.get_agent(args.path)

        logger.info(f"Retrieved agent: {agent.name}")
        print(json.dumps({
            "name": agent.name,
            "path": agent.path,
            "description": agent.description,
            "url": agent.url,
            "version": agent.version,
            "provider": agent.provider,
            "is_enabled": agent.is_enabled,
            "visibility": agent.visibility,
            "skills": [
                {
                    "name": skill.name,
                    "description": skill.description
                }
                for skill in agent.skills
            ]
        }, indent=2))
        return 0

    except Exception as e:
        logger.error(f"Get agent failed: {e}")
        return 1


def cmd_agent_update(args: argparse.Namespace) -> int:
    """
    Update an existing agent.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error(f"Config file not found: {config_path}")
            return 1

        with open(config_path, 'r') as f:
            config = json.load(f)

        # Convert skills list of dicts to Skill objects
        # Handle both 'input_schema' and 'parameters' field names
        skills = []
        for skill_data in config.get('skills', []):
            skill_dict = {
                'name': skill_data.get('name', skill_data.get('id', '')),
                'description': skill_data.get('description', '')
            }
            if 'input_schema' in skill_data:
                skill_dict['input_schema'] = skill_data['input_schema']
            elif 'parameters' in skill_data:
                skill_dict['input_schema'] = skill_data['parameters']
            skills.append(Skill(**skill_dict))
        config['skills'] = skills

        # Convert provider string to enum with validation
        if 'provider' in config:
            provider_value = config['provider'].lower()
            provider_map = {
                'anthropic': AgentProvider.ANTHROPIC,
                'custom': AgentProvider.CUSTOM,
                'other': AgentProvider.OTHER,
                'example corp': AgentProvider.CUSTOM,
                'example': AgentProvider.CUSTOM
            }
            if provider_value in provider_map:
                config['provider'] = provider_map[provider_value]
            else:
                logger.warning(f"Unknown provider '{config['provider']}', using 'custom'")
                config['provider'] = AgentProvider.CUSTOM

        # Convert visibility string to enum if present
        if 'visibility' in config:
            try:
                config['visibility'] = AgentVisibility(config['visibility'].lower())
            except ValueError:
                logger.warning(f"Unknown visibility '{config['visibility']}', using 'public'")
                config['visibility'] = AgentVisibility.PUBLIC

        # Handle security_schemes conversion
        if 'security_schemes' in config:
            transformed_schemes = {}
            for scheme_name, scheme_data in config['security_schemes'].items():
                scheme_type = scheme_data.get('type', '').lower()
                type_map = {
                    'http': 'bearer',
                    'bearer': 'bearer',
                    'apikey': 'api_key',
                    'api_key': 'api_key',
                    'oauth2': 'oauth2'
                }
                mapped_type = type_map.get(scheme_type, 'bearer')
                transformed_schemes[scheme_name] = {
                    'type': mapped_type,
                    'description': scheme_data.get('description', '')
                }
            config['security_schemes'] = transformed_schemes

        # Remove fields that aren't in AgentRegistration model
        valid_fields = {
            'name', 'description', 'path', 'url', 'version', 'provider',
            'security_schemes', 'skills', 'tags', 'visibility', 'license'
        }
        config = {k: v for k, v in config.items() if k in valid_fields}

        agent = AgentRegistration(**config)
        client = _create_client()
        response = client.update_agent(args.path, agent)

        logger.info(f"Agent updated successfully: {response.name}")
        return 0

    except Exception as e:
        logger.error(f"Agent update failed: {e}")
        logger.debug(f"Full error details:", exc_info=True)
        return 1


def cmd_agent_delete(args: argparse.Namespace) -> int:
    """
    Delete an agent from the registry.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        if not args.force:
            confirmation = input(f"Delete agent {args.path}? (yes/no): ")
            if confirmation.lower() != "yes":
                logger.info("Operation cancelled")
                return 0

        client = _create_client()
        client.delete_agent(args.path)

        logger.info(f"Agent deleted successfully: {args.path}")
        return 0

    except Exception as e:
        logger.error(f"Agent deletion failed: {e}")
        return 1


def cmd_agent_toggle(args: argparse.Namespace) -> int:
    """
    Toggle agent enabled/disabled status.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        client = _create_client()
        response = client.toggle_agent(args.path, args.enabled)

        logger.info(f"Agent {response.path} is now {'enabled' if response.is_enabled else 'disabled'}")
        return 0

    except Exception as e:
        logger.error(f"Agent toggle failed: {e}")
        return 1


def cmd_agent_discover(args: argparse.Namespace) -> int:
    """
    Discover agents by required skills.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        skills = [s.strip() for s in args.skills.split(',')]
        tags = [t.strip() for t in args.tags.split(',')] if args.tags else None

        client = _create_client()
        response = client.discover_agents_by_skills(
            skills=skills,
            tags=tags,
            max_results=args.max_results
        )

        if not response.agents:
            logger.info("No agents found matching the required skills")
            return 0

        logger.info(f"Found {len(response.agents)} matching agents:\n")
        for agent in response.agents:
            print(f"{agent.name} ({agent.path})")
            print(f"  Relevance: {agent.relevance_score:.2%}")
            print(f"  Matching skills: {', '.join(agent.matching_skills)}")
            print()

        return 0

    except Exception as e:
        logger.error(f"Agent discovery failed: {e}")
        return 1


def cmd_agent_search(args: argparse.Namespace) -> int:
    """
    Perform semantic search for agents.

    Args:
        args: Command arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        client = _create_client()
        response = client.discover_agents_semantic(
            query=args.query,
            max_results=args.max_results
        )

        if not response.agents:
            logger.info("No agents found matching the query")
            return 0

        logger.info(f"Found {len(response.agents)} matching agents:\n")
        for agent in response.agents:
            print(f"{agent.name} ({agent.path})")
            print(f"  Relevance: {agent.relevance_score:.2%}")
            print(f"  {agent.description[:100]}...")
            print()

        return 0

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
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

    # Agent Management Commands

    # Agent register command
    agent_register_parser = subparsers.add_parser("agent-register", help="Register a new A2A agent")
    agent_register_parser.add_argument(
        "--config",
        required=True,
        help="Path to agent configuration JSON file"
    )

    # Agent list command
    agent_list_parser = subparsers.add_parser("agent-list", help="List all A2A agents")
    agent_list_parser.add_argument(
        "--query",
        help="Search query string"
    )
    agent_list_parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="Show only enabled agents"
    )
    agent_list_parser.add_argument(
        "--visibility",
        choices=["public", "private", "internal"],
        help="Filter by visibility level"
    )

    # Agent get command
    agent_get_parser = subparsers.add_parser("agent-get", help="Get agent details")
    agent_get_parser.add_argument(
        "--path",
        required=True,
        help="Agent path (e.g., /code-reviewer)"
    )

    # Agent update command
    agent_update_parser = subparsers.add_parser("agent-update", help="Update an existing agent")
    agent_update_parser.add_argument(
        "--path",
        required=True,
        help="Agent path"
    )
    agent_update_parser.add_argument(
        "--config",
        required=True,
        help="Path to updated agent configuration JSON file"
    )

    # Agent delete command
    agent_delete_parser = subparsers.add_parser("agent-delete", help="Delete an agent")
    agent_delete_parser.add_argument(
        "--path",
        required=True,
        help="Agent path"
    )
    agent_delete_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )

    # Agent toggle command
    agent_toggle_parser = subparsers.add_parser("agent-toggle", help="Toggle agent enabled/disabled status")
    agent_toggle_parser.add_argument(
        "--path",
        required=True,
        help="Agent path"
    )
    agent_toggle_parser.add_argument(
        "--enabled",
        required=True,
        type=lambda x: x.lower() == 'true',
        help="True to enable, false to disable"
    )

    # Agent discover command
    agent_discover_parser = subparsers.add_parser("agent-discover", help="Discover agents by skills")
    agent_discover_parser.add_argument(
        "--skills",
        required=True,
        help="Comma-separated list of required skills"
    )
    agent_discover_parser.add_argument(
        "--tags",
        help="Comma-separated list of tag filters"
    )
    agent_discover_parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)"
    )

    # Agent search command
    agent_search_parser = subparsers.add_parser("agent-search", help="Semantic search for agents")
    agent_search_parser.add_argument(
        "--query",
        required=True,
        help="Natural language search query"
    )
    agent_search_parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)"
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
        "list-groups": cmd_list_groups,
        "agent-register": cmd_agent_register,
        "agent-list": cmd_agent_list,
        "agent-get": cmd_agent_get,
        "agent-update": cmd_agent_update,
        "agent-delete": cmd_agent_delete,
        "agent-toggle": cmd_agent_toggle,
        "agent-discover": cmd_agent_discover,
        "agent-search": cmd_agent_search
    }

    handler = command_handlers.get(args.command)
    if not handler:
        logger.error(f"Unknown command: {args.command}")
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
