#!/usr/bin/env python3
"""
Initialize DocumentDB collections and indexes for MCP Gateway Registry.

This script creates all necessary vector indexes and standard indexes for
the MCP Gateway Registry DocumentDB backend.

Usage:
    # Using environment variables
    export DOCUMENTDB_HOST=your-cluster.docdb.amazonaws.com
    export DOCUMENTDB_USERNAME=admin
    export DOCUMENTDB_PASSWORD=yourpassword
    uv run python scripts/init-documentdb-indexes.py

    # Using command-line arguments
    uv run python scripts/init-documentdb-indexes.py --host your-cluster.docdb.amazonaws.com
    uv run python scripts/init-documentdb-indexes.py --use-iam --host your-cluster.docdb.amazonaws.com

    # With namespace
    uv run python scripts/init-documentdb-indexes.py --namespace tenant-a

    # Recreate indexes
    uv run python scripts/init-documentdb-indexes.py --recreate

Requires:
    - motor (AsyncIOMotorClient)
    - boto3 (for IAM authentication)
    - DocumentDB connection details via environment variables or command-line
"""

import argparse
import asyncio
import json
import logging
import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient


# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)


# Collection names
COLLECTION_SERVERS = "mcp_servers"
COLLECTION_AGENTS = "mcp_agents"
COLLECTION_SCOPES = "mcp_scopes"
COLLECTION_EMBEDDINGS = "mcp_embeddings_1536"
COLLECTION_SECURITY_SCANS = "mcp_security_scans"
COLLECTION_FEDERATION_CONFIG = "mcp_federation_config"


async def _get_documentdb_connection_string(
    host: str,
    port: int,
    database: str,
    username: Optional[str],
    password: Optional[str],
    use_iam: bool,
    use_tls: bool,
    tls_ca_file: Optional[str],
) -> str:
    """Build DocumentDB connection string."""
    if use_iam:
        import boto3

        session = boto3.Session()
        credentials = session.get_credentials()

        if not credentials:
            raise ValueError("AWS credentials not found for DocumentDB IAM auth")

        connection_string = (
            f"mongodb://{credentials.access_key}:{credentials.secret_key}@"
            f"{host}:{port}/{database}?"
            f"tls=true&authSource=$external&authMechanism=MONGODB-AWS"
        )

        if tls_ca_file:
            connection_string += f"&tlsCAFile={tls_ca_file}"

        logger.info(f"Using AWS IAM authentication for DocumentDB (host: {host})")

    else:
        if username and password:
            connection_string = (
                f"mongodb://{username}:{password}@"
                f"{host}:{port}/{database}?"
                f"tls={str(use_tls).lower()}"
            )

            if use_tls and tls_ca_file:
                connection_string += f"&tlsCAFile={tls_ca_file}"

            logger.info(
                f"Using username/password authentication for DocumentDB (host: {host})"
            )
        else:
            connection_string = f"mongodb://{host}:{port}/{database}"
            logger.info(f"Using no authentication for DocumentDB (host: {host})")

    return connection_string


async def _create_vector_index(
    collection,
    collection_name: str,
    recreate: bool,
) -> None:
    """Create vector index for embeddings collection."""
    index_name = "embedding_vector_idx"

    if recreate:
        try:
            await collection.drop_index(index_name)
            logger.info(f"Dropped existing vector index '{index_name}' from {collection_name}")
        except Exception as e:
            logger.debug(f"No existing vector index to drop: {e}")

    try:
        await collection.create_index(
            [("embedding", "vector")],
            name=index_name,
            vectorOptions={
                "type": "hnsw",
                "similarity": "cosine",
                "dimensions": 1536,
                "m": 16,
                "efConstruction": 128,
            },
        )
        logger.info(f"Created vector index '{index_name}' on {collection_name}")
    except Exception as e:
        logger.error(f"Failed to create vector index on {collection_name}: {e}", exc_info=True)
        raise


async def _create_embeddings_indexes(
    collection,
    collection_name: str,
    recreate: bool,
) -> None:
    """Create all indexes for embeddings collection."""
    await _create_vector_index(collection, collection_name, recreate)

    indexes = [
        ("name", 1),
        ("path", 1),
        ("entity_type", 1),
    ]

    for field, order in indexes:
        index_name = f"{field}_idx"
        unique = field == "path"

        if recreate:
            try:
                await collection.drop_index(index_name)
                logger.info(f"Dropped existing index '{index_name}' from {collection_name}")
            except Exception as e:
                logger.debug(f"No existing index '{index_name}' to drop: {e}")

        try:
            await collection.create_index(
                [(field, order)],
                name=index_name,
                unique=unique,
            )
            logger.info(
                f"Created {'unique ' if unique else ''}index '{index_name}' on {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create index '{index_name}' on {collection_name}: {e}")


