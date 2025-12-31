"""DocumentDB-based repository for hybrid search (text + vector)."""

import logging
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorCollection

from ...core.config import embedding_config, settings
from ...schemas.agent_models import AgentCard
from ..interfaces import SearchRepositoryBase
from .client import get_collection_name, get_documentdb_client


logger = logging.getLogger(__name__)


class DocumentDBSearchRepository(SearchRepositoryBase):
    """DocumentDB implementation with hybrid search (text + vector)."""

    def __init__(self):
        self._collection: Optional[AsyncIOMotorCollection] = None
        self._collection_name = get_collection_name(
            f"mcp_embeddings_{settings.embeddings_model_dimensions}"
        )
        self._embedding_model = None


    async def _get_collection(self) -> AsyncIOMotorCollection:
        """Get DocumentDB collection."""
        if self._collection is None:
            db = await get_documentdb_client()
            self._collection = db[self._collection_name]
        return self._collection


    async def _get_embedding_model(self):
        """Lazy load embedding model."""
        if self._embedding_model is None:
            from ...embeddings import create_embeddings_client

            self._embedding_model = create_embeddings_client(
                provider=settings.embeddings_provider,
                model_name=settings.embeddings_model_name,
                model_dir=settings.embeddings_model_dir,
                api_key=settings.embeddings_api_key,
                api_base=settings.embeddings_api_base,
                aws_region=settings.embeddings_aws_region,
                embedding_dimension=settings.embeddings_model_dimensions,
            )
        return self._embedding_model


    async def initialize(self) -> None:
        """Initialize the search service and create vector index."""
        logger.info(
            f"Initializing DocumentDB hybrid search on collection: {self._collection_name}"
        )
        collection = await self._get_collection()

        try:
            indexes = await collection.list_indexes().to_list(length=100)
            index_names = [idx["name"] for idx in indexes]

            if "embedding_vector_idx" not in index_names:
                logger.info("Creating HNSW vector index for embeddings...")
                await collection.create_index(
                    [("embedding", "vector")],
                    name="embedding_vector_idx",
                    vectorOptions={
                        "type": "hnsw",
                        "similarity": "cosine",
                        "dimensions": settings.embeddings_model_dimensions,
                        "m": 16,
                        "efConstruction": 128
                    }
                )
                logger.info("Created HNSW vector index")
            else:
                logger.info("Vector index already exists")

            if "path_idx" not in index_names:
                await collection.create_index([("path", 1)], name="path_idx", unique=True)
                logger.info("Created path index")

        except Exception as e:
            logger.error(f"Failed to initialize search indexes: {e}", exc_info=True)


    async def index_server(
        self,
        path: str,
        server_info: Dict[str, Any],
        is_enabled: bool = False,
    ) -> None:
        """Index a server for search."""
        collection = await self._get_collection()

        text_parts = [
            server_info.get("server_name", ""),
            server_info.get("description", ""),
        ]

        tags = server_info.get("tags", [])
        if tags:
            text_parts.append("Tags: " + ", ".join(tags))

        for tool in server_info.get("tool_list", []):
            text_parts.append(tool.get("name", ""))
            text_parts.append(tool.get("description", ""))

        text_for_embedding = " ".join(filter(None, text_parts))

        model = await self._get_embedding_model()
        embedding = model.encode([text_for_embedding])[0].tolist()

        doc = {
            "_id": path,
            "entity_type": "mcp_server",
            "path": path,
            "name": server_info.get("server_name", ""),
            "description": server_info.get("description", ""),
            "tags": server_info.get("tags", []),
            "is_enabled": is_enabled,
            "text_for_embedding": text_for_embedding,
            "embedding": embedding,
            "embedding_metadata": embedding_config.get_embedding_metadata(),
            "tools": [
                {"name": t.get("name"), "description": t.get("description")}
                for t in server_info.get("tool_list", [])
            ],
            "metadata": server_info,
            "indexed_at": server_info.get("updated_at", server_info.get("registered_at"))
        }

        try:
            await collection.replace_one(
                {"_id": path},
                doc,
                upsert=True
            )
            logger.info(f"Indexed server '{server_info.get('server_name')}' for search")
        except Exception as e:
            logger.error(f"Failed to index server in search: {e}", exc_info=True)


    async def index_agent(
        self,
        path: str,
        agent_card: AgentCard,
        is_enabled: bool = False,
    ) -> None:
        """Index an agent for search."""
        collection = await self._get_collection()

        text_parts = [
            agent_card.name,
            agent_card.description or "",
        ]

        tags = agent_card.tags or []
        if tags:
            text_parts.append("Tags: " + ", ".join(tags))

        if agent_card.capabilities:
            text_parts.append("Capabilities: " + ", ".join(agent_card.capabilities))

        text_for_embedding = " ".join(filter(None, text_parts))

        model = await self._get_embedding_model()
        embedding = model.encode([text_for_embedding])[0].tolist()

        doc = {
            "_id": path,
            "entity_type": "a2a_agent",
            "path": path,
            "name": agent_card.name,
            "description": agent_card.description or "",
            "tags": agent_card.tags or [],
            "is_enabled": is_enabled,
            "text_for_embedding": text_for_embedding,
            "embedding": embedding,
            "embedding_metadata": embedding_config.get_embedding_metadata(),
            "capabilities": agent_card.capabilities or [],
            "metadata": agent_card.model_dump(mode="json"),
            "indexed_at": agent_card.updated_at or agent_card.registered_at
        }

        try:
            await collection.replace_one(
                {"_id": path},
                doc,
                upsert=True
            )
            logger.info(f"Indexed agent '{agent_card.name}' for search")
        except Exception as e:
            logger.error(f"Failed to index agent in search: {e}", exc_info=True)


    async def remove_entity(
        self,
        path: str,
    ) -> None:
        """Remove entity from search index."""
        collection = await self._get_collection()

        try:
            result = await collection.delete_one({"_id": path})
            if result.deleted_count > 0:
                logger.info(f"Removed entity '{path}' from search index")
            else:
                logger.warning(f"Entity '{path}' not found in search index")
        except Exception as e:
            logger.error(f"Failed to remove entity from search index: {e}", exc_info=True)


    async def search(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        max_results: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Perform hybrid search (text + vector)."""
        collection = await self._get_collection()

        try:
            model = await self._get_embedding_model()
            query_embedding = model.encode([query])[0].tolist()

            pipeline = [
                {
                    "$vectorSearch": {
                        "queryVector": query_embedding,
                        "path": "embedding",
                        "numCandidates": max_results * 10,
                        "limit": max_results * 2,
                        "index": "embedding_vector_idx"
                    }
                },
                {
                    "$addFields": {
                        "vector_score": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$match": {
                        "$or": [
                            {"name": {"$regex": query, "$options": "i"}},
                            {"description": {"$regex": query, "$options": "i"}},
                            {"tags": {"$in": [query]}}
                        ]
                    }
                },
                {
                    "$addFields": {
                        "text_score": {
                            "$add": [
                                {
                                    "$cond": [
                                        {
                                            "$regexMatch": {
                                                "input": "$name",
                                                "regex": query,
                                                "options": "i"
                                            }
                                        },
                                        3.0,
                                        0.0
                                    ]
                                },
                                {
                                    "$cond": [
                                        {
                                            "$regexMatch": {
                                                "input": "$description",
                                                "regex": query,
                                                "options": "i"
                                            }
                                        },
                                        2.0,
                                        0.0
                                    ]
                                }
                            ]
                        }
                    }
                },
                {
                    "$addFields": {
                        "combined_score": {
                            "$add": [
                                {"$multiply": ["$vector_score", 0.6]},
                                {"$multiply": ["$text_score", 0.4]}
                            ]
                        }
                    }
                },
                {"$sort": {"combined_score": -1}},
                {"$limit": max_results}
            ]

            if entity_types:
                pipeline.insert(1, {"$match": {"entity_type": {"$in": entity_types}}})

            cursor = collection.aggregate(pipeline)
            results = await cursor.to_list(length=max_results)

            grouped_results = {"mcp_servers": [], "a2a_agents": []}
            for doc in results:
                entity_type = doc.get("entity_type")
                result_entry = {
                    "path": doc.get("path"),
                    "name": doc.get("name"),
                    "description": doc.get("description"),
                    "tags": doc.get("tags", []),
                    "is_enabled": doc.get("is_enabled", False),
                    "score": doc.get("combined_score", 0.0),
                    "metadata": doc.get("metadata", {})
                }

                if entity_type == "mcp_server":
                    grouped_results["mcp_servers"].append(result_entry)
                elif entity_type == "a2a_agent":
                    grouped_results["a2a_agents"].append(result_entry)

            logger.info(
                f"Hybrid search for '{query}' returned "
                f"{len(grouped_results['mcp_servers'])} servers, "
                f"{len(grouped_results['a2a_agents'])} agents"
            )

            return grouped_results

        except Exception as e:
            logger.error(f"Failed to perform hybrid search: {e}", exc_info=True)
            return {"mcp_servers": [], "a2a_agents": []}
