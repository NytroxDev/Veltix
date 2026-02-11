"""Network utility functions."""

import socket
from typing import Optional

from veltix.logger.core import Logger


def recv(conn: socket.socket, buf_size: int = 1024) -> Optional[bytes]:
    """
    Receive data from a socket with error handling.

    Args:
        conn: Socket connection to receive from
        buf_size: Buffer size in bytes (default: 1024)

    Returns:
        Received data as bytes, or None if connection closed or error occurred
    """
    logger = Logger.get_instance()
    
    try:
        logger.debug(f"Attempting to receive data from socket {conn.getpeername() if hasattr(conn, 'getpeername') else 'unknown'} with buffer size {buf_size}")
        data = conn.recv(buf_size)
        if not data:  # Connection closed cleanly
            logger.info("Connection closed cleanly by peer")
            return None
        logger.debug(f"Successfully received {len(data)} bytes")
        return data
    except socket.timeout:
        # Timeout is expected with socket.settimeout(), not an error
        logger.debug("Socket receive timeout occurred")
        return None
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        # Connection issues
        logger.warning(f"Connection issue occurred: {type(e).__name__}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during socket receive: {type(e).__name__}: {e}")
        return None
