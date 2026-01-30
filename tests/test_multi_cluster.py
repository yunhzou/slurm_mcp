"""Tests for multi-cluster configuration and management."""

import json
import os
import tempfile
import pytest

from slurm_mcp.config import (
    ClusterConfig,
    ClusterNodes,
    MultiClusterConfig,
    load_clusters_config,
    get_cluster_configs,
)


class TestClusterNodes:
    """Tests for ClusterNodes model."""

    def test_create_cluster_nodes(self):
        """Test creating cluster nodes config."""
        nodes = ClusterNodes(
            login=["login-01.example.com", "login-02.example.com"],
            data=["dc-01.example.com", "dc-02.example.com"],
            vscode=["vscode-01.example.com"],
        )
        assert len(nodes.login) == 2
        assert len(nodes.data) == 2
        assert len(nodes.vscode) == 1

    def test_get_node_by_type_and_index(self):
        """Test getting a node by type and index."""
        nodes = ClusterNodes(
            login=["login-01.example.com", "login-02.example.com"],
            data=["dc-01.example.com"],
        )
        assert nodes.get_node("login", 0) == "login-01.example.com"
        assert nodes.get_node("login", 1) == "login-02.example.com"
        assert nodes.get_node("data", 0) == "dc-01.example.com"
        assert nodes.get_node("login", 99) is None  # Out of range
        assert nodes.get_node("vscode", 0) is None  # Empty list

    def test_list_all_nodes(self):
        """Test listing all nodes by type."""
        nodes = ClusterNodes(
            login=["login-01.example.com"],
            data=["dc-01.example.com", "dc-02.example.com"],
        )
        all_nodes = nodes.list_all_nodes()
        assert "login" in all_nodes
        assert "data" in all_nodes
        assert "vscode" in all_nodes
        assert len(all_nodes["data"]) == 2