async def _create_servers_indexes(
    collection,
    collection_name: str,
    recreate: bool,
) -> None:
    """Create all indexes for servers collection."""
    indexes = [
        ("_id", 1, True),
        ("server_name", 1, False),
        ("is_enabled", 1, False),
        ("version", 1, False),
        ("tags", 1, False),
    ]

    for field, order, unique in indexes:
        index_name = f"{field}_idx"

        if recreate:
            try:
                await collection.drop_index(index_name)
                logger.info(f"Dropped existing index '{index_name}' from {collection_name}")
            except Exception as e:
                logger.debug(f"No existing index '{index_name}' to drop: {e}")

        try:
            await collection.create_index(
                [(field, order)],
                name=index_name,
                unique=unique,
            )
            logger.info(
                f"Created {'unique ' if unique else ''}index '{index_name}' on {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create index '{index_name}' on {collection_name}: {e}")


async def _create_agents_indexes(
    collection,
    collection_name: str,
    recreate: bool,
) -> None:
    """Create all indexes for agents collection."""
    indexes = [
        ("_id", 1, True),
        ("name", 1, False),
        ("is_enabled", 1, False),
        ("version", 1, False),
        ("tags", 1, False),
    ]

    for field, order, unique in indexes:
        index_name = f"{field}_idx"

        if recreate:
            try:
                await collection.drop_index(index_name)
                logger.info(f"Dropped existing index '{index_name}' from {collection_name}")
            except Exception as e:
                logger.debug(f"No existing index '{index_name}' to drop: {e}")

        try:
            await collection.create_index(
                [(field, order)],
                name=index_name,
                unique=unique,
            )
            logger.info(
                f"Created {'unique ' if unique else ''}index '{index_name}' on {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create index '{index_name}' on {collection_name}: {e}")


async def _create_scopes_indexes(
    collection,
    collection_name: str,
    recreate: bool,
) -> None:
    """Create all indexes for scopes collection."""
    indexes = [
        ("_id", 1, True),
        ("name", 1, False),
    ]

    for field, order, unique in indexes:
        index_name = f"{field}_idx"

        if recreate:
            try:
                await collection.drop_index(index_name)
                logger.info(f"Dropped existing index '{index_name}' from {collection_name}")
            except Exception as e:
                logger.debug(f"No existing index '{index_name}' to drop: {e}")

        try:
            await collection.create_index(
                [(field, order)],
                name=index_name,
                unique=unique,
            )
            logger.info(
                f"Created {'unique ' if unique else ''}index '{index_name}' on {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create index '{index_name}' on {collection_name}: {e}")


async def _create_security_scans_indexes(
    collection,
    collection_name: str,
    recreate: bool,
) -> None:
    """Create all indexes for security scans collection."""
    indexes = [
        ("_id", 1, True),
        ("entity_path", 1, False),
        ("entity_type", 1, False),
        ("scan_status", 1, False),
        ("scanned_at", 1, False),
    ]

    for field, order, unique in indexes:
        index_name = f"{field}_idx"

        if recreate:
            try:
                await collection.drop_index(index_name)
                logger.info(f"Dropped existing index '{index_name}' from {collection_name}")
            except Exception as e:
                logger.debug(f"No existing index '{index_name}' to drop: {e}")

        try:
            await collection.create_index(
                [(field, order)],
                name=index_name,
                unique=unique,
            )
            logger.info(
                f"Created {'unique ' if unique else ''}index '{index_name}' on {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create index '{index_name}' on {collection_name}: {e}")


async def _create_federation_config_indexes(
    collection,
    collection_name: str,
    recreate: bool,
) -> None:
    """Create all indexes for federation config collection."""
    indexes = [
        ("_id", 1, True),
    ]

    for field, order, unique in indexes:
        index_name = f"{field}_idx"

        if recreate:
            try:
                await collection.drop_index(index_name)
                logger.info(f"Dropped existing index '{index_name}' from {collection_name}")
            except Exception as e:
                logger.debug(f"No existing index '{index_name}' to drop: {e}")

        try:
            await collection.create_index(
                [(field, order)],
                name=index_name,
                unique=unique,
            )
            logger.info(
                f"Created {'unique ' if unique else ''}index '{index_name}' on {collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create index '{index_name}' on {collection_name}: {e}")


