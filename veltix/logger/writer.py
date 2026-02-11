"""Log writing to file and console."""

import atexit
import threading
from collections import deque
from typing import Optional, TextIO

from veltix.logger.config import LoggerConfig


class Writer:
    """Handles writing logs to console and file."""

    def __init__(self, config: LoggerConfig):
        """
        Initialize writer.

        Args:
            config: Logger configuration
        """
        self.config = config
        self._lock = threading.RLock()

        # File handling
        self._file_handle: Optional[TextIO] = None
        self._current_size = 0

        # Async writing
        self._buffer: Optional[deque] = None
        self._flush_thread: Optional[threading.Thread] = None
        self._should_stop = threading.Event()

        # Initialize file
        if config.file_path:
            self._init_file()

            # Start async writer if enabled
            if config.async_write:
                self._init_async_writer()

        # Register cleanup
        atexit.register(self._cleanup)

    def _init_file(self) -> None:
        """Initialize log file."""
        try:
            # Create parent directories
            self.config.file_path.parent.mkdir(parents=True, exist_ok=True)

            # Open file in append mode
            self._file_handle = open(
                self.config.file_path, "a", encoding="utf-8", buffering=8192
            )

            # Get current size
            if self.config.file_path.exists():
                self._current_size = self.config.file_path.stat().st_size

        except (OSError, PermissionError) as e:
            print(f"⚠️  Failed to open log file: {e}")
            self.config.file_path = None

    def _init_async_writer(self) -> None:
        """Initialize async writing thread."""
        self._buffer = deque(maxlen=self.config.buffer_size)
        self._flush_thread = threading.Thread(
            target=self._flush_worker, daemon=True, name="VeltixLoggerFlush"
        )
        self._flush_thread.start()

    def _flush_worker(self) -> None:
        """Worker thread for async file writing."""
        import time

        while not self._should_stop.is_set():
            time.sleep(0.1)  # Flush every 100ms
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """Flush buffered messages to file."""
        if not self._buffer or not self._file_handle:
            return

        with self._lock:
            if not self._buffer:
                return

            # Get all messages
            messages = list(self._buffer)
            self._buffer.clear()

        # Write to file
        try:
            for message in messages:
                self._write_to_file_direct(message)
        except Exception as e:
            print(f"⚠️  Error flushing log buffer: {e}")

    def write(self, message: str) -> None:
        """
        Write a log message.

        Args:
            message: Formatted message to write
        """
        # Write to console
        if self.config.stream:
            try:
                print(message, file=self.config.stream)
            except Exception:
                pass

        # Write to file
        if self.config.file_path:
            if self.config.async_write:
                self._write_to_buffer(message)
            else:
                self._write_to_file(message)

    def _write_to_buffer(self, message: str) -> None:
        """Add message to async buffer."""
        with self._lock:
            if self._buffer is not None:
                self._buffer.append(message + "\n")

    def _write_to_file(self, message: str) -> None:
        """Write message to file synchronously."""
        with self._lock:
            self._write_to_file_direct(message + "\n")

    def _write_to_file_direct(self, message: str) -> None:
        """Write to file without locking (assumes lock held)."""
        if not self._file_handle:
            return

        try:
            # Write message
            self._file_handle.write(message)
            self._file_handle.flush()

            # Update size
            self._current_size += len(message.encode("utf-8"))

            # Check rotation
            if self._current_size >= self.config.file_rotation_size:
                self._rotate_file()

        except Exception as e:
            print(f"⚠️  Error writing to log file: {e}")

    def _rotate_file(self) -> None:
        """Rotate log files."""
        try:
            # Close current file
            if self._file_handle:
                self._file_handle.close()

            # Rotate backups
            base_path = self.config.file_path

            # Delete oldest backup
            oldest = base_path.with_suffix(
                f"{base_path.suffix}.{self.config.file_backup_count}"
            )
            if oldest.exists():
                oldest.unlink()

            # Shift backups
            for i in range(self.config.file_backup_count - 1, 0, -1):
                old_path = base_path.with_suffix(f"{base_path.suffix}.{i}")
                new_path = base_path.with_suffix(f"{base_path.suffix}.{i + 1}")
                if old_path.exists():
                    old_path.rename(new_path)

            # Rename current to .1
            if base_path.exists():
                base_path.rename(base_path.with_suffix(f"{base_path.suffix}.1"))

            # Open new file
            self._file_handle = open(base_path, "a", encoding="utf-8", buffering=8192)
            self._current_size = 0

        except Exception as e:
            print(f"⚠️  Error rotating log file: {e}")

    def _cleanup(self) -> None:
        """Cleanup on shutdown."""
        # Stop async writer
        if self._flush_thread:
            self._should_stop.set()
            self._flush_thread.join(timeout=2.0)
            self._flush_buffer()

        # Close file
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass
