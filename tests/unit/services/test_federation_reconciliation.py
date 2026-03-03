"""Unit tests for federation reconciliation behavior."""

import asyncio

from registry.schemas.federation_schema import AnthropicFederationConfig, FederationConfig
from registry.services.federation_reconciliation import reconcile_anthropic_servers


class _DummyServerRepo:
    def __init__(self, servers_by_path):
        self._servers_by_path = servers_by_path

    async def list_by_source(self, source):
        if source == "anthropic":
            return self._servers_by_path
        return {}

    async def list_all(self):
        return self._servers_by_path


class _DummyServerService:
    def __init__(self):
        self.removed_paths = []

    async def remove_server(self, path):
        self.removed_paths.append(path)
        return True


def test_reconciliation_skips_removal_in_full_catalog_mode():
    """Enabled Anthropic + empty config list should not remove synced servers."""
    config = FederationConfig(
        anthropic=AnthropicFederationConfig(
            enabled=True,
            endpoint="https://registry.modelcontextprotocol.io",
            servers=[],
        )
    )
    repo = _DummyServerRepo(
        {
            "/com.example-one": {"server_name": "com.example/one", "source": "anthropic"},
            "/com.example-two": {"server_name": "com.example/two", "source": "anthropic"},
        }
    )
    service = _DummyServerService()

    result = asyncio.run(
        reconcile_anthropic_servers(
            config=config,
            server_service=service,
            server_repo=repo,
        )
    )

    assert result["removed_count"] == 0
    assert service.removed_paths == []


def test_reconciliation_removes_all_when_anthropic_disabled():
    """Disabled Anthropic should remove stale anthropic servers."""
    config = FederationConfig(
        anthropic=AnthropicFederationConfig(
            enabled=False,
            endpoint="https://registry.modelcontextprotocol.io",
            servers=[],
        )
    )
    repo = _DummyServerRepo(
        {
            "/com.example-one": {"server_name": "com.example/one", "source": "anthropic"},
            "/com.example-two": {"server_name": "com.example/two", "source": "anthropic"},
        }
    )
    service = _DummyServerService()

    result = asyncio.run(
        reconcile_anthropic_servers(
            config=config,
            server_service=service,
            server_repo=repo,
        )
    )

    assert result["removed_count"] == 2
    assert set(service.removed_paths) == {"/com.example-one", "/com.example-two"}
