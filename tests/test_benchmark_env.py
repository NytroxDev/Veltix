"""Unit tests for benchmark environment capture (reproducibility context)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from veltix.benchmark import cli, utils
from veltix.benchmark.export import _get_system_info, build_json

if TYPE_CHECKING:
    import pytest


class TestCpuModel:
    def test_returns_non_empty_string(self) -> None:
        model = utils.cpu_model()
        assert isinstance(model, str)
        assert model


class TestGovernor:
    def test_string_or_none(self) -> None:
        governor = utils.cpu_governor()
        assert governor is None or isinstance(governor, str)


class TestFrequency:
    def test_float_or_none(self) -> None:
        freq = utils.cpu_freq_mhz()
        assert freq is None or freq > 0


class TestLoadAverage:
    def test_three_floats_or_none(self) -> None:
        load = utils.load_average()
        assert load is None or (len(load) == 3 and all(isinstance(v, float) for v in load))


class TestAffinity:
    def test_non_empty_list_or_none(self) -> None:
        affinity = utils.process_affinity()
        assert affinity is None or (affinity and all(isinstance(cpu, int) for cpu in affinity))

    def test_target_keeps_all_when_uncapped(self) -> None:
        assert utils._affinity_target([0, 1, 2, 3], None) == [0, 1, 2, 3]

    def test_target_limits_to_first_count(self) -> None:
        assert utils._affinity_target([0, 1, 2, 3], 2) == [0, 1]

    def test_target_clamps_to_at_least_one(self) -> None:
        assert utils._affinity_target([3, 4, 5], 0) == [3]
        assert utils._affinity_target([3, 4, 5], -5) == [3]

    def test_pin_without_count_does_not_narrow(self) -> None:
        result = utils.pin_to_cpus()
        current = utils.process_affinity()
        assert result is None or result == current


class TestSystemInfo:
    def test_includes_environment_keys(self) -> None:
        info = _get_system_info()
        for key in (
            "python",
            "python_impl",
            "cpu_model",
            "cpu_mhz",
            "cpu_governor",
            "load_avg",
            "affinity",
        ):
            assert key in info

    def test_is_json_serializable(self) -> None:
        import json

        json.dumps(_get_system_info())


class TestHarnessBlock:
    def test_records_harness_settings(self) -> None:
        data = build_json(None, None, None, None, None, harness={"runs": 5, "warmup": 1})
        assert data["harness"] == {"runs": 5, "warmup": 1}

    def test_defaults_to_empty(self) -> None:
        data = build_json(None, None, None, None, None)
        assert data["harness"] == {}


class TestLoadWarning:
    def test_idle_machine_has_no_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(utils, "load_average", lambda: [1.0, 0.5, 0.4])
        assert cli._load_warning(8) is None

    def test_overloaded_machine_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(utils, "load_average", lambda: [16.0, 8.0, 4.0])
        warning = cli._load_warning(8)
        assert warning is not None
        assert "16.00" in warning

    def test_missing_load_average_has_no_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(utils, "load_average", lambda: None)
        assert cli._load_warning(8) is None
