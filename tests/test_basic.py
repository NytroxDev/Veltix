"""
Basic tests for Veltix core functionality.

Run with: python -m pytest tests/test_basic.py
Or simply: python tests/test_basic.py
"""

import threading
import time

from Veltix import (
    Binding,
    Client,
    ClientConfig,
    MessageType,
    Request,
    RequestError,
    Response,
    Server,
    ServerConfig,
)

# Test message types
TEST_MSG = MessageType(code=200, name="test")


def test_message_type_creation():
    """Test creating a MessageType."""
    msg_type = MessageType(code=100, name="test", description="Test message")

    assert msg_type.code == 100
    assert msg_type.name == "test"
    assert msg_type.description == "Test message"
    print("✓ MessageType creation works")


def test_request_compile_and_parse():
    """Test Request compilation and Response parsing."""
    # Create request
    original_content = b"Hello Veltix!"
    request = Request(TEST_MSG, original_content)

    # Compile to bytes
    compiled = request.compile()
    assert isinstance(compiled, bytes)
    assert len(compiled) > 46  # Header is 46 bytes
    print("✓ Request compilation works")

    # Parse back to Response
    response = Request.parse(compiled)
    assert isinstance(response, Response)
    assert response.content == original_content
    assert response.type.code == TEST_MSG.code
    print("✓ Request parsing works")

    # Verify hash integrity
    import hashlib

    expected_hash = hashlib.sha256(original_content).digest()
    assert response.hash == expected_hash
    print("✓ Hash integrity verification works")


def test_server_client_communication():
    """Test basic server-client communication."""
    print("\nTesting server-client communication...")

    # Shared state
    received_messages = []
    server_ready = threading.Event()

    # Setup server
    server_config = ServerConfig(host="127.0.0.1", port=8765)
    server = Server(server_config)
    sender_server = server.get_sender()

    def on_server_recv(client, response):
        content = response.content.decode("utf-8")
        received_messages.append(f"server:{content}")

        # Echo back
        reply = Request(TEST_MSG, b"Echo: " + response.content)
        sender_server.send(reply, client=client.conn)

    server.bind(Binding.ON_RECV, on_server_recv)

    # Start server in thread
    def run_server():
        server.start(_on_th=True)
        server_ready.set()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    server_ready.wait(timeout=2)
    time.sleep(0.5)  # Give server time to start

    print("  Server started")

    # Setup client
    client_config = ClientConfig(server_addr="127.0.0.1", port=8765)
    client = Client(client_config)
    sender_client = client.get_sender()

    def on_client_recv(response):
        content = response.content.decode("utf-8")
        received_messages.append(f"client:{content}")

    client.bind(Binding.ON_RECV, on_client_recv)

    # Connect and send
    assert client.connect(), "Client failed to connect"
    print("  Client connected")
    time.sleep(0.2)

    # Send test message
    test_message = b"Test message"
    request = Request(TEST_MSG, test_message)
    assert sender_client.send(request), "Failed to send message"
    print("  Message sent")

    # Wait for response
    time.sleep(0.5)

    # Verify
    assert len(received_messages) >= 1, (
        f"No messages received. Got: {received_messages}"
    )
    assert "server:Test message" in received_messages, "Server didn't receive message"
    assert any("client:Echo" in msg for msg in received_messages), (
        "Client didn't receive echo"
    )

    print("  Messages exchanged successfully")

    # Cleanup
    client.disconnect()
    server.close_all()
    time.sleep(0.2)

    print("✓ Server-client communication works")


def test_message_integrity_check():
    """Test that corrupted messages are rejected."""
    # Create valid request
    request = Request(TEST_MSG, b"Valid content")
    compiled = request.compile()

    # Corrupt the data (change a byte in the content)
    corrupted = bytearray(compiled)
    corrupted[-1] ^= 0xFF  # Flip last byte

    # Should raise ValueError due to hash mismatch
    try:
        Request.parse(bytes(corrupted))
        assert False, "Should have raised ValueError for corrupted data"
    except RequestError as e:
        assert "Invalid hash" in str(e) or "Corrupted" in str(e)
        print("✓ Message integrity check works (corrupted data rejected)")


# Run tests
if __name__ == "__main__":
    print("Running Veltix Basic Tests")
    print("=" * 50)

    try:
        test_message_type_creation()
        test_request_compile_and_parse()
        test_message_integrity_check()
        test_server_client_communication()

        print("\n" + "=" * 50)
        print("ALL TESTS PASSED! ✓")
        print("Veltix is ready to deploy! 🚀")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
