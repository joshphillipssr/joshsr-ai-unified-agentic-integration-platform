#!/usr/bin/env python3
"""
MCP Gateway Registry Client - Standalone Pydantic-based client for the Registry API.

This client provides a type-safe interface to the MCP Gateway Registry API endpoints
documented in /home/ubuntu/repos/mcp-gateway-registry/docs/api-specs/server-management.yaml.

Authentication is handled via JWT tokens retrieved from AWS SSM Parameter Store using
the get-m2m-token.sh script.
"""

import logging
import subprocess
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

import requests
from pydantic import BaseModel, Field, HttpUrl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration for servers."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServiceRegistration(BaseModel):
    """Service registration request model (UI-based registration)."""

    name: str = Field(..., description="Service name")
    description: str = Field(..., description="Service description")
    path: str = Field(..., description="Service path")
    proxy_pass_url: str = Field(..., description="Proxy pass URL")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    num_tools: Optional[int] = Field(None, description="Number of tools")
    num_stars: Optional[int] = Field(None, description="Number of stars")
    is_python: Optional[bool] = Field(None, description="Is Python server")
    license: Optional[str] = Field(None, description="License type")


class InternalServiceRegistration(BaseModel):
    """Internal service registration model (Admin/M2M registration)."""

    service_path: str = Field(..., description="Service path (e.g., /cloudflare-docs)")
    name: Optional[str] = Field(None, description="Service name")
    description: Optional[str] = Field(None, description="Service description")
    proxy_pass_url: Optional[str] = Field(None, description="Proxy pass URL")
    auth_provider: Optional[str] = Field(None, description="Authentication provider")
    auth_type: Optional[str] = Field(None, description="Authentication type")
    supported_transports: Optional[List[str]] = Field(None, description="Supported transports")
    headers: Optional[Dict[str, str]] = Field(None, description="Custom headers")
    tool_list_json: Optional[str] = Field(None, description="Tool list as JSON string")
    overwrite: Optional[bool] = Field(False, description="Overwrite if exists")


class Server(BaseModel):
    """Server information model."""

    path: str = Field(..., description="Service path")
    name: str = Field(..., description="Service name")
    description: str = Field(..., description="Service description")
    is_enabled: bool = Field(..., description="Whether service is enabled")
    health_status: HealthStatus = Field(..., description="Health status")


class ServerDetail(BaseModel):
    """Detailed server information model."""

    path: str = Field(..., description="Service path")
    name: str = Field(..., description="Service name")
    description: str = Field(..., description="Service description")
    url: str = Field(..., description="Service URL")
    is_enabled: bool = Field(..., description="Whether service is enabled")
    num_tools: int = Field(..., description="Number of tools")
    health_status: str = Field(..., description="Health status")
    last_health_check: Optional[datetime] = Field(None, description="Last health check timestamp")


class ServerListResponse(BaseModel):
    """Server list response model."""

    servers: List[Server] = Field(..., description="List of servers")


class ServiceResponse(BaseModel):
    """Service operation response model."""

    path: str = Field(..., description="Service path")
    name: str = Field(..., description="Service name")
    message: str = Field(..., description="Response message")


class ToggleResponse(BaseModel):
    """Toggle service response model."""

    path: str = Field(..., description="Service path")
    is_enabled: bool = Field(..., description="Current enabled status")
    message: str = Field(..., description="Response message")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error detail message")
    error_code: Optional[str] = Field(None, description="Error code")
    request_id: Optional[str] = Field(None, description="Request ID")


class GroupListResponse(BaseModel):
    """Group list response model."""

    groups: List[Dict[str, Any]] = Field(..., description="List of groups")


