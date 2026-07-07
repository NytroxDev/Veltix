from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Optional

if TYPE_CHECKING:
    from veltix.socket_core.core import SocketCore

_registry: dict[str, type[Benchmark]] = {}


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

    def __init__(
        self,
        config: Optional[dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> None:
        self.config: dict[str, Any] = config if config is not None else {}
        self._instance_name: Optional[str] = name

    @property
    def benchmark_name(self) -> str:
        """Return instance-level name if set, otherwise class-level name."""
        return self._instance_name if self._instance_name is not None else self.name

    @abstractmethod
    def run(self, backend: SocketCore) -> Any:
        """Execute the benchmark and return a result object."""

    @classmethod
    def get(cls, name: str) -> type[Benchmark]:
        """Look up a benchmark class by name."""
        if name not in _registry:
            raise KeyError(f"Unknown benchmark: {name!r}. Available: {list(_registry)}")
        return _registry[name]

    @classmethod
    def all(cls) -> list[type[Benchmark]]:
        """Return all registered benchmark classes."""
        return list(_registry.values())

    @classmethod
    def names(cls) -> list[str]:
        """Return names of all registered benchmarks."""
        return list(_registry.keys())