class TestClusterConfig:
    """Tests for ClusterConfig model."""

    def test_create_cluster_config(self):
        """Test creating a cluster config."""
        config = ClusterConfig(
            name="test-cluster",
            ssh_host="login.example.com",
            ssh_user="testuser",
            user_root="/home/testuser",
        )
        assert config.name == "test-cluster"
        assert config.ssh_host == "login.example.com"
        assert config.ssh_user == "testuser"

    def test_create_cluster_config_with_nodes(self):
        """Test creating cluster config with multiple nodes."""
        config = ClusterConfig(
            name="test-cluster",
            ssh_user="testuser",
            user_root="/home/testuser",
            nodes=ClusterNodes(
                login=["login-01.example.com", "login-02.example.com"],
                data=["dc-01.example.com"],
                vscode=["vscode-01.example.com"],
            ),
        )
        assert config.nodes is not None
        assert len(config.nodes.login) == 2

    def test_get_ssh_host_legacy(self):
        """Test get_ssh_host with legacy ssh_host setting."""
        config = ClusterConfig(
            name="test",
            ssh_host="legacy.example.com",
            ssh_user="user",
            user_root="/home/user",
        )
        assert config.get_ssh_host() == "legacy.example.com"
        assert config.get_ssh_host(None) == "legacy.example.com"

    def test_get_ssh_host_by_type(self):
        """Test get_ssh_host with node type."""
        config = ClusterConfig(
            name="test",
            ssh_user="user",
            user_root="/home/user",
            nodes=ClusterNodes(
                login=["login-01.example.com", "login-02.example.com"],
                data=["dc-01.example.com"],
                vscode=["vscode-01.example.com"],
            ),
        )
        assert config.get_ssh_host("login") == "login-01.example.com"
        assert config.get_ssh_host("data") == "dc-01.example.com"
        assert config.get_ssh_host("vscode") == "vscode-01.example.com"

    def test_get_ssh_host_by_type_index(self):
        """Test get_ssh_host with type:index format."""
        config = ClusterConfig(
            name="test",
            ssh_user="user",
            user_root="/home/user",
            nodes=ClusterNodes(
                login=["login-01.example.com", "login-02.example.com", "login-03.example.com"],
            ),
        )
        assert config.get_ssh_host("login:0") == "login-01.example.com"
        assert config.get_ssh_host("login:1") == "login-02.example.com"
        assert config.get_ssh_host("login:2") == "login-03.example.com"

    def test_get_ssh_host_direct_hostname(self):
        """Test get_ssh_host with direct hostname."""
        config = ClusterConfig(
            name="test",
            ssh_user="user",
            user_root="/home/user",
            nodes=ClusterNodes(
                login=["login-01.example.com"],
            ),
        )
        # Direct hostname that matches a configured node
        assert config.get_ssh_host("login-01.example.com") == "login-01.example.com"
        # Direct hostname that doesn't match but has a dot (treated as hostname)
        assert config.get_ssh_host("other.example.com") == "other.example.com"

    def test_get_ssh_host_raises_when_no_host(self):
        """Test get_ssh_host raises when no host can be determined."""
        config = ClusterConfig(
            name="test",
            ssh_user="user",
            user_root="/home/user",
            # No ssh_host and no nodes configured
        )
        with pytest.raises(ValueError, match="Cannot determine SSH host"):
            config.get_ssh_host("nonexistent")

    def test_list_available_nodes(self):
        """Test listing available nodes."""
        config = ClusterConfig(
            name="test",
            ssh_user="user",
            user_root="/home/user",
            nodes=ClusterNodes(
                login=["login-01.example.com", "login-02.example.com"],
                data=["dc-01.example.com"],
            ),
        )
        nodes = config.list_available_nodes()
        assert "login" in nodes
        assert len(nodes["login"]) == 2

    def test_list_available_nodes_legacy(self):
        """Test listing available nodes with legacy ssh_host."""
        config = ClusterConfig(
            name="test",
            ssh_host="legacy.example.com",
            ssh_user="user",
            user_root="/home/user",
        )
        nodes = config.list_available_nodes()
        assert "default" in nodes
        assert nodes["default"] == ["legacy.example.com"]

    def test_default_directory_paths(self):
        """Test that directory paths are auto-generated from user_root."""
        config = ClusterConfig(
            name="test",
            ssh_host="host",
            ssh_user="user",
            user_root="/home/user",
        )
        assert config.dir_datasets == "/home/user/data"
        assert config.dir_results == "/home/user/results"
        assert config.dir_models == "/home/user/models"
        assert config.dir_logs == "/home/user/logs"

    def test_explicit_directory_paths(self):
        """Test that explicit directory paths override defaults."""
        config = ClusterConfig(
            name="test",
            ssh_host="host",
            ssh_user="user",
            user_root="/home/user",
            dir_datasets="/custom/datasets",
        )
        assert config.dir_datasets == "/custom/datasets"
        assert config.dir_results == "/home/user/results"

    def test_container_mounts(self):
        """Test container mounts generation."""
        config = ClusterConfig(
            name="test",
            ssh_host="host",
            ssh_user="user",
            user_root="/home/user",
        )
        mounts = config.get_container_mounts()
        assert "/home/user/data:/datasets" in mounts
        assert "/home/user/results:/results" in mounts

    def test_ssh_port_default(self):
        """Test default SSH port."""
        config = ClusterConfig(
            name="test",
            ssh_host="host",
            ssh_user="user",
            user_root="/home/user",
        )
        assert config.ssh_port == 22

    def test_interactive_account_inherits_default(self):
        """Test that interactive_account inherits from default_account."""
        config = ClusterConfig(
            name="test",
            ssh_host="host",
            ssh_user="user",
            user_root="/home/user",
            default_account="my_project",
        )
        assert config.interactive_account == "my_project"