class RegistryClient:
    """
    MCP Gateway Registry API client.

    Provides methods for interacting with the Registry API endpoints including
    server registration, removal, toggling, health checks, and group management.

    Authentication is handled via JWT tokens passed to the constructor.
    """

    def __init__(
        self,
        registry_url: str,
        token: str
    ):
        """
        Initialize the Registry Client.

        Args:
            registry_url: Base URL of the registry (e.g., https://registry.mycorp.click)
            token: JWT access token for authentication
        """
        self.registry_url = registry_url.rstrip('/')
        self._token = token

        # Redact token in logs - show only first 8 characters
        redacted_token = f"{token[:8]}..." if len(token) > 8 else "***"
        logger.info(f"Initialized RegistryClient for {self.registry_url} (token: {redacted_token})")

    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with JWT token.

        Returns:
            Dictionary of HTTP headers
        """
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json"
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """
        Make HTTP request to the Registry API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response object

        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self.registry_url}{endpoint}"
        headers = self._get_headers()

        logger.debug(f"{method} {url}")

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            params=params,
            timeout=30
        )

        response.raise_for_status()
        return response

    def register_service(
        self,
        registration: InternalServiceRegistration
    ) -> ServiceResponse:
        """
        Register a new service in the registry.

        Args:
            registration: Service registration data

        Returns:
            Service response with registration details

        Raises:
            requests.HTTPError: If registration fails
        """
        logger.info(f"Registering service: {registration.service_path}")

        response = self._make_request(
            method="POST",
            endpoint="/api/internal/register",
            data=registration.model_dump(exclude_none=True)
        )

        logger.info(f"Service registered successfully: {registration.service_path}")
        return ServiceResponse(**response.json())

    def remove_service(self, service_path: str) -> Dict[str, Any]:
        """
        Remove a service from the registry.

        Args:
            service_path: Path of service to remove

        Returns:
            Response data

        Raises:
            requests.HTTPError: If removal fails
        """
        logger.info(f"Removing service: {service_path}")

        response = self._make_request(
            method="POST",
            endpoint="/api/internal/remove",
            data={"service_path": service_path}
        )

        logger.info(f"Service removed successfully: {service_path}")
        return response.json()

    def toggle_service(self, service_path: str) -> ToggleResponse:
        """
        Toggle service enabled/disabled status.

        Args:
            service_path: Path of service to toggle

        Returns:
            Toggle response with current status

        Raises:
            requests.HTTPError: If toggle fails
        """
        logger.info(f"Toggling service: {service_path}")

        response = self._make_request(
            method="POST",
            endpoint="/api/internal/toggle",
            data={"service_path": service_path}
        )

        result = ToggleResponse(**response.json())
        logger.info(f"Service toggled: {service_path} -> enabled={result.is_enabled}")
        return result

    def list_services(self) -> ServerListResponse:
        """
        List all services in the registry.

        Returns:
            Server list response

        Raises:
            requests.HTTPError: If list operation fails
        """
        logger.info("Listing all services")

        response = self._make_request(
            method="GET",
            endpoint="/api/internal/list"
        )

        result = ServerListResponse(**response.json())
        logger.info(f"Retrieved {len(result.servers)} services")
        return result

    def healthcheck(self) -> Dict[str, Any]:
        """
        Perform health check on all services.

        Returns:
            Health check response with service statuses

        Raises:
            requests.HTTPError: If health check fails
        """
        logger.info("Performing health check on all services")

        response = self._make_request(
            method="POST",
            endpoint="/api/internal/healthcheck"
        )

        result = response.json()
        logger.info(f"Health check completed: {result.get('status', 'unknown')}")
        return result

    def add_server_to_groups(
        self,
        server_name: str,
        group_names: List[str]
    ) -> Dict[str, Any]:
        """
        Add a server to user groups.

        Args:
            server_name: Name of server
            group_names: List of group names

        Returns:
            Response data

        Raises:
            requests.HTTPError: If operation fails
        """
        logger.info(f"Adding server {server_name} to groups: {group_names}")

        response = self._make_request(
            method="POST",
            endpoint="/api/internal/add-to-groups",
            data={
                "server_name": server_name,
                "group_names": ",".join(group_names)
            }
        )

        logger.info(f"Server added to groups successfully")
        return response.json()

    def remove_server_from_groups(
        self,
        server_name: str,
        group_names: List[str]
    ) -> Dict[str, Any]:
        """
        Remove a server from user groups.

        Args:
            server_name: Name of server
            group_names: List of group names

        Returns:
            Response data

        Raises:
            requests.HTTPError: If operation fails
        """
        logger.info(f"Removing server {server_name} from groups: {group_names}")

        response = self._make_request(
            method="POST",
            endpoint="/api/internal/remove-from-groups",
            data={
                "server_name": server_name,
                "group_names": ",".join(group_names)
            }
        )

        logger.info(f"Server removed from groups successfully")
        return response.json()

    def create_group(
        self,
        group_name: str,
        description: Optional[str] = None,
        create_in_keycloak: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new user group.

        Args:
            group_name: Name of group
            description: Group description
            create_in_keycloak: Whether to create in Keycloak

        Returns:
            Response data

        Raises:
            requests.HTTPError: If creation fails
        """
        logger.info(f"Creating group: {group_name}")

        data = {"group_name": group_name}
        if description:
            data["description"] = description
        if create_in_keycloak:
            data["create_in_keycloak"] = True

        response = self._make_request(
            method="POST",
            endpoint="/api/internal/create-group",
            data=data
        )

        logger.info(f"Group created successfully: {group_name}")
        return response.json()

    def delete_group(
        self,
        group_name: str,
        delete_from_keycloak: bool = False,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Delete a user group.

        Args:
            group_name: Name of group
            delete_from_keycloak: Whether to delete from Keycloak
            force: Force deletion of system groups

        Returns:
            Response data

        Raises:
            requests.HTTPError: If deletion fails
        """
        logger.info(f"Deleting group: {group_name}")

        data = {"group_name": group_name}
        if delete_from_keycloak:
            data["delete_from_keycloak"] = True
        if force:
            data["force"] = True

        response = self._make_request(
            method="POST",
            endpoint="/api/internal/delete-group",
            data=data
        )

        logger.info(f"Group deleted successfully: {group_name}")
        return response.json()

    def list_groups(
        self,
        include_keycloak: bool = True,
        include_scopes: bool = True
    ) -> GroupListResponse:
        """
        List all user groups.

        Args:
            include_keycloak: Include Keycloak information
            include_scopes: Include scope information

        Returns:
            Group list response

        Raises:
            requests.HTTPError: If list operation fails
        """
        logger.info("Listing all groups")

        params = {
            "include_keycloak": str(include_keycloak).lower(),
            "include_scopes": str(include_scopes).lower()
        }

        response = self._make_request(
            method="GET",
            endpoint="/api/internal/list-groups",
            params=params
        )

        result = GroupListResponse(**response.json())
        logger.info(f"Retrieved {len(result.groups)} groups")
        return result
