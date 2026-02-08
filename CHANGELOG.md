# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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