"""OpenSearch-based repository for MCP server storage."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from opensearchpy import AsyncOpenSearch, NotFoundError

from ...core.config import settings
from ..interfaces import ServerRepositoryBase
from .client import get_opensearch_client, get_index_name

logger = logging.getLogger(__name__)


class OpenSearchServerRepository(ServerRepositoryBase):
    """OpenSearch implementation of server repository."""

    def __init__(self):
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._client: Optional[AsyncOpenSearch] = None
        self._index_name = get_index_name(settings.opensearch_index_servers)

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
            path: Server path to check
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
        """Load all servers from OpenSearch."""
        logger.info(f"Loading servers from OpenSearch index: {self._index_name}")
        client = await self._get_client()

        try:
            response = await client.search(
                index=self._index_name,
                body={
                    "query": {"match_all": {}},
                    "size": 10000
                }
            )

            self._servers = {}
            for hit in response["hits"]["hits"]:
                server_info = hit["_source"]
                path = server_info["path"]
                self._servers[path] = server_info

            logger.info(f"Loaded {len(self._servers)} servers from OpenSearch")

        except NotFoundError:
            logger.warning(f"Index {self._index_name} not found, starting with empty servers")
            self._servers = {}
        except Exception as e:
            logger.error(f"Error loading servers from OpenSearch: {e}", exc_info=True)
            self._servers = {}

    async def get(self, path: str) -> Optional[Dict[str, Any]]:
        """Get server by path - queries OpenSearch directly."""
        client = await self._get_client()

        try:
            # Query OpenSearch for this specific path
            search_response = await client.search(
                index=self._index_name,
                body={"query": {"term": {"path": path}}}
            )

            if search_response['hits']['total']['value'] > 0:
                return search_response['hits']['hits'][0]['_source']

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
                return search_response['hits']['hits'][0]['_source']

            return None

        except NotFoundError:
            logger.debug(f"Index {self._index_name} not found when getting server '{path}'")
            return None
        except Exception as e:
            logger.error(f"Error getting server '{path}' from OpenSearch: {e}", exc_info=True)
            return None

    async def list_all(self) -> Dict[str, Dict[str, Any]]:
        """List all servers - queries OpenSearch directly."""
        client = await self._get_client()

        try:
            response = await client.search(
                index=self._index_name,
                body={
                    "query": {"match_all": {}},
                    "size": 10000
                }
            )

            servers = {}
            for hit in response["hits"]["hits"]:
                server_info = hit["_source"]
                path = server_info["path"]
                servers[path] = server_info

            return servers

        except NotFoundError:
            logger.debug(f"Index {self._index_name} not found when listing servers")
            return {}
        except Exception as e:
            logger.error(f"Error listing servers from OpenSearch: {e}", exc_info=True)
            return {}

    async def create(self, server_info: Dict[str, Any]) -> bool:
        """Create a new server."""
        path = server_info["path"]

        # Check if server already exists by querying OpenSearch
        existing = await self.get(path)
        if existing:
            logger.error(f"Server path '{path}' already exists")
            return False

        client = await self._get_client()
        doc_id = self._path_to_doc_id(path)

        server_info["registered_at"] = datetime.utcnow().isoformat()
        server_info["updated_at"] = datetime.utcnow().isoformat()
        server_info.setdefault("is_enabled", False)
        server_info["path"] = path  # Store path in document for querying

        try:
            if self._is_aoss():
                # OpenSearch Serverless doesn't support custom IDs or refresh=true
                await client.index(
                    index=self._index_name,
                    body=server_info
                )

                # Wait for AOSS eventual consistency - document must be queryable before proceeding
                logger.info(f"Waiting for AOSS to index document for '{path}'...")
                if not await self._wait_for_document_available(path):
                    logger.error(f"Document for '{path}' not available after retries")
                    return False

            else:
                # Regular OpenSearch - use custom ID for backwards compatibility
                await client.index(
                    index=self._index_name,
                    id=doc_id,
                    body=server_info,
                    refresh=True
                )

            logger.info(f"Created server '{server_info['server_name']}' at '{path}'")
            return True

        except Exception as e:
            logger.error(f"Failed to create server in OpenSearch: {e}", exc_info=True)
            return False

    async def update(self, path: str, server_info: Dict[str, Any]) -> bool:
        """Update an existing server."""
        client = await self._get_client()

        server_info["path"] = path
        server_info["updated_at"] = datetime.utcnow().isoformat()

        try:
            # Find existing document by path field
            search_response = await client.search(
                index=self._index_name,
                body={"query": {"term": {"path": path}}}
            )

            if search_response['hits']['total']['value'] == 0:
                logger.error(f"Server at '{path}' not found in OpenSearch")
                return False

            # Get the document ID (auto-generated for AOSS, deterministic for regular OpenSearch)
            doc_id = search_response['hits']['hits'][0]['_id']

            # Update using the document ID
            if self._is_aoss():
                # AOSS doesn't support refresh=true
                await client.update(
                    index=self._index_name,
                    id=doc_id,
                    body={"doc": server_info}
                )
            else:
                await client.update(
                    index=self._index_name,
                    id=doc_id,
                    body={"doc": server_info},
                    refresh=True
                )

            logger.info(f"Updated server '{server_info['server_name']}' ({path})")
            return True

        except Exception as e:
            logger.error(f"Failed to update server in OpenSearch: {e}", exc_info=True)
            return False

    async def delete(self, path: str) -> bool:
        """Delete a server."""
        client = await self._get_client()

        try:
            # Find existing document by path field
            search_response = await client.search(
                index=self._index_name,
                body={"query": {"term": {"path": path}}}
            )

            if search_response['hits']['total']['value'] == 0:
                logger.error(f"Server at '{path}' not found in OpenSearch")
                return False

            # Get the document ID and server name
            doc_id = search_response['hits']['hits'][0]['_id']
            server_name = search_response['hits']['hits'][0]['_source'].get('server_name', 'Unknown')

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

            logger.info(f"Deleted server '{server_name}' from '{path}'")
            return True

        except Exception as e:
            logger.error(f"Failed to delete server from OpenSearch: {e}", exc_info=True)
            return False

    async def get_state(self, path: str) -> bool:
        """Get server enabled/disabled state."""
        server_info = await self.get(path)
        if server_info:
            return server_info.get("is_enabled", False)
        return False

    async def set_state(self, path: str, enabled: bool) -> bool:
        """Set server enabled/disabled state."""
        client = await self._get_client()

        try:
            # Find document by path field
            search_response = await client.search(
                index=self._index_name,
                body={"query": {"term": {"path": path}}}
            )

            if search_response['hits']['total']['value'] == 0:
                logger.error(f"Server at '{path}' not found in OpenSearch")
                return False

            # Get the document ID and server data
            doc_id = search_response['hits']['hits'][0]['_id']
            server_data = search_response['hits']['hits'][0]['_source']
            server_name = server_data.get('server_name', path)

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

            logger.info(f"Toggled '{server_name}' ({path}) to {enabled}")
            return True

        except Exception as e:
            logger.error(f"Failed to update server state in OpenSearch: {e}", exc_info=True)
            return False
