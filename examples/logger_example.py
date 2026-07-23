"""
Logger Example for Veltix

Demonstrates standalone logger usage and bus-integrated logging.
"""

from veltix import Logger, LoggerConfig, LogLevel

logger = Logger.get_instance(
    LoggerConfig(level=LogLevel.DEBUG, show_timestamp=True)
)

logger.trace("This is a trace message")
logger.debug("This is a debug message")
logger.info("Server starting...")
logger.success("Server is ready!")
logger.warning("Buffer almost full")
logger.error("Connection lost")
logger.critical("Out of memory")
