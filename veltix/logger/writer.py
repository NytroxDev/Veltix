"""Log writing to console and file."""

from __future__ import annotations

import atexit
import contextlib
import threading
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Optional, TextIO, Union

if TYPE_CHECKING:
    from .config import LoggerConfig


class Writer:
    """Handles writing logs to console and file."""

    def __init__(self, config: LoggerConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._file_path: Optional[Path] = Path(config.file_path) if config.file_path else None

        self._file_handle: Optional[TextIO] = None
        self._current_size = 0

        self._buffer: Optional[deque] = None
        self._flush_thread: Optional[threading.Thread] = None
        self._should_stop = threading.Event()

        if self._file_path:
            self._init_file()
            if config.async_write:
                self._init_async_writer()

        atexit.register(self._cleanup)

    def _init_file(self) -> None:
        file_path = self._file_path
        if file_path is None:
            return
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_handle = open(file_path, "a", encoding="utf-8", buffering=8192)  # noqa: SIM115
            if file_path.exists():
                self._current_size = file_path.stat().st_size
        except (OSError, PermissionError) as e:
            print(f"⚠️  Failed to open log file: {e}")
            self._file_path = None

    def _init_async_writer(self) -> None:
        self._buffer = deque(maxlen=self.config.buffer_size)
        self._flush_thread = threading.Thread(
            target=self._flush_worker, daemon=True, name="VeltixLoggerFlush"
        )
        self._flush_thread.start()

    def _flush_worker(self) -> None:
        while not self._should_stop.is_set():
            time.sleep(0.1)
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        if not self._buffer or not self._file_handle:
            return

        with self._lock:
            if not self._buffer:
                return
            messages = list(self._buffer)
            self._buffer.clear()

        try:
            for message in messages:
                with self._lock:
                    self._write_to_file_direct(message)
        except Exception as e:
            print(f"⚠️  Error flushing log buffer: {e}")

    def write(self, message: str) -> None:
        if self.config.stream:
            with contextlib.suppress(Exception):
                print(message, file=self.config.stream)

        if self._file_path:
            if self.config.async_write:
                self._write_to_buffer(message)
            else:
                self._write_to_file(message)

    def _write_to_buffer(self, message: str) -> None:
        with self._lock:
            if self._buffer is not None:
                self._buffer.append(message + "\n")

    def _write_to_file(self, message: str) -> None:
        with self._lock:
            self._write_to_file_direct(message + "\n")

    def _write_to_file_direct(self, message: str) -> None:
        if not self._file_handle:
            return

        try:
            self._file_handle.write(message)
            self._file_handle.flush()
            self._current_size += len(message.encode("utf-8"))

            if self._current_size >= self.config.file_rotation_size:
                self._rotate_file()
        except Exception as e:
            print(f"⚠️  Error writing to log file: {e}")

    def _rotate_file(self) -> None:
        with self._lock:
            try:
                if self._file_handle:
                    self._file_handle.close()

                base_path = self._file_path
                if base_path is None:
                    return
                oldest = base_path.with_suffix(
                    f"{base_path.suffix}.{self.config.file_backup_count}"
                )
                if oldest.exists():
                    oldest.unlink()

                for i in range(self.config.file_backup_count - 1, 0, -1):
                    old_path = base_path.with_suffix(f"{base_path.suffix}.{i}")
                    new_path = base_path.with_suffix(f"{base_path.suffix}.{i + 1}")
                    if old_path.exists():
                        old_path.rename(new_path)

                if base_path.exists():
                    base_path.rename(base_path.with_suffix(f"{base_path.suffix}.1"))

                self._file_handle = open(base_path, "a", encoding="utf-8", buffering=8192)  # noqa: SIM115
                self._current_size = 0
            except Exception as e:
                print(f"⚠️  Error rotating log file: {e}")

    def _cleanup(self) -> None:
        if self._flush_thread:
            self._should_stop.set()
            self._flush_thread.join(timeout=2.0)
            self._flush_buffer()

        if self._file_handle:
            with contextlib.suppress(Exception):
                self._file_handle.close()
