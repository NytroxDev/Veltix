# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2026-02-15

### Fixed

- **CRITICAL**: Added thread locks to prevent race conditions in client/request handling
    - Added `_clients_lock` for thread-safe client list operations
    - Added `_pending_requests_lock` for thread-safe request tracking
    - Added `_threads_lock` for thread management
    - All shared data structures are now properly protected

### Added

- `Events.ON_DISCONNECT` callback support
    - Called automatically when a client disconnects
    - Allows cleanup logic on client disconnect
- `Request.respond(response)` helper method
    - Simplifies request-response correlation
    - No need to manually pass `request_id=...`

### Changed

- `ClientInfo` now includes `thread_id` for better thread management

## [1.2.0] - 2026-02-11

### Added

- **Integrated Logger System**: Production-ready logging with powerful features
    - `Logger.get_instance()` - Singleton logger accessible throughout the application
    - Colorful console output with ANSI colors for better readability
    - File logging with automatic rotation based on file size
    - Multiple log levels: TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL
    - Configurable via `LoggerConfig` with extensive options
    - Automatic caller information (file:line) tracking
    - Thread-safe implementation for multi-threaded applications
    - Optional async file writing for high-performance scenarios
    - Zero configuration required - works great with defaults
- **Comprehensive Logging**: Added detailed logging throughout the entire codebase
    - Client operations (connect, disconnect, send, receive)
    - Server operations (start, stop, client handling)
    - Network operations (data transmission, parsing)
    - Error conditions with detailed context
    - Request/response tracking with request IDs
- **Enhanced Sender**: Improved broadcasting capabilities
    - `except_clients` parameter to exclude specific clients from broadcasts
    - Better error reporting and statistics
    - Detailed logging of broadcast operations
    - Success rate tracking for broadcast operations
- **Foundation for v1.3.0**: Prepared infrastructure for handshake system
    - HELLO message type added to system types
    - Architecture ready for connection handshake protocol
    - Base structure for client authentication

### Changed

- **API Improvements**: More intuitive method names
    - `bind()` → `set_callback()` for event binding
    - `Bindings` enum → `Events` enum for consistency
    - More descriptive variable names throughout
- **Security Enhancements**:
    - Improved error handling in network operations
    - Better data validation in request parsing
    - Enhanced exception handling with detailed error messages
    - More robust connection state management
- **Code Quality**:
    - Refactored multiple code sections for better maintainability
    - Improved type hints and documentation
    - Better separation of concerns
    - More consistent error handling patterns

### Fixed

- Minor bugs in connection handling
- Edge cases in broadcast operations
- Race conditions in multi-threaded scenarios
- Memory leaks in logger file rotation
- Improved socket cleanup on disconnection

### Technical

- Logger singleton pattern implementation
- File rotation with configurable backup count
- Async buffer flushing for file writes
- Enhanced exception hierarchy
- Better thread management in server
- Improved socket timeout handling

### Breaking Changes

- `bind()` method renamed to `set_callback()`
- `Bindings` enum renamed to `Events`

### Migration Guide

```python
# Before (v1.1.x)
from veltix import Bindings

server.bind(Bindings.ON_RECV, callback)
client.bind(Bindings.ON_RECV, callback)

# After (v1.2.0)
from veltix import Events

server.set_callback(Events.ON_RECV, callback)
client.set_callback(Events.ON_RECV, callback)
```

## [1.1.0] - 2026-02-08

### Added

- **Request/Response pattern**: New `send_and_wait()` method for synchronous request-response communication
    - Client-side: `client.send_and_wait(request, timeout=5.0)`
    - Server-side: `server.send_and_wait(request, client, timeout=5.0)`
    - Automatic response matching via UUID-based request tracking
    - Built-in timeout support to prevent infinite waiting
- **Built-in Ping/Pong functionality**:
    - `client.ping_server(timeout=2.0)` - Measure server latency from client
    - `server.ping_client(client, timeout=2.0)` - Measure client latency from server
    - Automatic PING/PONG message handling (no manual implementation needed)
    - Returns latency in milliseconds
- **Latency measurement**: `Response.latency` property calculates round-trip time automatically
- **UUID request tracking**: All requests now have a unique `request_id` for matching responses

### Fixed

- UUID formatting in request/response parsing (now properly maintains UUID format with hyphens)
- Request ID preservation in PING/PONG responses

### Technical

- Added `_pending_requests` queue system for managing async responses
- Improved message routing logic to handle both callbacks and waiting requests
- Enhanced protocol to include 16-byte UUID field in message header

## [1.0.0] - 2026-02-06

### Added

- TCP Server with multi-threading support
- TCP Client with event-driven callbacks
- Binary protocol with SHA256 integrity verification
- Custom MessageType system with code ranges:
    - 0-199: System messages
    - 200-499: User messages
    - 500+: Plugin messages
- Event binding system (ON_RECV, ON_CONNECT)
- Zero dependencies - pure Python stdlib only
- Message broadcasting to multiple clients
- Automatic message integrity checks
- Thread-safe client handling

### Features

- Message integrity verification using SHA256 hashing
- Extensible message types via MessageTypeRegistry
- Event-driven callbacks for clean code organization
- Multi-threaded server handling multiple connections
- Simple and intuitive API design

### Initial Release

- Core networking functionality
- Complete documentation
- Example implementations (echo server, chat server)
- MIT License