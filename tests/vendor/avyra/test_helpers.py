from enum import Enum, auto

import pytest

from veltix._vendor.avyra.core._base import _iter_members, _original_sub


class Color(Enum):
    RED = auto()
    GREEN = auto()
    BLUE = auto()


class TestIterMembers:
    def test_single_member(self):
        assert _iter_members(Color.RED) == [Color.RED]

    def test_enum_class(self):
        assert _iter_members(Color) == [Color.RED, Color.GREEN, Color.BLUE]

    def test_raises_on_plain_object(self):
        with pytest.raises(TypeError, match="Enum member or an Enum class"):
            _iter_members(42)  # type: ignore[arg-type]

    def test_raises_on_string(self):
        with pytest.raises(TypeError):
            _iter_members("nope")  # type: ignore[arg-type]

    def test_list_of_members(self):
        assert _iter_members([Color.RED, Color.BLUE]) == [Color.RED, Color.BLUE]


class TestOriginalSub:
    def test_plain_function(self):
        def f():
            pass

        assert _original_sub(f) is f

    def test_wrapper_with_original(self):
        def f():
            pass

        def wrapper():
            pass

        wrapper._original = f  # type: ignore[attr-defined]
        assert _original_sub(wrapper) is f

    def test_lambda(self):
        def f():
            pass

        assert _original_sub(f) is f
