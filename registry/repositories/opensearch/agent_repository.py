"""OpenSearch-based repository for A2A agent storage."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from opensearchpy import AsyncOpenSearch, NotFoundError

from ...core.config import settings
from ...schemas.agent_models import AgentCard
from ..interfaces import AgentRepositoryBase
from .client import get_opensearch_client, get_index_name

logger = logging.getLogger(__name__)


class OpenSearchAgentRepository(AgentRepositoryBase):
    """OpenSearch implementation of agent repository."""

    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}
        self._state: Dict[str, List[str]] = {"enabled": [], "disabled": []}
        self._client: Optional[AsyncOpenSearch] = None
        self._index_name = get_index_name(settings.opensearch_index_agents)

    async def _get_client(self) -> AsyncOpenSearch:
        """Get OpenSearch client."""
        if self._client is None:
            self._client = await get_opensearch_client()
        return self._client


    def _is_aoss(self) -> bool:
        """Check if using AWS OpenSearch Serverless (which doesn't support custom IDs)."""
        return settings.opensearch_auth_type == "aws_iam"


    def _path_to_doc_id(self, path: str) -> str:
        """Convert path to document ID."""
        return path.replace("/", "_").strip("_")


    async def _wait_for_document_available(
        self,
        path: str,
        max_retries: int = 5,
        initial_delay: float = 0.5
    ) -> bool:
        """Wait for AOSS eventual consistency - retry until document is queryable.

        Args:
            path: Agent path to check
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds (doubles each retry)

        Returns:
            True if document becomes available, False if max retries exceeded
        """
        client = await self._get_client()
        delay = initial_delay

        for attempt in range(max_retries):
            try:
                search_response = await client.search(
                    index=self._index_name,
                    body={"query": {"term": {"path": path}}}
                )

                if search_response['hits']['total']['value'] > 0:
                    logger.info(f"Document for '{path}' available after {attempt + 1} attempts")
                    return True

                logger.debug(f"Document for '{path}' not yet available, retry {attempt + 1}/{max_retries}")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff

            except Exception as e:
                logger.warning(f"Error checking document availability for '{path}': {e}")
                await asyncio.sleep(delay)
                delay *= 2

        logger.error(f"Document for '{path}' not available after {max_retries} retries")
        return False

    async def load_all(self) -> None:
        """Load all agents from OpenSearch."""
        logger.info(f"Loading agents from OpenSearch index: {self._index_name}")
        client = await self._get_client()

        try:
            response = await client.search(
                index=self._index_name,
                body={
                    "query": {"match_all": {}},
                    "size": 10000
                }
            )

            self._agents = {}
            self._state = {"enabled": [], "disabled": []}
            
            for hit in response["hits"]["hits"]:
                agent_data = hit["_source"]
                path = agent_data["path"]
                
                try:
                    agent_card = AgentCard(**agent_data)
                    self._agents[path] = agent_card
                    
                    # Build state from is_enabled field
                    if agent_data.get("is_enabled", False):
                        self._state["enabled"].append(path)
                    else:
                        self._state["disabled"].append(path)
                        
                except Exception as e:
                    logger.error(f"Failed to parse agent {path}: {e}")

            logger.info(f"Loaded {len(self._agents)} agents from OpenSearch")

        except NotFoundError:
            logger.warning(f"Index {self._index_name} not found, starting with empty agents")
            self._agents = {}
            self._state = {"enabled": [], "disabled": []}
        except Exception as e:
            logger.error(f"Error loading agents from OpenSearch: {e}", exc_info=True)
            self._agents = {}
            self._state = {"enabled": [], "disabled": []}

    async def get(self, path: str) -> Optional[AgentCard]:
        """Get agent by path - queries OpenSearch directly."""
        client = await self._get_client()

        try:
            # Query OpenSearch for this specific path
            search_response = await client.search(
                index=self._index_name,
                body={"query": {"term": {"path": path}}}
            )

            if search_response['hits']['total']['value'] > 0:
                agent_data = search_response['hits']['hits'][0]['_source']
                try:
                    return AgentCard(**agent_data)
                except Exception as e:
                    logger.error(f"Failed to parse agent at '{path}': {e}")
                    return None

            # Try alternate path format (with/without trailing slash)
            if path.endswith('/'):
                alternate_path = path.rstrip('/')
            else:
                alternate_path = path + '/'

            search_response = await client.search(
                index=self._index_name,
                body={"query": {"term": {"path": alternate_path}}}
            )

            if search_response['hits']['total']['value'] > 0:
                agent_data = search_response['hits']['hits'][0]['_source']
                try:
                    return AgentCard(**agent_data)
                except Exception as e:
                    logger.error(f"Failed to parse agent at '{alternate_path}': {e}")
                    return None

            return None

        except NotFoundError:
            logger.debug(f"Index {self._index_name} not found when getting agent '{path}'")
            return None
        except Exception as e:
            logger.error(f"Error getting agent '{path}' from OpenSearch: {e}", exc_info=True)
            return None

    async def list_all(self) -> List[AgentCard]:
        """List all agents - queries OpenSearch directly."""
        client = await self._get_client()

        try:
            response = await client.search(
                index=self._index_name,
                body={
                    "query": {"match_all": {}},
                    "size": 10000
                }
            )

            agents = []
            for hit in response["hits"]["hits"]:
                agent_data = hit["_source"]
                try:
                    agent_card = AgentCard(**agent_data)
                    agents.append(agent_card)
                except Exception as e:
                    logger.error(f"Failed to parse agent {agent_data.get('path', 'unknown')}: {e}")

            return agents

        except NotFoundError:
            logger.debug(f"Index {self._index_name} not found when listing agents")
            return []
        except Exception as e:
            logger.error(f"Error listing agents from OpenSearch: {e}", exc_info=True)
            return []

    async def create(self, agent: AgentCard) -> AgentCard:
        """Create a new agent."""
        path = agent.path

        # Check if agent already exists by querying OpenSearch
        existing = await self.get(path)
        if existing:
            logger.error(f"Agent path '{path}' already exists")
            raise ValueError(f"Agent path '{path}' already exists")

        client = await self._get_client()
        doc_id = self._path_to_doc_id(path)

        # Set timestamps
        if not agent.registered_at:
            agent.registered_at = datetime.utcnow()
        if not agent.updated_at:
            agent.updated_at = datetime.utcnow()

        agent_dict = agent.model_dump(mode="json")
        agent_dict["is_enabled"] = False
        agent_dict["path"] = path  # Store path for querying in AOSS

        try:
            if self._is_aoss():
                # OpenSearch Serverless doesn't support custom IDs or refresh=true
                await client.index(
                    index=self._index_name,
                    body=agent_dict
                )

                # Wait for AOSS eventual consistency - document must be queryable before proceeding
                logger.info(f"Waiting for AOSS to index document for '{path}'...")
                if not await self._wait_for_document_available(path):
                    logger.error(f"Document for '{path}' not available after retries")
                    raise ValueError(f"Failed to verify agent creation in OpenSearch")

            else:
                # Regular OpenSearch - use custom ID for backwards compatibility
                await client.index(
                    index=self._index_name,
                    id=doc_id,
                    body=agent_dict,
                    refresh=True
                )

            logger.info(f"Created agent '{agent.name}' at '{path}'")
            return agent

        except Exception as e:
            logger.error(f"Failed to create agent in OpenSearch: {e}", exc_info=True)
            raise ValueError(f"Failed to create agent: {e}")

    async def update(self, path: str, updates: Dict[str, Any]) -> AgentCard:
        """Update an existing agent."""
        # Query for existing agent
        existing_agent = await self.get(path)
        if not existing_agent:
            logger.error(f"Cannot update agent at '{path}': not found")
            raise ValueError(f"Agent not found at path: {path}")

        client = await self._get_client()

        # Merge updates with existing agent
        agent_dict = existing_agent.model_dump()
        agent_dict.update(updates)
        agent_dict["path"] = path
        agent_dict["updated_at"] = datetime.utcnow()

        try:
            updated_agent = AgentCard(**agent_dict)
        except Exception as e:
            logger.error(f"Failed to validate updated agent: {e}")
            raise ValueError(f"Invalid agent update: {e}")

        agent_dict = updated_agent.model_dump(mode="json")

        try:
            # Find existing document by path field
            search_response = await client.search(
                index=self._index_name,
                body={"query": {"term": {"path": path}}}
            )

            if search_response['hits']['total']['value'] == 0:
                raise ValueError(f"Agent at '{path}' not found in OpenSearch")

            # Get the document ID (auto-generated for AOSS, deterministic for regular OpenSearch)
            doc_id = search_response['hits']['hits'][0]['_id']

            # Update using the document ID - use update() for both to ensure consistency
            if self._is_aoss():
                # AOSS doesn't support refresh=true
                await client.update(
                    index=self._index_name,
                    id=doc_id,
                    body={"doc": agent_dict}
                )
            else:
                await client.update(
                    index=self._index_name,
                    id=doc_id,
                    body={"doc": agent_dict},
                    refresh=True
                )

            logger.info(f"Updated agent '{updated_agent.name}' ({path})")
            return updated_agent

        except Exception as e:
            logger.error(f"Failed to update agent in OpenSearch: {e}", exc_info=True)
            raise ValueError(f"Failed to update agent: {e}")

    async def delete(self, path: str) -> bool:
        """Delete an agent."""
        client = await self._get_client()

        try:
            # Find existing document by path field
            search_response = await client.search(
                index=self._index_name,
                body={"query": {"term": {"path": path}}}
            )

            if search_response['hits']['total']['value'] == 0:
                logger.error(f"Agent at '{path}' not found in OpenSearch")
                return False

            # Get the document ID and agent name
            doc_id = search_response['hits']['hits'][0]['_id']
            agent_data = search_response['hits']['hits'][0]['_source']
            agent_name = agent_data.get('name', 'Unknown')

            # Delete using the document ID
            if self._is_aoss():
                # AOSS doesn't support refresh=true
                await client.delete(
                    index=self._index_name,
                    id=doc_id
                )
            else:
                await client.delete(
                    index=self._index_name,
                    id=doc_id,
                    refresh=True
                )

            logger.info(f"Deleted agent '{agent_name}' from '{path}'")
            return True

        except Exception as e:
            logger.error(f"Failed to delete agent from OpenSearch: {e}", exc_info=True)
            return False

    async def get_state(self, path: str = None) -> Dict[str, List[str]] | bool:
        """Get agent state - queries OpenSearch directly if path provided, returns all state otherwise."""
        if path is None:
            # Return all state - query all agents from OpenSearch
            client = await self._get_client()

            try:
                response = await client.search(
                    index=self._index_name,
                    body={
                        "query": {"match_all": {}},
                        "size": 10000
                    }
                )

                state = {"enabled": [], "disabled": []}
                for hit in response["hits"]["hits"]:
                    agent_data = hit["_source"]
                    agent_path = agent_data.get("path")
                    if agent_path:
                        if agent_data.get("is_enabled", False):
                            state["enabled"].append(agent_path)
                        else:
                            state["disabled"].append(agent_path)

                return state

            except Exception as e:
                logger.error(f"Error getting all agent state from OpenSearch: {e}", exc_info=True)
                return {"enabled": [], "disabled": []}

        # Return individual agent state by querying OpenSearch
        agent = await self.get(path)
        if agent:
            return getattr(agent, "is_enabled", False)

        return False

    async def set_state(self, path: str, enabled: bool) -> bool:
        """Set agent enabled/disabled state."""
        client = await self._get_client()

        try:
            # Find existing document by path field
            search_response = await client.search(
                index=self._index_name,
                body={"query": {"term": {"path": path}}}
            )

            if search_response['hits']['total']['value'] == 0:
                logger.error(f"Agent at '{path}' not found in OpenSearch")
                return False

            # Get the document ID and agent data
            doc_id = search_response['hits']['hits'][0]['_id']
            agent_data = search_response['hits']['hits'][0]['_source']
            agent_name = agent_data.get('name', path)

            # Update state in OpenSearch
            update_body = {"doc": {"is_enabled": enabled, "updated_at": datetime.utcnow().isoformat()}}

            if self._is_aoss():
                # AOSS doesn't support refresh=true
                await client.update(
                    index=self._index_name,
                    id=doc_id,
                    body=update_body
                )
            else:
                await client.update(
                    index=self._index_name,
                    id=doc_id,
                    body=update_body,
                    refresh=True
                )

            logger.info(f"Toggled '{agent_name}' ({path}) to {enabled}")
            return True

        except Exception as e:
            logger.error(f"Failed to update agent state in OpenSearch: {e}", exc_info=True)
            return False


    async def save_state(self, state: Dict[str, List[str]]) -> None:
        """Save agent state (compatibility method for file repository interface)."""
        # For OpenSearch, state is managed per-agent via set_state()
        # This method updates internal state cache
        self._state = state
        logger.debug(f"Updated agent state cache: {len(state['enabled'])} enabled, {len(state['disabled'])} disabled")
