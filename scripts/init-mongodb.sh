#!/bin/bash
# Initialize MongoDB replica set and create vector search indexes
# For MongoDB Community Edition local development

set -e

DOCUMENTDB_HOST="${DOCUMENTDB_HOST:-mongodb}"
DOCUMENTDB_PORT="${DOCUMENTDB_PORT:-27017}"
DOCUMENTDB_USERNAME="${DOCUMENTDB_USERNAME:-admin}"
DOCUMENTDB_PASSWORD="${DOCUMENTDB_PASSWORD:-admin}"
DOCUMENTDB_DATABASE="${DOCUMENTDB_DATABASE:-mcp_registry}"
DOCUMENTDB_NAMESPACE="${DOCUMENTDB_NAMESPACE:-default}"

echo "=========================================="
echo "MongoDB Initialization for MCP Gateway"
echo "=========================================="
echo "Host: $DOCUMENTDB_HOST:$DOCUMENTDB_PORT"
echo "Database: $DOCUMENTDB_DATABASE"
echo "Namespace: $DOCUMENTDB_NAMESPACE"
echo ""

echo "Waiting for MongoDB to be ready..."
sleep 10

echo "Initializing MongoDB replica set..."
mongosh "mongodb://$DOCUMENTDB_HOST:$DOCUMENTDB_PORT" <<EOF
// Initialize replica set (required for transactions and vector search)
try {
  rs.initiate({
    _id: "rs0",
    members: [
      { _id: 0, host: "$DOCUMENTDB_HOST:$DOCUMENTDB_PORT" }
    ]
  });
  print("✓ Replica set initialized");
} catch (e) {
  if (e.codeName === 'AlreadyInitialized') {
    print("✓ Replica set already initialized");
  } else {
    throw e;
  }
}
EOF

echo "Waiting for replica set to elect primary..."
sleep 10

echo "Creating database and collections with indexes..."
mongosh "mongodb://$DOCUMENTDB_USERNAME:$DOCUMENTDB_PASSWORD@$DOCUMENTDB_HOST:$DOCUMENTDB_PORT/admin" <<EOF
// Switch to mcp_registry database
use $DOCUMENTDB_DATABASE;

// Collection 1: MCP Servers
const serversCollection = "mcp_servers_$DOCUMENTDB_NAMESPACE";
print("Creating collection: " + serversCollection);
db.createCollection(serversCollection);
db[serversCollection].createIndex({ path: 1 }, { unique: true });
db[serversCollection].createIndex({ enabled: 1 });
db[serversCollection].createIndex({ tags: 1 });
db[serversCollection].createIndex({ "manifest.serverInfo.name": 1 });
print("✓ " + serversCollection + " indexes created");

// Collection 2: MCP Agents
const agentsCollection = "mcp_agents_$DOCUMENTDB_NAMESPACE";
print("Creating collection: " + agentsCollection);
db.createCollection(agentsCollection);
db[agentsCollection].createIndex({ path: 1 }, { unique: true });
db[agentsCollection].createIndex({ enabled: 1 });
db[agentsCollection].createIndex({ tags: 1 });
db[agentsCollection].createIndex({ "card.name": 1 });
print("✓ " + agentsCollection + " indexes created");

// Collection 3: OAuth Scopes
const scopesCollection = "mcp_scopes_$DOCUMENTDB_NAMESPACE";
print("Creating collection: " + scopesCollection);
db.createCollection(scopesCollection);
db[scopesCollection].createIndex({ "scope_id": 1 }, { unique: true });
db[scopesCollection].createIndex({ "group": 1 });
print("✓ " + scopesCollection + " indexes created");

// Collection 4: Vector Embeddings (1536 dimensions for Titan/OpenAI)
const embeddingsCollection = "mcp_embeddings_1536_$DOCUMENTDB_NAMESPACE";
print("Creating collection: " + embeddingsCollection);
db.createCollection(embeddingsCollection);
db[embeddingsCollection].createIndex({ item_id: 1 }, { unique: true });
db[embeddingsCollection].createIndex({ item_type: 1 });

// Create vector search index
// Note: MongoDB 7.0 uses \$vectorSearch aggregation operator
// Index will be used automatically when using \$vectorSearch
print("Creating vector search index (HNSW)...");
db[embeddingsCollection].createIndex(
  { embedding: "vector" },
  {
    name: "vector_index",
    vectorOptions: {
      type: "hnsw",
      dimensions: 1536,
      similarity: "cosine"
    }
  }
);
print("✓ " + embeddingsCollection + " vector index created");

// Collection 5: Security Scans
const scansCollection = "mcp_security_scans_$DOCUMENTDB_NAMESPACE";
print("Creating collection: " + scansCollection);
db.createCollection(scansCollection);
db[scansCollection].createIndex({ server_path: 1 });
db[scansCollection].createIndex({ scan_status: 1 });
db[scansCollection].createIndex({ scanned_at: -1 });
print("✓ " + scansCollection + " indexes created");

// Collection 6: Federation Configuration
const federationCollection = "mcp_federation_config_$DOCUMENTDB_NAMESPACE";
print("Creating collection: " + federationCollection);
db.createCollection(federationCollection);
db[federationCollection].createIndex({ registry_name: 1 }, { unique: true });
db[federationCollection].createIndex({ enabled: 1 });
print("✓ " + federationCollection + " indexes created");

print("");
print("========================================");
print("MongoDB Initialization Complete!");
print("========================================");
print("Collections created:");
print("  • " + serversCollection);
print("  • " + agentsCollection);
print("  • " + scopesCollection);
print("  • " + embeddingsCollection + " (with vector search)");
print("  • " + scansCollection);
print("  • " + federationCollection);
print("");
print("To use MongoDB CE:");
print("  export STORAGE_BACKEND=documentdb");
print("  docker-compose up registry");
print("========================================");
EOF

echo ""
echo "✓ MongoDB initialization complete!"
