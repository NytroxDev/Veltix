# Performance

> Benchmarked on Python 3.14.5 : 12-core CPU (6 physical), 30.5 GB RAM, Linux (loopback).
> All numbers are **5-run averages** (`--runs 5`). Latency uses **250 000 iterations** (`--latency-iterations 250000`).

To run the benchmarks yourself:

```bash
# Run all benchmarks on both backends
python -m veltix.benchmark --socket-core both --runs 5

# Run specific benchmarks
python -m veltix.benchmark --only memory latency burst --socket-core both

# Save results to JSON
python -m veltix.benchmark --save results.json
```

---

## Side-by-Side Summary

| Metric                              | Threading        | Async            |
|-------------------------------------|------------------|------------------|
| Idle server memory                  | 20.8 KB          | 4 KB             |
| Per client memory (avg)             | 34.5 KB          | 12.4 KB          |
| Average latency                     | 0.033 ms         | 0.036 ms         |
| Burst send                          | 49 287 msg/s     | 49 878 msg/s     |
| Burst receive                       | 39 517 msg/s     | 39 909 msg/s     |
| Concurrent stress (100 clients)     | 32 297 msg/s     | **82 937 msg/s** |
| FPS simulation (64 players @ 64Hz)  | 4 490 msg/s      | 4 491 msg/s      |
| FPS simulation (128 players @ 20Hz) | 2 813 msg/s      | 2 813 msg/s      |

> **Async stress throughput is 2.6x higher** than Threading — the selectors-based single-thread model eliminates context-switch overhead under high concurrency.
> Both backends score similarly on FPS simulations (bottleneck is the simulation logic, not the transport layer).

---

## Memory Footprint

### Threading

| Metric               | Value                |
|----------------------|----------------------|
| Idle server          | +20.8 KB above Python baseline |
| Per client (avg)     | 34.5 KB              |
| Per client (min/max) | 16.8 KB / 39.2 KB    |
| Per client (median)  | 37.2 KB              |
| Per client (stdev)   | 7.5 KB               |
| Server + 10 clients  | 23.1 MB              |
| Server + 50 clients  | 24.6 MB              |
| RSS after teardown   | +362 KB (leak delta) |

### Async

| Metric               | Value                |
|----------------------|----------------------|
| Idle server          | +4 KB above Python baseline |
| Per client (avg)     | 12.4 KB              |
| Per client (min/max) | 4 KB / 16 KB         |
| Server + 10 clients  | 23.2 MB              |
| Server + 50 clients  | 23.8 MB              |
| RSS after teardown   | +22 KB (leak delta)  |

> Threading idle server dropped **54%** (45.6 KB → 20.8 KB) and per-client cost dropped slightly (36.1 KB → 34.5 KB).
> Async idle and per-client costs remain unchanged; leak delta stable at ~22 KB (mostly warm CPU caches).

---

## Ping / Pong Latency

250 000 iterations per backend, 100% success rate.

### Threading

| Metric     | Value         |
|------------|---------------|
| Average    | 0.033 ms      |
| Median P50 | 0.031 ms      |
| P95        | 0.039 ms      |
| P99        | 0.062 ms      |
| Min        | 0.026 ms      |
| Max        | 1.056 ms      |
| Stdev      | 0.008 ms      |
| Jitter     | 0.008 ms      |
| Throughput | 28 524 ping/s |

### Async

| Metric     | Value         |
|------------|---------------|
| Average    | 0.036 ms      |
| Median P50 | 0.035 ms      |
| P95        | 0.043 ms      |
| P99        | 0.066 ms      |
| Min        | 0.029 ms      |
| Max        | 2.109 ms      |
| Stdev      | 0.009 ms      |
| Jitter     | 0.010 ms      |
| Throughput | 25 701 ping/s |

> Threading has slightly lower latency (no selectors round-trip), but both backends remain well under 0.1 ms P99.
> Async shows lower stdev (more consistent) due to the single-thread scheduling.

---

## FPS Server Simulation

Both backends score identically (simulation logic is the bottleneck, not the transport layer).

| Scenario    | Tick rate                    | Throughput  | Success |
|-------------|------------------------------|-------------|---------|
| 64 players  | 63.8 Hz actual (target 64Hz) | 4 490 msg/s | 100%    |
| 128 players | 20.0 Hz actual (target 20Hz) | 2 813 msg/s | 100%    |

Zero overruns, zero lost messages in both scenarios.

---

## Burst Throughput

10 000 messages × 64 bytes.

### Threading

| Metric         | Value        |
|----------------|--------------|
| Send           | 49 287 msg/s |
| Receive        | 39 517 msg/s |
| Data rate      | 2.41 MB/s    |
| Success rate   | 100%         |
| Total duration | 253.0 ms     |

### Async

| Metric         | Value        |
|----------------|--------------|
| Send           | 49 878 msg/s |
| Receive        | 39 909 msg/s |
| Data rate      | 2.44 MB/s    |
| Success rate   | 100%         |
| Total duration | 251.0 ms     |

> Burst throughput slightly lower in this run; both backends remain within 1% of each other.
> Async recovers burst performance to within ~5% of v1.6.10 after hot-path optimisations (broadcast compile-once, unpack_from, bytearray passthrough).

---

## Concurrent Stress

100 clients firing 100 messages simultaneously (10 000 total).

### Threading

| Metric             | Value        |
|--------------------|--------------|
| Throughput         | 32 297 msg/s |
| Success rate       | 100%         |
| Total duration     | 310.0 ms     |
| Time to first recv | 1.8 ms       |
| Per-client avg     | 4 244 msg/s  |
| Per-client stdev   | 1 125 msg/s  |

### Async

| Metric             | Value         |
|--------------------|---------------|
| Throughput         | **82 937 msg/s** |
| Success rate       | 100%          |
| Total duration     | **121.0 ms**  |
| Time to first recv | 1.8 ms        |
| Per-client avg     | 9 332 msg/s   |
| Per-client stdev   | 8 626 msg/s   |

> **Async is 2.6x faster under stress** — single-thread selectors eliminate Python GIL contention between client-handler threads.
> Threading still handles 32k+ msg/s with zero failures; the GIL is the limiter at high concurrency.
