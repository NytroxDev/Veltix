"""Tests for veltix.internal.compatibility — Version and COMPATIBILITY table."""

import pytest

from veltix.internal.compatibility import COMPATIBILITY, Version


class TestVersionFromStr:
    def test_parse_basic(self):
        v = Version.from_str("1.8.0")
        assert v == Version(1, 8, 0)

    def test_parse_with_v_prefix(self):
        v = Version.from_str("v1.8.0")
        assert v == Version(1, 8, 0)

    def test_parse_components(self):
        v = Version.from_str("2.10.3")
        assert v.major == 2
        assert v.minor == 10
        assert v.patch == 3

    def test_parse_zeros(self):
        v = Version.from_str("0.0.0")
        assert v == Version(0, 0, 0)

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            Version.from_str("not_a_version")

    def test_parse_truncates_extra_components(self):
        """Only major.minor.patch should be used."""
        v = Version.from_str("1.2.3.4.5")
        assert v == Version(1, 2, 3)


class TestVersionHash:
    def test_hashable(self):
        v = Version(1, 8, 0)
        assert hash(v) is not None

    def test_usable_as_dict_key(self):
        d = {Version(1, 8, 0): "test"}
        assert d[Version(1, 8, 0)] == "test"

    def test_different_versions_different_hash(self):
        assert hash(Version(1, 8, 0)) != hash(Version(1, 8, 1))

    def test_same_version_same_hash(self):
        assert hash(Version(1, 8, 0)) == hash(Version(1, 8, 0))


class TestVersionStr:
    def test_str(self):
        assert str(Version(1, 8, 0)) == "1.8.0"

    def test_repr(self):
        assert repr(Version(1, 8, 0)) == "Version(1, 8, 0)"


class TestVersionIsCompatible:
    def test_compatible_with_itself(self):
        v = Version(1, 8, 0)
        assert v.is_compatible(Version(1, 8, 0)) is True

    def test_incompatible_different_patch(self):
        v = Version(1, 8, 0)
        assert v.is_compatible(Version(1, 8, 1)) is False

    def test_incompatible_different_minor(self):
        v = Version(1, 8, 0)
        assert v.is_compatible(Version(1, 7, 0)) is False

    def test_incompatible_different_major(self):
        v = Version(1, 8, 0)
        assert v.is_compatible(Version(2, 8, 0)) is False

    def test_unknown_version_returns_none(self):
        """Version not in COMPATIBILITY table should return None."""
        v = Version(99, 99, 99)
        assert v.is_compatible(Version(99, 99, 99)) is None

    def test_cross_compatibility(self):
        """If a version declares another as compatible, it should return True."""
        v1 = Version(1, 8, 0)
        v2 = Version(1, 8, 1)
        original = COMPATIBILITY.get(v1, [])
        try:
            COMPATIBILITY[v1] = [v1, v2]
            assert v1.is_compatible(v2) is True
        finally:
            COMPATIBILITY[v1] = original


class TestCompatibilityTable:
    def test_current_version_in_table(self):
        """Current version should always be in the compatibility table."""
        from veltix import __version__

        current = Version.from_str(__version__)
        assert current in COMPATIBILITY

    def test_current_version_compatible_with_itself(self):
        """Current version should be compatible with itself."""
        from veltix import __version__

        current = Version.from_str(__version__)
        assert current.is_compatible(current) is True
