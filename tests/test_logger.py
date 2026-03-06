"""Tests for Logger functionality."""

import pytest

from veltix import Logger, LoggerConfig, LogLevel


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
