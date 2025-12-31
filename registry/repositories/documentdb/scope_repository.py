"""DocumentDB-based repository for authorization scopes storage."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorCollection

from ..interfaces import ScopeRepositoryBase
from .client import get_collection_name, get_documentdb_client


logger = logging.getLogger(__name__)


class DocumentDBScopeRepository(ScopeRepositoryBase):
    """DocumentDB implementation of scope repository using embedded documents."""

    def __init__(self):
        self._collection: Optional[AsyncIOMotorCollection] = None
        self._collection_name = get_collection_name("mcp_scopes")
        self._scopes_cache: Dict[str, Any] = {}


    async def _get_collection(self) -> AsyncIOMotorCollection:
        """Get DocumentDB collection."""
        if self._collection is None:
            db = await get_documentdb_client()
            self._collection = db[self._collection_name]
        return self._collection


    async def load_all(self) -> None:
        """Load all scopes from DocumentDB."""
        logger.info(f"Loading scopes from DocumentDB collection: {self._collection_name}")
        collection = await self._get_collection()

        try:
            cursor = collection.find({})
            self._scopes_cache = {
                "UI-Scopes": {},
                "group_mappings": {},
            }

            async for doc in cursor:
                group_name = doc.get("_id")
                scope_type = doc.get("scope_type", "group")

                if scope_type == "group":
                    if doc.get("ui_permissions"):
                        self._scopes_cache["UI-Scopes"][group_name] = doc.get("ui_permissions", {})
                    if doc.get("group_mappings"):
                        self._scopes_cache["group_mappings"][group_name] = doc.get("group_mappings", [])
                    if doc.get("server_access"):
                        for scope_entry in doc.get("server_access", []):
                            scope_name = scope_entry.get("scope_name")
                            if scope_name:
                                if scope_name not in self._scopes_cache:
                                    self._scopes_cache[scope_name] = []
                                self._scopes_cache[scope_name].extend(
                                    scope_entry.get("access_rules", [])
                                )

            logger.info(f"Loaded scopes from DocumentDB")
        except Exception as e:
            logger.error(f"Error loading scopes from DocumentDB: {e}", exc_info=True)
            self._scopes_cache = {"UI-Scopes": {}, "group_mappings": {}}


    async def get_ui_scopes(
        self,
        group_name: str,
    ) -> Dict[str, Any]:
        """Get UI scopes for a Keycloak group."""
        ui_scopes = self._scopes_cache.get("UI-Scopes", {})
        return ui_scopes.get(group_name, {})


    async def get_group_mappings(
        self,
        keycloak_group: str,
    ) -> List[str]:
        """Get scope names mapped to a Keycloak group."""
        group_mappings = self._scopes_cache.get("group_mappings", {})
        return group_mappings.get(keycloak_group, [])


    async def get_server_scopes(
        self,
        scope_name: str,
    ) -> List[Dict[str, Any]]:
        """Get server access rules for a scope."""
        return self._scopes_cache.get(scope_name, [])


    async def add_server_scope(
        self,
        server_path: str,
        scope_name: str,
        methods: List[str],
        tools: Optional[List[str]] = None,
    ) -> bool:
        """Add scope for a server."""
        try:
            collection = await self._get_collection()
            server_name = server_path.lstrip("/")

            server_entry = {
                "server": server_name,
                "methods": methods,
                "tools": tools
            }

            result = await collection.update_many(
                {},
                {
                    "$push": {
                        "server_access": {
                            "$each": [{
                                "scope_name": scope_name,
                                "access_rules": [server_entry]
                            }]
                        }
                    },
                    "$set": {
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            self._scopes_cache.setdefault(scope_name, []).append(server_entry)

            logger.info(f"Added server '{server_name}' to scope '{scope_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to add server scope in DocumentDB: {e}", exc_info=True)
            return False


    async def remove_server_scope(
        self,
        server_path: str,
        scope_name: str,
    ) -> bool:
        """Remove scope for a server."""
        try:
            collection = await self._get_collection()
            server_name = server_path.lstrip("/")

            result = await collection.update_many(
                {},
                {
                    "$pull": {
                        "server_access": {
                            "scope_name": scope_name,
                            "access_rules.server": server_name
                        }
                    },
                    "$set": {
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if scope_name in self._scopes_cache:
                self._scopes_cache[scope_name] = [
                    s for s in self._scopes_cache[scope_name]
                    if s.get("server") != server_name
                ]

            logger.info(f"Removed server '{server_name}' from scope '{scope_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to remove server scope in DocumentDB: {e}", exc_info=True)
            return False


    async def create_group(
        self,
        group_name: str,
        description: str = "",
    ) -> bool:
        """Create a new group in scopes."""
        try:
            collection = await self._get_collection()

            doc = {
                "_id": group_name,
                "scope_type": "group",
                "description": description,
                "server_access": [],
                "group_mappings": [],
                "ui_permissions": {},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            await collection.insert_one(doc)

            self._scopes_cache.setdefault("UI-Scopes", {})[group_name] = {}
            self._scopes_cache.setdefault("group_mappings", {})[group_name] = []

            logger.info(f"Created group '{group_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to create group in DocumentDB: {e}", exc_info=True)
            return False


    async def delete_group(
        self,
        group_name: str,
        remove_from_mappings: bool = True,
    ) -> bool:
        """Delete a group from scopes."""
        try:
            collection = await self._get_collection()

            result = await collection.delete_one({"_id": group_name})

            if result.deleted_count == 0:
                logger.error(f"Group '{group_name}' not found")
                return False

            self._scopes_cache.get("UI-Scopes", {}).pop(group_name, None)
            self._scopes_cache.get("group_mappings", {}).pop(group_name, None)

            logger.info(f"Deleted group '{group_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete group in DocumentDB: {e}", exc_info=True)
            return False


    async def get_group(
        self,
        group_name: str,
    ) -> Dict[str, Any]:
        """Get full details of a specific group."""
        collection = await self._get_collection()

        try:
            group_doc = await collection.find_one({"_id": group_name})
            if not group_doc:
                return None

            group_doc["scope_name"] = group_doc.pop("_id")
            return group_doc
        except Exception as e:
            logger.error(f"Error getting group '{group_name}' from DocumentDB: {e}", exc_info=True)
            return None


    async def list_groups(self) -> Dict[str, Any]:
        """List all groups with server counts."""
        collection = await self._get_collection()

        try:
            cursor = collection.find({})
            groups = {}
            async for doc in cursor:
                group_name = doc.get("_id")
                server_count = len(doc.get("server_access", []))
                groups[group_name] = {
                    "server_count": server_count,
                    "ui_scopes": doc.get("ui_permissions", {}),
                    "mappings": doc.get("group_mappings", [])
                }
            return groups
        except Exception as e:
            logger.error(f"Error listing groups from DocumentDB: {e}", exc_info=True)
            return {}


    async def group_exists(
        self,
        group_name: str,
    ) -> bool:
        """Check if a group exists."""
        collection = await self._get_collection()

        try:
            count = await collection.count_documents({"_id": group_name})
            return count > 0
        except Exception as e:
            logger.error(f"Error checking group existence in DocumentDB: {e}", exc_info=True)
            return False


    async def add_server_to_ui_scopes(
        self,
        group_name: str,
        server_name: str,
    ) -> bool:
        """Add server to group's UI scopes list_service."""
        try:
            collection = await self._get_collection()

            result = await collection.update_one(
                {"_id": group_name},
                {
                    "$addToSet": {
                        "ui_permissions.list_service": server_name
                    },
                    "$set": {
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.matched_count == 0:
                logger.error(f"Group '{group_name}' not found")
                return False

            logger.info(f"Added server '{server_name}' to UI scopes for group '{group_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to add server to UI scopes in DocumentDB: {e}", exc_info=True)
            return False


    async def remove_server_from_ui_scopes(
        self,
        group_name: str,
        server_name: str,
    ) -> bool:
        """Remove server from group's UI scopes list_service."""
        try:
            collection = await self._get_collection()

            result = await collection.update_one(
                {"_id": group_name},
                {
                    "$pull": {
                        "ui_permissions.list_service": server_name
                    },
                    "$set": {
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.matched_count == 0:
                logger.error(f"Group '{group_name}' not found")
                return False

            logger.info(f"Removed server '{server_name}' from UI scopes for group '{group_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to remove server from UI scopes in DocumentDB: {e}", exc_info=True)
            return False


    async def add_group_mapping(
        self,
        group_name: str,
        scope_name: str,
    ) -> bool:
        """Add a scope to group mappings."""
        try:
            collection = await self._get_collection()

            result = await collection.update_one(
                {"_id": group_name},
                {
                    "$addToSet": {
                        "group_mappings": scope_name
                    },
                    "$set": {
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.matched_count == 0:
                logger.error(f"Group '{group_name}' not found")
                return False

            logger.info(f"Added mapping '{scope_name}' to group '{group_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to add group mapping in DocumentDB: {e}", exc_info=True)
            return False


    async def remove_group_mapping(
        self,
        group_name: str,
        scope_name: str,
    ) -> bool:
        """Remove a scope from group mappings."""
        try:
            collection = await self._get_collection()

            result = await collection.update_one(
                {"_id": group_name},
                {
                    "$pull": {
                        "group_mappings": scope_name
                    },
                    "$set": {
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.matched_count == 0:
                logger.error(f"Group '{group_name}' not found")
                return False

            logger.info(f"Removed mapping '{scope_name}' from group '{group_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to remove group mapping in DocumentDB: {e}", exc_info=True)
            return False


    async def get_all_group_mappings(self) -> Dict[str, List[str]]:
        """Get all group mappings."""
        collection = await self._get_collection()

        try:
            cursor = collection.find({})
            mappings = {}
            async for doc in cursor:
                group_name = doc.get("_id")
                mappings[group_name] = doc.get("group_mappings", [])
            return mappings
        except Exception as e:
            logger.error(f"Error getting all group mappings from DocumentDB: {e}", exc_info=True)
            return {}


    async def add_server_to_multiple_scopes(
        self,
        server_path: str,
        scope_names: List[str],
        methods: List[str],
        tools: List[str],
    ) -> bool:
        """Add server to multiple scopes at once."""
        try:
            for scope_name in scope_names:
                success = await self.add_server_scope(
                    server_path,
                    scope_name,
                    methods,
                    tools
                )
                if not success:
                    return False
            return True
        except Exception as e:
            logger.error(f"Failed to add server to multiple scopes: {e}", exc_info=True)
            return False


    async def remove_server_from_all_scopes(
        self,
        server_path: str,
    ) -> bool:
        """Remove server from all scopes."""
        try:
            collection = await self._get_collection()
            server_name = server_path.lstrip("/")

            result = await collection.update_many(
                {},
                {
                    "$pull": {
                        "server_access": {
                            "access_rules.server": server_name
                        }
                    },
                    "$set": {
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            for scope_name in list(self._scopes_cache.keys()):
                if scope_name not in ["UI-Scopes", "group_mappings"]:
                    self._scopes_cache[scope_name] = [
                        s for s in self._scopes_cache[scope_name]
                        if s.get("server") != server_name
                    ]

            logger.info(f"Removed server '{server_name}' from all scopes")
            return True
        except Exception as e:
            logger.error(f"Failed to remove server from all scopes in DocumentDB: {e}", exc_info=True)
            return False
