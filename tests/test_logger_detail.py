"""Detailed tests for Logger submodules: configure, config validation, Formatter, Writer, LogLevel."""

from pathlib import Path

import pytest

from veltix import Logger, LoggerConfig, LogLevel


class TestLogLevelStr:
    def test_str_returns_name(self):
        assert str(LogLevel.TRACE) == "TRACE"
        assert str(LogLevel.DEBUG) == "DEBUG"
        assert str(LogLevel.INFO) == "INFO"
        assert str(LogLevel.SUCCESS) == "SUCCESS"
        assert str(LogLevel.WARNING) == "WARNING"
        assert str(LogLevel.ERROR) == "ERROR"
        assert str(LogLevel.CRITICAL) == "CRITICAL"

    def test_repr(self):
        assert repr(LogLevel.INFO) == "<LogLevel.INFO: 20>"


class TestLoggerConfigValidation:
    """Test LoggerConfig __post_init__ validation."""

    def test_default_config(self):
        config = LoggerConfig()
        assert config.level == LogLevel.INFO
        assert config.enabled is True
        assert config.file_path is None

    def test_file_path_conversion(self):
        config = LoggerConfig(file_path="/tmp/test.log")
        assert isinstance(config.file_path, Path)
        assert str(config.file_path) == "/tmp/test.log"

    def test_file_rotation_size_zero_raises(self):
        with pytest.raises(ValueError, match="file_rotation_size must be positive"):
            LoggerConfig(file_rotation_size=0)

    def test_file_rotation_size_negative_raises(self):
        with pytest.raises(ValueError, match="file_rotation_size must be positive"):
            LoggerConfig(file_rotation_size=-1)

    def test_file_backup_count_zero_raises(self):
        with pytest.raises(ValueError, match="file_backup_count must be positive"):
            LoggerConfig(file_backup_count=0)

    def test_file_backup_count_negative_raises(self):
        with pytest.raises(ValueError, match="file_backup_count must be positive"):
            LoggerConfig(file_backup_count=-1)


class TestLoggerConfigure:
    def test_configure_changes_level(self, reset_logger):
        logger = Logger.get_instance()
        logger.configure(LoggerConfig(level=LogLevel.ERROR))
        assert logger.config.level == LogLevel.ERROR

    def test_configure_resets_stats(self, reset_logger):
        logger = Logger.get_instance()
        logger.info("test")
        assert logger.get_stats()[LogLevel.INFO] == 1
        logger.configure(LoggerConfig())
        assert logger.get_stats()[LogLevel.INFO] == 0

    def test_configure_creates_new_handler(self, reset_logger):
        logger = Logger.get_instance()
        old_handler = logger._console_handler
        logger.configure(LoggerConfig(level=LogLevel.DEBUG))
        assert logger._console_handler is not old_handler

    def test_configure_creates_new_formatter(self, reset_logger):
        logger = Logger.get_instance()
        old_handler = logger._console_handler
        logger.configure(LoggerConfig(use_colors=False))
        assert logger._console_handler is not old_handler

    def test_configure_disables_logging(self, reset_logger):
        logger = Logger.get_instance()
        logger.configure(LoggerConfig(enabled=False))
        assert logger.config.enabled is False

    def test_configure_changes_use_colors(self, reset_logger):
        logger = Logger.get_instance()
        logger.configure(LoggerConfig(use_colors=False))
        assert logger.config.use_colors is False


class TestLoggerFileRotation:
    def test_file_rotation_config(self, reset_logger, tmp_path):
        log_file = tmp_path / "test.log"
        config = LoggerConfig(
            level=LogLevel.DEBUG,
            file_path=str(log_file),
            file_rotation_size=1024,
            file_backup_count=2,
        )
        logger = Logger.get_instance(config)
        assert logger.config.file_path == log_file
        assert logger.config.file_rotation_size == 1024
        assert logger.config.file_backup_count == 2


class TestLoggerGetInstance:
    def test_get_instance_returns_singleton(self, reset_logger):
        logger1 = Logger.get_instance()
        logger2 = Logger.get_instance()
        assert logger1 is logger2

    def test_get_instance_with_config(self, reset_logger):
        config = LoggerConfig(level=LogLevel.ERROR)
        logger = Logger.get_instance(config)
        assert logger.config.level == LogLevel.ERROR

    def test_get_instance_without_config_uses_default(self, reset_logger):
        logger = Logger.get_instance()
        assert logger.config.level == LogLevel.INFO  # default from conftest override

    def test_get_instance_with_config_after_init(self, reset_logger):
        """Passing config to get_instance after logger exists updates config."""
        logger = Logger.get_instance(LoggerConfig(level=LogLevel.INFO))
        assert logger.config.level == LogLevel.INFO
        logger = Logger.get_instance(LoggerConfig(level=LogLevel.ERROR))
        assert logger.config.level == LogLevel.ERROR


class TestLoggerFiltering:
    """Test that log level filtering works correctly."""

    def test_trace_filtered_when_level_debug(self, reset_logger):
        logger = Logger.get_instance(LoggerConfig(level=LogLevel.DEBUG))
        logger.trace("should be filtered")
        assert logger.get_stats()[LogLevel.TRACE] == 0

    def test_debug_passes_when_level_debug(self, reset_logger):
        logger = Logger.get_instance(LoggerConfig(level=LogLevel.DEBUG))
        logger.debug("should pass")
        assert logger.get_stats()[LogLevel.DEBUG] == 1

    def test_success_logging(self, reset_logger):
        logger = Logger.get_instance()
        logger.success("success message")
        assert logger.get_stats()[LogLevel.SUCCESS] == 1

    def test_level_ordering(self):
        """Verify level ordering for filtering."""
        assert LogLevel.TRACE < LogLevel.DEBUG
        assert LogLevel.DEBUG < LogLevel.INFO
        assert LogLevel.INFO < LogLevel.SUCCESS
        assert LogLevel.SUCCESS < LogLevel.WARNING
        assert LogLevel.WARNING < LogLevel.ERROR
        assert LogLevel.ERROR < LogLevel.CRITICAL
