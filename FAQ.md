# Frequently Asked Questions

## Why create another networking library?

Raw sockets are fine, but too low-level. You have to rewrite dozens of components to get a system that can properly send
messages and manage clients cleanly. Libraries like Twisted or ZMQ have verbose APIs, are too complex, and too heavy.
Veltix turns raw sockets into a reliable, high-level tool while staying lightweight.

## Is Veltix production-ready?

Yes. Veltix has a stable API, extensive automated tests, and is already used in production projects. The main missing
networking feature is built-in TLS support, so for applications exposed directly to the Internet, you should either wait
for TLS support or secure the transport externally.

## How many simultaneous connections can Veltix handle?

The maximum number of connections depends on the hardware, operating system, backend, and workload. Hundreds of
concurrent clients are realistic on modern hardware, but file transfers or large messages naturally reduce that number.

## Does Veltix support encryption / TLS?

TLS support is planned after the core networking layer has fully stabilized. In the meantime, encryption can be provided
externally through tools such as stunnel, WireGuard, or a reverse proxy.

## Is Veltix compatible with asyncio?

Veltix is not an async framework, and that's intentional. No asyncio support is planned for the near future. It's
technically possible to use Veltix alongside asyncio, but it's not optimal and not officially supported.

## Is Veltix cross-platform (Windows, macOS)?

Yes. Veltix is designed to support most operating systems, even older ones. However, since the author primarily develops
on Linux, some platform-specific bugs may exist. If you find one, please open an issue.

## Can Veltix work over the Internet (WAN) or only LAN?

Veltix is not limited to LAN. However, for serious WAN applications, it's recommended to wait for encryption support.

## What is the maximum message size in Veltix?

By default, Veltix limits messages to 10 MB and the MessageBuffer to 20 MB. It's recommended to stay within 1-2 MB with
default settings. You can increase the buffer size to speed up reception of long messages.

## Does Veltix support message compression?

Not yet. Compression is planned for a future 3.x release and will use the flags system.

## Can I use Veltix for audio/video streaming?

For low-latency streaming, a UDP-based framework is recommended. Veltix could work for a prototype if latency isn't
critical. Native UDP support may be explored in the future, but it is not part of Veltix today.

## How do I update Veltix without breaking my project?

- Patch releases (3.0.0 → 3.0.1) never break the API.
- Minor releases (3.0.0 → 3.1.0) may introduce new features but remain backward compatible.
- Major releases (3.x → 4.0) may contain breaking changes and always include a migration guide.

## Can I use Veltix in Docker / containerized environments?

Yes. Veltix has no specific constraints for containerization. Just expose the necessary ports. Veltix doesn't require
any special configuration inside containers.

## Can I send large files with Veltix?

Yes, as long as you split large files into chunks. Veltix handles framing and integrity. Increase the buffer size based
on your chunk size (slightly larger than the chunk is ideal), and use the THREADING backend if you have few clients.

## Does Veltix have external dependencies?

No. Veltix only requires Python 3.11+ and stdlib libraries. The Rust engine ships packed inside the
prebuilt wheels - no runtime toolchain or third-party packages are needed. You can clone the repo
and use it directly without even running `pip install`.

## Does Veltix support Python 3.10 or below?

No. Veltix requires Python 3.11+ (3.10 is end-of-life), so it can use modern syntax and stdlib
features.

## What is the Rust engine in v3.0.0?

Since v3.0.0, the message hot path (parsing, compilation, buffering) is compiled in Rust via PyO3
and ships as a `cp311-abi3` extension inside the prebuilt wheels. It is used automatically when
available; otherwise Veltix falls back to the pure-Python implementation transparently. Set
`VELTIX_DISABLE_RUST=1` to force the fallback, or call `veltix.disable_rust()` / `veltix.enable_rust()`
at runtime (the switch is captured at each `Server`/`Client` initialization; `Server.restart()`
re-captures it). Check `veltix.network._rust.rust_enabled()` for the current decision.
It cuts P99 latency by **-41%**, jitter by **-68%**, and raises 100-client stress throughput by
**+23%** - see [PERFORMANCE.md](PERFORMANCE.md).

## How do I debug connection issues with Veltix?

The built-in logger can help with many cases. Make sure there are no OS-level or hardware issues. If you believe the
problem comes from Veltix, please open an issue.

