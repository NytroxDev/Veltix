"""
Comprehensive test suite for Veltix v1.2.0

Tests all major functionality:
- Message types and registry
- Request/Response protocol
- Client/Server communication
- Ping/Pong functionality
- send_and_wait pattern
- Broadcasting
- Logger
- Error handling
"""

import time

import pytest

from veltix import (
    # System types
    PING,
    PONG,
    # Core classes
    Client,
    ClientConfig,
    # Utils
    Events,
    # Logger
    Logger,
    LoggerConfig,
    LogLevel,
    MessageType,
    MessageTypeError,
    Mode,
    # Networking
    Request,
    RequestError,
    Sender,
    SenderError,
    Server,
    ServerConfig,
    # Exceptions
    VeltixError,
)

Logger(LoggerConfig(LogLevel.TRACE))

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test"""
    yield
    # Give threads time to clean up
    time.sleep(0.1)


@pytest.fixture
def reset_logger():
    """Reset logger instance before each test"""
    Logger.reset_instance()
    yield
    Logger.reset_instance()


code = 200


@pytest.fixture
def test_message_type():
    """Create a test message type"""
    global code
    code += 1
    return MessageType(code=code, name="test_msg2", description="Test message type")


# ============================================================================
# MESSAGE TYPE TESTS
# ============================================================================


class TestMessageType:
    """Tests for MessageType and MessageTypeRegistry"""

    def test_create_message_type(self):
        """Test creating a message type"""
        msg_type = MessageType(code=250, name="custom", description="Custom type")
        assert msg_type.code == 250
        assert msg_type.name == "custom"
        assert msg_type.description == "Custom type"

    def test_message_type_auto_register(self):
        """Test that message types auto-register"""
        from veltix.network.types import MessageTypeRegistry

        MessageType(code=251, name="auto_reg")
        retrieved = MessageTypeRegistry.get(251)

        assert retrieved is not None
        assert retrieved.code == 251
        assert retrieved.name == "auto_reg"

    def test_duplicate_code_raises_error(self):
        """Test that duplicate codes raise error"""
        MessageType(code=252, name="first")

        with pytest.raises(MessageTypeError):
            MessageType(code=252, name="duplicate")

    def test_invalid_code_range(self):
        """Test that invalid codes raise error"""
        with pytest.raises(MessageTypeError):
            MessageType(code=-1, name="negative")

        with pytest.raises(MessageTypeError):
            MessageType(code=70000, name="too_big")

    def test_message_type_equality(self):
        """Test message type equality"""
        msg1 = MessageType(code=253, name="type1")
        msg2 = MessageType(code=254, name="type2")

        # Same code = equal
        from veltix.network.types import MessageTypeRegistry

        msg1_copy = MessageTypeRegistry.get(253)
        assert msg1 == msg1_copy

        # Different code = not equal
        assert msg1 != msg2

    def test_system_types_exist(self):
        """Test that system types are registered"""
        assert PING.code == 0
        assert PONG.code == 1
        assert PING.name == "ping"
        assert PONG.name == "pong"


# ============================================================================
# REQUEST/RESPONSE PROTOCOL TESTS
# ============================================================================


class TestProtocol:
    """Tests for Request/Response binary protocol"""

    def test_request_compile(self, test_message_type):
        """Test Request compilation to bytes"""
        content = b"Hello World"
        request = Request(test_message_type, content)
        compiled = request.compile()

        # Header should be 62 bytes + content
        assert len(compiled) == 62 + len(content)
        assert isinstance(compiled, bytes)

    def test_request_parse_roundtrip(self, test_message_type):
        """Test parsing bytes back to Response"""
        content = b"Test Content 123"

        # Compile
        request = Request(test_message_type, content)
        request_id = request.request_id
        compiled = request.compile()

        # Parse
        response = Request.parse(compiled)

        assert response.type.code == test_message_type.code
        assert response.content == content
        assert response.request_id == request_id
        assert response.latency >= 0

    def test_request_id_auto_generation(self, test_message_type):
        """Test that request_id is auto-generated"""
        request = Request(test_message_type, b"test")

        assert request.request_id is not None
        assert len(request.request_id) > 0
        # Should be UUID format
        assert "-" in request.request_id

    def test_request_id_custom(self, test_message_type):
        """Test custom request_id"""
        custom_id = "my-custom-id-12345"
        request = Request(test_message_type, b"test", request_id=custom_id)

        assert request.request_id == custom_id

    def test_request_id_preservation(self, test_message_type):
        """Test that request_id is preserved in round-trip"""
        import uuid

        request_id = str(uuid.uuid4())

        request = Request(test_message_type, b"test", request_id=request_id)
        compiled = request.compile()
        response = Request.parse(compiled)

        assert response.request_id == request_id

    def test_hash_integrity_valid(self, test_message_type):
        """Test that valid hash passes integrity check"""
        request = Request(test_message_type, b"Valid content")
        compiled = request.compile()

        # Should parse without error
        response = Request.parse(compiled)
        assert response.content == b"Valid content"

    def test_hash_integrity_corrupted(self, test_message_type):
        """Test that corrupted hash is detected"""
        request = Request(test_message_type, b"Hello")
        compiled = request.compile()

        # Corrupt the content (after header)
        corrupted = bytearray(compiled)
        corrupted[62] = (corrupted[62] + 1) % 256  # Change first byte of content

        with pytest.raises(RequestError) as exc_info:
            Request.parse(bytes(corrupted))

        assert "Hash mismatch" in str(exc_info.value)

    def test_size_mismatch_detection(self, test_message_type):
        """Test that size mismatches are detected"""
        request = Request(test_message_type, b"Test")
        compiled = request.compile()

        # Add extra bytes
        corrupted = compiled + b"EXTRA"

        with pytest.raises(RequestError) as exc_info:
            Request.parse(corrupted)

        assert "mismatch" in str(exc_info.value)

    def test_unknown_message_type(self):
        """Test parsing with unknown message type code"""
        # Create a request with a valid type
        msg_type = MessageType(code=255, name="temp")
        request = Request(msg_type, b"test")
        compiled = request.compile()

        # Manually change the type code in the compiled data to unknown code
        corrupted = bytearray(compiled)
        # Type code is first 2 bytes (big-endian unsigned short)
        corrupted[0] = 0xFF  # 65535
        corrupted[1] = 0xFE

        with pytest.raises(RequestError) as exc_info:
            Request.parse(bytes(corrupted))

        assert "Unknown message type" in str(exc_info.value)

    def test_large_content(self, test_message_type):
        """Test handling large content"""
        large_content = b"X" * 10000  # 10KB

        request = Request(test_message_type, large_content)
        compiled = request.compile()
        response = Request.parse(compiled)

        assert response.content == large_content
        assert len(response.content) == 10000

    def test_empty_content(self, test_message_type):
        """Test handling empty content"""
        request = Request(test_message_type, b"")
        compiled = request.compile()
        response = Request.parse(compiled)

        assert response.content == b""

    def test_latency_calculation(self, test_message_type):
        """Test latency property calculation"""
        request = Request(test_message_type, b"test")
        compiled = request.compile()

        time.sleep(0.01)  # Small delay

        response = Request.parse(compiled)

        # Latency should be positive
        assert response.latency >= 0


# ============================================================================
# SENDER TESTS
# ============================================================================


class TestSender:
    """Tests for Sender class"""

    def test_sender_client_mode_requires_socket(self):
        """Test that CLIENT mode requires a socket"""
        with pytest.raises(SenderError):
            Sender(mode=Mode.CLIENT, conn=None)

    def test_sender_server_mode(self):
        """Test creating sender in SERVER mode"""
        sender = Sender(mode=Mode.SERVER)
        assert sender.mode == Mode.SERVER
        assert not sender.is_client


# ============================================================================
# CLIENT/SERVER INTEGRATION TESTS
# ============================================================================


class TestClientServer:
    """Integration tests for Client and Server"""

    def test_basic_connection(self):
        """Test basic server-client connection"""
        config_server = ServerConfig(host="127.0.0.1", port=19999)
        server = Server(config_server)

        messages_received = []

        def on_message(_client, response):
            messages_received.append(response.content)

        server.set_callback(Events.ON_RECV, on_message)
        server.start()
        time.sleep(0.3)

        # Client connects
        config_client = ClientConfig(server_addr="127.0.0.1", port=19999)
        client = Client(config_client)

        assert client.connect()
        time.sleep(0.2)

        # Send message
        msg_type = MessageType(code=300, name="test_basic")
        sender = client.get_sender()
        request = Request(msg_type, b"Hello Server")
        sender.send(request)

        time.sleep(0.3)

        # Verify
        assert len(messages_received) > 0
        assert messages_received[0] == b"Hello Server"

        # Cleanup
        client.disconnect()
        server.close_all()

    def test_client_reconnect(self):
        """Test client disconnect and reconnect"""
        config_server = ServerConfig(host="127.0.0.1", port=19998)
        server = Server(config_server)
        server.start()
        time.sleep(0.3)

        config_client = ClientConfig(server_addr="127.0.0.1", port=19998)
        client = Client(config_client)

        # First connection
        assert client.connect()
        time.sleep(0.2)
        assert client.is_connected

        # Disconnect
        client.disconnect()
        time.sleep(0.2)
        assert not client.is_connected

        # Cleanup
        server.close_all()

    def test_server_on_connect_callback(self):
        """Test server ON_CONNECT callback"""
        config_server = ServerConfig(host="127.0.0.1", port=19997)
        server = Server(config_server)

        connected_clients = []

        def on_connect(client_):
            connected_clients.append(client_.addr)

        server.set_callback(Events.ON_CONNECT, on_connect)
        server.start()
        time.sleep(0.3)

        config_client = ClientConfig(server_addr="127.0.0.1", port=19997)
        client = Client(config_client)
        client.connect()

        time.sleep(0.3)

        assert len(connected_clients) == 1

        # Cleanup
        client.disconnect()
        server.close_all()

    def test_multiple_clients(self):
        """Test server handling multiple clients"""
        config_server = ServerConfig(host="127.0.0.1", port=19996, max_connection=3)
        server = Server(config_server)
        server.start()
        time.sleep(0.3)

        clients = []
        for _i in range(3):
            config = ClientConfig(server_addr="127.0.0.1", port=19996)
            client = Client(config)
            assert client.connect()
            clients.append(client)
            time.sleep(0.2)

        time.sleep(0.3)
        assert len(server.clients) == 3

        # Cleanup
        for client in clients:
            client.disconnect()
        server.close_all()

    def test_broadcasting(self):
        """Test server broadcasting to multiple clients"""
        config_server = ServerConfig(host="127.0.0.1", port=19995, max_connection=3)
        server = Server(config_server)
        server.start()
        time.sleep(0.3)

        # Create clients with message tracking
        clients = []
        messages_received = [[], [], []]

        for i in range(3):
            config = ClientConfig(server_addr="127.0.0.1", port=19995)
            client = Client(config)

            # Capture index in closure
            def make_callback(index):
                def callback(response):
                    messages_received[index].append(response.content)

                return callback

            client.set_callback(Events.ON_RECV, make_callback(i))
            client.connect()
            clients.append(client)
            time.sleep(0.2)

        time.sleep(0.3)

        # Broadcast message
        msg_type = MessageType(code=301, name="broadcast_test")
        broadcast_msg = Request(msg_type, b"Broadcast to all")
        sender = server.get_sender()
        sender.broadcast(broadcast_msg, server.get_all_clients_sockets())

        time.sleep(0.5)

        # All clients should receive the message
        for msgs in messages_received:
            assert len(msgs) > 0
            assert msgs[0] == b"Broadcast to all"

        # Cleanup
        for client in clients:
            client.disconnect()
        server.close_all()

    def test_broadcast_with_exclusion(self):
        """Test broadcasting with client exclusion"""
        config_server = ServerConfig(host="127.0.0.1", port=19994, max_connection=3)
        server = Server(config_server)
        server.start()
        time.sleep(0.3)

        # Create 3 clients
        clients = []
        messages_received = [[], [], []]

        for i in range(3):
            config = ClientConfig(server_addr="127.0.0.1", port=19994)
            client = Client(config)

            def make_callback(index):
                def callback(response):
                    messages_received[index].append(response.content)

                return callback

            client.set_callback(Events.ON_RECV, make_callback(i))
            client.connect()
            clients.append(client)
            time.sleep(0.2)

        time.sleep(0.3)

        # Broadcast excluding first client
        msg_type = MessageType(code=302, name="selective_broadcast")
        broadcast_msg = Request(msg_type, b"Not for everyone")
        sender = server.get_sender()

        # Exclude first client
        exclude_socket = server.clients[0].conn
        sender.broadcast(
            broadcast_msg, server.get_all_clients_sockets(), except_clients=[exclude_socket]
        )

        time.sleep(0.5)

        # First client should not receive
        assert len(messages_received[0]) == 0

        # Others should receive
        assert len(messages_received[1]) > 0
        assert len(messages_received[2]) > 0

        # Cleanup
        for client in clients:
            client.disconnect()
        server.close_all()


# ============================================================================
# PING/PONG TESTS
# ============================================================================


class TestPingPong:
    """Tests for PING/PONG functionality"""

    def test_client_ping_server(self):
        """Test client pinging server"""
        config_server = ServerConfig(host="127.0.0.1", port=19993)
        server = Server(config_server)
        server.start()
        time.sleep(0.3)

        config_client = ClientConfig(server_addr="127.0.0.1", port=19993)
        client = Client(config_client)
        client.connect()
        time.sleep(0.2)

        # Ping server
        latency = client.ping_server(timeout=2.0)

        assert latency is not None
        assert latency >= 0
        assert latency < 2000  # Should be under 2 seconds

        # Cleanup
        client.disconnect()
        server.close_all()

    def test_server_ping_client(self):
        """Test server pinging client"""
        config_server = ServerConfig(host="127.0.0.1", port=19992)
        server = Server(config_server)

        ping_results = []

        def on_connect(client3):
            print(f"Callback called for client: {client3}")

            def ping_callback(latency):
                ping_results.append(latency)
                print(f"Latency: {latency}")

            server.ping_client_async(client3, ping_callback, timeout=2.0)

        server.set_callback(Events.ON_CONNECT, on_connect)
        print("Callback set, starting server...")
        server.start()
        time.sleep(0.3)

        print("Creating client...")
        config_client = ClientConfig(server_addr="127.0.0.1", port=19992)
        client = Client(config_client)
        print("Connecting client...")
        client.connect()
        print("Client connected, waiting...")

        time.sleep(0.5)

        print(ping_results)

        assert len(ping_results) > 0
        assert ping_results[0] is not None
        assert ping_results[0] >= 0

        # Cleanup
        client.disconnect()
        server.close_all()

    def test_ping_timeout(self):
        """Test ping timeout handling"""
        config_server = ServerConfig(host="127.0.0.1", port=19991)
        server = Server(config_server)
        server.start()
        time.sleep(0.3)

        config_client = ClientConfig(server_addr="127.0.0.1", port=19991)
        client = Client(config_client)
        client.connect()
        time.sleep(0.2)

        # Very short timeout should work or timeout gracefully
        latency = client.ping_server(timeout=0.001)

        # Either returns latency or None (timeout)
        assert latency is None or latency >= 0

        # Cleanup
        client.disconnect()
        server.close_all()


# ============================================================================
# SEND_AND_WAIT TESTS
# ============================================================================


class TestSendAndWait:
    """Tests for send_and_wait functionality"""

    def test_client_send_and_wait(self):
        """Test client send_and_wait"""
        config_server = ServerConfig(host="127.0.0.1", port=19990)
        server = Server(config_server)

        # Server echoes back
        def on_message(client3, response3):
            echo = Request(response3.type, response3.content, request_id=response3.request_id)
            server.get_sender().send(echo, client=client3.conn)

        server.set_callback(Events.ON_RECV, on_message)
        server.start()
        time.sleep(0.3)

        config_client = ClientConfig(server_addr="127.0.0.1", port=19990)
        client = Client(config_client)
        client.connect()
        time.sleep(0.2)

        # Send and wait
        msg_type = MessageType(code=303, name="echo_test")
        request = Request(msg_type, b"Echo this message!")

        response = client.send_and_wait(request, timeout=2.0)

        assert response is not None
        assert response.content == b"Echo this message!"
        assert response.request_id == request.request_id

        # Cleanup
        client.disconnect()
        server.close_all()

    def test_server_send_and_wait(self):
        """Test server send_and_wait"""
        config_server = ServerConfig(host="127.0.0.1", port=19989)
        server = Server(config_server)
        server.start()
        time.sleep(0.3)

        # Client echoes back
        config_client = ClientConfig(server_addr="127.0.0.1", port=19989)
        client = Client(config_client)

        def on_message(response2):
            echo = Request(response2.type, response2.content, request_id=response2.request_id)
            client.get_sender().send(echo)

        client.set_callback(Events.ON_RECV, on_message)
        client.connect()
        time.sleep(0.3)

        # Server sends and waits
        msg_type = MessageType(code=304, name="server_echo")
        request = Request(msg_type, b"Server to client")

        client_info = server.clients[0]
        response = server.send_and_wait(request, client_info, timeout=2.0)

        assert response is not None
        assert response.content == b"Server to client"

        # Cleanup
        client.disconnect()
        server.close_all()

    def test_send_and_wait_timeout(self):
        """Test send_and_wait timeout"""
        config_server = ServerConfig(host="127.0.0.1", port=19988)
        server = Server(config_server)

        # Server does NOT respond
        def on_message(_client, _response):
            pass  # Ignore message

        server.set_callback(Events.ON_RECV, on_message)
        server.start()
        time.sleep(0.3)

        config_client = ClientConfig(server_addr="127.0.0.1", port=19988)
        client = Client(config_client)
        client.connect()
        time.sleep(0.2)

        # Send and wait with short timeout
        msg_type = MessageType(code=305, name="timeout_test")
        request = Request(msg_type, b"No response expected")

        response = client.send_and_wait(request, timeout=0.5)

        # Should timeout and return None
        assert response is None

        # Cleanup
        client.disconnect()
        server.close_all()


# ============================================================================
# LOGGER TESTS
# ============================================================================


class TestLogger:
    """Tests for Logger functionality"""

    def test_logger_singleton(self, reset_logger):
        """Test logger is a singleton"""
        logger1 = Logger.get_instance()
        logger2 = Logger.get_instance()

        assert logger1 is logger2

    def test_logger_levels(self, reset_logger):
        """Test different log levels"""
        logger: Logger = Logger.get_instance()

        # Should not raise
        logger.trace("Trace message")
        logger.debug("Debug message")
        logger.info("Info message")
        logger.success("Success message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

    def test_logger_level_filtering(self, reset_logger):
        """Test log level filtering"""
        config = LoggerConfig(level=LogLevel.WARNING)
        logger = Logger.get_instance(config)

        # These should be filtered out (not crash)
        logger.trace("Should be filtered")
        logger.debug("Should be filtered")
        logger.info("Should be filtered")

        # These should pass
        logger.warning("Should pass")
        logger.error("Should pass")

    def test_logger_enable_disable(self, reset_logger):
        """Test enabling/disabling logger"""
        logger = Logger.get_instance()

        logger.info("Enabled message")

        logger.disable()
        logger.info("Disabled message")  # Should not crash

        logger.enable()
        logger.info("Re-enabled message")

    def test_logger_set_level(self, reset_logger):
        """Test changing log level"""
        logger = Logger.get_instance()

        logger.set_level(LogLevel.ERROR)
        logger.debug("Should be filtered")
        logger.error("Should pass")

        logger.set_level(LogLevel.DEBUG)
        logger.debug("Should pass now")

    def test_logger_stats(self, reset_logger):
        """Test logger statistics"""
        logger = Logger.get_instance()

        logger.info("Info 1")
        logger.info("Info 2")
        logger.error("Error 1")

        stats = logger.get_stats()

        assert stats[LogLevel.INFO] == 2
        assert stats[LogLevel.ERROR] == 1


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Tests for error handling and exceptions"""

    def test_veltix_error_hierarchy(self):
        """Test exception hierarchy"""
        assert issubclass(MessageTypeError, VeltixError)
        assert issubclass(RequestError, VeltixError)
        assert issubclass(SenderError, VeltixError)

    def test_connection_refused(self):
        """Test connection to non-existent server"""
        config = ClientConfig(server_addr="127.0.0.1", port=11111)  # No server here
        client = Client(config)

        result = client.connect()
        assert not result
        assert not client.is_connected


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
