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
# (two directions: each side allocates its own outgoing IDs)
_id_allocator = IDAllocator(
    max_ids=...,          # client: 32768, server: min(config.id_window, 32768)
    offset=...,           # client: 0, server: 32768 (reserved upper half)
    is_pending=lambda rid: rid in self.request_handler.pending_requests,
)
```

```python
def allocate(self) -> int:
    with self._lock:
        start = self._counter
        while self._is_pending(self._offset + self._counter):
            self._counter = (self._counter + 1) % self._max
            if self._counter == start:
                raise IDsExhaustedError("all IDs are currently pending")
        current = self._offset + self._counter
        self._counter = (self._counter + 1) % self._max
        return current
```

The invariant is now airtight: **an ID is never reused while its previous
request is still pending.** The only way to run out is to have every single ID
of the pool in flight at the same time, which raises `IDsExhaustedError`
instead of corrupting traffic.

## The other hole: interleaving across directions

Pending-safe allocation only protects one allocator from itself. Veltix runs
**two** allocators on a connection (one per direction), and until v3.0.1 both
drew from the same flat space starting at `0`. The pending-safe property does
not help here: the two allocators are independent and know nothing about each
other's counters.

The wire contract says *a response is a response to whatever request carries
the same ID*. There is no direction marker on the wire, so the receiver cannot
tell an echo of its own request from an unsolicited request of the peer that
happens to carry the same numeric ID. When the server pushes or broadcasts
while the client has a pending `send_and_wait`, the peer's auto-assigned ID
frequently equals the pending ID (both counters start at zero and advance
together). `PendingRequestRule` then delivers the push as the response:

- `send_and_wait()` returns the wrong message; the real reply goes unhandled.
- `broadcast()` used to never allocate, so every broadcast carried ID 0 and
  stole the peer's **first** pending request every time.

## The fix: direction-scoped ID halves

Since v3.0.1 each side reserves one half of the 16-bit space:

- **Client:** `[0, 32768)` (bit 15 clear)
- **Server:** `[32768, 65536)` (bit 15 set)

This is the QUIC parity-bit trick, applied **per role** instead of per
connection. It needs no coordinator and no handshake change: the wire still
carries a plain `uint16` that the peer echoes back unchanged. Because the two
ranges are disjoint, an auto-assigned ID from one direction can never equal
an auto-assigned ID of the other, so an unsolicited push or broadcast can
never match a pending request of the opposite direction.

Responses always **echo** the request's ID, exactly as before; an explicit
`request_id` supplied by the caller is honored unchanged on the wire. The only
pattern this invalidates is replying to a request by sending a fresh
`Request(...)` with an auto-assigned ID and hoping both counters are in sync.
That pattern was only ever reliable by coincidence and must now use the echo
form (`Request(..., request_id=response.request_id)` or `req.respond()`).

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
uses `[id_window, id_window*2)`; every client got its own window via a global
`ClientAllocator`. That variant kills interleaving collisions too, but it costs
you:

- A global `ClientAllocator` that must assign offsets and be kept in sync with
  connection lifecycle.
- Reintroducing a coordinator where none should be needed.

v3.0.1 reuses the idea in its cheap form: **two fixed halves, split by role**
(client `[0, 32768)`, server `[32768, 65536)`), not by connection. No
coordinator, no per-client bookkeeping, and each side keeps a generous
32768-ID pool. The genuine costs of the v2 design (the coordinator) are what
make the fixed per-role split attractive: it is the same trick, minus the
machinery.

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
[0, 32768) and the server allocates from the reserved upper half
[32768, 65536); the server no longer announces `id_window` during the
handshake (`meta` is simply `{}`). Older peers still send and read
`meta.id_window` and fall back to 30000 if absent, so the change is transparent
on the wire and the protocol MAJOR is untouched. `ServerConfig.id_window`
remains, validated to `1..65535`, and is clamped to 32768 at startup because
the client half of the space is reserved.

During a mixed-version window (new peer talking to a v3.0.0 peer), the old
peer still allocates from the full flat range, so a collision requires the old
peer's counter to have wrapped into the far side's half. It is far less likely
than the v3.0.0 behavior (where both sides started at 0), but only a full
upgrade removes it entirely.

## Source map

| Component                     | Role                                        |
|-------------------------------|---------------------------------------------|
| `network/id_allocator.py`     | Pending-safe, thread-safe ID pool           |
| `handler/rules.py`            | `PendingRequestRule`: dispatch reply to queue |
| `handler/request_handler.py`  | `pending_requests` map + `register/unregister/wait` |
| `network/sender.py`           | Auto-assigns IDs at send time               |
| `network/request.py`          | 2-byte ID serialization + echo via `respond()` |
| `client/client.py`            | Client-side register-before-send order      |