class TestMultiClusterConfig:
    """Tests for MultiClusterConfig model."""

    def test_create_multi_cluster_config(self):
        """Test creating a multi-cluster config."""
        config = MultiClusterConfig(
            default_cluster="prod",
            clusters=[
                ClusterConfig(
                    name="prod",
                    ssh_host="prod.example.com",
                    ssh_user="user",
                    user_root="/home/user",
                ),
                ClusterConfig(
                    name="dev",
                    ssh_host="dev.example.com",
                    ssh_user="user",
                    user_root="/scratch/user",
                ),
            ],
        )
        assert config.default_cluster == "prod"
        assert len(config.clusters) == 2

    def test_list_cluster_names(self):
        """Test listing cluster names."""
        config = MultiClusterConfig(
            clusters=[
                ClusterConfig(name="a", ssh_host="a", ssh_user="u", user_root="/a"),
                ClusterConfig(name="b", ssh_host="b", ssh_user="u", user_root="/b"),
            ]
        )
        assert config.list_cluster_names() == ["a", "b"]

    def test_get_cluster(self):
        """Test getting a cluster by name."""
        config = MultiClusterConfig(
            clusters=[
                ClusterConfig(name="prod", ssh_host="prod.example.com", ssh_user="u", user_root="/p"),
                ClusterConfig(name="dev", ssh_host="dev.example.com", ssh_user="u", user_root="/d"),
            ]
        )
        prod = config.get_cluster("prod")
        assert prod is not None
        assert prod.ssh_host == "prod.example.com"

    def test_get_cluster_returns_none_for_invalid(self):
        """Test getting a non-existent cluster returns None."""
        config = MultiClusterConfig(
            clusters=[
                ClusterConfig(name="prod", ssh_host="prod", ssh_user="u", user_root="/p"),
            ]
        )
        assert config.get_cluster("nonexistent") is None

    def test_default_cluster_auto_set(self):
        """Test that default_cluster is auto-set to first cluster if not specified."""
        config = MultiClusterConfig(
            clusters=[
                ClusterConfig(name="first", ssh_host="f", ssh_user="u", user_root="/f"),
                ClusterConfig(name="second", ssh_host="s", ssh_user="u", user_root="/s"),
            ]
        )
        assert config.default_cluster == "first"

    def test_duplicate_cluster_names_raises(self):
        """Test that duplicate cluster names raise an error."""
        with pytest.raises(ValueError, match="Duplicate cluster names"):
            MultiClusterConfig(
                clusters=[
                    ClusterConfig(name="same", ssh_host="a", ssh_user="u", user_root="/a"),
                    ClusterConfig(name="same", ssh_host="b", ssh_user="u", user_root="/b"),
                ]
            )

    def test_invalid_default_cluster_raises(self):
        """Test that invalid default_cluster raises an error."""
        with pytest.raises(ValueError, match="not found"):
            MultiClusterConfig(
                default_cluster="nonexistent",
                clusters=[
                    ClusterConfig(name="prod", ssh_host="p", ssh_user="u", user_root="/p"),
                ]
            )


