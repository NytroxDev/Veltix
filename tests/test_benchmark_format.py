"""Unit tests for the benchmark file format versioning."""

from __future__ import annotations

import json

import pytest

from veltix.benchmark.compare import _format_version, cmd_compare


def _write(tmp_path: pytest.TempPathFactory, name: str, data: dict) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


class TestFormatVersion:
    def test_missing_field_is_legacy_zero(self) -> None:
        assert _format_version({}) == 0
        assert _format_version({"results": {}}) == 0

    def test_parses_integer_and_numeric_string(self) -> None:
        assert _format_version({"format_version": 1}) == 1
        assert _format_version({"format_version": "2"}) == 2

    def test_junk_field_is_legacy_zero(self) -> None:
        assert _format_version({"format_version": "abc"}) == 0


class TestCompareValidation:
    def test_rejects_mismatched_format_versions(
        self, tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
    ) -> None:
        a = _write(tmp_path, "a.json", {"format_version": 1, "results": {}})
        b = _write(tmp_path, "b.json", {"format_version": 2, "results": {}})

        with pytest.raises(SystemExit) as exc:
            cmd_compare(a, b)

        assert exc.value.code == 1
        assert "Format version mismatch" in capsys.readouterr().out

    def test_rejects_legacy_vs_new_format(self, tmp_path: pytest.TempPathFactory) -> None:
        a = _write(tmp_path, "a.json", {"results": {}})
        b = _write(tmp_path, "b.json", {"format_version": 1, "results": {}})

        with pytest.raises(SystemExit):
            cmd_compare(a, b)

    def test_accepts_matching_format_versions(
        self, tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
    ) -> None:
        data = {"format_version": 1, "veltix_version": "3.0.0", "results": {}}
        a = _write(tmp_path, "a.json", data)
        b = _write(tmp_path, "b.json", data)

        cmd_compare(a, b)

        out = capsys.readouterr().out
        assert "SUMMARY" in out
        assert "Format" in out

    def test_accepts_two_legacy_files(self, tmp_path: pytest.TempPathFactory) -> None:
        a = _write(tmp_path, "a.json", {"results": {}})
        b = _write(tmp_path, "b.json", {"results": {}})

        cmd_compare(a, b)  # no SystemExit
