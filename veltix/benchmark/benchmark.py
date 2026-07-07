from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Type

from veltix.socket_core.core import SocketCore

if TYPE_CHECKING:
    pass

_registry: Dict[str, Type[Benchmark]] = {}


class Benchmark(ABC):
    """Base class for all benchmarks.

    Subclasses are auto-registered via their ``name`` class variable.
    """

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            _registry[cls.name] = cls

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = config if config is not None else {}

    @abstractmethod
    def run(self, backend: SocketCore) -> Any:
        """Execute the benchmark and return a result object."""

    @classmethod
    def get(cls, name: str) -> Type[Benchmark]:
        """Look up a benchmark class by name."""
        if name not in _registry:
            raise KeyError(f"Unknown benchmark: {name!r}. Available: {list(_registry)}")
        return _registry[name]

    @classmethod
    def all(cls) -> List[Type[Benchmark]]:
        """Return all registered benchmark classes."""
        return list(_registry.values())

    @classmethod
    def names(cls) -> List[str]:
        """Return names of all registered benchmarks."""
        return list(_registry.keys())
