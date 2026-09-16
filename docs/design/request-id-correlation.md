# Request-ID Correlation

> How Veltix correlates requests and responses over raw TCP, why the naive
> approach is broken, and how the design avoids collisions without a global
> coordinator.

## The problem

TCP is a byte stream: there is no native notion of a request or a response.
`recv()` gives you a sequence of bytes, but nothing tells you which request a
given payload answers. To build `send_and_wait()`, `ping`, or any
request/response RPC pattern, the protocol needs a correlation mechanism.

HTTP solves this with a strict one-response-per-request ordering. Veltix has no
such constraint: any peer can send several requests at once, and replies may
interleave. So each frame carries a **request ID** that ties a response to its
request.

## The wire contract

Every frame header embeds a 2-byte `request_id` (big-endian, range `0..65535`).
The flow is always the same:

1. The sender allocates an ID and stamps its request with it.
2. The receiver extracts the ID and **echoes it** unchanged in its reply.
3. The requester matches the incoming response against its pending map by ID.

That echo is the entire correlation contract. A response is a response to
whatever request carries the same ID on the wire. No sessions, no sequence
negotiation, no bookkeeping at the application layer.

A `ping` round-trip looks like this:

```
   Client                              Server
     |  allocate(-> 0)                   |
     |  register(0)                      |
     |  --- Request(PING, id=0) -------> |
     |                                   |  rule: PingRule
     |  <-- Response(PONG, id=0) ------- |
     |  rule: PendingRequestRule         |
     |  match! queue[0].put(response)    |
     |  wait() returns                   |
```

Because there are **two directions** on a connection, Veltix runs two allocators:
one on the server (for server-initiated requests such as `ping_client`) and one
on the client (for client-initiated calls such as `send_and_wait`). Each side
tracks only its **outgoing** IDs.

## The subtle bug: wrap-around collision

The ID space fits in 16 bits, so it wraps. A monotonic counter that cycles
`0, 1, ..., 65534, 65535, 0, ...` reuses an ID every 65536 requests. That is
fine... until the previously used ID still has a pending request on the wire.

If the requester allocated `id=7`, sent a request, and is still waiting for the
reply, a counter that wraps back around to `7` for a *new* request will make the
**old** reply (whenever it finally arrives) satisfy the **new** request. The two
responses land in the wrong queues and `send_and_wait()` returns the wrong
answer, silently.

Until recent versions this was a probabilistic bet: with a 30000-ID window and
short-lived requests the odds are low, but they are not zero. Latency spikes,
retries, or a burst near the wrap point make it simply a matter of time. A
network library must not ship a data-corruption bug with a convincing probability
of staying hidden.

## The fix: pending-safe allocation

The allocator does not just increment. It asks the `RequestHandler` whether a
candidate ID is still in flight before handing it out, and skips it if so:

```python
_id_allocator = IDAllocator(
    max_ids=...,  # server: config.id_window, client: 65535
    is_pending=lambda rid: rid in self.request_handler.pending_requests,
)
```

```python
def allocate(self) -> int:
    with self._lock:
        start = self._counter
        while self._is_pending(self._counter):
            self._counter = (self._counter + 1) % self._max
            if self._counter == start:
                raise IDsExhaustedError("all IDs are currently pending")
        current = self._counter
        self._counter = (self._counter + 1) % self._max
        return current
```

The invariant is now airtight: **an ID is never reused while its previous
request is still pending.** The only way to run out is to have every single ID
of the pool in flight at the same time, which raises `IDsExhaustedError`
instead of corrupting traffic.

Two properties make this design noteworthy:

- **One source of truth.** The allocator has no opinion about which IDs are
  busy. It delegates to `RequestHandler.pending_requests`, the same map that
  `send_and_wait()` registers and unregisters against. There is no second
  bookkeeping structure to keep in sync.
- **No global coordinator.** Each allocator is local to one peer direction.
  The server does not need to tell clients which IDs they may use, and clients
  do not need to agree with each other. Correlation stays a purely per-connection
  concern.

## The lifecycle of a request

The reader must never race with the sender. `send_and_wait()` therefore
**registers before it sends**:

```python
request_id = self._id_allocator.allocate()

self.request_handler.register(request_id)   # put a queue in pending_requests

if not self.sender.send(request):            # send the frame
    self.request_handler.unregister(request_id)
    return None

return self.request_handler.wait(request_id, timeout)  # block for the reply
```

Registering first guarantees that a response which arrives instantly (single
hop on loopback) still finds its queue already present.

On the receiving side, an incoming frame is run through the rule chain.
`PendingRequestRule` is the correlation dispatcher:

1. `can_handle()`: is `response.request_id` in `pending_requests`?
2. `try_handle()`: push the response into the matching queue under the lock.

If it matches, `wait()` wakes up with the response; if the timeout expires
first, the pending entry is unregistered so the ID becomes allocatable again.

## Why not the alternatives?

To highlight the design, here is what it deliberately avoids.

**Split ID ranges (what v2.0.0 shipped).** Server uses `[0, id_window)`, client
uses `[id_window, id_window*2)`; every client got its own window via a
`ClientAllocator`. This is the same trick QUIC uses with stream-ID parity bits.
It kills interleaving collisions by construction, but it costs you:

- Half (or more) of your ID space for ranges you will rarely saturate.
- A global `ClientAllocator` that must assign offsets and be kept in sync with
  connection lifecycle.
- Reintroducing a coordinator where none should be needed.

**Monotonic counter without skip.** Zero overhead, but the wrap-around
collision above. Every in-flight ID at the boundary is a latent misroute.

**UUIDs or full 32-bit random IDs.** No collisions to speak of, but a fatter
header on every frame, and you still have to filter stale replies yourself. The
skip-based allocator gives determinism with a 2-byte ID.

**Strict request/response serialization (HTTP/1.1 style).** Trivial to
implement, but forfeits pipelining and halves throughput for RPC bursts. Veltix
routes callbacks through a thread pool and wants many concurrent in-flight
calls per connection.

The chosen design is the one that gets determinism (no collisions), a dense
2-byte ID, and no cross-connection coordination at the same time.

## Wire compatibility notes

The ID window is a purely local concern now: the client allocator is fixed at
65535 and the server no longer announces `id_window` during the handshake
(`meta` is simply `{}`). Older peers still send and read `meta.id_window` and
fall back to 30000 if absent, so the change is transparent on the wire and the
protocol MAJOR is untouched. `ServerConfig.id_window` remains, validated to
`1..65535`, as the server-side pool size.

## Source map

| Component                     | Role                                        |
|-------------------------------|---------------------------------------------|
| `network/id_allocator.py`     | Pending-safe, thread-safe ID pool           |
| `handler/rules.py`            | `PendingRequestRule`: dispatch reply to queue |
| `handler/request_handler.py`  | `pending_requests` map + `register/unregister/wait` |
| `network/sender.py`           | Auto-assigns IDs at send time               |
| `network/request.py`          | 2-byte ID serialization + echo via `respond()` |
| `client/client.py`            | Client-side register-before-send order      |