"""Tests for ClientInfo tag system — v1.6.0."""

import socket

import pytest

from veltix.server.client_info import ClientInfo


# ── Fixture ───────────────────────────────────────────────────────────────────

def make_client() -> ClientInfo:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    return ClientInfo(conn=sock, addr=("127.0.0.1", 8080), thread_id=1)


# ── add_tag ───────────────────────────────────────────────────────────────────

class TestAddTag:
    def test_add_tag_without_value(self):
        client = make_client()
        result = client.add_tag("admin")
        assert result is True
        assert client.has_tag("admin")

    def test_add_tag_with_value(self):
        client = make_client()
        client.add_tag("role", value="moderator")
        assert client.get_tag("role") == "moderator"

    def test_add_tag_value_none_by_default(self):
        client = make_client()
        client.add_tag("guest")
        assert client.get_tag("guest") is None

    def test_add_duplicate_returns_false(self):
        client = make_client()
        client.add_tag("admin")
        result = client.add_tag("admin")
        assert result is False

    def test_add_duplicate_does_not_overwrite(self):
        client = make_client()
        client.add_tag("role", value="admin")
        client.add_tag("role", value="guest")
        assert client.get_tag("role") == "admin"

    def test_add_multiple_tags(self):
        client = make_client()
        client.add_tag("admin")
        client.add_tag("verified")
        client.add_tag("role", value="mod")
        assert client.has_tag("admin")
        assert client.has_tag("verified")
        assert client.get_tag("role") == "mod"


# ── has_tag ───────────────────────────────────────────────────────────────────

class TestHasTag:
    def test_has_tag_true(self):
        client = make_client()
        client.add_tag("admin")
        assert client.has_tag("admin") is True

    def test_has_tag_false(self):
        client = make_client()
        assert client.has_tag("admin") is False

    def test_has_tag_after_remove(self):
        client = make_client()
        client.add_tag("admin")
        client.remove_tag("admin")
        assert client.has_tag("admin") is False


# ── has_all_tags ──────────────────────────────────────────────────────────────

class TestHasAllTags:
    def test_has_all_tags_true(self):
        client = make_client()
        client.add_tag("admin")
        client.add_tag("verified")
        assert client.has_all_tags(["admin", "verified"]) is True

    def test_has_all_tags_partial(self):
        client = make_client()
        client.add_tag("admin")
        assert client.has_all_tags(["admin", "verified"]) is False

    def test_has_all_tags_empty_list(self):
        client = make_client()
        assert client.has_all_tags([]) is True

    def test_has_all_tags_none_present(self):
        client = make_client()
        assert client.has_all_tags(["admin", "mod"]) is False


# ── has_any_tags ──────────────────────────────────────────────────────────────

class TestHasAnyTags:
    def test_has_any_tags_one_match(self):
        client = make_client()
        client.add_tag("admin")
        assert client.has_any_tags(["admin", "mod"]) is True

    def test_has_any_tags_all_match(self):
        client = make_client()
        client.add_tag("admin")
        client.add_tag("mod")
        assert client.has_any_tags(["admin", "mod"]) is True

    def test_has_any_tags_no_match(self):
        client = make_client()
        assert client.has_any_tags(["admin", "mod"]) is False

    def test_has_any_tags_empty_list(self):
        client = make_client()
        assert client.has_any_tags([]) is False


# ── get_tag ───────────────────────────────────────────────────────────────────

class TestGetTag:
    def test_get_existing_tag(self):
        client = make_client()
        client.add_tag("role", value="admin")
        assert client.get_tag("role") == "admin"

    def test_get_nonexistent_tag(self):
        client = make_client()
        assert client.get_tag("role") is None

    def test_get_tag_any_type(self):
        client = make_client()
        client.add_tag("score", value=42)
        client.add_tag("data", value={"key": "val"})
        assert client.get_tag("score") == 42
        assert client.get_tag("data") == {"key": "val"}


# ── remove_tag ────────────────────────────────────────────────────────────────

class TestRemoveTag:
    def test_remove_existing_tag(self):
        client = make_client()
        client.add_tag("admin")
        result = client.remove_tag("admin")
        assert result is True
        assert not client.has_tag("admin")

    def test_remove_nonexistent_tag(self):
        client = make_client()
        result = client.remove_tag("admin")
        assert result is False

    def test_remove_does_not_affect_others(self):
        client = make_client()
        client.add_tag("admin")
        client.add_tag("verified")
        client.remove_tag("admin")
        assert client.has_tag("verified")


# ── clear_tags ────────────────────────────────────────────────────────────────

class TestClearTags:
    def test_clear_all_tags(self):
        client = make_client()
        client.add_tag("admin")
        client.add_tag("verified")
        client.add_tag("role", value="mod")
        client.clear_tags()
        assert not client.has_tag("admin")
        assert not client.has_tag("verified")
        assert not client.has_tag("role")

    def test_clear_empty_tags(self):
        client = make_client()
        client.clear_tags()  # Should not raise
        assert client.has_all_tags([]) is True

    def test_add_after_clear(self):
        client = make_client()
        client.add_tag("admin")
        client.clear_tags()
        result = client.add_tag("admin")
        assert result is True  # Should succeed after clear