class TestLoadClustersConfig:
    """Tests for loading cluster config from JSON file."""

    def test_load_from_json_file(self):
        """Test loading config from a JSON file."""
        config_data = {
            "default_cluster": "test",
            "clusters": [
                {
                    "name": "test",
                    "ssh_host": "test.example.com",
                    "ssh_user": "testuser",
                    "user_root": "/home/testuser",
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_clusters_config(temp_path)
            assert config.default_cluster == "test"
            assert len(config.clusters) == 1
            assert config.clusters[0].ssh_host == "test.example.com"
        finally:
            os.unlink(temp_path)

    def test_load_with_nodes(self):
        """Test loading config with multiple nodes."""
        config_data = {
            "default_cluster": "test",
            "clusters": [
                {
                    "name": "test",
                    "ssh_user": "testuser",
                    "user_root": "/home/testuser",
                    "nodes": {
                        "login": ["login-01.example.com", "login-02.example.com"],
                        "data": ["dc-01.example.com"],
                        "vscode": ["vscode-01.example.com"],
                    },
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_clusters_config(temp_path)
            cluster = config.clusters[0]
            assert cluster.nodes is not None
            assert len(cluster.nodes.login) == 2
            assert cluster.get_ssh_host("login") == "login-01.example.com"
            assert cluster.get_ssh_host("data") == "dc-01.example.com"
        finally:
            os.unlink(temp_path)

    def test_load_multiple_clusters(self):
        """Test loading multiple clusters from JSON."""
        config_data = {
            "default_cluster": "prod",
            "clusters": [
                {
                    "name": "prod",
                    "ssh_host": "prod.example.com",
                    "ssh_user": "user",
                    "user_root": "/lustre/users/user",
                    "default_account": "prod_account",
                },
                {
                    "name": "dev",
                    "ssh_host": "dev.example.com",
                    "ssh_user": "user",
                    "user_root": "/home/user",
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_clusters_config(temp_path)
            assert len(config.clusters) == 2
            assert config.get_cluster("prod").default_account == "prod_account"
            assert config.get_cluster("dev").ssh_host == "dev.example.com"
        finally:
            os.unlink(temp_path)

    def test_file_not_found_raises(self):
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_clusters_config("/nonexistent/path/config.json")


class TestClusterManagerUnit:
    """Unit tests for ClusterManager (without SSH connections)."""

    @pytest.mark.asyncio
    async def test_manager_initialization(self):
        """Test ClusterManager initialization."""
        from slurm_mcp.cluster_manager import ClusterManager

        config = MultiClusterConfig(
            default_cluster="test",
            clusters=[
                ClusterConfig(
                    name="test",
                    ssh_host="test.example.com",
                    ssh_user="user",
                    user_root="/home/user",
                )
            ],
        )

        manager = ClusterManager(config)
        await manager.initialize()

        assert manager.is_initialized
        assert manager.default_cluster == "test"

    @pytest.mark.asyncio
    async def test_manager_list_clusters(self):
        """Test listing clusters from manager."""
        from slurm_mcp.cluster_manager import ClusterManager

        config = MultiClusterConfig(
            clusters=[
                ClusterConfig(name="a", ssh_host="a.com", ssh_user="u", user_root="/a"),
                ClusterConfig(name="b", ssh_host="b.com", ssh_user="u", user_root="/b"),
            ]
        )

        manager = ClusterManager(config)
        await manager.initialize()

        clusters = manager.list_clusters()
        assert len(clusters) == 2
        assert clusters[0]["name"] == "a"
        assert clusters[1]["name"] == "b"

    @pytest.mark.asyncio
    async def test_manager_list_cluster_nodes(self):
        """Test listing cluster nodes from manager."""
        from slurm_mcp.cluster_manager import ClusterManager

        config = MultiClusterConfig(
            clusters=[
                ClusterConfig(
                    name="test",
                    ssh_user="u",
                    user_root="/home/u",
                    nodes=ClusterNodes(
                        login=["login-01.example.com", "login-02.example.com"],
                        data=["dc-01.example.com"],
                    ),
                ),
            ]
        )

        manager = ClusterManager(config)
        await manager.initialize()

        nodes = manager.list_cluster_nodes("test")
        assert "login" in nodes
        assert len(nodes["login"]) == 2
        assert "data" in nodes
        assert len(nodes["data"]) == 1

    @pytest.mark.asyncio
    async def test_manager_set_default_cluster(self):
        """Test changing default cluster."""
        from slurm_mcp.cluster_manager import ClusterManager

        config = MultiClusterConfig(
            default_cluster="a",
            clusters=[
                ClusterConfig(name="a", ssh_host="a.com", ssh_user="u", user_root="/a"),
                ClusterConfig(name="b", ssh_host="b.com", ssh_user="u", user_root="/b"),
            ]
        )

        manager = ClusterManager(config)
        await manager.initialize()

        assert manager.default_cluster == "a"
        manager.set_default_cluster("b")
        assert manager.default_cluster == "b"

    @pytest.mark.asyncio
    async def test_manager_set_invalid_default_raises(self):
        """Test that setting invalid default cluster raises error."""
        from slurm_mcp.cluster_manager import ClusterManager

        config = MultiClusterConfig(
            clusters=[
                ClusterConfig(name="a", ssh_host="a.com", ssh_user="u", user_root="/a"),
            ]
        )

        manager = ClusterManager(config)
        await manager.initialize()

        with pytest.raises(ValueError, match="not found"):
            manager.set_default_cluster("nonexistent")

    @pytest.mark.asyncio
    async def test_manager_get_cluster_config(self):
        """Test getting cluster config from manager."""
        from slurm_mcp.cluster_manager import ClusterManager

        config = MultiClusterConfig(
            clusters=[
                ClusterConfig(
                    name="test",
                    ssh_host="test.example.com",
                    ssh_user="testuser",
                    user_root="/home/testuser",
                    description="Test cluster",
                ),
            ]
        )

        manager = ClusterManager(config)
        await manager.initialize()

        cluster_config = manager.get_cluster_config("test")
        assert cluster_config is not None
        assert cluster_config.ssh_host == "test.example.com"
        assert cluster_config.description == "Test cluster"
