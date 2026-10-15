"""Unit tests for benchmark environment capture (reproducibility context)."""

from __future__ import annotations

from veltix.benchmark import utils
from veltix.benchmark.export import _get_system_info, build_json


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
