"""MCP Gateway Interaction Server (mcpgw).

This MCP server provides tools to interact with the MCP Gateway Registry API.
It acts as a thin protocol adapter, translating MCP tool calls into registry HTTP requests.

All tools require bearer token authentication via the Authorization header.
"""

import logging
from typing import Any

import httpx
from fastmcp import Context, FastMCP

from models import AgentInfo, RegistryStats, ServerInfo, SkillInfo, ToolSearchResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("mcpgw")


def _extract_bearer_token(ctx: Context | None) -> str | None:
    """Extract bearer token from FastMCP context."""
    if not ctx:
        return None

    try:
        if hasattr(ctx, "http_request") and ctx.http_request:
            auth_header = ctx.http_request.headers.get("authorization")
            if auth_header and auth_header.lower().startswith("bearer "):
                return auth_header.split(" ", 1)[1]
    except Exception as e:
        logger.warning(f"Failed to extract token: {e}")

    return None


@mcp.tool()
async def list_services(
    registry_url: str = "http://localhost", ctx: Context | None = None
) -> dict[str, Any]:
    """
    List all MCP servers registered in the gateway.

    Args:
        registry_url: Base URL of the registry (default: http://localhost)

    Returns:
        Dictionary containing services, total_count, enabled_count, and status
    """
    logger.info(f"list_services called with registry_url: {registry_url}")

    try:
        token = _extract_bearer_token(ctx)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{registry_url}/api/servers", headers=headers
            )
            response.raise_for_status()
            data = response.json()

        # Parse response
        if isinstance(data, dict) and "services" in data:
            servers = data["services"]
        elif isinstance(data, list):
            servers = data
        else:
            servers = []

        services = [ServerInfo(**s).model_dump() for s in servers]
        enabled_count = sum(1 for s in services if s.get("enabled"))

        return {
            "services": services,
            "total_count": len(services),
            "enabled_count": enabled_count,
            "status": "success",
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code}")
        return {
            "services": [],
            "total_count": 0,
            "error": f"Registry API error: {e.response.status_code}",
            "status": "failed",
        }
    except Exception as e:
        logger.error(f"Failed to list services: {e}")
        return {
            "services": [],
            "total_count": 0,
            "error": str(e),
            "status": "failed",
        }


@mcp.tool()
async def list_agents(
    registry_url: str = "http://localhost", ctx: Context | None = None
) -> dict[str, Any]:
    """
    List all agents registered in the gateway.

    Args:
        registry_url: Base URL of the registry (default: http://localhost)

    Returns:
        Dictionary containing agents, total_count, and status
    """
    logger.info(f"list_agents called with registry_url: {registry_url}")

    try:
        token = _extract_bearer_token(ctx)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{registry_url}/api/agents", headers=headers)
            response.raise_for_status()
            data = response.json()

        agents = data.get("agents", []) if isinstance(data, dict) else data
        agent_list = [AgentInfo(**a).model_dump() for a in agents]

        return {
            "agents": agent_list,
            "total_count": len(agent_list),
            "status": "success",
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code}")
        return {
            "agents": [],
            "total_count": 0,
            "error": f"Registry API error: {e.response.status_code}",
            "status": "failed",
        }
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        return {
            "agents": [],
            "total_count": 0,
            "error": str(e),
            "status": "failed",
        }


@mcp.tool()
async def list_skills(
    registry_url: str = "http://localhost", ctx: Context | None = None
) -> dict[str, Any]:
    """
    List all skills registered in the gateway.

    Args:
        registry_url: Base URL of the registry (default: http://localhost)

    Returns:
        Dictionary containing skills, total_count, and status
    """
    logger.info(f"list_skills called with registry_url: {registry_url}")

    try:
        token = _extract_bearer_token(ctx)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{registry_url}/api/skills", headers=headers)
            response.raise_for_status()
            data = response.json()

        skills = data.get("skills", []) if isinstance(data, dict) else data
        skill_list = [SkillInfo(**s).model_dump() for s in skills]

        return {
            "skills": skill_list,
            "total_count": len(skill_list),
            "status": "success",
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code}")
        return {
            "skills": [],
            "total_count": 0,
            "error": f"Registry API error: {e.response.status_code}",
            "status": "failed",
        }
    except Exception as e:
        logger.error(f"Failed to list skills: {e}")
        return {
            "skills": [],
            "total_count": 0,
            "error": str(e),
            "status": "failed",
        }


@mcp.tool()
async def intelligent_tool_finder(
    query: str,
    top_n: int = 5,
    registry_url: str = "http://localhost",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Search for tools using natural language semantic search.

    Args:
        query: Natural language description of what you want to do
        top_n: Number of results to return (default: 5)
        registry_url: Base URL of the registry (default: http://localhost)

    Returns:
        Dictionary containing results, query, total_results, and status
    """
    logger.info(f"intelligent_tool_finder called: query={query}, registry_url={registry_url}")

    try:
        token = _extract_bearer_token(ctx)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{registry_url}/api/search/semantic",
                headers=headers,
                json={"query": query, "entity_type": "tool", "top_k": top_n},
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", []) if isinstance(data, dict) else data
        result_list = [ToolSearchResult(**r).model_dump() for r in results]

        return {
            "results": result_list,
            "query": query,
            "total_results": len(result_list),
            "status": "success",
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code}")
        return {
            "results": [],
            "query": query,
            "total_results": 0,
            "error": f"Registry API error: {e.response.status_code}",
            "status": "failed",
        }
    except Exception as e:
        logger.error(f"Failed to search tools: {e}")
        return {
            "results": [],
            "query": query,
            "total_results": 0,
            "error": str(e),
            "status": "failed",
        }


@mcp.tool()
async def healthcheck(
    registry_url: str = "http://localhost", ctx: Context | None = None
) -> dict[str, Any]:
    """
    Get registry health status and statistics.

    Args:
        registry_url: Base URL of the registry (default: http://localhost)

    Returns:
        Dictionary containing health stats and status
    """
    logger.info(f"healthcheck called with registry_url: {registry_url}")

    try:
        token = _extract_bearer_token(ctx)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{registry_url}/api/servers/health", headers=headers
            )
            response.raise_for_status()
            data = response.json()

        stats = RegistryStats(**data)
        return {**stats.model_dump(), "status": "success"}

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code}")
        return {
            "health_status": "error",
            "error": f"Registry API error: {e.response.status_code}",
            "status": "failed",
        }
    except Exception as e:
        logger.error(f"Failed to get health status: {e}")
        return {
            "health_status": "error",
            "error": str(e),
            "status": "failed",
        }


if __name__ == "__main__":
    import os

    logger.info("Starting mcpgw server")
    logger.info("All tools accept registry_url parameter (default: http://localhost)")

    # Use HTTP transport if PORT is set (Docker container), otherwise stdio
    port = os.environ.get("PORT")
    if port:
        logger.info(f"Running in HTTP mode on 0.0.0.0:{port}")
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(port))
    else:
        logger.info("Running in stdio mode")
        mcp.run(transport="stdio")
