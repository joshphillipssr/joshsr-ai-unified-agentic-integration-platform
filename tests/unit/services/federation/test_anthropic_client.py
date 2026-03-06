"""Unit tests for Anthropic federation client."""

from unittest.mock import patch

from registry.schemas.federation_schema import AnthropicServerConfig
from registry.services.federation.anthropic_client import AnthropicFederationClient


class TestAnthropicFederationClientFetchAllServers:
    """Test fetch_all_servers behavior."""

    def test_fetch_all_servers_with_explicit_config_list(self):
        """Explicit config list should fetch only requested servers."""
        client = AnthropicFederationClient(endpoint="https://registry.modelcontextprotocol.io")
        configs = [
            AnthropicServerConfig(name="io.example/server-a"),
            AnthropicServerConfig(name="io.example/server-b"),
        ]

        with patch.object(
            client,
            "fetch_server",
            side_effect=[
                {"server_name": "io.example/server-a", "path": "/io.example-server-a"},
                {"server_name": "io.example/server-b", "path": "/io.example-server-b"},
            ],
        ) as mock_fetch_server:
            result = client.fetch_all_servers(configs)

        assert len(result) == 2
        assert result[0]["path"] == "/io.example-server-a"
        assert result[1]["path"] == "/io.example-server-b"
        assert mock_fetch_server.call_count == 2

    def test_fetch_all_servers_with_empty_list_fetches_full_catalog(self):
        """Empty config list should fetch paginated catalog and transform entries."""
        client = AnthropicFederationClient(endpoint="https://registry.modelcontextprotocol.io")

        page_one = {
            "servers": [
                {
                    "server": {
                        "name": "io.example/server-a",
                        "description": "A",
                        "version": "1.0.0",
                        "remotes": [{"type": "streamable-http", "url": "https://a.example/mcp"}],
                    },
                    "_meta": {},
                },
                {
                    "server": {
                        "name": "io.example/server-b",
                        "description": "B",
                        "version": "1.0.0",
                        "remotes": [{"type": "streamable-http", "url": "https://b.example/mcp"}],
                    },
                    "_meta": {},
                },
            ],
            "metadata": {"nextCursor": "io.example/server-b:1.0.0", "count": 2},
        }
        page_two = {
            "servers": [
                {
                    "server": {
                        "name": "io.example/server-c",
                        "description": "C",
                        "version": "1.0.0",
                        "remotes": [{"type": "streamable-http", "url": "https://c.example/mcp"}],
                    },
                    "_meta": {},
                },
                # Duplicate from page one should be de-duplicated.
                {
                    "server": {
                        "name": "io.example/server-b",
                        "description": "B",
                        "version": "1.0.0",
                        "remotes": [{"type": "streamable-http", "url": "https://b.example/mcp"}],
                    },
                    "_meta": {},
                },
            ],
            "metadata": {"count": 2},
        }

        with patch.object(client, "_make_request", side_effect=[page_one, page_two]) as mock_request:
            result = client.fetch_all_servers([])

        assert len(result) == 3
        paths = {item["path"] for item in result}
        assert "/io.example-server-a" in paths
        assert "/io.example-server-b" in paths
        assert "/io.example-server-c" in paths
        assert mock_request.call_count == 2
