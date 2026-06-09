"""Tests for ClientsManager and ClientEntry — v1.6.4."""

import threading

import pytest

from veltix.server.client_info import ClientInfo
from veltix.socket_core.managers.clients_manager import ClientEntry, ClientsManager


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_client_info(addr=("127.0.0.1", 8080)) -> ClientInfo:
    """Create a minimal ClientInfo for testing."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    return ClientInfo(conn=sock, addr=addr, thread_id=1)


# ── ClientEntry ───────────────────────────────────────────────────────────────

class TestClientEntry:
    def test_slots(self):
        manager = ClientsManager()
        info = make_client_info()
        client_id = manager.add_client(info)
        entry = manager.get_client(client_id)
        assert hasattr(entry, "id")
        assert hasattr(entry, "info")
        assert hasattr(entry, "buffer")

    def test_entry_has_correct_id(self):
        manager = ClientsManager()
        info = make_client_info()
        client_id = manager.add_client(info)
        entry = manager.get_client(client_id)
        assert entry.id == client_id

    def test_entry_has_correct_info(self):
        manager = ClientsManager()
        info = make_client_info()
        client_id = manager.add_client(info)
        entry = manager.get_client(client_id)
        assert entry.info is info


# ── ClientsManager ────────────────────────────────────────────────────────────

class TestClientsManagerAdd:
    def test_add_client_returns_id(self):
        manager = ClientsManager()
        info = make_client_info()
        client_id = manager.add_client(info)
        assert isinstance(client_id, int)
        assert client_id == 1

    def test_add_multiple_clients_increments_id(self):
        manager = ClientsManager()
        id1 = manager.add_client(make_client_info())
        id2 = manager.add_client(make_client_info())
        id3 = manager.add_client(make_client_info())
        assert id1 == 1
        assert id2 == 2
        assert id3 == 3

    def test_add_increases_count(self):
        manager = ClientsManager()
        assert manager.count() == 0
        manager.add_client(make_client_info())
        assert manager.count() == 1
        manager.add_client(make_client_info())
        assert manager.count() == 2


class TestClientsManagerRemove:
    def test_remove_existing_client(self):
        manager = ClientsManager()
        client_id = manager.add_client(make_client_info())
        result = manager.remove_client(client_id)
        assert result is True
        assert manager.count() == 0

    def test_remove_nonexistent_client(self):
        manager = ClientsManager()
        result = manager.remove_client(999)
        assert result is False

    def test_remove_decreases_count(self):
        manager = ClientsManager()
        id1 = manager.add_client(make_client_info())
        manager.add_client(make_client_info())
        manager.remove_client(id1)
        assert manager.count() == 1


class TestClientsManagerGet:
    def test_get_existing_client(self):
        manager = ClientsManager()
        info = make_client_info()
        client_id = manager.add_client(info)
        entry = manager.get_client(client_id)
        assert entry is not None
        assert entry.info is info

    def test_get_nonexistent_client(self):
        manager = ClientsManager()
        entry = manager.get_client(999)
        assert entry is None

    def test_get_all_clients_empty(self):
        manager = ClientsManager()
        assert manager.get_all_clients() == []

    def test_get_all_clients(self):
        manager = ClientsManager()
        manager.add_client(make_client_info())
        manager.add_client(make_client_info())
        clients = manager.get_all_clients()
        assert len(clients) == 2

    def test_get_all_clients_returns_copy(self):
        """Modifying the returned list should not affect the manager."""
        manager = ClientsManager()
        manager.add_client(make_client_info())
        clients = manager.get_all_clients()
        clients.clear()
        assert manager.count() == 1


class TestClientsManagerHas:
    def test_has_client_id_true(self):
        manager = ClientsManager()
        client_id = manager.add_client(make_client_info())
        assert manager.has_client_id(client_id) is True

    def test_has_client_id_false(self):
        manager = ClientsManager()
        assert manager.has_client_id(999) is False

    def test_has_client_info_true(self):
        manager = ClientsManager()
        info = make_client_info()
        manager.add_client(info)
        assert manager.has_client_info(info) is True

    def test_has_client_info_false(self):
        manager = ClientsManager()
        info = make_client_info()
        assert manager.has_client_info(info) is False


class TestClientsManagerTags:
    def test_get_clients_by_tag_no_value(self):
        manager = ClientsManager()
        info1 = make_client_info()
        info2 = make_client_info()
        info1.add_tag("admin")
        manager.add_client(info1)
        manager.add_client(info2)

        results = manager.get_clients_by_tag("admin")
        assert len(results) == 1
        assert results[0].info is info1

    def test_get_clients_by_tag_with_value(self):
        manager = ClientsManager()
        info1 = make_client_info()
        info2 = make_client_info()
        info1.add_tag("role", value="admin")
        info2.add_tag("role", value="guest")
        manager.add_client(info1)
        manager.add_client(info2)

        results = manager.get_clients_by_tag("role", value="admin")
        assert len(results) == 1
        assert results[0].info is info1

    def test_get_clients_by_tag_no_match(self):
        manager = ClientsManager()
        manager.add_client(make_client_info())
        results = manager.get_clients_by_tag("nonexistent")
        assert results == []

    def test_to_sockets(self):
        manager = ClientsManager()
        info1 = make_client_info()
        info2 = make_client_info()
        manager.add_client(info1)
        manager.add_client(info2)

        entries = manager.get_all_clients()
        sockets = manager.to_sockets(entries)

        assert len(sockets) == 2
        assert info1.conn in sockets
        assert info2.conn in sockets


class TestClientsManagerThreadSafety:
    def test_concurrent_add(self):
        """Concurrent adds should not lose any client."""
        manager = ClientsManager()
        errors = []

        def add_clients():
            try:
                for _ in range(50):
                    manager.add_client(make_client_info())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_clients) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert manager.count() == 200

    def test_concurrent_add_remove(self):
        """Concurrent adds and removes should not raise."""
        manager = ClientsManager()
        errors = []

        def worker():
            try:
                for _ in range(20):
                    client_id = manager.add_client(make_client_info())
                    manager.remove_client(client_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


@pytest.mark.usefixtures("socket_core_backend")
class TestCloseClientById:
    def test_close_client_with_none_id(self):
        """close_client(id_=None) should not crash — bugfix v1.6.6."""
        from veltix import Server, ServerConfig
        server = Server(ServerConfig(host="127.0.0.1", port=18200))
        # id_=0 used to be falsy — should now be handled correctly
        result = server.close_client(client=None, id_=None)
        assert result is False
        server.close_all()

    def test_close_client_with_zero_id(self):
        """id_=0 should not be treated as falsy — bugfix v1.6.6."""
        from veltix import Server, ServerConfig
        server = Server(ServerConfig(host="127.0.0.1", port=18201))
        # id=0 doesn't exist but should attempt lookup, not skip
        result = server.close_client(client=None, id_=0)
        assert result is False  # 0 doesn't exist, but it tried
        server.close_all()
