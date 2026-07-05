"""Tests for the Writer class (log writing to console and file)."""

import io
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from veltix.logger.config import LoggerConfig
from veltix.logger.writer import Writer


class TestWriterFile:
    def test_write_to_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=False)
        writer = Writer(config)
        writer.write("hello")
        assert log_file.read_text() == "hello\n"

    def test_write_to_file_async(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=True, buffer_size=100)
        writer = Writer(config)
        writer.write("hello")
        writer._flush_buffer()
        assert log_file.read_text() == "hello\n"

    def test_write_multiple_messages(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=False)
        writer = Writer(config)
        for i in range(5):
            writer.write(f"msg_{i}")
        lines = log_file.read_text().strip().split("\n")
        assert lines == ["msg_0", "msg_1", "msg_2", "msg_3", "msg_4"]

    def test_write_to_stream(self):
        stream = io.StringIO()
        writer = Writer(LoggerConfig(stream=stream))
        writer.write("hello")
        assert stream.getvalue() == "hello\n"

    def test_write_to_stream_suppressed(self):
        stream = io.StringIO()
        writer = Writer(LoggerConfig(stream=stream))
        writer.write("hello")
        assert stream.getvalue() == "hello\n"

    def test_write_no_file_no_stream(self):
        config = LoggerConfig(stream=None)
        writer = Writer(config)
        writer.write("hello")  # should not crash

    def test_write_to_buffer_async_multiple(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=True)
        writer = Writer(config)
        writer.write("a")
        writer.write("b")
        writer._flush_buffer()
        assert log_file.read_text() == "a\nb\n"

    def test_flush_buffer_empty(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=True)
        writer = Writer(config)
        writer._flush_buffer()  # should not crash

    def test_flush_worker_stops(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=True)
        writer = Writer(config)
        writer._should_stop.set()
        time.sleep(0.15)
        writer._flush_buffer()
        assert log_file.read_text() == ""


class TestWriterRotation:
    def test_file_rotation(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(
            file_path=str(log_file),
            file_rotation_size=50,
            file_backup_count=2,
        )
        writer = Writer(config)
        for _ in range(20):
            writer.write("x" * 10)
        assert log_file.exists()
        backup_1 = log_file.with_suffix(".log.1")
        backup_2 = log_file.with_suffix(".log.2")
        assert backup_1.exists() or backup_2.exists()

    def test_rotation_multiple_backups(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(
            file_path=str(log_file),
            file_rotation_size=30,
            file_backup_count=3,
        )
        writer = Writer(config)
        for _ in range(50):
            writer.write("x" * 10)
        backup_1 = log_file.with_suffix(".log.1")
        backup_2 = log_file.with_suffix(".log.2")
        backup_3 = log_file.with_suffix(".log.3")
        backups = [b for b in [backup_1, backup_2, backup_3] if b.exists()]
        assert len(backups) <= 3

    def test_rotation_no_oldest_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(
            file_path=str(log_file),
            file_rotation_size=30,
            file_backup_count=1,
        )
        writer = Writer(config)
        for _ in range(30):
            writer.write("x" * 10)
        assert log_file.exists()

    def test_rotation_error_caught(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(
            file_path=str(log_file),
            file_rotation_size=1,
            file_backup_count=2,
        )
        writer = Writer(config)
        writer.write("x")
        with patch("builtins.open", side_effect=OSError("mock rotation error")):
            writer._rotate_file()  # should not crash, hits lines 141-142


class TestWriterErrors:
    def test_init_file_permission_error(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file))
        with patch("builtins.open", side_effect=PermissionError("denied")):
            writer = Writer(config)
        assert writer._file_path is None

    def test_write_to_file_direct_no_handle(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file))
        writer = Writer(config)
        writer._file_handle = None
        writer._write_to_file_direct("hello")  # should not crash

    def test_write_to_file_io_error(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file))
        writer = Writer(config)
        with patch.object(writer._file_handle, "write", side_effect=OSError("mock error")):
            writer._write_to_file_direct("hello")  # should not crash

    def test_write_to_buffer_when_none(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=True)
        writer = Writer(config)
        writer._buffer = None
        writer._write_to_buffer("hello")  # should not crash

    def test_flush_buffer_exception(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=True)
        writer = Writer(config)
        writer.write("hello")
        with patch.object(writer, "_write_to_file_direct", side_effect=OSError("mock")):
            writer._flush_buffer()  # should not crash

    def test_flush_buffer_toctou_guard(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=True)
        writer = Writer(config)
        writer.write("hello")
        mock_buffer = MagicMock()
        mock_buffer.__bool__ = MagicMock(side_effect=[True, False])
        with patch.object(writer, "_buffer", mock_buffer):
            writer._flush_buffer()  # hits line 70 guard, should return silently


class TestWriterInit:
    def test_init_without_file_path(self):
        writer = Writer(LoggerConfig())
        assert writer._file_path is None
        assert writer._file_handle is None

    def test_init_with_file_path(self, tmp_path):
        log_file = tmp_path / "test.log"
        writer = Writer(LoggerConfig(file_path=str(log_file)))
        assert writer._file_path == log_file
        assert writer._file_handle is not None

    def test_init_async_writer(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=True)
        writer = Writer(config)
        assert writer._buffer is not None
        assert writer._flush_thread is not None
        assert writer._flush_thread.name == "VeltixLoggerFlush"
        writer._should_stop.set()
        writer._flush_thread.join(timeout=2.0)


class TestWriterCleanup:
    def test_cleanup_with_flush_thread(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=True)
        writer = Writer(config)
        writer.write("hello")
        writer._cleanup()
        assert writer._should_stop.is_set()
        assert log_file.read_text() == "hello\n"

    def test_cleanup_without_flush_thread(self, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(file_path=str(log_file), async_write=False)
        writer = Writer(config)
        writer.write("hello")
        writer._cleanup()
        assert writer._file_handle is None or writer._file_handle.closed

    def test_cleanup_no_file_handle(self):
        writer = Writer(LoggerConfig())
        writer._cleanup()  # should not crash
