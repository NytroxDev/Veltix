"""Tests for Logger functionality."""

import io

import pytest

from veltix import Logger, LoggerConfig, LogLevel
from veltix.internal.bus import VeltixBus


class TestLogger:
    def test_logger_singleton(self, reset_logger):
        logger1 = Logger.get_instance()
        logger2 = Logger.get_instance()
        assert logger1 is logger2

    def test_logger_levels(self, reset_logger):
        logger = Logger.get_instance()
        logger.trace("Trace message")
        logger.debug("Debug message")
        logger.info("Info message")
        logger.success("Success message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

    def test_logger_level_filtering(self, reset_logger):
        config = LoggerConfig(level=LogLevel.WARNING)
        logger = Logger.get_instance(config)
        logger.trace("Should be filtered")
        logger.debug("Should be filtered")
        logger.info("Should be filtered")
        logger.warning("Should pass")
        logger.error("Should pass")

    def test_logger_enable_disable(self, reset_logger):
        logger = Logger.get_instance()
        logger.info("Enabled message")
        logger.disable()
        logger.info("Disabled message")
        logger.enable()
        logger.info("Re-enabled message")

    def test_enable_after_disabled_config_restores_output(self, reset_logger):
        """enable() must restore output when logging was disabled via config."""
        stream = io.StringIO()
        logger = Logger.get_instance(LoggerConfig(enabled=False, stream=stream))
        logger.enable()
        logger.info("hello after enable")
        assert "hello after enable" in stream.getvalue()

    def test_logger_printf_style_arguments(self, reset_logger):
        """Log calls accept %-style formatting arguments like stdlib logging."""
        stream = io.StringIO()
        logger = Logger.get_instance(LoggerConfig(stream=stream, level=LogLevel.DEBUG))
        logger.info("Value: %d", 42)
        assert "Value: 42" in stream.getvalue()

    def test_logger_mapping_arguments(self, reset_logger):
        """A single mapping argument applies to named placeholders."""
        stream = io.StringIO()
        logger = Logger.get_instance(LoggerConfig(stream=stream, level=LogLevel.DEBUG))
        logger.info("hello %(name)s", {"name": "world"})
        assert "hello world" in stream.getvalue()

    def test_logger_message_without_args_unchanged(self, reset_logger):
        """A message with no args stays untouched (lone % is fine)."""
        stream = io.StringIO()
        logger = Logger.get_instance(LoggerConfig(stream=stream, level=LogLevel.DEBUG))
        logger.info("100% ready")
        assert "100% ready" in stream.getvalue()

    def test_bus_printf_style_arguments(self, reset_logger):
        """bus.error("... %s", exc) must format the args, not raise TypeError."""
        stream = io.StringIO()
        Logger.get_instance(LoggerConfig(stream=stream, level=LogLevel.DEBUG))
        bus = VeltixBus()
        bus.error("Something went wrong: %s", ValueError("boom"))
        assert "Something went wrong: boom" in stream.getvalue()

    def test_config_rejects_invalid_level(self):
        """level must be a LogLevel member, not a bare int or string."""
        with pytest.raises(TypeError, match="LogLevel"):
            LoggerConfig(level=25)
        with pytest.raises(TypeError, match="LogLevel"):
            LoggerConfig(level="INFO")

    def test_config_rejects_empty_file_path(self):
        """file_path="" must raise a clear ValueError, not be silently skipped."""
        with pytest.raises(ValueError, match="file_path"):
            LoggerConfig(file_path="")

    def test_config_rejects_non_path_file_path(self):
        """file_path must be a str or Path."""
        with pytest.raises(TypeError, match="file_path"):
            LoggerConfig(file_path=123)

    def test_config_rejects_non_writable_stream(self):
        """stream must expose a write() method."""
        with pytest.raises(TypeError, match="write"):
            LoggerConfig(stream=object())
        with pytest.raises(TypeError, match="write"):
            LoggerConfig(stream=42)

    def test_setup_reports_unopenable_log_file_clearly(self, reset_logger):
        """A missing directory must raise a clear ValueError, not a raw OSError."""
        with pytest.raises(ValueError, match="cannot open log file"):
            Logger.get_instance(LoggerConfig(file_path="/nonexistent_dir_xyz_veltix/log.txt"))

    def test_logger_set_level(self, reset_logger):
        logger = Logger.get_instance()
        logger.set_level(LogLevel.ERROR)
        logger.debug("Should be filtered")
        logger.error("Should pass")
        logger.set_level(LogLevel.DEBUG)
        logger.debug("Should pass now")

    def test_logger_stats(self, reset_logger):
        logger = Logger.get_instance()
        logger.info("Info 1")
        logger.info("Info 2")
        logger.error("Error 1")
        stats = logger.get_stats()
        assert stats[LogLevel.INFO] == 2
        assert stats[LogLevel.ERROR] == 1