async def _initialize_collections(
    db,
    namespace: str,
    recreate: bool,
) -> None:
    """Initialize all collections and indexes."""
    collection_configs = [
        (COLLECTION_SERVERS, _create_servers_indexes),
        (COLLECTION_AGENTS, _create_agents_indexes),
        (COLLECTION_SCOPES, _create_scopes_indexes),
        (COLLECTION_EMBEDDINGS, _create_embeddings_indexes),
        (COLLECTION_SECURITY_SCANS, _create_security_scans_indexes),
        (COLLECTION_FEDERATION_CONFIG, _create_federation_config_indexes),
    ]

    for base_name, create_indexes_func in collection_configs:
        collection_name = f"{base_name}_{namespace}"
        collection = db[collection_name]

        logger.info(f"Creating indexes for collection: {collection_name}")

        try:
            await create_indexes_func(collection, collection_name, recreate)
            logger.info(f"Successfully created indexes for {collection_name}")
        except Exception as e:
            logger.error(f"Failed to create indexes for {collection_name}: {e}", exc_info=True)
            raise


async def main():
    """Main initialization function."""
    parser = argparse.ArgumentParser(
        description="Initialize DocumentDB collections and indexes for MCP Gateway Registry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Using environment variables
    export DOCUMENTDB_HOST=your-cluster.docdb.amazonaws.com
    uv run python scripts/init-documentdb-indexes.py

    # Using command-line arguments
    uv run python scripts/init-documentdb-indexes.py --host your-cluster.docdb.amazonaws.com

    # With IAM authentication
    uv run python scripts/init-documentdb-indexes.py --use-iam --host your-cluster.docdb.amazonaws.com

    # With namespace
    uv run python scripts/init-documentdb-indexes.py --namespace tenant-a
""",
    )

    parser.add_argument(
        "--host",
        default=os.getenv("DOCUMENTDB_HOST", "localhost"),
        help="DocumentDB host (default: from DOCUMENTDB_HOST env var or 'localhost')",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("DOCUMENTDB_PORT", "27017")),
        help="DocumentDB port (default: from DOCUMENTDB_PORT env var or 27017)",
    )
    parser.add_argument(
        "--database",
        default=os.getenv("DOCUMENTDB_DATABASE", "mcp_registry"),
        help="Database name (default: from DOCUMENTDB_DATABASE env var or 'mcp_registry')",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("DOCUMENTDB_USERNAME"),
        help="DocumentDB username (default: from DOCUMENTDB_USERNAME env var)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("DOCUMENTDB_PASSWORD"),
        help="DocumentDB password (default: from DOCUMENTDB_PASSWORD env var)",
    )
    parser.add_argument(
        "--use-iam",
        action="store_true",
        default=os.getenv("DOCUMENTDB_USE_IAM", "false").lower() == "true",
        help="Use AWS IAM authentication (default: from DOCUMENTDB_USE_IAM env var or false)",
    )
    parser.add_argument(
        "--use-tls",
        action="store_true",
        default=os.getenv("DOCUMENTDB_USE_TLS", "true").lower() == "true",
        help="Use TLS for connection (default: from DOCUMENTDB_USE_TLS env var or true)",
    )
    parser.add_argument(
        "--tls-ca-file",
        default=os.getenv("DOCUMENTDB_TLS_CA_FILE", "global-bundle.pem"),
        help="TLS CA file path (default: from DOCUMENTDB_TLS_CA_FILE env var or 'global-bundle.pem')",
    )
    parser.add_argument(
        "--namespace",
        default=os.getenv("DOCUMENTDB_NAMESPACE", "default"),
        help="Namespace for collection names (default: from DOCUMENTDB_NAMESPACE env var or 'default')",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate indexes if they exist",
    )

    args = parser.parse_args()

    logger.info("Initializing DocumentDB collections and indexes")
    logger.info(f"Host: {args.host}:{args.port}")
    logger.info(f"Database: {args.database}")
    logger.info(f"Namespace: {args.namespace}")
    logger.info(f"Use IAM: {args.use_iam}")
    logger.info(f"Use TLS: {args.use_tls}")

    try:
        connection_string = await _get_documentdb_connection_string(
            host=args.host,
            port=args.port,
            database=args.database,
            username=args.username,
            password=args.password,
            use_iam=args.use_iam,
            use_tls=args.use_tls,
            tls_ca_file=args.tls_ca_file if args.use_tls else None,
        )

        client = AsyncIOMotorClient(connection_string)
        db = client[args.database]

        server_info = await client.server_info()
        logger.info(
            f"Connected to DocumentDB/MongoDB {server_info.get('version', 'unknown')}"
        )

        await _initialize_collections(db, args.namespace, args.recreate)

        logger.info(
            f"DocumentDB initialization complete for namespace '{args.namespace}'"
        )

        client.close()

    except Exception as e:
        logger.error(f"Failed to initialize DocumentDB: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