## What's the difference between the THREADING and ASYNC backends?

- **THREADING**: Uses one thread per connection. Easy to debug, good for high message throughput with few clients and
  low latency.
- **ASYNC**: Based on selectors, uses a single thread. Much lighter on memory. Ideal for many clients without excessive
  RAM usage.

See the README and PERFORMANCE.md for benchmarks.

## Can Veltix work with proxies or load balancers?

Veltix uses raw TCP, not HTTP. Classic web proxies (like HTTP reverse proxies) are not compatible.

However, TCP-level proxies and load balancers can work with Veltix as long as they forward data without modifying the
stream. A TCP load balancer can distribute connections while keeping the Veltix protocol intact.

Since Veltix maintains per-client state and uses persistent connections, load balancing must typically happen at the
connection level, not the message level.

For large deployments, choose infrastructure suited for long-lived TCP connections.

## Can Veltix be used for IoT or low-power devices?

It depends on the device and the use case.

Veltix is designed for Python applications on standard systems. It works well for IoT gateways, Raspberry Pi, local
controllers, or any device capable of running Python.

However, Veltix is not intended for extremely resource-constrained devices like microcontrollers with a few kilobytes of
memory or battery-powered sensors. For those, lighter protocols like MQTT, CoAP, or custom UDP protocols are better
suited.

Veltix is most relevant when the device needs reliable TCP communication and has the resources to run Python.

## Can Veltix run in non-blocking mode (without blocking the main thread)?

Yes. Veltix is designed to run in the background and doesn't require dedicating the main thread to network management.

```python
server.start()

# Your application continues here
game_loop()
render()
update()
```

The server accepts connections and processes messages in dedicated threads. User callbacks go through Veltix's request
handling system, preventing long operations from blocking network reception.

This makes Veltix suitable for applications that already have a main loop, like games, GUIs, simulations, or real-time
tools.

## Can Veltix be used for inter-process communication (IPC)?

Yes. Since Veltix uses TCP sockets, it can be used for communication between multiple processes on the same machine via
localhost. This can be useful for splitting an application into multiple components (GUI, computation engine, background
service, etc.).

For extremely specialized IPC needs with very low latency constraints, solutions like Unix sockets or shared memory may
be more appropriate.

## Does Veltix handle automatic reconnection?

Yes. The Veltix client has a configurable automatic reconnection system. On connection loss, it can retry multiple times
with a delay between each attempt.

Registered callbacks and routes are preserved after reconnection, allowing the client to resume normal operation without
manual reinitialization.

Reconnection can be disabled (`retry=0`) or cancelled dynamically with `client.stop_retry()`.

## Can Veltix be used for online multiplayer games?

Yes. Veltix works well for multiplayer games where reliability matters more than absolute latency: co-op games, strategy
games, turn-based games, private servers, LAN games, sync tools, or prototypes.

Veltix automatically handles common client/server game elements: player connections, message routing, disconnection,
reconnection, data integrity, and bidirectional communication.

For competitive games requiring very low latency (fast FPS, fighting games, simulations needing dozens of updates per
second), a UDP or QUIC-based solution is generally better, as it prioritizes speed and packet loss tolerance over
absolute reliability.

## Does Veltix have an event system to monitor connection state?

Yes. Veltix integrates an event bus that lets you subscribe to key library events, including connections,
disconnections, reconnection attempts, and internal protocol events.

```python
from veltix.internal.events import ServerEvent

server.bus.subscribe(ServerEvent.ON_CONNECT, on_connect)
server.bus.subscribe(ServerEvent.ON_DISCONNECT, on_disconnect)
```

Higher-level callbacks (`on_connect()`, `on_disconnect()`, `on_recv()`) are also available for common use cases.

## How do I handle errors in Veltix?

Veltix follows Python's philosophy: errors should be explicit.

Programming errors (invalid payload, wrong parameters, etc.) raise standard exceptions that you can catch with `try` /
`except`.

Expected network errors (disconnection, timeout, connection loss, etc.) are signaled through callbacks, events, and
return values (`None`, `False`, etc.), to avoid turning normal situations into exceptions.

The built-in logger and Event Bus also help you easily monitor network activity for debugging.

## How do I contribute to Veltix?

The full guide is available in [CONTRIBUTING.md](CONTRIBUTING.md).
