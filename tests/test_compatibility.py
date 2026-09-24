"""Tests for veltix.internal.compatibility - protocol version helpers."""

from veltix.internal.compatibility import (
    PROTOCOL_VERSION,
    protocol_is_compatible,
    protocol_version_str,
)


class TestProtocolVersion:
    def test_protocol_version_is_tuple(self):
        assert isinstance(PROTOCOL_VERSION, tuple)
        assert len(PROTOCOL_VERSION) == 2

    def test_protocol_version_str_format(self):
        text = protocol_version_str()
        assert text == f"{PROTOCOL_VERSION[0]}.{PROTOCOL_VERSION[1]}"

    def test_same_major_compatible(self):
        assert protocol_is_compatible("1.1", (1, 0)) is True

    def test_same_major_any_minor_compatible(self):
        assert protocol_is_compatible("1.99", (1, 0)) is True
        assert protocol_is_compatible("1.5", (1, 7)) is True

    def test_forward_compat_same_major(self):
        """A future minor with the same major must be accepted."""
        assert protocol_is_compatible("1.4", (1, 2)) is True

    def test_backward_compat_same_major(self):
        """An older minor with the same major must be accepted."""
        assert protocol_is_compatible("1.0", (1, 2)) is True

    def test_different_major_incompatible(self):
        assert protocol_is_compatible("2.0", (1, 0)) is False
        assert protocol_is_compatible("0.0", (1, 0)) is False

    def test_invalid_protocol_version(self):
        assert protocol_is_compatible("not_a_version", (1, 0)) is False
        assert protocol_is_compatible("", (1, 0)) is False
        assert protocol_is_compatible("1", (1, 0)) is False

    def test_local_defaults_to_current(self):
        text = protocol_version_str()
        assert protocol_is_compatible(text) is True
